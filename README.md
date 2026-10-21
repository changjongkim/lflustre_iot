# lflustre_iot

하이퍼컨버지드 엣지 분산 파일 시스템에서 LLM 라이프사이클을 위한 저장-연산 간섭 인지 스토리지 할당 (IFLustre 확장)

> 상태: 연구 설계 단계.
> 이 문서는 문제 정의, 해결 대상, 통합 구성, 실험 및 평가 계획을 관리한다.
> 설계가 바뀌면 이 문서를 갱신하고 커밋한다.

---

## 목차

1. [배경](#1-배경)
2. [용어](#2-용어)
3. [문제 정의](#3-문제-정의)
4. [해결 대상](#4-해결-대상)
5. [통합 구성](#5-통합-구성)
6. [구현 계획](#6-구현-계획)
7. [관찰 실험](#7-관찰-실험-논문-section-iii)
8. [평가 계획](#8-평가-계획)
9. [논문 구성](#9-논문-구성)
10. [일정](#10-일정)
11. [리스크](#11-리스크)
12. [미결 사항](#12-미결-사항)
13. [참고 문헌](#13-참고-문헌)

---

## 1. 배경

### 1.1 원 연구 (IFLustre)

| 버전 | 내용 |
|---|---|
| MASCOTS 2022 | Lustre에서 과거 실행 로그로 stripe count와 stripe size를 결정한다. 예측한 처리량과 실행 시간으로 OSS 할당 정책 3종(interference-free, throughput-aware, runtime-aware)을 적용한다. Lustre 대비 최대 47% 개선. |
| IEEE IoTJ (Reject & Resubmit) | 클라우드 DFS 환경과 IoT 데이터셋 6종을 사용한다. read-aware relocation을 추가했다. 최대 47.8% 개선. |

### 1.2 방향을 바꾸는 이유

1. **소파일 문제.** IoT 스트리밍 워크로드(RIoTBench 등)는 파일 크기가 KB 단위이다. 원 논문 Fig.4에서 256KB 파일은 stripe count를 늘려도 성능이 오르지 않았다(최대 4% 감소). 이 워크로드에서는 striping과 OSS 할당 기법의 효과가 드러나지 않는다.
2. **테스트베드 변경.** 테스트베드를 Jetson Orin 5대로 옮겼다. 이 환경에서는 스토리지 서버와 연산 노드가 분리되지 않는다.
3. **워크로드 변화.** 엣지 IoT 애플리케이션이 LLM으로 센서·로그 데이터를 해석하는 형태로 바뀌고 있다. LLM 데이터(가중치, KV cache, 체크포인트)는 MB에서 GB 단위이므로 배치 결정이 성능에 직접 영향을 준다.
4. **새 간섭 경로.** 노드가 스토리지와 연산을 함께 수행하면, 저장 I/O가 같은 노드의 LLM 연산을 지연시키는 간섭이 생긴다. 원 IFLustre는 이 경로를 다루지 않았다.

---

## 2. 용어

| 용어 | 정의 |
|---|---|
| 하이퍼컨버지드 엣지 DFS | 모든 노드가 Lustre OSS, Lustre client, LLM 연산을 동시에 수행하는 엣지 클러스터 구성 |
| Stage | 파이프라인 추론에서 한 노드가 담당하는 연속 layer 구간 |
| LG (Layer Group) | 연속된 g개 layer의 묶음. 분할, 저장, 이동의 공통 단위. 예: 64-layer 모델에서 g=4이면 LG 16개 |
| P | LG를 추론 노드에 배정하는 파이프라인 분할 |
| M | 각 데이터 객체의 저장 위치(OST)와 레이아웃(stripe count, stripe size, mirror) |
| S | 백그라운드 I/O(체크포인트, 재배치, 수집)의 실행 시점과 속도 |
| 소비 노드 | 어떤 데이터 객체를 읽어서 사용하는 노드 |
| 여유 노드 | 연산 부하가 낮아서 추가 I/O를 받아도 파이프라인 처리량이 떨어지지 않는 노드 |
| TTFT | Time To First Token. 요청 도착부터 첫 토큰 출력까지의 시간 |
| TPOT | Time Per Output Token. 출력 토큰 하나당 생성 시간 |
| Freshness | 적응 학습이 끝난 시점부터 새 어댑터로 서빙을 시작하기까지의 시간 |

---

## 3. 문제 정의

### 3.1 대상 환경

- 노드는 N개이다(현재 N=5, Jetson Orin).
- 각 노드는 Orin SoC(CPU와 GPU가 LPDDR5 unified memory를 공유), NVMe SSD, NIC로 구성된다.
- Lustre 구성: N0에 MGS/MDS를 둔다. 모든 노드에 OSS/OST를 1개씩 두고, 모든 노드가 client로 마운트한다.
- 모든 노드는 OSS, Lustre client, LLM 연산(추론 stage 또는 학습)을 동시에 수행한다.

| 노드 | Lustre 역할 | 연산 역할 |
|---|---|---|
| N0 | MGS/MDS, OST0, client | 제어 모듈(플래너 등), W1 수집, W2 학습 |
| N1–N4 | OST1–OST4, client | W3 추론 파이프라인 stage 1–4 |

모델 선택 기준: 노드 1대의 메모리에 가중치와 KV가 함께 들어가지 않는 모델을 쓴다.

| Orin 메모리 | 모델 예시 | 비고 |
|---|---|---|
| 64GB (AGX) | Qwen2.5-32B FP16 (가중치 약 65GB) | 이 문서의 기본 예시 |
| 64GB (AGX) | Llama-3.1-70B INT4 (약 40GB) | 대안 |
| 16GB (NX) | Llama-3.1-8B FP16 (약 16GB) | NX 사용 시 |

### 3.2 대상 워크로드

시나리오는 공장 엣지 사이트의 설비 이상 분석 LLM 서비스이다.

| ID | 이름 | 내용 | 실행 위치 |
|---|---|---|---|
| W1 | Ingest | 센서·음향·네트워크 로그 데이터를 Lustre에 저장한다. 원 논문 데이터셋(Bot-IoT, MIMII, EPIC-Sounds, LoRaWAN 등)과 RIoTBench로 생성한다. | N0 |
| W2 | Adapt | W1 데이터로 만든 학습 샘플로 LoRA(QLoRA) 적응 학습을 주기적으로 수행한다. 학습 중 체크포인트를 저장하고, 종료 시 어댑터를 생성한다. | N0 |
| W3 | Serve | 운영자 질의를 처리한다. 입력은 시스템 프롬프트, 설비 매뉴얼(공통 prefix), 최근 센서·로그 구간, 질문으로 구성된다. N1–N4에서 파이프라인으로 추론하고, KV cache를 Lustre에 저장해 재사용한다. | N1–N4 |

데이터 흐름: W1 데이터 → W2 학습 → 어댑터 생성 → W3 서빙 → 질의·응답 로그가 다시 W1 데이터에 추가된다.

데이터 객체 (크기는 Qwen2.5-32B 기준 계산값):

| 객체 | 생성 | 소비 | 크기 | 접근 패턴 | 요구사항 |
|---|---|---|---|---|---|
| 가중치 | 사전 배치 | W3 stage | 전체 약 65GB, layer당 약 1GB | 시작·재분할·복구 시 순차 읽기 | 로드 시간 |
| KV cache | W3 stage | W3 stage | 토큰당 256KiB (layer당 4KiB) | 서빙 중 쓰기, 재사용 시 읽기 | TTFT |
| 체크포인트 | W2 | W2 (학습 복구 시) | 약 0.5GB (r=16 LoRA + optimizer state) 이상 | 주기적 버스트 쓰기 | 학습 진행, 서빙 영향 최소화 |
| 어댑터 | W2 | W3 stage | 약 67MB (r=16, q/k/v/o) | 배포 시 1회 읽기 | 배포 지연 |
| IoT 데이터 | W1 | W2 | 파일당 KB–MB | 연속 쓰기, 학습 시 읽기 | 처리량 |

### 3.3 문제 서술

하이퍼컨버지드 엣지 DFS에서 W1–W3가 동시에 실행될 때 다음 세 가지를 결정하는 문제이다.

- **P:** 모델 layer(LG)를 추론 노드에 나누는 방법
- **M:** 각 데이터 객체를 저장할 OST와 레이아웃
- **S:** 백그라운드 I/O의 실행 시점과 속도

목표는 서빙 SLO(TTFT p99)를 만족하면서 서빙 처리량을 최대화하고, 어댑터 freshness를 최소화하는 것이다.

### 3.4 정식화

**입력**
- 노드별: 연산 능력, 메모리 용량, OST 대역폭과 용량, NIC 대역폭
- 모델: layer 수, LG별 가중치 크기, 토큰당 KV 크기, LG별 연산 시간
- 워크로드: 요청 도착률, prefix 재사용 분포, 컨텍스트 길이 분포, 학습 주기, 체크포인트 크기, 수집률
- 운영 정책: SLO, 우선순위, 시간대별 제약

**결정 변수:** P, M, S

**목적과 제약**

```
maximize    Throughput = 1 / max_k T_k
subject to  TTFT_p99 <= SLO
            mem_k(P, M) <= MemCap_k            (노드 k)
            used_j(M)   <= OstCap_j            (OST j)
            ckpt_interval(S) <= CkptMax        (학습 정책)
            freshness(S, M)  <= FreshMax       (선택)
```

T_k의 정의는 [5.3절](#53-비용-모델)에 있다.

### 3.5 문제를 어렵게 만드는 요인

| ID | 요인 | 설명 |
|---|---|---|
| D1 | 저장-연산 결합 | OST가 연산 노드에 있다. 어떤 OST로 I/O를 보내면 그 노드의 연산이 느려진다. 따라서 배치를 정하는 것이 곧 연산 부하를 정하는 것이 된다. |
| D2 | 파이프라인 병목 | 처리량은 가장 느린 stage가 결정한다. 한 노드에 I/O가 몰리면, 다른 노드에 여유가 있어도 전체 성능이 떨어진다. |
| D3 | P와 M의 상호 의존 | P가 바뀌면 각 객체의 소비 노드가 바뀌어 최적 M이 달라진다. 반대로 M이 고정되어 있으면 P를 바꿀 때 이동해야 하는 데이터량이 달라진다. |
| D4 | I/O 클래스 간 요구 충돌 | KV는 지연에 민감하다. 체크포인트는 처리량 중심이고 버스트로 발생한다. 두 I/O가 같은 OST나 NIC를 쓰면 KV 읽기가 지연된다. |
| D5 | 시간에 따른 변화 | 적응 라운드마다 새 어댑터가 생기고, 장애·부하 변화·정책 변경이 발생한다. 새 객체에는 과거 실행 이력이 없다. |

### 3.6 기존 방식의 한계

| 방식 | 다루는 것 | 이 문제에서 부족한 점 |
|---|---|---|
| Default Lustre (stripe count 1, offset -1) | 파일 단위 OST 분산 | 소비 노드와 연산 부하를 고려하지 않는다. 각 stage의 데이터가 모든 OST에 흩어져서 모든 노드에 I/O가 발생한다. |
| 원 IFLustre | OSS 간 간섭, 처리량·실행 시간 예측 기반 할당 | 저장-연산 간섭, layer 구조, 라이프사이클을 고려하지 않는다. 같은 애플리케이션의 과거 로그가 있어야 한다. |
| 로컬 디스크만 사용 | 노드 내 저장 | 생성 노드와 소비 노드가 다른 객체(어댑터, KV, IoT 데이터)를 공유할 수 없다. 재분할이나 장애 시 데이터 복사가 필요하다. |
| 데이터센터 KV 저장 (Mooncake, LMCache, CachedAttention) | KV 재사용, 계층형 저장 | 저장 계층과 연산이 분리된 구조를 가정한다. 저장-연산 간섭과 학습 I/O의 공존을 다루지 않는다. |
| 엣지 분산 추론 (EdgeShard, Galaxy, prima.cpp) | 연산·네트워크 기준 모델 분할 | 저장 I/O, KV 저장, 학습을 고려하지 않는다. |
| 체크포인트 최적화 (CheckFreq, Gemini, DataStates-LLM) | 학습 체크포인트 비용 감소 | 데이터센터 학습이 대상이다. 같은 노드에서 서빙과 공존하는 상황을 다루지 않는다. |
| LLM 기반 스토리지 튜닝 (ION, STELLAR) | LLM으로 I/O 설정 추천 | HPC 단일 애플리케이션의 오프라인 튜닝이다. 온라인 재계획과 연산 간섭을 다루지 않는다. |

### 3.7 연구 질문

- **RQ1.** 하이퍼컨버지드 엣지 노드에서 저장 I/O는 같은 노드의 LLM 연산을 얼마나 지연시키는가? 주된 경로는 CPU, 메모리 대역폭, page cache 중 무엇인가?
- **RQ2.** 파이프라인 분할(P)과 데이터 배치(M)를 함께 결정하면, 각각 독립적으로 결정할 때보다 서빙 성능이 얼마나 개선되는가?
- **RQ3.** KV, 체크포인트, 수집 I/O의 배치·시점·속도를 어떻게 제어해야 서빙 SLO를 유지하면서 적응 학습과 어댑터 배포를 지연 없이 수행할 수 있는가?
- **RQ4.** 이벤트가 발생했을 때 LLM 플래너와 검증기로 재계획하면, 규칙 기반이나 탐색 기반 방식과 비교해 결과 품질, 정책 준수, 결정 비용이 어떻게 다른가?

---

## 4. 해결 대상

번호는 기존 논의 번호(②③⑤⑦⑧)를 유지한다. 서술 순서는 의존 관계 순서(⑧ → ② → ⑤ → ③ → ⑦)이다.

| 번호 | 해결 대상 | 대응 요인 | 대응 RQ |
|---|---|---|---|
| ⑧ | 분산 추론의 분할과 가중치 배치 | D1, D2, D3 | RQ2 |
| ② | KV cache 저장과 재사용 | D1, D4 | RQ2, RQ3 |
| ⑤ | 적응 학습 체크포인트와 어댑터 배포 | D4, D5 | RQ3 |
| ③ | 저장-연산 간섭 측정과 완화 | D1, D2 | RQ1 |
| ⑦ | 이벤트 기반 재계획 (LLM 플래너) | D3, D5 | RQ4 |

### 4.1 ⑧ 분산 추론의 분할과 가중치 배치

**정의**

모델 LG를 N1–N4에 연속 구간으로 배정해 파이프라인 추론을 수행한다. 각 stage는 자기 LG의 가중치를 Lustre에서 로드한다. Stage 간 activation은 네트워크로 전달한다.

**해결해야 하는 이유**

1. 모델 크기가 노드 메모리를 넘는다. Qwen2.5-32B FP16 가중치(약 65GB)는 AGX Orin 64GB에 들어가지 않는다. 양자화로 1대에 올리더라도 KV, 학습, OS, Lustre에 쓸 메모리가 남지 않는다.
2. 가중치 로드는 시작, 재분할, 장애 복구 때 발생한다. 로드하는 동안 서비스가 중단된다.
3. Default layout에서는 한 stage의 가중치가 모든 OST에 흩어진다. 그래서 로드할 때 모든 노드에 서버 측 I/O가 생기고, 대부분의 읽기가 네트워크를 거친다.
4. 노드 장애 시 그 노드의 연산과 OST가 함께 사라진다. 그 노드의 OST에만 있던 가중치는 읽을 수 없게 된다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 8a | 분할 P 선택: LG별 연산 시간과 stage별 I/O 부하를 함께 고려 |
| 8b | 가중치 배치: 각 LG 가중치 파일의 OST와 stripe count |
| 8c | 장애 대비: 어느 OST에 mirror를 둘지 |
| 8d | 재분할: 이동량을 최소화하고, 이동 중 서빙 영향을 최소화 |

**해결 방법**

- **파일 단위**
  - 가중치를 LG 단위 파일로 저장한다(`weights/lg{i}.safetensors`). 예: g=4이면 파일당 약 4GB.
  - 재분할 시 파일 단위로 이동할 수 있다.
  - 단일 파일에 PFL 컴포넌트로 layer 구간별 OST를 지정하는 방식은, 재분할 시 레이아웃 변경이 복잡하므로 대안으로만 둔다.
- **배치 규칙**
  - 기본값: LG 파일을 소비 노드의 OST에 둔다(`lfs setstripe -c 1 -i <소비 노드 OST>`).
  - 예외: 소비 노드가 병목 stage이면, 비용 모델(5.3절)로 여유 노드의 OST와 비교해 T_k 최댓값이 작은 쪽을 고른다.
- **stripe count**
  - 기본값은 1이다.
  - O1 측정에서 단일 OST 읽기 속도가 로드 시간 목표를 만족하지 못할 때만 2(소비 노드 OST + 여유 노드 OST)를 쓴다.
- **mirror**
  - FLR(`lfs mirror`)로 각 LG 가중치의 mirror를 1개 만든다.
  - mirror 위치는 해당 노드에 장애가 났을 때 그 LG를 넘겨받을 노드의 OST이다. 플래너가 장애별 대체 분할을 미리 계산해 정한다.
  - 가중치는 읽기 전용이므로 mirror 동기화 비용이 없다.
- **분할 P 선택**
  - 후보 분할마다 비용 모델로 max_k T_k를 계산해 최소인 분할을 고른다.
  - 연속 분할이므로 LG 16개, stage 4개 기준 후보는 C(15,3)=455개이다. 전수 탐색이 가능하다.
- **재분할**
  - 새 P에서 소비 노드가 바뀐 LG 파일만 `lfs migrate -i <새 OST>`로 옮긴다.
  - 서빙 중 migrate는 NRS TBF로 속도를 제한한다.

**검증 방법**

- 로드 시간: default, 소비 노드 배치, 제안 기법
- 재분할 시간과 이동 바이트
- 장애 복구 시간 (mirror 유무)
- 로드·이동 중 다른 stage의 처리량 변화

**원 IFLustre와의 관계**

- stripe count와 offset 지정(`lfs setstripe -i -c`)을 그대로 사용한다.
- 할당 기준을 OSS 처리량에서 소비 노드와 연산 부하로 확장한다.

### 4.2 ② KV cache 저장과 재사용

**정의**

각 stage가 생성한 KV(자기 LG 구간)를 Lustre에 저장한다. 같은 prefix를 가진 요청이 다시 오면 재계산하지 않고 저장된 KV를 읽어서 사용한다.

**해결해야 하는 이유**

1. **Orin에서 긴 컨텍스트 prefill은 비용이 크다.**
   - 32B 모델의 8k 토큰 prefill은 약 2 × 32.5e9 × 8192 ≈ 5.3e14 FLOP이다. 수 초에서 수십 초가 걸린다(추정, O4에서 측정).
   - 같은 구간의 KV(전체 2GiB, stage당 512MiB)를 읽는 시간은 저장 경로에 따라 1초 내외에서 수 초이다(추정, O1과 O4에서 측정).
2. **IoT 질의는 재사용률이 높다.** 같은 시스템 프롬프트와 설비 매뉴얼을 공통 prefix로 반복 포함하고, 연속 질의는 시간적으로 겹치는 센서 로그 구간을 포함한다.
3. **메모리에 둘 수 있는 KV는 제한적이다.**
   - 32B 모델에서 KV는 stage당 토큰당 64KiB이므로, 8k 세션 하나가 stage당 512MiB를 쓴다.
   - 교대 근무나 멀티턴 휴지로 시간이 지난 세션은 메모리에서 밀려난다. 재사용하려면 저장 계층이 필요하다.
4. **KV I/O는 서빙 중 계속 발생하는 지연 민감 I/O이다.** 간섭을 일으키는 원인(쓰기)이면서 간섭의 피해자(읽기 지연이 TTFT로 이어짐)이다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 2a | 저장 단위: chunk 크기, 파일 단위, 메타데이터 연산 수 |
| 2b | 배치: LG별 KV 파일의 OST |
| 2c | 읽기 시점: 요청 도착 후 동기 읽기 vs prefetch |
| 2d | 재계산 vs 읽기: chunk별로 어느 쪽이 빠른지 (OST 부하에 따라 달라짐) |
| 2e | 재분할 후 호환: stage 구간이 바뀌어도 기존 KV 사용 가능 여부 |
| 2f | 용량 관리: 삭제 정책, 공통 prefix 고정 |

**해결 방법**

- **저장 단위**
  - 파일 1개 = (prefix 그룹, LG). 경로: `kv/{prefix_hash}/lg{i}.kv`
  - 256토큰 chunk를 파일 안에 오프셋으로 append한다. Chunk별 오프셋 인덱스는 별도로 관리한다.
  - 크기: LG(4 layer) 기준 토큰당 16KiB, chunk당 4MiB, 8k 토큰 파일 128MiB.
  - chunk마다 파일을 만들지 않으므로 메타데이터 연산이 줄어든다. 원 논문 Obs.1의 소파일 메타데이터 비용을 피하기 위해서다.
- **prefix 식별:** chunk 단위 해시 체인(이전 chunk 해시 + 현재 chunk 토큰)으로 재사용 가능한 최장 prefix를 찾는다.
- **배치**
  - LG의 KV 파일은 같은 LG 가중치와 같은 규칙(4.1절)을 따른다.
  - LG별 디렉터리에 default layout을 설정해 새 파일이 상속하게 한다(`lfs setstripe -c 1 -i <OST> kv/.../lg{i}`).
  - P가 바뀌면 default layout을 갱신하고, 재사용 빈도가 높은 파일만 migrate한다.
- **읽기 시점**
  - 요청이 도착하면 prefix 일치 범위를 확인한다.
  - 각 stage의 KV Manager가 자기 LG 파일을 동시에 읽는다(stage 간 병렬).
  - 반복 질의 패턴(교대 시작 시각 등)이 정책에 있으면 공통 prefix를 미리 읽어 둔다.
- **재계산 vs 읽기**
  - chunk별로 예상 읽기 시간(F_k, 현재 OST 부하 반영)과 예상 재계산 시간(LG 연산 프로파일)을 비교해 작은 쪽을 선택한다.
- **재분할 호환:** KV를 LG 단위로 저장하므로, stage 구간이 바뀌어도 LG 파일을 새 소비 노드가 그대로 읽을 수 있다.
- **용량 관리**
  - 기본은 LRU이며, 재사용 빈도를 가중치로 준다.
  - 공통 prefix(시스템 프롬프트, 매뉴얼)는 고정(pin)하고 FLR mirror를 1개 둔다.

**검증 방법**

- TTFT 비교: 재사용 없음, 메모리 재사용만, Lustre default 배치, 제안 기법
- prefix hit rate, prefetch 효과, 재분할 직후 TTFT
- 재계산과 읽기 선택의 정확도

**원 IFLustre와의 관계**

- Read-aware relocation을 KV 파일에 적용한다(재사용 빈도와 소비 노드 기준 재배치).
- 원 논문 Obs.1(소파일 메타데이터 비용)을 파일 단위 설계에 반영한다.

### 4.3 ⑤ 적응 학습 체크포인트와 어댑터 배포

**정의**

N0에서 W1 데이터로 LoRA(QLoRA, 4-bit base) 적응 학습을 주기적으로 수행한다. 학습 중 체크포인트를 저장하고, 학습이 끝나면 어댑터를 LG 단위로 나눠 추론 stage에 배포한다. 서빙은 FP16 base에 LoRA를 적용한다.

**해결해야 하는 이유**

1. IoT 데이터 분포는 설비 상태, 라인 변경, 계절에 따라 바뀐다. 그대로 두면 모델 응답 품질이 떨어진다.
2. IoT 데이터는 사이트 밖으로 반출이 제한되는 경우가 많다. 그래서 적응을 엣지 안에서 해야 한다.
3. 체크포인트는 수백 MB에서 GB 단위의 버스트 쓰기이다. 서빙 KV I/O와 같은 OST와 NIC를 공유하므로 TTFT를 늘린다(D4).
4. 어댑터는 N0에서 생성되고 N1–N4에서 소비된다. 생성 위치에 그대로 두면 모든 stage가 원격으로 읽는다.
5. 배포가 늦어지면 적응 결과가 서빙에 늦게 반영된다(freshness 증가).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 5a | 체크포인트를 쓸 OST |
| 5b | 체크포인트 쓰기 시점과 속도: 학습 진행 보장 vs 서빙 영향 |
| 5c | 어댑터 배포: LG 분할, 저장 위치, 로드, 버전 전환 |
| 5d | 학습이 쓰는 N0 연산과 N0 OST를 I/O 수용 노드로 쓰는 것 사이의 충돌 |

**해결 방법**

- **체크포인트 2단계 저장**
  1. 학습 프로세스 메모리에 스냅샷을 복사한다(학습 정지 시간 최소화).
  2. Lustre로 비동기 flush한다.
- **flush 대상 OST:** 비용 모델에서 T_k 최댓값 증가가 가장 작은 노드의 OST를 고른다. 기본 후보는 OST0이다. 단, 5d를 반영해 N0의 학습 연산 시간 증가도 함께 계산한다.
- **flush 속도**
  - Lustre jobid로 체크포인트 I/O를 태깅한다.
  - NRS TBF 규칙으로 OST별 RPC 속도 상한을 둔다.
  - 상한은 비용 모델에서 TTFT p99가 SLO를 넘지 않는 최대 I/O 부하로 계산한다.
- **flush 시점**
  - 최근 요청률 이동평균과 정책상 시간대 정보로 저부하 구간을 예측해 그 구간에 flush를 몰아 둔다.
  - 체크포인트 간격 상한(CkptMax)은 제약으로 유지한다. 상한에 도달하면 속도 제한 안에서 즉시 flush한다.
- **어댑터 배포**
  1. 학습이 끝나면 어댑터 텐서를 LG 단위로 나눈다(`adapters/v{n}/lg{i}.safetensors`, r=16 기준 LG당 약 4MiB).
  2. 쓰는 시점에 바로 각 LG 소비 노드의 OST를 지정한다. 이렇게 하면 이후 migrate가 필요 없다.
  3. 모든 stage가 자기 LG 어댑터 로드를 완료한 뒤 버전을 동시에 전환한다(2단계 전환).
- **학습 위치:** 기본은 N0이다. N0 부하가 SLO를 위협하면, 플래너가 학습 일시정지나 flush 지연을 선택한다.

**검증 방법**

- 체크포인트 중 TTFT p99
- 체크포인트 소요 시간, 학습 처리량(step/s)
- freshness, 버전 전환 시 서빙 중단 시간

**원 IFLustre와의 관계**

- Runtime-aware allocation(대기 후 실행)을 체크포인트 flush의 시점 제어와 속도 제한으로 확장한다.
- Read-aware relocation 대신, 쓰는 시점에 소비 위치를 지정한다.

### 4.4 ③ 저장-연산 간섭 측정과 완화

**정의**

한 노드의 OSS(서버 측)와 client가 처리하는 I/O가, 같은 노드의 LLM 연산(추론 stage, 학습)을 지연시키는 현상이다.

**해결해야 하는 이유**

1. 엣지에는 스토리지 전용 노드가 없다. 모든 OST가 연산 노드에 있다.
2. Orin은 CPU와 GPU가 같은 LPDDR5 메모리를 쓴다. OSS의 데이터 복사, 네트워크 처리, page cache가 GPU 연산과 메모리 대역폭·용량을 나눠 쓴다(가설, O2에서 측정).
3. OSS 스레드와 네트워크 softirq가 CPU 코어를 사용한다. 이 작업은 LLM 런타임의 CPU 측 작업(스케줄링, activation 송수신)과 경쟁한다.
4. 파이프라인에서는 한 stage의 지연이 전체 처리량을 결정하므로 영향이 커진다(D2).
5. 4.1–4.3의 모든 배치 결정은 "어느 노드에 I/O를 보내면 연산이 얼마나 느려지는가"를 기준으로 한다. 이 값을 측정하지 않으면 배치 기준이 없다. 따라서 ③은 다른 요소의 공통 입력이다.
6. Lustre는 같은 노드에 client와 OSS를 두는 구성을 권장하지 않는다(메모리 압박 시 문제 가능성). 엣지에서는 이 구성을 피할 수 없으므로 동작과 영향을 직접 확인해야 한다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 3a | 크기: I/O 유형(읽기/쓰기, I/O 크기, 서버 측/클라이언트 측)별 지연 계수 α |
| 3b | 경로: CPU, 메모리 대역폭(EMC), page cache 중 주 원인 |
| 3c | 완화: 배치 외의 노드 내 격리 수단과 그 효과 |
| 3d | 안정성: client와 OSS 동시 운용 시 메모리 압박 상황의 동작 |

**해결 방법**

- **측정 방법**
  - Node k에서 stage를 실행하는 동안, 다른 노드에서 Node k의 OST로 fio 부하를 건다.
  - 부하 변수: 읽기/쓰기, 1MiB/4MiB, 속도를 단계별로 변경.
  - 측정 지표: tokens/s, stage latency, tegrastats(CPU, GPU, EMC 사용률, 전력), `/proc/meminfo`의 Cached, `/proc/softirqs`.
  - client 측 부하(Node k가 원격 OST를 읽는 경우)도 같은 방식으로 측정한다.
- **모델링**
  - 측정값으로 α_k(read), α_k(write)를 회귀로 구한다.
  - 원 IFLustre의 예측 모델(linear/polynomial regression, random forest)을 재사용한다.
- **노드 내 격리 수단**

  | 수단 | 방법 |
  |---|---|
  | CPU 분리 | Lustre CPT(`cpu_pattern`)로 OSS와 ptlrpc 스레드를 지정 코어에 고정한다. LLM 프로세스는 cgroup cpuset으로 나머지 코어에 둔다. |
  | page cache 제한 | client는 `llite.*.max_cached_mb`로 제한한다. OSS 측은 read/writethrough cache 설정(`osd-ldiskfs.*.read_cache_enable` 등, 버전별 파라미터명 확인)으로 제어한다. |
  | 속도 제한 | NRS TBF로 I/O 클래스별 RPC 속도 상한을 둔다. |
  | 전력 모드 | `nvpmodel` 모드별로 α를 측정한다. |

- **배치에 반영:** 비용 모델이 후보 OST마다 α·L 증가로 인한 stage 시간 증가를 계산한다. 4.1–4.3의 결정은 이 값을 사용한다.

**검증 방법**

- I/O 부하에 따른 tokens/s 그래프와 α 값
- 격리 수단별 효과
- 비용 모델 예측 오차

**원 IFLustre와의 관계**

- 원 Obs.2("애플리케이션 성능은 가장 느린 OSS가 결정한다")를 연산 측으로 확장한다("파이프라인 처리량은 가장 느린 stage가 결정하고, stage 속도는 같은 노드의 I/O 부하에 영향을 받는다").

### 4.5 ⑦ 이벤트 기반 재계획 (LLM 플래너)

**정의**

이벤트가 발생하면 현재 상태와 운영 정책을 입력받아 (P, M, S) 변경안을 생성하는 제어 모듈이다. N0에서 소형 LLM으로 실행한다. 생성된 변경안은 검증기가 비용 모델로 검사한 뒤 적용한다.

**해결해야 하는 이유**

1. (P, M, S)는 한 번 정하고 끝나지 않는다. 적응 라운드(새 어댑터), 노드 장애와 복귀, 부하 변화, SLO 위반, 운영 정책 변경이 생길 때마다 다시 정해야 한다(D5).
2. 원 IFLustre의 분석기는 같은 애플리케이션 이름의 과거 실행 로그로 설정을 정한다. 새 어댑터나 모델 버전에는 이력이 없다.
3. 운영 정책은 IoT 현장 운영자가 자연어로 표현한다. 예: "라인 3 질의 우선", "주간 근무 시간에는 체크포인트 최소화", "야간에 재학습". 이를 목적 함수 가중치와 제약으로 변환해야 한다.
4. 이벤트마다 어느 범위까지 바꿀지 선택해야 한다. P 전체를 재계산하면 이동 비용이 크다. M 일부나 S만 바꾸면 비용이 작지만 효과도 제한된다.

**범위 한정**

- 노드 5개 규모에서는 비용 모델 기반 탐색으로 (P, M)의 수치 최적해를 구할 수 있다(4.1절, 후보 455개).
- 따라서 플래너는 수치 최적화를 대체하지 않는다. 플래너의 역할은 다음 세 가지이다.
  1. 운영 정책을 목적·제약으로 변환
  2. 이벤트별 변경 범위 결정
  3. 탐색 공간에 없는 조치 제안 (시간대 기반 사전 prefetch, 학습 일시정지 등)
- 수치 타당성은 검증기가 보장한다.
- 평가에서 Search-only 방식과 직접 비교한다(8절).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 7a | 상태 표현: telemetry를 LLM 입력 길이 안에서 요약 |
| 7b | 출력 형식: 실행 가능한 조치로 제한 |
| 7c | 정확성: 잘못된 계획의 적용 방지 |
| 7d | 비용: 플래너 실행이 N0 연산과 메모리를 사용 |

**해결 방법**

- **입력**
  - JSON 상태 요약: 노드별 CPU/GPU/EMC/메모리, OST별 부하와 용량, stage latency, 현재 P, 객체 배치 현황, 이벤트 내용
  - 운영 정책 텍스트
  - 모델 config(layer 수, KV 헤드 수 등)
  - 관찰 규칙 요약(O1–O6)
- **출력**
  - JSON 스키마로 제한한 조치 목록이다. llama.cpp JSON schema 기반 제약 디코딩을 쓴다.
  - 조치 유형: `repartition`, `set_layout`, `migrate`, `mirror`, `set_tbf`, `schedule_ckpt`, `pause_train`, `prefetch_prefix`, `pin_prefix`
- **propose-verify 루프**
  1. 플래너가 후보 계획 1–3개를 생성한다.
  2. 검증기가 제약(메모리, 용량, 연속 분할)을 검사하고, 비용 모델로 예상 TTFT p99, 처리량, 이동 바이트를 계산한다.
  3. 통과한 후보 중 최선을 적용한다.
  4. 모두 실패하면 실패 사유를 포함해 재요청한다(최대 2회).
  5. 그래도 실패하면 규칙 기반 정책(원 IFLustre 정책 확장판)을 적용한다.
- **호출 빈도:** 이벤트가 발생할 때만 호출한다. 요청 단위 결정은 플래너가 만든 계획 테이블을 조회하는 fast path로 처리한다.
- **플래너 모델:** Qwen2.5-7B-Instruct Q4(약 4–5GB)를 N0에서 실행한다. 플래너 실행 비용은 비용 모델의 C_0에 포함한다.

**검증 방법**

- 비교 대상: Search-only, 규칙 기반, LLM-only(검증기 없음), LLM + 검증기
- 지표: SLO 달성률, 이동 바이트, 결정 지연, 정책 준수율
- 처음 보는 시나리오(새 모델 크기, 새 정책 문장, 새 장애 패턴)에서 결과 비교

**원 IFLustre와의 관계**

- 원 Application Analyzer(로그 기반 설정 결정)를 비용 모델과 플래너로 나눈다. 수치 예측은 비용 모델이 맡고, 결정은 플래너가 맡는다.

---

## 5. 통합 구성

### 5.1 다섯 요소의 의존 관계

```
               ③ 저장-연산 간섭 측정
                       │  α (비용 모델의 공통 입력)
                       ▼
 ┌──────────────────── 비용 모델 T_k ────────────────────┐
 │                                                        │
 │  ⑧ 분할 P ──────────▶ 모든 LG 객체의 소비 노드 결정     │
 │      │                    │               │            │
 │      ▼                    ▼               ▼            │
 │  가중치 배치           ② KV 배치        ⑤ 어댑터 배치    │
 │  (로드 I/O)            (서빙 중 I/O)     체크포인트 시점·속도 │
 │                                          (버스트 I/O)  │
 └──────────────────────────┬─────────────────────────────┘
                            │ L_k (노드별 I/O 부하), 이벤트
                            ▼
                ⑦ 이벤트 발생 시 (P, M, S) 재결정
```

| 요소 | 다른 요소에 제공하는 것 | 다른 요소에서 받는 것 |
|---|---|---|
| ③ | α (모든 배치 결정의 기준) | 측정 대상 I/O 패턴(②, ⑤, ⑧) |
| ⑧ | P (모든 LG 객체의 소비 노드), 가중치 로드 부하 | α(③), 재분할 지시(⑦) |
| ② | 서빙 중 지속 I/O 부하, TTFT | P(⑧), α(③), 배치 규칙(⑦) |
| ⑤ | 버스트 I/O 부하, 새 어댑터 이벤트 | P(⑧), α(③), 시점·속도(⑦) |
| ⑦ | (P, M, S) 갱신 | α(③), 현재 P(⑧), 부하(②, ⑤), 운영 정책 |

### 5.2 공통 단위: LG

가중치, KV cache, LoRA 어댑터는 모두 layer 단위로 나뉜다. 그래서 LG를 분할, 저장, 이동의 공통 단위로 쓴다. P가 정해지면 모든 LG 객체의 소비 노드가 한 번에 정해진다.

| 객체 | 파일 경로 | 크기 (Qwen2.5-32B, g=4) |
|---|---|---|
| 가중치 | `weights/lg{i}.safetensors` | 약 4GB |
| KV cache | `kv/{prefix_hash}/lg{i}.kv` | 토큰당 16KiB, 8k 토큰 128MiB |
| 어댑터 | `adapters/v{n}/lg{i}.safetensors` | 약 4MiB (r=16) |
| 체크포인트 | `ckpt/step{s}/` | 약 0.5GB 이상 |
| IoT 데이터 | `iot/{dataset}/` | 파일당 KB–MB |

```
P = {N1: LG0–3, N2: LG4–7, N3: LG8–11, N4: LG12–15} 인 경우

N1 소비: weights/lg0–3, kv/*/lg0–3, adapters/v*/lg0–3  → 기본 배치 OST1
N2 소비: weights/lg4–7, kv/*/lg4–7, adapters/v*/lg4–7  → 기본 배치 OST2
...
병목 stage가 있으면 해당 LG의 KV 쓰기나 체크포인트를 여유 노드 OST로 이동
```

### 5.3 비용 모델

```
T_k = C_k(P) · (1 + α_k · L_k(M, S)) + F_k(M)

Throughput  = 1 / max_k T_k
TTFT        = (prefill 연산 또는 KV 로드) + 파이프라인 전달 지연
```

| 기호 | 의미 | 측정 또는 계산 방법 | 관련 요소 |
|---|---|---|---|
| C_k(P) | stage k의 순수 연산 시간 | LG별 연산 시간을 오프라인에서 1회 프로파일링한 뒤 합산 | ⑧ |
| L_k(M, S) | 노드 k의 OST와 client가 처리하는 I/O 부하 | 배치 M과 객체별 접근률(KV 재사용률, 체크포인트 크기·주기, 수집률)로 계산하고, 실행 중 jobstats로 보정 | ②, ⑤, W1 |
| α_k | I/O 부하에 따른 연산 지연 계수 | O2 측정 후 회귀 | ③ |
| F_k(M) | 연산과 겹치지 않는 KV fetch 대기 시간 | KV 크기, 경로 대역폭(로컬/원격, O1), OST 부하 | ② |

- 원 IFLustre는 이 모델에서 C_k=0, α=0이고 OSS 간 부하 L_k만 다루는 경우에 해당한다.
- α가 작게 측정되더라도 모델은 그대로 쓴다. 이 경우 F_k와 네트워크 항의 비중이 커진다.

**로컬 배치와 원격 배치의 선택 기준**

| 배치 | 네트워크 | 부하가 증가하는 노드 |
|---|---|---|
| stage k의 데이터를 OST k에 둠 | 사용하지 않음 | Node k (α_k · L_k 증가) |
| stage k의 데이터를 OST j에 둠 | F_k 증가 | Node j (α_j · L_j 증가) |

- 비용 모델은 두 경우의 max_k T_k를 비교해 작은 쪽을 고른다.
- 노드별 연산 여유는 요청 부하와 학습 상태에 따라 계속 바뀌므로, 이 선택도 시점마다 달라진다.

### 5.4 시스템 아키텍처

```
┌──────────────────────── N0: Control plane ────────────────────────┐
│                                                                    │
│  Telemetry Aggregator ─▶ Cost Model ─▶ LLM Planner ⇄ Verifier      │
│          ▲                                 ▲            │          │
│          │                         운영 정책(텍스트)      ▼          │
│          │                                          Executor       │
└──────────┼───────────────────────────────────────────────┼────────┘
           │ telemetry                                     │ 계획 테이블, lfs/lctl 명령
┌──────────┴────────────── 각 노드: Data plane ─────────────▼────────┐
│  Telemetry Agent   Stage Runtime   KV Manager                       │
│  Weight Loader     Adapter Loader  Trainer (N0)   Ingest Writer (N0) │
│  place() 라이브러리 (모든 I/O 공통 경로)                              │
│  Lustre client     OSS/OST                                          │
└─────────────────────────────────────────────────────────────────────┘
```

| 모듈 | 위치 | 입력 | 출력 |
|---|---|---|---|
| Telemetry Agent | 전 노드 | tegrastats, `/proc`, `lctl get_param` | 노드 상태 (1초 주기) |
| Telemetry Aggregator | N0 | 노드 상태 | 상태 요약 JSON |
| Cost Model | N0 | 상태, LG 프로파일, α | 후보 계획별 T_k, TTFT, 이동 바이트 |
| LLM Planner | N0 | 상태 요약, 운영 정책, 이벤트 | 후보 계획 (JSON 조치 목록) |
| Verifier | N0 | 후보 계획 | 선택된 계획 또는 재요청 |
| Executor | N0 | 선택된 계획 | `lfs setstripe/migrate/mirror`, `lctl set_param`(TBF), 계획 테이블 배포 |
| place() | 전 노드 | 객체 종류, LG, 생성 노드, 소비 노드, 크기 | 레이아웃 (계획 테이블 조회) |
| Stage Runtime | N1–N4 | LG 가중치, 어댑터, KV | 추론 결과, activation |
| KV Manager | N1–N4 | prefix 해시, 계획 테이블 | KV 읽기/쓰기, 재계산 vs 읽기 선택 |
| Trainer | N0 | IoT 데이터 | 체크포인트, 어댑터 |
| Ingest Writer | N0 | IoT 데이터셋 | IoT 파일 쓰기 |

**처리 경로**

| 경로 | 용도 | 수행 주체 |
|---|---|---|
| Slow path | 이벤트 발생 시 재계획 | Planner, Verifier, Executor |
| Fast path | 요청 단위 배치 | place()가 계획 테이블을 조회하여 즉시 결정 |

### 5.5 이벤트별 동작

| ID | 이벤트 | 트리거 | 처리 경로 | 수행 내용 | Lustre 조치 |
|---|---|---|---|---|---|
| E0 | 시작 | 클러스터 기동 | Slow | 초기 P 결정, LG 가중치 배치, 장애별 대체 분할 계산, mirror 위치 결정, 가중치 로드 | `setstripe -i`, `mirror` |
| E1 | 요청 도착 | 질의 | Fast | prefix 확인, KV 읽기와 재계산 중 선택, 새 KV chunk를 계획 테이블 위치에 append | 디렉터리 default layout |
| E2 | 학습 시작 | 스케줄 또는 데이터 누적량 | Slow | 체크포인트 OST, TBF 상한, flush 시간대 결정 | TBF 규칙 설정 |
| E3 | 체크포인트 | 학습 step | Fast | 메모리 스냅샷 후 비동기 flush (TBF 적용) | TBF |
| E4 | 학습 종료 | 어댑터 생성 | Slow (경량) | LG 분할, 소비 노드 OST에 쓰기, stage별 로드, 동시 전환 | `setstripe -i` |
| E5 | 노드 장애 | heartbeat 실패 | Slow | 미리 계산한 대체 분할 P' 적용, 가중치는 mirror에서 읽기, KV는 재계산 또는 mirror 읽기 | mirror 읽기, `migrate` |
| E6 | 부하 변화, SLO 위반 | telemetry 임계값 | Slow | 병목 stage 노드의 I/O를 여유 노드로 이동, TBF 조정, 필요 시 부분 재분할 | `migrate`, TBF |
| E7 | 정책 변경 | 운영자 입력 | Slow | 목적 가중치와 제약을 갱신한 뒤 재계획 | 계획에 따름 |

### 5.6 실행 예시

```
t0      E0  P = {N1: LG0–3, N2: LG4–7, N3: LG8–11, N4: LG12–15}
            weights/lg{i} → 소비 노드 OST, mirror → 대체 분할 기준 노드 OST
t0~     E1  매뉴얼 prefix KV 고정(pin) + mirror, 세션 KV는 소비 노드 OST에 append
t1      E2  학습 시작, 체크포인트 flush 대상 OST0, TBF 상한 = 비용 모델 계산값
t1~t2   E3  요청률이 높은 구간에는 flush 지연, 낮은 구간에 flush
t2      E4  어댑터 v(n+1) 생성 → adapters/v(n+1)/lg{i}를 소비 노드 OST에 쓰기
            → N1–N4 로드 완료 → 동시 전환
t3      E5  N3 장애 → 대체 분할 P' = {N1: LG0–5, N2: LG6–10, N4: LG11–15}
            → N3 담당 LG8–11의 가중치는 mirror(OST2, OST4)에서 읽기
            → 나머지 이동 LG는 기존 OST에서 읽은 뒤 새 소비 노드 OST로 migrate
            → LG8–11의 KV는 재계산 또는 mirror 읽기
t4      E6  N2 stage가 병목 → N2 OST로 가던 KV 쓰기를 OST0으로 변경, TBF 상한 조정
```

### 5.7 원 IFLustre와의 대응

| 원 IFLustre 구성 | 확장 내용 |
|---|---|
| Application Analyzer (로그 기반 stripe 결정, ML 예측) | Cost Model(LG 프로파일, α, 접근률) + LLM Planner(이벤트 기반 재계획) |
| Interference-free allocation | 연산 부하가 없는 노드의 OST를 선택 |
| Throughput-aware allocation | 비용 모델에서 max_k T_k 증가가 최소인 OST를 선택 |
| Runtime-aware allocation | 체크포인트·재배치 I/O의 시점 지연과 TBF 속도 제한 |
| Read-aware relocation | 재분할, 어댑터 배포, 병목 변화 시 LG 단위 migrate/mirror |
| 간섭 대상: OSS 간 | OSS 간 + 저장-연산 |

### 5.8 요소를 제거했을 때의 결과

| 제거 요소 | 결과 |
|---|---|
| ⑧ | LG를 노드에 나누는 분할이 없으므로, 소비 노드 기준 배치가 성립하지 않는다. 모델을 노드에 올릴 수 없다. |
| ② | 서빙 중 I/O가 거의 없다. 간섭이 가중치 로드 시점에만 발생한다. 긴 컨텍스트 prefill 비용을 줄일 수 없다. |
| ⑤ | 워크로드가 읽기 위주의 정적 패턴이 된다. 버스트 충돌, 생성·소비 위치 불일치, 새 객체 이벤트가 사라진다. |
| ③ | 배치 기준(α)이 없다. 항상 로컬 배치가 최적이 되어 최적화 문제가 사라진다. |
| ⑦ | 이벤트마다 수동으로 재설정해야 한다. 이력이 없는 새 어댑터에서는 로그 기반 결정을 할 수 없다. 자연어 운영 정책을 반영할 수 없다. |

---

## 6. 구현 계획

### 6.1 소프트웨어 스택

| 구성 | 선택 | 비고 |
|---|---|---|
| OS | JetPack 6.x (L4T) | 설치 버전 기록 필요 |
| DFS | Lustre (설치 버전 기록 필요) | PFL, FLR, NRS TBF, jobstats 지원 여부 확인 |
| 추론 런타임 | PyTorch + HF transformers 기반 자체 파이프라인 | LG 단위 로드, stage 간 TCP, I/O 경로 제어 용이. 대안: llama.cpp RPC |
| KV 저장 | HF DynamicCache 텐서를 LG 파일로 직렬화 | chunk 오프셋 인덱스 별도 관리 |
| 학습 | HF PEFT (QLoRA) | 체크포인트 jobid 태깅 |
| 플래너 | llama.cpp server + JSON schema | Qwen2.5-7B-Instruct Q4 |
| Telemetry | tegrastats 또는 jtop, `lctl get_param obdfilter.*.job_stats`, `osc.*.stats`, `/proc` | 1초 주기 |
| 트레이스 | Mooncake trace, BurstGPT 또는 Azure LLM trace, IoT 데이터셋 | |

### 6.2 디렉터리 구조 (예정)

```
lflustre_iot/
├── README.md
├── legacy/            # 기존 IFLustre IoT 벤치마크 스크립트 (현재 루트 파일, 정리 시 이동)
├── harness/
│   ├── place.py       # 배치 인터페이스 (모든 I/O 공통 경로)
│   ├── ingest/        # W1 (iotbenchlustre.py 기반)
│   ├── train/         # W2
│   ├── serve/         # W3: stage runtime, KV manager, weight/adapter loader
│   └── telemetry/
├── control/           # cost model, planner, verifier, executor
├── experiments/       # O1–O6 관찰 실험, 평가 스크립트
└── docs/
```

### 6.3 place() 인터페이스

모든 I/O는 아래 함수를 거친다. 비교 대상(baseline)은 이 함수와 스케줄러 구현만 다르고, 나머지 코드는 같다.

```python
def place(obj: str, lg: int | None, producer: str, consumer: str, size: int) -> Layout:
    """
    obj: 'weight' | 'kv' | 'adapter' | 'ckpt' | 'iot'
    반환: OST index 목록, stripe count, stripe size, mirror OST 목록
    """
```

### 6.4 기존 코드 재사용

| 파일 | 용도 |
|---|---|
| `iotbenchlustre.py` | W1 수집 부하 생성기 (데이터셋 선택, `lfs setstripe`, 지연·처리량 측정) |
| `fio*.sh`, `fiovarfilesize.sh` | O1 저장 경로 측정, O2 간섭 부하 생성 |
| `iotbenchhdfs*.py` | HDFS 비교용 (사용 여부 미정) |
| `listdataset.py`, `iot*.py` | 데이터셋 목록 및 기존 IoT 실험 |

---

## 7. 관찰 실험 (논문 Section III)

| ID | 목적 | 방법 | 지표 | 가설 | 반영 위치 |
|---|---|---|---|---|---|
| O1 | 저장 경로 특성 | raw NVMe, Lustre 로컬 OST(`-i` 자기 노드), 원격 OST, stripe count 2/4 비교. 파일 1GB/4GB, 읽기/쓰기, 단일/동시 client | MB/s, NIC 트래픽(`/proc/net/dev`), CPU | 원격 읽기는 NIC 대역폭으로 제한된다. 로컬 OST 읽기는 NIC를 쓰지 않는다(LNet loopback). | 4.1, 4.2 배치 규칙, F_k |
| O2 | 저장-연산 간섭 | stage 실행 중 해당 노드 OST에 fio 부하(읽기/쓰기, 1/4MiB, 속도 단계), client 측 부하도 측정 | tokens/s, stage latency, CPU/EMC/GPU 사용률, Cached, softirq | OSS 부하가 증가하면 같은 노드의 tokens/s가 감소한다. | α, 4.4 |
| O3 | 파이프라인 증폭 | 4-stage 파이프라인에서 stage 하나에만 I/O 부하를 준 경우와 같은 총 부하를 4노드에 분산한 경우 비교 | 전체 tokens/s, stage별 latency | 한 stage 집중 부하가 분산 부하보다 처리량을 더 떨어뜨린다. | 목적 함수 max_k T_k |
| O4 | 메모리와 prefill 비용 | 노드별 메모리 구성(가중치, KV, page cache, 학습) 측정, 컨텍스트 1k–16k에서 prefill 시간과 KV 로드 시간 비교 | GB, 초 | KV 로드가 prefill보다 짧다. 메모리에 둘 수 있는 세션 수가 제한된다. | 4.2 필요성, 재계산 vs 읽기 기준 |
| O5 | 라이프사이클 충돌 | 서빙 중 체크포인트 flush (속도·위치 변경) | TTFT 시계열, p99 | 체크포인트가 KV와 같은 OST·NIC를 쓰면 TTFT p99가 증가한다. | 4.3 시점·속도 제어 |
| O6 | 위치 불일치와 이벤트 | 어댑터를 생성 노드에 둘 때와 소비 노드에 둘 때의 로드 시간, 재분할 시 이동 바이트, 시나리오 기준 이벤트 발생 빈도 | 초, 바이트, 횟수 | 생성 위치에 두면 배포 지연이 길다. 이벤트가 주기적으로 발생한다. | 4.3 배포, 4.5 재계획 |

III장 끝에는 관찰-설계 대응표(관찰 ID, 시사점, 설계 절)를 둔다.

---

## 8. 평가 계획

### 8.1 비교 대상

| ID | 이름 | 설명 |
|---|---|---|
| B0 | Default Lustre | stripe count 1, offset -1 |
| B1 | Local-replica | 각 노드가 가중치 전체 사본을 로컬 디스크에 보관. KV는 로컬만 사용, 어댑터는 복사(rsync)로 배포 |
| B2 | 원 IFLustre | OSS 간 간섭만 고려한 할당 정책 |
| B3 | Search-only | 비용 모델 + 탐색으로 (P, M, S) 결정. 운영 정책은 사람이 수동으로 제약으로 변환 |
| B4 | 제안 기법 (규칙) | 5.7절 정책을 규칙 기반으로 적용 |
| B5 | 제안 기법 (LLM) | LLM 플래너 + 검증기 |
| B6 | Hand-tuned | 시나리오별 수동 최적 설정 |

### 8.2 실험 시나리오

| ID | 시나리오 | 확인 내용 |
|---|---|---|
| S1 (메인) | 2시간 end-to-end 라이프사이클. 적응 3회, 노드 장애 1회, 정책 변경 1회 | 시간축에 따른 SLO 달성률, TTFT p99, freshness |
| S2 | 정상 상태 서빙 + W1 수집 부하 | TTFT, TPOT, 처리량 |
| S3 | 서빙 + 체크포인트 | TTFT p99, 체크포인트 시간, 학습 처리량 |
| S4 | 어댑터 배포 | freshness, 전환 중 서빙 중단 시간 |
| S5 | 장애와 재분할 | 복구 시간, 이동 바이트 |
| S6 | 플래너 비교 | B3, B4, B5 및 LLM-only를 처음 보는 시나리오에서 비교, 결정 지연 |

### 8.3 지표

- 서빙: TTFT p50/p99, TPOT, tokens/s, SLO 달성률
- 라이프사이클: 가중치 로드 시간, 재분할 복구 시간, 체크포인트 시간, 학습 step/s, freshness
- 비용: J/token(tegrastats 전력), 이동 바이트, 플래너 결정 지연, 플래너 메모리 사용량

### 8.4 Ablation과 민감도

- Ablation: 저장-연산 간섭 반영(α) 제거, 소비 노드 배치 제거, TBF 제거, 재배치 제거, 플래너 제거(규칙으로 대체)
- 민감도: 노드 수(2–5), 네트워크 대역폭(`tc`로 제한), 모델 크기, 요청률, 체크포인트 주기, `nvpmodel` 전력 모드
- 확장성: 비용 모델 기반 시뮬레이션(8–32노드)

---

## 9. 논문 구성

| 섹션 | 내용 | README 대응 |
|---|---|---|
| I. Introduction | IoT 엣지 LLM의 필요성, 라이프사이클, 문제 요인 D1–D5, 기존 연구 한계, 기여 | 1, 3 |
| II. Background & Motivation | 엣지 LLM 라이프사이클, Lustre 레이아웃 기능(striping, PFL, FLR, NRS TBF), 파이프라인 추론·KV·LoRA, 기존 연구 비교표 | 3.2, 3.6 |
| III. Empirical Analysis | O1–O6, 관찰-설계 대응표 | 7 |
| IV. Design | 아키텍처, 비용 모델, LG 기반 배치(⑧②), 라이프사이클 스케줄링(⑤), 간섭 완화(③), 플래너와 검증기(⑦), 구현 | 4, 5, 6 |
| V. Evaluation | 8절의 실험 | 8 |
| VI. Discussion | 규모 한계, 다른 DFS(Ceph, BeeGFS)로의 일반화, 전력 | 11 |
| VII. Related Work | 로그 기반 I/O 분석, 자원 상태 기반 할당, 성능 예측, LLM 서빙·학습 저장 시스템, 엣지 분산 추론 | 3.6, 13 |
| VIII. Conclusion | | |

**기여**

1. 하이퍼컨버지드 엣지 DFS에서 LLM 라이프사이클 I/O 특성과 저장-연산 간섭 분석 (O1–O6)
2. 비용 모델과 LG 기반 분할·배치 공동 결정 기법
3. 원 IFLustre 정책을 라이프사이클 전체로 확장한 시스템, 그리고 LLM 플래너와 검증기
4. Jetson Orin 5대 실제 장비 평가

---

## 10. 일정

| 단계 | 기간 | 작업 | 논문 위치 |
|---|---|---|---|
| P0 | 1주 | 장비 사양 확정, 모델 선택, LNet loopback 경로 확인, client+OSS 동시 운용 안정성 확인 | III 설정 |
| P1 | 3주 | Lifecycle harness 구현 (W1, W2, W3, telemetry, place()) | IV 구현 |
| P2 | 2주 | O1–O6 측정 | III |
| P3 | 1주 | 비용 모델 피팅, 예측 오차 검증 | IV 비용 모델 |
| P4 | 2주 | LG 기반 배치, 정책, Executor | IV |
| P5 | 1주 | 플래너, 검증기, Search-only | IV |
| P6 | 2주 | 평가 | V |
| P7 | 1–2주 | 집필, response letter | 전체 |

---

## 11. 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| α가 작게 측정됨 | ③의 비중 감소 | O1(네트워크 경로)과 O5(클래스 간 충돌) 중심으로 서술한다. 비용 모델은 그대로 쓴다. |
| LLM 플래너가 Search-only보다 성능이 낮음 | ⑦의 기여 약화 | 정책 해석, 처음 보는 시나리오, 이벤트 대응 결과를 보고한다. 주 기여는 LG 기반 공동 배치로 둔다. |
| client+OSS 동시 운용 시 불안정 | 실험 진행 불가 | P0에서 확인한다. 메모리 제한(`max_cached_mb`)을 적용한다. 문제 정의의 근거로도 사용한다. |
| Lustre 기능 미지원(FLR, PFL, TBF 버전 차이) | 일부 조치 불가 | P0에서 설치 버전의 기능을 확인하고, 미지원 기능은 대체 수단(파일 복사, 사용자 공간 속도 제한)을 쓴다. |
| 추론 런타임 성능이 낮음 | 절대 성능 비교의 설득력 저하 | 상대 비교 중심으로 서술하고, llama.cpp 기반 측정을 보조로 추가한다. |
| 일정 지연 | 평가 축소 | ⑦은 마지막 단계에서 결합하므로 나머지 구성은 영향을 받지 않는다. |

---

## 12. 미결 사항

- [ ] Orin 모델과 메모리 용량 (모델 크기 결정)
- [ ] NIC 사양 (1GbE / 10GbE)
- [ ] NVMe 모델과 용량
- [ ] 설치된 Lustre 버전과 기능 지원 여부 (PFL, FLR, NRS TBF, jobstats, CPT)
- [ ] 추론 런타임 최종 선택 (자체 PyTorch 파이프라인 / llama.cpp RPC)
- [ ] 시스템 이름
- [ ] IoTJ 리뷰어 코멘트 정리 및 반영 범위
- [ ] 기존 루트 스크립트의 `legacy/` 이동 여부

---

## 13. 참고 문헌

투고 전에 서지 정보를 다시 확인한다.

- S. Kim, D. K. Sung, Y. Son, "IFLustre: Towards Interference-free and Efficient Storage Allocation in Distributed File System," MASCOTS 2022.
- R. Qin et al., "Mooncake: Trading More Storage for Less Computation — A KVCache-centric Architecture for Serving LLM Chatbot," FAST 2025.
- B. Gao et al., "Cost-Efficient Large Language Model Serving for Multi-turn Conversations with CachedAttention," USENIX ATC 2024.
- Y. Liu et al., "CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving," SIGCOMM 2024.
- LMCache (open-source KV cache layer for vLLM).
- Y. Fu et al., "ServerlessLLM: Low-Latency Serverless Inference for Large Language Models," OSDI 2024.
- M. Zhang et al., "EdgeShard: Efficient LLM Inference via Collaborative Edge Computing," IEEE IoTJ 2024.
- S. Ye et al., "Galaxy: A Resource-Efficient Collaborative Edge AI System for In-situ Transformer Inference," INFOCOM 2024.
- prima.cpp: distributed LLM inference on home clusters (2025).
- J. Mohan et al., "CheckFreq: Frequent, Fine-Grained DNN Checkpointing," FAST 2021.
- Z. Wang et al., "GEMINI: Fast Failure Recovery in Distributed Training with In-Memory Checkpoints," SOSP 2023.
- A. Maurya et al., "DataStates-LLM: Lazy Asynchronous Checkpointing for Large Language Models," HPDC 2024.
- C. Egersdoerfer et al., "ION: Navigating the HPC I/O Optimization Journey using Large Language Models," HotStorage 2024.
- STELLAR: LLM-based storage tuning for parallel file systems, SC 2025.
- Lustre Operations Manual: Progressive File Layout, File Level Redundancy, NRS TBF, Job Stats, CPU Partition Table.
