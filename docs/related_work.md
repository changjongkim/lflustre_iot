# 관련 연구와 참고 문헌

> README 2.8절(관련 연구와 연구 공백)의 상세 자료이다. 분야별 비교, 종합 비교표, 전체 참고 문헌을 담는다. 서지 정보는 투고 전에 원문으로 다시 확인한다.

## 1. 분야별 관련 연구

### 1.1 저장 I/O 간섭과 QoS

공유 스토리지의 간섭을 다룬 연구는 세 갈래가 있다.
- **스케줄링·조정:** CALCioM, GIFT, LoomIO, Lustre NRS TBF
- **배치·설정:** iez, DCA-IO, A2FL
- **장치 수준:** Radio, Jaliminche et al., CoFS

모두 스토리지와 연산이 분리된 환경을 가정한다.

| 연구 | 발표 | 방법 | 본 연구와의 차이 |
|---|---|---|---|
| CALCioM | IPDPS 2014 | 앱 간 I/O 조정 | 스토리지와 연산 분리 가정, NIC·메모리 공유 미고려 |
| GIFT | FAST 2020 | 쿠폰 기반 대역폭 관리 | 스토리지와 연산 분리 가정, NIC·메모리 공유 미고려 |
| iez | IPDPS 2019 | OSS 용량 불균형 완화 | 소비 위치 미고려 |
| LoomIO | TPDS 2021 | 객체 수준 요청 조정 | 스토리지와 연산 분리 가정, NIC·메모리 공유 미고려 |
| Lustre NRS TBF | SC 2017 | 토큰 버킷 요청 스케줄러 | 본 연구의 실행 수단 |
| DCA-IO | CCGrid 2019 | 로그 기반 설정 조정 | 로그 필요 |
| A2FL | IPDPS 2024 | 실시간 패턴 기반 레이아웃 | 스토리지와 연산 분리 가정, NIC·메모리 공유 미고려 |
| Radio / Jaliminche et al. / CoFS | CLOUD 2022 / SoCC 2023 / TCAD 2024 | 장치 수준 간섭 | 장치 수준 |
| IFLustre | MASCOTS 2022 | 예측 기반 OSS 할당 | 본 연구의 기반 |

### 1.2 자원 공존과 간섭 격리

Heracles(ISCA 2015), PARTIES(ASPLOS 2019), Caladan(OSDI 2020)은 한 서버의 자원을 나누어 지연 민감 서비스의 SLO를 지킨다. MemGuard(RTAS 2013)는 코어별 메모리 대역폭을 예약한다. 본 연구와의 차이는 세 가지이다.
- 간섭원이 DFS 서버 측 I/O라서 데이터 배치로 간섭 위치를 바꿀 수 있다.
- 피해자가 파이프라인 stage라서 한 노드의 지연이 전체로 전파된다.
- 8GB 장치에서는 메모리 용량이 먼저 한계에 도달한다.
- 본 실측에서 GPU 중심 추론은 CPU·메모리 대역폭 경쟁에 둔감했다(감속 3% 이내). 문제는 NIC 공유와 메모리 용량에서 나타났다.

### 1.3 LLM 모델 로딩과 오프로딩

ServerlessLLM(OSDI 2024), LLM in a flash(ACL 2024), PowerInfer(SOSP 2024), PowerInfer-2(arXiv 2024), FlexGen(ICML 2023), prima.cpp(arXiv 2025), NVMe 오프로딩 I/O 특성 분석(ACM 2025)은 로딩 시간과 메모리 부족을 다룬다. 모두 장치·서버 한 대의 로컬 저장 계층을 대상으로 한다.

### 1.4 KV cache 저장과 재사용 (데이터센터)

| 연구 | 발표 | 방법 | 본 연구와의 차이 |
|---|---|---|---|
| vLLM | SOSP 2023 | PagedAttention, 블록 해시 prefix 재사용 | GPU 메모리 안, 요청 시점 생성 |
| SGLang | NeurIPS 2024 | radix tree prefix 재사용 | 동일 |
| CachedAttention | USENIX ATC 2024 | 멀티턴 KV를 메모리·디스크에 저장 | 서버 내부, 요청 시점 생성 |
| Mooncake | FAST 2025 | KV 중심 분리형 서빙, 블록 해시 기반 KV 풀 | 분리형 풀, RDMA |
| LMCache | arXiv 2025 | 엔진 독립 KV 계층, chunk 해시(256토큰) | 요청 시점 생성, 저장 계층과의 노드 메모리 예산 공유 미고려 |
| CacheGen | SIGCOMM 2024 | KV 압축·스트리밍 | 전송 중심 |
| IMPRESS | FAST 2025 | 중요도 기반 다계층 prefix KV | 단일 서버 |

이 연구들은 블록·chunk 해시로 KV를 식별한다는 점에서 이미 content addressing을 사용한다. 그러나 KV를 요청 시점에 만들고, 분리된 저장 풀을 가정한다.

### 1.5 KV 사전 계산과 위치 독립 재사용

| 연구 | 발표 | 방법 | 본 연구와의 차이 |
|---|---|---|---|
| Prompt Cache | MLSys 2024 | 스키마로 정의한 프롬프트 모듈 단위 KV 재사용 | 정적 모듈, 스트림 아님 |
| CacheBlend | EuroSys 2025 | 여러 문서 KV를 결합하고 일부 토큰을 다시 계산 | 근사 재사용, RAG 대상 |
| EPIC | arXiv 2024 (ICML 2025) | 위치 독립 컨텍스트 캐싱 | 근사 재사용 |
| TurboRAG | arXiv 2024 | RAG 문서 chunk KV를 미리 계산 | 고정 문서 |
| MemLLM | arXiv 2026 | 장치 내 RAG용 사전 계산 KV를 플래시에 저장 | 고정 문서, 단일 장치 |

본 연구와의 차이는 네 가지이다.
1. **스트림 대상.** 계속 늘어나는 IoT 스트림의 KV를 수집 시점에 만든다.
2. **근사 없음.** 스트림 단위 이어 쓰기 컨텍스트로 근사 없이 재사용한다.
3. **압축과 버전.** 컨텍스트 한계에서 의미 기반 압축을 하고, 어댑터 버전 변화에 따른 부분 재생성을 다룬다.
4. **엣지 DFS.** 하이퍼컨버지드 엣지 DFS에서 배치와 간섭을 함께 다룬다.

### 1.6 엣지 KV cache 오프로딩

| 연구 | 발표 | 환경 | 방법 | 본 연구와의 차이 |
|---|---|---|---|---|
| KVSwap | arXiv 2025 | Jetson AGX Orin, NVMe 약 1.8GB/s | 디스크 인지 KV 교체 | 단일 장치 |
| Dual-Blade | arXiv 2026 | 엣지, NVMe | page cache 경로와 NVMe 직접 경로 병행 (page cache thrashing 지적) | 단일 장치 |
| MTDS | Complex & Intelligent Systems 2025 | 자원 제약 엣지 | DRAM-SSD 다계층 KV | 단일 장치 |

### 1.7 엣지 분산 LLM 추론

| 연구 | 발표 | 환경 | 분할 기준 | 본 연구와의 차이 |
|---|---|---|---|---|
| PipeEdge | DSD 2022 | 이기종 엣지 | 연산, 메모리, 네트워크 | 저장 I/O 미고려 |
| EdgeShard | IEEE IoTJ 2025 | Jetson Orin + 클라우드 | 장치 선택 + 분할 (동적 계획법) | 저장 I/O, KV, 학습 미고려 |
| Galaxy | INFOCOM 2024 | 엣지 협력 | 연산, 통신 | 동일 |
| LOIP | arXiv 2025 | Jetson AGX Orin, Xavier NX | 파이프라인 + 로컬 layer 오프로딩 | 공유 DFS 없음 |
| prima.cpp | arXiv 2025 | 가정용 장치 | 장치 성능, 디스크 속도 | 로컬 디스크 |

### 1.8 엣지 학습, 추론·학습 공동 실행, 어댑터 서빙

| 연구 | 발표 | 내용 | 본 연구와의 차이 |
|---|---|---|---|
| LoRA / QLoRA | ICLR 2022 / NeurIPS 2023 | 저랭크 적응 | 상위 LG 한정 LoRA로 사용 |
| PockEngine | MICRO 2023 | Jetson Orin 희소 역전파 미세조정 | 학습 단독 |
| MobiZO | EMNLP 2025 | 엣지 zeroth-order 미세조정 | 학습 단독 |
| FlexLLM | arXiv 2024 | 추론과 PEFT의 토큰 단위 공동 실행 | 데이터센터, 저장 I/O·KV 유효성 미고려 |
| ConServe / DeltaServe | arXiv 2024 / 2026 | 온라인·오프라인 공동 실행 | 데이터센터 |
| S-LoRA / Punica / EdgeLoRA | MLSys 2024 / MLSys 2024 / arXiv 2025 | 다중 LoRA 서빙 | 어댑터 변경에 따른 저장 KV 무효화 미고려 |

### 1.9 학습 체크포인트

CheckFreq(FAST 2021), Check-N-Run(NSDI 2022), Gemini(SOSP 2023), DataStates-LLM(HPDC 2024), ByteCheckpoint(NSDI 2025)는 학습 처리량과 복구 시간을 목표로 한다. 같은 저장 계층·NIC를 쓰는 서빙 지연에 주는 영향은 다루지 않는다.

### 1.10 Content-addressed 저장과 중복 제거

LBFS(SOSP 2001), Venti(FAST 2002), Data Domain(FAST 2008), Git, IPFS(2014)는 내용 해시로 데이터를 식별한다. 이 연구들은 일반 데이터를 대상으로 하므로 다음을 다루지 않는다.
- LLM 상태의 의존성: 앞부분 토큰과 가중치 버전
- 의미 정보에 따른 정책
- 연산 노드와 저장 노드가 같을 때의 배치

### 1.11 LLM 기반 시스템·스토리지 튜닝

ION(HotStorage 2024)과 STELLAR(SC 2025)는 LLM으로 HPC I/O를 진단하거나 병렬 파일 시스템 설정을 튜닝한다. DB-BERT(SIGMOD 2022), GPTuner(VLDB 2024), λ-Tune(SIGMOD 2025)은 데이터베이스 설정을 튜닝한다. 모두 단일 대상의 오프라인 튜닝이다. 본 연구의 플래너는 서비스 중 이벤트마다 온라인으로 재계획하고, 검증기로 실행 전 결과를 확인하며, 8GB 장치에서 실행된다.

## 2. 종합 비교와 연구 공백

| 분류 | 대표 연구 | 엣지 | 저장-연산 공존 | 분산 추론 | KV 저장 | 스트림 KV 사전 생성 | 버전 인지 KV | 학습 I/O | 공유 DFS | 온라인 재계획 |
|---|---|---|---|---|---|---|---|---|---|---|
| 저장 간섭/QoS | GIFT, LoomIO, IFLustre | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | △ |
| 자원 공존 격리 | Heracles, Caladan | ✗ | △ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ |
| prefix KV 재사용 | vLLM, Mooncake, LMCache | ✗ | ✗ | ✗ | ✓ | ✗ | ✗ | ✗ | △ | ✗ |
| 사전 계산·위치 독립 KV | Prompt Cache, CacheBlend, TurboRAG | ✗ | ✗ | ✗ | ✓ | △ (고정 문서) | ✗ | ✗ | ✗ | ✗ |
| 엣지 KV 오프로딩 | KVSwap, Dual-Blade | ✓ | △ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 엣지 분산 추론 | EdgeShard, LOIP | ✓ | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | △ |
| 추론·학습 공동 실행 | FlexLLM, ConServe | ✗ | △ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ | △ |
| 체크포인트 | CheckFreq, Gemini | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | △ | ✗ |
| CAS | Venti, LBFS, IPFS | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| LLM 기반 튜닝 | ION, STELLAR | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| **CoStripe** | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

(✓: 주요 대상, △: 일부, ✗: 다루지 않음. 투고 전 원문으로 재확인한다.)

**연구 공백**

| ID | 공백 |
|---|---|
| G1 | 저장 서버와 LLM 연산 노드가 같은 소형 엣지 클러스터에서 공유 자원(OSS, NIC, 노드 메모리)과 데이터 위치가 LLM 서빙에 주는 영향이 측정·모델링되지 않았다. 본 실측에서 이 영향은 저장 I/O의 LLM 연산 감속(3% 이내)보다 훨씬 컸다. |
| G2 | 엣지 분산 추론의 분할은 저장 위치를 고려하지 않고, DFS 배치 연구는 연산 분할을 고려하지 않는다. |
| G3 | 계속 늘어나는 IoT 스트림을 컨텍스트로 쓰는 요청에서 KV를 수집 시점에 만들어 근사 없이 재사용하는 저장 구조가 없다. 어댑터 버전 변화에 따른 저장 KV의 유효성 관리도 다뤄지지 않았다. |
| G4 | 수집, 적응, 서빙의 I/O가 한 클러스터에서 공존할 때 체크포인트·복제·재생성 I/O의 위치·시점·속도 제어가 다뤄지지 않았다. |
| G5 | 엣지 현장의 잦은 이벤트와 자연어 운영 정책 아래에서의 온라인 재계획이 다뤄지지 않았다. |

## 3. 참고 문헌

투고 전에 서지 정보를 원문으로 다시 확인한다.

### 원 연구
- S. Kim, D. K. Sung, Y. Son, "IFLustre: Towards Interference-free and Efficient Storage Allocation in Distributed File System," MASCOTS 2022.
- "Interference-free and Efficient Storage Allocation for IoT Applications in Distributed File System on Cloud Environment," IEEE IoTJ (Reject & Resubmit).

### IoT 데이터와 LLM-IoT
- N. Koroniotis et al., "Bot-IoT Dataset," FGCS, 2019.
- Z. Yang et al., "Widar 3.0," IEEE Dataport, 2020.
- H. Purohit et al., "MIMII Dataset," arXiv:1909.09347, 2019.
- P. Zhu et al., "Detection and Tracking Meet Drones Challenge," IEEE TPAMI, 2021.
- J. Huh et al., "EPIC-SOUNDS," ICASSP 2023.
- L. Bhatia et al., "LoED: The LoRaWAN at the Edge Dataset," 2020.
- A. Shukla, S. Chaturvedi, Y. Simmhan, "RIoTBench," Concurrency and Computation: Practice and Experience, 2017.
- J. Zhu et al., "Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics," ISSRE 2023.
- "When IoT Meet LLMs: Applications and Challenges," arXiv:2411.17722, 2024.
- O. Friha et al., "LLM-Based Edge Intelligence: A Comprehensive Survey," IEEE OJ-COMS, 2024.

### 하드웨어
- NVIDIA, Jetson Orin Nano Super Developer Kit 및 Jetson Orin 모듈 datasheet.

### Lustre와 DFS
- P. J. Braam, P. Schwan, "Lustre: The Intergalactic File System," OLS 2002.
- Y. Qian et al., "A Configurable Rule based Classful Token Bucket Filter Network Request Scheduler for the Lustre File System," SC 2017.
- S. A. Weil et al., "Ceph," OSDI 2006.
- Lustre Operations Manual (PFL, DoM, FLR, NRS TBF, Job Stats, CPT, `max_cached_mb`).

### Content-addressed 저장
- A. Muthitacharoen, B. Chen, D. Mazières, "A Low-bandwidth Network File System," SOSP 2001.
- S. Quinlan, S. Dorward, "Venti: A New Approach to Archival Storage," FAST 2002.
- B. Zhu, K. Li, H. Patterson, "Avoiding the Disk Bottleneck in the Data Domain Deduplication File System," FAST 2008.
- J. Benet, "IPFS — Content Addressed, Versioned, P2P File System," arXiv:1407.3561, 2014.

### 저장 I/O 간섭과 QoS
- M. Dorier et al., "CALCioM," IPDPS 2014.
- T. Patel et al., "GIFT," FAST 2020.
- B. Wadhwa et al., "iez," IPDPS 2019.
- Y. Hua et al., "LoomIO," IEEE TPDS, 2021.
- G. Yang et al., "Radio," IEEE CLOUD 2022.
- L. N. Jaliminche et al., "Enabling Multi-tenancy on SSDs with Accurate IO Interference Modeling," SoCC 2023.
- Y. Zhou et al., "CoFS," IEEE TCAD, 2024.
- S. Kim et al., "DCA-IO," CCGrid 2019.
- S. Kim et al., "Towards HPC I/O Performance Prediction through Large-scale Log Analysis," HPDC 2020.
- D. K. Sung et al., "A2FL," IPDPS 2024.
- E. Costa et al., "Systematically Inferring I/O Performance Variability by Examining Repetitive Job Behavior," SC 2021.

### 자원 공존과 간섭 격리
- D. Lo et al., "Heracles," ISCA 2015.
- S. Chen et al., "PARTIES," ASPLOS 2019.
- J. Fried et al., "Caladan," OSDI 2020.
- H. Yun et al., "MemGuard," RTAS 2013.

### LLM 서빙, 로딩, 오프로딩
- W. Kwon et al., "Efficient Memory Management for Large Language Model Serving with PagedAttention," SOSP 2023.
- L. Zheng et al., "SGLang," NeurIPS 2024.
- Y. Fu et al., "ServerlessLLM," OSDI 2024.
- K. Alizadeh et al., "LLM in a flash," ACL 2024.
- Y. Song et al., "PowerInfer," SOSP 2024.
- Z. Xue et al., "PowerInfer-2," arXiv:2406.06282, 2024.
- Y. Sheng et al., "FlexGen," ICML 2023.
- "An I/O Characterizing Study of Offloading LLM Models and KV Caches to NVMe SSD," ACM, 2025 (DOI 10.1145/3719330.3721230).

### KV cache 저장, 재사용, 사전 계산
- B. Gao et al., "CachedAttention," USENIX ATC 2024.
- R. Qin et al., "Mooncake: Trading More Storage for Less Computation — A KVCache-centric Architecture for Serving LLM Chatbot," FAST 2025.
- Y. Cheng et al., "LMCache: An Efficient KV Cache Layer for Enterprise-Scale LLM Inference," arXiv:2510.09665, 2025.
- Y. Liu et al., "CacheGen," SIGCOMM 2024.
- W. Chen et al., "IMPRESS," FAST 2025.
- I. Gim et al., "Prompt Cache: Modular Attention Reuse for Low-Latency Inference," MLSys 2024.
- J. Yao et al., "CacheBlend," EuroSys 2025.
- J. Hu et al., "EPIC: Efficient Position-Independent Context Caching for Serving Large Language Models," arXiv:2410.15332 (ICML 2025).
- S. Lu et al., "TurboRAG: Accelerating Retrieval-Augmented Generation with Precomputed KV Caches for Chunked Text," arXiv:2410.07590, 2024.
- "MemLLM," arXiv:2610.22579, 2026.
- Z. Zhang et al., "H2O: Heavy-Hitter Oracle for Efficient Generative Inference of Large Language Models," NeurIPS 2023.
- Y. Li et al., "SnapKV," NeurIPS 2024.

### 엣지 KV 오프로딩
- "KVSwap," arXiv:2511.11907, 2025.
- "DUAL-BLADE," arXiv:2604.26557, 2026.
- "Multi-tier Dynamic Storage of KV Cache for LLM Inference under Resource-constrained Conditions," Complex & Intelligent Systems, 2025.

### 엣지 분산 추론
- Y. Hu et al., "PipeEdge," Euromicro DSD 2022.
- M. Zhang et al., "EdgeShard," IEEE IoTJ, vol. 12, no. 10, 2025 (DOI 10.1109/JIOT.2024.3524255).
- S. Ye et al., "Galaxy," INFOCOM 2024.
- "LOIP," arXiv:2512.21835, 2025.
- Z. Li et al., "Prima.cpp," arXiv:2504.08791, 2025.

### 엣지 학습, 공동 실행, 어댑터
- E. J. Hu et al., "LoRA," ICLR 2022.
- T. Dettmers et al., "QLoRA," NeurIPS 2023.
- L. Zhu et al., "PockEngine," MICRO 2023.
- "MobiZO," EMNLP 2025.
- X. Miao, G. Oliaro et al., "FlexLLM: Token-Level Co-Serving of LLM Inference and Finetuning with SLO Guarantees," arXiv:2402.18789.
- "ConServe," arXiv:2410.01228, 2024.
- "DeltaServe," arXiv:2607.28848, 2026.
- Y. Sheng et al., "S-LoRA," MLSys 2024.
- L. Chen et al., "Punica," MLSys 2024.
- "EdgeLoRA," arXiv:2507.01438, 2025.

### 학습 체크포인트
- J. Mohan et al., "CheckFreq," FAST 2021.
- A. Eisenman et al., "Check-N-Run," NSDI 2022.
- Z. Wang et al., "GEMINI," SOSP 2023.
- A. Maurya et al., "DataStates-LLM," HPDC 2024.
- B. Wan et al., "ByteCheckpoint," NSDI 2025.

### LLM 기반 시스템 튜닝
- C. Egersdoerfer et al., "ION," HotStorage 2024.
- C. Egersdoerfer et al., "STELLAR," SC 2025 (DOI 10.1145/3712285.3759887).
- I. Trummer, "DB-BERT," SIGMOD 2022.
- J. Lao et al., "GPTuner," VLDB 2024.
- V. Giannakouris, I. Trummer, "λ-Tune," SIGMOD 2025.

### 모델과 트레이스
- Qwen Team, "Qwen3 Technical Report," arXiv:2505.09388, 2025.
- Y. Wang et al., "BurstGPT," arXiv:2401.17644, 2024.
- P. Patel et al., "Splitwise," ISCA 2024 (Azure LLM inference trace).
- Mooncake traces (FAST 2025 공개).
