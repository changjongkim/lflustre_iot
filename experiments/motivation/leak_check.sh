#!/bin/bash
# F7 원인 확인: llama-server가 요청 종류별로 메모리를 늘리는지 본다 (노드 안에서 실행).
# 단계마다 llama-server RSS와 MemAvailable을 기록하고, MemAvailable이 1,500MiB 아래로 내려가면 바로 중단한다.
# 사용: leak_check.sh <model> <bin_dir> <ctx>
MODEL=$1; BIN=$2; CTX=${3:-8192}; PORT=8090; W=$(dirname $0)
LD_LIBRARY_PATH=$BIN nohup $BIN/llama-server -m $MODEL -ngl 99 -c $CTX -np 1 --port $PORT </dev/null > $W/leak_server.log 2>&1 &
SPID=$!
for i in $(seq 1 120); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done
mem() { echo "$1 rss_MiB=$(( $(awk '/VmRSS/{print $2}' /proc/$SPID/status) / 1024 )) avail_MiB=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"; }
guard() { [ $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo) -lt 1500 ] && { mem "ABORT(low memory)"; kill $SPID; exit 1; }; }
mem "loaded"
TXT=$(python3 -c "
import random; random.seed(1)
print(''.join(f'{random.randint(0,23):02d}:{random.randint(0,59):02d} vib={random.uniform(0,9):.2f} T={random.uniform(20,90):.1f}\n' for _ in range(800)))")
J=$(python3 -c "import json,sys; print(json.dumps({'content': sys.stdin.read()}))" <<< "$TXT")
for k in 1 2 3; do curl -s -X POST http://127.0.0.1:$PORT/tokenize -d "$J" >/dev/null; guard; done; mem "after 3x tokenize"
P=$(python3 -c "import json,sys; print(json.dumps({'prompt': sys.stdin.read()[:6000], 'n_predict': 128, 'cache_prompt': False, 'ignore_eos': True}))" <<< "$TXT")
for k in 1 2 3; do curl -s -X POST http://127.0.0.1:$PORT/completion -d "$P" >/dev/null; guard; mem "after non-stream completion $k"; done
PS=$(python3 -c "import json,sys; d=json.loads(sys.stdin.read()); d['stream']=True; print(json.dumps(d))" <<< "$P")
for k in 1 2 3; do curl -s -N -X POST http://127.0.0.1:$PORT/completion -d "$PS" >/dev/null; guard; mem "after stream completion $k"; done
kill $SPID; wait $SPID 2>/dev/null
grep -E "model buffer|KV buffer|compute buffer|graph" $W/leak_server.log | head -8
