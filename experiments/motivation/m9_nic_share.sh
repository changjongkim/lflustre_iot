#!/bin/bash
# M9: stage 노드의 NIC를 pipeline activation과 저장 I/O가 함께 쓸 때 activation 전달 지연 (A' 구성, 마운트 추가 없음).
# activation: jetson1(stage 1) → jetson2(stage 2). 저장 I/O: jetson(client)이 fio로
#   rx  = OST0001(jetson2)에 쓰기 → jetson2 수신 링크 공유
#   tx  = OST0000(jetson1)에서 읽기 → jetson1 송신 링크 공유
#   both = 둘 다
# 사용: RSH=<ssh 래퍼> ./m9_nic_share.sh <out_dir>
# RSH <node> <command> 형식이며 node는 j(client), j1/j2(OSS)이다.
OUT=${1:?out_dir}; mkdir -p $OUT
HERE=$(cd $(dirname $0) && pwd); W='$HOME/lflustre_iot_work/motiv'; T=/mnt/lustrefs/llmio_test/m9
PORT=19090; RX_HOST=192.168.0.52; BG_RT=75
rx() { $RSH "$@"; }

for n in j j1 j2; do rx $n "mkdir -p $W"; done
for f in act_probe.py sampler.py; do rx j1 "cat > $W/$f" < $HERE/$f; rx j2 "cat > $W/$f" < $HERE/$f; done
# fio는 파일이 --size보다 작으면 지우고 다시 만들어 Lustre 레이아웃을 잃는다. dd로 미리 채운 뒤 배치를 확인한다.
rx j "mkdir -p $T && for i in 0 1; do lfs setstripe -c 1 -i \$i $T/ost\$i && dd if=/dev/zero of=$T/ost\$i bs=4M count=512 oflag=direct status=none; done; \
      [ \$(lfs getstripe -i $T/ost0) = 0 ] && [ \$(lfs getstripe -i $T/ost1) = 1 ]" || { echo "layout check failed" >&2; exit 1; }
rx j2 "pkill -f 'act_probe.p[y] serve'; true"     # 패턴과 실행 명령을 한 셸에 두면 pkill이 그 셸을 죽인다
rx j2 "nohup python3 $W/act_probe.py serve $PORT </dev/null >/dev/null 2>&1 &"
sleep 2

bg() { # cond
  case $1 in
    rx)   echo "fio --name=m9bg --filename=$T/ost1 --rw=write --bs=4M --size=2G --direct=1 --ioengine=libaio --iodepth=16 --time_based --runtime=$BG_RT --output-format=json --output=$W/fio_\$c.json" ;;
    tx)   echo "fio --name=m9bg --filename=$T/ost0 --rw=read --bs=4M --size=2G --direct=1 --ioengine=libaio --iodepth=16 --time_based --runtime=$BG_RT --output-format=json --output=$W/fio_\$c.json" ;;
    both) echo "fio --output-format=json --output=$W/fio_\$c.json --direct=1 --ioengine=libaio --iodepth=16 --bs=4M --size=2G --time_based --runtime=$BG_RT \
                --name=m9w --filename=$T/ost1 --rw=write --name=m9r --filename=$T/ost0 --rw=read" ;;
  esac
}

echo -e "label\tmode\tbytes\ti\tms" > $OUT/m9_act.tsv
for rep in 1 2; do
  for cond in idle rx tx both; do
    c=${cond}_$rep
    for n in j1 j2; do rx $n "nohup python3 $W/sampler.py $W/samp_$c.tsv 70 </dev/null >/dev/null 2>&1 &"; done
    if [ $cond != idle ]; then rx j "c=$c; nohup $(bg $cond) </dev/null >/dev/null 2>&1 &"; sleep 6; fi
    rx j1 "python3 $W/act_probe.py burst $RX_HOST $PORT $c 2048 10 1.0; \
           python3 $W/act_probe.py burst $RX_HOST $PORT $c 8192 5 2.0; \
           python3 $W/act_probe.py ping $RX_HOST $PORT $c 400 0.05" >> $OUT/m9_act.tsv
    rx j "pkill -INT -f 'fio --nam[e]=m9|--nam[e]=m9w' ; sleep 2; true"
    sleep 4
    echo "$(date +%T) done $c" >&2
  done
done

rx j "echo layout after run: \$(lfs getstripe -i $T/ost0) \$(lfs getstripe -i $T/ost1)" > $OUT/m9_layout.txt
rx j2 "pkill -f 'act_probe.p[y] serve'; true"
for c in rx_1 tx_1 both_1 rx_2 tx_2 both_2; do
  rx j "cat $W/fio_$c.json 2>/dev/null" | python3 -c "
import json,sys
try: s=sys.stdin.read(); j=json.loads(s[s.index('{'):])   # SIGINT 종료 시 앞에 안내 줄이 붙는다
except Exception: sys.exit()
for job in j['jobs']:
    print('$c', job['jobname'], round(job['read']['bw_bytes']/1e6,1), round(job['write']['bw_bytes']/1e6,1), sep='\t')"
done > $OUT/m9_fio.tsv
for n in j1 j2; do for f in $(rx $n "ls $W/samp_*.tsv"); do rx $n "cat $f" > $OUT/${n}_$(basename $f); done; done
rx j "rm -rf $T $W/fio_*.json"; for n in j1 j2; do rx $n "rm -f $W/samp_*.tsv"; done
