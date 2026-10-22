# 설계 상세

> README 4장(Design)의 상세 자료이다. README에는 요약만 두고, 세부 절차·표·예시는 이 문서에 둔다.

## 1. 현재 실제 구성과 메모리 실측

| 호스트 | 설계 노드 | 현재 Lustre 역할 | NVMe 사용 | client 마운트 | 설계와의 차이 |
|---|---|---|---|---|---|
| jetson0 | NM | MGS + MDT0000 | Samsung 970 EVO Plus 500GB: MGT 8GB + MDT 457.8GB | 없음 | 없음 (플래너는 실험 시 실행) |
| jetson1 | N1 | OSS, OST0000 | Samsung 980 500GB 전체 | 없음 | client 마운트 추가 필요 |
| jetson2 | N2 | OSS, OST0001 | Samsung 980 500GB 전체 | 없음 | client 마운트 추가 필요 |
| jetson3 | N3 | OSS, OST0002 | Samsung 980 500GB 전체 | 없음 | client 마운트 추가 필요 |
| jetson | N0 | Client | 없음 | `/mnt/lustrefs` | 없음 |

- 5대 모두 Orin Nano Super(25W), L4T R36.4.4, Lustre 2.17.0(ldiskfs), OS는 microSD, GUI 켜짐, zram 3.8GB이다.
- 데이터 경로는 유선 1Gb/s이다. jetson 송신만 약 725Mb/s이다.
- **A' 적용 방법:** jetson1–3에 client를 비영구로 마운트하고 캐시 상한(512MB)을 설정한다. 되돌릴 때는 `umount`만 하면 된다. 포맷, 재구축, 장치 추가는 없다(`docs/hyperconverged_plan.md`).
- **MGS 주소:** 서버의 MGS 연결이 무선 IP로 설정되어 끊겨 있다(`docs/testbed.md` F1). client 마운트와 실험 조작에는 영향이 없으므로 당장 고치지 않는다. 서버 재부팅, OST 추가, 영구 설정(`set_param -P`)이 필요할 때 정정한다.
- **5-OST 구성(방안 B)은 제외했다.** jetson에 NVMe가 없고 jetson0 NVMe는 MGT·MDT가 전부 쓰므로, 장치 추가와 MDT 재구축이 필요하다.
- 현재 분리형 구성(jetson만 client)은 관찰 실험의 비교 기준으로도 쓴다.

**노드별 메모리 예산의 근거와 P0 실측**

- **상주 가능한 컨텍스트 수:** 3-stage에서 8k 컨텍스트 하나는 stage당 384MiB(12 layer)이다. 따라서 N1 약 3개, N2 약 5개, N3 약 2개를 메모리에 둘 수 있다. 8개 컨텍스트 중 대부분은 저장 계층에 있다.
- **stage별 상주 차이:** stage마다 상주 가능한 수가 다르므로, 어떤 요청은 일부 stage에서만 메모리 적중이 일어난다. 이 경우 TTFT는 저장 계층에서 읽어야 하는 stage가 결정한다(3.2절 2f).
- **캐시 상한:** Lustre client 캐시를 기본값(약 3.7GB)으로 두면 KV 상주 공간이 없어진다. 따라서 상한 설정은 필수 조건이다.
- **N0의 대체 stage 여유:** 남는 4.6GB로 대체 stage(런타임 1.2GB + 가중치 최대 3.2GB)를 올릴 수 있다. KV 상주 공간은 거의 남지 않으므로, 대체 중에는 KV를 원격에서 읽거나 재계산한다. jetson의 실험과 무관한 프로세스(F4)를 정리한다는 전제이다.

**P0 실측 (2026-10-22, jetson·서버 노드)**

| 항목 | 실측 | 위 추정과 비교 |
|---|---|---|
| OS + GUI + 서비스 (서버 노드 유휴) | 약 0.8GB 사용, MemAvailable 약 6.5–6.6GB | GUI가 켜진 상태. headless로 전환하면 줄어듦 |
| 실험과 무관한 프로세스 (jetson) | 약 1.8GB (`node` 4개, `codex`, GNOME, docker) | 실험 전 정리 필요 |
| CUDA 컨텍스트 (PyTorch 제외) | 약 74MiB | PyTorch 오버헤드는 미측정 (미설치) |
| Lustre 서버 memused | 약 120MiB | 추정(0.3GB) 이내 |
| client 캐시 상한 기본값 | 3,810MB (RAM의 1/2) | 가정과 일치. 2GiB buffered 읽기에서 MemFree가 2.16GB 감소 |
| client 캐시 상한 512MB 적용 시 | 캐시 증가가 약 0.38–0.49GB에서 멈춤 | 상한 설정이 실제로 작동함 |
| 플래너 (llama.cpp, Qwen3-4B Q4_K_M, ctx 4096) | 약 4.1GB | 추정 3.0GB보다 큼. 그래서 플래너를 NM(jetson0)에 둔다 |
| Lustre 캐시 3.9GB가 찬 상태의 GPU 할당 | 실패 없음, 할당 시간 +25%, 최악 지연 2배 | 캐시 상한으로 해소 |

## 2. 모델 선정 상세

### 2.1 선정 기준

1. 목표 정밀도에서 노드 1대에 가중치와 KV가 함께 들어가지 않아야 한다.
2. 3대로 나눴을 때 노드당 메모리가 7.4GiB 안에 들어가야 한다.
3. base 가중치를 공유한 LoRA 학습의 추가 메모리가 수백 MB 이내여야 한다.
4. GQA 구조여야 한다.
5. HF transformers와 llama.cpp에서 모두 실행할 수 있어야 한다.
6. 가중치가 공개되어 있어야 한다.

### 2.2 기본 구성

| 역할 | 모델 | 정밀도 | 크기 | 실행 노드 |
|---|---|---|---|---|
| 서빙 (W3), 수집 시점 prefill (W1) | Qwen3-4B | FP16 | 약 8.0GB | N1–N3 (stage당 LG 4개) |
| 적응 학습 (W2) | Qwen3-4B + LoRA (LG9–11) | FP16 base 공유, LoRA FP32 | N3 추가 약 0.3GB | N1–N3 (backward는 N3) |
| 플래너 (⑦) | Qwen3-4B | Q4_K_M (GGUF) | 파일 약 2.5GB, 실행 시 약 4.1GB | NM (llama.cpp) |
| 플래너 비교 | Qwen3-1.7B / Qwen3-0.6B | Q8_0 | 약 1.8GB / 0.6GB | NM |
| 비교 대상 B7 | Qwen3-4B | Q4_K_M | 약 2.5GB | N1–N3 각각 (복제 서빙) |
| 서빙 규모 민감도 (선택) | Qwen3-8B | Q8_0 (llama.cpp RPC) | 약 8.7GB | N1–N3 (O1–O3만) |
| 작은 모델 민감도 | Qwen3-1.7B | FP16 | 약 3.4GB | 2-stage 또는 1대 |

**서빙 모델 분할**
- 36 layer를 g=3으로 묶어 LG 12개(LG0–LG11, LG당 약 0.6GB)를 만든다.
- 임베딩(약 0.78GB)은 입력과 출력 head가 공유한다. stage 1과 stage 3이 모두 필요하므로 FLR mirror로 두 노드에 둔다.
- 초기 분할: `{N1: LG0–3 + 임베딩, N2: LG4–7, N3: LG8–11 + head}`
- LoRA를 적용하는 LG9–11은 모두 N3에 있다.

**적응 학습 설정**

| 항목 | 값 |
|---|---|
| LoRA 적용 범위 | LG9–11 (layer 27–35). 비교: 전체 LG |
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 |
| 대상 projection | q, k, v, o |
| 시퀀스 길이 | 512–1024 |
| micro-batch / gradient accumulation | 1 / 8 |
| 라운드당 step | 50–100 (측정 후 조정) |
| 체크포인트 간격 | 25 step |
| 대용량 체크포인트 민감도 | rank 64, 전체 linear (N3에서 약 0.4GB) |

### 2.3 선택하지 않은 대안과 이유

| 대안 | 이유 |
|---|---|
| Qwen3-4B Q8_0을 노드 1대에 | KV 여유가 1GB 미만이다. |
| Qwen3-4B Q4_K_M 노드별 복제 | 품질 저하, KV 공유 없음, 학습 불가. 비교 대상(B7)으로만 사용 |
| Qwen3-8B FP16 분할 | 3-stage에서 stage당 가중치가 약 4.6–5.9GB로 메모리 초과 |
| 노드 1대 단독 QLoRA | Jetson ARM64 bitsandbytes 불안정, 메모리 부족 |
| 전체 layer LoRA | 어댑터가 바뀔 때마다 모든 LG의 KV가 무효가 된다. 비교 구성으로만 사용 |
| 위치 독립 근사 재사용 (CacheBlend 방식) | 품질 영향이 있다. 이어 쓰기 컨텍스트로 근사 없이 재사용할 수 있으므로 채택하지 않는다. 선택 비교 대상으로만 둔다. |

## 3. 해결 요소 상세

### 3.1 ⑧ 분산 추론의 분할과 가중치 배치

**정의**

LG 12개를 N1–N3에 연속 구간으로 배정해 파이프라인 추론을 수행한다. 각 stage는 자기 LG 가중치를 Lustre에서 읽는다. 장애에 대비해 대체 분할과 복제 위치를 미리 정한다.

**해결해야 하는 이유**
1. **모델이 노드 1대에 들어가지 않는다.** FP16 약 8.0GB는 가용 7.4GiB보다 크다.
2. **로드 시간이 곧 서비스 중단 시간이다.** stage 가중치(2.4–3.2GB)를 로컬 NVMe에서 읽으면 수 초 이내이지만, 1GbE 원격으로 읽으면 약 21–28초이다.
3. **기본 레이아웃은 모든 노드에 부하를 준다.** LG 파일이 OST 전체에 흩어져 대부분 원격 읽기가 되고, 다른 stage 노드의 OSS에도 부하가 생긴다.
4. **striping이 이득이 되지 않는다.** 1GbE에서는 원격 stripe가 가장 느린 stripe가 되어 파일 읽기 전체를 늦춘다.
5. **장애 시 데이터도 함께 사라진다.** 노드 장애가 나면 연산과 OST가 함께 사라진다. 연산이 없는 OST가 없으므로 복제본도 다른 stage 노드에 두어야 한다.
6. **임베딩은 소비 노드가 둘이다(stage 1, 3).**
7. **분할과 배치는 따로 정할 수 없다(D5).**

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 8a | 분할 P 선택: LG별 연산 시간, 출력 head 연산, 학습(N3), 노드별 I/O 부하, 메모리를 함께 고려 |
| 8b | 가중치 배치: LG 파일과 임베딩의 OST, stripe count |
| 8c | 장애 대비: 대체 분할과 mirror 위치 |
| 8d | 재분할: 이동량과 서빙 영향 최소화 |

**해결 방법**
1. **LG 단위 파일.** `weights/<model>/lg{i}.safetensors`(약 0.6GB)로 저장한다. 재분할할 때 파일 단위로 이동한다.
2. **기본 배치.** LG 파일은 소비 노드 OST에 둔다(`lfs setstripe -c 1 -i <OST>`). 임베딩은 stage 1 OST에 두고 stage 3 OST에 mirror를 둔다.
3. **stripe count는 1로 고정한다.** O1의 striping 측정 결과를 근거로 쓴다.
4. **이웃 stage mirror.** stage k의 LG 가중치는 다음 stage 노드 OST에 FLR mirror를 둔다(N1 → N2 → N3 → N1). 임베딩은 두 소비 노드(N1, N3)에 이미 한 벌씩 있다. 노드당 추가 저장량은 약 2.4GB이고, 읽기 전용이므로 동기화 비용이 없다. 이웃 노드도 서빙 노드이므로, mirror 생성 I/O는 비용 모델이 고른 저부하 시점에 TBF로 속도를 제한해 수행한다.
5. **대체 분할 두 가지.**

   | 대체 분할 | 내용 | 장점 | 단점 |
   |---|---|---|---|
   | P'_k (N0 대체) | N0가 N_k의 LG 구간을 넘겨받고, 이웃 stage mirror에서 원격으로 읽는다(2.4–3.2GB, 약 21–28초). | 남은 stage와 플래너(NM)를 그대로 유지 | N0에 OST가 없어 KV pack도 원격 읽기 |
   | P''_k (2-stage 재분할) | 남은 2개 노드에 LG를 다시 나눈다. | 추가 노드 불필요 | FP16에서는 노드당 가중치가 약 4.4GB(LG 6개 + 임베딩)로 KV 공간이 남지 않는다. INT8 weight-only로 바꿀 때만 가능 |

   기본값은 P'_k이다.
6. **분할 선택.** C(11,2)=55개 후보를 비용 모델로 전수 평가한다. 규모가 커지면 동적 계획법을 쓴다.
7. **재분할.** 바뀐 LG 파일만 이동한다. 새 담당 노드는 먼저 mirror에서 읽어 서비스를 재개하고, 이후 저부하 구간에 자기 OST로 `lfs migrate`한다. 이동 I/O는 TBF로 속도를 제한한다. N0는 OST가 없으므로 원격 읽기를 유지하고, 장애 노드가 복귀하면 stage를 반납한다.

**검증 방법**
- 초기 로드 시간과 로드 중 다른 stage 처리량
- stripe count 1/2/3 비교
- 재분할 시 이동 바이트와 시간
- 장애 복구 시간 (mirror 없음 / 이웃 stage mirror + P'_k / P''_k(INT8))

**관련 연구와의 차이**

EdgeShard, PipeEdge, LOIP는 연산·메모리·네트워크로 분할한다. 본 기법은 분할에 저장 I/O 부하를 포함하고, 분할 결과로 배치를 함께 정하고, 장애 대체 분할을 기준으로 복제 위치를 정한다.

**원 IFLustre와의 관계**

시작 OST 지정을 그대로 쓰고, 할당 기준을 소비 노드와 연산 부하로 확장한다. 1GbE에서 stripe count 증가가 불리한 현상은 원 관찰("성능은 가장 느린 OSS가 결정")의 연장으로 설명한다.

### 3.2 ② 의미 기반 content-addressed KV 저장소

**정의**

스트림 단위로 뒤에만 이어 쓰는 컨텍스트를 유지하고, 그 KV를 데이터 수집 시점에 미리 계산한다. 계산한 KV는 내용 주소로 식별되는 객체로 DFS에 저장한다. 요청은 컨텍스트의 KV를 주소로 찾아 읽고, 아직 계산되지 않은 꼬리 부분과 질문만 prefill한다.

**설계 원칙: 이름, 위치, 정책의 분리**

| 구분 | 결정 근거 | 예 |
|---|---|---|
| 이름 (식별) | 내용 | 토큰 체인 해시, 모델 버전, 해당 LG에 영향을 주는 어댑터 버전, LG 번호 |
| 위치 (배치) | 비용 모델 (README 4.9.3절) | 어느 OST, mirror 여부, 메모리 상주 여부 |
| 정책 | IoT 의미 정보 | 스트림·라인(묶음 단위, 우선순위), 시간(보존, 압축 대상), 이상 여부(압축 시 원문 유지), 접근 패턴(미리 읽기) |

이름이 위치와 독립이므로, 객체를 옮기거나 복제해도 이름과 유효성이 바뀌지 않는다. 의미 정보는 이름에 들어가지 않으므로, 정책을 바꿔도 객체를 다시 만들 필요가 없다.

**해결해야 하는 이유**
1. **슬라이딩 윈도우에서 prefix 재사용이 깨진다.** 기존 요청 시점 prefix 재사용(vLLM, LMCache)에서는 기록 구간이 매번 다시 계산된다(README 2.4.1절).
2. **Orin Nano에서 prefill은 비용이 크다.** Qwen3-4B 8k 토큰 prefill은 약 8.6e13 FLOP으로, 3-stage에서 수 초에서 10초 이상 걸린다(추정, O4). 반면 로컬 NVMe에서 stage당 KV 384MiB를 읽는 데는 약 0.15–0.3초가 걸린다.
3. **스트림 컨텍스트 KV는 메모리보다 크다.** 8개 컨텍스트 × 8k이면 stage당 약 3GiB로, 상주 가용량(0.9–2.0GB)을 넘는다. 16k 한계에서는 두 배가 된다. 저장 계층이 필수이다.
4. **여러 요청이 같은 내용을 공유한다.** 같은 라인의 컨텍스트는 지시문·매뉴얼 KV를 공유한다. 같은 스트림을 묻는 여러 운영자는 같은 스트림 로그 KV를 공유한다. 내용 주소로 중복 없이 한 번만 저장하고 계산한다.
5. **분할 변경, 장애, 복제를 단순하게 만든다.** 봉인된 객체는 바뀌지 않으므로 복제본이 낡지 않고, 이름이 위치와 무관하므로 재배치가 위치 변경만으로 끝난다.
6. **어댑터 버전이 KV 유효성을 바꾼다.** 버전 의존성을 이름에 넣어야 잘못된 KV를 재사용하지 않는다.
7. **KV I/O는 간섭의 원인이자 피해자이다.** 수집 시점 prefill의 KV 쓰기와 컨텍스트 읽기, 요청 시점 KV 읽기가 모두 저장 위치 노드의 OSS, NIC, 메모리를 쓴다. 원격에서 읽히는 KV는 그 노드의 송신 링크를 써서 activation 전달과 경쟁한다(M9).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 2a | 주소 설계: 무엇을 이름에 넣는가 |
| 2b | 컨텍스트 구성: 토큰 단위 결정성, chunk 경계 |
| 2c | 수집 시점 prefill: 배치 간격, 읽기 증폭(D8), 데이터 최신성 |
| 2d | 묶음(pack)과 인덱스: 메타데이터 비용, 조회 비용 |
| 2e | 배치와 복제: LG pack의 OST, 공유 prefix와 봉인된 pack의 mirror |
| 2f | 메모리 상주와 미리 읽기: stage별 상주 집합, stage 간 조정 |
| 2g | 압축: 시점, 결정적 규칙, 이상 기록 보존 |
| 2h | 어댑터 버전과 유효성: 범위 반영 주소, 부분 재생성 |
| 2i | 수거(GC)와 용량 |
| 2j | 읽기 경로: 재계산 vs 읽기 선택, 캐시 이중 점유 |

**해결 방법**

1. **주소 (2a)**

   ```
   chain_0  = H(model_id ‖ tokenizer_id)
   chain_n  = H(chain_{n-1} ‖ tokens(chunk_n))                  # chunk 단위 체인 해시
   key(i,n) = H(model_id ‖ adapter_scope_version(i) ‖ LG_i ‖ chain_n)
   adapter_scope_version(i) = LG_i 이하 layer에 적용된 어댑터 버전 (없으면 "none")
   ```

   - LoRA를 LG9–11에만 적용하면 LG0–8의 주소에는 어댑터 버전이 들어가지 않는다. 따라서 적응 라운드가 지나도 그대로 유효하다.
   - 체인 해시 덕분에 같은 앞부분을 가진 컨텍스트끼리 chunk를 공유한다. 그래서 같은 라인의 지시문·매뉴얼은 한 번만 저장된다.
   - 세션 턴은 스트림 컨텍스트의 체인에서 갈라지는 별도 체인이 된다.

2. **컨텍스트 구성 (2b)**
   - 레코드를 하나씩 따로 토큰화하고 토큰 ID를 이어 붙인다. 텍스트를 합친 뒤 토큰화하면 경계에서 토큰이 합쳐질 수 있어 결정성이 깨지기 때문이다.
   - 컨텍스트 시작부터 256토큰마다 chunk 경계를 고정한다. 가득 찬 chunk만 객체가 되고(봉인), 덜 찬 꼬리는 요청 시 prefill한다.
3. **수집 시점 prefill (2c)**
   - N0의 Prefill Scheduler가 스트림별로 봉인 가능한 chunk를 모아, 배치 간격(기본 5분, 변수 1–15분)마다 파이프라인에 낮은 우선순위 작업으로 넣는다. 서빙 요청이 우선이다.
   - 작업을 실행하려면 그 컨텍스트의 이전 KV가 각 stage 메모리에 있어야 한다. 상주하지 않은 컨텍스트는 저장소에서 읽어야 한다(읽기 증폭).
   - 배치 간격은 다음 셋의 균형으로 정한다.
     - 길수록 읽기 증폭과 연산 횟수가 줄어든다.
     - 길수록 요청 시점 꼬리 prefill(데이터 최신성)이 늘어난다.
     - 연산 여유와 SLO에 맞아야 한다.
   - 비용 모델과 플래너가 스트림별로 조정한다.
   - 연산 비용 추정: 8개 스트림, 스트림당 시간당 7.2k 토큰이면 시간당 약 5.8만 토큰이다. 이는 시간당 수십 초에서 수 분의 파이프라인 연산으로, 유휴 시간의 일부를 쓴다(O7에서 측정).
4. **묶음과 인덱스 (2d)**
   - 같은 (컨텍스트, LG, epoch)의 chunk를 순서대로 pack 파일에 이어 쓴다(32 chunk, LG당 96MiB).
   - 가득 차면 pack을 봉인하고, 이후에는 수정하지 않는다.
   - 스트림 로그 chunk의 위치는 (컨텍스트, epoch, chunk 순번)으로 경로와 오프셋을 계산한다. pack 헤더에 기록된 주소로 내용을 검증한다.
   - 공유 prefix chunk는 라인별 공유 pack에 두고, 작은 전역 인덱스(주소 → 경로·오프셋)로 찾는다.
   - chunk마다 파일을 만드는 방식(세션당 수백 개 파일)보다 MDS 메타데이터 연산이 크게 줄어든다. 원 IFLustre의 소파일 관찰을 반영한 설계이다.
5. **배치와 복제 (2e)**
   - LG i의 pack은 LG i 소비 노드 OST에 둔다(로컬 쓰기·읽기).
   - 비용 모델이 소비 노드를 병목으로 판단하면, 새 pack의 위치를 다른 노드로 바꾼다(디렉터리 default layout).
   - 공유 prefix pack은 이웃 stage 노드 OST에 FLR mirror를 둔다. 봉인된 스트림 pack의 복제 여부는 의미 정보(라인 우선순위, 이상 구간 포함 여부)로 정한다.
   - 이웃 노드도 서빙 노드이므로, 복제는 비용 모델이 고른 저부하 시점에 TBF로 속도를 제한해 실행한다. 봉인된 pack은 바뀌지 않으므로 mirror가 낡지 않는다.
6. **메모리 상주와 미리 읽기 (2f)**
   - 각 stage는 상주 집합 R_k를 가진다.
   - 요청 TTFT는 상주하지 않은 stage들의 KV 읽기 시간 중 최댓값이 결정한다. 그래서 상주 집합을 stage마다 독립적으로 정하지 않고 같은 컨텍스트를 함께 상주시키도록 조정한다. 상주 공간이 가장 작은 stage(N3)가 기준이 된다.
   - 운영 정책의 시간대 정보(교대 시각, 라인 우선순위)로 요청이 몰릴 스트림 컨텍스트를 미리 읽는다.
7. **압축 (2g)**
   - 컨텍스트가 한계에 도달하면 결정적 규칙으로 압축한다.
     - 일정 시간보다 오래된 정상 레코드는 구간별 통계 한 줄로 요약한다.
     - 경고·이상 레코드는 원문 그대로 유지한다.
   - 새 epoch 컨텍스트는 `[지시문][매뉴얼][헤더][요약][최근 레코드]`이다.
   - 공유 prefix KV는 그대로 재사용하고, 요약 이후 부분만 다시 계산한다.
   - 이전 epoch 객체는 참조하는 세션이 끝나면 수거 대상이 된다.
   - 규칙 기반이므로 결과가 재현 가능하고 주소 체계와 맞는다. LLM 요약은 선택 비교 항목으로 둔다.
8. **어댑터 버전과 부분 재생성 (2h)**
   - LG9 입력 activation(hidden state, 토큰당 5KiB)을 수집 시점 prefill 중에 함께 저장한다(경계 activation 객체).
   - 새 어댑터 버전으로 전환할 때, LG0–8의 KV는 그대로 쓰고 LG9–11의 KV만 경계 activation에서 다시 계산한다.
   - 비용 비교:
     - 처음부터 다시 계산하는 것보다 연산이 약 75% 줄어든다.
     - 경계 activation 저장 비용은 KV의 약 3.5%이다.
   - 재생성은 컨텍스트별로 진행한다. 재생성이 끝난 컨텍스트부터 새 버전으로 서빙하고, 나머지는 이전 버전 어댑터(LG당 약 2MB)를 함께 유지해 서빙한다.
9. **수거와 용량 (2i)**
   - 다음 기준 중 하나라도 해당하는 객체는 유지하고, 나머지는 유예 시간 뒤 삭제한다.
     - 현재 epoch에서 쓰는 객체
     - 사용 중인 어댑터 버전의 객체
     - 열린 세션이 참조하는 객체
   - OST 사용률이 임계값을 넘으면 오래된 epoch와 세션 객체부터 지운다.
10. **읽기 경로 (2j)**
    - chunk별로 예상 읽기 시간(경로, NIC·OST 부하)과 재계산 시간을 비교해 작은 쪽을 고른다.
    - 읽은 데이터는 GPU 버퍼로 옮긴 뒤 page cache에서 해제한다(`posix_fadvise(DONTNEED)`, direct I/O와 비교).

**검증 방법**

| 항목 | 비교 |
|---|---|
| 슬라이딩 윈도우 요청의 prefix 재사용률과 TTFT | 요청 시점 prefix 재사용 vs 이어 쓰기 컨텍스트 + 수집 시점 prefill |
| 수집 시점 prefill 비용 | 배치 간격별 연산 시간, 읽기 증폭량, 데이터 최신성 |
| 메타데이터 연산 수 | chunk별 파일 vs pack |
| 중복 제거 효과 | 공유 prefix 저장량 |
| 어댑터 전환 비용 | 전체 LoRA(전체 재계산) vs 상위 LG LoRA(경계 activation 재생성) |
| 압축 비용과 품질 | 규칙 압축 vs LLM 요약 vs 압축 없음(한계 도달 시 재계산) |
| stage 간 상주 조정 | 독립 상주 vs 조정 상주의 TTFT |

**관련 연구와의 차이**

| 연구 | 차이 |
|---|---|
| vLLM, SGLang, LMCache, Mooncake | 블록·chunk 해시로 KV를 식별하지만 요청 시점에 만들고, 스트림·버전 범위·의미 정책을 다루지 않는다. |
| Prompt Cache, CacheBlend, EPIC | 정적 모듈을 근사적으로 재사용한다. |
| TurboRAG, MemLLM | 고정 문서의 KV를 미리 계산한다. |
| Venti, LBFS, IPFS | 일반 데이터의 CAS이다. |
| CoStripe | IoT 스트림의 KV를 수집 시점에 만들어 근사 없이 재사용한다. 주소에 어댑터 범위를 반영하고, 의미 정보로 묶음·배치·압축하며, 하이퍼컨버지드 엣지 DFS에서 간섭을 고려해 배치한다. |

**원 IFLustre와의 관계**

소파일 메타데이터 관찰을 pack 설계로, read-aware relocation을 의미 기반 배치와 미리 읽기로 확장한다.

### 3.3 ⑤ 적응 학습과 KV 유효성

**정의**

N0가 학습 샘플을 만들고, 서빙 파이프라인이 FP16 base 가중치를 공유하며 상위 LG(LG9–11)의 LoRA를 학습한다. forward는 전체 stage를 지나고, backward와 학습 상태는 LG9–11을 맡은 N3에만 생긴다. 라운드가 끝나면 새 어댑터로 전환하고, 영향받는 LG9–11의 KV를 다시 만든다.

**해결해야 하는 이유**
1. **모델이 현장 변화를 따라가야 한다.** IoT 데이터 분포는 장비 노후, 라인 변경, 계절로 바뀐다.
2. **적응은 엣지 안에서 해야 한다.** 데이터 반출이 제한된다.
3. **8GB 노드 1대로는 학습할 수 없다.** 서빙 base를 공유하는 공동 학습이 현실적인 유일한 방법이다.
4. **어댑터 변경은 저장 KV를 무효로 만든다.** 전체 layer에 LoRA를 적용하면 매 라운드 모든 컨텍스트의 모든 KV를 다시 만들어야 한다(8개 컨텍스트 × 8k 토큰 전체 prefill). 범위를 제한하고 경계 activation을 쓰면 이 비용이 크게 줄어든다.
5. **체크포인트는 생성 노드에만 두면 장애에 취약하다.** N3가 고장 나면 N3의 OST도 함께 사라진다. 다른 stage 노드로 복제해야 하고, 이 복제는 1GbE와 받는 노드의 서빙과 경쟁한다.
6. **학습 연산과 메모리가 N3에 몰린다.** N3는 출력 head도 계산하므로, 학습까지 더해지면 병목이 될 수 있다. 분할(⑧)이 이를 반영해야 한다.
7. **새 버전은 이벤트를 만든다.** 새 어댑터 버전에는 이력이 없으므로 재계획(⑦)이 필요하다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 5a | LoRA 적용 범위: 적응 품질 vs KV 재생성 비용 vs 학습 비용 |
| 5b | 체크포인트 저장·복제 위치·시점·속도 |
| 5c | 적응 시간대와 연산 비율 |
| 5d | 버전 전환: 컨텍스트별 전환, 이전 버전 유지, 실패 시 롤백 |
| 5e | KV 재생성 일정 (경계 activation 기반) |

**해결 방법**
1. **LoRA 범위 (5a)**
   - 기본은 LG9–11이고, 비교 구성으로 LG6–11과 전체를 둔다.
   - 품질은 라벨이 있는 IoT 판정 과제로 확인한다(README 5.2절).
2. **3단계 체크포인트 (5b)**
   1. 메모리 스냅샷 (N3, rank 16 기준 약 35MB)
   2. 로컬 OST 쓰기
   3. `lfs mirror extend`로 N1 또는 N2 OST에 지연 복제 (비용 모델이 부하가 낮은 노드를 고른다)
   - 복제는 jobid로 태깅하고 TBF로 속도를 제한하며, 저부하 구간에 실행한다.
   - 복제되지 않은 체크포인트가 간격 상한(CkptMax)을 넘으면 속도 제한 범위 안에서 즉시 복제한다.
3. **적응 시간대 (5c)**
   - 플래너가 요청률 예측과 정책으로 시간대와 학습 비율을 정한다.
   - 서빙 요청을 우선 처리하고, 남는 연산에 학습 micro-batch를 넣는다.
   - 선택 최적화: 스트림 컨텍스트에서 만든 학습 샘플은 저장된 경계 activation을 입력으로 쓸 수 있다. 이 경우 N1, N2와 N3의 LG8 forward를 생략할 수 있다.
4. **버전 전환 (5d)**
   - 라운드가 끝나면 어댑터를 확정하고(`adapters/v{n}/lg{i}`) 세 stage OST 모두에 mirror한다(LG당 약 2MB).
   - 재생성이 끝난 컨텍스트부터 새 버전으로 서빙하고, 나머지는 이전 버전으로 서빙한다. 한 요청 안에서는 LG9–11 전체가 같은 버전을 쓴다.
   - 확정에 실패하면 이전 버전을 유지한다.
5. **KV 재생성 (5e)**
   - 비용(경계 activation 읽기, LG9–11 연산, KV 쓰기)을 비용 모델로 계산해 저부하 구간에 컨텍스트별로 실행한다.
   - 요청이 많은 스트림부터 처리하며, 우선순위는 정책과 접근 빈도로 정한다.

**검증 방법**
- 체크포인트·복제 중 TTFT p99
- 학습 처리량과 라운드 완료 시간
- 재생성 소요 시간과 재생성 중 TTFT
- LoRA 범위별 적응 품질
- 장애 시 학습 재개 손실
- 버전 불일치 발생 여부

**관련 연구와의 차이**

FlexLLM 등 공동 실행 연구는 연산 자원 공유를, CheckFreq 등은 학습 처리량을 다룬다. 본 기법은 어댑터 변경이 저장된 KV에 주는 영향을 LoRA 범위와 경계 activation으로 제한하고, 그 재생성·복제 I/O를 서빙 SLO 기준으로 스케줄한다.

**원 IFLustre와의 관계**

runtime-aware allocation을 복제·재생성 I/O의 시점 제어와 속도 제한으로 확장한다.

### 3.4 ③ 공유 자원 간섭(OSS·NIC·메모리) 측정과 완화

**정의**

하이퍼컨버지드 노드에서 여러 I/O 흐름과 pipeline 전달이 같은 공유 자원을 나눠 쓰면서 생기는 지연과 실패이다. 원 IFLustre의 OSS 공유 간섭을 NIC와 노드 메모리로 넓힌 것이다. 경로별 크기는 3장에서 측정했다.

| 경로 | 내용 | 실측 크기 |
|---|---|---|
| OSS 공유 | 동시 흐름이 같은 OSS에 몰리면 총 처리량이 그 OSS의 1GbE로 묶인다. 여러 OST에 걸친 파일은 가장 붐비는 OST가 속도를 정한다. | 공유 시 합계 120MB/s, 분산 시 243–303MB/s, 최악 흐름 14MB/s. 3-stripe 쓰기 −25% (M7) |
| NIC 공유 | stage 노드의 OSS가 처리하는 원격 I/O가 같은 NIC의 activation 전달과 경쟁한다. 원격 읽기는 송신 방향을, 원격 쓰기는 수신 방향을 쓴다. | activation 전달 2.0배(수신 공유), 4.1배(송신 공유). decode 메시지 왕복 0.6 → 4.6ms (M9) |
| 노드 메모리 | 가중치, 상주 KV, 런타임의 호스트 RAM KV 캐시, Lustre client 캐시, OSS·RPC 메모리가 8GB를 나눠 쓴다. 각자 자기 상한만 지킨다. | client 캐시 기본 상한은 RAM의 1/2, GPU 할당 +25% (M4). 런타임 캐시가 요청마다 약 300–370MB 증가, 노드 정지 2회 (M10) |
| 쓰기 시점 | 체크포인트·복제·수집 쓰기가 같은 OST의 지연 민감 읽기와 겹친다. LLM 실행 중에는 같은 노드의 쓰기도 느려진다. | KV 복원 +41%(동시) 대 +2%(지연) (M11). 로컬 direct 쓰기 714 → 559MB/s (M8) |
| 연산 (대조) | 저장 I/O가 CPU·메모리 대역폭을 써서 같은 노드의 LLM 연산을 늦춘다. | prefill·decode 감속 3% 이내. OSS가 CPU 13–19%를 써도 LLM 감속은 거의 없음 (M5, M8) |

**해결해야 하는 이유**
1. **스토리지 전용 노드가 없다.** 모든 OST가 서빙 stage 노드(N1–N3)에 있다. 어떤 객체를 어느 OST에 두는지가 곧 어느 stage의 NIC와 메모리를 쓰는지를 정한다.
2. **차이가 몇 배 단위이다.** OSS 공유(2–2.5배), NIC 공유(2–4배), KV 배치 정책에 따른 TTFT(p50 8–20배, M14)는 연산 감속(3% 이내)보다 훨씬 크다.
3. **메모리 초과는 성능 저하가 아니라 노드 정지이다.** 런타임 KV 캐시와 저장 계층이 서로 모른 채 8GB를 나눠 쓰면 노드가 멈춘다(M10). 노드가 멈추면 그 노드의 OST도 함께 사용할 수 없다.
4. **KV 저장소가 I/O를 늘린다.** 수집 시점 prefill, 재생성, 압축, 복제가 추가 흐름을 만든다. 이 흐름이 어느 OSS·NIC를 거치는지가 서빙에 영향을 준다.
5. **파이프라인이 영향을 키운다(D3).** 한 stage의 activation 전달 지연은 전체 TTFT에 더해진다.
6. **다른 요소들의 공통 입력이다.** 모든 배치 결정의 기준(OSS별 동시 흐름 n_j, NIC 방향별 점유 U_k, 메모리 예산 mem_k)이 된다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 3a | 크기: OSS 공유, NIC 공유(송신·수신), 메모리, 쓰기 시점별 영향. 연산 감속은 대조로 측정 |
| 3b | 배치: 동시 흐름의 OSS 분산, NIC 방향별 부하를 고려한 OST 선택 |
| 3c | 메모리 예산: KV 계층(GPU, 호스트 RAM, 로컬 OST, 원격 OST)과 저장 계층 메모리를 하나의 예산으로 관리 |
| 3d | 시점: 백그라운드 쓰기의 지연과 속도 제한 |
| 3e | 안정성: 메모리 압박 시 노드 보호 |

**해결 방법**
1. **측정 (3a).** README 5.4절 O2에서 측정한다.
   - OSS 공유: 동시 client 수와 OST 배치를 바꾼다.
   - NIC 공유: stage 사이 activation 전달 시간을 원격 읽기·쓰기 부하 아래에서 잰다.
   - 메모리: 노드 내부 샘플러로 MemAvailable, 회수, 스왑을 기록한다.
   - 연산 감속은 대조 측정으로 함께 기록한다.
2. **OSS 분산 (3b).** 동시에 실행되는 흐름을 서로 다른 OSS로 나눈다(IFLustre interference-free 계승). 같은 OSS의 동시 흐름 수 n_j를 비용 모델에 넣는다.
3. **NIC 인지 배치 (3b).**
   - 원격에서 읽히는 객체(공유 prefix pack, mirror, 대체 stage용 가중치)는 activation을 보내는 stage의 OST에 두지 않는다. 원격 읽기는 그 노드의 송신 방향을 쓰기 때문이다(M9, 4.1배).
   - mirror·복제·재배치는 지연에 민감한 hop의 NIC가 한가한 시점에 한다.
   - stage 노드 OST에 대한 원격 읽기는 NRS TBF로 속도를 제한한다.
4. **메모리 예산 관리 (3c).**
   - CoStripe가 KV 계층(GPU 메모리, 호스트 RAM, 로컬 OST, 원격 OST)의 위치를 정한다. LLM 런타임의 호스트 RAM KV 캐시는 끄거나(`--cache-ram 0`) 예산 안의 크기로 제한한다.
   - client 캐시 상한(`max_cached_mb`), OSS·RPC 여유분, 보호 기준(MemAvailable 하한)을 노드별 메모리 예산(README 4.1.3절)에 넣는다.
   - KV 읽기는 direct I/O 또는 캐시 해제로 page cache를 거치지 않는다.
5. **쓰기 시점 (3d).** 체크포인트·복제·수집 시점 prefill 쓰기는 같은 OST의 지연 민감 읽기와 겹치지 않게 미루고, 필요하면 TBF로 속도를 제한한다(IFLustre runtime-aware 계승). LLM 실행 중 같은 노드 쓰기가 22% 느려지므로(M8) 쓰기 완료 시간 추정에 반영한다.
6. **안정성 (3e).** 메모리 보호(MemAvailable 하한 아래에서 백그라운드 작업부터 중지)를 둔다. KV 상주가 가득 찬 상태에서 학습과 원격 I/O를 함께 실행해 장시간 확인한다.

**노드 내 격리 수단 (보조)**

| 수단 | 방법 |
|---|---|
| 캐시 상한 | client `max_cached_mb`, OSS read/writethrough cache |
| 런타임 캐시 | llama.cpp `--cache-ram`, PyTorch 런타임의 KV 캐시 크기 |
| 캐시 해제 | `posix_fadvise(DONTNEED)`, direct I/O |
| 속도 제한 | NRS TBF |
| CPU 분리 | CPT로 OSS 스레드 고정, cgroup cpuset (CPU를 쓰는 작업에 한정) |
| 스왑 | zram 설정 고정 |

**검증 방법**
- OSS별 동시 흐름 수와 처리량, activation 전달 시간, 노드 메모리 추이
- 배치 정책별 TTFT (M14 확장)
- 비용 모델 예측 오차 (목표 평균 15% 이내)
- 연산 감속(대조)이 작다는 것의 재확인: PyTorch FP16 pipeline과 LoRA 학습 (README 9장)

**관련 연구와의 차이**

Heracles 등은 노드 내 CPU·메모리 대역폭 분할을 다룬다. 본 실측에서 GPU 중심 추론은 이 경로에 둔감했다. 본 기법은 데이터 배치로 OSS·NIC 경쟁의 위치를 정하고, 8GB 장치의 메모리 용량을 런타임과 저장 계층에 걸쳐 하나의 예산으로 다룬다.

**원 IFLustre와의 관계**

원 IFLustre의 간섭은 OSS를 공유하는 흐름 사이의 경쟁이었다. 본 기법은 이를 세 가지로 넓힌다.
- 같은 OSS를 공유하는 흐름
- 같은 NIC를 쓰는 저장 I/O와 activation
- 같은 노드 메모리를 쓰는 런타임과 저장 계층

"성능은 가장 느린 OSS가 결정한다"는 관찰은 "TTFT는 가장 느린 stage가 결정하고, stage의 전달 시간과 상주 KV는 그 노드의 OSS가 처리하는 I/O와 메모리 사용에 영향을 받는다"로 확장된다.

### 3.5 ⑦ 이벤트 기반 재계획 (LLM 플래너)

**정의**

이벤트가 발생하면 현재 상태와 운영 정책을 입력받아 (P, M, R, S) 변경안을 만드는 제어 모듈이다. NM(jetson0)에서 llama.cpp로 Qwen3-4B Q4_K_M을 실행한다. 변경안은 비용 모델 기반 검증기가 검사한 뒤 적용한다.

**해결해야 하는 이유**
1. **결정을 반복해야 한다.** 다음 이벤트마다 다시 정해야 한다.
   - 적응 라운드
   - 장애
   - 부하 변화
   - 정책 변경
   - 컨텍스트 압축
2. **이력이 없다.** 원 IFLustre의 로그 기반 결정은 새 어댑터·epoch에 쓸 수 없다.
3. **운영 정책이 자연어이고 IoT 의미와 직결된다.** 예를 들면 다음과 같은 정책이다.
   - "라인 3 우선"
   - "교대 시작 10분 전 해당 라인 미리 준비"
   - "점검 중인 장비의 스트림은 수집 시점 prefill 중단"

   이 정책들은 스트림·시간 의미 정보와 바로 연결되어 상주 집합, 미리 읽기, prefill 배치 간격, 재생성 순서로 바뀌어야 한다.
4. **변경 범위를 골라야 한다.** 1GbE에서 LG 하나를 원격으로 옮기는 데 약 5초가 걸린다.
5. **탐색 공간 밖의 조치가 있다.** 시간대 기반 미리 읽기, 적응 시간대 조정, 정비 일정에 맞춘 사전 재분할이 그 예이다.

**범위 한정**
- 분할 후보는 55개라서 탐색으로 풀 수 있다. 플래너는 수치 최적화를 대체하지 않는다.
- 플래너의 역할은 세 가지이다.
  1. 정책을 목적·제약으로 변환
  2. 이벤트별 변경 범위 결정
  3. 탐색 공간 밖의 조치 제안
- 수치 타당성은 검증기가 보장한다.
- 장애는 미리 계산한 대체 분할을 규칙으로 즉시 적용한다.
- 평가에서 Search-only, 규칙 기반, LLM-only와 직접 비교한다(S6).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 7a | 상태 표현 |
| 7b | 출력 형식 |
| 7c | 정확성 |
| 7d | 비용 (NM 메모리 약 4.1GB, P0 실측) |
| 7e | 가용성과 MDS 영향 (플래너와 MDS가 같은 노드) |

**해결 방법**
1. **입력 (7a)**
   - JSON 상태 요약(1–2k 토큰)
   - 운영 정책 텍스트
   - 스트림 목록과 의미 속성(라인, 우선순위, 교대 일정)
   - 모델 config 요약
   - 관찰 규칙 요약
   - 정적 부분은 llama.cpp prompt cache로 재사용한다.
2. **출력 (7b).** JSON 스키마로 제한한 조치 목록이다.

   | 조치 | 내용 |
   |---|---|
   | `repartition` | 새 분할 |
   | `set_layout` | 레이아웃 |
   | `migrate` | 파일 이동 |
   | `mirror` | 복제 |
   | `set_tbf` | TBF 규칙 |
   | `set_cache_limit` | 캐시 상한 |
   | `set_residency` | stage별 상주 컨텍스트 |
   | `prefetch_context` | 컨텍스트 미리 읽기 |
   | `set_ingest_batch` | 스트림별 수집 시점 prefill 배치 간격 |
   | `pause_ingest_prefill` | 수집 시점 prefill 중단 |
   | `schedule_compaction` | 압축 시점 |
   | `schedule_regeneration` | 재생성 순서·시점 |
   | `schedule_replication` | 복제 시점·속도 |
   | `set_adapt_window` | 적응 시간대·비율 |
   | `pause_adapt` | 학습 정지 |
   | `set_objective` | 목적 가중치 |

3. **propose-verify 루프 (7c)**
   1. 플래너가 후보 1–3개를 만든다.
   2. 검증기가 제약을 검사하고, 비용 모델로 TTFT, 처리량, 최신성, 이동 바이트를 계산한다.
   3. 통과한 최선 후보를 적용한다.
   4. 모두 실패하면 사유를 넣어 재요청한다(최대 2회).
   5. 그래도 실패하면 규칙 기반 정책을 적용한다.
4. **호출 (7d)**
   - 이벤트 시에만 호출하며, 10초 안의 이벤트는 모아서 한 번 호출한다.
   - 요청 단위 결정은 계획 테이블을 조회한다.
   - 결정 지연은 10–20초로 추정한다.
5. **가용성과 MDS 영향 (7e)**
   - 플래너는 NM에서 실행하므로, stage 장애로 N0가 대체 stage를 맡아도 계속 동작한다.
   - 플래너 실행 중 MDS 메타데이터 처리 지연을 O4에서 측정한다. 영향이 크면 플래너 모델을 Qwen3-1.7B로 줄이거나 실행 시점을 제한한다.

**검증 방법**
- 비교 대상: Search-only, 규칙, LLM-only, LLM + 검증기
- 지표: SLO 달성률, 최신성, 이동 바이트, 결정 지연, 정책 준수율, 유효하지 않은 계획 비율
- 처음 보는 시나리오에서의 결과
- 플래너 모델 크기(0.6B/1.7B/4B) 비교

**관련 연구와의 차이**

ION, STELLAR 등은 오프라인 단일 대상 튜닝이다. 본 플래너는 온라인, 검증기 결합, 8GB 장치 실행이며, IoT 의미 정책을 저장 결정으로 바꾼다.

**원 IFLustre와의 관계**

Application Analyzer를 비용 모델(수치 예측)과 플래너·검증기(결정)로 나눈다.

## 4. 이벤트별 동작

| ID | 이벤트 | 경로 | 수행 내용 |
|---|---|---|---|
| E0 | 시작 | Slow | 초기 P, LG 배치, 이웃 stage mirror, 대체 분할, 캐시 상한, 공유 prefix KV 생성 |
| E1 | 요청 도착 | Fast | 체인 해시 계산 → stage별 상주 확인 → 미상주 pack 읽기 → 꼬리 + 질문 prefill → 세션 체인 생성 |
| E2 | 레코드 도착 | Background | 컨텍스트에 이어 붙임 → 봉인 가능 chunk가 생기면 대기열에 등록 |
| E3 | prefill 배치 시점 | Background | 컨텍스트 KV 로드(미상주 시) → 새 chunk 계산 → stage별 pack append, 경계 activation 저장 |
| E4 | 컨텍스트 한계 | Background | 규칙 압축 → 새 epoch 컨텍스트 → 공유 prefix 재사용, 나머지 KV 생성 → 이전 epoch 수거 예약 |
| E5 | 적응 시간대 시작 | Slow | 학습 비율, 복제 위치·속도 결정 |
| E6 | 체크포인트 | Background | 스냅샷 → 로컬 쓰기 → 지연 복제 |
| E7 | 라운드 종료 | Slow (경량) | 어댑터 확정·mirror → 컨텍스트별 LG9–11 KV 재생성 일정 → 재생성 완료 컨텍스트부터 새 버전 서빙 |
| E8 | 노드 장애 | Rule → Slow | P'_k 적용(N0가 대체, 이웃 stage mirror에서 원격 로드), 장애 노드 LG의 미복제 pack은 재계산. 플래너(NM)는 계속 동작 |
| E9 | 부하 변화·SLO 위반 | Slow | 상주 집합·배치 간격·캐시 상한·TBF 조정, 필요 시 부분 재분할 |
| E10 | 정책 변경 | Slow | 목적·제약 갱신 후 재계획 |
| E11 | 노드 복귀 | Slow | N0 stage 반납, 복귀 노드 OST의 `mirror resync` |

## 5. 실행 예시

```
t0      E0   P = {N1: LG0–3+embed, N2: LG4–7, N3: LG8–11+head}
             가중치 mirror: N1 → N2, N2 → N3, N3 → N1 (저부하 시점, TBF)
             라인 1–4의 [지시문][매뉴얼] KV 생성 → 공유 pack (이웃 stage mirror)
t0~     E2   데이터 스트림 8개의 레코드가 10초마다 컨텍스트에 이어 붙음 (N0)
        E3   5분마다 스트림별 새 chunk를 수집 시점 prefill → stage별 로컬 pack append, N3에 경계 activation 저장
        E1   요청: 상주 stage는 메모리, 미상주 stage는 로컬 pack 읽기 → 꼬리 + 질문만 prefill
t1      E9   교대 시작 10분 전: 정책에 따라 라인 2 컨텍스트를 전 stage에 함께 상주시키도록 조정
t2      E4   스트림 L1-A 컨텍스트 8k 도달 → 규칙 압축 → epoch 1 생성 (공유 prefix 재사용)
t3      E5–E6  야간 적응 시간대: N3에서 LG9–11 LoRA 학습, 25 step마다 체크포인트 → N1 또는 N2로 지연 복제
t4      E7   어댑터 v8 확정 → 세 stage OST에 mirror → 스트림별 LG9–11 KV를 N3의 경계 activation에서 재생성
             (요청이 많은 스트림부터) → 재생성이 끝난 스트림부터 v8로 서빙, 나머지는 v7
t5      E8   N3 장애 (N3의 OST0002도 사용 불가) → N0가 LG8–11 담당
             N1의 mirror에서 LG8–11 가중치, N1의 임베딩으로 head 로드, mirror된 봉인 pack 사용
             → 미복제 pack의 chunk는 재계산, 학습은 마지막으로 복제된 체크포인트에서 재개 대기
             플래너(NM)는 계속 동작
t6      E11  N3 복귀 → OST0002 mirror resync → 저부하 구간에 N0가 LG8–11 반납
```

## 6. 구현 상세

### 6.0 모듈 위치

| 모듈 | 위치 | 역할 |
|---|---|---|
| Context Builder | N0 | 레코드 토큰화, 컨텍스트 체인 유지, chunk 봉인 판정 |
| Prefill Scheduler | N0 | 스트림별 배치 간격에 따라 수집 시점 prefill 작업 생성 (낮은 우선순위) |
| Compactor | N0 | 한계 도달 시 규칙 기반 압축, 새 epoch 생성 |
| KV Store | N1–N3 | 주소 계산(chain, key), pack append·봉인, 조회(경로 계산 + 헤더 검증, 공유 prefix는 전역 인덱스), 상주 집합 관리, page cache 해제 |
| Activation Store | N3 (로컬 쓰기·읽기) | 경계 activation 객체. LG8 출력을 쓰고, 재생성 시 LG9 입력으로 읽는다 |
| Planner | NM | 이벤트 시 변경안 생성 (3.5절) |
| Telemetry Aggregator, Cost Model, Verifier, Executor | N0 | 상태 수집, 비용 계산, 변경안 검증, lfs/lctl 실행 |
| Weight Loader, Adapter Manager, Checkpoint Manager, place() | N1–N3 (Checkpoint Manager는 N3) | 가중치·어댑터 로드, 체크포인트, 배치 결정 |

### 6.1 소프트웨어 구성

| 구성 | 선택 | 이유 |
|---|---|---|
| 서빙·학습 런타임 | PyTorch + HF transformers + PEFT 자체 파이프라인 | LG 단위 로드, KV 직렬화, 경계 activation 추출, 부분 재생성, 상위 LG LoRA 학습 제어 |
| stage 간 통신 | TCP (ZeroMQ 또는 gRPC) | activation 토큰당 5KiB |
| KV Store | Python 라이브러리 (각 stage 프로세스에 포함) | pack append·봉인, 주소 계산(BLAKE3 또는 SHA-256), 헤더 검증, 상주 관리 |
| 전역 인덱스 | 공유 prefix용 작은 KV DB (SQLite 또는 LMDB) 파일, 한 stage OST + 다른 두 stage에 mirror | 조회 빈도 낮음, 파일이 작음 |
| 체크포인트 | 스냅샷 → 로컬 쓰기 → `lfs mirror extend` | 3단계 분리 |
| 플래너 | llama.cpp server (Qwen3-4B Q4_K_M) + JSON schema + prompt cache, NM에서 실행 | NM 메모리 예산 (실측 약 4.1GB) |
| 비교 대상 B7 | llama.cpp server 노드별 복제 | 단일 노드 양자화 |
| 비용 모델·검증기·Executor | Python, N0에서 실행 | 분할 전수 탐색(55개) |
| Telemetry | tegrastats, `lctl get_param`, `/proc`, PSI | 1초 주기 |

### 6.2 디렉터리 구조 (예정)

```
lflustre_iot/
├── README.md
├── legacy/                # 기존 IFLustre IoT 스크립트 (정리 시 이동)
├── harness/
│   ├── place.py           # 배치 인터페이스
│   ├── ingest/            # W1 수집, 레코드 변환
│   ├── context/           # Context Builder, Prefill Scheduler, Compactor
│   ├── kvstore/           # 주소, pack, 인덱스, 상주, 수거
│   ├── runtime/           # stage runtime, weight/adapter loader, activation store, checkpoint manager
│   ├── samples/           # W2 학습 샘플
│   ├── workload/          # 요청 생성기, 트레이스 재생
│   └── telemetry/
├── control/               # cost model, planner client, verifier, executor
├── tools/                 # LG 분할 변환기, 크기·메모리 계산기
├── baselines/             # B7, B8 등
├── experiments/
│   ├── p0_env/
│   ├── o1_path/ ... o7_kvreuse/
│   └── eval/
└── docs/
```

### 6.3 주요 인터페이스

```python
def place(obj: str, lg: int | None, producer: str, consumer: list[str],
          size: int, attrs: dict) -> Layout:
    """obj: 'weight'|'embed'|'kvpack'|'act'|'session'|'ckpt'|'adapter'|'iot'
       attrs: 의미 속성 (line, stream, epoch, anomaly, priority 등)
       반환: 기본 OST, stripe, mirror OST 목록, 복제 정책"""

class KVStore:
    def key(self, lg: int, chain: bytes) -> bytes: ...                 # 내용 주소
    def append(self, ctx: str, lg: int, chunk_kv, chain: bytes): ...   # 열린 pack에 append
    def seal(self, ctx: str, lg: int): ...                             # pack 봉인 → 복제 대기열
    def get(self, ctx: str, lg: int, chain_upto: bytes) -> KVView: ...  # 경로 계산 + 검증 + 읽기
    def resident(self, ctx: str) -> bool: ...
    def gc(self, live_epochs, live_versions, live_sessions): ...
```

비교 대상(baseline)은 `place()`, KV Store의 정책 부분, 스케줄러 구현만 다르고 나머지 코드는 같다.

## 7. 플래너 입출력 예시

### 7.1 입력 (요약)

```json
{
  "event": {"type": "policy_change", "text": "07:50부터 라인 2 교대 시작. 라인 2 요청 우선. 스트림 L4-B는 장비 점검 중"},
  "slo": {"ttft_p99_s": 2.0, "tpot_p99_ms": 200, "lag_max_min": 10},
  "contexts": [
    {"id": "L2-A", "line": 2, "tokens": 6900, "resident": ["N2"], "unprefilled_records": 31},
    {"id": "L2-B", "line": 2, "tokens": 5200, "resident": [], "unprefilled_records": 12},
    {"id": "L4-B", "line": 4, "tokens": 7700, "resident": ["N1","N2","N3"], "status": "maintenance"}
  ],
  "nodes": {
    "N3": {"kv_free_gb": 0.2, "psi_mem": 6.1, "training": false},
    "N1": {"kv_free_gb": 0.5}
  },
  "ingest_batch_min": {"default": 5},
  "rules": ["O7: 상주하지 않은 stage가 하나라도 있으면 TTFT는 그 stage의 KV 읽기 시간이 결정한다", "..."]
}
```

### 7.2 출력

```json
{
  "actions": [
    {"type": "pause_ingest_prefill", "context": "L4-B"},
    {"type": "set_residency", "evict": [{"context": "L4-B", "nodes": ["N1","N2","N3"]}],
     "admit": [{"context": "L2-A", "nodes": ["N1","N3"]}, {"context": "L2-B", "nodes": ["N1","N2","N3"]}],
     "at": "07:40"},
    {"type": "set_ingest_batch", "context": ["L2-A","L2-B"], "minutes": 1, "until": "09:00"},
    {"type": "set_objective", "priority": {"line": 2, "weight": 2.0}, "until": "09:00"}
  ],
  "rationale": "점검 중인 L4-B의 사전 계산과 상주를 해제해 메모리를 확보한다. 교대 10분 전에 라인 2 컨텍스트를 모든 stage에 함께 상주시켜 TTFT를 상주 적중 수준으로 맞춘다. 라인 2의 배치 간격을 1분으로 줄여 꼬리 prefill을 줄인다."
}
```

검증기는 이 출력에 대해 stage별 상주 메모리(특히 N3), 예상 TTFT p99, 최신성 지연을 계산한 뒤 적용 여부를 결정한다.

## 8. 주소와 저장 경로 규격

### 8.1 주소

```
H            = BLAKE3-256 (또는 SHA-256)
chain_0      = H("costripe/v1" ‖ model_id ‖ tokenizer_id ‖ chunk_size)
chain_n      = H(chain_{n-1} ‖ token_ids(chunk_n))
key(i, n)    = H(model_id ‖ adapter_scope_version(i) ‖ i ‖ chain_n)
act_key(n)   = H(model_id ‖ "act@LG" ‖ boundary_lg ‖ chain_n)     # 경계 activation (하위 LG에 어댑터가 없으므로 버전 없음)
```

### 8.2 경로

```
<MNT>/costripe/
├── weights/<model>/lg{i}.safetensors, embed.safetensors
├── adapters/<model>/v{n}/lg{i}.safetensors
├── kv/<model>/<scope>/shared/line{L}/lg{i}/{seq}.pack       # 공유 prefix pack
├── kv/<model>/<scope>/ctx/{ctx_id}/e{epoch}/lg{i}/{seq}.pack # 스트림 컨텍스트 pack
├── kv/<model>/sessions/{session_id}/lg{i}.pack               # 세션 (단기)
├── act/<model>/ctx/{ctx_id}/e{epoch}/lg{b}/{seq}.pack       # 경계 activation
├── index/shared.db                                           # 공유 prefix 전역 인덱스
├── ckpt/<model>/r{round}/s{step}/lg{i}.pt
├── iot/{dataset}/...  records/{ctx_id}/...
└── train/r{round}/*.jsonl
```

- `<scope>`: 해당 LG에 영향을 주는 어댑터 버전. 하위 LG는 `none`, 상위 LG는 `v{n}`이다.
- 디렉터리 단위로 default layout을 설정해 OST를 정한다. 예: `ctx/{ctx_id}/e{epoch}/lg{i}/` → LG i 소비 노드 OST.

### 8.3 pack 형식

| 부분 | 내용 |
|---|---|
| 헤더 | 형식 버전, model_id, scope, LG, ctx_id, epoch, 시작 chunk 순번, chunk 크기 |
| 엔트리 (chunk마다) | key, chain_n, 데이터 오프셋, 길이, 체크섬 |
| 데이터 | LG의 K, V 텐서 (layer 순, FP16) |
| 봉인 표시 | 엔트리 수 확정, 이후 수정하지 않음 |
