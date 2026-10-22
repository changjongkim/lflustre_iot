#!/bin/bash
# M8: 같은 노드에서 LLM 연산과 저장 I/O가 겹칠 때 서로의 성능 (A' stage 노드 jetson1).
# LLM: jetson1의 llama-server (Qwen3-4B Q4_K_M, 모델은 jetson1 로컬 디스크), llm_probe.py로 prefill·decode 측정.
# 저장 I/O 조건:
#   idle
#   rread / rwrite : jetson(client)이 OST0000(jetson1)을 읽기/쓰기 → jetson1의 OSS가 원격 I/O 처리 (마운트 추가 없음)
#   lread / lwrite / lread_buf / lwrite_buf : jetson1 자신의 client로 로컬 OST0000 읽기/쓰기 (LOCAL=1, jetson1 client 마운트 필요)
# 사용: RSH=<ssh 래퍼> SUDO_PW=... [LOCAL=1] ./m8_oss_llm.sh <out_dir>
OUT=${1:?out_dir}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'; T=/mnt/lustrefs/llmio_test/m8
MODEL_SRC=/mnt/lustrefs/llmio_test/models; MODEL=Qwen3-4B-Q4_K_M.gguf; PORT=8089; BG_RT=100
CONDS=${CONDS:-"idle rread rwrite"}; [ "$LOCAL" = 1 ] && CONDS="idle lread lwrite lread_buf lwrite_buf"
rx() { $RSH "$@"; }
# 로컬 조건에서 마운트가 없으면 fio가 microSD 루트 파일 시스템에 쓰게 된다 (재부팅으로 마운트가 사라진 경우)
[ "$LOCAL" = 1 ] && { rx j1 "mount -t lustre | grep -q ' /mnt/lustrefs '" || { echo "client mount missing on j1" >&2; exit 1; }; }
fio_cmd() { # file rw direct runtime
  echo "fio --name=m8bg --filename=$1 --rw=$2 --bs=4M --size=2G --direct=$3 --ioengine=libaio --iodepth=16 --time_based --runtime=$4 --output-format=json"; }
fio_bw() { python3 -c "
import json,sys
try: s=sys.stdin.read(); j=json.loads(s[s.index('{'):])['jobs'][0]   # SIGINT 종료 시 앞에 안내 줄이 붙는다
except Exception: sys.exit()
print(round((j['read']['bw_bytes']+j['write']['bw_bytes'])/1e6,1))"; }

# 1. 준비: 스크립트, 모델(jetson → jetson1, 유선 LAN의 임시 HTTP), fio 파일
rx j1 "mkdir -p $W/models"; rx j "mkdir -p $W"
for f in llm_probe.py sampler.py; do rx j1 "cat > $W/$f" < $HERE/$f; done
if [ "$(rx j1 "stat -c %s $W/models/$MODEL 2>/dev/null")" != "$(rx j "stat -c %s $MODEL_SRC/$MODEL")" ]; then
  rx j "nohup python3 -m http.server 18080 --bind 192.168.0.100 --directory $MODEL_SRC </dev/null >/dev/null 2>&1 &"; sleep 2
  rx j1 "curl -sf -o $W/models/$MODEL http://192.168.0.100:18080/$MODEL; ls -la $W/models/$MODEL"
  rx j "pkill -f 'http.serve[r] 18080'; true"
fi
# fio는 파일이 --size보다 작으면 지우고 다시 만들어 Lustre 레이아웃을 잃는다. dd로 미리 채운 뒤 배치를 확인한다.
rx j "mkdir -p $T && lfs setstripe -c 1 -i 0 $T/ost0 && dd if=/dev/zero of=$T/ost0 bs=4M count=512 oflag=direct status=none && [ \$(lfs getstripe -i $T/ost0) = 0 ]" \
  || { echo "layout check failed" >&2; exit 1; }

start_sampler() { rx j1 "read -r SUDO_PW; export SUDO_PW; nohup python3 $W/sampler.py $W/samp_$1.tsv $2 </dev/null >/dev/null 2>&1 &" <<< "$SUDO_PW"; }
start_bg() { # cond label
  case $1 in
    rread)  rx j  "nohup $(fio_cmd $T/ost0 read 1 $BG_RT) --output=$W/fio_$2.json </dev/null >/dev/null 2>&1 &" ;;
    rwrite) rx j  "nohup $(fio_cmd $T/ost0 write 1 $BG_RT) --output=$W/fio_$2.json </dev/null >/dev/null 2>&1 &" ;;
    lread)  rx j1 "nohup $(fio_cmd $T/ost0 read 1 $BG_RT) --output=$W/fio_$2.json </dev/null >/dev/null 2>&1 &" ;;
    lwrite) rx j1 "nohup $(fio_cmd $T/ost0 write 1 $BG_RT) --output=$W/fio_$2.json </dev/null >/dev/null 2>&1 &" ;;
    lread_buf)  rx j1 "nohup $(fio_cmd $T/ost0 read 0 $BG_RT) --output=$W/fio_$2.json </dev/null >/dev/null 2>&1 &" ;;
    lwrite_buf) rx j1 "nohup $(fio_cmd $T/ost0 write 0 $BG_RT) --output=$W/fio_$2.json </dev/null >/dev/null 2>&1 &" ;;
  esac
}
node_of() { case $1 in r*) echo j ;; *) echo j1 ;; esac; }
stop_bg() { for n in j j1; do rx $n "pkill -INT -f 'fio --nam[e]=m8bg'; true"; done; sleep 3; }

# 2. LLM 없이 저장 I/O만 (역방향 비교 기준)
echo -e "cond\tllm\tfio_MB_s" > $OUT/m8_fio.tsv
for cond in $CONDS; do
  [ $cond = idle ] && continue
  start_sampler noLLM_$cond 40; start_bg $cond noLLM_$cond; sleep 38; stop_bg
  echo -e "$cond\toff\t$(rx $(node_of $cond) "cat $W/fio_noLLM_$cond.json" | fio_bw)" >> $OUT/m8_fio.tsv
done

# 3. LLM 서버 기동
# cd와 nohup을 &&로 묶어 &를 붙이면 서브셸이 SSH 출력을 잡고 있어 세션이 끝나지 않는다. 문장을 나눈다.
rx j1 "cd $W; LD_LIBRARY_PATH=\$HOME/lflustre_iot_work/llama-bin nohup \$HOME/lflustre_iot_work/llama-bin/llama-server -m $W/models/$MODEL \
       -ngl 99 -c 4096 -np 1 --port $PORT </dev/null > $W/m8_server.log 2>&1 &"
rx j1 "for i in \$(seq 1 120); do curl -sf http://127.0.0.1:$PORT/health >/dev/null && break; sleep 2; done; \
       echo server ready; awk '/MemAvailable/{print \"MemAvailable MiB\", int(\$2/1024)}' /proc/meminfo"
rx j1 "python3 $W/llm_probe.py $PORT warmup 1 512 16 >/dev/null"

# 4. 조건별 LLM 측정
echo -e "label\treq\tt_start\tprompt_n\tprefill_ms\tprefill_tok_s\tgen_n\tdecode_tok_s\tgap_p50_ms\tgap_p99_ms\tgap_max_ms" > $OUT/m8_llm.tsv
for rep in 1 2; do
  for cond in $CONDS; do
    c=${cond}_$rep
    start_sampler $c 85
    [ $cond != idle ] && { start_bg $cond $c; sleep 6; }
    rx j1 "python3 $W/llm_probe.py $PORT $c 5 2048 128" >> $OUT/m8_llm.tsv
    if [ $cond != idle ]; then stop_bg; echo -e "$cond\ton\t$(rx $(node_of $cond) "cat $W/fio_$c.json" | fio_bw)" >> $OUT/m8_fio.tsv; fi
    echo "$(date +%T) done $c" >&2
    sleep 3
  done
done

# 5. 정리와 수집
rx j1 "pkill -f 'llama-serve[r] -m'; true"
rx j1 "grep -E 'model buffer|KV buffer|compute buffer' $W/m8_server.log | head -6" > $OUT/m8_server_mem.txt
for f in $(rx j1 "ls $W/samp_*.tsv"); do rx j1 "cat $f" > $OUT/j1_$(basename $f); done
rx j1 "rm -f $W/samp_*.tsv $W/fio_*.json"; rx j "rm -rf $T $W/fio_*.json"
