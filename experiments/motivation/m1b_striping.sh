#!/bin/bash
# M1b 재측정: client(jetson)의 stripe count 1/2/3 처리량.
# P0 C2에서는 fio가 크기가 모자란 파일을 지우고 다시 만들어 stripe 설정이 사라졌을 수 있다. 그래서 다시 잰다.
# 파일은 dd로 미리 채워 레이아웃을 유지하고, 측정마다 OSS별 송수신량으로 실제 분산을 확인한다.
# 사용: RSH=<ssh 래퍼> ./m1b_striping.sh <out.tsv>
OUT=${1:?out.tsv}; T=/mnt/lustrefs/llmio_test/m1b
rx() { $RSH "$@"; }
nic() { rx $1 "awk '/enP8p1s0/{printf \"%.0f\\n\", \$2 + \$10}' /proc/net/dev"; }     # rx + tx bytes (지수 표기 방지)
fio_bw() { python3 -c "
import json,sys
s=sys.stdin.read(); j=json.loads(s[s.index('{'):])['jobs'][0]
print(round((j['read']['bw_bytes']+j['write']['bw_bytes'])/1e6,1))"; }

echo -e "stripe\trw\trep\tMB_s\tlayout_osts\tjetson1_MiB\tjetson2_MiB\tjetson3_MiB" > $OUT
rx j "mkdir -p $T"
for sc in 1 2 3; do
  f=$T/sc$sc
  rx j "lfs setstripe -c $sc -i 0 $f && dd if=/dev/zero of=$f bs=4M count=512 oflag=direct status=none"
  osts=$(rx j "lfs getstripe $f | awk '/obdidx/{p=1;next} p&&NF{printf \"%s \", \$1}'")
  for rep in 1 2 3; do
    for rw in write read; do
      a1=$(nic j1); a2=$(nic j2); a3=$(nic j3)
      bw=$(rx j "fio --name=m1b --filename=$f --rw=$rw --bs=4M --size=2G --direct=1 --ioengine=libaio --iodepth=16 --output-format=json" | fio_bw)
      b1=$(nic j1); b2=$(nic j2); b3=$(nic j3)
      echo -e "$sc\t$rw\t$rep\t$bw\t$osts\t$(( (b1-a1)>>20 ))\t$(( (b2-a2)>>20 ))\t$(( (b3-a3)>>20 ))" >> $OUT
    done
  done
  echo "layout after: $(rx j "lfs getstripe -c $f") stripes on [$(rx j "lfs getstripe $f | awk '/obdidx/{p=1;next} p&&NF{printf \"%s \", \$1}'")]" >&2
  rx j "rm -f $f"
done
rx j "rmdir $T"
