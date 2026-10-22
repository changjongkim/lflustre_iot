#!/bin/bash
# M7: OSS 공유 간섭과 "가장 느린 OSS" 관찰을 엣지(1GbE)에서 재현 (원 IFLustre 전제 확인).
# client 3개(jetson, jetson1, jetson3)가 동시에 30초 fio 읽기(또는 쓰기)를 한다.
#   same   : 세 흐름 모두 OST0001(jetson2)
#   spread : jetson → OST0001, jetson1 → OST0002, jetson3 → OST0000 (OSS마다 흐름 1개)
#   slow   : jetson은 3-stripe 파일(OST0000–0002), jetson1·jetson3은 OST0001 → OST0001만 붐빔
#   alone  : jetson 혼자 3-stripe 파일 (slow의 비교 기준)
# 사용: RSH=<ssh 래퍼> ./m7_oss_share.sh <out_dir>     (jetson1, jetson3에 client 마운트 필요)
OUT=${1:?out_dir}; mkdir -p $OUT
W='$HOME/lflustre_iot_work/motiv'; T=/mnt/lustrefs/llmio_test/m7; RT=30
rx() { $RSH "$@"; }
for n in j j1 j3; do rx $n "mkdir -p $W && mount -t lustre | grep -q /mnt/lustrefs" || { echo "client mount missing on $n" >&2; exit 1; }; done

# 파일: <client>_<ost>. 각 2GiB
rx j "mkdir -p $T"
for p in j:1 j1:1 j3:1 j1:2 j3:0; do
  c=${p%%:*}; o=${p##*:}
  rx j "lfs setstripe -c 1 -i $o $T/${c}_ost$o && dd if=/dev/zero of=$T/${c}_ost$o bs=4M count=512 oflag=direct status=none && [ \$(lfs getstripe -i $T/${c}_ost$o) = $o ]" \
    || { echo "layout check failed: ${c}_ost$o" >&2; exit 1; }
done
# fio는 파일이 --size보다 작으면 지우고 다시 만들어 Lustre 레이아웃을 잃는다. dd로 미리 채운다.
rx j "lfs setstripe -c 3 -i 0 $T/j_stripe3 && dd if=/dev/zero of=$T/j_stripe3 bs=4M count=512 oflag=direct status=none && [ \$(lfs getstripe -c $T/j_stripe3) = 3 ]" \
  || { echo "layout check failed: j_stripe3" >&2; exit 1; }

run() { # label rw "node:file ..."
  local label=$1 rw=$2; shift 2
  for p in "$@"; do
    n=${p%%:*}; f=${p##*:}
    rx $n "nohup fio --name=m7 --filename=$T/$f --rw=$rw --bs=4M --size=2G --direct=1 --ioengine=libaio --iodepth=16 \
           --time_based --runtime=$RT --output-format=json --output=$W/m7_$label.json </dev/null >/dev/null 2>&1 &"
  done
  sleep $((RT + 4))
  for p in "$@"; do
    n=${p%%:*}; f=${p##*:}
    rx $n "cat $W/m7_$label.json" | python3 -c "
import json,sys; j=json.load(sys.stdin)['jobs'][0]
print('$label', '$rw', '$n', '$f', round((j['read']['bw_bytes']+j['write']['bw_bytes'])/1e6,1), sep='\t')"
  done
}

echo -e "label\trw\tclient\tfile\tMB_s" > $OUT/m7.tsv
for rep in 1 2; do
  for rw in read write; do
    run same_$rep $rw j:j_ost1 j1:j1_ost1 j3:j3_ost1 >> $OUT/m7.tsv
    run spread_$rep $rw j:j_ost1 j1:j1_ost2 j3:j3_ost0 >> $OUT/m7.tsv
    run alone_$rep $rw j:j_stripe3 >> $OUT/m7.tsv
    run slow_$rep $rw j:j_stripe3 j1:j1_ost1 j3:j3_ost1 >> $OUT/m7.tsv
  done
done
rx j "rm -rf $T"; for n in j j1 j3; do rx $n "rm -f $W/m7_*.json"; done
