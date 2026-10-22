# 테스트베드 사양과 P0 점검 결과

> 점검일: 2026-10-22
> 원시 로그: `results/p0/<호스트>/`, 스크립트: `experiments/p0_env/`
> 이 문서에는 외부 접속 주소와 비밀번호를 기록하지 않는다.

## 1. 노드 사양

| 호스트 (실제 이름) | 계정 | 보드 | L4T | 전력 모드 | 부팅 대상 | 메모리 (MemTotal) | zram 스왑 | OS 저장 장치 | NVMe |
|---|---|---|---|---|---|---|---|---|---|
| jetson0 (jetson0-desktop) | jetson0 | Orin Nano Engineering Reference Developer Kit Super | R36.4.4 | 25W | graphical.target | 7,620MiB | 6 × 635MB (3.8GB) | microSD 477.5GB | Samsung 970 EVO Plus 500GB |
| jetson1 (jetson1-desktop) | jetson1 | 위와 같음 | R36.4.4 | 25W | graphical.target | 7,620MiB | 3.8GB | microSD 477.5GB | Samsung 980 500GB |
| jetson2 (jetson2-desktop) | jetson2 | 위와 같음 | R36.4.4 | 25W | graphical.target | 7,620MiB | 3.8GB | microSD 477.5GB | Samsung 980 500GB |
| jetson3 (jetson3-desktop) | jetson3 | 위와 같음 | R36.4.4 | 25W | graphical.target | 7,608MiB | 3.8GB | microSD 477.5GB | Samsung 980 500GB |
| jetson (jetson-desktop) | jetson | 위와 같음 | R36.4.4 | 25W | graphical.target | 7,620MiB | 3.8GB | microSD 238.5GB | **없음** |

- 공통: Cortex-A78AE 6코어(최대 1.728GHz), 커널 5.15.148-tegra, CUDA 12.6, Python 3.10.12
- PyTorch: 5대 모두 미설치
- jetson에는 실험과 무관한 프로세스가 실행 중: `node` 4개(약 1.07GB), `codex`(약 451MB), GNOME(약 128MB), dockerd(약 78MB)

## 2. 네트워크

| 호스트 | 유선 인터페이스 / IP | 무선 인터페이스 / IP | 유선 속도 | LNet NID |
|---|---|---|---|---|
| jetson0 | enP8p1s0 / 192.168.0.50 | wlP1p1s0 / 192.168.0.60 | 1000Mb/s Full, MTU 1500 | 192.168.0.50@tcp (enP8p1s0) |
| jetson1 | enP8p1s0 / 192.168.0.51 | wlP1p1s0 / 192.168.0.61 | 1000Mb/s Full | 192.168.0.51@tcp |
| jetson2 | enP8p1s0 / 192.168.0.52 | wlP1p1s0 / 192.168.0.62 | 1000Mb/s Full | 192.168.0.52@tcp |
| jetson3 | enP8p1s0 / 192.168.0.53 | wlP1p1s0 / 192.168.0.63 | 1000Mb/s Full | 192.168.0.53@tcp |
| jetson | enP8p1s0 / 192.168.0.100 | wlP1p1s0 / 192.168.0.110 | 1000Mb/s Full | 192.168.0.100@tcp |

- 유선 IP(.5x, .100)는 유선 인터페이스로, 무선 IP(.6x, .110)는 무선 인터페이스로 가는 호스트 경로가 설정되어 있다.
- client와 서버 사이 Lustre TCP(988) 연결은 모두 유선 IP로 맺어져 있다. 데이터 경로는 유선이다.

**iperf3 (10초, 단일 스트림)**

| 경로 | 정방향 | 역방향 |
|---|---|---|
| jetson → jetson1 / 2 / 3 (유선) | 722 / 725 / 723 Mb/s | 929 / 932 / 929 Mb/s |
| jetson0 → jetson1 (유선) | 927 Mb/s | 930 Mb/s |
| jetson1 → jetson2 (유선) | 929 Mb/s | 932 Mb/s |
| jetson → jetson1 (무선, 참고) | 154 Mb/s | 146 Mb/s |

- jetson의 송신만 약 725Mb/s로 낮다. 4개 스트림(`-P 4`)에서도 729Mb/s이다. NIC 오프로드, 흐름 제어, EEE 설정은 jetson0와 같으므로 케이블이나 스위치 포트 문제로 추정한다.

## 3. Lustre 구성

| 항목 | 값 |
|---|---|
| 버전 | 2.17.0 (서버·client 모두) |
| 파일 시스템 | `lustrefs`, 총 1.4TB, 사용 약 150GB |
| OSD 백엔드 | ldiskfs |
| MGS | jetson0, `/dev/nvme0n1p1` (8GB) |
| MDT0000 | jetson0, `/dev/nvme0n1p2` (457.8GB, 사용 약 0.2GB) |
| OST0000 | jetson1, `/dev/nvme0n1` 전체 (사용 94GB) |
| OST0001 | jetson2, `/dev/nvme0n1` 전체 (사용 36GB) |
| OST0002 | jetson3, `/dev/nvme0n1` 전체 (사용 20GB) |
| client 마운트 | jetson만 `/mnt/lustrefs` (`192.168.0.50@tcp:/lustrefs`). 서버 노드는 client 마운트 없음, client 모듈은 로드되어 있음 |
| 기본 레이아웃 | stripe count 1, stripe size 4MB, 시작 OST 자동 |
| 테스트 디렉터리 | `/mnt/lustrefs/llmio_test` (P0에서 생성, 소유자 jetson) |

**주요 파라미터 (조회 결과)**

| 파라미터 | 값 | 비고 |
|---|---|---|
| `llite.*.max_cached_mb` (client) | 3,810MB | RAM의 1/2 |
| `llite.*.max_read_ahead_mb` | 256MB | |
| `osc.*.checksums` / 방식 | 켜짐 / t10ip4K | |
| `osc.*.max_rpcs_in_flight` / RPC 크기 / `max_dirty_mb` | 8 / 4MB / 953MB | |
| `jobid_var` | disable | jobstats 비활성, I/O 클래스 태깅 시 켜야 함 |
| OSS `read_cache_enable` / `writethrough_cache_enable` | 0 / 0 | 서버 측 page cache 사용 안 함 |
| OSS NRS 정책 | fifo (TBF 사용 가능, 정지 상태) | |
| OSS ost_io 스레드 | 시작 3, 최대 142 | |
| `brw_size` | 4MB | |
| `mdt.*.md_stats` | 조회 가능 | O7 메타데이터 연산 측정에 사용 |
| CPT | 단일 파티션 (코어 0–5) | |
| Lustre 서버 메모리 (`memused`) | MDS 약 122MiB, OSS 약 119MiB | |

## 4. 발견한 문제

| ID | 문제 | 영향 | 제안 조치 (승인 필요) |
|---|---|---|---|
| F1 | MDT와 OST 3대의 `mgsnode`가 무선 IP `192.168.0.60@tcp`를 먼저 가리키고 있다. 서버의 MGC import가 CONNECTING 상태로 약 1,650회 재연결을 시도 중이다. jetson0의 LNet NID는 유선 `.50`뿐이다. | 데이터 I/O는 정상이다. 영구 설정(`set_param -P`), OST pool, 새 OST 등록 등 MGS가 필요한 작업이 실패할 수 있다. | 각 target을 잠시 내리고 `tunefs.lustre --erase-param mgsnode --mgsnode=192.168.0.50@tcp` |
| F2 | jetson(client)에 NVMe가 없고, jetson0 NVMe는 MGT·MDT가 전부 사용한다. | 이전 README의 5-OST 하이퍼컨버지드 구성은 장치 추가나 MDT 재구축 없이는 불가능하다. | 방안 A' 채택, 방안 B 제외 (2026-10-22, `docs/hyperconverged_plan.md`) |
| F3 | jetson 송신 대역폭이 약 725Mb/s로 다른 노드(약 930Mb/s)보다 낮다. | client 쓰기 대역폭이 약 93MB/s로 제한된다. | 케이블·스위치 포트 교체 후 재측정 |
| F4 | 5대 모두 GUI(graphical.target)가 켜져 있고, jetson에는 다른 에이전트 프로세스가 실행 중이다. | 실험과 무관한 메모리 사용(jetson 약 1.8GB)으로 메모리 실측과 간섭 측정이 왜곡된다. | 실험 기간 multi-user.target 전환, 실험 노드에서 다른 프로세스 중지 |
| F5 | 노드 간 시각 오차가 NTP 기준 12–30ms이다. | 노드 간 이벤트 정렬 정확도가 떨어진다(목표 1ms). | jetson0를 로컬 시간 서버로 하는 chrony 구성 |
| F6 | 측정 중 SSH로 상태를 자주 조회하면 polkitd·dbus CPU가 증가한다. P0에서 jetson2만 OSS CPU가 13–19%로 높게 나와 SSH 영향으로 보았으나, 노드 내부 샘플러 재측정에서 원격 I/O를 처리하는 OSS CPU는 13–19%가 맞았다. jetson1·3의 약 2%는 fio가 파일을 다시 만들어 데이터가 다른 OST에 놓인 측정으로 보인다. | P0의 OSS CPU 값(약 2%)은 쓰지 않는다. | 노드 안에서 직접 기록하는 샘플러 사용 (`experiments/motivation/sampler.py`) |
| F7 | jetson1이 두 번 멈췄다(17:46 M8 원격 쓰기 중, 18:22 M10 측정 중). 첫 재부팅 직후 NVIDIA 디스플레이 드라이버(`nv_pmops_runtime_suspend`) NULL 참조 panic이 한 번 더 있었다. 원인은 llama.cpp 서버의 호스트 RAM prompt cache(`--cache-ram`, 기본 8,192MiB)이다. 프롬프트가 바뀔 때마다 이전 KV(2k 토큰 기준 약 300–370MB)를 RAM에 쌓아 MemAvailable을 1GB 아래로 낮췄고, 같은 노드의 Lustre I/O가 남은 메모리를 쓰면서 zram 스왑이 3.4GB까지 찬 뒤 멈췄다(README 3.11절). 두 번 모두 `lustre-starter`가 OST0000을 자동 마운트해 복구되었고 client 마운트는 사라졌다. | P0·M8·M10의 llama-server 측정은 prompt cache가 켜진 상태였다. LLM 속도 값은 유효하지만, 메모리 값은 런타임 캐시를 포함한다. | 모든 llama-server를 `--cache-ram 0`으로 실행, 실험 중 메모리 보호(`memguard.sh`, MemAvailable 700MB 미만이면 실험 프로세스 종료), 모델은 로컬 디스크 사본 사용 |

## 5. 사전 점검 결과

| 점검 | 결과 | 측정값·내용 | README 가정과 차이 |
|---|---|---|---|
| C1 Lustre 기능 | 통과 | OST 지정, 디렉터리 상속, PFL, FLR(create/extend/resync/verify), migrate(경로 유지), NRS TBF(활성화·규칙 추가·복원), jobstats(조회) | jobstats는 꺼져 있음 |
| C2 저장 경로 | 통과 (원격 경로만). stripe 2·3은 fio가 파일을 다시 만들어 설정이 사라졌을 수 있어 재측정함(`results/motivation/m1b`, 결론 동일) | 아래 표 | 같은 노드 OST 경로는 client 마운트가 없어 측정 불가. raw NVMe는 Lustre 외 파일 시스템이 없어 측정 불가 |
| C4 캐시 설정 | 기록 완료 | 3절 표 | client 캐시 상한이 RAM의 1/2로 README 가정과 일치 |
| C5 메모리 | 일부 완료 | 아래 표, 캐시–GPU 할당 실험은 `results/p0/summary.md` ③ | PyTorch 미설치로 런타임 오버헤드는 미측정 |
| C8 플래너 | 통과 (형식), 내용 품질 부족 | llama.cpp(commit e3797b1, CUDA sm_87), Qwen3-4B Q4_K_M: 입력 1,653토큰 prefill 2.84초, 생성 15.4 tok/s, 결정 1회 16–21초, JSON 3/3 유효, 메모리 약 4.1GB | README 추정 3.0GB보다 메모리가 큼 |
| 판단 실험 ①②③ | 완료 | `results/p0/summary.md` | 로컬 OST가 원격보다 15–22배 빠름, 로컬 KV 복원이 prefill보다 7–12배 빠름 |
| C9 시간 동기화 | 미달 | systemd-timesyncd, NTP 기준 오프셋 12–30ms | 목표 1ms |
| C3, C6, C7, C10, C11 | 이번 범위 아님 | – | – |

**C2: client(jetson) → OST 대역폭 (2GiB 파일, libaio, iodepth 16)**

| 레이아웃 | 쓰기 4M direct (3회 평균) | 읽기 4M direct | 쓰기 1M direct | 읽기 1M direct | 쓰기 4M buffered | 읽기 4M buffered |
|---|---|---|---|---|---|---|
| OST0000 (jetson1) | 93.5MB/s | 114.8MB/s | 92.4MB/s | 114.8MB/s | 65.4MB/s | 113.6MB/s |
| OST0001 (jetson2) | 93.3MB/s | 114.8MB/s | 92.7MB/s | 114.8MB/s | 65.2MB/s | 113.7MB/s |
| OST0002 (jetson3) | 93.3MB/s | 114.6MB/s | 92.7MB/s | 114.6MB/s | 65.1MB/s | 113.4MB/s |
| stripe count 2 (OST0–1) | 93.2MB/s | 114.8MB/s | – | – | – | – |
| stripe count 3 (OST0–2) | 93.3MB/s | 114.7MB/s | – | – | – | – |

- 쓰기는 jetson 송신 한계(약 725Mb/s), 읽기는 1GbE 한계에 걸린다.
- stripe count를 늘려도 단일 client 대역폭은 변하지 않는다(README O1 가설과 일치).
- buffered 쓰기는 direct보다 약 30% 느리다.
- buffered 읽기 후 client page cache가 약 2GB 늘어난다.
- OSS 메모리는 측정 중 변화가 없다(서버 측 캐시 꺼짐).

**C5: 메모리 실측 (jetson)**

| 항목 | 값 |
|---|---|
| drop_caches 후 MemAvailable | 5,443MiB (다른 프로세스 약 1.8GB 포함) |
| 서버 노드 MemAvailable (유휴) | 약 6,550–6,600MiB |
| CUDA 컨텍스트 (64MiB 버퍼 제외) | 약 74MiB |
| 2GiB buffered 읽기, 캐시 상한 3,810MB | MemFree −2,162MiB, Cached +2,048MiB, llite used 2,048MB, MemAvailable −105MiB |
| 2GiB buffered 읽기, 캐시 상한 512MB | MemFree −520MiB, Cached +488MiB, llite used 378MB |
| Lustre 서버 memused | 약 120MiB |

- `MemAvailable`은 page cache를 회수 가능으로 계산하므로 캐시 증가를 거의 반영하지 않는다.
- unified memory에서 GPU 할당과 캐시 회수의 상호작용(할당 지연, 실패)은 O2·O4에서 직접 측정해야 한다.
