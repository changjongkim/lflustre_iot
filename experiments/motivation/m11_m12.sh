#!/bin/bash
# M12(read-aware relocation, jetson1)와 M11(runtime-aware 체크포인트, jetson3)을 차례로 실행한다.
# 필요 조건: jetson1, jetson3 client 마운트. 이 스크립트는 마운트를 하지 않는다.
# 사용: RSH=<ssh 래퍼> SUDO_PW=... ./m11_m12.sh <out_dir>
OUT=${1:?out_dir}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'
MODEL=/mnt/lustrefs/llmio_test/models/Qwen3-4B-Q4_K_M.gguf; BIN=/mnt/lustrefs/llmio_test/llama-bin
rx() { $RSH "$@"; }

bench() { # node local_ost args...
  local n=$1 lost=$2; shift 2
  local SLOT=/mnt/lustrefs/llmio_test/m1112_$n
  rx $n "mount -t lustre | grep -q /mnt/lustrefs" || { echo "client mount missing on $n" >&2; return 1; }
  rx $n "mkdir -p $W $SLOT && lfs setstripe -c 1 -i $lost $SLOT"
  rx $n "cat > $W/kv_restore_bench.py" < $HERE/kv_restore_bench.py
  rx $n "LD_LIBRARY_PATH=$BIN nohup $BIN/llama-server -m $MODEL -ngl 99 -c 4608 -np 1 --cache-ram 0 --port 8089 --slot-save-path $SLOT/ </dev/null > $W/m1112_server.log 2>&1 &"
  rx $n "for i in \$(seq 1 150); do curl -sf http://127.0.0.1:8089/health >/dev/null && break; sleep 2; done; echo $n ready"
  rx $n "read -r SUDO_PW; export SUDO_PW; python3 $W/kv_restore_bench.py $* " <<< "$SUDO_PW"
  rx $n "pkill -f 'llama-serve[r] -m $MODEL'; true"; rx $n "rm -rf $SLOT"
}

WHICH=${2:-both}     # m12 | m11 | both
[ -f $OUT/m11_m12.tsv ] || echo -e "mode\tcase\tk\top\tms" > $OUT/m11_m12.tsv
[ $WHICH != m11 ] && bench j1 0 relocation 8089 /mnt/lustrefs/llmio_test/m1112_j1 0 1 5 4096 >> $OUT/m11_m12.tsv
[ $WHICH != m12 ] && bench j3 2 ckpt 8089 /mnt/lustrefs/llmio_test/m1112_j3 2 10 4096 >> $OUT/m11_m12.tsv
