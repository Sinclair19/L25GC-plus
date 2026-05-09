#!/usr/bin/env bash

ensure_mongodb() {
    if mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
        return
    fi

    echo "MongoDB is not reachable; starting mongod..."
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl start mongod
    else
        echo "ERROR: systemctl is not available; please start MongoDB before running CP NFs." >&2
        exit 1
    fi

    for _ in $(seq 1 20); do
        if mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; then
            echo "MongoDB is ready."
            return
        fi
        sleep 1
    done

    echo "ERROR: MongoDB did not become ready after starting mongod." >&2
    exit 1
}

run_nf() {
    local name=$1
    local core=$2
    echo "Starting $name on core $core..."
    NF_NAME=$name sudo -E taskset -c $core ./bin/$name > log/${name}.log 2>&1 &
    sleep 2
}

mkdir -p log
ensure_mongodb

run_nf nrf 5
run_nf amf 6
run_nf smf 7
run_nf udr 8
run_nf pcf 9
run_nf udm 10
run_nf nssf 11
run_nf ausf 12
run_nf chf 13

echo "All NFs started. Logs are in ./log/"
