# P0 결과 요약 (2026-10-22)

> 장비·구성 상세: `docs/testbed.md`
> 전환 계획: `docs/hyperconverged_plan.md`
> 원시 로그: `results/p0/<호스트>/`

## 1. 결론

**진행할 만하다 (go).** 판단 실험 세 가지 중 두 가지가 기대보다 강하게, 한 가지는 보조 근거 수준으로 나왔다.

| 판단 실험 | 결과 | 판정 |
|---|---|---|
| ① 로컬 OST 대 원격 OST | 로컬이 쓰기 15배, 읽기 22배 빠름 | go |
| ② prefill 대 KV 복원 | 로컬 복원이 prefill보다 7–12배 빠름. 원격 복원은 prefill과 비슷하거나 더 느림 | go |
| ③ Lustre 캐시와 GPU 할당 | 실패는 없음. 할당 시간 +25%, 최악 할당 지연 2배. 캐시 상한으로 해소 | 보조 근거 |

논문의 무게중심은 "데이터와 KV를 어디에 두느냐"(위치)와 공유 자원(OSS, NIC, 8GB 노드 메모리)에 둔다. 이후 재측정에서 같은 노드 저장 I/O의 LLM 연산 감속은 모든 조건에서 3% 이내여서, 연산 간섭은 주장에서 빼고 대조 측정으로만 보고한다(README 3.14절). 다른 노드의 I/O를 처리하는 OSS는 CPU의 13–19%를 쓰지만(재측정, P0의 약 2%는 fio 레이아웃 문제로 인한 측정 오류), 같은 노드의 GPU 중심 LLM은 1% 안팎만 느려진다(README 3.6, 3.9절). 자기 노드의 로컬 I/O는 CPU의 약 45%를 쓴다.

## 2. 판단 실험 상세

### ① 로컬 OST 대 원격 OST (jetson1에 client를 임시 마운트, 2GiB, 4M, libaio iodepth 16, 3회)

| 경로 | 쓰기 | 읽기 | NIC 사용 | 노드 CPU (6코어 전체 대비) |
|---|---|---|---|---|
| 로컬 OST0000 (direct) | 1,656–1,728MB/s | 2,480–2,486MB/s | 0 | 41–46% |
| 원격 OST0001 (direct) | 114.6MB/s | 114.8MB/s | 회선 최대 | 13–20% |
| 로컬 buffered 읽기 | – | 1,419MB/s, page cache +2.07GB | 0 | 46% |

같은 노드 OST 접근은 NIC를 거치지 않는다. 측정 후 client 마운트는 해제했다.

### ② prefill 대 KV 복원 (jetson1, llama.cpp, Qwen3-4B Q4_K_M, KV FP16, slot save/restore, 2회)

| 토큰 | prefill | KV 파일 | 로컬 OST 복원 | 원격 OST 복원 | 복원 후 첫 토큰 |
|---|---|---|---|---|---|
| 1,024 | 1.73초 | 144MiB | 0.19–0.20초 | 1.36–1.37초 | 0.11초 |
| 2,048 | 3.42초 | 288MiB | 0.30–0.38초 | 2.68초 | 0.12초 |
| 4,096 | 7.03초 | 576MiB | 0.58–0.63초 | 5.30초 | 0.12초 |
| 8,192 | 15.2초 | 1,152MiB | 2.13–2.19초 | 21.8–21.9초 | 0.14초 |

- KV 파일 크기는 토큰당 144KiB로 README 계산과 일치한다.
- 원격 복원은 8k에서 prefill보다 느리다. 이때 원격 읽기 속도가 약 53MB/s로 회선 속도의 절반이었다.
- 8k에서는 로컬 복원도 4k 대비 3.5배 느려졌다(크기는 2배). llama-server 실행 중 남은 메모리가 약 1.8GB여서, 1.15GB 파일을 page cache로 읽는 동안 메모리 회수가 일어난 것으로 추정한다.
- 설계 반영: KV는 소비 노드 로컬에 둔다. 읽기 경로는 direct I/O나 캐시 해제로 page cache를 거치지 않게 한다. 원격 KV는 재계산과 비교해 선택한다(README 4.8.2절, `docs/design_details.md` 3.2절 2j).

### ③ Lustre client 캐시와 GPU 메모리 할당 (jetson1, 256MiB 단위 cudaMalloc + memset)

| 조건 | 4GiB 할당 총시간 | 최악 256MiB | 5GiB 할당 총시간 | 최악 256MiB |
|---|---|---|---|---|
| 캐시 비어 있음 | 1,461ms | 97ms | 1,832ms | 99ms |
| 캐시 약 3.9GB (기본 상한) | 1,807ms | 192ms | 2,298ms | 200ms |
| 캐시 상한 512MB | 1,460ms | 95ms | 1,824ms | 99ms |

할당은 모두 성공했다. 커널이 Lustre 캐시를 회수해 GPU 메모리를 내준다(할당 후 캐시 3.9GB → 0.9–2.0GB).

## 3. 기타 점검

| 점검 | 결과 |
|---|---|
| C1 Lustre 기능 | 통과 (OST 지정, 상속, PFL, FLR, migrate, TBF) |
| C2 client → OST (분리형) | 쓰기 93MB/s, 읽기 115MB/s, stripe count 1–3 모두 동일. stripe 2·3은 레이아웃을 확인하며 재측정함(`results/motivation/m1b`, 읽기 117.5MB/s, 결론 동일) |
| C4 캐시 설정 | client 캐시 상한 3,810MB (RAM의 1/2), OSS 측 캐시 꺼짐, jobstats 꺼짐 |
| C5 메모리 | CUDA 컨텍스트 약 74MiB, 2GiB buffered 읽기 시 MemFree −2.16GB (상한 512MB면 −0.52GB), Lustre 서버 memused 약 120MiB |
| C8 플래너 | Qwen3-4B Q4_K_M, 입력 1,653토큰 prefill 2.84초(583 tok/s), 생성 15.4 tok/s, 결정 1회 16–21초, JSON 3/3 유효, 메모리 약 4.1GB. 조치 내용은 부정확 → 검증기와 조치별 형식 제한 필요 |
| C9 시간 동기화 | NTP 기준 오프셋 12–30ms (목표 1ms 미달) |

## 4. 발견한 문제와 결정 필요 사항

| ID | 내용 | 필요한 결정 |
|---|---|---|
| F1 | 서버 MGS 주소가 무선 IP로 설정되어 MGS 연결이 끊김 | 당장은 불필요. 서버 재부팅·OST 추가·영구 설정 때만 정정 |
| F2 | jetson에 NVMe 없음, jetson0 NVMe는 MDT가 전부 사용 → 5-OST 구성 불가 (방안 B 제외 결정) | 방안 A'(jetson1–3을 stage 노드로) 채택 여부 |
| F3 | jetson 송신 약 725Mb/s | 케이블·포트 교체 |
| F4 | GUI 켜짐, jetson에 다른 프로세스 약 1.8GB | 실험 기간 GUI 끄기, 프로세스 정리 |
| F5 | 시간 오차 12–30ms | 로컬 시간 서버 구성 |
| F6 | SSH 조회가 CPU 측정을 오염 | 노드 내부 샘플러 사용 (적용함, `experiments/motivation/sampler.py`) |
| F7 | jetson1이 LLM 실행 중 두 번 멈춤. 원인은 llama-server의 호스트 RAM prompt cache(기본 8GiB)와 같은 노드 Lustre I/O의 메모리 소진 (`docs/testbed.md`, README 3.9절) | `--cache-ram 0`과 메모리 보호를 켜고 M8, M10, M14 재측정 |
| – | PyTorch 미설치 | 설치 방식(NVIDIA wheel / jetson-containers) |
| – | 플래너 메모리 4.1GB | 플래너 모델 크기(4B/1.7B)와 배치 노드 |

## 5. 다음 단계 제안 (P1)

1. 결정 사항 반영: F1 정정, 방안 A' 적용(jetson1–3 client 마운트, 캐시 상한 512MB), GUI 끄기, PyTorch 설치
2. 노드 내부 샘플러 작성 (tegrastats, /proc, PSI, Lustre stats를 노드 안에서 기록)
3. 파이프라인 런타임 최소 버전: Qwen3-4B FP16 3-stage(jetson1–3), LG 단위 로드, C6 토큰 일치 확인
4. KV Store 최소 버전: 컨텍스트 체인 해시, pack append·봉인, 로컬 OST 배치, direct I/O 읽기, C10 검증
5. O2(간섭)·O4(메모리)·O7(KV 재사용 구조) 본 측정
