#!/bin/bash
# go/no-go ② 실행 (jetson1): llama-server를 띄우고 x2_client.py를 실행한 뒤 서버를 종료한다.
W=~/lflustre_iot_work; MNT=/mnt/lustrefs; BIN=$W/llama-bin; MODEL=$MNT/llmio_test/models/Qwen3-4B-Q4_K_M.gguf
SLOT=$MNT/llmio_test/x2_slots_$(hostname -s); mkdir -p $SLOT && lfs setstripe -c 1 -i ${LOCAL_OST:-0} $SLOT
echo "model OST: $(lfs getstripe -i $MODEL), slot dir default OST: $(lfs getstripe -d -i $SLOT)"
export LD_LIBRARY_PATH=$BIN:$LD_LIBRARY_PATH
$BIN/llama-server -m $MODEL -ngl 99 -c 9216 -np 1 --port 8088 --slot-save-path $SLOT/ > $W/x2_server.log 2>&1 &
SP=$!
for i in $(seq 1 120); do curl -sf http://127.0.0.1:8088/health >/dev/null && break; sleep 2; done
echo "server ready after ~$((i*2))s; mem: $(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)MiB available"
python3 $W/x2_client.py 8088 $SLOT ${REPS:-2}
kill $SP; wait $SP 2>/dev/null; rm -rf $SLOT
grep -E "model size|n_ctx|flash_attn|KV self size|CUDA0 KV buffer|CUDA0 model buffer" $W/x2_server.log | head -8
