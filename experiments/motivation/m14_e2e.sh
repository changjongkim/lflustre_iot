#!/bin/bash
# M14: KV 배치 정책(Lustre 기본 / OSS 부하 기반 분산 / 소비 노드 배치)별 TTFT. kv_router.py를 jetson에서 실행한다.
# 필요 조건: jetson1–3 client 마운트, 캐시 상한 512MB(비영구). 이 스크립트는 마운트를 하지 않는다.
# 사용: RSH=<ssh 래퍼> ./m14_e2e.sh <out_dir> [duration_s] [rate_req_s]
OUT=${1:?out_dir}; DUR=${2:-240}; RATE=${3:-0.3}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'
SLOT=/mnt/lustrefs/llmio_test/m14_slots; BIN=/mnt/lustrefs/llmio_test/llama-bin
# 모델은 노드 로컬 사본을 쓴다. Lustre에서 mmap하면 종료 후에도 약 1.3GB가 MemAvailable에서 빠진다(F7).
MODEL='$HOME/lflustre_iot_work/motiv/models/Qwen3-4B-Q4_K_M.gguf'
ip_of() { case $1 in j1) echo 192.168.0.51 ;; j2) echo 192.168.0.52 ;; j3) echo 192.168.0.53 ;; esac; }   # macOS bash 3.2에는 연관 배열이 없다
rx() { $RSH "$@"; }
for n in j j1 j2 j3; do rx $n "mount -t lustre | grep -q /mnt/lustrefs" || { echo "client mount missing on $n" >&2; exit 1; }; done

rx j "mkdir -p $W $SLOT && lfs setstripe -c 1 $SLOT"
rx j "cat > $W/kv_router.py" < $HERE/kv_router.py
for n in j1 j2 j3; do
  rx $n "mkdir -p $W"   # mkdir && nohup ... & 로 묶으면 서브셸이 SSH 출력을 잡아 세션이 끝나지 않는다
  rx $n "LD_LIBRARY_PATH=$BIN nohup $BIN/llama-server -m $MODEL -ngl 99 -c 4608 -np 1 --cache-ram 0 --host $(ip_of $n) --port 8089 \
         --slot-save-path $SLOT/ </dev/null > $W/m14_server.log 2>&1 &"
done
for n in j1 j2 j3; do
  rx $n "for i in \$(seq 1 150); do curl -sf http://$(ip_of $n):8089/health >/dev/null && break; sleep 2; done; echo $n ready; \
         awk '/MemAvailable/{print \"MemAvailable MiB\", int(\$2/1024)}' /proc/meminfo; lctl get_param -n llite.*.max_cached_mb | head -1"
done

rx j "python3 $W/kv_router.py prep $SLOT" 2> $OUT/m14_prep.log
echo -e "policy\ti\tctx\tnode\tost\tlocal\tt_arrival\twait_ms\trestore_ms\ttail_prompt_n\ttail_ms\tttft_ms" > $OUT/m14.tsv
for policy in lustre_default balanced local; do
  rx j "python3 $W/kv_router.py run $SLOT $policy $DUR $RATE 7" >> $OUT/m14.tsv 2>> $OUT/m14_run.log
  echo "$(date +%T) done $policy" >&2
done

for n in j1 j2 j3; do rx $n "pkill -f 'llama-serve[r] -m'; true"; done
rx j "rm -rf $SLOT"
