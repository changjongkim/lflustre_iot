#!/bin/bash
# P0 C5: client(jetson) 메모리 예산 실측. llite 캐시 상한은 비영구로 바꾸고 마지막에 원래 값으로 복원한다.
s() { echo "$SUDO_PW" | sudo -S -p '' "$@"; }
memline() { awk '/MemAvailable|^Cached|MemFree/{printf "%s=%dMiB ", $1, $2/1024}' /proc/meminfo; echo; }
dropc() { s sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'; }
W=~/lflustre_iot_work; mkdir -p $W; T=/mnt/lustrefs/llmio_test/c5; mkdir -p $T
echo "== 0 baseline (after drop_caches)"; dropc; memline
echo "== other big processes (RSS MiB)"; ps -eo rss,comm --sort=-rss | head -8 | awk 'NR==1{print;next}{printf "%d %s\n", $1/1024, $2}'

echo "== 1 CUDA context overhead"
cat > $W/cuda_ctx.cu <<'CU'
#include <cstdio>
#include <unistd.h>
#include <cuda_runtime.h>
int main(){ void*p; cudaFree(0); cudaMalloc(&p, 64<<20); cudaMemset(p,0,64<<20); cudaDeviceSynchronize(); printf("ctx_ready\n"); fflush(stdout); sleep(8); cudaFree(p); return 0; }
CU
/usr/local/cuda/bin/nvcc -O2 -o $W/cuda_ctx $W/cuda_ctx.cu 2>&1 | tail -2
dropc; before=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
$W/cuda_ctx > $W/cuda_ctx.out & pid=$!
for i in $(seq 1 20); do grep -q ctx_ready $W/cuda_ctx.out 2>/dev/null && break; sleep 0.5; done; sleep 1
during=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); rss=$(ps -o rss= -p $pid | awk '{print int($1/1024)}')
wait $pid
echo "MemAvailable before=${before}MiB during=${during}MiB delta=$((before-during))MiB (incl. 64MiB buffer), process RSS=${rss}MiB"

echo "== 2 Lustre client cache growth (buffered 2GiB read)"
orig=$(s lctl get_param -n llite.*.max_cached_mb | awk '/^max_cached_mb/{print $2}')
echo "original max_cached_mb=$orig"
lfs setstripe -c 1 -i 1 $T/f2g 2>/dev/null; dd if=/dev/zero of=$T/f2g bs=4M count=512 oflag=direct status=none
for cap in $orig 512; do
  s lctl set_param llite.*.max_cached_mb=$cap >/dev/null
  dropc; b=$(memline); dd if=$T/f2g of=/dev/null bs=4M status=none; a=$(memline)
  used=$(s lctl get_param -n llite.*.max_cached_mb | awk '/^used_mb/{print $2}')
  echo "cap=${cap}MiB | before: $b| after: $a| llite used_mb=$used"
done
s lctl set_param llite.*.max_cached_mb=$orig >/dev/null; echo "restored max_cached_mb=$(s lctl get_param -n llite.*.max_cached_mb | awk '/^max_cached_mb/{print $2}')"
rm -f $T/f2g; dropc
