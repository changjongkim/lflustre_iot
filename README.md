# lflustre_iot

**하이퍼컨버지드 엣지 분산 파일 시스템에서 IoT용 LLM 라이프사이클을 위한 저장-연산 간섭 인지 스토리지 할당**

(IFLustre 확장 연구 설계 문서)

> **상태:** 연구 설계 단계
> **관리:** 설계가 바뀌면 이 문서를 수정하고 커밋한다. 수치 중 "추정"으로 표시한 값은 4장의 실험으로 확인한 뒤 갱신한다.
> **구성:** 이 문서는 논문의 흐름을 따른다. 1장 Introduction → 2장 Background and Related Work → 3장 Design(문제 정의, 해결 대상, 해결 방법, 통합 구성) → 4장 Experiment Plan.

---

## 목차

- [0. 요약](#0-요약)
- [1. Introduction](#1-introduction)
- [2. Background and Related Work](#2-background-and-related-work)
  - [2.1 IoT 데이터 처리와 엣지 컴퓨팅](#21-iot-데이터-처리와-엣지-컴퓨팅)
  - [2.2 엣지 하드웨어: NVIDIA Jetson Orin](#22-엣지-하드웨어-nvidia-jetson-orin)
  - [2.3 IoT 애플리케이션에서의 LLM 활용](#23-iot-애플리케이션에서의-llm-활용)
  - [2.4 LLM 추론과 학습의 구조, 그리고 저장 I/O](#24-llm-추론과-학습의-구조-그리고-저장-io)
  - [2.5 분산 파일 시스템과 Lustre](#25-분산-파일-시스템과-lustre)
  - [2.6 원 연구: IFLustre](#26-원-연구-iflustre)
  - [2.7 관련 연구](#27-관련-연구)
  - [2.8 종합 비교와 연구 공백](#28-종합-비교와-연구-공백)
- [3. Design](#3-design)
  - [3.1 대상 환경](#31-대상-환경)
  - [3.2 대상 시나리오와 워크로드](#32-대상-시나리오와-워크로드)
  - [3.3 모델 선정](#33-모델-선정)
  - [3.4 데이터 객체와 I/O 특성](#34-데이터-객체와-io-특성)
  - [3.5 문제 정의](#35-문제-정의)
  - [3.6 문제를 어렵게 만드는 요인](#36-문제를-어렵게-만드는-요인)
  - [3.7 연구 질문](#37-연구-질문)
  - [3.8 해결 대상](#38-해결-대상)
  - [3.9 통합 구성](#39-통합-구성)
  - [3.10 구현](#310-구현)
- [4. Experiment Plan](#4-experiment-plan)
  - [4.1 테스트베드 구성과 사전 점검](#41-테스트베드-구성과-사전-점검)
  - [4.2 워크로드 구성 상세](#42-워크로드-구성-상세)
  - [4.3 측정 도구와 방법](#43-측정-도구와-방법)
  - [4.4 관찰 실험 (논문 Section III)](#44-관찰-실험-논문-section-iii)
  - [4.5 평가 실험 (논문 Section V)](#45-평가-실험-논문-section-v)
  - [4.6 예상 그림과 표](#46-예상-그림과-표)
- [5. 논문 구성 대응](#5-논문-구성-대응)
- [6. 일정](#6-일정)
- [7. 리스크](#7-리스크)
- [8. 미결 사항](#8-미결-사항)
- [9. 참고 문헌](#9-참고-문헌)
- [부록 A. 크기 계산식](#부록-a-크기-계산식)
- [부록 B. 플래너 입출력 예시](#부록-b-플래너-입출력-예시)
- [부록 C. 저장소의 기존 코드](#부록-c-저장소의-기존-코드)

---

## 0. 요약

### 0.1 국문 요약

IoT 애플리케이션은 센서, 음향, 로그 데이터를 해석하기 위해 LLM을 사용하기 시작했다. 지연 시간, 네트워크 대역폭, 데이터 반출 제한 때문에 이 처리는 데이터가 생성되는 엣지 사이트에서 수행하는 것이 바람직하다. 그러나 엣지 장치 한 대의 메모리로는 최신 LLM의 가중치, 긴 IoT 컨텍스트의 KV cache, 현장 적응 학습을 동시에 수용할 수 없다. 따라서 엣지 사이트는 여러 장치로 소규모 클러스터를 구성하고, 장치들이 공유 분산 파일 시스템(DFS)으로 데이터를 주고받는다.

이 구성에서는 각 장치가 LLM 연산 노드이면서 동시에 DFS 스토리지 서버가 된다(하이퍼컨버지드 구성). 이때 모델 가중치, KV cache, 학습 체크포인트를 읽고 쓰는 저장 I/O가 같은 장치의 LLM 연산과 unified memory·CPU를 나눠 쓴다. 파이프라인 병렬 추론에서는 한 장치의 지연이 서비스 전체의 처리량을 결정하므로 이 영향이 커진다.

본 연구는 다음을 수행한다.
1. Jetson Orin 5대와 Lustre로 구성한 엣지 클러스터에서 LLM 라이프사이클(수집, 적응, 서빙)의 I/O 특성과 저장-연산 간섭을 분석한다.
2. 분석 결과를 바탕으로 세 가지 기법을 설계한다.
   - 파이프라인 분할과 데이터 배치를 Layer Group 단위로 함께 결정하는 기법
   - 라이프사이클 I/O의 시점과 속도를 제어하는 기법
   - 이벤트 발생 시 LLM 플래너와 비용 모델 검증기로 재계획하는 기법

본 연구는 MASCOTS 2022에 발표한 IFLustre를 확장한다. IFLustre의 할당 정책은 OSS 간 간섭만 고려했는데, 이를 저장-연산 간섭과 LLM 라이프사이클까지 포함하도록 일반화한다.

### 0.2 영문 초록 초안

> IoT applications increasingly rely on large language models (LLMs) to interpret sensor streams, acoustic signals, and logs close to where data is generated. Since a single edge device cannot simultaneously host a modern LLM, the key-value (KV) cache for long IoT contexts, and on-site model adaptation, edge sites form small clusters in which every device serves as both an LLM compute node and a storage server of a shared distributed file system (DFS). In such hyperconverged edge clusters, storage I/O for model weights, KV caches, and fine-tuning checkpoints competes with LLM computation on the same unified memory, and pipeline parallelism amplifies the slowdown of a single device to the entire service. In this article, we first characterize the I/O of the edge LLM lifecycle (ingest, adapt, and serve) on a five-node NVIDIA Jetson Orin cluster running Lustre. Based on our observations, we propose [NAME], which (1) jointly decides the pipeline partition and the file layout of weights, KV caches, and adapters at layer-group granularity, (2) schedules lifecycle I/O to minimize interference with the bottleneck stage, and (3) re-plans upon lifecycle events using an LLM-based planner with a cost-model verifier. Our evaluation shows that [NAME] improves p99 TTFT by X% and SLO attainment by Y% compared to the default Lustre configuration and our prior work.

---

## 1. Introduction

**IoT 데이터와 엣지 처리.** IoT는 제조, 물류, 에너지, 농업 등에 널리 쓰이고 있으며, 생성되는 데이터의 양과 종류가 함께 늘고 있다. 산업 현장의 IoT 장치는 진동·온도 같은 시계열 센서 값, 설비 음향, 네트워크 트래픽과 시스템 로그, 카메라와 드론 영상을 계속 생성한다. 이전에는 이 데이터를 클라우드로 보내 처리하는 구성이 일반적이었다. 그러나 다음 세 가지 이유로 데이터가 생성된 사이트 안에서 처리하는 엣지 컴퓨팅이 확산되고 있다.
- 응답 지연 시간에 대한 요구
- 원격 전송 대역폭의 비용
- 설비·공정 데이터의 반출 제한

**IoT에서의 LLM.** IoT 데이터를 해석하는 방식도 바뀌고 있다. 기존에는 이상 탐지 모델이 정상/이상 여부를 판정하는 것으로 끝났다. 최근에는 LLM이 여러 형태의 데이터를 함께 해석하고, 이상의 원인을 설명하고, 현장 운영자의 자연어 질의에 답하고, 설비 매뉴얼과 로그를 연결해 조치 방법을 제시하는 방식이 연구되고 있다. 이런 활용에서 LLM 입력은 길다. 시스템 지시문, 설비 매뉴얼, 최근 센서·로그 구간이 함께 들어가기 때문이다. 또한 설비와 공정이 바뀌면 모델도 현장 데이터로 주기적으로 적응해야 한다.

**엣지 장치 한 대의 한계와 클러스터 구성.** 엣지에서 LLM을 운용하려면 장치 한 대의 자원 한계를 넘어야 한다. NVIDIA Jetson AGX Orin은 64GB unified memory를 갖지만, 32B급 모델의 FP16 가중치(약 65GB)를 담을 수 없다. 양자화로 가중치를 줄여도 긴 컨텍스트의 KV cache, 적응 학습, 운영체제와 파일 시스템이 같은 메모리를 나눠 써야 한다. 이 문제를 해결하기 위해 여러 엣지 장치에 모델 layer를 나누어 배치하는 파이프라인 병렬 추론이 제안되었다(EdgeShard, PipeEdge, LOIP, prima.cpp 등).

**라이프사이클과 데이터 공유.** 엣지의 LLM 운용은 추론만으로 끝나지 않는다. 운용은 세 단계가 반복되는 라이프사이클이다.
1. 수집(Ingest): IoT 데이터를 저장한다.
2. 적응(Adapt): 저장된 데이터로 모델을 주기적으로 적응시킨다.
3. 서빙(Serve): 적응된 모델로 질의를 처리한다.

이 과정에서 생성되는 데이터 객체는 크다. 모델 가중치는 수십 GB, 세션별 KV cache는 수백 MB에서 GB, 체크포인트와 어댑터는 수백 MB에서 GB이다. 또한 데이터를 생성하는 장치와 사용하는 장치가 다르다. 어댑터는 학습 장치에서 생성되어 모든 추론 장치가 읽는다. 장애나 부하 변화로 분할이 바뀌면, 어떤 layer의 가중치와 KV를 다른 장치가 읽어야 한다. 따라서 장치들 사이에 공유 저장 계층이 필요하고, 그 역할로 분산 파일 시스템(DFS)을 사용한다.

**하이퍼컨버지드 구성의 문제.** 엣지 사이트에는 스토리지 전용 서버를 따로 둘 여유가 없다. 그래서 각 장치가 DFS의 스토리지 서버(Lustre의 OSS)이면서 LLM 연산 노드가 된다. 이 구성에서는 데이터센터에서 나타나지 않는 간섭 경로가 생긴다. 어떤 장치의 OST로 I/O가 몰리면, 그 장치의 OSS 처리(데이터 복사, 네트워크 처리, page cache)가 같은 장치의 LLM 연산과 CPU 코어 및 unified memory 대역폭을 나눠 쓴다. 파이프라인 병렬 추론에서는 가장 느린 stage가 전체 처리량을 결정하므로, 한 장치의 지연이 서비스 전체로 전파된다. 즉, 이 환경에서는 데이터를 어느 장치에 저장할지를 정하는 것이 곧 어느 장치의 연산을 느리게 할지를 정하는 것이 된다.

**기존 연구의 공백.** 기존 연구는 이 문제를 직접 다루지 않는다.

| 연구 분야 | 다루지 않는 부분 |
|---|---|
| DFS 저장 할당 (본 연구진의 IFLustre 포함) | 스토리지 서버 사이의 간섭만 고려하고, 스토리지와 연산이 분리된 환경을 가정한다. |
| 데이터센터 KV cache 저장 (Mooncake, LMCache, CachedAttention) | 연산 노드와 분리된 메모리·스토리지 풀을 가정한다. |
| 엣지 KV 오프로딩 (KVSwap, Dual-Blade) | 장치 한 대의 로컬 SSD만 다룬다. |
| 엣지 분산 추론 (EdgeShard, LOIP) | 연산량과 네트워크를 기준으로 분할하며, 저장 I/O와 학습 I/O를 고려하지 않는다. |
| LLM 기반 스토리지 튜닝 (ION, STELLAR) | HPC 단일 애플리케이션의 오프라인 튜닝을 다룬다. |

**본 연구의 접근.** 본 연구는 네 단계로 접근한다.
1. Jetson Orin 5대와 Lustre로 구성한 엣지 클러스터에서 LLM 라이프사이클의 I/O 특성과 저장-연산 간섭을 측정한다.
2. 가중치, KV cache, 어댑터가 모두 layer 단위로 나뉜다는 점에 주목한다. 연속된 layer 묶음(Layer Group, LG)을 파이프라인 분할과 데이터 배치의 공통 단위로 정하고, 둘을 하나의 비용 모델 위에서 함께 결정한다.
3. 체크포인트, 어댑터 배포, 재배치 같은 라이프사이클 I/O의 시점과 속도를 서빙 SLO에 맞추어 제어한다.
4. 적응 라운드, 장애, 부하 변화, 운영 정책 변경 같은 이벤트가 발생하면, LLM 플래너가 변경안을 만들고 비용 모델 기반 검증기가 이를 검사한 뒤 적용한다.

이 기법은 IFLustre의 할당 정책(interference-free, throughput-aware, runtime-aware, read-aware relocation)을 일반화한 것이다. IFLustre는 본 연구의 비용 모델에서 연산 항을 제외한 특수한 경우에 해당한다.

**기여.** 본 연구의 기여는 다음과 같다.
1. 하이퍼컨버지드 엣지 DFS에서 LLM 라이프사이클 I/O의 특성과 저장-연산 간섭을 실측으로 분석하고, 관찰 결과 6개를 제시한다.
2. Layer Group 단위로 파이프라인 분할과 데이터 배치를 함께 결정하는 비용 모델과 배치 기법을 제안한다.
3. IFLustre의 할당 정책을 라이프사이클 전체로 확장한 시스템과, 이벤트 기반 LLM 플래너 및 검증기를 설계하고 구현한다.
4. Jetson Orin 5대로 구성한 실제 장비에서 기존 기법 대비 성능을 평가한다.

---

## 2. Background and Related Work

### 2.1 IoT 데이터 처리와 엣지 컴퓨팅

**IoT 데이터의 형태.** IoT 데이터는 도메인에 따라 형태와 크기가 크게 다르다. 원 IFLustre 연구는 아래 6종의 공개 데이터셋으로 IoT I/O를 모사했다. 파일 크기가 수백 KB에서 수 GB까지 분포하며, 이 차이가 DFS의 striping 효과를 다르게 만든다는 것을 보였다.

| 데이터셋 | 도메인 | 데이터 형태 | 파일 크기 | 원 논문 이름 |
|---|---|---|---|---|
| Bot-IoT | 네트워크 보안 | 네트워크 트래픽(봇넷 공격 포함) | 수백 MB | IoTApp1 |
| Widar3.0 | 행동 인식 | WiFi CSI 기반 제스처 | 약 215KB | IoTApp2 |
| MIMII | 산업 설비 | 정상/고장 설비 음향 | 약 2.5MB | IoTApp3 |
| VisDrone | 영상 | 드론 촬영 이미지 | 수십~수백 KB | IoTApp4 |
| EPIC-Sounds | 음향 | 주방 활동 음향 | 단일 4GB | IoTApp5 |
| LoED | 센서 네트워크 | LoRaWAN 패킷 | 10~30MB | IoTApp6 |

여기에 두 종류를 추가로 고려한다.
- **RIoTBench:** 분산 스트림 처리용 IoT 벤치마크이다. 수백 바이트 단위의 센서 레코드가 연속으로 들어오는 패턴을 대표한다.
- **Loghub:** 시스템 로그 모음(HDFS, BGL, Thunderbird 등)으로, LLM이 직접 해석하는 텍스트 형태의 데이터를 대표한다.

**소파일 IoT 데이터와 striping.** RIoTBench처럼 레코드가 작은 데이터는 파일 단위 striping의 효과가 거의 없다. 원 IFLustre 연구에서도 256KB 파일은 stripe count를 늘려도 처리량이 오르지 않았다(최대 4% 감소). 따라서 본 연구에서 IoT 수집 데이터는 성능 최적화의 주 대상이 아니다. 대신 LLM 라이프사이클의 입력이자 배경 I/O 부하로 다룬다.

**엣지 컴퓨팅.** 클라우드는 자원이 크지만, 엣지 사이트에서 원격 데이터센터까지의 네트워크 지연과 대역폭 비용이 든다. 공정 데이터와 영상은 보안 정책상 외부 반출이 제한되는 경우가 많다. 엣지 컴퓨팅은 데이터 생성 위치 근처에서 처리해 이 문제를 줄인다. 그 대신 장치별 연산, 메모리, 저장 자원이 작고, 전력과 발열 제약이 있다. 엣지 사이트에서는 보통 수 대에서 수십 대의 장치가 같은 LAN에 연결된다.

| 항목 | 클라우드 | 엣지 사이트 |
|---|---|---|
| 노드 수 | 수천 이상 | 수~수십 |
| 저장 계층 | 전용 스토리지 서버 | 연산 장치에 내장된 SSD |
| 네트워크 | 25–400Gbps, RDMA | 1–10GbE |
| 메모리 | CPU DRAM과 GPU HBM 분리 | SoC unified memory (CPU와 GPU 공유) |
| 데이터 반출 | 가능 | 제한되는 경우가 많음 |
| 전력 | 노드당 수백 W–kW | 장치당 수십 W |

### 2.2 엣지 하드웨어: NVIDIA Jetson Orin

Jetson Orin은 ARM CPU, Ampere GPU, DLA 등을 하나의 SoC에 통합한 엣지 AI 모듈이다. 가장 중요한 구조적 특징은 **CPU와 GPU가 하나의 LPDDR5 메모리를 공유하는 unified memory**라는 점이다. GPU 텐서, CPU 프로세스 메모리, 운영체제 page cache, 파일 시스템 버퍼가 모두 같은 물리 메모리와 같은 메모리 컨트롤러(EMC)를 사용한다.

| 모듈 | CPU | GPU | 메모리 | 메모리 대역폭 | AI 성능 (INT8, sparse) | 전력 모드 | 개발자 키트 NIC |
|---|---|---|---|---|---|---|---|
| AGX Orin 64GB | 12-core Cortex-A78AE | 2048-core Ampere, Tensor Core 64개 | 64GB LPDDR5 | 204.8GB/s | 275 TOPS | 15–60W | RJ45, 최대 10GbE |
| AGX Orin 32GB | 8-core Cortex-A78AE | 1792-core Ampere, Tensor Core 56개 | 32GB LPDDR5 | 204.8GB/s | 200 TOPS | 15–40W | RJ45, 최대 10GbE |
| Orin NX 16GB | 8-core Cortex-A78AE | 1024-core Ampere, Tensor Core 32개 | 16GB LPDDR5 | 102.4GB/s | 100 TOPS (Super 157) | 10–25W (Super 40W) | 1GbE |
| Orin Nano 8GB | 6-core Cortex-A78AE | 1024-core Ampere, Tensor Core 32개 | 8GB LPDDR5 | 68GB/s (Super 102GB/s) | 40 TOPS (Super 67) | 7–15W (Super 25W) | 1GbE |

수치는 NVIDIA 공개 자료 기준이며, 사용하는 장비의 공식 datasheet로 다시 확인한다(8장 미결 사항).

- **저장 장치.** AGX Orin 개발자 키트는 64GB eMMC를 내장하고, M.2 Key M 슬롯(PCIe Gen4 x4)에 NVMe SSD를 장착할 수 있다. KVSwap 연구는 AGX Orin에서 NVMe 약 1.8GB/s, eMMC 약 250MB/s의 대역폭을 보고했다.
- **전력 모드.** `nvpmodel`로 전력 모드를 바꾸면 CPU, GPU, EMC 클럭이 함께 바뀐다. 연산 성능과 I/O 처리 성능이 같이 영향을 받는다.

**본 연구에 대한 시사점**

1. **메모리 대역폭 경쟁.** LLM decode는 매 토큰마다 가중치 전체를 읽으므로 메모리 대역폭이 성능을 결정한다. 같은 메모리 컨트롤러를 쓰는 저장 I/O 처리가 decode 속도에 직접 영향을 줄 수 있다.
2. **page cache의 메모리 점유.** page cache와 파일 시스템 캐시가 GPU가 쓸 수 있는 메모리를 줄인다. Lustre OSD 백엔드로 ZFS를 쓰면 ARC 캐시도 같은 메모리를 사용한다.
3. **원격 접근이 로컬보다 느림.** 개발자 키트의 NIC 대역폭(1GbE 약 117MB/s, 10GbE 약 1.1GB/s)이 NVMe 대역폭보다 낮다. 데이터센터와 달리 원격 접근이 로컬 접근보다 느리다.

### 2.3 IoT 애플리케이션에서의 LLM 활용

LLM을 IoT에 적용하는 연구는 크게 다섯 가지 형태로 나뉜다.

| 활용 | 입력 | 출력 | 요구 특성 |
|---|---|---|---|
| 이상 원인 설명 | 센서·음향 특징 요약, 이상 탐지 결과, 설비 정보 | 원인 후보와 근거 | 긴 컨텍스트, 도메인 지식 |
| 운영자 질의 응답 | 매뉴얼, 최근 로그·센서 구간, 질문 | 답변, 조치 절차 | 긴 공통 prefix 반복, 낮은 응답 지연 |
| 로그 분석 | 시스템·설비 로그 | 이상 로그 판정, 요약 | 긴 입력, 로그 형식 적응 |
| 멀티모달 판독 | 이미지, 음향 | 판독 결과 | VLM, 큰 입력 |
| 에이전트 제어 | 상태 요약, 정책 | 제어 명령 | 도구 호출, 정확한 출력 형식 |

이 활용들의 공통점은 다음과 같다.
- 입력에 반복되는 긴 공통 부분(시스템 지시문, 매뉴얼)과 시간적으로 겹치는 데이터 구간(최근 센서·로그)이 포함된다. 그래서 KV cache를 재사용할 여지가 크다.
- 설비와 공정이 바뀌면 응답 품질이 떨어지므로 현장 데이터로 주기적으로 적응해야 한다.
- 데이터 반출 제한과 지연 요구 때문에 엣지 실행이 선호된다. 단, 장치 한 대의 자원 한계 때문에 여러 장치의 협력이 필요하다.

관련 조사 연구로 "When IoT Meet LLMs"(2024), LLM 기반 엣지 인텔리전스 조사(Friha et al., 2024)가 있다. LLM 기반 로그 분석은 Loghub 데이터셋을 기준으로 활발히 연구되고 있다.

### 2.4 LLM 추론과 학습의 구조, 그리고 저장 I/O

#### 2.4.1 Transformer 구조와 추론 단계

Decoder-only LLM은 임베딩 layer, L개의 transformer layer, 출력 head로 구성된다. 각 transformer layer는 attention 블록과 MLP 블록으로 이루어지며, 파라미터는 대부분 transformer layer에 있다. 추론은 두 단계로 나뉜다.

| 단계 | 내용 | 성능 결정 요인 |
|---|---|---|
| Prefill | 입력 프롬프트 전체를 한 번에 처리해 KV cache를 만든다. | 연산량 (약 2 × 파라미터 수 × 입력 토큰 수 FLOP + attention 항) |
| Decode | 토큰을 하나씩 생성한다. 매 토큰마다 가중치 전체와 누적 KV를 읽는다. | 메모리 대역폭 |

- TTFT(첫 토큰까지의 시간)는 prefill 시간이 결정한다.
- TPOT(토큰당 생성 시간)는 decode 속도가 결정한다.

#### 2.4.2 KV cache

Attention은 이전 토큰들의 Key와 Value를 다시 사용하므로, 이를 저장해 두는 것이 KV cache이다. 토큰당 KV 크기는 다음과 같다.

```
KV bytes/token = 2 (K, V) × L (layer 수) × H_kv (KV head 수) × d_head (head 차원) × b (원소 바이트)
```

GQA(Grouped Query Attention)를 쓰는 최신 모델은 H_kv가 작아 KV 크기가 줄었다. 그래도 긴 컨텍스트에서는 세션 하나의 KV가 GB 단위가 된다. KV를 재사용하면 같은 prefix의 prefill을 다시 계산하지 않아도 되므로 TTFT가 크게 줄어든다. vLLM의 PagedAttention과 automatic prefix caching, SGLang의 RadixAttention은 GPU 메모리 안에서 KV를 재사용한다. CachedAttention, Mooncake, LMCache는 KV를 CPU 메모리와 SSD 같은 하위 계층으로 확장한다.

**후보 모델의 구조와 크기** (FP16 기준, 부록 A의 식으로 계산)

| 모델 | 파라미터 | Layer 수 | Q head | KV head | head 차원 | hidden | FP16 가중치 | KV/토큰 |
|---|---|---|---|---|---|---|---|---|
| Llama-3.1-8B | 8.0B | 32 | 32 | 8 | 128 | 4096 | 약 16GB | 128KiB |
| Qwen3-8B | 8.2B | 36 | 32 | 8 | 128 | 4096 | 약 16.4GB | 144KiB |
| Qwen2.5-32B | 32.5B | 64 | 40 | 8 | 128 | 5120 | 약 65GB | 256KiB |
| Qwen3-32B | 32.8B | 64 | 64 | 8 | 128 | 5120 | 약 65.6GB | 256KiB |
| Llama-3.1-70B | 70.6B | 80 | 64 | 8 | 128 | 8192 | 약 141GB (INT4 약 40GB) | 320KiB |

#### 2.4.3 병렬화 방식과 엣지

여러 장치로 모델을 나누는 방법은 두 가지이다.

| 방식 | 분할 방법 | 통신 | 엣지 적합성 |
|---|---|---|---|
| Tensor Parallelism | layer 내부 행렬을 장치들이 나눔 | layer마다 all-reduce | 고대역폭 연결이 필요해서 1–10GbE 엣지에는 부적합 |
| Pipeline Parallelism | 연속된 layer 구간을 장치에 배정 (stage) | stage 경계에서 activation만 전달 (토큰당 hidden × b 바이트, 32B 모델 기준 10KiB) | 엣지 분산 추론의 표준 방식 |

파이프라인 병렬에서 처리량은 가장 느린 stage가 결정한다. 그래서 각 stage의 연산량을 균형 있게 맞추는 분할이 중요하다.

#### 2.4.4 적응 학습과 어댑터

LoRA는 원래 가중치를 고정하고, 각 layer의 일부 projection에 저랭크 행렬(A, B)을 추가해 학습한다. QLoRA는 기본 가중치를 4-bit로 양자화한 상태에서 LoRA를 학습해 메모리 사용을 더 줄인다. 학습 결과물인 어댑터는 원래 모델보다 훨씬 작다(32B 모델, rank 16, q/k/v/o 기준 약 80MB). 서빙할 때는 기본 가중치에 어댑터를 적용한다. 체크포인트는 다음 항목으로 구성되며, 학습 중 주기적으로 저장된다.
- 어댑터 파라미터
- optimizer 상태 (Adam의 1차·2차 모멘트)
- 학습 진행 정보

여러 어댑터를 동시에 서빙하는 시스템으로 S-LoRA, Punica가 있고, 엣지용으로 EdgeLoRA가 있다.

#### 2.4.5 LLM 라이프사이클의 저장 I/O 유형

| I/O 유형 | 발생 시점 | 크기 | 패턴 | 성능 영향 |
|---|---|---|---|---|
| 가중치 로드 | 시작, 재분할, 장애 복구 | 수 GB–수십 GB | 순차 읽기 | 서비스 시작·복구 시간 |
| KV 저장 | 요청 처리 후 | 세션당 수백 MB–GB | 순차 쓰기(append) | 저장 위치 노드의 부하 |
| KV 로드 | 같은 prefix의 요청 도착 시 | 세션당 수백 MB–GB | 순차 읽기 | TTFT |
| 체크포인트 | 학습 중 주기적 | 수백 MB–수십 GB | 버스트 쓰기 | 학습 정지 시간, 동시 서빙 지연 |
| 어댑터 배포 | 학습 종료 후 | 수십–수백 MB | 쓰기 1회, 읽기 stage 수만큼 | 적응 결과 반영 지연 |
| IoT 수집 | 계속 | 레코드 수백 B–파일 수 GB | 소파일 쓰기, 대용량 순차 쓰기 | 배경 부하 |
| 학습 데이터 읽기 | 학습 중 | 수 GB | 순차·무작위 읽기 | 학습 속도 |

### 2.5 분산 파일 시스템과 Lustre

#### 2.5.1 DFS 개요

DFS는 여러 서버의 저장 장치를 하나의 이름 공간으로 묶어 제공한다.

| DFS | 구조 | 특징 |
|---|---|---|
| Lustre | 메타데이터와 데이터 서버 분리 | HPC와 클라우드(Amazon FSx for Lustre 등)에서 널리 쓰인다. 파일 단위로 데이터 서버를 명시적으로 지정할 수 있다. |
| Ceph | CRUSH 해시로 객체 위치 결정 | 블록·객체·파일을 모두 지원한다. 위치를 사용자가 직접 지정하기 어렵다. |
| BeeGFS | Lustre와 유사한 구조 | 설정이 간단하다. |
| HDFS | 대용량 블록, 복제 | 배치 분석용이며 POSIX를 완전히 지원하지 않는다. |

본 연구는 Lustre를 사용한다. 이유는 다음과 같다.
1. 파일과 디렉터리 단위로 데이터 서버(OST)를 직접 지정할 수 있다.
2. 레이아웃, 복제, QoS, 작업별 통계 기능을 갖춘다.
3. 원 IFLustre 연구를 계승한다.

#### 2.5.2 Lustre 구조

| 구성 요소 | 역할 |
|---|---|
| MGS (Management Server) | 파일 시스템 설정 관리 |
| MDS / MDT (Metadata Server / Target) | 이름 공간, 파일 속성, 파일 레이아웃 관리 |
| OSS / OST (Object Storage Server / Target) | 파일 데이터 저장. OSS 하나가 OST 하나 이상을 관리 |
| Client | POSIX 인터페이스 제공. 파일 레이아웃에 따라 OST에 직접 I/O |
| LNet | Lustre 네트워크 계층. TCP, InfiniBand 등 지원 |
| OSD 백엔드 | OST의 로컬 파일 시스템. ldiskfs(ext4 기반) 또는 ZFS |

#### 2.5.3 Lustre 레이아웃과 관리 기능

| 기능 | 설명 | 본 연구에서의 용도 |
|---|---|---|
| Striping (`lfs setstripe -c -S -i`) | 파일을 stripe size 단위로 나누어 stripe count개 OST에 round-robin 배치. `-i`로 시작 OST 지정 | LG 파일과 KV 파일의 OST 지정 |
| 디렉터리 default layout | 디렉터리에 레이아웃을 설정하면 새 파일이 상속 | stage별 KV 디렉터리 배치 |
| PFL (Progressive File Layout) | 파일 오프셋 구간마다 다른 레이아웃(컴포넌트) 지정 | 단일 가중치 파일의 layer 구간별 OST 지정 (대안) |
| DoM (Data-on-MDT) | 작은 파일의 앞부분을 MDT에 저장 | IoT 소파일 수집 부하 감소 (선택) |
| FLR (File Level Redundancy, `lfs mirror`) | 파일 단위 복제본(mirror) 생성, 읽기 시 사용 가능한 mirror 선택 | 가중치와 공통 prefix KV의 장애 대비 복제 |
| `lfs migrate` | 파일 데이터를 새 레이아웃으로 이동 | 재분할과 재배치 |
| OST pool | OST 묶음에 이름을 붙여 배치 대상으로 사용 | 노드 그룹 지정 (선택) |
| NRS (Network Request Scheduler) TBF | 요청 분류(jobid, NID, opcode 등)별 토큰 버킷 속도 제한. 단위는 RPC/s | 체크포인트와 재배치 I/O 속도 제한 |
| Job stats | jobid별 OST/MDT I/O 통계 | I/O 클래스별 부하 측정 |
| CPT (CPU Partition Table) | Lustre 서비스 스레드를 CPU 파티션에 고정 | OSS 스레드와 LLM 연산의 코어 분리 |
| Client cache 제한 (`llite.*.max_cached_mb`) | client page cache 상한 | unified memory 점유 제한 |

#### 2.5.4 엣지에서 Lustre를 쓸 때의 고려 사항

- **client와 서버의 동시 운용.** Lustre 운영 지침은 같은 노드에서 client와 서버(OSS)를 함께 운용하는 구성을 권장하지 않는다. 메모리 압박 상황에서 서버와 client가 서로의 메모리 회수를 기다리는 문제가 생길 수 있기 때문이다. 엣지의 하이퍼컨버지드 구성에서는 이 구성을 피할 수 없으므로 동작 안정성을 직접 확인해야 한다(4.1절).
- **같은 노드 OST 접근 경로.** 같은 노드의 OST에 접근할 때 NIC를 거치지 않는 LNet 경로가 쓰이는지 확인이 필요하다. 이 경로에서도 Lustre RPC 처리 비용(CPU, 메모리 복사)은 남는다.
- **OSD 백엔드.** ZFS를 사용하면 ARC 캐시가 unified memory를 점유하므로 크기를 제한해야 한다.

### 2.6 원 연구: IFLustre

#### 2.6.1 MASCOTS 2022 버전

IFLustre는 Lustre에서 여러 애플리케이션이 OSS를 공유할 때 생기는 간섭을 줄이는 저장 할당 기법이다. 구성 요소는 두 가지이다.

- **Application Analyzer**
  - 같은 애플리케이션 이름의 과거 실행 로그(SLURM, Lustre Monitoring Tool, Darshan)로 stripe count와 stripe size를 결정한다.
  - 처리량과 실행 시간을 ML 모델로 예측한다.
- **OSS Allocator:** 세 가지 정책을 순서대로 적용한다.
  1. Interference-free allocation: 다른 애플리케이션이 쓰지 않는 OSS를 할당한다.
  2. Throughput-aware allocation: 여유 처리량이 충분한 OSS를 할당한다.
  3. Runtime-aware allocation: 가장 빨리 비는 OSS를 기다렸다가 할당한다.

관찰 결과는 다음과 같다.
- 애플리케이션 성능은 가장 느린 OSS가 결정한다.
- 공유 상황에서도 많은 OSS를 쓰는 것이 유리할 수 있다.
- 총 처리량이 하드웨어 한계에 가까우면 OSS 공유가 성능을 떨어뜨린다.

평가에서 Lustre 기본 설정 대비 최대 47% 개선했다.

#### 2.6.2 IEEE IoTJ 버전 (Reject & Resubmit)

클라우드 DFS 환경에서 IoT 데이터셋 6종을 대상으로 확장했다. 다음 두 가지를 추가했다.
- 파일 크기에 따른 striping 효과 차이
- 쓰기 시점 배치와 읽기 최적 배치의 차이 (read-aware relocation)

최대 47.8% 개선을 보고했다.

#### 2.6.3 새 환경에서의 한계

| 항목 | IFLustre의 가정 | 엣지 LLM 환경 |
|---|---|---|
| 노드 역할 | 스토리지 서버와 연산 노드가 분리 | 같은 장치가 둘 다 수행 |
| 간섭 범위 | OSS 사이 | OSS 사이 + 저장 I/O와 LLM 연산 사이 |
| 데이터 구조 | 애플리케이션별 파일 집합 | layer 구조를 가진 가중치, KV, 어댑터 |
| 소비 위치 | 고려하지 않음 | 객체마다 소비 노드가 정해짐 (pipeline stage) |
| 워크로드 | 독립 애플리케이션 | 서로 데이터를 주고받는 라이프사이클 |
| 결정 근거 | 같은 애플리케이션의 과거 로그 | 새 어댑터·모델 버전은 로그 없음 |
| 결정 시점 | 애플리케이션 시작 시 1회 | 이벤트마다 반복 |
| 파일 크기 | IoT 소파일 비중이 커서 효과 제한 | MB–GB 단위 객체가 중심 |

### 2.7 관련 연구

#### 2.7.1 저장 I/O 간섭과 QoS

대규모 공유 스토리지에서 애플리케이션 간 I/O 간섭은 오래 연구된 주제이다.
- **스케줄링·조정:** CALCioM은 애플리케이션 사이의 I/O 조정 정책을 동적으로 선택한다. GIFT는 쿠폰 기반 throttle-and-reward로 대역폭을 공정하게 나눈다. LoomIO는 객체 단위 간섭을 감시해 요청을 조정한다. Lustre NRS TBF는 규칙 기반 토큰 버킷으로 클라이언트나 작업별 요청 속도를 제한한다.
- **배치·설정:** iez는 OSS 용량 불균형을 줄이도록 데이터를 배치한다. DCA-IO와 A2FL은 실행 로그나 실시간 접근 패턴으로 파일 레이아웃을 자동 조정한다.
- **클라우드 장치 수준:** Radio, Jaliminche et al., CoFS는 클라우드 저장 장치 수준의 간섭을 분석하거나 공정성을 보장한다.

이 연구들은 모두 스토리지 서버가 연산과 분리된 환경에서 스토리지 사이의 간섭을 다룬다.

| 연구 | 발표 | 방법 | 환경 | 본 연구와의 차이 |
|---|---|---|---|---|
| CALCioM | IPDPS 2014 | 애플리케이션 간 I/O 조정 정책 동적 선택 | HPC | 연산 간섭 없음 |
| GIFT | FAST 2020 | 쿠폰 기반 대역폭 throttle/reward | HPC PFS | 연산 간섭 없음 |
| iez | IPDPS 2019 | OSS 용량 불균형 완화 배치 | HPC PFS | 소비 위치·연산 미고려 |
| LoomIO | TPDS 2021 | 객체 수준 간섭 감시와 요청 조정 | DFS | 연산 간섭 없음 |
| Lustre NRS TBF | SC 2017 | 규칙 기반 토큰 버킷 요청 스케줄러 | Lustre | 본 연구에서 실행 수단으로 사용 |
| DCA-IO | CCGrid 2019 | 실행 로그 기반 DFS 설정 조정 | HPC | 로그 필요, 단일 앱 |
| A2FL | IPDPS 2024 | 실시간 접근 패턴 기반 레이아웃 | HPC | 연산 간섭 없음 |
| Radio | CLOUD 2022 | 가상화 디스크 I/O 간섭 분석 | 클라우드 | 장치 수준, 연산 간섭 없음 |
| Jaliminche et al. | SoCC 2023 | SSD 간섭 모델링 | 클라우드 SSD | 장치 수준 |
| CoFS | TCAD 2024 | NVMe SSD 공정성 | 클라우드 | 장치 수준 |
| IFLustre | MASCOTS 2022 | 예측 기반 OSS 할당 3정책 | Lustre | 본 연구의 기반 |

#### 2.7.2 자원 공존과 간섭 격리

데이터센터에서는 지연에 민감한 서비스와 배치 작업을 같은 서버에 두면서 간섭을 줄이는 연구가 있었다. Heracles, PARTIES, Caladan은 CPU 코어, 캐시, 메모리 대역폭, 네트워크를 동적으로 나누어 지연 민감 서비스의 SLO를 지킨다. 실시간 시스템 분야의 MemGuard는 멀티코어에서 코어별 메모리 대역폭을 예약한다.

본 연구의 저장-연산 간섭은 이 문제의 한 형태이다. 차이는 두 가지이다.
1. 간섭원이 DFS의 서버 측 I/O 처리이다. 그래서 어느 장치가 그 I/O를 처리할지를 데이터 배치로 바꿀 수 있다.
2. 피해자가 파이프라인 stage여서, 한 장치의 지연이 전체로 전파된다.

| 연구 | 발표 | 방법 | 본 연구와의 차이 |
|---|---|---|---|
| Heracles | ISCA 2015 | 지연 민감 서비스와 배치 작업의 자원 분할 | 저장 배치로 간섭 위치를 바꾸는 방법 없음 |
| PARTIES | ASPLOS 2019 | 여러 지연 민감 서비스의 자원 분할 | 동일 |
| Caladan | OSDI 2020 | 마이크로초 단위 코어 재할당 | 동일 |
| MemGuard | RTAS 2013 | 코어별 메모리 대역폭 예약 | 통합 메모리 SoC 격리 수단으로 참고 |

#### 2.7.3 LLM 모델 로딩과 오프로딩

모델 로딩 시간과 메모리 부족 문제를 저장 계층으로 해결하는 연구가 있다.
- **로딩 시간 단축:** ServerlessLLM은 서버리스 환경에서 다계층 체크포인트 저장과 로딩 최적화로 cold start를 줄인다.
- **오프로딩 실행:** LLM in a flash, PowerInfer, PowerInfer-2, FlexGen은 가중치 일부를 플래시나 CPU 메모리에 두고 필요한 부분만 읽는다.
- **엣지 분산:** prima.cpp는 mmap 기반 오프로딩과 파이프라인을 결합해 가정용 장치 클러스터에서 30–70B 모델을 실행한다.
- **I/O 특성 분석:** NVMe SSD로 모델과 KV를 오프로딩할 때의 I/O 특성을 분석한 연구도 있다.

이 연구들은 장치 한 대 또는 서버 한 대의 로컬 저장 계층을 다룬다. 여러 장치가 공유하는 DFS에서 저장 위치가 다른 장치의 연산에 주는 영향은 다루지 않는다.

| 연구 | 발표 | 방법 | 환경 | 본 연구와의 차이 |
|---|---|---|---|---|
| ServerlessLLM | OSDI 2024 | 다계층 체크포인트 저장, 빠른 로딩 | GPU 서버 | 공유 DFS, 연산 간섭 없음 |
| LLM in a flash | ACL 2024 | 플래시에서 필요한 가중치만 로드 | 장치 1대 | 로컬 플래시 |
| PowerInfer | SOSP 2024 | hot/cold 뉴런 분리, CPU-GPU 혼합 | PC | 단일 장치 |
| PowerInfer-2 | arXiv 2024 | 스마트폰 플래시 기반 추론 | 스마트폰 | 단일 장치 |
| FlexGen | ICML 2023 | GPU/CPU/디스크 오프로딩 스케줄 | 단일 GPU | 처리량 중심 오프라인 |
| prima.cpp | arXiv 2025 | mmap 오프로딩 + 파이프라인 링 | 가정용 장치 클러스터 | 장치별 로컬 디스크 |
| NVMe 오프로딩 I/O 특성 분석 | ACM 2025 | 모델·KV 오프로딩 I/O 측정 | NVMe SSD | 단일 장치 측정 |

#### 2.7.4 KV cache 저장과 재사용 (데이터센터)

- **GPU 메모리 안의 재사용:** vLLM은 PagedAttention으로 KV를 블록 단위로 관리하고, 같은 prefix를 공유한다. SGLang은 radix tree로 prefix를 재사용한다.
- **하위 계층으로의 확장:** CachedAttention은 멀티턴 대화의 KV를 CPU 메모리와 디스크에 저장해 재사용한다. Mooncake는 KV cache를 중심으로 prefill과 decode를 분리하고, 클러스터의 CPU 메모리와 SSD를 KV 저장 풀로 사용한다. LMCache는 엔진과 독립적인 KV cache 계층으로, CPU 메모리, 로컬·원격 디스크, Redis 등에 KV를 저장한다(기본 chunk 256토큰).
- **전송·압축·저장 최적화:** CacheGen은 KV를 압축해 네트워크로 스트리밍한다. CacheBlend는 prefix가 아닌 위치의 KV 재사용을 다룬다. IMPRESS는 중요도에 따라 prefix KV를 다계층 저장 장치에 나누어 둔다.

이 연구들은 GPU 서버와 분리된 메모리·스토리지 풀을 가정하고, 고대역폭 네트워크(RDMA 등)를 사용한다.

| 연구 | 발표 | 방법 | 본 연구와의 차이 |
|---|---|---|---|
| vLLM (PagedAttention) | SOSP 2023 | 블록 단위 KV 관리, prefix 공유 | GPU 메모리 안에서만 재사용 |
| SGLang (RadixAttention) | NeurIPS 2024 | radix tree prefix 재사용 | 동일 |
| CachedAttention | USENIX ATC 2024 | 멀티턴 KV를 메모리·디스크 계층에 저장 | 서버 내부 계층 |
| Mooncake | FAST 2025 | KV 중심 분리형 서빙, 클러스터 메모리·SSD 풀 | 분리형 풀, RDMA |
| LMCache | arXiv 2025 | 엔진 독립 KV 계층, 다양한 저장 백엔드 | 연산 간섭 고려 없음 |
| CacheGen | SIGCOMM 2024 | KV 압축과 스트리밍 | 네트워크 전송 중심 |
| CacheBlend | EuroSys 2025 | 비-prefix KV 재사용 | 재사용 범위 확장 |
| IMPRESS | FAST 2025 | 중요도 기반 다계층 prefix KV 저장 | 단일 서버 다계층 |

#### 2.7.5 엣지 KV cache 오프로딩

최근 엣지 장치에서 KV를 SSD로 오프로딩하는 연구가 나오고 있다.
- **KVSwap:** Jetson AGX Orin에서 NVMe와 eMMC를 대상으로 장문 컨텍스트 KV를 디스크로 교체한다.
- **Dual-Blade:** 파일 기반 KV 오프로딩이 커널 page cache에 의존해 cache thrashing을 일으키는 문제를 지적한다. 이를 해결하기 위해 page cache 경로와 NVMe 직접 경로를 함께 쓴다.
- **MemLLM:** 장치 내 RAG를 위해 미리 계산한 KV를 플래시에 저장한다.
- **MTDS:** 자원 제약 환경에서 DRAM과 SSD에 걸친 다계층 KV 저장을 제안한다.

이 연구들은 장치 한 대의 로컬 저장 장치를 다룬다. Dual-Blade가 지적한 page cache 문제는 unified memory를 쓰는 Jetson에서 저장 I/O가 연산 메모리에 영향을 준다는 본 연구의 가설과 같은 방향이다. 다만 본 연구는 다음을 추가로 다룬다.
- 여러 장치가 서로의 KV를 저장해 주는 공유 DFS 구성
- 그 저장 처리가 다른 장치의 LLM 연산에 주는 영향
- 학습 I/O와의 공존

| 연구 | 발표 | 환경 | 방법 | 본 연구와의 차이 |
|---|---|---|---|---|
| KVSwap | arXiv 2025 | Jetson AGX Orin, NVMe/eMMC | 디스크 인지 KV 교체 | 단일 장치, 로컬 디스크 |
| Dual-Blade | arXiv 2026 | 엣지 장치, NVMe | page cache 경로와 NVMe 직접 경로 병행 | 단일 장치 |
| MemLLM | arXiv 2026 | Jetson Orin 등 | 저장 장치 내 RAG KV 가속 | 단일 장치, RAG |
| MTDS | Complex & Intelligent Systems 2025 | 자원 제약 엣지 | DRAM-SSD 다계층 KV | 단일 장치 |

#### 2.7.6 엣지 분산 LLM 추론

- **PipeEdge:** 이기종 엣지 장치에서 연산, 메모리, 네트워크를 고려한 파이프라인 분할을 제안했다.
- **EdgeShard:** 엣지 장치와 클라우드 서버에 걸쳐 장치 선택과 모델 분할을 동적 계획법으로 함께 결정한다. IEEE IoTJ에 발표되었으며, Jetson AGX Orin 12대 등으로 구성한 테스트베드를 사용했다.
- **Galaxy:** 엣지 장치 협력으로 transformer 추론을 수행한다.
- **LOIP:** Jetson AGX Orin과 Xavier NX로 구성한 클러스터에서 파이프라인과 layer 오프로딩을 결합해 70B 모델을 손실 없이 실행한다. 오프로딩된 layer 로드를 연산·통신과 겹치는 스케줄을 사용한다.
- **오픈소스:** exo, llama.cpp RPC.

이 연구들은 분할을 연산량, 메모리, 네트워크 기준으로 정한다. 저장 데이터의 위치, KV 저장, 학습 I/O가 분할에 주는 영향은 다루지 않는다.

| 연구 | 발표 | 환경 | 분할 기준 | 본 연구와의 차이 |
|---|---|---|---|---|
| PipeEdge | DSD 2022 | 이기종 엣지 | 연산, 메모리, 네트워크 | 저장 I/O 미고려 |
| EdgeShard | IEEE IoTJ 2025 | Jetson Orin + 클라우드 | 장치 선택 + 분할 (동적 계획법) | 저장 I/O, KV, 학습 미고려 |
| Galaxy | INFOCOM 2024 | 엣지 장치 협력 | 연산, 통신 | 동일 |
| LOIP | arXiv 2025 | Jetson AGX Orin, Xavier NX | 파이프라인 + 로컬 layer 오프로딩 | 장치별 로컬 저장, 공유 DFS 없음 |
| prima.cpp | arXiv 2025 | 가정용 장치 | 장치 성능, 디스크 속도 | 장치별 로컬 디스크 |

#### 2.7.7 엣지 학습과 어댑터 서빙

- **엣지 학습:** PockEngine은 중요하지 않은 layer와 채널의 갱신을 생략하는 희소 역전파로 Jetson Orin에서 LLaMA2-7B 미세조정 속도를 높였다. MobiZO는 zeroth-order 방식으로 엣지 장치의 LLM 미세조정 메모리를 줄인다.
- **어댑터 서빙:** S-LoRA와 Punica는 많은 LoRA 어댑터를 동시에 서빙하는 GPU 커널과 메모리 관리를 제안했다. EdgeLoRA는 엣지 장치에서 여러 사용자의 LoRA 어댑터 서빙을 다룬다.

이 연구들은 학습 또는 서빙 중 하나에 집중한다. 같은 클러스터에서 학습이 만든 체크포인트와 어댑터가 서빙 I/O와 공존하는 상황은 다루지 않는다.

| 연구 | 발표 | 내용 | 본 연구와의 차이 |
|---|---|---|---|
| LoRA / QLoRA | ICLR 2022 / NeurIPS 2023 | 저랭크 적응 / 4-bit 기반 LoRA | 본 연구에서 학습 방식으로 사용 |
| PockEngine | MICRO 2023 | 엣지 희소 역전파 미세조정 | 학습 단독 |
| MobiZO | EMNLP 2025 | 엣지 zeroth-order 미세조정 | 학습 단독 |
| S-LoRA | MLSys 2024 | 대규모 LoRA 동시 서빙 | 데이터센터 서빙 |
| Punica | MLSys 2024 | 다중 LoRA 서빙 커널 | 데이터센터 서빙 |
| EdgeLoRA | arXiv 2025 | 엣지 다중 테넌트 LoRA 서빙 | 서빙 단독, 저장 I/O 미고려 |

#### 2.7.8 학습 체크포인트

- **CheckFreq:** 체크포인트 빈도를 동적으로 정하고, 스냅샷과 저장을 파이프라인화한다.
- **Check-N-Run:** 추천 모델 체크포인트의 크기를 줄인다.
- **Gemini:** 다른 노드의 CPU 메모리에 체크포인트를 두어 복구를 빠르게 한다.
- **DataStates-LLM:** LLM 체크포인트를 지연·비동기 방식으로 저장한다.
- **ByteCheckpoint:** 대규모 모델 개발용 통합 체크포인트 시스템을 제안한다.

이 연구들은 학습 처리량과 복구 시간을 목표로 한다. 체크포인트 I/O가 같은 저장 계층을 쓰는 서빙의 지연에 주는 영향은 다루지 않는다.

| 연구 | 발표 | 방법 | 본 연구와의 차이 |
|---|---|---|---|
| CheckFreq | FAST 2021 | 동적 빈도, 2단계 스냅샷·저장 | 서빙 공존 미고려 |
| Check-N-Run | NSDI 2022 | 차분·양자화 체크포인트 | 동일 |
| Gemini | SOSP 2023 | 원격 CPU 메모리 체크포인트 | 동일 |
| DataStates-LLM | HPDC 2024 | 지연 비동기 체크포인트 | 동일 |
| ByteCheckpoint | NSDI 2025 | 통합 체크포인트 시스템 | 동일 |

#### 2.7.9 LLM 기반 시스템·스토리지 튜닝

- **스토리지:** ION은 LLM으로 HPC I/O 추적(Darshan)을 해석해 성능 문제를 진단한다. STELLAR(SC 2025)는 검색 증강 생성, 도구 사용, 다중 에이전트를 결합해 병렬 파일 시스템 설정을 자율적으로 튜닝한다. 처음 보는 애플리케이션에서도 다섯 번 이내 시도로 최적에 가까운 설정을 찾는다고 보고했다.
- **데이터베이스:** DB-BERT, GPTuner, λ-Tune은 언어 모델로 매뉴얼과 작업 특성을 해석해 파라미터를 튜닝한다.

이 연구들은 한 애플리케이션 또는 한 데이터베이스의 설정을 반복 실행으로 오프라인 탐색한다. 본 연구의 플래너는 다음 점에서 다르다.
- 서비스 중에 이벤트가 발생할 때마다 온라인으로 재계획한다.
- 여러 I/O 클래스와 저장-연산 간섭을 함께 다룬다.
- 엣지 장치 위에서 실행된다.

| 연구 | 발표 | 대상 | 방식 | 본 연구와의 차이 |
|---|---|---|---|---|
| ION | HotStorage 2024 | HPC I/O 진단 | LLM 추적 해석 | 진단 중심, 오프라인 |
| STELLAR | SC 2025 | 병렬 파일 시스템 튜닝 | RAG + 도구 + 다중 에이전트, 반복 실행 | 단일 앱, 오프라인, 연산 간섭 없음 |
| DB-BERT | SIGMOD 2022 | DB 파라미터 | 매뉴얼 해석 + 강화학습 | DB 대상 |
| GPTuner | VLDB 2024 | DB 파라미터 | LLM + 베이지안 최적화 | DB 대상 |
| λ-Tune | SIGMOD 2025 | DB 설정 | LLM 프롬프트 기반 | DB 대상 |

### 2.8 종합 비교와 연구 공백

| 분류 | 대표 연구 | 엣지 | 저장-연산 공존 | 분산 추론 | KV 저장 | 학습 I/O | 공유 DFS | 온라인 재계획 |
|---|---|---|---|---|---|---|---|---|
| 저장 간섭/QoS | GIFT, iez, LoomIO, IFLustre | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | △ |
| 자원 공존 격리 | Heracles, PARTIES, Caladan | ✗ | △ | ✗ | ✗ | ✗ | ✗ | ✓ |
| 모델 로딩/오프로딩 | ServerlessLLM, FlexGen, prima.cpp | △ | ✗ | △ | ✗ | ✗ | ✗ | ✗ |
| 데이터센터 KV 저장 | Mooncake, LMCache, CachedAttention, IMPRESS | ✗ | ✗ | ✗ | ✓ | ✗ | △ | ✗ |
| 엣지 KV 오프로딩 | KVSwap, Dual-Blade | ✓ | △ | ✗ | ✓ | ✗ | ✗ | ✗ |
| 엣지 분산 추론 | EdgeShard, LOIP, PipeEdge | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | △ |
| 엣지 학습/어댑터 | PockEngine, EdgeLoRA | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ |
| 체크포인트 | CheckFreq, Gemini, DataStates-LLM | ✗ | ✗ | ✗ | ✗ | ✓ | △ | ✗ |
| LLM 기반 튜닝 | ION, STELLAR, GPTuner | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| **본 연구** | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

(✓: 주요 대상, △: 일부 고려, ✗: 다루지 않음. 각 연구의 세부 특성은 투고 전 원문으로 재확인한다.)

**연구 공백**

| ID | 공백 |
|---|---|
| G1 | 저장 서버와 LLM 연산 노드가 같은 엣지 클러스터에서, 저장 I/O가 LLM 연산에 주는 간섭은 측정되거나 모델링되지 않았다. |
| G2 | 엣지 분산 추론의 분할 결정은 저장 데이터의 위치를 고려하지 않는다. DFS 배치 연구는 연산 분할을 고려하지 않는다. 두 결정이 서로 영향을 주는 환경에서 이를 함께 결정하는 방법이 없다. |
| G3 | 수집, 적응, 서빙의 I/O가 한 클러스터에서 공존할 때의 시점과 속도 제어가 다뤄지지 않았다. |
| G4 | 엣지 현장의 잦은 이벤트와 자연어 운영 정책 아래에서의 온라인 재계획이 다뤄지지 않았다. 기존 LLM 기반 튜닝은 오프라인 단일 애플리케이션을 대상으로 한다. |

---

## 3. Design

### 3.1 대상 환경

#### 3.1.1 하드웨어와 역할

| 노드 | 장비 (기본 가정) | Lustre 역할 | 연산 역할 |
|---|---|---|---|
| N0 | Jetson AGX Orin 64GB + NVMe | MGS/MDS(MDT), OSS(OST0), client | 제어 모듈(플래너, 검증기, 실행기, telemetry 집계), W1 수집, W2 적응 학습 |
| N1 | Jetson AGX Orin 64GB + NVMe | OSS(OST1), client | W3 stage 1 |
| N2 | Jetson AGX Orin 64GB + NVMe | OSS(OST2), client | W3 stage 2 |
| N3 | Jetson AGX Orin 64GB + NVMe | OSS(OST3), client | W3 stage 3 |
| N4 | Jetson AGX Orin 64GB + NVMe | OSS(OST4), client | W3 stage 4 |

- 장비가 AGX Orin이 아니면 3.3.3절의 대체 구성을 쓴다.
- 네트워크: 같은 스위치에 연결한다. NIC 속도(1GbE / 10GbE)는 확인이 필요하다.
- 네트워크 대역폭 민감도 실험에서는 `tc`로 대역폭을 제한한다.

#### 3.1.2 소프트웨어

| 구성 | 내용 |
|---|---|
| OS | JetPack 6.x (L4T, Ubuntu 22.04 기반) |
| Lustre | 설치 버전, OSD 백엔드(ldiskfs / ZFS)를 기록한다. PFL, FLR, NRS TBF, jobstats, CPT 지원 여부를 확인한다. |
| 딥러닝 | PyTorch (JetPack용 빌드), HF transformers, PEFT, bitsandbytes 또는 대체 4-bit 양자화 |
| 플래너 실행 | llama.cpp (CUDA 빌드), JSON schema 기반 제약 디코딩 |
| 측정 | tegrastats 또는 jtop, `lctl get_param`, `/proc`, fio, iperf3 |

### 3.2 대상 시나리오와 워크로드

#### 3.2.1 시나리오

공장 엣지 사이트에서 설비 이상 분석 LLM 서비스를 운영한다.
- 현장 운영자는 생산 라인별로 설비 상태와 이상 원인을 자연어로 질의한다.
- 서비스는 다음을 입력으로 응답한다.
  - 해당 라인의 설비 매뉴얼
  - 최근 센서·음향 이상 탐지 결과
  - 네트워크·시스템 로그 구간
- 설비 상태와 공정이 바뀌므로, 사이트는 수집된 데이터로 모델을 주기적으로 적응시키고 새 어댑터를 서비스에 반영한다.
- 데이터는 사이트 밖으로 반출하지 않는다.

#### 3.2.2 워크로드 정의

| ID | 이름 | 내용 | 실행 위치 | 사용 데이터·도구 |
|---|---|---|---|---|
| W1 | Ingest | IoT 데이터를 Lustre에 계속 저장한다. W2 학습 데이터의 원천이며, 클러스터의 배경 I/O 부하가 된다. | N0 (게이트웨이 역할) | 원 논문 6종 데이터셋, Loghub, RIoTBench 레코드 스트림, `iotbenchlustre.py` 확장 |
| W2 | Adapt | W1 데이터로 만든 지시-응답 샘플로 서빙 모델과 같은 base 모델에 QLoRA 적응 학습을 수행한다. 학습 중 체크포인트를 저장하고, 종료 시 어댑터를 생성한다. | N0 | HF PEFT, 3.3절 모델 |
| W3 | Serve | 운영자 질의를 4-stage 파이프라인으로 처리한다. KV cache를 Lustre에 저장하고 재사용한다. 새 어댑터가 준비되면 교체한다. | N1–N4 | 자체 파이프라인 런타임 (3.10절) |

**데이터 흐름:** W1 데이터 → W2 학습 샘플 생성 → W2 학습 → 체크포인트·어댑터 → W3 서빙 → 질의·응답 로그가 W1 데이터에 추가

#### 3.2.3 W3 요청 구성

| 구성 요소 | 길이 (토큰) | 재사용 특성 |
|---|---|---|
| 시스템 지시문 | 약 300 | 모든 요청 공통 |
| 라인별 설비 매뉴얼 | 4k–8k | 같은 라인 요청 공통 (라인 4개 가정) |
| 최근 센서·로그 구간 | 1k–8k | 같은 라인의 연속 요청끼리 시간 구간이 겹친다 (슬라이딩 윈도우) |
| 질문 | 30–100 | 재사용 없음 |
| 출력 | 128–256 | – |

- 멀티턴 세션: 1–5턴, 턴 간격 30초–10분.
- 도착 패턴: 4.2.3절.

### 3.3 모델 선정

#### 3.3.1 선정 기준

1. **분할 필요성:** 서빙 모델의 가중치는 노드 1대의 메모리를 넘어야 한다. 넘지 않으면 파이프라인 분할(⑧)이 필요 없다.
2. **GQA 구조:** KV head 수가 작아 KV 크기가 현실적이어야 한다.
3. **실행 환경 지원:** HF transformers와 llama.cpp에서 모두 실행할 수 있어야 한다.
4. **적응 학습 가능성:** 같은 base 모델로 엣지에서 QLoRA 학습이 가능해야 한다.
5. **공개 여부:** 가중치가 공개되어 재현할 수 있어야 한다.

#### 3.3.2 기본 구성 (AGX Orin 64GB × 5)

| 역할 | 모델 | 정밀도 | 크기 | 실행 노드 | 선정 이유 |
|---|---|---|---|---|---|
| 서빙 (W3) | Qwen3-32B | FP16 (BF16) | 약 65.6GB | N1–N4 (stage당 LG 4개) | 노드 1대(64GB)에 들어가지 않음. GQA(KV head 8개). HF와 llama.cpp 지원 |
| 서빙 대안 | Qwen2.5-32B-Instruct | FP16 | 약 65GB | N1–N4 | Qwen3와 구조가 같아 KV 크기 동일. 비교·대체용 |
| 서빙 성능 민감도 | Qwen3-32B | INT8 weight-only | 약 33GB | N1–N4 | decode 속도와 가중치 I/O 크기 변화에 따른 결과 비교 |
| 서빙 규모 민감도 | Llama-3.1-70B-Instruct | INT4 (AWQ/GPTQ) | 약 40GB | N1–N4 | layer 80개, KV 320KiB/토큰 |
| 적응 학습 (W2) | Qwen3-32B | 4-bit NF4 (QLoRA) | base 약 18–20GB + 어댑터·활성화 | N0 | 서빙 모델과 같은 base |
| 대용량 체크포인트 민감도 | Qwen3-1.7B | BF16 full fine-tuning | 체크포인트 약 20GB 이상 | N0 | 체크포인트 버스트 크기 변화 실험 |
| 플래너 (⑦) | Qwen3-8B | Q4_K_M (GGUF) | 약 5GB | N0 | JSON 출력과 도구 호출 성능, 메모리 사용 적음 |
| 플래너 대안 | Qwen2.5-7B-Instruct | Q4_K_M | 약 4.7GB | N0 | 비교용 |

**서빙 모델 분할 (기본)**
- Qwen3-32B는 64 layer이다. g=4로 묶어 LG 16개를 만든다(LG0–LG15).
- 임베딩(약 1.56GB)은 stage 1에, 출력 head(약 1.56GB)와 최종 norm은 stage 4에 붙인다.
- 초기 분할: `{N1: LG0–3 + 임베딩, N2: LG4–7, N3: LG8–11, N4: LG12–15 + head}`
- 노드별 가중치 메모리: N1·N4 약 17.2GB, N2·N3 약 15.6GB

**적응 학습 설정 (기본)**

| 항목 | 값 |
|---|---|
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 |
| 대상 projection | q, k, v, o |
| 시퀀스 길이 | 1024–2048 |
| micro-batch / gradient accumulation | 1 / 16 |
| gradient checkpointing | 사용 |
| 라운드당 step | 약 200 (학습 처리량 측정 후 조정) |
| 체크포인트 간격 | 50 step |

학습 처리량은 측정 후 라운드 길이를 조정한다(예상치는 4.2.2절).

#### 3.3.3 대체 구성

| 장비 | 서빙 모델 | 적응 학습 | 플래너 |
|---|---|---|---|
| Orin NX 16GB × 5 | Qwen3-8B 또는 Llama-3.1-8B FP16 (약 16GB, 4-stage) | 같은 모델 QLoRA | Qwen3-1.7B 또는 Qwen3-4B Q4 |
| Orin Nano 8GB × 5 | Qwen3-8B FP16 (4-stage, stage당 약 4.1GB) | Qwen3-1.7B LoRA | Qwen3-1.7B Q4 |
| AGX Orin 32GB × 5 | Qwen3-32B INT8 (약 33GB, 4-stage) | Qwen3-8B QLoRA | Qwen3-8B Q4 |

**텍스트 외 데이터 (선택):** 이미지 데이터(VisDrone)를 서빙 입력으로 쓰려면 Qwen2.5-VL-7B 같은 VLM을 추가 워크로드로 둔다.

### 3.4 데이터 객체와 I/O 특성

기본 구성(Qwen3-32B, g=4) 기준 계산값이다. 계산식은 부록 A에 있다.

| 객체 | 파일 경로 | 단위 크기 | 전체 크기 | 생성 | 소비 | 접근 패턴 | 요구사항 |
|---|---|---|---|---|---|---|---|
| 가중치 | `weights/lg{i}.safetensors` | LG당 약 3.9GB | 약 65.6GB | 사전 배치 | 해당 LG 담당 stage | 시작·재분할·복구 시 순차 읽기 | 로드 시간, 장애 시 가용성 |
| 임베딩/헤드 | `weights/embed.safetensors`, `weights/head.safetensors` | 각 약 1.56GB | – | 사전 배치 | stage 1 / stage 4 | 로드 시 읽기 | 로드 시간 |
| KV cache | `kv/{prefix_hash}/lg{i}.kv` | LG당 토큰당 16KiB, 256토큰 chunk 4MiB | 8k 토큰 세션: LG 파일당 128MiB, 전체 2GiB | 해당 LG 담당 stage | 같은 LG 담당 stage | chunk append 쓰기, 재사용 시 순차 읽기 | TTFT |
| 체크포인트 | `ckpt/r{round}/step{s}/` | 약 0.5GB | 라운드당 수 GB | N0 학습 | N0 (학습 복구 시) | 주기적 버스트 쓰기 | 학습 정지 최소, 서빙 영향 최소 |
| 어댑터 | `adapters/v{n}/lg{i}.safetensors` | LG당 약 5MB (FP16) | 약 80MB | N0 학습 | 해당 LG 담당 stage | 쓰기 1회, 배포 시 읽기 | freshness |
| IoT 데이터 | `iot/{dataset}/...` | 수백 B–4GB | 설정에 따름 | N0 수집 | N0 학습 | 연속 쓰기, 학습 시 읽기 | 처리량 |
| 학습 샘플 | `train/r{round}/*.jsonl` | 수 MB | 라운드당 수십–수백 MB | N0 | N0 | 순차 쓰기·읽기 | – |

**참고 수치**
- Stage당 KV: 토큰당 64KiB, 8k 세션당 512MiB
- Stage 간 activation: 토큰당 10KiB

### 3.5 문제 정의

#### 3.5.1 문제 서술

하이퍼컨버지드 엣지 DFS에서 W1–W3가 동시에 실행될 때 다음 세 가지를 결정하는 문제이다.

| 기호 | 결정 대상 |
|---|---|
| P | LG를 추론 노드에 배정하는 파이프라인 분할 |
| M | 각 데이터 객체(가중치, KV, 어댑터, 체크포인트, IoT 데이터)의 저장 OST, stripe count, stripe size, mirror 위치 |
| S | 백그라운드 I/O(체크포인트, 재배치, 수집)의 실행 시점과 속도 상한 |

목표는 서빙 SLO(TTFT p99)를 만족하면서 서빙 처리량을 최대화하고, 어댑터 freshness를 정책 상한 안으로 유지하는 것이다.

#### 3.5.2 정식화

**입력**

| 분류 | 항목 |
|---|---|
| 노드 k | 연산 성능 프로파일, 메모리 용량 MemCap_k, OST 대역폭과 용량 OstCap_k, NIC 대역폭 |
| 모델 | LG별 연산 시간 c_i, LG별 가중치 크기 w_i, LG별 토큰당 KV 크기 v_i |
| 워크로드 | 요청 도착률 λ(t), prefix 재사용 분포, 컨텍스트 길이 분포, 학습 라운드 주기, 체크포인트 크기·간격, 수집률 |
| 정책 | TTFT SLO, TPOT SLO, 우선순위, 시간대별 제약, 체크포인트 간격 상한 CkptMax, freshness 상한 FreshMax |

**목적과 제약**

```
maximize    Throughput(P, M, S) = 1 / max_k T_k(P, M, S)

subject to  TTFT_p99(P, M, S)   <= SLO_TTFT
            TPOT_p99(P, M, S)   <= SLO_TPOT
            mem_k(P, M)         <= MemCap_k          for all nodes k
            used_j(M)           <= OstCap_j          for all OSTs j
            ckpt_interval(S)    <= CkptMax
            freshness(S, M)     <= FreshMax          (정책에 따라 선택)
            P는 연속 분할 (각 stage는 연속된 LG 구간)
```

T_k의 정의는 3.9.3절의 비용 모델이다.

#### 3.5.3 문제가 성립하는 이유

다음 세 조건이 동시에 성립하기 때문에 이 문제가 생긴다. 셋 중 하나라도 없으면 문제는 기존 연구로 해결된다.
1. 모델이 노드 1대에 들어가지 않는다 → 분할이 필요하다.
2. 생성 노드와 소비 노드가 다른 데이터가 있다 → 공유 저장이 필요하다.
3. 엣지에는 별도 스토리지 계층이 없다 → 저장 서버와 연산 노드가 같다.

### 3.6 문제를 어렵게 만드는 요인

| ID | 요인 | 설명 | 관련 배경 |
|---|---|---|---|
| D1 | 저장-연산 결합 | OST가 연산 노드에 있다. 어떤 OST로 I/O를 보내면 그 노드의 OSS 처리가 같은 노드의 CPU와 unified memory를 사용해 LLM 연산이 느려질 수 있다. 데이터 배치를 정하는 것이 곧 노드별 연산 부하를 정하는 것이다. | 2.2, 2.5.4 |
| D2 | 파이프라인 병목 | 처리량은 가장 느린 stage가 결정한다. 한 노드에 I/O가 몰리면 다른 노드에 여유가 있어도 전체 성능이 떨어진다. 원 IFLustre 관찰("가장 느린 OSS가 성능을 결정")의 연산 버전이다. | 2.4.3, 2.6 |
| D3 | P와 M의 상호 의존 | P가 바뀌면 각 객체의 소비 노드가 바뀌어 최적 M이 바뀐다. 반대로 M이 정해져 있으면 P를 바꿀 때 이동해야 할 데이터량과 원격 읽기량이 달라져서 최적 P가 바뀐다. | 2.7.6 |
| D4 | I/O 클래스 간 요구 충돌 | KV는 지연에 민감하고 서빙 중 계속 발생한다. 체크포인트는 처리량 중심이고 버스트로 발생한다. 두 I/O가 같은 OST나 NIC를 쓰면 KV 읽기가 지연된다. | 2.4.5 |
| D5 | 시간에 따른 변화 | 적응 라운드마다 새 어댑터가 생긴다. 장애, 부하 변화, 운영 정책 변경이 발생한다. 새 객체에는 과거 실행 이력이 없어서 로그 기반 결정을 쓸 수 없다. | 2.6.3 |

### 3.7 연구 질문

| ID | 질문 | 관련 공백 | 답하는 실험 |
|---|---|---|---|
| RQ1 | 하이퍼컨버지드 엣지 노드에서 저장 I/O는 같은 노드의 LLM 연산을 얼마나 지연시키는가? 주된 경로는 CPU, 메모리 대역폭, page cache 중 무엇인가? | G1 | O1, O2, O3 |
| RQ2 | 파이프라인 분할(P)과 데이터 배치(M)를 함께 결정하면, 각각 독립적으로 결정할 때보다 서빙 성능과 복구 시간이 얼마나 개선되는가? | G2 | O4, O6, S2, S5 |
| RQ3 | KV, 체크포인트, 수집 I/O의 배치·시점·속도를 어떻게 제어해야 서빙 SLO를 유지하면서 적응 학습과 어댑터 배포를 지연 없이 수행할 수 있는가? | G3 | O5, S3, S4 |
| RQ4 | 이벤트 발생 시 LLM 플래너와 검증기로 재계획하면, 규칙 기반·탐색 기반 방식과 비교해 결과 품질, 정책 준수, 결정 비용이 어떻게 다른가? | G4 | S1, S6 |

### 3.8 해결 대상

해결 대상은 다섯 가지이다. 번호는 기존 논의의 번호(②③⑤⑦⑧)를 유지한다. 서술은 의존 관계 순서(⑧ → ② → ⑤ → ③ → ⑦)를 따른다. 각 항목은 같은 형식으로 작성한다: 정의 → 해결해야 하는 이유 → 세부 문제 → 해결 방법 → 검증 방법 → 관련 연구와의 차이 → 원 IFLustre와의 관계.

| 번호 | 해결 대상 | 대응 요인 | 대응 RQ |
|---|---|---|---|
| ⑧ | 분산 추론의 분할과 가중치 배치 | D1, D2, D3 | RQ2 |
| ② | KV cache 저장과 재사용 | D1, D4 | RQ2, RQ3 |
| ⑤ | 적응 학습 체크포인트와 어댑터 배포 | D4, D5 | RQ3 |
| ③ | 저장-연산 간섭 측정과 완화 | D1, D2 | RQ1 |
| ⑦ | 이벤트 기반 재계획 (LLM 플래너) | D3, D5 | RQ4 |

#### 3.8.1 ⑧ 분산 추론의 분할과 가중치 배치

**정의**

모델의 LG를 N1–N4에 연속 구간으로 배정해 파이프라인 추론을 수행한다. 각 stage는 자기 LG의 가중치를 Lustre에서 읽어 메모리에 올린다. stage 간에는 activation을 TCP로 전달한다.

**해결해야 하는 이유**

1. **모델이 노드 1대에 들어가지 않는다.** Qwen3-32B FP16 가중치(약 65.6GB)는 AGX Orin 64GB의 전체 메모리보다 크다. 양자화로 1대에 올리더라도 KV, 운영체제, Lustre에 쓸 메모리가 부족하다.
2. **가중치 로드 시간이 곧 서비스 중단 시간이다.** 로드는 시작, 재분할, 장애 복구 때 발생한다. 로드하는 동안 해당 stage는 요청을 처리하지 못한다.
3. **기본 레이아웃은 모든 노드에 부하를 준다.** Lustre 기본 레이아웃(stripe count 1, 시작 OST 자동 선택)에서는 LG 파일들이 OST 전체에 흩어진다. 그래서 한 stage가 로드할 때도 모든 노드에 서버 측 I/O가 생기고, 대부분의 읽기가 NIC를 거친다. 다른 stage의 연산도 함께 느려진다(D1, D2).
4. **장애 시 데이터도 함께 사라진다.** 노드 장애가 나면 그 노드의 연산과 OST가 함께 사라진다. 그 OST에만 있던 LG 파일은 읽을 수 없게 되어 복구가 불가능해진다.
5. **분할과 배치는 따로 정할 수 없다.** 연산량만 보고 분할하면, 어떤 노드는 자기 LG 외에 다른 객체의 I/O까지 받아서 병목이 될 수 있다(D3).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 8a | 분할 P 선택: LG별 연산 시간, 노드별 I/O 부하, 메모리를 함께 고려 |
| 8b | 가중치 배치: LG 파일의 OST와 stripe count |
| 8c | 장애 대비: mirror 위치 선택 |
| 8d | 재분할: 이동량 최소화, 이동 중 서빙 영향 최소화 |

**해결 방법**

1. **LG 단위 파일 (8b, 8d)**
   - 가중치를 LG 단위 파일로 저장한다(`weights/lg{i}.safetensors`, 약 3.9GB).
   - 재분할할 때 LG 파일 단위로 이동할 수 있다.
   - 단일 파일에 PFL 컴포넌트로 구간별 OST를 지정하는 방식은 재분할 시 레이아웃 재구성이 복잡하다. 그래서 대안으로만 둔다.
2. **기본 배치 (8b)**
   - LG 파일을 소비 노드의 OST에 둔다(`lfs setstripe -c 1 -i <소비 노드 OST>`).
   - 로드할 때 NIC를 쓰지 않고, 서버 측 부하도 자기 노드에만 생긴다.
3. **예외 배치 (8b)**
   - 비용 모델(3.9.3절)에서 소비 노드가 병목 stage로 계산될 때 적용한다.
   - 여유 노드의 OST에 둘 때의 max_k T_k와 비교해 작은 쪽을 선택한다.
4. **stripe count (8b)**
   - 기본값은 1이다.
   - O1 측정에서 단일 OST 읽기 속도가 로드 시간 목표를 만족하지 못할 때만 2를 쓴다(소비 노드 OST + 여유 노드 OST).
5. **mirror (8c)**
   - FLR로 각 LG 파일의 mirror를 1개 만든다.
   - 위치 결정 방법: 플래너가 시작 시점에 "노드 k 장애 시의 대체 분할 P'_k"를 노드별로 미리 계산한다. 노드 k의 LG 파일 mirror는 P'_k에서 그 LG를 넘겨받는 노드의 OST에 둔다.
   - 장애가 나면 새 담당 노드가 자기 로컬 OST의 mirror를 읽는다.
   - 가중치는 읽기 전용이므로 mirror 동기화 비용이 없다.
6. **분할 선택 (8a)**
   - LG 16개를 4 stage로 나누는 연속 분할은 C(15,3)=455개이다.
   - 후보마다 비용 모델로 max_k T_k와 메모리 제약을 계산해 최적 분할을 고른다.
   - 노드 수와 LG 수가 커지면 동적 계획법으로 푼다.
7. **재분할 (8d)**
   - 새 P에서 소비 노드가 바뀐 LG 파일만 이동한다(`lfs migrate -i <새 OST>`).
   - 이동 순서는 새 담당 노드의 로드가 필요한 순서를 따른다.
   - 서빙 중 이동은 NRS TBF로 속도 상한을 둔다.

**검증 방법**

| 항목 | 비교 |
|---|---|
| 초기 로드 시간 | 기본 레이아웃 vs 소비 노드 배치 vs 제안 기법 |
| 로드 중 다른 stage의 처리량 변화 | 위와 같음 |
| 재분할 시 이동 바이트와 소요 시간 | 위와 같음 |
| 장애 복구 시간 | mirror 없음 vs 임의 위치 mirror vs 대체 분할 기준 mirror |

**관련 연구와의 차이**

EdgeShard, PipeEdge, LOIP는 연산량, 메모리, 네트워크로 분할을 정한다. 본 기법은 분할 결정에 노드별 저장 I/O 부하를 포함한다. 또한 분할 결과로 데이터 배치를 함께 정한다. 그리고 장애 시 대체 분할을 기준으로 복제 위치를 정한다.

**원 IFLustre와의 관계**

- stripe count와 시작 OST 지정(`lfs setstripe -c -i`)을 그대로 사용한다.
- 할당 기준을 "OSS 여유 처리량"에서 "소비 노드와 연산 부하"로 확장한다.

#### 3.8.2 ② KV cache 저장과 재사용

**정의**

각 stage는 자기 LG 구간의 KV를 생성한다. 이를 Lustre에 저장하고, 같은 prefix를 가진 요청이 다시 오면 prefill을 다시 계산하지 않고 저장된 KV를 읽어서 사용한다.

**해결해야 하는 이유**

1. **Orin에서 긴 컨텍스트 prefill은 비용이 크다.**

   | 항목 | 추정값 | 비고 |
   |---|---|---|
   | Qwen3-32B 8k 토큰 prefill 연산량 | 약 6.1e14–6.8e14 FLOP | 선형 항 약 5.4e14 + attention 항 약 0.7e14(causal)–1.4e14 (부록 A) |
   | 4-stage 파이프라인 prefill 시간 | 수 초~십수 초 | 노드당 유효 연산 성능 가정에 따른 범위 (O4에서 측정) |
   | 같은 구간 KV 읽기 시간 (stage당 512MiB를 병렬로) | 로컬 NVMe 약 0.3초, 원격 10GbE 약 0.5초, 원격 1GbE 약 4.5초 | O1, O4에서 측정 |

   KV를 읽는 것이 다시 계산하는 것보다 빠를 가능성이 높고, 그 차이가 TTFT 차이로 이어진다.
2. **IoT 질의는 재사용률이 높다.** 같은 라인 질의는 같은 시스템 지시문과 설비 매뉴얼(4k–8k 토큰)을 포함한다. 같은 라인의 연속 질의는 겹치는 센서·로그 구간을 포함한다(3.2.3절).
3. **재사용은 시간 간격을 두고 일어난다.** 교대 근무, 멀티턴 대화의 휴지, 라인별 질의 주기 때문에 같은 prefix가 몇 분에서 몇 시간 뒤에 다시 나온다. 메모리 안의 KV는 다른 세션에 밀려나거나 재분할·재시작 때 사라진다.
   - 메모리 여유 추정(AGX Orin 64GB): 가중치 약 17GB, 운영체제와 런타임 약 5GB, Lustre와 page cache 수 GB를 빼면 노드당 KV에 쓸 수 있는 메모리는 30GB대이다. 이는 stage당 8k 세션 약 60–70개에 해당한다.
   - 하루 동안 라인과 운영자가 만드는 세션 수와 재사용 간격을 고려하면, 메모리 밖의 저장 계층이 필요하다.
   - 메모리가 작은 장비(NX 16GB, AGX 32GB)에서는 이 제약이 더 강하다.
4. **KV I/O는 간섭 문제의 원인이자 피해자이다.** 서빙 중 계속 발생하는 KV 쓰기는 저장 위치 노드의 부하를 만든다. KV 읽기 지연은 TTFT로 이어진다. 그래서 KV 배치는 3.8.4절의 간섭 문제와 직접 연결된다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 2a | 저장 단위: chunk 크기, 파일 단위, 메타데이터 연산 수 |
| 2b | 배치: LG별 KV 파일의 OST |
| 2c | 읽기 시점: 요청 도착 후 동기 읽기 vs 미리 읽기 |
| 2d | 재계산 vs 읽기: chunk별로 어느 쪽이 빠른지 (OST 부하에 따라 달라짐) |
| 2e | 재분할 후 호환: stage 구간이 바뀌어도 기존 KV 사용 가능 여부 |
| 2f | 용량 관리: 삭제 정책, 공통 prefix 고정 |

**해결 방법**

1. **저장 단위 (2a)**
   - 파일 1개 = (prefix 그룹, LG). 경로: `kv/{prefix_hash}/lg{i}.kv`
   - 256토큰 chunk를 파일 안에 오프셋으로 이어 쓴다(append).
   - chunk별 오프셋과 해시는 파일별 인덱스(`.idx`)에 기록한다.
   - 크기: LG 기준 chunk당 4MiB, 8k 토큰 파일 128MiB.
   - chunk마다 파일을 만들면 세션 하나에 파일 512개가 생긴다(chunk 32개 × LG 16개). 이 방식은 세션당 파일 16개로 줄여 MDS 메타데이터 연산을 줄인다. 원 IFLustre 연구의 관찰(소파일 메타데이터 비용)을 반영한 설계이다.
2. **prefix 식별 (2a)**
   - chunk 해시 체인을 사용한다: `h_n = hash(h_{n-1}, tokens_n)`.
   - 요청이 도착하면 가장 긴 일치 prefix를 찾는다.
   - 공통 prefix(시스템 지시문 + 매뉴얼)는 별도 prefix 그룹으로 저장해 여러 세션이 공유한다.
3. **배치 (2b)**
   - LG i의 KV 파일은 LG i 가중치와 같은 규칙(3.8.1절)으로 OST를 정한다. 기본은 소비 노드 OST이고, 병목이면 여유 노드 OST이다.
   - 실제 적용은 LG별 디렉터리에 default layout을 설정해 새 파일이 상속하게 한다.
   - 비용 모델이 병목 노드를 바꾸면, 새로 생성되는 파일의 위치만 바꾼다(디렉터리 default layout 갱신). 기존 파일은 재사용 빈도가 높은 것만 이동한다.
4. **읽기 시점 (2c)**
   - 요청이 도착하면 일치 범위를 확인하고, 각 stage의 KV Manager가 자기 LG 파일을 동시에 읽는다(stage 간 병렬).
   - stage 1이 새 토큰의 prefill을 시작하는 동안 뒤쪽 stage는 KV 읽기를 진행한다.
   - 운영 정책에 반복 시간대(교대 시작 등)가 있으면, 해당 라인의 공통 prefix를 미리 읽는다(플래너 조치 `prefetch_prefix`).
5. **재계산 vs 읽기 (2d)**
   - chunk별로 예상 읽기 시간(현재 OST 부하를 반영한 F_k)과 예상 재계산 시간(LG 연산 프로파일)을 비교해 작은 쪽을 고른다.
   - OST가 체크포인트로 바쁜 구간에는 재계산이 선택될 수 있다.
6. **재분할 호환 (2e)**
   - KV를 LG 단위로 저장하므로, stage 구간이 바뀌어도 새 담당 노드가 LG 파일을 그대로 읽는다.
   - 위치가 원격이면 재사용 빈도에 따라 이동 여부를 정한다.
7. **용량 관리 (2f)**
   - 재사용 빈도를 가중치로 준 LRU를 적용한다.
   - 공통 prefix는 고정(pin)하고, FLR mirror를 1개 둔다(장애 대비 겸용).
   - OST 사용률이 임계값을 넘으면 오래된 세션 KV부터 삭제한다.

**검증 방법**

| 항목 | 비교 |
|---|---|
| TTFT p50/p99 | 재사용 없음 vs 메모리 안 재사용만 vs Lustre 기본 레이아웃 저장 vs 제안 기법 |
| prefix hit rate, 저장 KV 용량 | 위와 같음 |
| 미리 읽기 효과 | 미리 읽기 사용 vs 미사용 |
| 재계산/읽기 선택 정확도 | 실제 빠른 쪽과의 일치율 |
| 재분할 직후 TTFT | 위와 같음 |
| MDS 메타데이터 연산 수 | chunk별 파일 vs (prefix, LG) 파일 |

**관련 연구와의 차이**

CachedAttention, Mooncake, LMCache는 연산 노드와 분리된 메모리·스토리지 풀을 쓴다. KVSwap과 Dual-Blade는 장치 한 대의 로컬 SSD를 쓴다. 본 기법은 다음 세 점에서 다르다.
1. 여러 노드가 서로의 KV를 저장해 주는 공유 DFS를 쓴다.
2. 저장 위치를 정할 때 그 노드의 연산 부하를 고려한다.
3. KV를 LG 단위로 저장해 분할 변경과 호환되게 한다.

**원 IFLustre와의 관계**

- read-aware relocation을 KV 파일에 적용한다(재사용 빈도와 소비 노드 기준 재배치).
- 소파일 메타데이터 비용에 대한 관찰을 파일 단위 설계에 반영한다.

#### 3.8.3 ⑤ 적응 학습 체크포인트와 어댑터 배포

**정의**

N0에서 W1 데이터로 만든 학습 샘플로 서빙 모델과 같은 base 모델(4-bit)에 QLoRA 적응 학습을 주기적으로 수행한다. 학습 중에는 체크포인트를 저장한다. 학습이 끝나면 어댑터를 LG 단위로 나누어 추론 stage에 배포하고, 서빙을 새 어댑터로 전환한다.

**해결해야 하는 이유**

1. **모델이 현장 변화를 따라가야 한다.** IoT 데이터의 분포는 설비 노후, 라인 변경, 계절 요인으로 바뀐다. 적응 없이 운용하면 응답 품질이 떨어진다.
2. **적응은 엣지 안에서 해야 한다.** 데이터 반출이 제한되기 때문이다.
3. **체크포인트가 KV I/O와 충돌한다.** 체크포인트는 수백 MB에서 수십 GB의 버스트 쓰기이다. 서빙 KV I/O와 같은 OST, NIC, 서버 측 처리 자원을 공유하므로 TTFT를 늘린다(D4).
4. **생성 위치와 소비 위치가 다르다.** 어댑터는 N0에서 생성되고 N1–N4가 소비한다. 생성 위치에 그대로 두면 모든 stage가 원격으로 읽고, N0의 서버 측 부하가 학습 연산과 겹친다.
5. **배포가 늦으면 적응 결과가 늦게 반영된다.** 어댑터 배포가 늦어지면 freshness가 커진다.
6. **이벤트를 만든다.** 학습 라운드는 새 객체(어댑터 버전)를 만든다. 원 IFLustre처럼 과거 로그로 결정하는 방식은 새 버전에 적용할 수 없다(D5). 그래서 ⑦의 재계획을 일으키는 주요 이벤트가 된다.

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 5a | 체크포인트를 쓸 OST |
| 5b | 체크포인트 쓰기 시점과 속도: 학습 진행 보장 vs 서빙 영향 |
| 5c | 어댑터 배포: LG 분할, 저장 위치, 로드, 버전 전환 |
| 5d | N0 학습 연산과 N0 OST를 I/O 수용 노드로 쓰는 것 사이의 충돌 |

**해결 방법**

1. **2단계 체크포인트 (5b)**
   - 1단계: 학습 프로세스가 체크포인트 상태를 메모리 버퍼에 복사한다. 학습 정지 시간은 이 복사 시간뿐이다.
   - 2단계: 별도 스레드가 Lustre로 비동기 flush한다(CheckFreq의 2단계 방식을 서빙 공존 환경에 맞게 적용).
2. **flush 대상 OST (5a, 5d)**
   - 후보 OST마다 비용 모델로 서빙 max_k T_k의 증가량과 N0 학습 시간 증가량을 계산해, 둘의 가중합이 최소인 OST를 고른다.
   - 기본 후보는 OST0이다. 단, N0가 학습 중이면 학습 연산과의 간섭도 계산에 넣는다.
3. **flush 속도 (5b)**
   - 체크포인트 I/O에 Lustre jobid를 부여한다(예: `ckpt.r{round}`).
   - NRS TBF 규칙으로 OST별 RPC 속도 상한을 둔다.
   - 상한값은 비용 모델에서 TTFT p99가 SLO를 넘지 않는 최대 I/O 부하로 계산한다.
4. **flush 시점 (5b)**
   - 최근 요청률 이동평균과 운영 정책의 시간대 정보로 저부하 구간을 예측해, 그 구간에 flush를 몰아 둔다.
   - 체크포인트 간격 상한(CkptMax)은 제약으로 유지한다. 상한에 도달하면 속도 제한 범위 안에서 즉시 flush한다.
5. **어댑터 배포 (5c)**
   1. 학습이 끝나면 어댑터 텐서를 LG 단위로 나눈다(`adapters/v{n}/lg{i}.safetensors`, LG당 약 5MB).
   2. 쓰는 시점에 각 파일의 OST를 LG 소비 노드로 지정한다. 이렇게 하면 이후 이동이 필요 없다(쓰기 시점 배치).
   3. 각 stage가 자기 LG 어댑터를 로드한다.
   4. 모든 stage의 로드가 완료되면 동시에 버전을 전환한다(2단계 전환: 준비 → 전환). 진행 중인 요청은 이전 버전으로 끝낸다.
6. **학습 제어 (5d)**
   - N0 부하가 서빙 SLO를 위협하는 경우(N0 OST가 KV 저장 대상이거나 N0가 대체 분할에 포함된 경우), 플래너가 학습 일시정지(`pause_train`)나 flush 지연을 선택할 수 있다.

**검증 방법**

| 항목 | 비교 |
|---|---|
| 체크포인트 중 TTFT p99와 시계열 | 같은 OST vs 다른 OST, TBF 유무, 시점 제어 유무 |
| 체크포인트 소요 시간, 학습 처리량(step/s), 학습 정지 시간 | 위와 같음 |
| freshness, 전환 중 서빙 중단 시간 | 생성 위치 저장 vs 쓰기 시점 소비 노드 배치 |
| 대용량 체크포인트(약 20GB 이상) 시 위 지표 | 위와 같음 |

**관련 연구와의 차이**

CheckFreq, Gemini, DataStates-LLM은 학습 처리량과 복구 시간을 목표로 한다. S-LoRA, EdgeLoRA는 어댑터 서빙만 다룬다. 본 기법은 체크포인트 I/O의 위치·시점·속도를 서빙 SLO 기준으로 정한다. 또한 어댑터를 생성 시점부터 소비 위치에 배치한다.

**원 IFLustre와의 관계**

- runtime-aware allocation(기다렸다가 할당)을 체크포인트 flush의 시점 제어와 속도 제한으로 확장한다.
- read-aware relocation 대신 쓰기 시점에 소비 위치를 지정한다.

#### 3.8.4 ③ 저장-연산 간섭 측정과 완화

**정의**

한 노드에서 OSS(서버 측)와 Lustre client가 처리하는 I/O가 같은 노드의 LLM 연산(추론 stage, 학습)을 지연시키는 현상이다. 이를 측정하고, 모델링하고, 완화한다.

**해결해야 하는 이유**

1. **엣지에는 스토리지 전용 노드가 없다.** 모든 OST가 연산 노드에 있다.
2. **메모리 대역폭을 나눠 쓴다.** Orin은 CPU와 GPU가 같은 LPDDR5 메모리와 메모리 컨트롤러(EMC)를 쓴다. OSS의 데이터 복사, 체크섬, 네트워크 처리가 메모리 대역폭을 사용한다. LLM decode는 메모리 대역폭이 성능을 결정하므로 이 영향을 직접 받을 수 있다(가설, O2에서 측정).
3. **메모리 용량을 나눠 쓴다.** page cache와 OSD 캐시(ZFS의 경우 ARC)가 GPU가 쓸 수 있는 메모리를 줄인다. Dual-Blade는 파일 기반 KV 오프로딩에서 page cache thrashing이 성능을 떨어뜨린다고 보고했다.
4. **CPU를 나눠 쓴다.** OSS 서비스 스레드와 네트워크 softirq가 CPU 코어를 사용한다. 이 작업은 LLM 런타임의 CPU 측 작업(커널 실행 준비, 스케줄링, activation 송수신)과 경쟁한다.
5. **파이프라인이 영향을 키운다.** 한 stage의 지연이 전체 처리량을 결정한다(D2).
6. **다른 요소들의 공통 입력이다.** ⑧, ②, ⑤의 배치 결정은 모두 "어느 노드에 I/O를 보내면 연산이 얼마나 느려지는가"를 기준으로 한다. 이 값(α)을 측정하지 않으면 배치 기준이 없다.
7. **안정성을 확인해야 한다.** client와 OSS의 동시 운용은 Lustre가 권장하지 않는 구성이다. 엣지에서는 피할 수 없으므로 메모리 압박 시 동작을 확인해야 한다(2.5.4절).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 3a | 크기: I/O 유형(읽기/쓰기, I/O 크기, 서버 측/client 측)별, LLM 단계(prefill/decode)별 지연 계수 α |
| 3b | 경로: CPU, 메모리 대역폭(EMC), page cache 중 주 원인 |
| 3c | 완화: 배치 외의 노드 내 격리 수단과 그 효과 |
| 3d | 안정성: client와 OSS 동시 운용 시 메모리 압박 상황의 동작 |

**해결 방법**

1. **측정 (3a, 3b)**
   - Node k에서 stage를 실행하는 동안, 다른 노드에서 Node k의 OST로 fio 부하를 건다(서버 측 부하).
   - Node k가 원격 OST를 읽는 경우도 같은 방식으로 측정한다(client 측 부하).
   - 부하 변수와 지표는 4.4절 O2에 정리했다.
2. **경로 분리 (3b)**

   | 경로 | 분리 방법 |
   |---|---|
   | CPU | CPU 분리를 적용한 경우와 비교 |
   | 메모리 대역폭 | EMC 사용률과 tokens/s의 상관 분석 |
   | page cache | 캐시 상한을 바꿔가며 비교 |

3. **모델링 (3a)**
   - 측정값으로 α_k(유형, 단계)를 회귀로 구한다.
   - 원 IFLustre의 예측 모델(선형·다항 회귀, random forest)을 재사용한다.
   - 비용 모델은 이 값으로 후보 배치별 stage 시간 증가를 계산한다.
4. **노드 내 격리 수단 (3c)**

   | 수단 | 방법 |
   |---|---|
   | CPU 분리 | Lustre CPT(`cpu_pattern`)로 OSS와 ptlrpc 스레드를 지정 코어에 고정한다. LLM 프로세스는 cgroup cpuset으로 나머지 코어에 둔다. |
   | page cache 상한 | client는 `llite.*.max_cached_mb`로 제한한다. OSS 측 read/writethrough cache 설정(예: `osd-ldiskfs.*.read_cache_enable`)은 버전별 파라미터 이름을 확인한다. ZFS를 쓰면 ARC 최대 크기를 제한한다. |
   | 속도 제한 | NRS TBF로 I/O 클래스별 상한을 둔다. |
   | 전력 모드 | `nvpmodel` 모드별로 α를 측정해 모드에 따른 비용 모델 값을 둔다. |

5. **안정성 확인 (3d)**
   - 메모리 사용을 높인 상태(대형 KV, 학습 동시 실행)에서 장시간 I/O를 실행한다.
   - hang, OOM, 성능 급락 여부를 확인한다.
   - 문제가 생기면 캐시 상한과 메모리 예약으로 대응한다.

**검증 방법**

| 항목 | 내용 |
|---|---|
| α 곡선 | I/O 부하에 따른 tokens/s 변화 (prefill/decode, 읽기/쓰기, 서버/client 측) |
| 경로 분해 | 격리 수단별 α 감소량 |
| 비용 모델 예측 오차 | 측정값 대비 예측값 (목표: 평균 오차 15% 이내) |

**관련 연구와의 차이**

Heracles, PARTIES, Caladan은 같은 서버의 자원을 나누어 간섭을 줄인다. 본 기법은 노드 내 격리에 더해 데이터 배치로 간섭을 어느 노드에 둘지 정한다. 기존 저장 간섭 연구(GIFT, LoomIO, IFLustre)는 스토리지 사이의 간섭만 다룬다.

**원 IFLustre와의 관계**

원 관찰("애플리케이션 성능은 가장 느린 OSS가 결정한다")을 연산 측으로 확장한다: "파이프라인 처리량은 가장 느린 stage가 결정하고, stage 속도는 같은 노드의 저장 I/O 부하에 영향을 받는다."

#### 3.8.5 ⑦ 이벤트 기반 재계획 (LLM 플래너)

**정의**

이벤트가 발생하면 현재 상태와 운영 정책을 입력받아 (P, M, S) 변경안을 생성하는 제어 모듈이다. N0에서 소형 LLM(Qwen3-8B Q4)으로 실행한다. 생성된 변경안은 비용 모델 기반 검증기가 검사한 뒤 적용한다.

**해결해야 하는 이유**

1. **결정을 반복해야 한다.** (P, M, S)는 한 번 정하고 끝나지 않는다. 다음 이벤트가 생길 때마다 다시 정해야 한다(D5).
   - 적응 라운드 시작과 종료 (새 어댑터)
   - 노드 장애와 복귀
   - 요청 부하 변화와 SLO 위반
   - 운영 정책 변경
2. **이력이 없다.** 원 IFLustre의 분석기는 같은 애플리케이션 이름의 과거 실행 로그로 설정을 정한다. 새 어댑터 버전이나 새 모델에는 이력이 없다.
3. **운영 정책이 자연어이다.** 운영 정책은 IoT 현장 운영자가 자연어로 표현한다. 예: "라인 3 질의를 우선 처리", "주간 근무 시간에는 체크포인트 최소화", "야간에 재학습", "정기 점검 동안 N2 사용 금지". 이를 목적 함수 가중치와 제약으로 바꿔야 한다. 수동으로 바꾸는 것은 현장 운영자에게 부담이다.
4. **변경 범위를 골라야 한다.** P 전체를 다시 계산하면 이동 비용이 크다. M 일부나 S만 바꾸면 비용이 작지만 효과도 제한된다. 이벤트마다 어느 범위까지 바꿀지 선택해야 한다.
5. **탐색 공간 밖의 조치가 있다.** 시간대 기반 미리 읽기, 학습 일시정지, 정비 일정에 맞춘 사전 재분할처럼 정책과 일정에 근거한 조치는 수치 탐색 공간에 넣기 어렵다.

**범위 한정**

- 노드 5개 규모에서는 비용 모델 기반 탐색으로 (P, M)의 수치 최적해를 구할 수 있다(분할 후보 455개).
- 따라서 플래너는 수치 최적화를 대체하지 않는다. 플래너의 역할은 다음 세 가지이다.
  1. 운영 정책을 목적·제약으로 변환
  2. 이벤트별 변경 범위 결정
  3. 탐색 공간 밖의 조치 제안
- 수치 타당성은 검증기가 보장한다.
- 평가에서는 탐색 기반(Search-only), 규칙 기반, LLM 단독(검증기 없음), LLM + 검증기를 직접 비교한다(4.5.2절 S6).

**세부 문제**

| ID | 세부 문제 |
|---|---|
| 7a | 상태 표현: telemetry를 LLM 입력 길이 안에서 요약 |
| 7b | 출력 형식: 실행 가능한 조치로 제한 |
| 7c | 정확성: 잘못된 계획의 적용 방지 |
| 7d | 비용: 플래너 실행이 N0의 연산과 메모리를 사용 |

**해결 방법**

1. **입력 (7a)**
   - JSON 상태 요약(2–4k 토큰): 노드별 CPU/GPU/EMC/메모리 사용률, OST별 부하와 사용량, stage latency, 현재 P, 객체 배치 요약, 진행 중인 학습 상태, 이벤트 내용
   - 운영 정책 텍스트
   - 모델 config 요약(LG 수, LG별 크기, KV 크기)
   - 관찰 규칙 요약(O1–O6 결과를 규칙 문장으로 정리)
   - 예시는 부록 B에 있다.
2. **출력 (7b)**
   - JSON 스키마로 제한한 조치 목록이다. llama.cpp의 JSON schema 제약 디코딩을 쓴다.
   - 조치 유형:

     | 조치 | 내용 |
     |---|---|
     | `repartition` | 새 분할 |
     | `set_layout` | 디렉터리·파일 레이아웃 |
     | `migrate` | 파일 이동 |
     | `mirror` | 복제 생성·삭제 |
     | `set_tbf` | TBF 규칙 |
     | `schedule_ckpt` | 체크포인트 시점·속도 |
     | `pause_train` / `resume_train` | 학습 정지·재개 |
     | `prefetch_prefix` | 공통 prefix 미리 읽기 |
     | `pin_prefix` | 공통 prefix 고정 |
     | `set_objective` | 목적 가중치·제약 갱신 |

3. **propose-verify 루프 (7c)**
   1. 플래너가 후보 계획 1–3개를 생성한다.
   2. 검증기가 제약(메모리, OST 용량, 연속 분할, 정책 금지 사항)을 검사한다.
   3. 검증기가 비용 모델로 예상 TTFT p99, 처리량, 이동 바이트, freshness를 계산한다.
   4. 통과한 후보 중 목적값이 가장 좋은 계획을 적용한다.
   5. 모두 실패하면 실패 사유를 입력에 추가해 재요청한다(최대 2회).
   6. 그래도 실패하면 규칙 기반 정책(3.9.7절의 확장 IFLustre 정책)을 적용한다.
4. **호출 빈도 (7d)**
   - 플래너는 이벤트가 발생할 때만 호출한다. 요청 단위 결정은 플래너가 만든 계획 테이블을 조회하는 fast path로 처리한다.
   - 이벤트가 연달아 발생하면 일정 시간(예: 10초) 동안 모아서 한 번 호출한다.
5. **비용 반영 (7d)**
   - 플래너는 N0에서 실행되므로, 그 실행 시간과 메모리 사용을 비용 모델의 C_0와 mem_0에 포함한다.
   - 결정 지연(이벤트 발생부터 적용까지)을 측정해 보고한다.

**검증 방법**

| 항목 | 내용 |
|---|---|
| 비교 대상 | Search-only, 규칙 기반, LLM-only, LLM + 검증기 |
| 지표 | SLO 달성률, 이동 바이트, 결정 지연, 정책 준수율, 유효하지 않은 계획 비율 |
| 처음 보는 시나리오 | 새 모델 크기, 새 정책 문장, 새 장애 패턴에서의 결과 |
| 플래너 모델 크기 영향 | Qwen3-1.7B / 4B / 8B 비교 |

**관련 연구와의 차이**

ION, STELLAR, GPTuner, λ-Tune은 애플리케이션이나 데이터베이스 하나의 설정을 반복 실행으로 오프라인 탐색한다. 본 플래너는 서비스 중에 이벤트마다 온라인으로 재계획하고, 비용 모델 검증기로 실행 전에 결과를 확인하며, 엣지 장치 위에서 실행된다.

**원 IFLustre와의 관계**

원 Application Analyzer(로그 기반 설정 결정과 ML 예측)를 두 부분으로 나눈다. 수치 예측은 비용 모델이 맡고, 결정은 플래너와 검증기가 맡는다.

### 3.9 통합 구성

#### 3.9.1 다섯 요소가 하나의 시스템이어야 하는 이유

다섯 요소는 따로 동작하는 기능이 아니다. 다음 네 가지 관계로 묶인다.

1. **같은 라이프사이클.** W1–W3는 데이터를 주고받는 하나의 반복 과정이다. ⑤가 만든 어댑터는 ⑧과 ②가 쓰는 서빙에 들어간다. 서빙 로그는 다시 W1 데이터가 된다.
2. **같은 자원.** 모든 노드가 저장과 연산을 함께 수행한다. 그래서 ⑧의 가중치 I/O, ②의 KV I/O, ⑤의 체크포인트 I/O가 모두 같은 노드들의 연산 자원을 사용한다(③).
3. **같은 단위.** 가중치, KV, 어댑터가 모두 LG 단위로 나뉜다. 그래서 ⑧의 분할 P 하나가 세 객체의 소비 노드를 동시에 정한다.
4. **같은 비용 모델.** 모든 결정이 하나의 식(3.9.3절)의 서로 다른 항을 바꾼다. ⑦은 이 식을 기준으로 이벤트마다 결정을 갱신한다.

#### 3.9.2 의존 관계

```
                    ③ 저장-연산 간섭 측정
                            │ α (비용 모델의 공통 입력)
                            ▼
 ┌───────────────────── 비용 모델 T_k ──────────────────────┐
 │                                                           │
 │   ⑧ 분할 P ───────▶ 모든 LG 객체의 소비 노드 결정           │
 │       │                    │                  │           │
 │       ▼                    ▼                  ▼           │
 │   가중치 배치          ② KV 배치            ⑤ 어댑터 배치     │
 │   (로드 I/O)           (서빙 중 지속 I/O)    체크포인트 시점·속도 │
 │                                              (버스트 I/O)  │
 └─────────────────────────────┬─────────────────────────────┘
                               │ L_k (노드별 I/O 부하), 이벤트
                               ▼
                 ⑦ 이벤트 발생 시 (P, M, S) 재결정
```

| 요소 | 다른 요소에 제공 | 다른 요소에서 받음 |
|---|---|---|
| ③ | α (모든 배치 결정의 기준) | 측정 대상 I/O 패턴 (⑧, ②, ⑤) |
| ⑧ | P (모든 LG 객체의 소비 노드), 가중치 로드 부하 | α (③), 재분할 지시 (⑦) |
| ② | 서빙 중 지속 I/O 부하, TTFT | P (⑧), α (③), 배치·미리 읽기 지시 (⑦) |
| ⑤ | 버스트 I/O 부하, 새 어댑터 이벤트 | P (⑧), α (③), 시점·속도 지시 (⑦) |
| ⑦ | (P, M, S) 갱신 | α (③), 현재 P (⑧), 부하 (②, ⑤), 운영 정책 |

#### 3.9.3 비용 모델

```
T_k = C_k(P) · (1 + α_k · L_k(M, S)) + F_k(M)

Throughput  = 1 / max_k T_k
TTFT        = min(prefill 재계산 시간, KV 로드 시간) + 파이프라인 전달 지연
mem_k       = 가중치(P) + KV 메모리 + 어댑터 + 캐시 상한 + 런타임 + (k=0이면 학습, 플래너)
```

| 기호 | 의미 | 측정 또는 계산 방법 | 관련 요소 |
|---|---|---|---|
| C_k(P) | stage k의 순수 연산 시간 | LG별 연산 시간 c_i를 오프라인에서 1회 프로파일링한 뒤 합산 (prefill/decode 구분) | ⑧ |
| L_k(M, S) | 노드 k의 OST(서버 측)와 client가 처리하는 I/O 부하 (MB/s) | 배치 M과 객체별 접근률(KV 쓰기·재사용률, 체크포인트 크기·주기, 수집률, 재배치량)로 계산하고, 실행 중 jobstats로 보정 | ②, ⑤, W1 |
| α_k | 단위 I/O 부하당 연산 지연 비율 | O2 측정 후 회귀 (I/O 유형, LLM 단계, 전력 모드별) | ③ |
| F_k(M) | 연산과 겹치지 않는 KV 읽기 대기 시간 | KV 크기, 경로 대역폭(로컬/원격, O1), 해당 OST 부하 | ② |

- 원 IFLustre는 이 모델에서 C_k=0, α=0이고 OSS 사이의 부하 L_k만 다루는 경우에 해당한다.
- α가 작게 측정되더라도 모델은 그대로 쓸 수 있다. 이 경우 F_k와 네트워크 항의 비중이 커진다.

#### 3.9.4 로컬 배치와 원격 배치의 선택

| 배치 | 네트워크 | 부하가 증가하는 노드 |
|---|---|---|
| stage k의 데이터를 OST k에 둠 | 사용하지 않음 | Node k (α_k · L_k 증가) |
| stage k의 데이터를 OST j에 둠 | F_k 증가 | Node j (α_j · L_j 증가) |

- 비용 모델은 두 경우의 max_k T_k를 비교해 작은 쪽을 고른다.
- 노드별 연산 여유는 요청 부하와 학습 상태에 따라 계속 바뀌므로, 같은 객체라도 시점에 따라 선택이 달라진다.
- 데이터센터의 분리형 스토리지에서는 이 선택이 성능 문제가 되지 않는다. 원 IFLustre도 연산을 고려하지 않으므로 이 선택을 다루지 않는다.

#### 3.9.5 시스템 아키텍처

```
┌────────────────────────── N0: Control plane ──────────────────────────┐
│                                                                        │
│   Telemetry Aggregator ─▶ Cost Model ─▶ LLM Planner ⇄ Verifier         │
│            ▲                                  ▲            │           │
│            │                          운영 정책(텍스트)       ▼           │
│            │                                            Executor        │
└────────────┼──────────────────────────────────────────────┼───────────┘
             │ telemetry (1초 주기)                            │ 계획 테이블, lfs/lctl 명령
┌────────────┴──────────────── 각 노드: Data plane ─────────────▼───────────┐
│  Telemetry Agent    Stage Runtime    KV Manager                           │
│  Weight Loader      Adapter Loader   Trainer (N0)    Ingest Writer (N0)    │
│  place() 라이브러리 (모든 I/O가 거치는 공통 경로)                              │
│  Lustre client      OSS/OST                                               │
└───────────────────────────────────────────────────────────────────────────┘
```

| 모듈 | 위치 | 입력 | 출력 |
|---|---|---|---|
| Telemetry Agent | 전 노드 | tegrastats, `/proc`, `lctl get_param` | 노드 상태 (1초 주기) |
| Telemetry Aggregator | N0 | 노드 상태 | 상태 요약 JSON, 이벤트 감지 |
| Cost Model | N0 | 상태, LG 프로파일, α, 접근률 | 후보 계획별 T_k, TTFT, 메모리, 이동 바이트 |
| LLM Planner | N0 | 상태 요약, 운영 정책, 이벤트 | 후보 계획 (JSON 조치 목록) |
| Verifier | N0 | 후보 계획 | 선택된 계획 또는 재요청 사유 |
| Executor | N0 | 선택된 계획 | `lfs setstripe/migrate/mirror`, `lctl set_param`(TBF), 계획 테이블 배포 |
| place() | 전 노드 | 객체 종류, LG, 생성 노드, 소비 노드, 크기 | 레이아웃 (계획 테이블 조회) |
| Stage Runtime | N1–N4 | LG 가중치, 어댑터, KV | 추론 결과, activation |
| KV Manager | N1–N4 | prefix 해시, 계획 테이블 | KV 읽기/쓰기, 재계산 vs 읽기 선택 |
| Weight Loader / Adapter Loader | N1–N4 | LG 파일 | 메모리 적재, 버전 전환 |
| Trainer | N0 | 학습 샘플 | 체크포인트, 어댑터 |
| Ingest Writer | N0 | IoT 데이터셋 | IoT 파일 쓰기 |

**처리 경로**

| 경로 | 용도 | 수행 주체 | 지연 |
|---|---|---|---|
| Slow path | 이벤트 발생 시 재계획 | Planner, Verifier, Executor | 초~수십 초 |
| Fast path | 요청·chunk 단위 배치 | place()가 계획 테이블을 조회 | 마이크로초~밀리초 |

#### 3.9.6 이벤트별 동작

| ID | 이벤트 | 트리거 | 경로 | 수행 내용 | Lustre 조치 |
|---|---|---|---|---|---|
| E0 | 시작 | 클러스터 기동 | Slow | 초기 P 결정, LG 배치, 노드별 대체 분할 P'_k 계산, mirror 위치 결정, 가중치 로드 | `setstripe -i`, `mirror` |
| E1 | 요청 도착 | 질의 | Fast | prefix 확인, 읽기·재계산 선택, 새 KV chunk를 계획 테이블 위치에 append | 디렉터리 default layout |
| E2 | 학습 시작 | 일정 또는 데이터 누적량 | Slow | 체크포인트 OST, TBF 상한, flush 시간대 결정 | TBF 규칙 설정 |
| E3 | 체크포인트 | 학습 step | Fast | 메모리 스냅샷 후 비동기 flush | TBF 적용 |
| E4 | 학습 종료 | 어댑터 생성 | Slow (경량) | LG 분할, 소비 노드 OST에 쓰기, stage별 로드, 동시 전환 | `setstripe -i` |
| E5 | 노드 장애 | heartbeat 실패 | Slow | 미리 계산한 P'_k 적용, 가중치는 mirror에서 읽기, KV는 재계산 또는 mirror 읽기 | mirror 읽기, `migrate` |
| E6 | 부하 변화·SLO 위반 | telemetry 임계값 | Slow | 병목 stage 노드의 I/O를 여유 노드로 이동, TBF 조정, 필요하면 부분 재분할 | `migrate`, TBF |
| E7 | 정책 변경 | 운영자 입력 | Slow | 목적 가중치와 제약 갱신 후 재계획 | 계획에 따름 |
| E8 | 노드 복귀 | heartbeat 회복 | Slow | 원래 분할 복귀 여부 결정, 이동 일정 결정 | `migrate` |

#### 3.9.7 원 IFLustre 정책과의 대응

| 원 IFLustre 구성 | 확장 내용 |
|---|---|
| Application Analyzer (로그 기반 stripe 결정, ML 예측) | Cost Model(LG 프로파일, α, 접근률) + LLM Planner(이벤트 기반 재계획) + Verifier |
| Interference-free allocation | 연산 부하가 없는 노드의 OST를 선택 |
| Throughput-aware allocation | 비용 모델에서 max_k T_k 증가가 최소인 OST를 선택 |
| Runtime-aware allocation | 체크포인트·재배치 I/O의 시점 지연과 TBF 속도 제한 |
| Read-aware relocation | 재분할, 어댑터 배포, 병목 변화 시 LG 단위 migrate/mirror. 어댑터는 쓰기 시점 배치 |
| 간섭 대상: OSS 사이 | OSS 사이 + 저장 I/O와 LLM 연산 사이 |
| 결정 시점: 애플리케이션 시작 | 이벤트마다 |

위 정책들을 플래너 없이 규칙으로 적용한 것을 "제안 기법(규칙)" 구성으로 평가한다. 이 구성은 플래너 실패 시의 fallback으로도 쓰인다.

#### 3.9.8 실행 예시

```
t0      E0  P = {N1: LG0–3+embed, N2: LG4–7, N3: LG8–11, N4: LG12–15+head}
            weights/lg{i} → 소비 노드 OST
            노드별 대체 분할 P'_k 계산 → mirror 위치 결정
            (예: N3 장애 시 P'_3 = {N1: LG0–5, N2: LG6–10, N4: LG11–15}
                 → lg8–10 mirror는 OST2, lg11 mirror는 OST4)
t0~     E1  매뉴얼 prefix KV는 pin + mirror, 세션 KV는 소비 노드 OST에 append
t1      E2  학습 라운드 시작. 체크포인트 flush 대상 = OST0, TBF 상한 = 비용 모델 계산값
t1~t2   E3  요청률이 높은 구간에는 flush 지연, 낮은 구간에 flush
t2      E4  어댑터 v(n+1) 생성 → adapters/v(n+1)/lg{i}를 소비 노드 OST에 쓰기
            → N1–N4 로드 완료 → 동시 전환
t3      E5  N3 장애 → P'_3 적용
            → lg8–11은 OST2, OST4의 mirror에서 읽기
            → lg4–5(N2→N1)는 OST2에서 읽은 뒤 OST1로 migrate
            → lg8–11의 KV는 재계산 또는 mirror 읽기
t4      E6  N2 stage가 병목 → N2 OST로 가던 KV 쓰기를 OST0으로 변경, TBF 상한 조정
t5      E8  N3 복귀 → 부하가 낮은 시간대에 원래 분할로 단계적 복귀
```

#### 3.9.9 요소를 제거했을 때의 결과

| 제거 요소 | 결과 |
|---|---|
| ⑧ | LG를 노드에 나누는 분할이 없으므로 소비 노드 기준 배치가 성립하지 않는다. 모델을 올릴 수 없다. |
| ② | 서빙 중 I/O가 거의 없어 간섭이 가중치 로드 시점에만 생긴다. 긴 컨텍스트 prefill 비용을 줄일 수 없다. |
| ⑤ | 워크로드가 읽기 위주의 정적 패턴이 된다. 버스트 충돌, 생성·소비 위치 불일치, 새 객체 이벤트가 사라진다. |
| ③ | 배치 기준(α)이 없다. 항상 로컬 배치가 최적이 되어 최적화 문제가 사라진다. |
| ⑦ | 이벤트마다 수동으로 재설정해야 한다. 이력이 없는 새 어댑터에는 로그 기반 결정을 쓸 수 없다. 자연어 운영 정책을 반영할 수 없다. |

### 3.10 구현

#### 3.10.1 소프트웨어 구성

| 구성 | 선택 | 이유 |
|---|---|---|
| 추론 런타임 | PyTorch + HF transformers 기반 자체 파이프라인 | LG 단위 로드, stage별 KV 저장·로드, 어댑터 교체, I/O 경로 계측을 직접 제어할 수 있다. 대안: llama.cpp RPC (성능 비교용) |
| stage 간 통신 | TCP (ZeroMQ 또는 gRPC) | activation이 토큰당 10KiB로 작다. |
| KV 직렬화 | HF DynamicCache 텐서를 LG 단위 연속 바이트로 기록, 오프셋 인덱스 별도 저장 | append와 부분 읽기 지원 |
| 학습 | HF PEFT (QLoRA), 체크포인트 2단계 저장 직접 구현 | 시점·속도 제어 필요 |
| 플래너 | llama.cpp server + JSON schema | 엣지 실행, 제약 디코딩 |
| 비용 모델·검증기 | Python | 분할 전수 탐색 또는 동적 계획법 |
| Executor | Python에서 `lfs`, `lctl` 호출 | 적용 결과와 실패 기록 |
| Telemetry | tegrastats 또는 jtop, `lctl get_param obdfilter.*.job_stats`, `osc.*.stats`, `/proc/meminfo`, `/proc/softirqs`, `/proc/net/dev` | 1초 주기 |

#### 3.10.2 디렉터리 구조 (예정)

```
lflustre_iot/
├── README.md
├── legacy/                # 기존 IFLustre IoT 벤치마크 스크립트 (현재 루트 파일, 정리 시 이동)
├── harness/
│   ├── place.py           # 배치 인터페이스 (모든 I/O 공통 경로)
│   ├── ingest/            # W1 (iotbenchlustre.py 기반, 속도 제한 모드 추가)
│   ├── train/             # W2 (QLoRA, 2단계 체크포인트, 어댑터 LG 분할)
│   ├── serve/             # W3 (stage runtime, KV manager, weight/adapter loader)
│   ├── workload/          # 요청 생성기 (3.2.3절 구성, 트레이스 재생)
│   └── telemetry/
├── control/               # cost model, planner, verifier, executor
├── tools/                 # 가중치 LG 분할 변환기, 크기 계산기
├── experiments/
│   ├── o1_path/ ... o6_events/   # 관찰 실험
│   └── eval/                     # 평가 실험
└── docs/
```

#### 3.10.3 place() 인터페이스

모든 I/O는 아래 함수를 거친다. 비교 대상(baseline)은 이 함수와 스케줄러의 구현만 다르고, 나머지 코드는 같다.

```python
def place(obj: str, lg: int | None, producer: str, consumer: str, size: int) -> Layout:
    """
    obj      : 'weight' | 'kv' | 'adapter' | 'ckpt' | 'iot' | 'train'
    lg       : LG 번호 (해당 없으면 None)
    producer : 생성 노드
    consumer : 소비 노드
    size     : 예상 크기 (bytes)
    반환     : OST index 목록, stripe count, stripe size, mirror OST 목록
    """
```

---

## 4. Experiment Plan

### 4.1 테스트베드 구성과 사전 점검

#### 4.1.1 기록할 장비 정보

| 항목 | 기록 내용 |
|---|---|
| 모듈 | 모델명, 메모리 용량, JetPack 버전, 전력 모드 |
| 저장 장치 | NVMe 모델, 용량, raw 순차 읽기/쓰기 대역폭 (fio) |
| 네트워크 | NIC 속도, 스위치, iperf3 측정 대역폭 (노드 쌍별) |
| Lustre | 버전, OSD 백엔드, MDT/OST 크기, LNet 설정 |

#### 4.1.2 사전 점검 항목

| ID | 점검 | 방법 | 통과 기준 |
|---|---|---|---|
| C1 | Lustre 기능 지원 | `lfs setstripe -E`(PFL), `lfs mirror create`(FLR), `lctl set_param ost.OSS.ost_io.nrs_policies="tbf jobid"`(TBF), `lctl get_param obdfilter.*.job_stats`(jobstats) 실행 | 각 명령 정상 동작 |
| C2 | 같은 노드 OST 접근 경로 | N1에서 OST1 파일을 읽으면서 `/proc/net/dev`의 NIC 바이트 변화 확인 | 경로 확인 결과 기록 |
| C3 | client + OSS 동시 운용 안정성 | 메모리 사용 80% 이상 상태에서 2시간 연속 읽기·쓰기 | hang, OOM 없음 |
| C4 | OSD 캐시 메모리 | ZFS 사용 시 ARC 상한 설정, ldiskfs 사용 시 캐시 파라미터 확인 | 설정 기록 |
| C5 | 모델 실행 | Qwen3-32B 4-stage 파이프라인으로 출력 확인, 단일 노드 대비 출력 일치 | 토큰 일치 |
| C6 | 학습 실행 | Qwen3-32B QLoRA 10 step 실행, 메모리 사용과 step 시간 기록 | OOM 없음 |
| C7 | 플래너 실행 | Qwen3-8B Q4 llama.cpp server, JSON schema 출력 확인 | 스키마 준수 |
| C8 | 시간 동기화 | 전 노드 chrony/NTP | 오차 1ms 이내 |

### 4.2 워크로드 구성 상세

#### 4.2.1 W1 Ingest

| 항목 | 값 |
|---|---|
| 데이터 | Bot-IoT, Widar3.0, MIMII, VisDrone, EPIC-Sounds, LoED (원 논문 6종), Loghub(HDFS, BGL), RIoTBench 레코드 스트림 |
| 쓰기 방식 | 데이터셋별 디렉터리에 원본 파일 단위로 쓰기. 레코드 스트림은 1분 단위 파일로 묶어서 쓰기 |
| 수집률 | 0 / 50 / 100 / 200 MB/s (민감도 변수), 기본 50 MB/s |
| 배치 | 기본 OST0. 비교 구성에서는 Lustre 기본 레이아웃 |
| 도구 | `iotbenchlustre.py`에 속도 제한과 연속 실행 모드 추가 |

#### 4.2.2 W2 Adapt

| 항목 | 값 |
|---|---|
| 학습 샘플 생성 | W1 데이터에서 라운드마다 생성한다. ① MIMII: 음향 특징 요약 + 정상/고장 라벨 → 원인 설명 응답, ② Bot-IoT: flow 요약 + 공격 라벨 → 판정 응답, ③ Loghub: 로그 구간 + 이상 라벨 → 판정과 근거 응답 |
| 라운드당 샘플 | 2,000–5,000개 |
| 라운드 주기 | 실험용 30–60분 (현장 가정: 일 1회 야간) |
| 학습 설정 | 3.3.2절 표 |
| 예상 학습 처리량 | 측정 필요. 라운드 길이를 맞추기 위해 step 수를 조정 |
| 체크포인트 | 50 step마다, 약 0.5GB (민감도: Qwen3-1.7B full FT, 약 20GB 이상) |
| 어댑터 | 라운드 종료 시 약 80MB, LG 16개 파일로 분할 |

어댑터가 응답 품질에 기여하는지는 별도로 확인한다. 라운드별 검증 샘플에서 판정 정확도를 1회 측정하며, 이는 주 평가 대상이 아닌 확인용 실험이다.

#### 4.2.3 W3 Serve

| 항목 | 값 |
|---|---|
| 모델 | Qwen3-32B FP16, 4-stage (3.3.2절) |
| 라인 수 | 4 (라인별 매뉴얼 4k–8k 토큰) |
| 요청 구성 | 3.2.3절 표 |
| 세션 | 1–5턴, 턴 간격 30초–10분 |
| 도착 과정 ① | Poisson, 평균 도착률 = 측정된 최대 지속 처리량의 30%, 60%, 90% |
| 도착 과정 ② | BurstGPT 또는 Azure LLM inference trace의 시간 패턴을 Orin 처리 용량에 맞춰 축소 재생 |
| 도착 과정 ③ | 교대 시작 시각에 라인별 질의가 몰리는 패턴 (정책 기반 미리 읽기 평가용) |
| prefix 재사용 | 기본은 3.2.3절 구성으로 합성. 대안으로 Mooncake trace의 블록 해시를 재생 |
| SLO | TTFT p99: O4 측정 후 "KV 적중 시 TTFT의 2배"로 설정. TPOT p99: O2 무부하 측정값의 1.5배 |
| 배치 처리 | stage별 micro-batch로 여러 요청을 파이프라인에 동시에 흘림 |

#### 4.2.4 배경 간섭 부하

| 부하 | 용도 |
|---|---|
| fio (읽기/쓰기, 1MiB/4MiB, 속도 단계) | O2, O3의 통제된 간섭원 |
| W1 수집 | 실제 IoT 배경 부하 |
| W2 체크포인트 | 버스트 부하 |

### 4.3 측정 도구와 방법

| 측정 대상 | 도구 | 주기 |
|---|---|---|
| GPU 사용률, EMC 사용률·주파수, CPU 코어별 사용률, 전력 | tegrastats (또는 jtop API) | 100ms–1s |
| 메모리 (Cached, Free, 프로세스별) | `/proc/meminfo`, `/proc/<pid>/status` | 1s |
| softirq, 컨텍스트 스위치 | `/proc/softirqs`, `pidstat` | 1s |
| NIC 송수신 | `/proc/net/dev`, `sar -n DEV` | 1s |
| Lustre OST I/O (jobid별) | `lctl get_param obdfilter.*.job_stats`, `obdfilter.*.brw_stats` | 1s |
| Lustre client RPC | `lctl get_param osc.*.rpc_stats`, `osc.*.stats` | 1s |
| 블록 장치 | `iostat -x` | 1s |
| LLM 지표 | 런타임 내부 계측 (요청별 TTFT, 토큰별 시간, stage별 처리 시간) | 이벤트 단위 |

**실험 규칙**

| 항목 | 규칙 |
|---|---|
| 반복 | 같은 설정을 5회 반복한다. 평균과 95% 신뢰구간을 보고한다. |
| 백분위 지표 | p99는 구성당 최소 500 요청 이상에서 계산한다. |
| 캐시 초기화 | 측정 전 client와 서버의 캐시를 비운다(`echo 3 > /proc/sys/vm/drop_caches`, Lustre `ldlm` lock 정리). |
| 예열 | 측정 전 2분 예열 구간을 두고 결과에서 제외한다. |
| 전력 모드 | 기본은 MAXN으로 고정하고, 민감도 실험에서만 변경한다. |
| 시간 동기화 | 전 노드 시계를 맞춘 뒤 이벤트 타임스탬프를 결합한다. |

### 4.4 관찰 실험 (논문 Section III)

각 실험의 결과는 3.9.3절 비용 모델의 파라미터와 3.8절 설계 결정의 근거가 된다.

#### O1. 엣지 저장 경로 특성

| 항목 | 내용 |
|---|---|
| 목적 | 로컬 OST, 원격 OST, striping 경로의 대역폭과 CPU·NIC 비용을 측정한다. 원격 접근이 로컬보다 느린지 확인한다. |
| 구성 | client N1. 대상: ① raw NVMe(ext4, Lustre 미사용), ② OST1(같은 노드), ③ OST2(원격), ④ stripe count 2 (OST1+OST2), ⑤ stripe count 4 (OST1–4), ⑥ Lustre 기본 레이아웃 |
| 변수 | 읽기/쓰기, bs 1MiB/4MiB, 파일 4GiB/16GiB, direct 0/1, numjobs 1/4, 동시 client 수 1/2/4 |
| 지표 | MB/s, client·server 노드 CPU 사용률, NIC 바이트, softirq |
| 가설 | 원격 경로는 NIC 대역폭으로 제한된다. 같은 노드 OST 경로는 NIC를 쓰지 않지만 CPU 비용이 있다. 원 논문과 달리 stripe count 증가의 이득이 NIC에서 막힌다. |
| 반영 | ⑧, ②의 기본 배치 규칙. F_k의 경로 대역폭 |
| 산출 그림 | 경로별 대역폭 막대그래프, 경로별 CPU·NIC 사용량 |

#### O2. 저장-연산 간섭

| 항목 | 내용 |
|---|---|
| 목적 | 같은 노드의 저장 I/O가 LLM 연산을 얼마나, 어떤 경로로 지연시키는지 측정한다(α). |
| 구성 | N1에서 stage 1(LG0–3)만 단독 실행한다. 입력은 고정 activation이며, ① decode 루프(batch 1/4/8, 컨텍스트 4k)와 ② prefill(2k 토큰)을 측정한다. 부하: N2–N4에서 OST1로 fio(서버 측 부하), N1에서 OST2–4로 fio(client 측 부하) |
| 변수 | 부하 속도 0/100/200/400/800MB/s/최대, 읽기/쓰기, bs 1MiB/4MiB, 격리 수단(없음/CPU 분리/캐시 상한/TBF), 전력 모드 |
| 지표 | tokens/s, 토큰 지연 p50/p99, GPU 사용률, EMC 사용률·주파수, CPU 코어별 사용률, Cached, softirq, 전력 |
| 가설 | 서버 측 부하가 증가하면 tokens/s가 감소한다. decode가 prefill보다 영향이 크다(메모리 대역폭). 쓰기가 읽기보다 영향이 크다(page cache, 데이터 복사). |
| 반영 | α_k (I/O 유형, LLM 단계, 전력 모드별), 격리 수단의 기본 설정 |
| 산출 그림 | 부하 대비 tokens/s 곡선, EMC 사용률과 tokens/s 상관, 격리 수단별 비교 |

#### O3. 파이프라인 증폭

| 항목 | 내용 |
|---|---|
| 목적 | 한 stage의 간섭이 파이프라인 전체 처리량에 미치는 영향을 측정한다. |
| 구성 | 4-stage 파이프라인 정상 decode(동시 요청 8개). 총 부하 800MB/s를 ① OST1 한 곳에 집중, ② OST1–4에 균등 분산, ③ OST0(비 stage 노드)에 집중 |
| 지표 | 파이프라인 tokens/s, stage별 처리 시간, 대기 시간 |
| 가설 | ①이 가장 나쁘다. ③은 네트워크 여유가 있으면 가장 좋다. ②는 그 사이이다. |
| 반영 | 목적 함수 max_k T_k, 여유 노드 배치 규칙 |
| 산출 그림 | 배치 방식별 처리량, stage별 처리 시간 분해 |

#### O4. 메모리 구성과 prefill 대 KV 로드

| 항목 | 내용 |
|---|---|
| 목적 | 노드별 메모리 구성을 확인하고, prefill 재계산과 KV 로드의 시간을 비교한다. |
| 구성 | ① 서빙 중 노드별 메모리 분해(가중치, KV, page cache, Lustre, 런타임), ② 컨텍스트 1k/2k/4k/8k/16k에서 prefill 시간과 KV 로드 시간(로컬 OST, 원격 OST, 기본 레이아웃) 비교, ③ 메모리 안에 유지 가능한 세션 수 |
| 지표 | GB, 초, 세션 수 |
| 가설 | KV 로드가 prefill보다 수 배 이상 빠르다. 메모리 안 세션 수는 하루 세션 수보다 작다. |
| 반영 | ②의 필요성 근거, 재계산 vs 읽기 판단 기준, TTFT SLO 설정 |
| 산출 그림 | 컨텍스트 길이별 prefill 시간 vs KV 로드 시간, 메모리 구성 누적 막대 |

#### O5. 라이프사이클 I/O 충돌

| 항목 | 내용 |
|---|---|
| 목적 | 체크포인트 버스트가 서빙 TTFT에 미치는 영향을 측정한다. |
| 구성 | W3를 최대 처리량의 60%로 서빙(KV 재사용 포함)하는 중에 체크포인트 flush를 실행한다. 크기 0.5GB / 20GB, flush 위치 ① KV와 같은 OST, ② 다른 stage 노드 OST, ③ OST0, TBF 유무 |
| 지표 | TTFT 시계열, p50/p99, 체크포인트 소요 시간 |
| 가설 | ①에서 TTFT p99가 크게 증가한다. TBF로 TTFT 증가를 줄이는 대신 체크포인트 시간이 늘어난다. |
| 반영 | ⑤의 위치·속도·시점 제어 |
| 산출 그림 | TTFT 시계열 (flush 구간 표시), 구성별 p99와 체크포인트 시간 |

#### O6. 생성·소비 위치 불일치와 이벤트 빈도

| 항목 | 내용 |
|---|---|
| 목적 | 쓰기 시점 위치가 이후 읽기에 주는 영향과, 재계획이 필요한 이벤트의 빈도를 확인한다. |
| 구성 | ① 어댑터를 OST0(생성 노드)에 둘 때와 소비 노드 OST에 둘 때의 로드·전환 시간, ② 기본 레이아웃과 LG 기반 배치에서 재분할 시 이동 바이트와 시간, ③ S1 시나리오(4.5.2절) 2시간 동안 E2–E8 이벤트 발생 횟수 |
| 지표 | 초, 바이트, 이벤트 횟수 |
| 가설 | 생성 위치 배치는 배포 지연이 길다. 기본 레이아웃은 재분할 시 이동량과 원격 읽기가 많다. 이벤트는 시간당 수 회 발생한다. |
| 반영 | ⑤의 쓰기 시점 배치, ⑧의 LG 파일 설계, ⑦의 필요성 |
| 산출 그림 | 배치별 배포 시간, 재분할 이동량, 이벤트 타임라인 |

III장 끝에는 관찰-설계 대응표(관찰 ID, 시사점, 설계 절)를 둔다.

### 4.5 평가 실험 (논문 Section V)

#### 4.5.1 비교 대상

| ID | 이름 | 분할 P | 배치 M | 시점·속도 S | 재계획 |
|---|---|---|---|---|---|
| B0 | Default Lustre | 연산량 균등 분할 | Lustre 기본 레이아웃 (stripe count 1, offset -1) | 제어 없음 | 없음 |
| B1 | Local-replica | 연산량 균등 분할 | 노드마다 가중치 전체 사본을 로컬 디스크에 보관, KV는 로컬만, 어댑터는 rsync로 복사 | 제어 없음 | 없음 |
| B2 | 원 IFLustre | 연산량 균등 분할 | OSS 여유 처리량 기반 할당 (연산 간섭 미고려) | runtime-aware | 시작 시 1회 |
| B3 | Search-only | 비용 모델 탐색 | 비용 모델 탐색 | 비용 모델 탐색 | 이벤트마다 전체 재탐색. 운영 정책은 사람이 미리 제약으로 변환 |
| B4 | 제안 기법 (규칙) | 비용 모델 | 3.9.7절 규칙 | 3.9.7절 규칙 | 이벤트마다 규칙 적용 |
| B5 | 제안 기법 (LLM) | 비용 모델 + 플래너 | 플래너 + 검증기 | 플래너 + 검증기 | 이벤트마다 propose-verify |
| B6 | Hand-tuned | 시나리오별 수동 최적 | 수동 | 수동 | 수동 |

S6에서는 여기에 LLM-only(검증기 없음)를 추가한다.

#### 4.5.2 평가 시나리오

| ID | 시나리오 | 설정 | 확인 내용 | 관련 RQ |
|---|---|---|---|---|
| S1 (메인) | End-to-end 라이프사이클 | 2시간. W1 50MB/s, W3 도착 과정 ②, W2 라운드 3회, 60분 시점 N3 장애, 90분 시점 N3 복귀, 30분 시점 정책 변경 1회 | 시간축에 따른 SLO 달성률, TTFT p99, freshness, 이동 바이트 | RQ1–RQ4 |
| S2 | 정상 상태 서빙 | W3 도착률 30/60/90%, W1 0/50/200MB/s | TTFT, TPOT, 처리량 | RQ2 |
| S3 | 서빙 + 체크포인트 | W3 60%, 체크포인트 0.5GB/20GB, 간격 변화 | TTFT p99, 체크포인트 시간, 학습 처리량 | RQ3 |
| S4 | 어댑터 배포 | 라운드 종료 시점 반복 | freshness, 전환 중 서빙 중단 시간 | RQ3 |
| S5 | 장애와 재분할 | N1–N4 각각 장애, 부하 변화에 의한 재분할 | 복구 시간, 이동 바이트, 복구 중 TTFT | RQ2 |
| S6 | 플래너 비교 | 이벤트 30종 (기존 정책 15종, 처음 보는 정책·모델·장애 15종) | SLO 달성률, 정책 준수율, 유효하지 않은 계획 비율, 결정 지연 | RQ4 |

#### 4.5.3 지표

| 분류 | 지표 |
|---|---|
| 서빙 | TTFT p50/p99, TPOT p50/p99, tokens/s, SLO 달성률 |
| 라이프사이클 | 가중치 로드 시간, 재분할·장애 복구 시간, 체크포인트 소요 시간, 학습 step/s, 학습 정지 시간, freshness |
| 자원·비용 | J/token (tegrastats 전력), 이동 바이트, OST 사용량, MDS 메타데이터 연산 수 |
| 플래너 | 결정 지연, 플래너 메모리·전력, 정책 준수율, 유효하지 않은 계획 비율, 검증기 거절 횟수 |

#### 4.5.4 Ablation

| 제거 대상 | 확인 내용 |
|---|---|
| α 반영 (비용 모델에서 α=0) | 저장-연산 간섭을 고려하는 효과 |
| 소비 노드 배치 (기본 레이아웃 사용) | LG 기반 배치의 효과 |
| TBF 속도 제한 | 속도 제한의 효과 |
| 체크포인트 시점 제어 | 시점 제어의 효과 |
| 쓰기 시점 어댑터 배치 | 배포 지연 감소 효과 |
| 대체 분할 기준 mirror | 장애 복구 효과 |
| 노드 내 격리 (CPU 분리, 캐시 상한) | 격리 수단의 효과 |
| 플래너 (규칙으로 대체) | 플래너의 효과 |

#### 4.5.5 민감도

| 변수 | 범위 |
|---|---|
| 노드 수 | 2–5 (stage 수 1–4) |
| 네트워크 대역폭 | `tc`로 1Gbps, 2.5Gbps, 10Gbps |
| 모델 | Qwen3-32B FP16 / INT8, Llama-3.1-70B INT4 |
| 요청 도착률 | 30–90% |
| 컨텍스트 길이 | 2k–16k |
| 체크포인트 크기와 간격 | 0.5GB–20GB 이상, 25–200 step |
| 수집률 | 0–200MB/s |
| 전력 모드 | `nvpmodel` 2–3개 모드 |

#### 4.5.6 규모 확장 시뮬레이션

1. 비용 모델과 측정 파라미터로 트레이스 기반 시뮬레이터를 만든다.
2. 5노드 실측 결과와 비교해 오차를 보고한다.
3. 8, 16, 32노드에서 B0, B2, B3, B4의 차이를 비교한다.

### 4.6 예상 그림과 표

| 번호 | 내용 | 섹션 |
|---|---|---|
| Fig.1 | 엣지 LLM 라이프사이클과 하이퍼컨버지드 클러스터 구조 | I |
| Fig.2 | Lustre 레이아웃 기능 (striping, PFL, FLR) | II |
| Table 1 | 관련 연구 종합 비교 (2.8절 표) | II |
| Fig.3 | O1 경로별 대역폭과 CPU·NIC 비용 | III |
| Fig.4 | O2 부하 대비 tokens/s, EMC 상관 | III |
| Fig.5 | O3 배치 방식별 파이프라인 처리량 | III |
| Fig.6 | O4 prefill vs KV 로드, 메모리 구성 | III |
| Fig.7 | O5 체크포인트 중 TTFT 시계열 | III |
| Fig.8 | O6 배포 시간, 재분할 이동량, 이벤트 타임라인 | III |
| Table 2 | 관찰-설계 대응표 | III |
| Fig.9 | 시스템 아키텍처 (3.9.5절) | IV |
| Fig.10 | LG 기반 배치와 대체 분할 기준 mirror 예시 | IV |
| Table 3 | 원 IFLustre 정책과의 대응 (3.9.7절) | IV |
| Fig.11 | S1 end-to-end 시간축 결과 | V |
| Fig.12 | S2 서빙 성능 비교 | V |
| Fig.13 | S3, S4 체크포인트·배포 결과 | V |
| Fig.14 | S5 장애 복구 | V |
| Fig.15 | S6 플래너 비교와 오버헤드 | V |
| Fig.16 | Ablation | V |
| Fig.17 | 민감도, 시뮬레이션 | V |

---

## 5. 논문 구성 대응

| 논문 섹션 | 내용 | 이 문서의 대응 절 |
|---|---|---|
| I. Introduction | 배경, 문제, 기존 연구 공백, 접근, 기여 | 1 |
| II. Background and Motivation | IoT와 엣지, Jetson, IoT LLM, LLM 구조와 I/O, Lustre, IFLustre, 관련 연구 비교표 | 2.1–2.6, 2.8 |
| III. Empirical Analysis | O1–O6, 관찰-설계 대응표 | 4.4 |
| IV. Design | 문제 정의, 비용 모델, ⑧②⑤③⑦ 설계, 통합 구성, 구현 | 3 |
| V. Evaluation | 비교 대상, 시나리오, 결과, ablation, 민감도 | 4.5 |
| VI. Discussion | 규모 한계, 다른 DFS로의 일반화, 전력, 보안 | 7 |
| VII. Related Work | 2.7절 분류를 압축 | 2.7 |
| VIII. Conclusion | | |

**IEEE IoTJ 투고 관련**
- 이전 버전(MASCOTS 2022)과의 차이는 3.9.7절 표와 2.6.3절 표로 설명한다.
- 이전 IoTJ 심사 의견에 대한 응답은 별도 문서(`docs/response.md`, 예정)로 관리한다.

---

## 6. 일정

| 단계 | 기간 | 작업 | 산출물 | 논문 위치 |
|---|---|---|---|---|
| P0 | 1주 | 장비 사양 기록, 사전 점검 C1–C8, 모델 확정 | 4.1절 표 완성 | III 설정 |
| P1 | 3주 | Lifecycle harness 구현 (W1, W2, W3, telemetry, place(), LG 변환 도구) | 실행 가능한 harness | IV 구현 |
| P2 | 2주 | O1–O6 측정 | Fig.3–8 | III |
| P3 | 1주 | 비용 모델 파라미터 피팅, 예측 오차 검증 | 비용 모델, 오차 결과 | IV |
| P4 | 2주 | LG 기반 배치, 규칙 정책, Executor, 대체 분할 mirror | B4 구성 | IV |
| P5 | 1주 | 플래너, 검증기, Search-only | B3, B5 구성 | IV |
| P6 | 2주 | 평가 S1–S6, ablation, 민감도, 시뮬레이션 | Fig.11–17 | V |
| P7 | 1–2주 | 집필, 심사 의견 응답서 | 원고 | 전체 |

---

## 7. 리스크

| 리스크 | 영향 | 대응 |
|---|---|---|
| α가 작게 측정됨 | ③의 비중 감소 | O1(네트워크 경로)과 O5(I/O 클래스 간 충돌) 중심으로 서술한다. 비용 모델은 그대로 쓴다. |
| LLM 플래너가 Search-only보다 성능이 낮음 | ⑦의 기여 약화 | 정책 해석, 처음 보는 시나리오, 이벤트 대응 결과를 그대로 보고한다. 주 기여는 LG 기반 공동 결정으로 둔다. |
| client + OSS 동시 운용 불안정 | 실험 진행 불가 | P0(C3)에서 확인한다. 캐시 상한과 메모리 예약을 적용한다. 문제 정의의 근거로도 사용한다. |
| Lustre 기능 미지원 (FLR, PFL, TBF 버전 차이) | 일부 조치 불가 | P0(C1)에서 확인한다. 미지원 기능은 대체 수단(파일 복사로 mirror, 사용자 공간 속도 제한)을 쓴다. |
| Qwen3-32B QLoRA 학습이 Orin에서 너무 느림 | 라운드 길이 증가 | step 수와 시퀀스 길이를 줄인다. 필요하면 적응 대상을 Qwen3-8B로 낮추고, 서빙 모델과 분리된 실험으로 구성한다. |
| 자체 파이프라인 런타임의 절대 성능이 낮음 | 비교의 설득력 저하 | 상대 비교 중심으로 서술한다. llama.cpp RPC 기반 측정을 보조 결과로 추가한다. |
| 네트워크가 1GbE임 | 원격 경로가 매우 느림 | locality 효과가 커지는 방향이므로 결과를 그대로 보고한다. 10GbE는 민감도로 다룬다. |
| 노드 수가 5대뿐임 | 일반화 의문 | 엣지 사이트 규모가 원래 작다는 점을 서술한다. 비용 모델 기반 시뮬레이션으로 확장한다. |
| 일정 지연 | 평가 축소 | ⑦은 마지막 단계에서 결합하므로 나머지 구성은 영향을 받지 않는다. |

---

## 8. 미결 사항

- [ ] Orin 모델과 메모리 용량 (3.3절 모델 구성 확정에 필요)
- [ ] NIC 사양과 스위치 (1GbE / 10GbE)
- [ ] NVMe 모델, 용량, raw 대역폭
- [ ] Lustre 버전, OSD 백엔드, 기능 지원 여부 (C1)
- [ ] Jetson 사양 수치의 공식 datasheet 확인 (2.2절 표)
- [ ] 추론 런타임 최종 선택 (자체 PyTorch 파이프라인 / llama.cpp RPC)
- [ ] 시스템 이름
- [ ] 이전 IoTJ 심사 의견 정리와 반영 범위
- [ ] 기존 루트 스크립트의 `legacy/` 이동 여부
- [ ] 참고 문헌 서지 정보 원문 확인

---

## 9. 참고 문헌

투고 전에 서지 정보를 원문으로 다시 확인한다.

### 원 연구

- S. Kim, D. K. Sung, Y. Son, "IFLustre: Towards Interference-free and Efficient Storage Allocation in Distributed File System," MASCOTS 2022.
- "Interference-free and Efficient Storage Allocation for IoT Applications in Distributed File System on Cloud Environment," IEEE IoTJ (Reject & Resubmit).

### IoT 데이터와 LLM-IoT

- N. Koroniotis et al., "Towards the Development of Realistic Botnet Dataset in the Internet of Things for Network Forensic Analytics: Bot-IoT Dataset," FGCS, 2019.
- Z. Yang et al., "Widar 3.0: WiFi-based Activity Recognition Dataset," IEEE Dataport, 2020.
- H. Purohit et al., "MIMII Dataset: Sound Dataset for Malfunctioning Industrial Machine Investigation and Inspection," arXiv:1909.09347, 2019.
- P. Zhu et al., "Detection and Tracking Meet Drones Challenge," IEEE TPAMI, 2021.
- J. Huh et al., "EPIC-SOUNDS: A Large-Scale Dataset of Actions that Sound," ICASSP 2023.
- L. Bhatia et al., "LoED: The LoRaWAN at the Edge Dataset," Workshop on Data: Acquisition to Analysis, 2020.
- A. Shukla, S. Chaturvedi, Y. Simmhan, "RIoTBench: An IoT Benchmark for Distributed Stream Processing Systems," Concurrency and Computation: Practice and Experience, 2017.
- J. Zhu et al., "Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics," ISSRE 2023.
- "When IoT Meet LLMs: Applications and Challenges," arXiv:2411.17722, 2024.
- O. Friha et al., "LLM-Based Edge Intelligence: A Comprehensive Survey on Architectures, Applications, Security and Trustworthiness," IEEE Open Journal of the Communications Society, 2024.

### Lustre와 DFS

- P. J. Braam, P. Schwan, "Lustre: The Intergalactic File System," Ottawa Linux Symposium, 2002.
- Y. Qian et al., "A Configurable Rule based Classful Token Bucket Filter Network Request Scheduler for the Lustre File System," SC 2017.
- S. A. Weil et al., "Ceph: A Scalable, High-Performance Distributed File System," OSDI 2006.
- Lustre Operations Manual (PFL, DoM, FLR, NRS TBF, Job Stats, CPT).

### 저장 I/O 간섭과 QoS

- M. Dorier et al., "CALCioM: Mitigating I/O Interference in HPC Systems through Cross-Application Coordination," IPDPS 2014.
- T. Patel et al., "GIFT: A Coupon Based Throttle-and-Reward Mechanism for Fair and Efficient I/O Bandwidth Management on Parallel Storage Systems," FAST 2020.
- B. Wadhwa et al., "iez: Resource Contention Aware Load Balancing for Large-Scale Parallel File Systems," IPDPS 2019.
- Y. Hua et al., "LoomIO: Object-Level Coordination in Distributed File Systems," IEEE TPDS, 2021.
- G. Yang et al., "Radio: Reconciling Disk I/O Interference in a Para-virtualized Cloud," IEEE CLOUD 2022.
- L. N. Jaliminche et al., "Enabling Multi-tenancy on SSDs with Accurate IO Interference Modeling," SoCC 2023.
- Y. Zhou et al., "CoFS: A Collaboration-Aware Fairness Scheme for NVMe SSD in Cloud Storage System," IEEE TCAD, 2024.
- S. Kim et al., "DCA-IO: A Dynamic I/O Control Scheme for Parallel and Distributed File Systems," CCGrid 2019.
- S. Kim et al., "Towards HPC I/O Performance Prediction through Large-scale Log Analysis," HPDC 2020.
- D. K. Sung et al., "A2FL: Autonomous and Adaptive File Layout in HPC through Real-time Access Pattern Analysis," IPDPS 2024.
- E. Costa et al., "Systematically Inferring I/O Performance Variability by Examining Repetitive Job Behavior," SC 2021.

### 자원 공존과 간섭 격리

- D. Lo et al., "Heracles: Improving Resource Efficiency at Scale," ISCA 2015.
- S. Chen et al., "PARTIES: QoS-Aware Resource Partitioning for Multiple Interactive Services," ASPLOS 2019.
- J. Fried et al., "Caladan: Mitigating Interference at Microsecond Timescales," OSDI 2020.
- H. Yun et al., "MemGuard: Memory Bandwidth Reservation System for Efficient Performance Isolation in Multi-core Platforms," RTAS 2013.

### LLM 서빙, 로딩, 오프로딩

- W. Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention," SOSP 2023.
- L. Zheng et al., "SGLang: Efficient Execution of Structured Language Model Programs," NeurIPS 2024.
- Y. Fu et al., "ServerlessLLM: Low-Latency Serverless Inference for Large Language Models," OSDI 2024.
- K. Alizadeh et al., "LLM in a flash: Efficient Large Language Model Inference with Limited Memory," ACL 2024.
- Y. Song et al., "PowerInfer: Fast Large Language Model Serving with a Consumer-grade GPU," SOSP 2024.
- Z. Xue et al., "PowerInfer-2: Fast Large Language Model Inference on a Smartphone," arXiv:2406.06282, 2024.
- Y. Sheng et al., "FlexGen: High-Throughput Generative Inference of Large Language Models with a Single GPU," ICML 2023.
- "An I/O Characterizing Study of Offloading LLM Models and KV Caches to NVMe SSD," ACM, 2025 (DOI 10.1145/3719330.3721230).

### KV cache 저장과 재사용

- B. Gao et al., "Cost-Efficient Large Language Model Serving for Multi-turn Conversations with CachedAttention," USENIX ATC 2024.
- R. Qin et al., "Mooncake: Trading More Storage for Less Computation — A KVCache-centric Architecture for Serving LLM Chatbot," FAST 2025.
- Y. Cheng et al., "LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference," arXiv:2510.09665, 2025.
- Y. Liu et al., "CacheGen: KV Cache Compression and Streaming for Fast Large Language Model Serving," SIGCOMM 2024.
- J. Yao et al., "CacheBlend: Fast Large Language Model Serving for RAG with Cached Knowledge Fusion," EuroSys 2025.
- W. Chen et al., "IMPRESS: An Importance-Informed Multi-Tier Prefix KV Storage System for Large Language Model Inference," FAST 2025.
- "KVSwap: Disk-aware KV Cache Offloading for Long-Context On-device Inference," arXiv:2511.11907, 2025.
- "DUAL-BLADE: Dual-Path NVMe-Direct KV-Cache Offloading for Edge LLM Inference," arXiv:2604.26557, 2026.
- "MemLLM: End-to-end In-Storage Acceleration of On-device Retrieval-Augmented Generation using Precomputed KV Caches," arXiv:2610.22579, 2026.
- "Multi-tier Dynamic Storage of KV Cache for LLM Inference under Resource-constrained Conditions," Complex & Intelligent Systems, 2025.

### 엣지 분산 추론

- Y. Hu et al., "PipeEdge: Pipeline Parallelism for Large-Scale Model Inference on Heterogeneous Edge Devices," Euromicro DSD 2022.
- M. Zhang et al., "EdgeShard: Efficient LLM Inference via Collaborative Edge Computing," IEEE Internet of Things Journal, vol. 12, no. 10, 2025 (DOI 10.1109/JIOT.2024.3524255).
- S. Ye et al., "Galaxy: A Resource-Efficient Collaborative Edge AI System for In-situ Transformer Inference," INFOCOM 2024.
- "LOIP: Collaborative Lossless LLM Inference Serving with Offloading-based Pipeline Parallelism on Edge Devices," arXiv:2512.21835, 2025.
- Z. Li et al., "Prima.cpp: Fast 30-70B LLM Inference on Heterogeneous and Low-Resource Home Clusters," arXiv:2504.08791, 2025.
- exo (open-source distributed inference), llama.cpp RPC backend.

### 엣지 학습과 어댑터

- E. J. Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models," ICLR 2022.
- T. Dettmers et al., "QLoRA: Efficient Finetuning of Quantized LLMs," NeurIPS 2023.
- L. Zhu et al., "PockEngine: Sparse and Efficient Fine-tuning in a Pocket," MICRO 2023.
- "MobiZO: Enabling Efficient LLM Fine-Tuning at the Edge via Inference Engines," EMNLP 2025.
- Y. Sheng et al., "S-LoRA: Serving Thousands of Concurrent LoRA Adapters," MLSys 2024.
- L. Chen et al., "Punica: Multi-Tenant LoRA Serving," MLSys 2024.
- "EdgeLoRA: An Efficient Multi-Tenant LLM Serving System on Edge Devices," arXiv:2507.01438, 2025.

### 학습 체크포인트

- J. Mohan et al., "CheckFreq: Frequent, Fine-Grained DNN Checkpointing," FAST 2021.
- A. Eisenman et al., "Check-N-Run: A Checkpointing System for Training Deep Learning Recommendation Models," NSDI 2022.
- Z. Wang et al., "GEMINI: Fast Failure Recovery in Distributed Training with In-Memory Checkpoints," SOSP 2023.
- A. Maurya et al., "DataStates-LLM: Lazy Asynchronous Checkpointing for Large Language Models," HPDC 2024.
- B. Wan et al., "ByteCheckpoint: A Unified Checkpointing System for Large Foundation Model Development," NSDI 2025.

### LLM 기반 시스템 튜닝

- C. Egersdoerfer et al., "ION: Navigating the HPC I/O Optimization Journey using Large Language Models," HotStorage 2024.
- C. Egersdoerfer et al., "STELLAR: Storage Tuning Engine Leveraging LLM Autonomous Reasoning for High Performance Parallel File Systems," SC 2025 (DOI 10.1145/3712285.3759887).
- I. Trummer, "DB-BERT: A Database Tuning Tool that Reads the Manual," SIGMOD 2022.
- J. Lao et al., "GPTuner: A Manual-Reading Database Tuning System via GPT-Guided Bayesian Optimization," VLDB 2024.
- V. Giannakouris, I. Trummer, "λ-Tune: Harnessing Large Language Models for Automated Database System Tuning," SIGMOD 2025.

### 모델과 트레이스

- Qwen Team, "Qwen3 Technical Report," arXiv:2505.09388, 2025.
- Qwen Team, "Qwen2.5 Technical Report," arXiv:2412.15115, 2024.
- Llama Team, "The Llama 3 Herd of Models," arXiv:2407.21783, 2024.
- Y. Wang et al., "BurstGPT: A Real-world Workload Dataset to Optimize LLM Serving Systems," arXiv:2401.17644, 2024.
- P. Patel et al., "Splitwise: Efficient Generative LLM Inference Using Phase Splitting," ISCA 2024 (Azure LLM inference trace).
- Mooncake traces (FAST 2025 공개 트레이스).

---

## 부록 A. 크기 계산식

| 항목 | 식 | Qwen3-32B 값 |
|---|---|---|
| layer당 파라미터 | (전체 − 임베딩 − 출력 head) / L | (32.8B − 0.78B − 0.78B) / 64 ≈ 0.488B |
| layer당 가중치 (FP16) | layer당 파라미터 × 2B | 약 0.98GB |
| LG당 가중치 (g=4) | 4 × layer당 가중치 | 약 3.9GB |
| 임베딩 / 출력 head | vocab × hidden × 2B | 151,936 × 5,120 × 2B ≈ 1.56GB (각각) |
| 토큰당 KV (전체) | 2 × L × H_kv × d_head × 2B | 2 × 64 × 8 × 128 × 2 = 262,144B = 256KiB |
| 토큰당 KV (layer당) | 2 × H_kv × d_head × 2B | 4KiB |
| 토큰당 KV (LG당, g=4) | 4 × 4KiB | 16KiB |
| 토큰당 KV (stage당, LG 4개) | 4 × 16KiB | 64KiB |
| 256토큰 chunk (LG당) | 256 × 16KiB | 4MiB |
| 8k 토큰 세션 KV | 8,192 × 256KiB | 2GiB (stage당 512MiB, LG 파일당 128MiB) |
| stage 간 activation (토큰당) | hidden × 2B | 5,120 × 2 = 10KiB |
| LoRA 파라미터 (layer당, rank r) | q: r(5,120 + 8,192), k: r(5,120 + 1,024), v: r(5,120 + 1,024), o: r(8,192 + 5,120) | r=16: 622,592 |
| LoRA 어댑터 전체 | 64 × layer당 × 2B (FP16) | 약 39.8M 파라미터, 약 80MB (LG당 약 5MB) |
| 체크포인트 | 어댑터 FP32(4B) + Adam m, v(각 4B) + 기타 | 약 0.48GB |
| Prefill 연산량 (선형 항) | 2 × 파라미터 × 토큰 | 2 × 32.8e9 × 8,192 ≈ 5.4e14 FLOP |
| Prefill 연산량 (attention 항, causal) | QK와 AV 합계: 2 × L × (H_q × d_head) × n² | 2 × 64 × 8,192 × 8,192² ≈ 7e13 FLOP (causal mask를 무시한 상한은 약 1.4e14) |

Qwen3-32B의 Q projection 출력 차원은 H_q × d_head = 64 × 128 = 8,192이고, hidden 5,120과 다르다.

---

## 부록 B. 플래너 입출력 예시

### B.1 입력 (요약)

```json
{
  "event": {"type": "node_failure", "node": "N3", "time": "2026-10-21T14:00:05"},
  "policy": "라인 3 질의를 우선 처리한다. 주간(09-18시)에는 학습 체크포인트로 인한 TTFT 증가를 허용하지 않는다.",
  "slo": {"ttft_p99_s": 4.0, "tpot_p99_ms": 450},
  "partition": {"N1": [0,1,2,3], "N2": [4,5,6,7], "N3": [8,9,10,11], "N4": [12,13,14,15]},
  "precomputed_fallback": {"N3": {"N1": [0,1,2,3,4,5], "N2": [6,7,8,9,10], "N4": [11,12,13,14,15]}},
  "nodes": {
    "N0": {"gpu": 0.71, "emc": 0.52, "cpu": 0.40, "mem_used_gb": 41.2, "training": "round 3, step 120/200"},
    "N1": {"gpu": 0.63, "emc": 0.58, "cpu": 0.35, "mem_used_gb": 38.0, "stage_ms": 96},
    "N2": {"gpu": 0.66, "emc": 0.61, "cpu": 0.37, "mem_used_gb": 36.5, "stage_ms": 92},
    "N4": {"gpu": 0.64, "emc": 0.57, "cpu": 0.33, "mem_used_gb": 37.1, "stage_ms": 95}
  },
  "osts": {"OST0": {"load_mbps": 180, "used_pct": 41}, "OST1": {"load_mbps": 60, "used_pct": 52},
           "OST2": {"load_mbps": 75, "used_pct": 55}, "OST4": {"load_mbps": 58, "used_pct": 50}},
  "rules": ["O2: 쓰기 400MB/s 이상이면 같은 노드 decode 처리량이 감소한다", "..."]
}
```

### B.2 출력

```json
{
  "actions": [
    {"type": "repartition", "partition": {"N1": [0,1,2,3,4,5], "N2": [6,7,8,9,10], "N4": [11,12,13,14,15]}},
    {"type": "migrate", "files": ["weights/lg4", "weights/lg5"], "to_ost": "OST1", "tbf_rpc": 80},
    {"type": "set_layout", "dir": "kv/*/lg4-5", "ost": "OST1"},
    {"type": "schedule_ckpt", "defer_until": "low_load", "tbf_rpc": 20},
    {"type": "pin_prefix", "line": 3}
  ],
  "rationale": "N3 장애로 사전 계산한 대체 분할을 적용한다. lg8-11은 mirror에서 읽는다. 주간 정책에 따라 체크포인트를 미룬다. 라인 3의 공통 prefix를 고정한다."
}
```

검증기는 이 출력에 대해 메모리 제약, OST 용량, 예상 TTFT p99를 계산한 뒤 적용 여부를 결정한다.

---

## 부록 C. 저장소의 기존 코드

| 파일 | 내용 | 향후 용도 |
|---|---|---|
| `iotbenchlustre.py` | 데이터셋을 Lustre에 쓰는 IoT 벤치마크 (`lfs setstripe` 설정, 메타데이터·I/O 지연 측정) | W1 수집 부하 생성기 (속도 제한 모드 추가) |
| `iotbenchhdfs.py`, `iotbenchhdfs_orig.py`, `iotBhdfs_old.py` | HDFS 대상 벤치마크 | 사용 여부 미정 |
| `iotBench.py`, `iot0.py`, `iot1.py`, `iot2.py`, `iotr.py`, `iotmultiepic.py`, `iotmultiepic2.py` | 기존 IoT 실험 스크립트 | 참고용 |
| `listdataset.py` | 데이터셋 디렉터리 목록 출력 | 유지 |
| `fio.sh`, `fio0320.sh`, `fio1.sh`–`fio3.sh`, `fiodk.sh`, `fios1.sh`, `fios2.sh`, `fiovarfilesize.sh`, `2fio.sh` | fio 측정 스크립트 (파일 크기별 쓰기 등) | O1 경로 측정, O2 간섭 부하 생성 |
| `cpfile.sh`, `config.sh` | 파일 복사, Hadoop 환경 변수 | 유지 |
| `readme.txt` | `lfs setstripe` 예시 | 이 문서로 대체 예정 |
