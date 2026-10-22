#!/bin/bash
# F7 원인 확인 2: llama-server의 호스트 RAM prompt cache(--cache-ram, 기본 8192MiB)가 서로 다른 프롬프트마다
# 이전 KV를 RAM에 쌓는지 본다. 프롬프트를 매번 바꿔 요청 4개를 보내고 MemAvailable을 기록한다 (노드 안에서 실행).
# 사용: cache_ram_check.sh <model> <bin_dir> [extra llama-server args...]
MODEL=$1; BIN=$2; shift 2; PORT=8091; W=$(dirname $0)
LD_LIBRARY_PATH=$BIN nohup $BIN/llama-server -m $MODEL -ngl 99 -c 4096 -np 1 --port $PORT "$@" </dev/null > $W/cram_server.log 2>&1 &
SPID=$!
for i in $(seq 1 120); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done
av() { awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo; }
echo "args=[$*] loaded avail_MiB=$(av)"
for k in 1 2 3 4; do
  P=$(python3 -c "
import json, random; random.seed($k)
t='Request $k. '+''.join(f'{random.randint(0,23):02d}:{random.randint(0,59):02d} vib={random.uniform(0,9):.2f} T={random.uniform(20,90):.1f}\n' for _ in range(150))
print(json.dumps({'prompt': t, 'n_predict': 64, 'cache_prompt': False, 'ignore_eos': True}))")
  curl -s -X POST http://127.0.0.1:$PORT/completion -d "$P" | python3 -c "import json,sys; d=json.load(sys.stdin); print('  request $k prompt_n', d.get('timings',{}).get('prompt_n', d.get('error')), end=' ')"
  echo "avail_MiB=$(av)"
  [ $(av) -lt 1200 ] && { echo "  stop: low memory"; break; }
done
kill $SPID; wait $SPID 2>/dev/null; sleep 2; echo "after exit avail_MiB=$(av)"
