#!/bin/bash
# go/no-go ③: Lustre client 캐시가 찬 상태에서 GPU 메모리 할당(cudaMalloc + memset)이 늦어지거나 실패하는지 측정한다.
s() { echo "$SUDO_PW" | sudo -S -p '' "$@"; }
W=~/lflustre_iot_work; mkdir -p $W; MNT=/mnt/lustrefs; F=$MNT/llmio_test/x3_$(hostname -s)/fill
dropc() { s sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'; }
mf() { awk '/MemFree/{f=$2} /MemAvailable/{a=$2} /^Cached/{c=$2} END{printf "MemFree=%d MemAvail=%d Cached=%d MiB", f/1024, a/1024, c/1024}' /proc/meminfo; }
cat > $W/gpu_alloc.cu <<'CU'
#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <vector>
#include <cuda_runtime.h>
int main(int argc, char** argv){
  size_t chunk = 256ull<<20; int n = atoi(argv[1]);           // n x 256MiB
  cudaFree(0); std::vector<void*> ps; double worst = 0;
  auto t0 = std::chrono::steady_clock::now(); int ok = 0;
  for (int i = 0; i < n; i++) {
    auto a = std::chrono::steady_clock::now(); void* p = nullptr;
    cudaError_t e = cudaMalloc(&p, chunk);
    if (e == cudaSuccess) e = cudaMemset(p, 1, chunk);
    cudaDeviceSynchronize();
    double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - a).count();
    if (e != cudaSuccess) { printf("FAIL at chunk %d (%s) after %.1f ms\n", i, cudaGetErrorString(e), ms); break; }
    ps.push_back(p); ok++; if (ms > worst) worst = ms;
  }
  double tot = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  printf("allocated %d x 256MiB = %.2f GiB, total %.0f ms, worst chunk %.0f ms\n", ok, ok*0.25, tot, worst);
  for (auto p: ps) cudaFree(p); return 0;
}
CU
/usr/local/cuda/bin/nvcc -O2 -o $W/gpu_alloc $W/gpu_alloc.cu 2>&1 | grep -v warning | tail -2
mkdir -p $(dirname $F); lfs setstripe -c 1 -i 0 $F 2>/dev/null; dd if=/dev/zero of=$F bs=4M count=900 oflag=direct status=none   # 3.5GiB, 로컬 OST
orig=$(s lctl get_param -n llite.*.max_cached_mb | awk '/^max_cached_mb/{print $2}')
for N in 16 20; do   # 4GiB, 5GiB
  echo "===== target $((N/4)) GiB"
  dropc; echo "[A] cache empty      | $(mf)"; $W/gpu_alloc $N
  dropc; dd if=$F of=/dev/null bs=4M status=none
  echo "[B] cache full (cap ${orig}MB) | $(mf)"; $W/gpu_alloc $N; echo "    after: $(mf)"
  s lctl set_param llite.*.max_cached_mb=512 >/dev/null
  dropc; dd if=$F of=/dev/null bs=4M status=none
  echo "[C] cache capped 512MB | $(mf)"; $W/gpu_alloc $N
  s lctl set_param llite.*.max_cached_mb=$orig >/dev/null
done
echo "restored max_cached_mb=$(s lctl get_param -n llite.*.max_cached_mb | awk '/^max_cached_mb/{print $2}')"
rm -rf $(dirname $F); dropc
