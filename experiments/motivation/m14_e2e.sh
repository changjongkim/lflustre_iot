#!/bin/bash
# M14: KV 배치 정책(Lustre 기본 / OSS 부하 기반 분산 / 소비 노드 배치)별 TTFT. kv_router.py를 jetson에서 실행한다.
# 필요 조건: jetson1–3 client 마운트, 캐시 상한 512MB(비영구). 이 스크립트는 마운트를 하지 않는다.
# 사용: RSH=<ssh 래퍼> ./m14_e2e.sh <out_dir> [duration_s] [rate_req_s]
OUT=${1:?out_dir}; DUR=${2:-240}; RATE=${3:-0.3}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'
SLOT=/mnt/lustrefs/llmio_test/m14_slots; MODEL=/mnt/lustrefs/llmio_test/models/Qwen3-4B-Q4_K_M.gguf; BIN=/mnt/lustrefs/llmio_test/llama-bin
declare -A IP=([j1]=192.168.0.51 [j2]=192.168.0.52 [j3]=192.168.0.53)
rx() { $RSH "$@"; }
for n in j j1 j2 j3; do rx $n "mount -t lustre | grep -q /mnt/lustrefs" || { echo "client mount missing on $n" >&2; exit 1; }; done

rx j "mkdir -p $W $SLOT && lfs setstripe -c 1 $SLOT"
rx j "cat > $W/kv_router.py" < $HERE/kv_router.py
for n in j1 j2 j3; do
  rx $n "mkdir -p $W && LD_LIBRARY_PATH=$BIN nohup $BIN/llama-server -m $MODEL -ngl 99 -c 4608 -np 1 --host ${IP[$n]} --port 8089 \
         --slot-save-path $SLOT/ </dev/null > $W/m14_server.log 2>&1 &"
done
for n in j1 j2 j3; do
  rx $n "for i in \$(seq 1 150); do curl -sf http://${IP[$n]}:8089/health >/dev/null && break; sleep 2; done; echo $n ready; \
         awk '/MemAvailable/{print \"MemAvailable MiB\", int(\$2/1024)}' /proc/meminfo; lctl get_param -n llite.*.max_cached_mb | head -1"
done

rx j "python3 $W/kv_router.py prep $SLOT" 2> $OUT/m14_prep.log
echo -e "policy\ti\tctx\tnode\tost\tlocal\tt_arrival\twait_ms\trestore_ms\ttail_prompt_n\ttail_ms\tttft_ms" > $OUT/m14.tsv
for policy in lustre_default balanced local; do
  rx j "python3 $W/kv_router.py run $SLOT $policy $DUR $RATE 7" >> $OUT/m14.tsv 2>> $OUT/m14_run.log
  echo "$(date +%T) done $policy" >&2
done

for n in j1 j2 j3; do rx $n "pkill -f 'llama-serve[r] -m $MODEL'; true"; done
rx j "rm -rf $SLOT"
