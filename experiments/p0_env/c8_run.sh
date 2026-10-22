#!/bin/bash
# P0 C8 실행 (jetson): llama-server 기동 → 플래너 시험 → 종료. 메모리는 기동 전후로 기록한다.
W=~/lflustre_iot_work; BIN=$W/llama.cpp/build/bin; MODEL=/mnt/lustrefs/llmio_test/models/Qwen3-4B-Q4_K_M.gguf
mem() { awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo; }
before=$(mem)
$BIN/llama-server -m $MODEL -ngl 99 -c 4096 -np 1 --port 8089 > $W/c8_server.log 2>&1 &
SP=$!; t0=$(date +%s)
for i in $(seq 1 120); do curl -sf http://127.0.0.1:8089/health >/dev/null && break; sleep 2; done
echo "server ready after $(( $(date +%s) - t0 ))s (model on Lustre OST $(lfs getstripe -i $MODEL), remote for this node)"
python3 $W/c8_planner_test.py 8089 3
during=$(mem); rss=$(ps -o rss= -p $SP | awk '{print int($1/1024)}')
echo "MemAvailable before=${before}MiB during=${during}MiB delta=$((before-during))MiB server RSS=${rss}MiB"
kill $SP; wait $SP 2>/dev/null
