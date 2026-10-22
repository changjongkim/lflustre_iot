#!/bin/bash
# P0 C2: client(jetson)에서 OST별·stripe별 순차 읽기/쓰기 대역폭 측정 (현재 분리형 구성).
# 사용: RSH=<ssh 래퍼 경로> SUDO_PW=... ./c2_bandwidth.sh > out.tsv
# RSH <node> <command> 형식이며 node는 j(client), j1/j2/j3(OSS)이다.
T=/mnt/lustrefs/llmio_test/c2
OSS_OF=(j1 j2 j3)           # OST 번호 → OSS 노드
rx() { $RSH "$@"; }
dropc() { for n in "$@"; do rx $n "echo \"$SUDO_PW\" | sudo -S -p '' sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'"; done; }
nic() { rx $1 "awk '/enP8p1s0/{print \$2, \$10}' /proc/net/dev"; }          # rx_bytes tx_bytes
cpu() { rx $1 "head -1 /proc/stat"; }
mem() { rx $1 "awk '/MemAvailable|^Cached/{printf \"%s=%d \", \$1, \$2/1024}' /proc/meminfo"; }
cpupct() { python3 -c "
a=list(map(int,'$1'.split()[1:])); b=list(map(int,'$2'.split()[1:]))
idle=(b[3]+b[4])-(a[3]+a[4]); tot=sum(b)-sum(a); print(round(100*(1-idle/tot),1) if tot else 0)"; }
fiorun() { # rw bs direct file
  rx j "fio --name=p0 --filename=$4 --rw=$1 --bs=$2 --size=2G --direct=$3 --ioengine=libaio --iodepth=16 --numjobs=1 --output-format=json 2>/dev/null | python3 -c 'import json,sys; j=json.load(sys.stdin)[\"jobs\"][0]; k=\"read\" if \"$1\"==\"read\" else \"write\"; print(round(j[k][\"bw_bytes\"]/1e6,1))'"; }
measure() { # label layout(osts) rw bs direct file oss_nodes...
  local label=$1 osts=$2 rw=$3 bs=$4 d=$5 f=$6; shift 6
  dropc j "$@"
  local c0=$(nic j) s0=$(nic $1) p0=$(cpu $1)
  local bw=$(fiorun $rw $bs $d $f)
  local c1=$(nic j) s1=$(nic $1) p1=$(cpu $1) m=$(mem $1) cm=$(mem j)
  local crx=$(( ($(echo $c1|cut -d' ' -f1) - $(echo $c0|cut -d' ' -f1)) / 1048576 ))
  local ctx=$(( ($(echo $c1|cut -d' ' -f2) - $(echo $c0|cut -d' ' -f2)) / 1048576 ))
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$label" "$osts" "$rw" "$bs" "$d" "$bw" "$crx" "$ctx" "$(cpupct "$p0" "$p1")" "$m" "$cm"
}
echo -e "label\tosts\trw\tbs\tdirect\tMB_s\tclient_rx_MiB\tclient_tx_MiB\toss1_cpu_pct\toss1_mem_MiB\tclient_mem_MiB"
rx j "mkdir -p $T && rm -f $T/*"
for i in 0 1 2; do
  f=$T/ost$i; rx j "lfs setstripe -c 1 -i $i $f"; o=${OSS_OF[$i]}
  for rep in 1 2 3; do measure ost$i "$i" write 4M 1 $f $o; measure ost$i "$i" read 4M 1 $f $o; done
  measure ost$i "$i" write 1M 1 $f $o; measure ost$i "$i" read 1M 1 $f $o
  measure ost$i "$i" write 4M 0 $f $o; measure ost$i "$i" read 4M 0 $f $o
  rx j "rm -f $f"
done
for sc in 2 3; do
  f=$T/sc$sc; rx j "lfs setstripe -c $sc -i 0 $f"
  for rep in 1 2 3; do measure stripe$sc "0-$((sc-1))" write 4M 1 $f j1 j2 j3; measure stripe$sc "0-$((sc-1))" read 4M 1 $f j1 j2 j3; done
  rx j "rm -f $f"
done
