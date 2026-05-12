#!/usr/bin/env bash

SESSION="ue"
ROOT="$HOME/L25GC-plus"
UERANSIM="$ROOT/UERANSIM"

tmux has-session -t "$SESSION" 2>/dev/null && tmux kill-session -t "$SESSION"

# Window 0: UERANSIM
tmux new-session -d -s "$SESSION" -n ue

# Pane 0: run gNB immediately
tmux send-keys -t "$SESSION:ue.0" \
"cd '$UERANSIM' && sudo ./build/nr-gnb -c config/free5gc-gnb.yaml" C-m

# Pane 1: pre-fill UE 1, but do NOT run
tmux split-window -t "$SESSION:ue" -h
tmux send-keys -t "$SESSION:ue.1" \
"cd '$UERANSIM' && sudo ./build/nr-ue -c config/free5gc-ue1.yaml"

# Pane 2: pre-fill UE 2, but do NOT run
tmux split-window -t "$SESSION:ue" -v
tmux send-keys -t "$SESSION:ue.2" \
"cd '$UERANSIM' && sudo ./build/nr-ue -c config/free5gc-ue2.yaml"

# Pane 3: empty shell
tmux split-window -t "$SESSION:ue" -v

tmux select-layout -t "$SESSION:ue" tiled

# Stay on the single UE window
tmux select-window -t "$SESSION:ue"

tmux attach -t "$SESSION"
