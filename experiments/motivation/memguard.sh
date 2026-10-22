#!/bin/bash
# 메모리 보호 (F7 대응): MemAvailable이 기준 아래로 내려가면 실험이 띄운 llama-server와 fio를 끝내 노드 정지를 막는다.
# jetson1은 MemAvailable이 약 40MB까지 떨어진 뒤 zram 스왑이 차면서 두 번 멈췄다.
# 사용: nohup memguard.sh <log> [threshold_MiB=700] [seconds=7200] &
LOG=$1; TH=${2:-700}; DUR=${3:-7200}; END=$(( $(date +%s) + DUR ))
while [ $(date +%s) -lt $END ]; do
  a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  if [ $a -lt $TH ]; then
    echo "$(date +%T) MemAvailable ${a}MiB < ${TH}MiB: stopping llama-server and fio" >> $LOG
    pkill -f 'llama-serve[r] -m'; pkill -f 'fio --nam[e]=m'
    sleep 5
  fi
  sleep 1
done
