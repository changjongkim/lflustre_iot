#!/bin/bash
# M5 재측정: 원격 client의 I/O를 처리하는 OSS 노드(jetson3)의 CPU를 노드 내부 샘플러로 잰다.
# P0에서는 SSH로 /proc/stat를 조회해 jetson1·3 약 2%, jetson2 13–19%로 노드마다 달랐다(F6).
# 조건마다 60초: idle / jetson이 OST0002를 읽음 / jetson이 OST0002에 씀. LLM은 실행하지 않는다.
# 사용: RSH=<ssh 래퍼> ./m5_oss_cpu.sh <out_dir>
OUT=${1:?out_dir}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'; T=/mnt/lustrefs/llmio_test/m5
rx() { $RSH "$@"; }
rx j3 "mkdir -p $W"; rx j3 "cat > $W/sampler.py" < $HERE/sampler.py
rx j "mkdir -p $T && lfs setstripe -c 1 -i 2 $T/ost2 && dd if=/dev/zero of=$T/ost2 bs=4M count=512 oflag=direct status=none && [ \$(lfs getstripe -i $T/ost2) = 2 ]" \
  || { echo "layout check failed" >&2; exit 1; }
for rep in 1 2; do
  for cond in idle read write; do
    c=${cond}_$rep
    rx j3 "nohup python3 $W/sampler.py $W/samp_m5_$c.tsv 62 </dev/null >/dev/null 2>&1 &"
    if [ $cond = idle ]; then sleep 62
    else rx j "fio --name=m5 --filename=$T/ost2 --rw=$cond --bs=4M --size=2G --direct=1 --ioengine=libaio --iodepth=16 --time_based --runtime=60 --output-format=json" \
           | python3 -c "
import json,sys; s=sys.stdin.read(); j=json.loads(s[s.index('{'):])['jobs'][0]
print('$c', round((j['read']['bw_bytes']+j['write']['bw_bytes'])/1e6,1), sep='\t')" >> $OUT/m5_fio.tsv
    fi
    sleep 3
    rx j3 "cat $W/samp_m5_$c.tsv" > $OUT/j3_samp_m5_$c.tsv
  done
done
rx j "rm -rf $T"; rx j3 "rm -f $W/samp_m5_*.tsv"
