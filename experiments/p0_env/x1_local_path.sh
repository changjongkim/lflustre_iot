#!/bin/bash
# go/no-go ①: 서버 노드(jetson1)에 client를 마운트하고 로컬 OST(OST0000)와 원격 OST(OST0001) 경로를 비교한다.
# 노드 안에서 측정하므로 SSH 조회에 의한 CPU 오염이 없다.
s() { echo "$SUDO_PW" | sudo -S -p '' "$@"; }
MNT=/mnt/lustrefs; T=$MNT/llmio_test/x1_$(hostname -s)
dropc() { s sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'; }
nic() { awk '/enP8p1s0/{print $2, $10}' /proc/net/dev; }
cpu() { head -1 /proc/stat; }
pct() { python3 -c "
a=list(map(int,'$1'.split()[1:])); b=list(map(int,'$2'.split()[1:]))
i=(b[3]+b[4])-(a[3]+a[4]); t=sum(b)-sum(a); print(round(100*(1-i/t),1))"; }
mf() { awk '/MemFree/{f=$2} /^Cached/{c=$2} END{printf "MemFree=%dMiB Cached=%dMiB", f/1024, c/1024}' /proc/meminfo; }
run() { # label ost rw direct
  local f=$T/$1; dropc; local n0=$(nic) c0=$(cpu) m0=$(mf)
  local bw=$(fio --name=x1 --filename=$f --rw=$3 --bs=4M --size=2G --direct=$4 --ioengine=libaio --iodepth=16 --output-format=json 2>/dev/null | python3 -c "import json,sys;j=json.load(sys.stdin)['jobs'][0];k='read' if '$3'=='read' else 'write';print(round(j[k]['bw_bytes']/1e6,1))")
  local n1=$(nic) c1=$(cpu) m1=$(mf)
  local rx=$(( ($(echo $n1|cut -d' ' -f1)-$(echo $n0|cut -d' ' -f1))/1048576 )) tx=$(( ($(echo $n1|cut -d' ' -f2)-$(echo $n0|cut -d' ' -f2))/1048576 ))
  printf "%-14s ost=%s %-5s direct=%s  %7s MB/s  nic_rx=%5sMiB nic_tx=%5sMiB  cpu=%5s%%  before[%s] after[%s]\n" "$1" "$2" "$3" "$4" "$bw" "$rx" "$tx" "$(pct "$c0" "$c1")" "$m0" "$m1"
}
echo "== mount client on $(hostname -s)"
mount -t lustre | grep -q " $MNT " || { s mkdir -p $MNT && s mount -t lustre 192.168.0.50@tcp:/lustrefs $MNT && echo mounted; }
mount -t lustre | grep " $MNT "
mkdir -p $T && lfs setstripe -c 1 -i 0 $T/local && lfs setstripe -c 1 -i 1 $T/remote
echo "local file OST: $(lfs getstripe -i $T/local), remote file OST: $(lfs getstripe -i $T/remote)"
for r in 1 2 3; do
  run local 0 write 1; run local 0 read 1
  run remote 1 write 1; run remote 1 read 1
done
run local 0 read 0; run remote 1 read 0
rm -rf $T; dropc
