#!/bin/bash
# 카운터를 백그라운드로 켜고, 풀밭 창을 앞에 띄운다. 창을 닫으면 카운터도 종료한다.
cd "$(dirname "$0")/.." || exit 1
source .venv/bin/activate
python -m typegrass counter &
COUNTER_PID=$!
trap 'kill -TERM $COUNTER_PID 2>/dev/null; wait $COUNTER_PID 2>/dev/null' EXIT
sleep 1
python -m typegrass grass
