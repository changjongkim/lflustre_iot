#!/bin/bash
# M10: 같은 노드의 buffered I/O가 page cache로 메모리를 압박할 때 LLM 서빙 성능 (jetson1).
# llama-server(Qwen3-4B Q4_K_M, ctx 8192)가 상주한 상태에서 로컬 OST0000의 3GiB 파일을 계속 읽는다.
#   idle        : 저장 I/O 없음
#   direct      : O_DIRECT 읽기 (page cache 사용 안 함)
#   buf_cap512  : buffered 읽기, client 캐시 상한 512MB
#   buf_default : buffered 읽기, client 캐시 상한 기본값(RAM의 1/2)
# 캐시 상한은 비영구 설정이며 끝나면 측정 전 값으로 되돌린다.
# 사용: RSH=<ssh 래퍼> SUDO_PW=... ./m10_memory.sh <out_dir>     (jetson1 client 마운트 필요)
OUT=${1:?out_dir}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'; T=/mnt/lustrefs/llmio_test/m10
MODEL='$HOME/lflustre_iot_work/motiv/models/Qwen3-4B-Q4_K_M.gguf'; BIN='$HOME/lflustre_iot_work/llama-bin'; PORT=8089
rx() { $RSH "$@"; }
srx() { local n=$1; shift; rx $n "read -r P; echo \"\$P\" | sudo -S -p '' $*" <<< "$SUDO_PW"; }   # 비밀번호는 stdin으로만 전달
getcap() { srx j1 "lctl get_param -n llite.*.max_cached_mb" | awk '/^max_cached_mb/{print $2}'; }   # 일반 사용자는 읽을 수 없다
cap() { srx j1 "lctl set_param llite.*.max_cached_mb=$1" >/dev/null; getcap; }

rx j1 "mount -t lustre | grep -q /mnt/lustrefs" || { echo "client mount missing on j1" >&2; exit 1; }
for f in llm_probe.py sampler.py; do rx j1 "cat > $W/$f" < $HERE/$f; done
ORIG=$(getcap); [ -n "$ORIG" ] || { echo "cannot read cache cap" >&2; exit 1; }
DEFAULT=$(rx j1 "awk '/MemTotal/{print int(\$2/2048)}' /proc/meminfo")
echo "cache cap before: $ORIG MB, default (RAM/2): $DEFAULT MB" | tee $OUT/m10_info.txt
rx j1 "mkdir -p $T && lfs setstripe -c 1 -i 0 $T/f3g && dd if=/dev/zero of=$T/f3g bs=4M count=768 oflag=direct status=none && [ \$(lfs getstripe -i $T/f3g) = 0 ]" \
  || { echo "layout check failed" >&2; exit 1; }

rx j1 "cd $W; LD_LIBRARY_PATH=$BIN nohup $BIN/llama-server -m $MODEL -ngl 99 -c 8192 -np 1 --port $PORT </dev/null > $W/m10_server.log 2>&1 &"
rx j1 "for i in \$(seq 1 120); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done; \
       awk '/MemAvailable/{print \"server ready, MemAvailable MiB\", int(\$2/1024)}' /proc/meminfo" | tee -a $OUT/m10_info.txt
rx j1 "python3 $W/llm_probe.py $PORT warmup 1 512 16 >/dev/null"

echo -e "label\treq\tt_start\tprompt_n\tprefill_ms\tprefill_tok_s\tgen_n\tdecode_tok_s\tgap_p50_ms\tgap_p99_ms\tgap_max_ms" > $OUT/m10_llm.tsv
echo -e "cond\tcap_MB\tfio_MB_s" > $OUT/m10_fio.tsv
for rep in 1 2; do
  for cond in idle direct buf_cap512 buf_default; do
    c=${cond}_$rep
    case $cond in buf_default) CAP=$(cap $DEFAULT) ;; *) CAP=$(cap 512) ;; esac
    srx j1 "sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'"
    rx j1 "read -r SUDO_PW; export SUDO_PW; nohup python3 $W/sampler.py $W/samp_$c.tsv 90 </dev/null >/dev/null 2>&1 &" <<< "$SUDO_PW"
    if [ $cond != idle ]; then
      d=1; [ ${cond:0:3} = buf ] && d=0
      rx j1 "nohup fio --name=m10bg --filename=$T/f3g --rw=read --bs=4M --size=3G --direct=$d --ioengine=libaio --iodepth=16 \
             --time_based --runtime=100 --output-format=json --output=$W/fio_$c.json </dev/null >/dev/null 2>&1 &"
      sleep 8
    fi
    rx j1 "python3 $W/llm_probe.py $PORT $c 5 2048 128" >> $OUT/m10_llm.tsv
    if [ $cond != idle ]; then
      rx j1 "pkill -INT -f 'fio --nam[e]=m10bg'; sleep 2; cat $W/fio_$c.json" | python3 -c "
import json,sys
s=sys.stdin.read(); j=json.loads(s[s.index('{'):])['jobs'][0]; print('$c', '$CAP', round(j['read']['bw_bytes']/1e6,1), sep='\t')" >> $OUT/m10_fio.tsv
    fi
    echo "$(date +%T) done $c (cap $CAP)" >&2
    sleep 3
  done
done

rx j1 "pkill -f 'llama-serve[r] -m'; true"
echo "cache cap restored: $(cap $ORIG) MB" | tee -a $OUT/m10_info.txt
rx j1 "grep -E 'model buffer|KV buffer|compute buffer' $W/m10_server.log | head -6" >> $OUT/m10_info.txt
for f in $(rx j1 "ls $W/samp_*.tsv"); do rx j1 "cat $f" > $OUT/j1_$(basename $f); done
rx j1 "rm -f $W/samp_*.tsv $W/fio_*.json; rm -rf $T"
