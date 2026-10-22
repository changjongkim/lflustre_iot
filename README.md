# lflustre_iot

**CoStripe: Interference-Aware Storage Allocation for LLM Serving and Adaptation in Hyperconverged IoT Edge Clusters**

IFLustre(MASCOTS 2022) 확장 연구의 설계 문서이다. 하이퍼컨버지드 IoT 엣지 클러스터에서 LLM 서빙과 온라인 적응을 위한 간섭 인지 스토리지 할당을 다룬다.

| 항목 | 내용 |
|---|---|
| 시스템 이름 | CoStripe. 연산과 그 연산이 쓰는 데이터를 같은 노드에 두는 설계(co-placement)와 Lustre striping(파일 레이아웃) 제어를 결합한다는 뜻이다. |
| 상태 | 연구 설계 단계. 테스트베드 실측(3장) 완료 |
| 대상 장비 | NVIDIA Jetson Orin Nano 8GB × 5, 1GbE, Lustre 2.17.0 |
| 문서 구성 | 논문 흐름을 따른다. 요약 → 1장 Introduction → 2장 Background → 3장 Motivation(실측) → 4장 Design → 5장 Experiment Plan |
| 상세 자료 | 관련 연구 `docs/related_work.md`, 실측 상세 `docs/motivation_details.md`, 설계 상세 `docs/design_details.md`, 실험 계획 상세 `docs/experiment_plan.md`, 테스트베드 `docs/testbed.md`, 변경 이력 `docs/CHANGELOG.md` |

"추정"으로 표시한 수치는 5장의 실험으로 확인한 뒤 갱신한다.

---

## 목차

- [0. 요약](#0-요약)
  - [0.1 국문 요약](#01-국문-요약)
  - [0.2 영문 초록 초안](#02-영문-초록-초안)
- [1. Introduction](#1-introduction)
- [2. Background and Related Work](#2-background-and-related-work)
  - [2.1 IoT 데이터와 엣지 컴퓨팅](#21-iot-데이터와-엣지-컴퓨팅)
  - [2.2 엣지 하드웨어: Jetson Orin Nano](#22-엣지-하드웨어-jetson-orin-nano)
  - [2.3 IoT 애플리케이션에서의 LLM 활용](#23-iot-애플리케이션에서의-llm-활용)
  - [2.4 LLM 추론·학습과 저장 I/O](#24-llm-추론학습과-저장-io)
  - [2.5 Content-addressed 저장](#25-content-addressed-저장)
  - [2.6 분산 파일 시스템과 Lustre](#26-분산-파일-시스템과-lustre)
  - [2.7 원 연구: IFLustre](#27-원-연구-iflustre)
  - [2.8 관련 연구와 연구 공백](#28-관련-연구와-연구-공백)
- [3. Motivation: 테스트베드 실측](#3-motivation-테스트베드-실측)
  - [3.1 테스트베드와 측정 방법](#31-테스트베드와-측정-방법)
  - [3.2 관찰 M14: KV를 사용 노드에 두면 TTFT가 Lustre 기본 할당보다 8–19배 짧다](#32-관찰-m14-kv를-사용-노드에-두면-ttft가-lustre-기본-할당보다-819배-짧다)
  - [3.3 관찰 M1·M2: 원격 접근은 1GbE가 상한이고, 같은 노드 OST는 15–22배 빠르다](#33-관찰-m1m2-원격-접근은-1gbe가-상한이고-같은-노드-ost는-1522배-빠르다)
  - [3.4 관찰 M3: 로컬 KV 복원은 재계산보다 7–12배 빠르고, 원격 KV는 재계산보다 느릴 수 있다](#34-관찰-m3-로컬-kv-복원은-재계산보다-712배-빠르고-원격-kv는-재계산보다-느릴-수-있다)
  - [3.5 관찰 M10: LLM 런타임의 KV 캐시와 저장 계층이 서로 모른 채 8GB를 나눠 쓰면 노드가 멈춘다](#35-관찰-m10-llm-런타임의-kv-캐시와-저장-계층이-서로-모른-채-8gb를-나눠-쓰면-노드가-멈춘다)
  - [3.6 관찰 M9: stage 노드의 저장 I/O가 stage 사이 activation 전달을 2–4배 늦춘다](#36-관찰-m9-stage-노드의-저장-io가-stage-사이-activation-전달을-24배-늦춘다)
  - [3.7 관찰 M7: 여러 흐름이 OSS 하나를 공유하면 합계가 그 OSS의 1GbE로 제한된다](#37-관찰-m7-여러-흐름이-oss-하나를-공유하면-합계가-그-oss의-1gbe로-제한된다)
  - [3.8 관찰 M13: IoT 레코드를 파일 단위로 쓰면 MDS가 병목이고, pack에 붙이면 30배 빠르다](#38-관찰-m13-iot-레코드를-파일-단위로-쓰면-mds가-병목이고-pack에-붙이면-30배-빠르다)
  - [3.9 관찰 M12: 원격 KV는 사용 노드로 옮기면 이동 비용을 포함해도 세 번째 사용부터 이득이다](#39-관찰-m12-원격-kv는-사용-노드로-옮기면-이동-비용을-포함해도-세-번째-사용부터-이득이다)
  - [3.10 관찰 M11: 체크포인트 쓰기를 KV 복원과 겹치면 복원이 41% 느려지고, 시점을 미루면 2%로 줄어든다](#310-관찰-m11-체크포인트-쓰기를-kv-복원과-겹치면-복원이-41-느려지고-시점을-미루면-2로-줄어든다)
  - [3.11 관찰 M4: Lustre client 캐시가 8GB 메모리를 잠식하고 GPU 할당을 늦춘다](#311-관찰-m4-lustre-client-캐시가-8gb-메모리를-잠식하고-gpu-할당을-늦춘다)
  - [3.12 관찰 M6: 엣지 LLM 플래너는 형식은 지키지만 내용 검증이 필요하다](#312-관찰-m6-엣지-llm-플래너는-형식은-지키지만-내용-검증이-필요하다)
  - [3.13 관찰 M5·M8: 저장 I/O는 같은 노드의 LLM 연산을 3% 이내로만 늦춘다](#313-관찰-m5m8-저장-io는-같은-노드의-llm-연산을-3-이내로만-늦춘다)
  - [3.14 관찰 요약: 성능을 크게 바꾸는 것과 거의 바꾸지 않는 것](#314-관찰-요약-성능을-크게-바꾸는-것과-거의-바꾸지-않는-것)
  - [3.15 IFLustre 이점의 계승](#315-iflustre-이점의-계승)
  - [3.16 관찰에서 설계로](#316-관찰에서-설계로)
- [4. Design](#4-design)
  - [4.1 대상 환경](#41-대상-환경)
  - [4.2 시나리오와 워크로드](#42-시나리오와-워크로드)
  - [4.3 모델 선정](#43-모델-선정)
  - [4.4 데이터 객체와 I/O 특성](#44-데이터-객체와-io-특성)
  - [4.5 문제 정의](#45-문제-정의)
  - [4.6 문제를 어렵게 만드는 요인](#46-문제를-어렵게-만드는-요인)
  - [4.7 연구 질문](#47-연구-질문)
  - [4.8 해결 요소](#48-해결-요소)
  - [4.9 통합 구성](#49-통합-구성)
  - [4.10 구현](#410-구현)
- [5. Experiment Plan](#5-experiment-plan)
  - [5.1 테스트베드와 사전 점검](#51-테스트베드와-사전-점검)
  - [5.2 워크로드](#52-워크로드)
  - [5.3 측정 도구와 실험 규칙](#53-측정-도구와-실험-규칙)
  - [5.4 관찰 실험 (논문 Section III)](#54-관찰-실험-논문-section-iii)
  - [5.5 비교 대상](#55-비교-대상)
  - [5.6 평가 시나리오](#56-평가-시나리오)
  - [5.7 지표](#57-지표)
  - [5.8 Ablation과 민감도](#58-ablation과-민감도)
  - [5.9 규모 확장 시뮬레이션](#59-규모-확장-시뮬레이션)
- [6. 논문 구성 대응](#6-논문-구성-대응)
- [7. 일정](#7-일정)
- [8. 리스크와 예상 반론](#8-리스크와-예상-반론)
  - [8.1 기술 리스크](#81-기술-리스크)
  - [8.2 예상 반론과 대응](#82-예상-반론과-대응)
  - [8.3 기여 판단 기준](#83-기여-판단-기준)
- [9. 미결 사항](#9-미결-사항)
- [10. 참고 문헌](#10-참고-문헌)
- [부록 A. 크기와 메모리 계산](#부록-a-크기와-메모리-계산)
- [부록 B. 저장소의 기존 코드](#부록-b-저장소의-기존-코드)

---

## 0. 요약

### 0.1 국문 요약

**배경.** IoT 애플리케이션은 센서, 음향, 로그 데이터를 해석하는 데 LLM을 쓰기 시작했다. 지연 시간, 네트워크 대역폭, 데이터 반출 제한 때문에 이 처리는 데이터가 생기는 엣지 사이트에서 하는 것이 바람직하다.

**엣지 장치의 한계.** Jetson Orin Nano는 CPU와 GPU가 공유하는 8GB 메모리를 가지며, 4B급 LLM의 FP16 가중치(약 8GB)도 한 대에 올릴 수 없다. 그래서 엣지 사이트는 여러 장치로 소규모 클러스터를 만들고 모델 layer를 나누어 파이프라인으로 추론한다. 이 구성에서는 공유 분산 파일 시스템(DFS)의 스토리지 서버가 LLM 연산 노드를 겸한다(하이퍼컨버지드 구성).

**두 가지 문제.**
1. **IoT 요청에서는 기존 KV 재사용이 잘 동작하지 않는다.** IoT 요청은 최근 센서·로그 구간을 컨텍스트로 넣는다. 이 구간이 시간에 따라 밀리면(슬라이딩 윈도우) 앞부분 일치(prefix) 기반 KV 재사용이 깨지고, 요청마다 수천 토큰을 다시 계산한다.
2. **데이터 위치와 공유 자원이 성능을 정한다.** 실측(3장)에서 저장 I/O가 LLM 연산 자체를 늦추는 효과는 3% 이내였다. 대신 다음이 TTFT와 처리량을 몇 배씩 바꿨다.
   - 데이터·KV가 사용 노드에 있는지 (로컬 대 원격 15–22배, KV 배치 정책별 TTFT p50 8–20배)
   - 여러 I/O 흐름이 같은 OSS를 공유하는지 (분산 시 총 처리량 2–2.5배)
   - 저장 I/O가 pipeline activation과 같은 NIC를 쓰는지 (activation 전달 2–4배)
   - LLM 런타임의 KV 캐시와 저장 계층이 서로 모른 채 8GB를 나눠 쓰는지 (노드 정지 2회)
   - 백그라운드 쓰기가 지연에 민감한 읽기와 겹치는지 (KV 복원 +41% 대 +2%)

**용어.** 사용 노드는 그 데이터를 실제로 읽어 쓰는 노드이다. 모델을 layer 단위로 나눠 노드마다 실행하므로, 어떤 layer의 가중치와 KV의 사용 노드는 그 layer를 실행하는 노드로 정해진다.

본 연구에서 **간섭**은 공유 자원(OSS, NIC, 노드 메모리)을 둘러싼 경쟁과 쓰기 시점의 충돌을 뜻한다. 원 IFLustre가 다룬 OSS 공유 간섭을 하이퍼컨버지드 구성으로 넓힌 정의이며, 제목의 Interference-Aware도 이 뜻이다.

**본 연구가 하는 일.**
1. Jetson Orin Nano 5대와 Lustre로 구성한 클러스터에서 LLM 라이프사이클(수집, 적응, 서빙)의 I/O와 공유 자원 간섭을 실측한다.
2. 스트림 단위로 이어 쓰는 컨텍스트의 KV를 수집 시점에 미리 계산하고 내용 주소(content address)로 식별되는 객체로 저장하는 **semantic-aware content-addressed KV 저장소**를 설계한다. 객체의 이름은 내용, 위치는 비용 모델, 묶음·미리 읽기·압축 정책은 IoT 의미 정보(스트림, 시간, 이상 여부)가 정한다.
3. 파이프라인 분할과 데이터 배치를 Layer Group 단위로 함께 결정한다. 배치는 사용 노드, OSS별 동시 흐름, NIC 방향별 점유, 노드 메모리 예산을 함께 본다.
4. 적응 학습의 체크포인트·복제·KV 재생성 I/O의 위치·시점·속도를 서빙 SLO에 맞춰 제어한다.
5. 이벤트가 생기면 LLM 플래너와 비용 모델 검증기로 재계획한다.

### 0.2 영문 초록 초안

> IoT applications increasingly rely on large language models (LLMs) to interpret sensor streams, acoustic signals, and logs close to where data is generated. Edge devices such as the NVIDIA Jetson Orin Nano offer only 8 GB of memory shared by the CPU and GPU, which cannot hold even a 4B-parameter model in FP16. Edge sites therefore run pipeline-parallel inference on small clusters and exchange model weights, key-value (KV) caches, and adaptation state through a shared distributed file system (DFS), whose storage servers are also the LLM compute nodes. Two problems arise. First, IoT requests carry sliding windows of recent sensor and log records, which defeat prefix-based KV reuse and force repeated long prefills on weak devices. Second, our measurements show that storage I/O barely slows LLM computation itself (at most 3%), yet performance changes several-fold with where data and KV caches live relative to the consuming stage and with which shared resource each I/O stream uses: concurrent flows on one storage server share its single 1 GbE link, storage traffic on a stage node slows pipeline activation transfers by 2–4×, and an LLM runtime's own host-memory KV cache and the storage stack, each unaware of the other, can exhaust the 8 GB memory and stall the node. Pipeline parallelism spreads the delay of one stage to the entire service. We present CoStripe, which treats interference as contention for shared storage servers, network links, and node memory, generalizing the server-sharing interference addressed by our prior work. CoStripe maintains append-only per-stream contexts, builds their KV caches at ingestion time, and stores them as content-addressed objects whose names are derived from token-chain hashes and model versions, while IoT semantics (data stream, time, anomaly status) drive packing, placement, prefetching, and compaction. CoStripe further co-decides pipeline partitioning and layer-group-aligned file layouts with a cost model of per-server flow sharing, per-direction link load, and a node memory budget that covers both runtime and storage caches, controls the placement, timing, and rate of checkpoint, replication, and KV-regeneration I/O generated by adaptation, and re-plans upon lifecycle events using an LLM-based planner with a cost-model verifier. On a five-node Jetson Orin Nano cluster running Lustre, CoStripe reduces p99 TTFT by X% and improves SLO attainment by Y% compared to the default Lustre configuration, request-time prefix caching, and our prior work.

---

## 1. Introduction

**IoT 데이터와 엣지 처리.** 산업 현장의 IoT 장치는 진동·온도 같은 시계열 센서 값, 장비 음향, 네트워크 트래픽, 시스템 로그를 계속 만든다. 응답 지연 요구, 원격 전송 비용, 데이터 반출 제한 때문에 이 데이터를 사이트 안에서 처리하는 엣지 컴퓨팅이 늘고 있다.

**IoT 요청의 구조.** LLM은 이상의 원인을 설명하고, 운영자의 자연어 질문에 답하고, 장비 매뉴얼과 로그를 연결해 조치를 제시한다. 이런 요청의 입력은 다음 구조를 가진다.

```
[시스템 지시문] [라인별 장비 매뉴얼] [해당 스트림의 최근 센서·로그 기록] [질문]
```

앞의 두 부분은 같은 라인의 요청 사이에서 반복되고, 세 번째 부분은 시간에 따라 계속 늘어난다.

**KV 재사용이 깨지는 이유.** LLM 서빙 시스템은 같은 prefix의 KV cache를 재사용해 prefill을 줄인다(vLLM, SGLang, LMCache). IoT 요청이 최근 N분의 기록만 넣는 슬라이딩 윈도우를 쓰면, 가장 오래된 기록이 빠질 때 그 뒤 토큰 전체의 prefix가 달라진다. 그래서 지시문과 매뉴얼만 재사용되고, 센서·로그 구간(수천 토큰)은 요청마다 다시 계산된다. 엣지 장치에서 이 재계산은 수 초에서 수십 초이다.

**엣지 장치 한 대의 한계와 공유 저장.** Qwen3-4B의 FP16 가중치(약 8GB)는 Orin Nano 한 대(가용 약 7.4GiB)에 들어가지 않는다. 8-bit로 올리면 KV에 남는 메모리가 1GB 미만이다. 그래서 여러 장치에 layer를 나누는 파이프라인 추론이 필요하다(EdgeShard, PipeEdge, LOIP, prima.cpp). 스트림 8개의 컨텍스트가 각각 8k 토큰이면 KV는 stage당 약 3GiB로 노드의 KV 공간(0.9–2.0GB)보다 크다. 이 KV는 여러 요청이 공유하고 분할 변경과 장애 후에도 남아야 하므로 장치들 사이의 공유 저장 계층(DFS)이 필요하다.

**온라인 적응과 KV 유효성.** 장비와 공정이 바뀌면 모델도 현장 데이터로 주기적으로 적응해야 한다. 8GB 장치 한 대로는 4B 모델을 학습할 수 없으므로, 서빙 파이프라인의 base 가중치를 공유해 LoRA만 학습한다. LoRA 어댑터가 바뀌면 그 layer 이후의 KV가 달라지므로, 적응 학습은 저장된 KV의 유효성 문제를 만든다.

**하이퍼컨버지드 구성에서 성능을 정하는 것.** 엣지 사이트에는 스토리지 전용 서버를 둘 여유가 없어 DFS의 스토리지 서버가 LLM 연산 노드를 겸한다. 실측(3장)에서 같은 노드의 저장 I/O가 LLM 연산을 늦추는 효과는 모든 조건에서 3% 이내였다. 성능을 바꾼 것은 다음이다.

| 공유 자원·결정 | 실측 (3장) |
|---|---|
| 데이터·KV 위치 | 같은 노드 OST가 원격보다 15–22배 빠르다. 로컬 KV 복원이 재계산보다 7–12배 빠르다. KV를 사용 노드에 두면 TTFT p50이 0.79초이고, Lustre 기본 할당은 6.2초이다(M2, M3, M14). |
| OSS | 흐름 3개가 OSS 하나를 공유하면 합계가 120MB/s로 제한되고, 분산하면 2–2.5배가 된다(M7). |
| NIC | stage 노드의 OSS가 다른 노드의 읽기를 처리하면 그 stage의 activation 전달이 4배 느려진다(M9). |
| 노드 메모리 | LLM 런타임의 호스트 RAM KV 캐시와 Lustre client·OSS 메모리가 8GB를 나눠 써서 노드가 두 번 멈췄다(M10). |
| 쓰기 시점 | 체크포인트 쓰기가 KV 복원과 겹치면 복원이 41% 느려지고, 미루면 2%이다. LLM 실행 중 같은 노드 쓰기는 22% 느려진다(M8, M11). |

파이프라인에서는 가장 느린 stage가 처리량과 TTFT를 정한다. 따라서 데이터를 어느 노드에 두고, 각 흐름을 어느 OSS·NIC에 싣고, 언제 쓸지가 서비스 성능을 정한다.

**기존 연구의 공백.** prefix 기반 KV 재사용은 요청 시점에 KV를 만들고 스트림을 다루지 않는다. 사전 계산 KV는 고정 문서를 대상으로 한다. 엣지 KV 오프로딩은 장치 한 대의 로컬 SSD만 다루고, 엣지 분산 추론은 저장 I/O를 보지 않는다. IFLustre를 포함한 DFS 할당 연구는 스토리지와 연산이 분리된 환경의 OSS 공유만 다룬다(2.8절).

**본 연구의 접근 (CoStripe).**
1. **실측 분석.** LLM 라이프사이클 I/O와 공유 자원(OSS, NIC, 메모리) 간섭을 측정하고, 연산 감속은 대조 측정으로 보고한다.
2. **Semantic-aware content-addressed KV 저장소.** 스트림 단위로 컨텍스트를 이어 쓰고, 수집 시점에 KV를 미리 계산해 내용 주소 객체로 저장한다. 의미 정보로 묶음, 배치, 미리 읽기, 압축을 정한다.
3. **분할과 배치의 공동 결정.** Layer Group(LG)을 파이프라인 분할과 데이터 배치의 공통 단위로 삼고, 사용 노드·OSS별 동시 흐름·NIC 방향별 점유·노드 메모리 예산을 다루는 하나의 비용 모델로 결정한다.
4. **적응 학습 I/O 제어.** LoRA를 상위 LG에만 적용해 하위 LG의 KV를 어댑터와 무관하게 만들고, 상위 LG 입력 activation을 저장해 어댑터가 바뀌면 상위 LG만 다시 계산한다. 체크포인트·복제·재생성 I/O의 위치·시점·속도를 서빙 SLO에 맞춘다.
5. **이벤트 기반 재계획.** LLM 플래너가 변경안을 만들고 비용 모델 검증기가 검사한 뒤 적용한다.

CoStripe는 IFLustre의 할당 정책(interference-free, throughput-aware, runtime-aware, read-aware relocation)을 일반화한다. 3장 실측에서 이 정책들의 전제가 엣지에서도 성립함을 확인했다(M7, M11, M12, M13). IFLustre는 본 연구의 비용 모델에서 연산, activation 전달, 메모리 제약, 사용 노드 항을 뺀 특수한 경우이다.

**기여.**
1. 8GB unified memory와 1GbE를 갖는 하이퍼컨버지드 엣지 DFS에서 LLM 라이프사이클 I/O, 공유 자원 간섭, IoT 요청의 KV 재사용 특성을 실측으로 분석한다. 저장 I/O의 연산 감속은 3% 이내이고, 데이터 위치와 공유 자원이 성능을 몇 배씩 바꾸며, 메모리 예산을 넘기면 노드가 멈춘다는 점을 보인다.
2. 이름(내용), 위치(비용 모델), 정책(IoT 의미)을 분리한 semantic-aware content-addressed KV 저장소를 제안한다. 수집 시점 prefill, 의미 기반 묶음과 압축, 어댑터 범위를 반영한 주소, 경계 activation 기반 부분 재생성을 포함한다.
3. Layer Group 단위로 파이프라인 분할과 데이터 배치를 함께 결정하는 비용 모델과 배치 기법을 제안한다. 장애 대체 분할을 고려한 복제 위치 결정을 포함한다.
4. IFLustre의 할당 정책을 라이프사이클 전체로 확장한 CoStripe와 이벤트 기반 LLM 플래너·검증기를 구현하고, Jetson Orin Nano 5대에서 평가한다.

---

## 2. Background and Related Work

### 2.1 IoT 데이터와 엣지 컴퓨팅

원 IFLustre 연구는 아래 6종의 공개 데이터셋으로 IoT I/O를 모사했다. 본 연구는 여기에 RIoTBench(수백 바이트 센서 레코드 스트림)와 Loghub(HDFS, BGL 등 시스템 로그)를 더한다.

| 데이터셋 | 도메인 | 데이터 형태 | 파일 크기 | 원 논문 이름 |
|---|---|---|---|---|
| Bot-IoT | 네트워크 보안 | 네트워크 트래픽(봇넷 공격 포함) | 수백 MB | IoTApp1 |
| Widar3.0 | 행동 인식 | WiFi CSI 기반 제스처 | 약 215KB | IoTApp2 |
| MIMII | 산업 장비 | 정상/고장 장비 음향 | 약 2.5MB | IoTApp3 |
| VisDrone | 영상 | 드론 촬영 이미지 | 수십~수백 KB | IoTApp4 |
| EPIC-Sounds | 음향 | 주방 활동 음향 | 단일 4GB | IoTApp5 |
| LoED | 센서 네트워크 | LoRaWAN 패킷 | 10~30MB | IoTApp6 |

IoT 레코드에는 공통된 의미 속성이 있고, 본 연구는 이를 저장 정책에 쓴다.

| 속성 | 예시 | 용도 |
|---|---|---|
| 출처 | 라인, 스트림, 센서 | 컨텍스트 단위, 묶음 단위, 정책 우선순위 |
| 시간 | 타임스탬프, 측정 주기 | 컨텍스트 순서, 보존 기간, 압축 대상 |
| 상태 | 정상, 경고, 이상 | 압축 규칙(이상 기록은 원문 유지) |
| 접근 패턴 | 교대 시각, 점검 일정 | 미리 읽기, 메모리 상주 |

작은 레코드는 파일 단위 striping의 효과가 없다(원 IFLustre IoTJ, M13). 그래서 IoT 원본 데이터는 성능 최적화의 주 대상이 아니라, 컨텍스트와 KV를 만드는 입력이자 배경 I/O 부하로 다룬다.

| 항목 | 클라우드 | 엣지 사이트 (본 연구) |
|---|---|---|
| 노드 수 | 수천 이상 | 5 |
| 노드 메모리 | CPU DRAM 수백 GB + GPU HBM 수십 GB | 8GB (CPU와 GPU 공유) |
| 저장 계층 | 전용 스토리지 서버 | 연산 장치에 장착한 NVMe SSD |
| 네트워크 | 25–400Gbps, RDMA | 1GbE |
| 데이터 반출 | 가능 | 제한되는 경우가 많음 |
| 전력 | 노드당 수백 W–kW | 장치당 7–25W |

### 2.2 엣지 하드웨어: Jetson Orin Nano

Jetson Orin은 ARM CPU와 Ampere GPU를 하나의 SoC에 통합한다. GPU 텐서, CPU 프로세스 메모리, page cache, Lustre 캐시가 모두 같은 LPDDR5 메모리와 메모리 컨트롤러(EMC)를 쓴다.

| 모듈 | CPU | GPU | 메모리 | 메모리 대역폭 | AI 성능 (INT8, sparse) | 전력 | NIC |
|---|---|---|---|---|---|---|---|
| **Orin Nano 8GB** | 6-core Cortex-A78AE (1.5GHz, Super 1.7GHz) | 1024-core Ampere, Tensor Core 32개 | 8GB LPDDR5 (128-bit) | 68GB/s (Super 102GB/s) | 40 TOPS (Super 67 TOPS) | 7–15W (Super 최대 25W) | 1GbE |
| Orin NX 16GB | 8-core Cortex-A78AE | 1024-core Ampere, Tensor Core 32개 | 16GB LPDDR5 | 102.4GB/s | 100 TOPS (Super 157) | 10–25W (Super 40W) | 1GbE |
| AGX Orin 64GB | 12-core Cortex-A78AE | 2048-core Ampere, Tensor Core 64개 | 64GB LPDDR5 | 204.8GB/s | 275 TOPS | 15–60W | 최대 10GbE |

수치는 NVIDIA 공개 자료 기준이며 공식 datasheet로 다시 확인한다(9장).

| 제약 | 영향 | 실측 |
|---|---|---|
| 가용 메모리 약 7.4GiB를 OS, 런타임(런타임 자체 KV 캐시 포함), Lustre 서버·client·캐시, 가중치, KV, 학습 상태가 나눠 씀 | 메모리 용량 경쟁이 가장 직접적이다. client 캐시 기본 상한은 RAM의 1/2이다. | M4, M10 |
| CPU 6코어를 OSS 스레드, LNet/TCP, LLM 런타임이 나눠 씀 | GPU 중심 추론은 거의 영향을 받지 않는다. 수집, 토큰화, 압축은 영향을 받을 수 있다. | M5, M8 |
| 메모리 대역폭 68–102GB/s가 decode의 상한 | 같은 노드 저장 I/O에 따른 decode 감속은 3% 이내였다. | M8 |
| 1GbE 하나 (약 117MB/s) | 원격 접근이 로컬 NVMe보다 10배 이상 느리다. OSS의 원격 I/O와 stage 사이 activation이 같은 NIC를 쓴다. | M1, M2, M9 |
| 연산 성능이 낮아 긴 prefill이 수 초에서 수십 초 | KV 재사용의 가치가 데이터센터보다 크다. | M3 |
| NVMe는 M.2 슬롯에 따로 장착, OS는 microSD, 전력 모드(`nvpmodel`)와 zram 스왑이 성능에 영향 | 측정 전에 기록하고 고정한다. | `docs/testbed.md` |

### 2.3 IoT 애플리케이션에서의 LLM 활용

| 활용 | 입력 | 출력 | 요구 특성 |
|---|---|---|---|
| 이상 원인 설명 | 센서·음향 특징 요약, 이상 탐지 결과, 장비 정보 | 원인 후보와 근거 | 긴 컨텍스트, 도메인 지식 |
| 운영자 질문 응답 | 매뉴얼, 최근 로그·센서 기록, 질문 | 답변, 조치 절차 | 긴 공통 prefix, 계속 늘어나는 기록, 낮은 지연 |
| 로그 분석 | 시스템·장비 로그 | 이상 로그 판정, 요약 | 긴 입력, 로그 형식 적응 |
| 멀티모달 판독 | 이미지, 음향 | 판독 결과 | VLM, 큰 입력 |
| 에이전트 제어 | 상태 요약, 정책 | 제어 명령 | 정확한 출력 형식 |

공통점은 세 가지이다. 입력에 반복되는 공통 부분(지시문, 매뉴얼)과 스트림별로 누적되는 기록이 함께 들어간다. 장비와 공정이 바뀌면 현장 데이터로 온라인 적응해야 한다. 데이터 반출 제한과 지연 요구 때문에 엣지 실행이 선호된다. 관련 조사로 "When IoT Meet LLMs"(2024)와 LLM 기반 엣지 인텔리전스 조사(Friha et al., 2024)가 있다.

### 2.4 LLM 추론·학습과 저장 I/O

#### 2.4.1 추론 단계와 KV 재사용

Decoder-only LLM은 임베딩, L개의 transformer layer, 출력 head로 구성된다. Qwen3-4B는 입력 임베딩과 출력 head가 같은 행렬을 쓴다(tied embedding).

| 단계 | 내용 | 성능 결정 요인 |
|---|---|---|
| Prefill | 입력 전체를 한 번에 처리해 KV cache를 만든다. | 연산량 |
| Decode | 토큰을 하나씩 생성하며 매번 가중치 전체와 누적 KV를 읽는다. | 메모리 대역폭 |

토큰당 KV 크기는 `2 × L × H_kv × d_head × b`이다. layer l의 KV는 앞의 모든 토큰과 layer 0–l의 모든 가중치에 의존한다. 그래서 KV는 같은 모델·가중치 버전과 같은 앞부분 토큰 열에서만 그대로 재사용할 수 있다.

| 재사용 방식 | 대표 연구 | 재사용 조건 | 한계 |
|---|---|---|---|
| prefix 재사용 (GPU 메모리) | vLLM (PagedAttention, block hash), SGLang (RadixAttention) | 앞부분 토큰 열이 같아야 함 | 메모리 용량, 요청 시점에만 생성 |
| prefix 재사용 (계층형 저장) | CachedAttention, Mooncake, LMCache, IMPRESS | 위와 같음 | 요청 시점 생성, 데이터센터 저장 풀 |
| 위치 독립 재사용 | Prompt Cache, CacheBlend, EPIC | 모듈·문서 단위 재사용, 일부 토큰 재계산 | 근사(품질 영향), 정적 모듈 |
| 사전 계산 KV | TurboRAG, MemLLM | 고정 문서의 KV를 미리 계산 | 고정 문서 대상 |

vLLM은 블록 해시(`hash(부모 블록 해시, 블록 토큰)`)로 KV 블록을 식별한다. 메모리 안에서 이미 content addressing을 쓰는 셈이며, 본 연구는 이를 저장 계층과 스트림으로 넓힌다.

**슬라이딩 윈도우 문제.** 요청이 `[지시문][매뉴얼][최근 N분 기록][질문]`이면, 가장 오래된 기록이 빠질 때 그 뒤 기록 전체의 위치와 앞부분이 바뀐다. prefix 재사용은 매뉴얼까지만 적용되고 기록 구간은 매번 다시 계산된다.

#### 2.4.2 모델 크기와 병렬화

| 모델 | 파라미터 | Layer | Q head | KV head | hidden | 임베딩 공유 | FP16 | Q8_0 | Q4_K_M | KV/토큰 (FP16) |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-0.6B | 0.6B | 28 | 16 | 8 | 1024 | 예 | 약 1.2GB | 약 0.6GB | 약 0.4GB | 112KiB |
| Qwen3-1.7B | 1.7B | 28 | 16 | 8 | 2048 | 예 | 약 3.4GB | 약 1.8GB | 약 1.1GB | 112KiB |
| **Qwen3-4B** | 4.0B | 36 | 32 | 8 | 2560 | 예 | **약 8.0GB** | 약 4.3GB | 약 2.5GB | **144KiB** |
| Qwen3-8B | 8.2B | 36 | 32 | 8 | 4096 | 아니오 | 약 16.4GB | 약 8.7GB | 약 5.0GB | 144KiB |
| Qwen3-14B | 14.8B | 40 | 40 | 8 | 5120 | 아니오 | 약 29.5GB | 약 15.7GB | 약 9.0GB | 160KiB |

Orin Nano 1대에 Qwen3-4B FP16은 들어가지 않는다. Q8_0은 들어가지만 KV 여유가 1GB 미만이고, Q4_K_M은 KV 여유가 약 2–3GB이지만 4-bit 품질 저하가 있다(비교 대상 B7로만 사용). 계산식은 부록 A에 있다.

| 병렬화 | 분할 방법 | 통신 | 엣지 적합성 |
|---|---|---|---|
| Tensor Parallelism | layer 내부 행렬 | layer마다 all-reduce | 1GbE에서 부적합 |
| Pipeline Parallelism | 연속된 layer 구간을 장치에 배정 (stage) | stage 경계에서 activation만 전달 (Qwen3-4B 토큰당 5KiB) | 엣지 분산 추론의 표준 |

- 처리량은 가장 느린 stage가 결정한다.
- 8k 토큰 prefill은 stage 경계마다 약 40MiB(1GbE로 약 0.35초)를 전달하며, 같은 NIC의 원격 저장 I/O와 경쟁한다(M9).
- stage 경계 activation은 토큰당 5KiB로 KV(144KiB)보다 훨씬 작다. 이를 저장하면 경계 이후 layer만 다시 계산할 수 있다(4.8.2절).

#### 2.4.3 적응 학습과 어댑터

- **LoRA와 QLoRA.** LoRA는 가중치를 고정하고 일부 projection에 저랭크 행렬을 더해 학습한다. QLoRA는 4-bit base 위에서 LoRA를 학습한다. Jetson ARM64에서는 bitsandbytes 4-bit가 불안정하다는 보고가 있고, Orin Nano 8GB에서 안정적으로 보고된 범위는 1B급 FP16 LoRA 정도이다.
- **파이프라인 공동 적응.** 서빙 파이프라인의 FP16 base 가중치를 공유하고 LoRA만 학습한다. 데이터센터에서는 FlexLLM, ConServe, DeltaServe가 같은 GPU에서 추론과 미세조정을 함께 실행한다.
- **LoRA 범위와 KV.** LoRA를 layer a 이상에만 적용하면 그 아래 layer의 KV는 어댑터와 무관하게 유효하고, backward도 지나가지 않는다. 대신 적응 능력이 일부 줄어든다(5.7절 품질 확인).
- **크기.** 어댑터는 Qwen3-4B, rank 16, q/k/v/o, 상위 9 layer 기준 약 6MB이다. 체크포인트(어댑터 + optimizer 상태)는 장애에 대비해 다른 장치에 복제해야 한다. 다중 어댑터 서빙으로 S-LoRA, Punica, EdgeLoRA가 있다.

#### 2.4.4 LLM 라이프사이클의 저장 I/O

| I/O 유형 | 발생 시점 | 크기 (Qwen3-4B 기준) | 패턴 | 성능 영향 |
|---|---|---|---|---|
| 가중치 로드 | 시작, 재분할, 장애 복구 | stage당 2.4–3.2GB | 순차 읽기 | 시작·복구 시간 |
| 수집 시점 KV 생성 | 레코드 수집 후 배치 단위 | 256토큰 chunk당 stage별 12MiB | 컨텍스트 KV 읽기 + 새 chunk 쓰기 | 저장 위치 노드의 부하, 데이터 최신성 |
| 요청 시점 KV 로드 | 요청 도착 | 8k 컨텍스트당 stage별 384MiB | 순차 읽기 | TTFT |
| 경계 activation 저장 | 수집 시점 prefill 중 | 토큰당 5KiB | 순차 쓰기 | 작음 |
| 어댑터 전환 후 KV 재생성 | 적응 라운드 종료 후 | LG9–11 KV, 8k 컨텍스트당 288MiB | activation 읽기 + KV 쓰기 | 버스트 |
| 체크포인트 | 적응 학습 중 주기적 | 수십–수백 MB | 버스트 쓰기 + 원격 복제 | 동시 서빙 지연 |
| 컨텍스트 압축 | 컨텍스트 한계 도달 | 컨텍스트 KV 재생성 | 쓰기 버스트 | 연산·I/O 버스트 |
| IoT 수집 | 계속 | 레코드 수백 B–파일 수 GB | 소파일 쓰기 | 배경 부하 |

### 2.5 Content-addressed 저장

Content-addressed 저장(CAS)은 객체의 이름을 위치가 아니라 내용의 해시로 정한다. 대표 시스템은 LBFS(SOSP 2001), Venti(FAST 2002), Data Domain(FAST 2008), Git(packfile), IPFS(2014)이다.

| 성질 | 본 연구에서의 의미 |
|---|---|
| 중복 제거 | 같은 내용은 한 번만 저장된다. 예: 같은 라인의 지시문·매뉴얼 KV |
| 쓰기 후 변경 없음 | 봉인된 객체는 바뀌지 않으므로 복제본이 낡지 않는다. |
| 위치 독립 | 객체를 옮기거나 복제해도 이름이 바뀌지 않는다. 재분할과 장애 대응이 위치 변경만으로 끝난다. |
| 검증 | 읽은 데이터가 기대한 내용인지 해시로 확인한다. |
| 묶음 저장 | 작은 객체를 큰 파일(pack)로 묶어 메타데이터 비용을 줄인다. |

LLM KV에 적용하려면 세 가지가 다르다. 주소는 chunk 내용이 아니라 앞부분 체인 해시, 모델·어댑터 버전, layer 구간을 포함해야 한다. 어댑터 버전이 바뀔 때 어떤 layer의 KV가 무효가 되는지 주소에 반영해야 한다. 객체의 묶음·배치·보존은 해시로 정할 수 없으므로 IoT 의미 정보를 별도 속성으로 둔다.

### 2.6 분산 파일 시스템과 Lustre

본 연구는 Lustre를 쓴다. 파일·디렉터리 단위로 OST를 지정할 수 있고, 레이아웃·복제·QoS·작업 통계·캐시 제한 기능이 있으며, IFLustre를 계승하기 때문이다. Ceph는 CRUSH 해시로 위치가 정해져 사용자가 지정하기 어렵고, HDFS는 POSIX를 완전히 지원하지 않는다.

| 구성 요소 | 역할 |
|---|---|
| MGS | 파일 시스템 설정 관리 |
| MDS / MDT | 이름 공간, 파일 속성, 레이아웃 관리 |
| OSS / OST | 파일 데이터 저장 |
| Client | POSIX 인터페이스, OST에 직접 I/O |
| LNet | 네트워크 계층 (TCP는 ksocklnd) |
| OSD 백엔드 | ldiskfs 또는 ZFS |

| 기능 | 본 연구에서의 용도 |
|---|---|
| Striping (`lfs setstripe -c -S -i`), 디렉터리 default layout | LG 파일과 KV pack 파일의 OST 지정 |
| PFL, DoM | 가중치 파일 구간별 OST 지정(대안), 작은 인덱스 파일(선택) |
| FLR (`lfs mirror create/extend/resync`) | 가중치, 공유 prefix KV, 봉인된 pack, 체크포인트의 복제 |
| `lfs migrate` | 경로를 유지한 채 재배치. CAS의 위치 독립성과 맞음 |
| NRS TBF | 복제, 재배치, 재생성, 원격 읽기의 속도 제한 |
| Job stats, CPT | I/O 클래스별 부하 측정, OSS 스레드의 CPU 고정 |
| `llite.*.max_cached_mb` | client 캐시 상한 (기본 RAM의 1/2). 8GB 노드에서 반드시 설정 |

엣지에서 고려할 점은 네 가지이다. Lustre는 같은 노드에서 client와 OSS를 함께 운용하는 구성을 권장하지 않는다(메모리 압박 시 문제). 다른 노드가 이 노드의 OST를 쓰면 이 노드의 OSS가 메모리와 CPU를 쓴다. 같은 노드 OST 접근도 RPC 처리 비용이 남는다. MDS 이중화는 범위 밖이다.

### 2.7 원 연구: IFLustre

**MASCOTS 2022 버전.** Lustre에서 여러 애플리케이션이 OSS를 공유할 때 생기는 간섭을 줄이는 저장 할당 기법이다. Application Analyzer가 같은 이름의 과거 실행 로그로 stripe count·size를 정하고 처리량과 실행 시간을 ML로 예측한다. OSS Allocator는 interference-free, throughput-aware, runtime-aware allocation을 순서대로 적용한다. 관찰은 세 가지이다. 성능은 가장 느린 OSS가 정한다. 공유 상황에서도 많은 OSS를 쓰는 것이 유리할 수 있다. 총 처리량이 하드웨어 한계에 가까우면 OSS 공유가 성능을 떨어뜨린다. 최대 47% 개선했다.

**IEEE IoTJ 버전 (Reject & Resubmit).** 클라우드 DFS와 IoT 데이터셋 6종으로 확장하고, 파일 크기에 따른 striping 효과 차이와 read-aware relocation을 추가했다. 최대 47.8% 개선을 보고했다.

**새 환경에서의 한계**

| 항목 | IFLustre의 가정 | Orin Nano 엣지 LLM 환경 |
|---|---|---|
| 노드 역할 | 스토리지와 연산 분리 | 같은 장치가 둘 다 수행 |
| 노드 자원 | 서버급, 10GbE | 8GB 공유 메모리, 6코어, 1GbE |
| 간섭 범위 | OSS 사이 | OSS 사이 + NIC(저장 I/O와 activation) + 노드 메모리(런타임 KV 캐시와 저장 계층). 연산 감속은 3% 이내 |
| striping 효과 | stripe count 증가로 대역폭 확대 | 1GbE에서는 원격 stripe가 가장 느린 stripe가 되어 불리 |
| 데이터와 식별 | 애플리케이션별 파일, 경로로 식별 | layer 구조와 버전 의존성을 가진 LLM 상태, 내용으로 식별 |
| 사용 노드 | 고려하지 않음 | 객체마다 사용 노드가 정해짐 |
| 워크로드 | 독립 애플리케이션 | 데이터를 주고받는 라이프사이클 |
| 결정 근거와 시점 | 같은 앱의 과거 로그, 시작 시 1회 | 새 어댑터·컨텍스트는 이력 없음, 이벤트마다 |

### 2.8 관련 연구와 연구 공백

분야별 상세 비교와 전체 참고 문헌은 `docs/related_work.md`에 있다.

| 연구 갈래 | 대표 연구 | 다루는 것 | 이 환경에서 다루지 않는 것 |
|---|---|---|---|
| 저장 I/O 간섭과 QoS | CALCioM, GIFT, LoomIO, A2FL, Lustre NRS TBF, IFLustre | 공유 스토리지 대역폭 조정, 레이아웃 | 스토리지와 연산이 같은 노드일 때의 NIC·메모리 공유, 사용 노드 |
| 자원 공존과 격리 | Heracles, PARTIES, Caladan, MemGuard | 노드 내 CPU·메모리 대역폭 분할 | 데이터 배치로 간섭 위치를 바꾸는 방법. 본 실측에서 GPU 추론은 이 경로에 둔감했다 |
| 모델 로딩·오프로딩 | ServerlessLLM, LLM in a flash, PowerInfer, FlexGen | 로딩 시간, 메모리 부족 | 장치 한 대의 로컬 저장만 다룸 |
| prefix KV 재사용 | vLLM, SGLang, CachedAttention, Mooncake, LMCache | 블록·chunk 해시 KV 재사용, 계층형 KV 저장 | 요청 시점 생성, 스트림, 저장 계층과의 노드 메모리 예산 공유 |
| KV 사전 계산·위치 독립 재사용 | Prompt Cache, CacheBlend, EPIC, TurboRAG, MemLLM | 모듈·문서 KV 재사용 | 고정 문서·근사 재사용. 계속 늘어나는 스트림과 버전 범위 |
| 엣지 KV 오프로딩 | KVSwap, Dual-Blade, MTDS | 디스크 인지 KV 교체 | 단일 장치 |
| 엣지 분산 추론 | PipeEdge, EdgeShard, Galaxy, LOIP, prima.cpp | 연산·메모리·네트워크 기준 분할 | 저장 I/O, KV, 학습 |
| 추론·학습 공동 실행, 어댑터 서빙 | FlexLLM, ConServe, DeltaServe, S-LoRA, Punica, EdgeLoRA | 같은 GPU에서 추론과 미세조정, 다중 LoRA | 어댑터 변경에 따른 저장 KV 무효화, 저장 I/O |
| 학습 체크포인트 | CheckFreq, Check-N-Run, Gemini, ByteCheckpoint | 학습 처리량, 복구 시간 | 같은 저장 계층·NIC를 쓰는 서빙 지연 |
| CAS·LLM 기반 튜닝 | Venti, LBFS, IPFS / ION, STELLAR, GPTuner | 내용 해시 식별 / 오프라인 설정 튜닝 | LLM 상태의 버전 의존성 / 온라인 이벤트 재계획 |

| ID | 연구 공백 |
|---|---|
| G1 | 저장 서버와 LLM 연산 노드가 같은 소형 엣지 클러스터에서 공유 자원(OSS, NIC, 노드 메모리)과 데이터 위치가 LLM 서빙에 주는 영향이 측정·모델링되지 않았다. 본 실측에서 이 영향은 저장 I/O의 연산 감속(3% 이내)보다 훨씬 컸다. |
| G2 | 엣지 분산 추론의 분할은 저장 위치를 보지 않고, DFS 배치 연구는 연산 분할을 보지 않는다. |
| G3 | 계속 늘어나는 IoT 스트림의 KV를 수집 시점에 만들어 근사 없이 재사용하는 저장 구조가 없다. 어댑터 버전 변화에 따른 저장 KV의 유효성 관리도 다뤄지지 않았다. |
| G4 | 수집, 적응, 서빙의 I/O가 한 클러스터에서 공존할 때 체크포인트·복제·재생성 I/O의 위치·시점·속도 제어가 다뤄지지 않았다. |
| G5 | 엣지 현장의 잦은 이벤트와 자연어 운영 정책 아래에서의 온라인 재계획이 다뤄지지 않았다. |

---

## 3. Motivation: 테스트베드 실측

2026-10-22에 실제 클러스터에서 측정했다. 4장 설계의 근거이며, 5.4절 관찰 실험(O1–O7)의 예비 결과이다. 관찰마다 그림, 핵심 수치, 시사점만 둔다. 관찰은 LLM 응답 시간과 노드 가용성에 미치는 영향이 큰 순서(강함 → 약함)로 둔다. 관찰 번호(M1–M14)는 측정 순서이다.

| 절 | 관찰 | 효과 크기 | 강도 |
|---|---|---|---|
| 3.2 | M14 KV 배치 정책과 TTFT | TTFT p50 8–20배 | 강함 |
| 3.3 | M1·M2 같은 노드 대 원격 OST | 처리량 15–22배 | 강함 |
| 3.4 | M3 KV 복원 대 재계산 | 7–12배 | 강함 |
| 3.5 | M10 런타임 KV 캐시와 저장 계층의 메모리 | 노드 정지 2회 | 강함 |
| 3.6 | M9 저장 I/O와 activation의 NIC 공유 | 2–4배 | 중간 |
| 3.7 | M7 OSS 공유 | 2–2.5배 | 중간 |
| 3.8 | M13 수집 저장 단위 (pack) | 30배 (수집 경로) | 중간 |
| 3.9 | M12 원격 KV 재배치 | 5회 사용 1.8배 | 중간 |
| 3.10 | M11 백그라운드 쓰기 시점 | +41% 대 +2% | 중간 |
| 3.11 | M4 client 캐시와 GPU 할당 | 할당 시간 +25% | 약함 |
| 3.12 | M6 LLM 플래너 | 실행 가능성만 확인 | 약함 |
| 3.13 | M5·M8 저장 I/O의 LLM 연산 감속 | 3% 이내 | 약함 (대조) | 측정 구성, 전체 표, 분석은 `docs/motivation_details.md`에 있고, 원시 결과는 `results/p0/`, `results/motivation/`에 있다.

### 3.1 테스트베드와 측정 방법

| 항목 | 내용 |
|---|---|
| 노드 | jetson0: MGS + MDT / jetson1–3: OSS(OST0000–0002) + client / jetson: client (NVMe 없음) |
| 공통 | Orin Nano 8GB Super(25W), L4T R36.4.4, Lustre 2.17.0(ldiskfs), 유선 1GbE, OS는 microSD |
| 저장 측정 | fio, 2GiB 파일, 4MiB I/O, libaio iodepth 16, direct I/O(표기 시 buffered), 측정 전 캐시 비움. 파일은 dd로 미리 채워 Lustre 레이아웃을 유지하고 레이아웃을 확인한다 |
| LLM 측정 | llama.cpp(CUDA sm_87), Qwen3-4B Q4_K_M, KV FP16, slot 저장·복원. M8 재측정부터 `--cache-ram 0` |
| 노드 기록 | 노드 내부 샘플러(1초 간격: CPU, NIC, 메모리, 회수·스왑, GPU, 전력) |
| 그림 색 | 로컬 = 파랑, 원격 = 주황, 재계산 = 청록 |

### 3.2 관찰 M14: KV를 사용 노드에 두면 TTFT가 Lustre 기본 할당보다 8–19배 짧다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m14-ttft-cdf-dark.svg">
  <img alt="KV 배치 정책별 TTFT 누적 분포: 사용 노드 배치는 모든 요청이 1.4초 안, Lustre 기본 할당은 중앙값 6.2초·최대 29초, 사용 노드를 보지 않는 부하 분산은 중앙값 16초·최대 42초" src="docs/figures/m14-ttft-cdf-light.svg" width="620">
</picture>

stage 노드 3대(jetson1–3)가 각자 llama-server를 실행하고, 스트림 컨텍스트 12개(각 4k 토큰, KV 576MiB)에 대한 Zipf 분포 요청(초당 0.3개, 4분)을 처리한다. 정책은 KV 파일을 어느 OST에 두느냐만 다르다.

| KV 배치 정책 | 로컬 복원 요청 | TTFT p50 | TTFT p90 | TTFT p99 |
|---|---|---|---|---|
| Lustre 기본 할당기 | 35 / 79 | 6.2초 | 19.1초 | 25.9초 |
| OSS 부하 기반 분산 (사용 노드 무시, IFLustre식) | 9 / 79 | 16.0초 | 27.2초 | 38.2초 |
| 사용 노드 OST | 79 / 79 | 0.79초 | 1.01초 | 1.36초 |

**시사점:** 원격 KV 복원(576MiB에 5–6초) 동안 같은 노드의 다음 요청이 기다려 꼬리 지연이 커진다. 사용 노드를 보지 않는 부하 분산은 Lustre 기본 할당보다 나쁠 수 있다. 부하 분산의 결과는 배치에 크게 좌우되므로 논문에서는 seed를 바꿔 반복한다.

### 3.3 관찰 M1·M2: 원격 접근은 1GbE가 상한이고, 같은 노드 OST는 15–22배 빠르다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m1a-network-dark.svg">
  <img alt="노드 간 iperf3 대역폭: 서버 간 약 930Mb/s, 서버→client 약 930Mb/s, client→서버 약 723Mb/s, WiFi 약 150Mb/s" src="docs/figures/m1a-network-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m1b-striping-dark.svg">
  <img alt="client의 원격 OST 처리량: stripe count 1, 2, 3 모두 쓰기 약 93MB/s, 읽기 115–118MB/s" src="docs/figures/m1b-striping-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m2a-local-remote-dark.svg">
  <img alt="같은 노드 OST와 원격 OST 처리량: 로컬 쓰기 1,699MB/s 읽기 2,482MB/s, 원격 115MB/s, 쓰기 15배 읽기 22배 차이" src="docs/figures/m2a-local-remote-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m2b-io-cpu-dark.svg">
  <img alt="I/O 중 CPU 사용률: 로컬 읽기 45%, 로컬 쓰기 42%, 원격 읽기 client 측 20%, 원격 쓰기 client 측 13%, 원격 I/O를 처리하는 OSS 서버 측 읽기 13%, 쓰기 19%" src="docs/figures/m2b-io-cpu-light.svg" width="620">
</picture>

| 경로 | 쓰기 | 읽기 | CPU (6코어 기준) |
|---|---|---|---|
| 같은 노드 OST (jetson1) | 1,699MB/s | 2,482MB/s | 42–45% |
| 원격 OST | 114.6MB/s | 114.8MB/s | 13–20% (client 측) |
| 원격, stripe count 1 / 2 / 3 (jetson) | 93.3 / 92.8 / 92.8MB/s | 114.6 / 117.5 / 117.5MB/s | – |

노드 간 유선 대역폭은 약 930Mb/s이다(jetson 송신만 약 723Mb/s).

**시사점:** 원격 경로는 client NIC가 상한이라 striping으로 대역폭을 넓힐 수 없다. 성능을 바꾸는 수단은 데이터를 어느 노드에 두느냐이다.

### 3.4 관찰 M3: 로컬 KV 복원은 재계산보다 7–12배 빠르고, 원격 KV는 재계산보다 느릴 수 있다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m3-prefill-vs-kv-dark.svg">
  <img alt="컨텍스트 길이별 재계산과 KV 복원 시간: 8k에서 재계산 15.2초, 원격 OST 복원 21.9초, 로컬 OST 복원 2.2초" src="docs/figures/m3-prefill-vs-kv-light.svg" width="620">
</picture>

| 토큰 | 재계산 (prefill) | KV 파일 | 로컬 OST 복원 | 원격 OST 복원 |
|---|---|---|---|---|
| 1k | 1.73초 | 144MiB | 0.20초 | 1.37초 |
| 2k | 3.42초 | 288MiB | 0.34초 | 2.68초 |
| 4k | 7.03초 | 576MiB | 0.61초 | 5.30초 |
| 8k | 15.2초 | 1,152MiB | 2.16초 | 21.9초 |

복원 후 첫 토큰까지는 0.1초대이다.

**시사점:** KV를 수집 시점에 미리 만들어 사용 노드에 두면 이득이 크다. 원격 KV는 재계산과 비교해 고른다.

### 3.5 관찰 M10: LLM 런타임의 KV 캐시와 저장 계층이 서로 모른 채 8GB를 나눠 쓰면 노드가 멈춘다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m10-jetson1-hang-dark.svg">
  <img alt="jetson1 메모리 추이: MemAvailable이 LLM 서버 로드와 요청마다 줄어 906MB가 된 뒤, 같은 노드의 Lustre direct 읽기가 시작되자 41MB까지 떨어지고 zram 스왑이 3.4GB까지 차면서 노드가 멈춤" src="docs/figures/m10-jetson1-hang-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m10c-reclaim-dark.svg">
  <img alt="같은 노드 Lustre 읽기 중 메모리 회수: direct 읽기는 회수 없음, buffered 캐시 상한 512MB는 direct reclaim 67k, 기본 상한은 340k 페이지 스캔. decode 감속은 1.7–3.0%" src="docs/figures/m10c-reclaim-light.svg" width="620">
</picture>

- jetson1이 측정 중 두 번 멈췄다. 감시 샘플러 기록에서 MemAvailable이 41MB까지 떨어지고 zram 스왑이 3.4GB까지 찬 뒤 멈췄다.
- 주된 원인은 llama.cpp 서버의 호스트 RAM prompt cache(`--cache-ram`, 기본 8,192MiB)이다. 서버는 프롬프트가 바뀔 때마다 이전 KV를 RAM에 쌓는다. 서로 다른 요청 4개(각 2,705토큰)에서 MemAvailable이 2,668 → 1,581MB로 줄었고, `--cache-ram 0`이면 2,738 → 2,726MB로 유지되었다. 같은 노드의 Lustre I/O가 남은 메모리를 마저 썼다.
- `--cache-ram 0`이면 ctx 8192 서버와 같은 노드 Lustre 읽기를 함께 돌려도 MemAvailable이 약 2GB로 유지된다. client 캐시 상한이 기본값이면 512MB일 때보다 페이지 회수가 약 5배 많다(direct reclaim 340k 대 67k 페이지 스캔).

**시사점:** 런타임 캐시, client 캐시, OSS 메모리는 각자 자기 상한만 지킨다. KV 계층(GPU, 호스트 RAM, 로컬 OST, 원격 OST)과 저장 계층 메모리를 하나의 노드 메모리 예산으로 관리해야 한다. 이후 측정은 모두 `--cache-ram 0`으로 한다.

### 3.6 관찰 M9: stage 노드의 저장 I/O가 stage 사이 activation 전달을 2–4배 늦춘다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m9a-activation-handoff-dark.svg">
  <img alt="8k 토큰 prefill activation(40MiB) 전달 시간: 저장 I/O 없음 362ms, 받는 stage에 쓰기 709ms(2.0배), 보내는 stage에서 읽기 1,473ms(4.1배), 둘 다 1,267ms(3.5배)" src="docs/figures/m9a-activation-handoff-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m9b-decode-hop-dark.svg">
  <img alt="decode 토큰 메시지(5KiB) 왕복: 저장 I/O 없음 0.6ms, 받는 stage에 쓰기 0.4ms, 보내는 stage에서 읽기 4.6ms, 둘 다 3.0ms" src="docs/figures/m9b-decode-hop-light.svg" width="620">
</picture>

| 조건 (jetson1 → jetson2, jetson이 저장 I/O) | 8k prefill activation (40MiB) | decode 메시지 왕복 (5KiB) |
|---|---|---|
| 저장 I/O 없음 | 362ms | 0.6ms |
| 받는 stage의 OST에 쓰기 (수신 링크 공유) | 709ms (2.0배) | 0.4ms |
| 보내는 stage의 OST에서 읽기 (송신 링크 공유) | 1,473ms (4.1배) | 4.6ms |
| 둘 다 | 1,267ms (3.5배) | 3.0ms |

저장 I/O 처리량은 거의 줄지 않는다(읽기 111MB/s, 단독 115MB/s). 손해는 activation 쪽에 생긴다.

**시사점:** 원격에서 읽히는 객체를 activation을 보내는 stage의 OST에 두면 그 stage가 느려진다. NIC 방향별 점유를 비용 모델에 넣는다.

### 3.7 관찰 M7: 여러 흐름이 OSS 하나를 공유하면 합계가 그 OSS의 1GbE로 제한된다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m7-oss-sharing-dark.svg">
  <img alt="client 3개의 총 처리량: OSS 하나를 공유하면 읽기·쓰기 모두 120MB/s, 서로 다른 OSS로 나누면 읽기 303MB/s(2.5배), 쓰기 243MB/s(2.0배)" src="docs/figures/m7-oss-sharing-light.svg" width="620">
</picture>

| 조건 (client 3개, 30초, direct 4MiB) | 읽기 합계 | 쓰기 합계 |
|---|---|---|
| 세 흐름이 OST0001 하나를 공유 | 120MB/s (흐름별 76–92 / 14–21 / 17–21MB/s) | 120MB/s (흐름별 40MB/s) |
| 서로 다른 OSS로 분산 | 303MB/s (2.5배) | 243MB/s (2.0배) |
| 3-stripe 파일 + OST0001에 다른 흐름 2개 | 110.8MB/s (혼자 117.6MB/s, −6%) | 69.5MB/s (혼자 93.0MB/s, −25%) |

**시사점:** 원 IFLustre의 OSS 공유 간섭과 "가장 느린 OSS가 성능을 정한다"는 관찰이 엣지에서도 나타난다. 동시 흐름은 서로 다른 OSS로 나눈다.

### 3.8 관찰 M13: IoT 레코드를 파일 단위로 쓰면 MDS가 병목이고, pack에 붙이면 30배 빠르다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m13-ingest-pack-dark.svg">
  <img alt="IoT 레코드 수집 속도: 레코드당 파일 stripe 1 224 rec/s, stripe 3 217 rec/s, pack append 6,642 rec/s(30배), MDS 요청은 레코드당 2.0 대 0.0013" src="docs/figures/m13-ingest-pack-light.svg" width="620">
</picture>

| 방식 (jetson, 512B 레코드 3,000개) | 처리량 | 레코드(파일)당 MDS 요청 |
|---|---|---|
| 레코드당 파일, stripe count 1 / 3 | 224 / 217 rec/s | 2.0 |
| 256KiB 창 파일, stripe count 1 / 3 | 47 / 46MB/s | 2.0 |
| pack append (32개마다 fsync) | 6,642 rec/s (30배) | 0.0013 |

**시사점:** 원 IFLustre IoTJ의 소파일 관찰이 엣지에서도 나타난다. KV chunk와 수집 레코드는 pack 단위로 저장한다.

### 3.9 관찰 M12: 원격 KV는 사용 노드로 옮기면 이동 비용을 포함해도 세 번째 사용부터 이득이다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m12-relocation-dark.svg">
  <img alt="같은 KV를 5번 쓸 때 누적 시간: 매번 재계산 35.1초, 원격 유지 27.3초, 첫 사용 후 로컬 이동 14.8초" src="docs/figures/m12-relocation-light.svg" width="620">
</picture>

| 방식 (jetson1, 4k KV 576MiB, 5회 사용) | 1회째 | 2회째부터 (회당) | 5회 누적 |
|---|---|---|---|
| 매번 재계산 | 7.15초 | 약 6.98초 | 35.1초 |
| 원격 OST에서 복원 | 5.49초 | 약 5.46초 | 27.3초 |
| 첫 사용 후 로컬 OST로 이동 (`lfs migrate`) | 5.49초 + 이동 6.50초 | 약 0.70초 | 14.8초 |

**시사점:** IoTJ 버전의 read-aware relocation이 KV에서도 성립한다. 이동을 백그라운드로 하면 두 번째 사용부터 이득이다. 옮길 KV는 재사용 예측으로 고른다.

### 3.10 관찰 M11: 체크포인트 쓰기를 KV 복원과 겹치면 복원이 41% 느려지고, 시점을 미루면 2%로 줄어든다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m11-runtime-aware-dark.svg">
  <img alt="KV 복원 시간 중앙값: 체크포인트 없음 663ms, 동시 최대 속도 932ms, 100MB/s 제한 696ms(최대 5,378ms), 복원 사이로 지연 679ms" src="docs/figures/m11-runtime-aware-light.svg" width="620">
</picture>

| 조건 (jetson3, 576MiB KV 복원 10회, 같은 로컬 OST에 체크포인트) | 복원 중앙값 | 체크포인트 쓰기 속도 |
|---|---|---|
| 체크포인트 없음 | 663ms | – |
| 동시에 최대 속도로 쓰기 | 932ms (+41%) | 1,472MiB/s |
| 100MB/s로 제한 | 696ms (+5%, 최대 5,378ms) | 102MiB/s |
| 복원 사이로 미루기 | 679ms (+2%) | 45MiB/s |

**시사점:** 원 IFLustre의 runtime-aware allocation(기다릴지, 공유할지)이 엣지에서도 의미가 있다. 체크포인트 크기와 마감 시간으로 시점과 속도를 정한다.

### 3.11 관찰 M4: Lustre client 캐시가 8GB 메모리를 잠식하고 GPU 할당을 늦춘다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m4a-cache-memfree-dark.svg">
  <img alt="2GiB buffered 읽기 한 번 후 줄어든 여유 메모리: 기본 캐시 상한 2,162MiB, 캐시 상한 512MB 520MiB" src="docs/figures/m4a-cache-memfree-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m4b-cache-gpu-dark.svg">
  <img alt="Lustre 캐시 상태별 GPU 메모리 할당 시간: 4GiB 1,461/1,807/1,460ms, 5GiB 1,832/2,298/1,824ms (캐시 비움/가득/상한 512MB)" src="docs/figures/m4b-cache-gpu-light.svg" width="620">
</picture>

- client 캐시 기본 상한은 3,810MB(RAM의 1/2)이다. 2GiB buffered 읽기 1회 후 MemFree가 2,162MiB 줄고(상한 512MB이면 520MiB), `MemAvailable`은 105MiB만 줄어든다.
- 캐시가 찬 상태에서 GPU 4GiB / 5GiB 할당 시간이 24% / 25% 늘고, 가장 느린 256MiB 할당 지연이 2배가 된다. 상한 512MB이면 캐시가 빈 상태와 같다.

**시사점:** 8GB unified memory에서 캐시 상한은 필수이다. 메모리 압박은 MemFree와 회수 카운터로 측정한다.

### 3.12 관찰 M6: 엣지 LLM 플래너는 형식은 지키지만 내용 검증이 필요하다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m6-planner-dark.svg">
  <img alt="플래너 결정 시간: 새 프롬프트 21.4초(prefill 2.8초 + 생성 18.5초), 프롬프트 캐시 시 16.1초, 17.3초" src="docs/figures/m6-planner-light.svg" width="620">
</picture>

- jetson, llama.cpp, Qwen3-4B Q4_K_M(ctx 4096): 입력 1,653토큰 prefill 2.84초, 생성 약 15.4 tok/s, 결정 1회 16–21초, JSON 스키마 준수 3/3, 메모리 약 4.1GB이다.
- 조치 유형을 잘못 쓰는 경우가 있었다(예: `repartition` 대상에 컨텍스트 ID 지정).

**시사점:** 이벤트 단위 재계획에 쓸 수 있는 지연이다. 검증기와 조치별 입력 형식 제한이 필요하다.

### 3.13 관찰 M5·M8: 저장 I/O는 같은 노드의 LLM 연산을 3% 이내로만 늦춘다

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m5-oss-cpu-dark.svg">
  <img alt="원격 I/O를 처리하는 OSS 노드의 CPU: 유휴 0.8%, 원격 읽기 처리 13.0%, 원격 쓰기 처리 19.0%, softirq는 약 6%" src="docs/figures/m5-oss-cpu-light.svg" width="620">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/figures/m8-llm-under-io-dark.svg">
  <img alt="저장 I/O 중 LLM 속도(저장 I/O 없을 때 대비): 원격 읽기·쓰기 100%, 로컬 direct 읽기 99%, 로컬 direct 쓰기 99–100%, 로컬 buffered 읽기 prefill 99% decode 97%, 로컬 buffered 쓰기 100%" src="docs/figures/m8-llm-under-io-light.svg" width="620">
</picture>

| 측정 | 결과 |
|---|---|
| 원격 client의 I/O를 처리하는 OSS의 CPU (jetson3, M5) | 읽기 처리(114MB/s) 13.0%, 쓰기 처리(93MB/s) 19.0%. 그중 softirq 약 6% |
| 같은 노드 저장 I/O 중 LLM 속도 (jetson1, ctx 4096, M8) | 원격 읽기·쓰기, 로컬 direct·buffered 읽기·쓰기 6개 조건 모두 prefill·decode 감속 3% 이내. 가장 큰 감속은 로컬 buffered 읽기의 decode −2.9% |
| LLM 실행 중 같은 노드 저장 쓰기 (M8) | 로컬 direct 쓰기 714 → 559MB/s (−22%) |

P0의 OSS CPU 값(약 2%)은 fio가 파일을 다시 만들어 데이터가 다른 OST에 놓인 측정 오류였고, 노드 내부 샘플러로 다시 쟀다.

**시사점:** 이 장치와 런타임에서 저장 I/O는 LLM 연산을 거의 늦추지 않는다. 연산 감속은 대조 측정으로만 보고하고, 반대 방향의 쓰기 감속은 쓰기 시점 결정에 넣는다.

### 3.14 관찰 요약: 성능을 크게 바꾸는 것과 거의 바꾸지 않는 것

| 구분 | 요인 | 실측 | 관찰 |
|---|---|---|---|
| 크게 바꾸는 것 | KV 배치 정책 | TTFT p50 사용 노드 0.79초, Lustre 기본 6.2초, 부하 분산 16.0초 (p90 1.0 / 19.1 / 27.2초) | M14 |
| | 데이터·KV 위치 | 로컬 대 원격 OST 15–22배, 로컬 KV 복원 대 재계산 7–12배 | M2, M3 |
| | 노드 메모리 | 런타임 KV 캐시와 저장 계층 메모리의 합이 넘쳐 노드 정지 2회 | M4, M10 |
| | NIC 공유 | activation 전달 2–4배, decode 메시지 왕복 0.6 → 4.6ms | M9 |
| | OSS 공유 | 흐름 3개 공유 시 합계 120MB/s, 분산 시 243–303MB/s, 최악 흐름 14MB/s | M7 |
| | 수집 저장 단위 | pack이 레코드당 파일보다 30배 빠름, MDS 요청 1/1,500 | M13 |
| | 재배치 | 같은 KV 5회 사용 27.3초 → 14.8초 | M12 |
| | 쓰기 시점 | KV 복원 +41%(동시 체크포인트) 대 +2%(시점 지연) | M11 |
| 거의 바꾸지 않는 것 | 저장 I/O의 LLM 연산 감속 | prefill·decode 3% 이내 (원격·로컬, direct·buffered 모두) | M8 |
| | 원격 I/O를 처리하는 OSS의 CPU | CPU 13–19%를 쓰지만 같은 노드 LLM 감속은 거의 없음 | M5, M8 |
| | striping | stripe 1–3 차이 2% 이내 | M1 |

따라서 본 연구는 저장 I/O가 LLM 연산을 늦추는 문제가 아니라 데이터 위치, 공유 자원(OSS, NIC, 메모리), 쓰기 시점을 다룬다.

### 3.15 IFLustre 이점의 계승

CoStripe가 IFLustre의 확장이 되려면 원 IFLustre의 전제가 엣지에서도 성립해야 한다.

| 원 IFLustre 정책·관찰 | 엣지에서의 확인 | 관찰 |
|---|---|---|
| 소파일은 striping 효과가 없음 (IoTJ) | 레코드당 파일은 MDS 요청이 병목이고 stripe와 무관. pack이 30배 | M13 |
| Throughput-aware allocation (많은 OSS 사용) | 단일 client는 자기 NIC가 상한. stripe 1–3 차이 2% 이내 | M1 |
| Interference-free allocation (OSS 공유 회피) | 공유 시 합계 120MB/s, 분산 시 2–2.5배 | M7 |
| 가장 느린 OSS가 성능을 정함 | 붐비는 OST 하나가 3-stripe 쓰기를 25% 늦춤 | M7 |
| Runtime-aware allocation (대기 대 공유) | 체크포인트 동시 쓰기 +41%, 시점 지연 +2% | M11 |
| Read-aware relocation (IoTJ) | 원격 KV 5회 사용 27.3초 → 14.8초 | M12 |
| (확장) 간섭 범위 | NIC 공유 2–4배, 메모리 초과 시 노드 정지. 연산 감속은 3% 이내 | M5, M8, M9, M10 |
| (확장) 사용 노드 | 사용 노드 배치 TTFT p50 0.79초, 사용 노드를 보지 않는 부하 분산 16.0초 | M14 |

LLM이 없는 IoT 수집 워크로드에서 CoStripe가 IFLustre(B2)보다 나빠지지 않는지는 평가에서 확인한다.

### 3.16 관찰에서 설계로

| 관찰 | 설계 반영 | 위치 |
|---|---|---|
| M14 사용 노드 배치 TTFT p50 0.79초 대 부하 분산 16.0초 | 사용 노드를 아는 배치를 기본으로 하고, 부하 기반 할당은 그 위에서 예외 결정 | 4.9.4절 |
| M1 원격은 1GbE가 상한, striping 이득 없음 | stripe count 1 + 사용 노드 배치 | 4.8.1, 4.9.4절 |
| M2 로컬 15–22배, 로컬 I/O가 CPU 약 45% 사용 | 사용 노드 배치. CPU 사용은 CPU를 쓰는 작업과의 경쟁으로만 반영 | 4.8.1, 4.9.3절 |
| M3 로컬 KV 복원이 재계산보다 7–12배 빠름 | KV pack 로컬 배치, 재계산 대 읽기 판단, page cache 우회 | 4.8.2절 |
| M10 런타임 KV 캐시와 저장 계층 메모리가 8GB를 넘겨 노드 정지 | KV 계층과 저장 계층 메모리를 하나의 예산으로 관리, 런타임 캐시는 끄거나 예산에 포함 | 4.1.3, 4.8.4절 |
| M9 저장 I/O가 activation 전달을 2–4배 늦춤 | 원격에서 읽히는 객체를 activation을 보내는 stage의 OST에 두지 않음, NIC 방향별 점유 U_k | 4.8.4, 4.9.4절 |
| M7 OSS 공유 시 합계가 NIC 하나로 제한됨 | 동시 흐름을 서로 다른 OSS로 분산, OSS별 동시 흐름 수 n_j | 4.8.4, 4.9.3절 |
| M13 레코드당 파일은 MDS가 병목 | KV chunk와 수집 레코드를 pack 단위로 저장 | 4.8.2절 |
| M12 원격 KV는 이동 후 세 번째 사용부터 이득 | 재사용 예측 기반 migrate (read-aware relocation 계승) | 4.8.2절 |
| M11 체크포인트와 KV 복원이 겹치면 +41% | 백그라운드 쓰기의 시점 지연 (runtime-aware 계승) | 4.8.3, 4.8.4절 |
| M4 캐시가 메모리를 잠식하고 GPU 할당을 늦춤 | 캐시 상한 필수, 메모리 항을 비용 모델에 | 4.1.3, 4.9.3절 |
| M6 플래너는 형식만 신뢰 가능, 메모리 4.1GB | 검증기 필수, 플래너를 NM에 배치 | 4.8.5절 |
| M5·M8 연산 감속 3% 이내, LLM 실행 중 로컬 쓰기 −22% | β는 작은 항으로 두고 주장에서 제외. 쓰기 감속 γ를 쓰기 시점 결정에 | 4.8.4, 4.9.3절 |

---

## 4. Design

### 4.1 대상 환경

#### 4.1.1 노드와 역할

기존 Lustre(MGS/MDT 1개, OST 3개)를 다시 만들지 않는다. OST를 가진 세 노드에 client 마운트만 더해, 스토리지 서버가 LLM 연산 노드를 겸하는 구성(A')을 만든다.

| 노드 | 호스트 | Lustre 역할 | 연산 역할 |
|---|---|---|---|
| NM | jetson0 | MGS, MDS(MDT0000) | LLM 플래너(llama.cpp, Qwen3-4B Q4_K_M) |
| N1 | jetson1 | OSS(OST0000), client | stage 1 (LG0–3 + 임베딩), 수집 시점 prefill, 재생성 |
| N2 | jetson2 | OSS(OST0001), client | stage 2 (LG4–7), 수집 시점 prefill, 재생성 |
| N3 | jetson3 | OSS(OST0002), client | stage 3 (LG8–11 + head), LoRA 학습(LG9–11), 재생성 |
| N0 | jetson | client (NVMe 없음) | 제어 모듈, W1 수집, Context Builder, Prefill Scheduler, 압축기, 장애 시 대체 stage |

- 5대를 같은 1GbE 스위치에 연결한다. 연산 부하가 없는 OST는 없으므로 복제본은 이웃 stage 노드에 둔다(4.8.1절).
- NM이 플래너를 맡는다. MDS 메모리 사용이 약 120MiB로 작고, 플래너(약 4.1GB)는 이벤트 때만 실행되며, N0가 대체 stage를 맡아도 플래너를 내리지 않아도 된다. 플래너 실행 중 MDS 지연은 O4에서 확인한다.
- N0는 NVMe가 없어 OST를 둘 수 없으므로 서빙 stage에서 뺀다. 수집과 제어를 서빙과 분리하고, 장애 시 대체 stage가 된다.
- LoRA를 LG9–11에만 적용하므로 backward, 학습 상태, LG9 입력 경계 activation이 모두 N3 안에 생긴다.

#### 4.1.2 소프트웨어와 현재 구성

| 구성 | 내용 |
|---|---|
| OS, Lustre | JetPack 6.x (L4T R36.4.4, Ubuntu 22.04), Lustre 2.17.0 (ldiskfs). PFL, FLR, NRS TBF, jobstats, CPT 확인 |
| 서빙·학습 런타임 | PyTorch + HF transformers + PEFT 기반 자체 파이프라인 런타임 |
| KV 저장소 | CoStripe KV Store (Lustre 위 pack 파일 + 인덱스) |
| 플래너·비교 대상 | llama.cpp (CUDA), JSON schema 제약 디코딩 |
| 측정 | tegrastats, `lctl get_param`, `/proc`, fio, iperf3, 노드 내부 샘플러 |

- jetson1–3의 client는 비영구로 마운트하고 캐시 상한 512MB를 설정한다(`umount`로 원복). 5-OST 구성은 장치 추가와 MDT 재구축이 필요해 제외했다.
- 5대 모두 Orin Nano Super(25W), OS는 microSD, GUI 켜짐, zram 3.8GB이다. 서버의 MGS 연결이 무선 IP로 설정된 문제(F1)는 서버 재부팅, OST 추가, 영구 설정이 필요할 때 정정한다.
- 상세 구성과 실측은 `docs/testbed.md`, `docs/design_details.md` 1절에 있다.

#### 4.1.3 노드별 메모리 예산

가용 메모리 약 7.4GiB 기준의 추정이다. O4에서 측정해 갱신한다.

| 항목 | N1 (stage 1) | N2 (stage 2) | N3 (stage 3) | NM | N0 |
|---|---|---|---|---|---|
| OS (headless) + 서비스 | 0.6GB | 0.6GB | 0.6GB | 0.6GB | 0.6GB |
| CUDA + PyTorch 런타임 | 1.2GB | 1.2GB | 1.2GB | – | – |
| Lustre 서버 + client (캐시 제외) | 0.3GB | 0.3GB | 0.3GB | 0.5GB (MGS/MDS) | 0.3GB (client) |
| Lustre 캐시 상한 (설정값) | 0.5GB | 0.5GB | 0.5GB | – | 0.5GB |
| 모델 가중치 (FP16) | 3.2GB (LG 4개 + 임베딩) | 2.4GB (LG 4개) | 3.2GB (LG 4개 + head) | – | – |
| 적응 학습 (LoRA 상태 + 활성화) | – | – | 0.3GB | – | – |
| 플래너 (Qwen3-4B Q4_K_M, 실측) | – | – | – | 4.1GB | – |
| 수집, 컨텍스트 구성, 압축, 제어 모듈 | – | – | – | – | 0.8GB |
| 안전 마진 | 0.4GB | 0.4GB | 0.4GB | 0.6GB | 0.6GB |
| **KV 상주 가용 / 남는 메모리** | **KV 약 1.2GB** | **KV 약 2.0GB** | **KV 약 0.9GB** | 약 1.6GB | 약 4.6GB |

- 8k 컨텍스트 하나는 stage당 384MiB이므로 N1 약 3개, N2 약 5개, N3 약 2개를 상주시킬 수 있다. 8개 컨텍스트 중 대부분은 저장 계층에 있다.
- client 캐시 상한과 런타임 KV 캐시 비활성화(`--cache-ram 0`)는 필수 조건이다(M4, M10).

### 4.2 시나리오와 워크로드

공장 엣지 사이트에서 장비 이상 분석 LLM 서비스를 운영한다. 4개 생산 라인에서 라인마다 데이터 스트림 2개가 들어와 스트림 컨텍스트가 8개 있다. 운영자는 특정 스트림의 상태와 이상 원인을 자연어로 묻는다. 요청이 적은 시간대에 모델을 적응시키며, 데이터는 사이트 밖으로 반출하지 않는다.

| ID | 이름 | 내용 | 실행 위치 |
|---|---|---|---|
| W1 | Ingest | IoT 데이터를 저장하고 스트림별 레코드로 변환해 스트림 컨텍스트에 이어 붙인다. 일정량이 쌓이면 수집 시점 prefill 작업을 파이프라인에 넣는다. | 수집·변환: N0 / prefill: N1–N3 |
| W2 | Adapt | 학습 샘플로 상위 LG의 LoRA를 학습한다(forward는 전체, backward는 상위 LG만). 라운드가 끝나면 새 어댑터로 전환하고 상위 LG의 KV를 다시 만든다. | 샘플: N0 / 학습: N1–N3 (backward는 N3) |
| W3 | Serve | 스트림 컨텍스트의 KV를 주소로 찾아 읽고, 아직 prefill되지 않은 꼬리와 질문만 계산한다. | N1–N3 |

```
스트림 컨텍스트 (epoch e):
[시스템 지시문 ~300] [라인 매뉴얼 2k–4k] [스트림 헤더 ~50] [압축 요약 (e>0)] [레코드 r1 r2 r3 ...]

요청:
[스트림 컨텍스트 (현재까지)] [세션 이전 턴 (있으면)] [질문 30–100]  →  출력 128–256
```

| 항목 | 값 |
|---|---|
| 레코드 | 한 줄 텍스트, 예: `10:01:20 P2 vib=3.2 T=61 a=0.12` (약 20토큰). 스트림당 10초에 1개 → 시간당 약 7.2k 토큰 |
| 컨텍스트 한계 | 기본 8k 토큰, 민감도 16k. 한계에 도달하면 압축 |
| 세션 | 1–5턴, 턴 간격 30초–10분. 스트림 컨텍스트에서 갈라지는 별도 체인 |

같은 라인의 두 스트림 컨텍스트는 `[지시문][매뉴얼]`이 같으므로 그 KV 객체를 공유한다.

### 4.3 모델 선정

목표 정밀도에서 노드 1대에 가중치와 KV가 함께 들어가지 않고, 3대로 나누면 노드당 7.4GiB 안에 들어가며, base를 공유한 LoRA 학습이 가능한 GQA 공개 모델을 고른다. 선정 기준, 학습 설정, 선택하지 않은 대안은 `docs/design_details.md` 2절에 있다.

| 역할 | 모델 | 정밀도 | 크기 | 실행 노드 |
|---|---|---|---|---|
| 서빙(W3), 수집 시점 prefill(W1) | Qwen3-4B | FP16 | 약 8.0GB | N1–N3 (stage당 LG 4개) |
| 적응 학습(W2) | Qwen3-4B + LoRA (LG9–11, rank 16, q/k/v/o) | FP16 base 공유, LoRA FP32 | N3 추가 약 0.3GB | N1–N3 (backward는 N3) |
| 플래너 | Qwen3-4B (비교: 1.7B, 0.6B) | Q4_K_M (비교: Q8_0) | 실행 시 약 4.1GB | NM (llama.cpp) |
| 비교 대상 B7 | Qwen3-4B | Q4_K_M | 약 2.5GB | N1–N3 각각 (복제 서빙) |
| 민감도 | Qwen3-8B Q8_0 (llama.cpp RPC), Qwen3-1.7B FP16 | – | 약 8.7GB / 3.4GB | N1–N3 |

36 layer를 3개씩 묶어 LG 12개(LG당 약 0.6GB)를 만든다. 임베딩(약 0.78GB)은 입력과 출력 head가 공유하므로 stage 1과 3에 둔다. 초기 분할은 `{N1: LG0–3 + 임베딩, N2: LG4–7, N3: LG8–11 + head}`이다.

### 4.4 데이터 객체와 I/O 특성

기본 구성(Qwen3-4B FP16, chunk 256토큰, 컨텍스트 한계 8k) 기준이다. 계산식은 부록 A, 경로 규격은 `docs/design_details.md` 8절에 있다.

| 객체 | 식별 | 단위 크기 | 생성 | 사용 노드 | 접근 패턴 |
|---|---|---|---|---|---|
| 가중치 | 모델 버전 + LG | LG당 약 0.6GB | 사전 배치 | 해당 LG stage | 시작·재분할·복구 시 읽기 |
| 임베딩 | 모델 버전 | 약 0.78GB | 사전 배치 | stage 1, 3 | 로드 시 읽기 |
| KV chunk (공유 prefix) | 내용 주소 | LG당 3MiB/chunk | 첫 컨텍스트의 수집 시점 prefill | 같은 라인의 모든 컨텍스트 | 요청·prefill 시 읽기 |
| KV chunk (스트림 로그) | 내용 주소 | LG당 3MiB/chunk | 수집 시점 prefill | 해당 스트림 요청 | append 후 봉인, 읽기 |
| KV pack | (컨텍스트, LG, epoch, 순번) | 32 chunk, LG당 96MiB | KV Store | – | 봉인 후 수정 없음, 복제 |
| 경계 activation | 내용 주소 (LG9 입력) | chunk당 1.25MiB | N3 (LG8 출력) | N3 (재생성 시) | 로컬 쓰기, 로컬 읽기 |
| 세션 KV | 내용 주소 (컨텍스트 체인에서 분기) | 턴당 수 MiB | stage | 같은 세션 | 단기 보존 |
| 체크포인트 | (라운드, step, LG) | LG당 약 12MB (rank 16) | N3 | N3, 장애 시 N0 | 로컬 쓰기 + 다른 stage로 지연 복제 |
| 어댑터 | (버전, LG) | LG당 약 2MB | N3 | N3 | 라운드 종료 시 확정, 세 stage에 복제 |
| IoT 원본, 레코드 로그 | 경로 | 수백 B–4GB | N0 (stage 노드 OST에 저장) | N0 | 연속 쓰기 |

컨텍스트 KV는 8k 기준 컨텍스트당 1.125GiB(stage당 384MiB)이다. 8개 합계는 stage당 약 3GiB, 클러스터 전체 약 9GiB이며 16k 한계에서는 두 배이다.

### 4.5 문제 정의

#### 4.5.1 문제 서술

하이퍼컨버지드 엣지 DFS에서 W1–W3가 동시에 실행될 때 다음을 결정한다.

| 기호 | 결정 대상 |
|---|---|
| P | LG를 서빙 노드에 배정하는 파이프라인 분할 (장애 시 대체 분할 포함) |
| M | 각 객체(가중치, KV pack, 경계 activation, 체크포인트, 어댑터)의 OST, stripe, mirror 위치 |
| R | stage별 메모리 상주 컨텍스트 집합 |
| S | 백그라운드 작업의 시점과 속도 (수집 시점 prefill 배치 간격, 압축, KV 재생성, 체크포인트 복제, 재배치, 적응 시간대) |

결정의 핵심은 세 가지이다. 각 객체를 사용 노드 기준으로 어디에 둘지, 각 I/O 흐름과 pipeline 전달이 어떤 OSS·NIC·메모리를 거치게 할지, 백그라운드 쓰기를 언제 할지이다. 목표는 서빙 SLO(TTFT p99, TPOT p99)를 지키면서 처리량을 최대화하고, 데이터 최신성, 적응 라운드 완료 시간, 장애 복구 시간을 정책 상한 안에 두는 것이다.

#### 4.5.2 정식화

```
maximize    Throughput(P, M, R, S) = 1 / max_k T_k

subject to  TTFT_p99            <= SLO_TTFT
            TPOT_p99            <= SLO_TPOT
            mem_k(P, R, S)      <= MemCap_k − margin        for all k  (런타임 KV 캐시, client 캐시, OSS·RPC 메모리 포함. 넘으면 노드 정지)
            used_j(M)           <= OstCap_j                 for all OSTs j
            freshness_lag(S)    <= LagMax                   (미처리 레코드 시간)
            ckpt_interval(S)    <= CkptMax
            recover_time(P', M) <= RecoverMax               for all single-node failures
            P는 연속 분할
```

T_k와 mem_k의 정의는 4.9.3절에 있다.

#### 4.5.3 문제가 성립하는 이유

네 조건이 함께 성립한다. 모델이 노드 1대에 들어가지 않아 분할이 필요하다. 스트림 컨텍스트의 KV가 메모리보다 크고 여러 요청이 공유하므로 공유 저장이 필요하다. 엣지에는 별도 스토리지 계층이 없어 저장 서버와 연산 노드가 같다. 적응 학습이 모델 버전을 바꿔 저장 KV의 유효성 관리가 필요하다.

Orin Nano에서는 세 가지가 문제를 키운다. 메모리가 작아 캐시와 런타임 KV 캐시가 연산 메모리를 직접 줄이고, 합이 넘치면 노드가 멈춘다(M10). 1GbE라서 위치에 따른 접근 시간 차이가 10배 이상이고, OSS 하나를 공유하는 흐름들이 그 OSS의 1GbE를 나눠 쓴다(M7). 스토리지 서버와 stage가 NIC 하나를 나눠 써서 OSS의 원격 읽기가 그 stage의 activation 전달을 4배 늦춘다(M9). 반면 GPU 중심 추론은 같은 노드의 저장 I/O에 거의 영향을 받지 않는다(M8). 문제의 원인은 연산 경쟁이 아니라 위치와 공유 자원이다.

### 4.6 문제를 어렵게 만드는 요인

| ID | 요인 | 설명 |
|---|---|---|
| D1 | 저장-연산 결합 | OST가 연산 노드에 있어, I/O를 어디로 보내는지가 그 노드의 NIC·메모리 부하를 정한다. 연산 감속은 작지만(3% 이내) activation 지연(2–4배)과 메모리 초과(노드 정지)는 크다. |
| D2 | 메모리 용량 경쟁 | 가중치, 상주 KV, 런타임(호스트 RAM KV 캐시 포함), client 캐시, OSS·RPC 메모리, 학습 상태가 7.4GiB 안에서 경쟁하고, 각자 자기 상한만 지킨다(M10). |
| D3 | 파이프라인 병목 | 가장 느린 stage가 처리량과 TTFT를 정한다. |
| D4 | 1GbE 네트워크 | 원격 접근이 10배 이상 느리고, activation·원격 KV·복제가 같은 NIC를 쓴다(M9). |
| D5 | P, M, R의 상호 의존 | P가 바뀌면 객체의 사용 노드가 바뀌고 M과 R의 최적값도 바뀐다. |
| D6 | I/O 클래스 간 충돌 | 요청 시점 KV 읽기(지연 민감)와 수집 시점 prefill, 체크포인트 복제, 재생성, 압축(버스트)이 같은 OST·NIC·메모리를 쓴다(M11). |
| D7 | 스트림 KV의 증가와 수명 | 스트림 KV는 계속 늘고, 압축으로 epoch가 바뀌며, 어댑터 버전으로 상위 LG KV가 무효가 된다. |
| D8 | 수집 시점 prefill의 읽기 증폭 | 새 chunk를 계산하려면 그 컨텍스트의 이전 KV가 메모리에 있어야 하므로, 상주하지 않은 컨텍스트는 매번 KV를 읽는다. |
| D9 | 시간에 따른 변화 | 적응 라운드, 장애, 부하 변화, 정책 변경이 일어나고, 새 객체에는 이력이 없다. |
| D10 | OSS 공유 | 동시 흐름이 같은 OSS에 몰리면 합계가 그 OSS의 1GbE로 제한되고 흐름별 몫이 고르지 않다(M7: 최악 흐름 14MB/s). |

### 4.7 연구 질문

| ID | 질문 | 공백 | 실험 |
|---|---|---|---|
| RQ1 | 하이퍼컨버지드 엣지 클러스터에서 데이터 위치와 공유 자원(OSS, NIC, 노드 메모리)은 LLM 서빙 성능을 얼마나, 어떤 경로로 바꾸는가? 저장 I/O의 연산 감속은 그에 비해 얼마인가? | G1 | O1–O4 |
| RQ2 | 파이프라인 분할(P)과 데이터 배치(M, R)를 함께 결정하면 각각 결정할 때보다 서빙 성능과 복구 시간이 얼마나 개선되는가? | G2 | O4, O6, S2, S5 |
| RQ3 | 이어 쓰기 컨텍스트, 수집 시점 prefill, content-addressed KV 저장은 요청 시점 prefix 재사용 대비 TTFT를 얼마나 줄이며, 그 비용(저장 용량, 수집 시점 I/O, 압축·재생성)은 얼마인가? | G3 | O7, S2, S7 |
| RQ4 | 적응 학습과 KV 재생성의 I/O를 어떻게 제어해야 서빙 SLO를 지키면서 라운드를 제시간에 끝낼 수 있는가? | G4 | O5, S3, S4, S7 |
| RQ5 | 이벤트 발생 시 LLM 플래너와 검증기로 재계획하면 규칙·탐색 기반 대비 결과 품질, 정책 준수, 결정 비용이 어떻게 다른가? | G5 | S1, S6 |

### 4.8 해결 요소

해결 요소는 다섯 가지이며, 번호(②③⑤⑦⑧)는 기존 논의의 번호를 유지한다. 서술은 의존 관계 순서(⑧ → ② → ⑤ → ③ → ⑦)를 따른다. 각 요소의 세부 문제, 전체 절차, 검증 방법, 관련 연구와의 차이는 `docs/design_details.md` 3절에 있다.

| 번호 | 해결 요소 | 대응 요인 | 대응 RQ |
|---|---|---|---|
| ⑧ | 분산 추론의 분할과 가중치 배치 | D1, D3, D4, D5 | RQ2 |
| ② | semantic-aware content-addressed KV 저장소 | D2, D4, D6, D7, D8 | RQ2, RQ3 |
| ⑤ | 적응 학습과 KV 유효성 | D6, D7, D9 | RQ4 |
| ③ | 공유 자원 간섭(OSS·NIC·메모리) 측정과 완화 | D1, D2, D3, D4, D6, D10 | RQ1 |
| ⑦ | 이벤트 기반 재계획 (LLM 플래너) | D5, D9 | RQ5 |

#### 4.8.1 ⑧ 분산 추론의 분할과 가중치 배치

**문제**
- FP16 약 8.0GB는 노드 1대(7.4GiB)에 들어가지 않는다.
- stage 가중치(2.4–3.2GB)를 원격으로 읽으면 약 21–28초가 걸린다. 기본 레이아웃은 LG 파일을 OST 전체에 흩어 원격 읽기를 만든다.
- 노드 장애 시 연산과 OST가 함께 사라진다. 연산 부하가 없는 OST가 없어 복제본도 다른 stage 노드에 둔다.
- 분할과 배치는 따로 정할 수 없다(D5).

**방법**
1. 가중치를 LG 단위 파일(약 0.6GB)로 저장하고 사용 노드 OST에 둔다. stripe count는 1로 고정한다(M1).
2. 임베딩은 stage 1 OST에 두고 stage 3 OST에 mirror를 둔다.
3. stage k의 가중치는 다음 stage 노드 OST에 FLR mirror를 둔다(N1 → N2 → N3 → N1). mirror 생성은 저부하 시점에 TBF로 속도를 제한한다.
4. 장애 시 기본 대체 분할 P'_k는 N0가 장애 노드의 LG 구간을 맡고 이웃 mirror에서 읽는 것이다(약 21–28초). 2-stage 재분할은 FP16에서 노드당 약 4.4GB라 INT8 weight-only일 때만 쓴다.
5. 분할 후보 55개(C(11,2))를 비용 모델로 전수 평가한다. 재분할 시 바뀐 LG만 옮기고, 새 담당 노드는 mirror에서 먼저 읽은 뒤 저부하 구간에 `lfs migrate`한다.

**IFLustre와의 관계:** 시작 OST 지정을 그대로 쓰고, 할당 기준을 사용 노드와 공유 자원으로 넓힌다.

#### 4.8.2 ② Semantic-aware content-addressed KV 저장소

스트림 단위로 뒤에만 이어 쓰는 컨텍스트를 유지하고, 그 KV를 데이터 수집 시점에 미리 계산해 내용 주소로 식별되는 객체로 저장한다. 요청은 KV를 주소로 찾아 읽고, 아직 계산되지 않은 꼬리와 질문만 prefill한다.

| 구분 | 결정 근거 | 예 |
|---|---|---|
| 이름 (식별) | 내용 | 토큰 체인 해시, 모델 버전, 해당 LG에 영향을 주는 어댑터 버전, LG 번호 |
| 위치 (배치) | 비용 모델 (4.9.3절) | OST, mirror 여부, 메모리 상주 여부 |
| 정책 | IoT 의미 정보 | 스트림·라인(묶음, 우선순위), 시간(보존, 압축), 이상 여부(원문 유지), 접근 패턴(미리 읽기) |

이름이 위치와 독립이므로 객체를 옮기거나 복제해도 이름과 유효성이 바뀌지 않는다. 의미 정보는 이름에 들어가지 않으므로 정책을 바꿔도 객체를 다시 만들 필요가 없다.

**문제**
- 슬라이딩 윈도우에서 prefix 재사용이 깨져 기록 구간을 요청마다 다시 계산한다(2.4.1절).
- 8k 토큰 prefill은 3-stage에서 수 초에서 10초 이상 걸린다(추정). 로컬에서 stage KV 384MiB를 읽는 데는 약 0.15–0.3초이다(M3).
- 8개 컨텍스트 × 8k이면 stage당 약 3GiB로 상주 가용량(0.9–2.0GB)을 넘는다.
- 여러 요청이 같은 내용을 공유하고, 어댑터 버전이 KV 유효성을 바꾼다.
- KV I/O도 OSS·NIC·메모리를 쓴다. 원격에서 읽히는 KV는 그 노드의 송신 링크를 써서 activation 전달과 경쟁한다(M9).

**방법**
1. **주소.** LG0–8 주소에는 어댑터 버전이 들어가지 않으므로 적응 라운드가 지나도 유효하다. 체인 해시로 같은 앞부분을 가진 컨텍스트끼리 chunk를 공유한다.

   ```
   chain_0  = H(model_id ‖ tokenizer_id)
   chain_n  = H(chain_{n-1} ‖ tokens(chunk_n))
   key(i,n) = H(model_id ‖ adapter_scope_version(i) ‖ LG_i ‖ chain_n)
   ```
2. **컨텍스트 구성.** 레코드를 따로 토큰화해 이어 붙이고(결정성), 256토큰마다 chunk 경계를 고정한다. 가득 찬 chunk만 봉인하고 덜 찬 꼬리는 요청 시 prefill한다.
3. **수집 시점 prefill.** N0의 Prefill Scheduler가 배치 간격(기본 5분)마다 낮은 우선순위 작업으로 넣는다. 배치 간격은 읽기 증폭, 데이터 최신성, 연산 여유로 정한다.
4. **pack.** (컨텍스트, LG, epoch)의 chunk를 pack 파일(32 chunk, LG당 96MiB)에 이어 쓰고 봉인한다. 위치는 경로·오프셋 계산으로 찾고 헤더의 주소로 검증한다. 공유 prefix는 작은 전역 인덱스로 찾는다(M13).
5. **배치와 복제.** LG i의 pack은 사용 노드 OST에 둔다. 공유 prefix pack은 이웃 stage에 mirror하고, 봉인된 스트림 pack의 복제는 의미 정보(라인 우선순위, 이상 구간)로 정한다.
6. **상주와 미리 읽기.** TTFT는 상주하지 않은 stage의 읽기 시간이 정하므로, stage들이 같은 컨텍스트를 함께 상주시키도록 조정한다(기준은 상주 공간이 가장 작은 N3). 교대 시각 같은 정책 정보로 미리 읽는다.
7. **압축.** 한계에 도달하면 오래된 정상 레코드는 구간 통계로 요약하고 경고·이상 레코드는 원문을 유지한다. 공유 prefix KV는 재사용하고 요약 이후만 다시 계산한다.
8. **부분 재생성.** LG9 입력 activation(토큰당 5KiB)을 함께 저장해, 어댑터가 바뀌면 LG9–11 KV만 다시 계산한다(연산 약 75% 감소, 저장 비용은 KV의 약 3.5%).
9. **수거와 읽기 경로.** 현재 epoch, 사용 중인 어댑터, 열린 세션이 참조하는 객체만 유지한다. chunk별로 읽기와 재계산 중 빠른 쪽을 고르고, 읽은 데이터는 page cache에서 해제한다(M3, M4).

**IFLustre와의 관계:** 소파일 관찰을 pack 설계로, read-aware relocation을 재사용 예측 기반 migrate와 미리 읽기로 넓힌다(M12, M13).

#### 4.8.3 ⑤ 적응 학습과 KV 유효성

**문제**
- IoT 데이터 분포가 바뀌므로 엣지 안에서 주기적으로 적응해야 하고, 8GB 노드 1대로는 학습할 수 없다.
- 어댑터가 바뀌면 그 이후 layer의 KV가 무효가 된다. 전체 layer에 LoRA를 적용하면 매 라운드 모든 컨텍스트를 다시 계산한다.
- 체크포인트를 생성 노드(N3)에만 두면 N3 장애 시 함께 사라진다. 복제는 1GbE와 받는 노드의 서빙과 경쟁한다.
- 학습 연산과 메모리가 출력 head도 맡는 N3에 몰린다.

**방법**
1. LoRA 범위는 LG9–11을 기본으로 하고 LG6–11, 전체와 비교한다.
2. 체크포인트는 3단계로 한다: N3 메모리 스냅샷(rank 16 기준 약 35MB) → 로컬 OST 쓰기 → N1 또는 N2로 지연 복제(`lfs mirror extend`, TBF). 복제 시점은 KV 복원과 겹치지 않게 정한다(M11).
3. 적응 시간대와 학습 비율은 플래너가 요청률 예측과 정책으로 정한다. 서빙 요청이 우선이다.
4. 라운드가 끝나면 어댑터를 확정해 세 stage에 mirror하고, 재생성이 끝난 컨텍스트부터 새 버전으로 서빙한다. 한 요청 안에서는 LG9–11 전체가 같은 버전을 쓴다.
5. KV 재생성은 저부하 구간에 요청이 많은 스트림부터 실행한다.

**IFLustre와의 관계:** runtime-aware allocation을 체크포인트·복제·재생성 I/O의 시점과 속도 제어로 넓힌다.

#### 4.8.4 ③ 공유 자원 간섭(OSS·NIC·메모리) 측정과 완화

하이퍼컨버지드 노드에서 여러 I/O 흐름과 pipeline 전달이 공유 자원을 나눠 쓰면서 생기는 지연과 실패이다. 원 IFLustre의 OSS 공유 간섭을 NIC와 노드 메모리로 넓힌 것이다.

| 경로 | 내용 | 실측 크기 |
|---|---|---|
| OSS 공유 | 동시 흐름이 같은 OSS에 몰리면 합계가 그 OSS의 1GbE로 제한된다. 여러 OST에 걸친 파일은 가장 붐비는 OST가 속도를 정한다. | 공유 시 합계 120MB/s, 분산 시 243–303MB/s, 최악 흐름 14MB/s, 3-stripe 쓰기 −25% (M7) |
| NIC 공유 | stage 노드의 OSS가 처리하는 원격 I/O가 같은 NIC의 activation 전달과 경쟁한다. 원격 읽기는 송신 방향, 원격 쓰기는 수신 방향을 쓴다. | activation 전달 2.0배(수신), 4.1배(송신). decode 메시지 왕복 0.6 → 4.6ms (M9) |
| 노드 메모리 | 가중치, 상주 KV, 런타임 호스트 RAM KV 캐시, client 캐시, OSS·RPC 메모리가 8GB를 나눠 쓰며 각자 자기 상한만 지킨다. | GPU 할당 +25% (M4). 런타임 캐시가 요청마다 약 300–370MB 증가, 노드 정지 2회 (M10) |
| 쓰기 시점 | 체크포인트·복제·수집 쓰기가 같은 OST의 지연 민감 읽기와 겹친다. LLM 실행 중에는 같은 노드 쓰기도 느려진다. | KV 복원 +41%(동시) 대 +2%(지연) (M11). 로컬 direct 쓰기 −22% (M8) |
| 연산 (대조) | 저장 I/O가 CPU·메모리 대역폭을 써서 같은 노드 LLM을 늦춘다. | prefill·decode 3% 이내. OSS가 CPU 13–19%를 써도 LLM 감속은 거의 없음 (M5, M8) |

**문제**
- 모든 OST가 서빙 stage 노드에 있어, 객체를 어느 OST에 두는지가 그 stage의 NIC와 메모리 사용을 정한다.
- 차이가 몇 배 단위이고(OSS 2–2.5배, NIC 2–4배, 배치 정책별 TTFT p50 8–20배), 메모리 초과는 성능 저하가 아니라 노드 정지이다.
- 수집 시점 prefill, 재생성, 압축, 복제가 흐름을 늘리고, 파이프라인이 한 stage의 지연을 전체로 전파한다.

**방법**
1. **측정.** O2에서 OSS 공유, NIC 공유, 메모리를 재고, 연산 감속은 대조로 기록한다.
2. **OSS 분산.** 동시 흐름을 서로 다른 OSS로 나누고, OSS별 동시 흐름 수 n_j를 비용 모델에 넣는다.
3. **NIC 인지 배치.** 원격에서 읽히는 객체(공유 prefix pack, mirror, 대체 stage용 가중치)는 activation을 보내는 stage의 OST에 두지 않는다. mirror·복제·재배치는 해당 hop의 NIC가 한가할 때 하고, stage 노드 OST에 대한 원격 읽기는 NRS TBF로 제한한다.
4. **메모리 예산.** CoStripe가 KV 계층(GPU, 호스트 RAM, 로컬 OST, 원격 OST)의 위치를 정하고, 런타임의 호스트 RAM KV 캐시는 끄거나(`--cache-ram 0`) 예산 안으로 제한한다. client 캐시 상한, OSS·RPC 여유분, 보호 기준(MemAvailable 하한)을 노드 예산(4.1.3절)에 넣는다. KV 읽기는 page cache를 거치지 않는다.
5. **쓰기 시점.** 백그라운드 쓰기는 같은 OST의 지연 민감 읽기와 겹치지 않게 미루고, 필요하면 TBF로 제한한다. LLM 실행 중 쓰기 감속을 완료 시간 추정에 넣는다.
6. **보호.** MemAvailable 하한 아래에서는 백그라운드 작업부터 멈춘다.

**IFLustre와의 관계:** 원 IFLustre의 간섭(OSS를 공유하는 흐름)을 같은 NIC를 쓰는 저장 I/O와 activation, 같은 노드 메모리를 쓰는 런타임과 저장 계층으로 넓힌다. "성능은 가장 느린 OSS가 정한다"는 관찰은 "TTFT는 가장 느린 stage가 정하고, stage의 전달 시간과 상주 KV는 그 노드의 OSS가 처리하는 I/O와 메모리 사용에 영향을 받는다"로 확장된다.

#### 4.8.5 ⑦ 이벤트 기반 재계획 (LLM 플래너)

이벤트가 생기면 현재 상태와 운영 정책을 입력받아 (P, M, R, S) 변경안을 만들고, 비용 모델 기반 검증기가 검사한 뒤 적용한다. 플래너는 NM에서 llama.cpp로 실행한다.

**문제**
- 적응 라운드, 장애, 부하 변화, 정책 변경, 압축마다 결정을 다시 해야 하고, 새 어댑터·epoch에는 이력이 없다.
- 운영 정책은 자연어이고 스트림·시간 의미와 직결된다(예: "라인 3 우선", "교대 시작 10분 전 해당 라인 미리 준비", "점검 중인 스트림은 수집 시점 prefill 중단").
- 탐색 공간 밖의 조치(시간대 기반 미리 읽기, 적응 시간대 조정, 정비 일정에 맞춘 사전 재분할)가 있다.

**범위:** 분할 후보는 55개라 탐색으로 푼다. 플래너는 정책을 목적·제약으로 바꾸고, 이벤트별 변경 범위를 정하고, 탐색 밖의 조치를 제안한다. 수치 타당성은 검증기가 보장한다. 장애는 미리 계산한 대체 분할을 규칙으로 즉시 적용한다.

**방법**
1. **입력.** JSON 상태 요약(1–2k 토큰), 운영 정책, 스트림 의미 속성, 관찰 규칙 요약. 정적 부분은 prompt cache로 재사용한다.
2. **출력.** JSON 스키마로 제한한 조치 목록(분할, 레이아웃, migrate, mirror, TBF, 캐시 상한, 상주, 미리 읽기, prefill 배치 간격, 압축·재생성·복제 일정, 적응 시간대, 목적 가중치 등 16종).
3. **propose-verify.** 후보 1–3개 생성 → 검증기가 제약과 비용 모델로 검사 → 통과한 최선 후보 적용 → 실패 시 사유를 넣어 최대 2회 재요청 → 그래도 실패하면 규칙 정책.
4. **호출.** 이벤트 때만 호출하고 10초 안의 이벤트는 모은다. 결정 지연은 16–21초이다(M6).
5. **가용성.** 플래너는 NM에서 실행하므로 N0가 대체 stage를 맡아도 동작한다. 플래너 실행 중 MDS 지연은 O4에서 측정한다.

**IFLustre와의 관계:** Application Analyzer를 비용 모델(수치 예측)과 플래너·검증기(결정)로 나눈다.

### 4.9 통합 구성

#### 4.9.1 하나의 시스템이어야 하는 이유

1. **같은 라이프사이클.** W1 데이터가 컨텍스트와 KV가 되고(②), 그 KV로 서빙하며(⑧), 학습(⑤)이 어댑터를 바꿔 KV 재생성을 요구하고, 서빙 로그가 다시 W1 데이터가 된다.
2. **같은 메모리.** 가중치(⑧), 상주 KV(②), 학습 상태(⑤), 런타임 KV 캐시와 저장 계층 메모리(③)가 한 노드의 7.4GiB에서 경쟁한다(M10).
3. **같은 공유 자원.** 가중치·KV·체크포인트·재생성 I/O와 pipeline activation이 같은 OSS와 NIC를 쓴다(③, M7, M9).
4. **같은 단위.** 가중치, KV, 경계 activation, 어댑터, 체크포인트가 모두 LG 단위이므로 분할 P 하나가 모든 객체의 사용 노드를 정한다.
5. **같은 이름 체계.** 모든 KV·activation 객체가 내용 주소로 식별되어 재분할, 복제, 장애 대응이 위치 변경만으로 처리된다.
6. **같은 비용 모델.** 모든 결정이 하나의 식(4.9.3절)의 서로 다른 항을 바꾸고, ⑦이 이벤트마다 결정을 갱신한다.

#### 4.9.2 의존 관계

```
                   ③ 공유 자원 간섭 측정 (OSS·NIC·메모리)
                                  │ n_j (OSS별 동시 흐름), U_k (NIC 방향별 점유), mem_k 항, β (작음)
                                  ▼
 ┌───────────────────────── 비용 모델 T_k, mem_k ──────────────────────────┐
 │                                                                          │
 │  ⑧ 분할 P ──▶ 모든 LG 객체의 사용 노드·대체 노드                           │
 │      │                 │                            │                   │
 │      ▼                 ▼                            ▼                   │
 │  가중치 배치      ② content-addressed KV 저장소    ⑤ 적응 학습             │
 │  이웃 stage mirror 이름=내용, 위치=비용 모델,         LoRA 범위 → KV 유효성    │
 │                   정책=IoT 의미                     체크포인트·재생성 I/O    │
 │                   (수집 시점 prefill, 상주, 압축)                          │
 └──────────────────────────────────┬───────────────────────────────────────┘
                                    │ L_k, U_k, 이벤트
                                    ▼
                    ⑦ 이벤트 발생 시 (P, M, R, S) 재결정
```

| 요소 | 다른 요소에 제공 | 다른 요소에서 받음 |
|---|---|---|
| ③ | OSS별 동시 흐름 한계, NIC 방향별 점유 함수, 메모리 예산 항, β(작음) | 측정 대상 I/O 패턴 |
| ⑧ | P, 대체 분할, 가중치 로드 부하 | NIC·메모리 항, 재분할 지시 |
| ② | 수집 시점·요청 시점 KV I/O, 상주 메모리, TTFT, 최신성 | P, OSS·NIC·메모리 항, 어댑터 범위(⑤), 상주·배치 간격·압축 지시(⑦) |
| ⑤ | 학습 연산·메모리(N3), 체크포인트·재생성 I/O, 새 어댑터 이벤트 | P, OSS·NIC 항, 쓰기 감속 γ, 시점·속도 지시 |
| ⑦ | (P, M, R, S) 갱신 | 전 요소의 상태, 운영 정책, 스트림 의미 정보 |

#### 4.9.3 비용 모델

```
T_k    = C_k(P, S) · (1 + β_k(L_k)) + A_k(P, U_k^tx, U_k^rx) + F_k(M, R, n, U)

Throughput  = 1 / max_k T_k
TTFT(e)     = max_k load_k(e) + tail_prefill(e) + Σ_k A_k
              load_k(e)   : stage k에서 컨텍스트 e가 상주하지 않으면 KV 읽기 시간, 상주하면 0
              tail_prefill: 아직 수집 시점 prefill되지 않은 레코드 + 질문의 prefill 시간
mem_k  = W_k(P) + KV_k(R) + RT_k + cache_k(limit_k) + OSS_k(L_k) + Train_k(S)  ≤  MemCap_k − margin
U_k^tx = (activation 송신 + 이 노드 OST에서 원격으로 읽히는 양 + 복제·재배치 송신) / NIC 대역폭
U_k^rx = (activation 수신 + 이 노드 OST에 원격으로 쓰이는 양 + 원격 KV·가중치 읽기 + 복제 수신) / NIC 대역폭
n_j    = OSS j를 동시에 쓰는 흐름 수.  흐름별 대역폭 ≈ min(흐름 요구량, OSS j의 NIC 대역폭 / n_j)
L_k    = 서빙 KV 읽기 + 수집 시점 prefill의 컨텍스트 읽기·KV 쓰기 + 재생성 + 압축 + 체크포인트 + 수집 + 재배치
C_k    = 서빙 연산 + 수집 시점 prefill 연산 + 재생성 연산 + 학습 연산 (S가 시점과 비율을 정함)
D_w    = 백그라운드 쓰기 w의 완료 시간 = 쓰기량 / (대상 OST 쓰기 대역폭 · (1 − γ_k))
```

| 기호 | 의미 | 측정·계산 |
|---|---|---|
| C_k | stage k 연산 시간 | LG별 연산 프로파일(prefill, decode, 학습) 합산, 마지막 stage는 head 추가 |
| β_k | 저장 I/O에 따른 연산 감속 | 실측 3% 이내(M8). 작은 항으로 두고, CPU를 쓰는 작업(수집, 토큰화, 압축)에만 의미가 있다 |
| A_k | activation 전달 시간 | 전달량 / (NIC 대역폭 − 같은 방향 저장 트래픽). 송신 방향 공유가 더 크다(M9) |
| F_k | 연산과 겹치지 않는 KV 읽기 대기 | 경로(로컬/원격), OSS 동시 흐름 n_j, NIC 점유 (M2, M7) |
| n_j | OSS j의 동시 흐름 수 | 흐름 3개 공유 시 합계 120MB/s, 흐름별 몫이 고르지 않음 (M7) |
| RT_k | 런타임 메모리 | CUDA·런타임 + 런타임 자체 KV 캐시(기본 끔, M10) |
| cache_k | client 캐시 점유 | 상한 limit_k (M4) |
| OSS_k | OSS·RPC 메모리 | 이 노드 OST가 처리하는 I/O에 따른 여유분 (O2, O4) |
| KV_k(R) | 상주 KV 메모리 | 상주 집합 × 컨텍스트 크기 |
| γ_k | LLM 실행 중 같은 노드 쓰기 감속 | 로컬 direct 쓰기 −22% (M8) |

- 원 IFLustre는 C=0, β=0, A=0, 메모리 제약 없음이고, n_j(OSS 공유)와 S 중 runtime 대기만 있는 특수한 경우이다.
- 실측상 β는 작고, A_k, n_j, mem_k, 쓰기 시점(S)이 결정의 대부분을 정한다.
- 메모리 제약은 성능 항이 아니라 하드 제약이다. 넘으면 노드가 멈춘다(M10).

#### 4.9.4 로컬 배치와 원격 배치의 선택

| 배치 | 접근 시간 (stage KV 384MiB) | 네트워크 | 부하가 늘어나는 노드 |
|---|---|---|---|
| 사용 노드 OST | 약 0.15–0.3초 | 사용 안 함 | 사용 노드 (메모리, 로컬 I/O CPU) |
| 다른 stage 노드 OST | 약 3.5초 이상 | 양쪽 NIC | 다른 stage 노드 (송신 NIC가 그 stage의 activation 송신과 경쟁) |
| 이웃 stage 노드 OST (mirror) | 쓰기는 백그라운드, 장애 시 읽기 약 3.5초 이상 | 양쪽 NIC | 이웃 stage 노드 (쓰기 시점을 비용 모델이 고름) |

- 지연에 민감한 객체(KV pack)는 사용 노드에 둔다(M14).
- 내구성 객체(mirror, 체크포인트 복제본, 어댑터)는 이웃 stage 노드 OST에 두고, 받는 노드의 부하가 낮은 시점에 TBF로 쓴다.
- 원격에서 읽히는 객체(공유 prefix pack, mirror)는 activation을 보내는 stage의 OST를 피한다(M9). 다음 stage로 보내는 activation이 없는 마지막 stage(N3)의 OST가 상대적으로 유리하나, N3는 학습과 체크포인트 쓰기를 함께 하므로 쓰기 시점과 함께 판단한다.
- 병목 stage 노드의 새 pack은 비용 모델 비교로 원격이 선택될 수 있다.

#### 4.9.5 시스템 아키텍처

```
N0 (jetson): 제어·수집 ──────────────────────────────────────────────────────
  Telemetry Aggregator ─▶ Cost Model ─▶ Verifier ─▶ Executor
  Ingest Writer (W1)   Context Builder   Prefill Scheduler   Compactor   Sample Builder
  Lustre client        (장애 시) 대체 Stage Runtime
      │ 상태 요약 ▲ 변경안                       │ 계획 테이블, lfs/lctl, prefill·재생성 작업
      ▼          │                               ▼
NM (jetson0) ────────────────     N1–N3 (jetson1–3): Data plane ─────────────────────
  LLM Planner (llama.cpp)         Stage Runtime (서빙, 수집 시점 prefill, 재생성, N3: LoRA 학습)
  운영 정책·스트림 의미 정보 해석    KV Store (주소 계산, pack 쓰기·봉인, 조회·검증, 상주 관리, 캐시 해제)
  Lustre MGS/MDS                  Activation Store (N3)   Weight Loader   Adapter Manager
                                  Checkpoint Manager (N3)   Telemetry Agent   place()
                                  Lustre client   OSS/OST0000–0002 (이웃 stage mirror 포함)
```

| 처리 경로 | 용도 | 지연 |
|---|---|---|
| Slow path | 이벤트 시 재계획 (Planner, Verifier, Executor) | 10–20초 (추정) |
| Rule path | 장애 등 즉시 대응 (미리 계산한 대체 분할) | 수 초 |
| Background path | 수집 시점 prefill, 재생성, 압축, 복제 (스케줄러, TBF) | 분 단위 |
| Fast path | 요청·chunk 단위 배치와 조회 (place(), KV Store) | 마이크로초–밀리초 |

모듈 위치, 이벤트별 동작(E0–E11), 실행 예시는 `docs/design_details.md` 4–6절에 있다.

#### 4.9.6 원 IFLustre 정책과의 대응

| 원 IFLustre | CoStripe |
|---|---|
| Application Analyzer | Cost Model + LLM Planner + Verifier |
| Interference-free allocation | 동시 흐름을 서로 다른 OSS로 나눈다(M7). 원격에서 읽히는 객체는 activation을 보내는 stage의 OST에 두지 않는다(M9). 내구성 객체는 저부하 시점에 이웃 stage 노드에 쓴다. |
| Throughput-aware allocation | max_k T_k 증가와 메모리 감소가 최소인 OST 선택 |
| Runtime-aware allocation | 수집 시점 prefill·재생성·압축·복제 I/O의 시점 지연과 TBF 속도 제한 (M11) |
| Read-aware relocation | 재사용 예측 기반 migrate, 의미 기반 상주·미리 읽기 (M12) |
| 소파일 관찰 | KV pack 설계 (M13) |
| stripe count 결정 | 1GbE에서는 stripe count 1 + 사용 노드 배치 (M1) |
| 파일 경로 기반 식별 | 내용 주소 기반 식별, 의미 정보 기반 정책 |
| 간섭: OSS 사이 | OSS 사이 + NIC(저장 I/O와 activation) + 노드 메모리(런타임 KV 캐시와 저장 계층). 연산 감속은 3% 이내 |

#### 4.9.7 요소를 제거했을 때의 결과

| 제거 요소 | 결과 |
|---|---|
| ⑧ | FP16 모델을 올릴 수 없고, 사용 노드 기준 배치가 성립하지 않는다. |
| ② | 요청마다 기록 구간 수천 토큰을 다시 계산하고, 스트림 KV를 공유·보존할 수 없다. |
| ⑤ | 온라인 적응이 없고, KV 유효성 문제와 재생성·복제 I/O도 사라진다. |
| ③ | 흐름이 한 OSS에 몰리고(M7), 원격 읽기가 activation 전달을 늦추며(M9), 런타임 캐시와 저장 계층이 메모리를 넘겨 노드가 멈출 수 있다(M10). |
| ⑦ | 이벤트마다 수동 재설정이 필요하고, 스트림 의미 정책을 저장 결정으로 바꿀 수 없다. |

### 4.10 구현

| 구성 | 선택 |
|---|---|
| 서빙·학습 런타임 | PyTorch + HF transformers + PEFT 자체 파이프라인 (LG 단위 로드, KV 직렬화, 경계 activation 추출, 부분 재생성, 상위 LG LoRA) |
| stage 간 통신 | TCP (ZeroMQ 또는 gRPC), activation 토큰당 5KiB |
| KV Store | 각 stage 프로세스의 Python 라이브러리. pack append·봉인, 주소 계산(BLAKE3 또는 SHA-256), 헤더 검증, 상주 관리 |
| 전역 인덱스 | 공유 prefix용 작은 KV DB(SQLite 또는 LMDB) 파일, 한 stage OST + 다른 두 stage에 mirror |
| 플래너 | llama.cpp server (Qwen3-4B Q4_K_M) + JSON schema + prompt cache, NM에서 실행 |
| 비용 모델·검증기·Executor | Python, N0에서 실행, 분할 전수 탐색(55개) |

비교 대상은 `place()`, KV Store의 정책 부분, 스케줄러 구현만 다르고 나머지 코드는 같다. 디렉터리 구조, 주요 인터페이스, 주소·경로·pack 형식, 플래너 입출력 예시는 `docs/design_details.md` 6–8절에 있다.

---

## 5. Experiment Plan

각 표의 전체 설정과 변수는 `docs/experiment_plan.md`에 있다.

### 5.1 테스트베드와 사전 점검

장비 정보(모듈, 전력 모드, 메모리, zram, NVMe, 네트워크, Lustre 구성)는 `docs/testbed.md`에 기록한다.

| ID | 점검 | 통과 기준 |
|---|---|---|
| C1 | Lustre 기능 (PFL, FLR, migrate, TBF, jobstats, CPT) | 정상 동작 |
| C2 | 같은 노드 OST 경로, 원격 경로 대역폭 | 결과 기록 |
| C3 | client + OSS 동시 운용 안정성 | hang, OOM 없음 |
| C4, C5 | 캐시 설정 기록, 메모리 예산 실측 | 4.1.3절 표 갱신 |
| C6 | Qwen3-4B 3-stage 출력 일치 | 토큰 일치 |
| C7 | 상위 LG LoRA 공동 학습 10 step | OOM 없음 |
| C8 | 플래너 JSON 출력, 결정 지연 | 스키마 준수 |
| C9 | 시간 동기화 | 1ms 이내 |
| C10 | KV 직렬화·복원 정확성 (복원 KV로 생성한 토큰이 전체 prefill 결과와 일치) | 토큰 일치 |
| C11 | 경계 activation 기반 LG9–11 재생성 KV가 전체 재계산 KV와 일치 | FP16 허용 오차 이내 |

### 5.2 워크로드

| 워크로드 | 주요 설정 |
|---|---|
| W1 Ingest | 원 논문 6종, Loghub(HDFS, BGL), RIoTBench 레코드. 4개 라인 × 2개 스트림. 레코드 주기 10초(변수 2/10/30초), 기록 시간 2–10배 가속 재생. 원본 수집률 10MB/s(변수 0–60MB/s). prefill 배치 간격 5분(변수 1/5/15분, 비활성). 컨텍스트 한계 8k(민감도 16k) |
| W2 Adapt | 스트림 구간 + 라벨(MIMII 정상/고장, Bot-IoT 공격 여부, Loghub 이상 여부) → 판정·근거 응답. 라운드당 400–1,000 샘플. LoRA LG9–11(비교 LG6–11, 전체). 체크포인트 25 step, 약 35MB(민감도 0.4GB) |
| W3 Serve | 라인·스트림별 Zipf 분포 + 교대 시각 집중. 도착은 Poisson(최대 처리량의 30/60/90%), BurstGPT/Azure 패턴 축소 재생. 세션 1–5턴. SLO: TTFT p99 = 상주 적중 TTFT의 3배, TPOT p99 = 무부하의 1.5배 |
| 배경 부하 | fio(로컬·원격, 읽기/쓰기, 속도 단계), W1 수집, W2 체크포인트·복제, KV 재생성, 압축 |

### 5.3 측정 도구와 실험 규칙

- **측정.** tegrastats(GPU, EMC, CPU, 전력), `/proc/meminfo`·`/proc/vmstat`(메모리, 회수, 스왑. 이 커널은 PSI가 없다), `/proc/net/dev`, Lustre `job_stats`·`rpc_stats`·`md_stats`, `iostat -x`를 노드 내부 샘플러로 1초마다 기록한다(매 줄 fsync). KV Store는 적중 계층, 저장량, 최신성을, LLM은 TTFT, 토큰별 시간, stage별 시간을 이벤트 단위로 기록한다.
- **규칙.** 단기 실험 5회, 장시간 실험 3회 반복하고 평균과 95% 신뢰구간을 보고한다. p99는 구성당 300 요청 이상이다. 측정 전 캐시를 비우고 2분 예열한다. 전력 모드와 zram을 고정하고, 전 노드 시간을 동기화한다. 실험 중 메모리 보호(MemAvailable 700MB 미만이면 실험 프로세스 종료)를 켠다.

### 5.4 관찰 실험 (논문 Section III)

3장의 실측(M1–M14)을 다음 실험으로 확장한다.

| ID | 질문 | 방법 | 반영 |
|---|---|---|---|
| O1 | 로컬·원격·striping 경로의 대역폭과 CPU·NIC·캐시 비용은? | 같은 노드 OST, 원격 OST, stripe 2/3, 기본 레이아웃 × 읽기/쓰기, bs, 파일 크기, direct, 동시 client 수. 원격 읽기 중 activation 전달 시간 | 기본 배치 규칙, F_k, A_k |
| O2 | 공유 자원(OSS, NIC, 메모리)이 성능을 얼마나 바꾸는가? | ① 동시 client 1–3개의 OSS 공유/분산 ② 3-stage에서 activation 전달·decode hop을 원격 읽기·쓰기 부하 아래 측정 ③ 서버 ctx, 런타임 캐시, client 캐시 상한, Lustre I/O 종류별 메모리와 LLM 성능 ④ 대조: 연산 감속 | n_j, A_k, mem_k의 항, 보호 기준, β는 작은 항 |
| O3 | 한 stage의 NIC·메모리 경쟁이 pipeline 전체에 주는 영향은? | 같은 원격 I/O 부하를 병목 stage OST에 집중 / 균등 분산 / N3 OST에 집중 | 목적 함수, 배치 규칙 |
| O4 | 메모리 구성과 prefill 대 KV 로드의 관계는? | 노드별 메모리 분해, 1k–16k 컨텍스트의 prefill 대 경로별 KV 로드, 상주 가능 컨텍스트 수, 캐시 해제·direct I/O, 플래너 실행 중 MDS 지연 | ②의 필요성, 재계산 대 읽기 기준, SLO, 플래너 배치 |
| O5 | 체크포인트·복제·재생성·압축 버스트가 TTFT에 주는 영향은? | 서빙 60% 부하 중 버스트 실행, 위치(로컬/이웃/저부하 stage), TBF, 시점 제어 유무 | ⑤와 ②의 백그라운드 I/O 제어 |
| O6 | 복구 방식별 시간과 이벤트 빈도는? | mirror 없음 / 이웃 mirror + P'_k / P''_k(INT8), 기본 레이아웃 대 LG 배치, 2시간 시나리오의 이벤트 수 | ⑧ mirror·대체 분할, ⑦ 호출 정책 |
| O7 | 슬라이딩 윈도우 대비 이어 쓰기 컨텍스트와 수집 시점 prefill의 효과와 비용은? | 재사용 토큰 비율과 TTFT, 배치 간격별 연산·읽기 증폭·최신성, chunk별 파일 대 pack, 중복 제거량, 어댑터 전환 후 재계산량, 하루 KV 저장량 | ②의 근거, 배치 간격·LoRA 범위 기본값 |

### 5.5 비교 대상

| ID | 이름 | KV 재사용 | 분할·배치 | 백그라운드 I/O 제어 | 재계획 |
|---|---|---|---|---|---|
| B0 | Default Lustre | 요청 시점 prefix (KV를 기본 레이아웃에 저장) | 균등 분할, 기본 레이아웃, 기본 캐시 | 없음 | 없음 |
| B1 | Local-replica | 요청 시점 prefix, 로컬 디스크 | 노드별 전체 가중치 사본 | 없음 | 없음 |
| B2 | 원 IFLustre | 요청 시점 prefix | OSS 처리량 기반 할당 | runtime-aware | 시작 시 |
| B3 | Search-only | CoStripe KV 저장소 | 비용 모델 탐색 | 비용 모델 탐색 | 전체 재탐색, 정책은 수동 변환 |
| B4 | CoStripe (규칙) | CoStripe KV 저장소 | 4.9.6절 규칙 | 규칙 | 규칙 |
| B5 | CoStripe (LLM) | CoStripe KV 저장소 | 플래너 + 검증기 | 플래너 + 검증기 | propose-verify |
| B6 | Hand-tuned | 수동 | 수동 | 수동 | 수동 |
| B7 | Replicated-Q4 | llama.cpp prompt cache (로컬) | 노드별 Q4 복제 | – | 없음, 학습 불가 |
| B8 | Prefix-only CoStripe | 요청 시점 prefix (LMCache 방식 chunk 해시) | CoStripe | CoStripe | CoStripe |

B8은 KV 재사용 구조(②)의 효과만 분리하기 위한 것이다. S6에서는 LLM-only를 추가하고, CacheBlend 방식 근사 재사용을 선택 비교로 둔다.

### 5.6 평가 시나리오

| ID | 시나리오 | 설정 | 확인 내용 | RQ |
|---|---|---|---|---|
| S1 (메인) | End-to-end 라이프사이클 | 2시간(가속), 스트림 8개, 적응 라운드 2회, N3 장애·복귀, 정책 변경 1회, 압축 포함 | 시간축 SLO 달성률, TTFT p99, 최신성, 라운드 완료, 복구 시간 | RQ1–RQ5 |
| S2 | 정상 상태 서빙 | 도착률 30/60/90%, 컨텍스트 8k/16k, 배치 간격 | TTFT, TPOT, 처리량, KV 적중 계층 분포 | RQ2, RQ3 |
| S3 | 서빙 + 적응 학습 | 학습 비율, 체크포인트 크기·간격 | TTFT p99, 학습 처리량, 복제 완료 | RQ4 |
| S4 | 어댑터 전환 | 라운드 종료 반복 | 전환·재생성 시간, 재생성 중 TTFT, 버전 불일치 | RQ4 |
| S5 | 장애와 재분할 | N1–N3 각각 장애, 부하 변화 재분할 | 복구 시간, 이동 바이트, 복구 중 TTFT | RQ2 |
| S6 | 플래너 비교 | 이벤트 30종 (기존 15, 처음 보는 15) | SLO, 정책 준수, 무효 계획 비율, 결정 지연 | RQ5 |
| S7 | KV 재사용 구조 | 레코드 주기, 요청 분포, 컨텍스트 한계, LoRA 범위 | B0/B8/B4 비교, 저장량, 수집 시점 연산, 압축·재생성 비용 | RQ3 |

### 5.7 지표

- **서빙:** TTFT p50/p95/p99, TPOT, tokens/s, SLO 달성률
- **KV:** 적중 계층 분포(상주/로컬/원격/재계산), 재사용 토큰 비율, 최신성 지연, 저장량, 중복 제거량
- **라이프사이클:** 로드·복구 시간, 체크포인트·복제 완료, 학습 step/s, 라운드 완료, 재생성·압축 시간
- **메모리:** 상주 KV, client 캐시 점유, 런타임 캐시, MemAvailable 최저값, 회수·스왑, 노드 정지·보호 동작
- **자원·비용:** J/token, 이동 바이트, NIC 방향별 사용률, OSS별 동시 흐름 수, MDS 메타데이터 연산 수
- **플래너:** 결정 지연, 메모리·전력, 정책 준수율, 무효 계획 비율
- **품질 (확인용):** LoRA 범위별·압축 방식별 판정 정확도

### 5.8 Ablation과 민감도

| Ablation (제거 → 대체) | 확인 내용 |
|---|---|
| 수집 시점 prefill → 요청 시점 계산 / 이어 쓰기 컨텍스트 → 슬라이딩 윈도우 | 사전 계산과 컨텍스트 구조의 효과 |
| pack → chunk별 파일 / 공유 prefix 중복 제거 제거 | 메타데이터 비용, 저장량·연산 |
| stage 간 상주 조정 → 독립 상주 / 의미 기반 미리 읽기 제거 | 상주 조정, 교대 시각 TTFT |
| 규칙 압축 → 한계 도달 시 재계산 / 상위 LG LoRA + 경계 activation → 전체 LoRA, 전체 재계산 | 압축과 재생성 비용 |
| OSS 분산 → 흐름을 한 OSS에 모음 | OSS 공유 회피 효과 (interference-free) |
| NIC 인지 배치 → activation을 보내는 stage의 OST도 원격 읽기 대상으로 허용 | NIC 공유 회피 효과 |
| 메모리 예산 관리 → 런타임 캐시·client 캐시 기본값 | 메모리 관리 효과, 노드 정지 여부 |
| β 반영 → β=0 | 연산 감속 항의 기여 (작을 것으로 예상) |
| 사용 노드 배치, 이웃 mirror + N0 대체 / 3단계 체크포인트, TBF, 시점 제어 / 플래너 → 규칙 | 배치·복구, 백그라운드 I/O 제어, 플래너 효과 |

| 민감도 변수 | 범위 |
|---|---|
| 노드·stage 수 | 2–4 (4는 N0를 stage로 추가, 로컬 OST 없음) |
| 네트워크 | `tc` 100M/300M/1G, 선택 USB 2.5GbE |
| 모델 | Qwen3-1.7B FP16, Qwen3-4B FP16, Qwen3-8B Q8_0 (O1–O3) |
| 스트림 수, 레코드 주기, 컨텍스트 한계, 배치 간격 | 4/8/16, 2/10/30초, 4k/8k/16k, 1/5/15분 |
| 요청 분포, 도착률 | 균등 / Zipf, 30–90% |
| 체크포인트, LoRA 범위 | 35MB–0.4GB와 10–50 step, LG9–11 / LG6–11 / 전체 |
| 캐시 상한, 런타임 KV 캐시 | 256MB–기본값, 끔 / 512MB / 기본값(8GiB) |
| OSS당 동시 흐름 수, 전력 모드 | 1–4, 7W/15W/최대 |

### 5.9 규모 확장 시뮬레이션

비용 모델과 측정 파라미터로 트레이스 기반 시뮬레이터를 만들고 5노드 실측과의 오차를 보고한다. 이후 노드 8–32대, 스트림 16–128개에서 B0, B2, B8, B4를 비교한다.

---

## 6. 논문 구성 대응

| 논문 섹션 | 내용 | 이 문서 |
|---|---|---|
| I. Introduction | 배경, IoT 요청 구조, 두 문제, 간섭의 정의, 공백, CoStripe, 기여 | 1 |
| II. Background | IoT·엣지, Jetson, IoT LLM, LLM 구조·KV 재사용·I/O, CAS, Lustre, IFLustre | 2 |
| III. Motivation (Empirical Analysis) | 실측 M1–M14, 관찰 요약과 관찰-설계 대응표, 이후 O1–O7로 확장 | 3, 5.4 |
| IV. Design | 문제 정의, 비용 모델, ⑧②⑤③⑦, 통합 구성, 구현 | 4 |
| V. Evaluation | 비교 대상, S1–S7, ablation, 민감도, 시뮬레이션 | 5.5–5.9 |
| VI. Discussion | 규모, MDS 단일 장애점, 다른 DFS, 큰 장비, 근사 재사용과의 결합, 보안 | 8 |
| VII. Related Work | 2.8절과 `docs/related_work.md` | 2.8 |
| VIII. Conclusion | | |

주요 그림과 표는 다음과 같다(전체 목록은 `docs/experiment_plan.md` 6절). II장: 라이프사이클과 하이퍼컨버지드 클러스터, 슬라이딩 윈도우 예, 관련 연구 비교표, 메모리 예산. III장: M1–M14와 O1–O7 결과, 관찰 요약표(3.14절), 관찰-설계 대응표(3.16절). IV장: 아키텍처, 주소 구조, 부분 재생성, LG 배치와 대체 분할, IFLustre 대응표(4.9.6절). V장: S1–S7, ablation, 민감도.

IEEE IoTJ 이전 버전과의 차이는 2.7절과 4.9.6절 표로 설명한다. 심사 의견 응답서는 `docs/response.md`(예정)로 관리한다.

---

## 7. 일정

| 단계 | 기간 | 작업 | 논문 위치 |
|---|---|---|---|
| P0 | 1주 | 장비·네트워크·Lustre 기록, C1–C9, A' 구성, 테스트베드 실측 M1–M14 | III |
| P1 | 4주 | harness 구현: 파이프라인 런타임, KV Store, Context Builder, Prefill Scheduler, Compactor, 경계 activation, 상위 LG 학습, telemetry, place() / C6, C7, C10, C11 | IV |
| P2 | 2주 | O1–O7 측정 | III |
| P3 | 1주 | 비용 모델 피팅, 오차 검증 | IV |
| P4 | 2주 | LG 배치, 상주 조정, 백그라운드 I/O 제어, 대체 분할, 규칙 정책 | IV |
| P5 | 1주 | 플래너, 검증기, Search-only, B7, B8 | IV |
| P6 | 2주 | S1–S7, ablation, 민감도, 시뮬레이션 | V |
| P7 | 1–2주 | 집필, 응답서 | 전체 |

---

## 8. 리스크와 예상 반론

### 8.1 기술 리스크

| 리스크 | 대응 |
|---|---|
| PyTorch 런타임 메모리가 추정보다 큼 | C5 실측. 초과 시 4-stage(N0를 stage로 추가), INT8 weight-only, Qwen3-1.7B 2-stage 순으로 조정 |
| 파이프라인·KV Store 구현량 | 학습을 상위 LG로 한정하고, KV Store는 pack·경로 계산 중심으로 단순화(전역 인덱스는 공유 prefix만) |
| KV 직렬화·재생성 정확성, 레코드 토큰화 결정성 | C10, C11 검증 후 진행. 레코드별 독립 토큰화, 토크나이저 버전을 주소에 포함 |
| LLM 런타임의 호스트 RAM KV 캐시와 client + OSS 동시 운용 | llama.cpp 기본값(`--cache-ram` 8GiB)은 8GB 장치에서 노드를 멈추게 한다. 끄거나 메모리 예산에 포함하고, 캐시 상한과 메모리 보호를 운영한다(M10) |
| 연산 간섭(β)이 작음 (실측 3% 이내) | 간섭을 공유 자원과 쓰기 시점으로 정의하고, 위치·배치와 KV 재사용 구조(②) 중심으로 서술한다. β는 대조 측정으로 보고한다. PyTorch FP16 pipeline과 LoRA 학습에서 다시 확인한다 |
| 수집 시점 prefill의 유휴 연산 부족 | 배치 간격 확대, 우선 스트림만 사전 계산, 나머지는 요청 시점 계산 |
| 상위 LG LoRA의 적응 품질 부족 | LG6–11로 범위를 넓히고 재생성 비용과 함께 보고 |
| 플래너가 Search-only보다 낮음 | 정책 해석·이벤트 대응 결과를 보고하고, 주 기여는 ②⑧로 둔다 |
| 이웃 stage mirror 쓰기가 받는 노드의 서빙을 방해 | 비용 모델이 저부하 시점을 고르고 TBF로 속도 제한 (O5) |
| 플래너와 MDS가 같은 노드(jetson0) | 플래너 실행 중 메타데이터 지연 측정(O4). 영향이 크면 1.7B 모델로 줄이거나 실행 시점 제한 |
| N0 대체 stage에 로컬 OST 없음, MDS 단일 장애점 | 대체 중 KV는 원격 읽기 또는 재계산하고 S5에서 보고. MDS 장애는 범위 밖으로 명시(Discussion) |

### 8.2 예상 반론과 대응

| 반론 | 대응 |
|---|---|
| "DFS가 왜 필요한가? 로컬 디스크로 충분하지 않나" | 스트림 KV 로그는 메모리보다 크고, 여러 요청이 공유하며, 재분할·장애 후에도 유지되어야 한다. Local-replica(B1)와 재분할·장애·어댑터 전환에서 비교한다. |
| "locality는 오래된 개념이다" | 하이퍼컨버지드 노드에서는 로컬 배치가 그 노드의 NIC와 메모리를 쓴다. 원격에서 읽히는 객체의 위치가 그 stage의 activation 전달을 4배 바꾸고(M9), 메모리 예산을 넘기면 노드가 멈춘다(M10). 수집 시점 prefill과 재생성 같은 새 I/O 클래스의 배치도 다룬다. |
| "저장 I/O가 LLM을 거의 늦추지 않는데 간섭 인지가 왜 필요한가" | 연산 감속이 3% 이내임을 먼저 보인다(M8). 간섭은 공유 자원에서 생긴다. OSS를 공유하는 흐름 3개는 합계 120MB/s로 제한되고 분산하면 2–2.5배이다(M7). OSS의 원격 읽기가 그 stage의 activation 전달을 4배 늦춘다(M9). 런타임 KV 캐시와 저장 계층이 메모리를 나눠 쓰면 노드가 멈춘다(M10). KV를 사용 노드에 두면 TTFT p50이 0.79초이고, Lustre 기본 할당은 6.2초, 사용 노드를 보지 않는 부하 분산은 16.0초이다(M14). 이것은 원 IFLustre의 OSS 공유 간섭을 NIC와 메모리로 넓힌 것이다. |
| "KV 사전 계산은 TurboRAG, MemLLM에 있다" | 고정 문서가 아닌 계속 늘어나는 스트림, 근사 없는 이어 쓰기 재사용, 압축 epoch, 어댑터 범위 기반 주소와 부분 재생성, 공유 엣지 DFS 배치가 차이이다. |
| "content addressing은 vLLM, LMCache도 쓴다" | 그들은 요청 시점 생성과 메모리·분리형 풀을 다룬다. 본 연구는 이름·위치·정책 분리, 버전 범위 주소, 의미 기반 묶음·압축·상주를 저장 계층에서 다룬다. |
| "5대는 작다" | 엣지 사이트 규모가 원래 작다. 시뮬레이션으로 확장한다. |
| "LLM 플래너가 왜 필요한가" | Search-only를 비교 대상에 넣는다. 플래너의 가치는 의미 정책 해석과 이벤트 대응에 둔다. |

### 8.3 기여 판단 기준

테스트베드 실측(3장)의 판단은 다음과 같다. 상세는 `results/p0/summary.md`에 있다.

| 판단 항목 | 결과 | 판정 |
|---|---|---|
| 데이터·KV 위치 (M2, M3) | 로컬 대 원격 15–22배, 로컬 KV 복원 대 재계산 7–12배 | go |
| 공유 자원과 배치 (M7, M9, M10, M14) | OSS 공유 2–2.5배, activation 전달 2–4배, 메모리 초과 시 노드 정지, 배치 정책별 TTFT p50 8–20배 | go (주장의 중심) |
| 쓰기 시점과 재배치 (M11, M12) | KV 복원 +41% 대 +2%, 원격 KV 5회 사용 27.3초 → 14.8초 | go |
| 저장 I/O의 연산 감속 (M5, M8) | 3% 이내 | 주장에서 제외, 대조 측정으로 보고 |

O1–O7 결과로 투고 대상을 정한다. 공유 자원과 배치 정책이 TTFT를 바꾸는 크기(O2, O3, M14) 또는 슬라이딩 윈도우 대비 수집 시점 prefill의 TTFT 개선(O7)이 크게 나타나면 IoTJ 외에 상위 시스템 학회 버전을 검토한다. 작게 나타나면 IoTJ에 집중한다.

---

## 9. 미결 사항

완료한 항목은 `docs/CHANGELOG.md` 3절로 옮겼다.

- [ ] PyTorch FP16 pipeline과 LoRA 학습에서 연산 간섭 재확인 (CPU 비중이 커서 llama.cpp Q4보다 민감할 수 있음)
- [ ] M14 반복 측정: 부하 분산 정책의 결과가 배치에 좌우되므로 seed를 바꿔 반복
- [ ] PyTorch 설치 방식 결정과 메모리 사용량 실측
- [ ] 플래너 모델 크기 확정 (기본 배치는 jetson0, Qwen3-4B Q4 실측 약 4.1GB. MDS 영향은 O4에서 확인)
- [ ] zram 설정을 실험 중 유지할지 결정
- [ ] 서버 MGS 주소 정정 (F1). 서버 재부팅, OST 추가, 영구 설정(`set_param -P`)이 필요할 때 정정
- [ ] GUI 비활성화와 실험 노드의 다른 프로세스 정리 (F4)
- [ ] 노드 간 시간 동기화 개선 (F5), jetson 송신 대역폭 저하 원인 확인 (F3)
- [ ] Jetson 사양 수치 공식 확인
- [ ] 제목에 KV 저장 구조(content-addressed)를 반영할지 여부 (시스템 이름 CoStripe는 가제)
- [ ] 이전 IoTJ 심사 의견 정리와 반영 범위
- [ ] 기존 루트 스크립트의 `legacy/` 이동 여부
- [ ] 참고 문헌 서지 정보 원문 확인

---

## 10. 참고 문헌

전체 참고 문헌(분야별 약 100편)은 `docs/related_work.md` 3절에 있다. 원 연구는 다음과 같다.

- S. Kim, D. K. Sung, Y. Son, "IFLustre: Towards Interference-free and Efficient Storage Allocation in Distributed File System," MASCOTS 2022.
- "Interference-free and Efficient Storage Allocation for IoT Applications in Distributed File System on Cloud Environment," IEEE IoTJ (Reject & Resubmit).

---

## 부록 A. 크기와 메모리 계산

| 항목 | 값 |
|---|---|
| Qwen3-4B 구조 | vocab 151,936, hidden 2,560, layer 36, Q head 32, KV head 8, head 차원 128, MLP intermediate 9,728, 임베딩 공유 |
| 임베딩 | 약 0.389B 파라미터, FP16 약 0.78GB |
| layer / LG (g=3) | 약 100.9M 파라미터, FP16 약 0.2GB / LG당 약 0.6GB |
| stage 가중치 (3-stage, LG 4개) | 약 2.4GB (stage 1·3은 임베딩 포함 약 3.2GB) |
| KV/토큰 | 전체 144KiB, layer 4KiB, LG 12KiB, stage 48KiB |
| chunk (256토큰) / pack (32 chunk) | LG 3MiB, stage 12MiB, 전체 36MiB / LG당 96MiB |
| 8k 컨텍스트 KV | 1.125GiB (stage 384MiB, LG 96MiB, LG9–11 288MiB). 16k는 두 배 |
| 8개 컨텍스트 × 8k | stage당 3GiB, 전체 9GiB |
| 경계 activation | 토큰당 5KiB, chunk 1.25MiB, 8k 컨텍스트 40MiB (KV의 약 3.5%) |
| prefill 8k 연산량 | 선형 약 6.6e13 + attention(causal) 약 2.0e13 FLOP |
| 수집 시점 prefill | 스트림당 시간당 약 7.2k 토큰, 8개 합계 시간당 약 5.8만 토큰 → 시간당 약 5e14–7e14 FLOP (유효 2–8 TFLOPS 가정 시 약 1–6분) |
| 압축 주기 | 8k 한계, 기본 prefix 약 3.3k → 기록 공간 약 4.7k ÷ 시간당 7.2k = 스트림당 약 40분 |
| 상위 LG 재생성 | 연산은 전체 재계산의 약 25%. I/O는 8k 컨텍스트당 activation 읽기 40MiB + LG9–11 KV 쓰기 288MiB |
| LoRA (LG9–11, rank 16, q/k/v/o) | 9 layer 약 2.95M 파라미터, 어댑터 약 6MB(LG당 약 2MB), 체크포인트 약 35MB(FP32 + Adam m, v), 학습 메모리 약 0.15–0.3GB |
| LoRA (rank 64, 7개 linear) | 약 33M 파라미터, 체크포인트 약 0.4GB |
| 접근 시간 추정 | stage 가중치 로컬 약 1–2초 / 원격 약 21–28초, LG 원격 이동 약 5초, stage KV 8k 로컬 약 0.15–0.3초 / 원격 약 3.5초, decode stage 시간(12 layer) 약 24–50ms |

모든 값은 5장 실험으로 확인한다.

## 부록 B. 저장소의 기존 코드

| 파일 | 내용 | 향후 용도 |
|---|---|---|
| `iotbenchlustre.py` | 데이터셋을 Lustre에 쓰는 IoT 벤치마크 | W1 수집 부하 생성기 |
| `iotbenchhdfs*.py`, `iotBhdfs_old.py` | HDFS 벤치마크 | 사용 여부 미정 |
| `iotBench.py`, `iot0.py`–`iot2.py`, `iotr.py`, `iotmultiepic*.py` | 기존 IoT 실험 | 참고용 |
| `listdataset.py`, `cpfile.sh`, `config.sh` | 데이터셋 목록, 파일 복사, Hadoop 환경 | 유지 |
| `fio*.sh`, `2fio.sh` | fio 측정 | O1, O2 부하 생성 |
| `readme.txt` | `lfs setstripe` 예시 | 이 문서로 대체 예정 |

---

변경 이력은 `docs/CHANGELOG.md`에 있다.
