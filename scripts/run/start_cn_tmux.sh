#!/usr/bin/env bash

SESSION="upf"
ROOT="$HOME/L25GC-plus"
LOG_ONVM_MGR="${LOG_ONVM_MGR:-0}"

usage() {
  cat <<EOF
Usage: $0 [--log|--no-log]

Start the CN/UPF tmux session.

Options:
  --log      Save pane 0 ONVM manager output to log/onvm_mgr_<timestamp>.log
  --no-log   Do not save pane 0 output to a log file (default)
  -h, --help Show this help

Environment:
  LOG_ONVM_MGR=1 also enables pane 0 logging.
EOF
}

case "${1:-}" in
  --log)
    LOG_ONVM_MGR=1
    ;;
  --no-log|"")
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage
    exit 2
    ;;
esac

ONVM_MGR_CMD="cd '$ROOT' && stdbuf -oL -eL ./scripts/run/run_onvm_mgr.sh -n 0x2FFF8 -s stdout -a '0000:09:00.0 0000:07:00.0'"

if [[ "$LOG_ONVM_MGR" == "1" || "$LOG_ONVM_MGR" == "true" || "$LOG_ONVM_MGR" == "yes" ]]; then
  ONVM_MGR_CMD="cd '$ROOT' && mkdir -p log && LOG=\"log/onvm_mgr_\$(date +%Y%m%d_%H%M%S).log\" && stdbuf -oL -eL ./scripts/run/run_onvm_mgr.sh -n 0x2FFF8 -s stdout -a '0000:09:00.0 0000:07:00.0' 2>&1 | tee -a \"\$LOG\""
fi

tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"

# Window 0: UPF / ONVM
tmux new-session -d -s "$SESSION" -n upf

# Pane 0: run ONVM manager immediately
tmux send-keys -t "$SESSION:upf.0" "$ONVM_MGR_CMD" C-m

# Pane 1: pre-fill UPF LB, but do NOT run
tmux split-window -t "$SESSION:upf" -h
tmux send-keys -t "$SESSION:upf.1" \
"cd '$ROOT' && ./scripts/run/run_upf_lb.sh 1 ./NFs/onvm-upf/5gc/upf_lb/config/upf_lb.yaml"

# Pane 2: pre-fill UPF-U 1
tmux split-window -t "$SESSION:upf" -v
tmux send-keys -t "$SESSION:upf.2" \
"cd '$ROOT' && ./scripts/run/run_upf_u.sh -l 5 -- -m -r 14 -- ./NFs/onvm-upf/5gc/upf_u/config/upf_u.yaml"

# Pane 3: pre-fill UPF-U 2
tmux split-window -t "$SESSION:upf" -v
tmux send-keys -t "$SESSION:upf.3" \
"cd '$ROOT' && ./scripts/run/run_upf_u.sh -l 17 -- -m -r 15 -- ./NFs/onvm-upf/5gc/upf_u/config/upf_u.yaml"

# Pane 4: pre-fill UPF-C
tmux split-window -t "$SESSION:upf" -v
tmux send-keys -t "$SESSION:upf.4" \
"cd '$ROOT' && ./scripts/run/run_upf_c.sh 2 ./NFs/onvm-upf/5gc/upf_c/config/upfcfg.yaml"

# Pane 5: CP NFs + logs
tmux split-window -t "$SESSION:upf" -v
tmux send-keys -t "$SESSION:upf.5" \
"cd '$ROOT' && ./scripts/run/run_cp_nfs.sh && reset && tail -f log/*.log"

tmux select-layout -t "$SESSION:upf" tiled

# Stay on the single UPF/CN window
tmux select-window -t "$SESSION:upf"

tmux attach -t "$SESSION"
