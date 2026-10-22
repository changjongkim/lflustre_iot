#!/bin/bash
# P0 C8: llama.cpp(CUDA) 빌드와 Qwen3-4B Q4_K_M 다운로드. 사용자 영역(홈, Lustre 테스트 디렉터리)만 사용한다.
set -u
W=~/lflustre_iot_work; M=/mnt/lustrefs/llmio_test/models; mkdir -p $W $M
LOG=$W/c8_setup.log; : > $LOG
(
  echo "[$(date +%T)] download start"
  curl -sL --retry 3 -o $M/Qwen3-4B-Q4_K_M.gguf \
    https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf
  echo "[$(date +%T)] download done: $(ls -l $M/Qwen3-4B-Q4_K_M.gguf | awk '{print $5}') bytes"
) >> $LOG 2>&1 &
(
  echo "[$(date +%T)] build start"
  [ -d $W/llama.cpp ] || git clone --depth 1 https://github.com/ggml-org/llama.cpp $W/llama.cpp
  cd $W/llama.cpp && git log -1 --format='commit %h %cd'
  cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87 -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
        -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release > $W/c8_cmake.log 2>&1 && \
  cmake --build build --target llama-server llama-cli llama-bench -j 4 > $W/c8_build.log 2>&1
  echo "[$(date +%T)] build exit=$? bins: $(ls build/bin 2>/dev/null | tr '\n' ' ')"
) >> $LOG 2>&1 &
wait
echo "[$(date +%T)] all done" >> $LOG
