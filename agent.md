# Agent Notes

This repo has a nested `NFs/onvm-upf` git repo/submodule. Changes inside it need a
commit in that nested repo first, then the parent repo records the updated
submodule pointer.

## Runtime Structure

- `scripts/run/run_onvm_mgr.sh` starts ONVM manager.
  - `-n` is the NF core mask. Default `0xFFF8` allows cores `3-15`.
  - To allow cores `3-15` plus `17`, use `-n 0x2FFF8`.
  - To allow only `3,4,5,17`, use `-n 0x20038`.
- `scripts/run/run_upf_lb.sh` starts UPF-LB.
  - `UPF_LB_CORE_ID=<core>` controls its DPDK `-l` core in simple mode.
- `scripts/run/run_upf_u.sh` starts UPF-U workers.
  - Simple mode accepts `UPF_U_CORE_ID=<core>`, but ONVM may still assign a
    different core unless the ONVM `-m` manual-core flag is passed.
  - Reliable manual binding:
    `./scripts/run/run_upf_u.sh -l 5 -- -m -r 14 -- ./NFs/onvm-upf/5gc/upf_u/config/upf_u.yaml`
    `./scripts/run/run_upf_u.sh -l 17 -- -m -r 15 -- ./NFs/onvm-upf/5gc/upf_u/config/upf_u.yaml`
- `scripts/run/run_upf_c.sh` starts UPF-C.
  - It now passes `UPF_PCAP_REPLAY_TEID` through `sudo env` so UPF-C can read it.
- `scripts/run/run_cp_nfs.sh` starts CP NFs with `taskset`.
- `NFs/onvm-upf/5gc/upf_c/n4_onvm_pfcp_handler.c` handles PFCP PDR/FAR/QER updates
  and classifier snapshot rebuilds.
- `NFs/onvm-upf/5gc/upf_u/upf_u.c` classifies packets against snapshots and applies
  PDR/FAR behavior.
- `NFs/onvm-upf/5gc/upf_lb/upf_lb.c` selects UPF-U workers using TEID/UE-IP session
  maps.
  - `UPF_LB_BENCH_DROP=1` enables pure LB benchmark mode: LB parses/selects a
    worker, increments its counters, then drops instead of forwarding to UPF-U.
    In this mode use `upf_lb rx_pps` as the LB processing rate; `tx_pps` should
    be near zero and `drop` will increase by design.
- `NFs/onvm-upf/onvm/upf/upf.c` owns shared session maps:
  `TEID -> UpfSession`, `UE IP -> UpfSession`, and session pool state.

## PCAP Replay TEID Alias

Old pktgen pcaps can fail after a CN restart because UPF shared memory loses
PFCP/session state, and new UE registrations may get different TEIDs. Logs look like:

- UPF-U: `CLS classify: no snapshot yet (ver=0) - dropping`
- UPF-U: `Couldn't classify the packet to a PDR`
- UPF-LB: `Not Found InsertTEIDtoSessionMap[33554432]`

Implemented test-only support in nested commit:

- `775f704 Add UPF pcap replay TEID aliases`
- Parent commit: `7c80688 Record UPF pcap replay TEID aliases`

Usage:

```bash
UPF_PCAP_REPLAY_TEID=2,6 ./scripts/run/run_upf_c.sh 2 ./NFs/onvm-upf/5gc/upf_c/config/upfcfg.yaml
```

`UPF_PCAP_REPLAY_TEID` accepts comma or whitespace separated host-order TEIDs.
It installs extra uplink classifier rules and TEID map aliases for the current
session. It does not create PFCP state by itself; one UE/PDU session still needs
to be established after restart so SMF installs PDR/FAR state.

## UERANSIM / Registration Findings

If `nr-ue` shows:

```text
Security Mode Command received
NAS timer[3510] expired
```

then this is before user-plane routing. `ue1tun` is not created because NAS
registration did not complete. Check AMF/CP logs rather than N3 routes first.

Useful checks on CN:

```bash
cd ~/L25GC-plus
grep -nE "Security|Registration|GMM|error|ERRO|WARN|supi|imsi|context" log/amf.log | tail -100
tail -80 log/nssf.log
tail -80 log/nrf.log
ps aux | grep -E './bin/(amf|smf|nrf|nssf|ausf|udm|udr|pcf|chf)' | grep -v grep
```

Observed AMF got through authentication and Security Mode Complete, then stopped
after slice selection:

```text
Handle Security Mode Complete
Handle InitialRegistration
RequestedNssai - ServingSnssai: &{Sst:1 Sd:010203}
```

Likely area: CP NF/SBI issue after slice selection, especially NSSF/NRF/UDM/UDR
availability or stale CP processes after restart. Subscriber key looked likely OK
because authentication succeeded.

## UERANSIM Interface Setup

For the topology used in this session:

```bash
sudo ip link set enp7s0 up
sudo ip link set enp8s0 up
sudo ip addr replace 192.168.1.1/24 dev enp7s0
sudo ip addr replace 192.168.2.1/24 dev enp8s0
sudo ip addr replace 192.168.2.3/24 dev enp8s0
sudo ip route replace 192.168.3.2 via 192.168.2.2 dev enp8s0
```

Expected `free5gc-gnb.yaml` values on UERANSIM node:

```yaml
linkIp: 192.168.1.1
ngapIp: 192.168.1.1
gtpIp: 192.168.2.1

amfConfigs:
  - address: 192.168.1.2
    port: 38412
```

## Common Cleanups

Kill UERANSIM:

```bash
sudo pkill -f nr-ue
sudo pkill -f nr-gnb
sudo ip link delete ue1tun 2>/dev/null || true
```

Clean CP restart shape:

```bash
./scripts/run/stop_cn.sh
sudo pkill -f './bin/amf|./bin/smf|./bin/nrf|./bin/nssf|./bin/ausf|./bin/udm|./bin/udr|./bin/pcf|./bin/chf'
sudo pkill -f mongod
```

Then restart ONVM manager, UPF-LB, UPF-U workers, UPF-C, and CP NFs in order.
