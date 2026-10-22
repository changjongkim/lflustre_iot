# 하이퍼컨버지드 구성 전환 계획서 (P0)

> 작성: 2026-10-22, P0 점검 결과 기준
> 상태: 검토용 초안. 아래 명령은 실행하지 않았다. 실행 전 사용자 승인이 필요하다.

## 1. 현재 구성 (실측)

| 호스트 | Lustre 역할 | NVMe | NVMe 사용 | OS 위치 | client 마운트 |
|---|---|---|---|---|---|
| jetson0 | MGS + MDT0000 | Samsung 970 EVO Plus 500GB | p1 8GB MGT, p2 457.8GB MDT (사용 약 0.2GB) | microSD 477.5GB | 없음 (client 모듈은 로드됨) |
| jetson1 | OSS, OST0000 | Samsung 980 500GB | 장치 전체가 OST (사용 94GB) | microSD 477.5GB | 없음 (client 모듈은 로드됨) |
| jetson2 | OSS, OST0001 | Samsung 980 500GB | 장치 전체가 OST (사용 36GB) | microSD 477.5GB | 없음 |
| jetson3 | OSS, OST0002 | Samsung 980 500GB | 장치 전체가 OST (사용 20GB) | microSD 477.5GB | 없음 |
| jetson | client | 없음 | – | microSD 238.5GB | `/mnt/lustrefs` |

## 2. README 설계와의 차이

| README 설계 | 실제 | 영향 |
|---|---|---|
| N0(jetson0)에 OST0 | jetson0 NVMe는 MGT·MDT가 전부 사용 | OST0을 만들려면 MDT 재포맷(파일 시스템 재구축) 또는 microSD 사용이 필요 |
| N4(jetson)에 OST4 | jetson에 NVMe 없음 | OST4를 만들려면 NVMe 장착이 필요 |
| 모든 노드에 client 마운트 | client는 jetson에만 마운트 | 서버 노드에 client 마운트 필요 (모듈은 이미 로드되어 있어 설치 불필요) |
| 서버의 MGS 연결 정상 | MDT와 OST 3대의 MGC가 `192.168.0.60@tcp`(무선 IP)로 연결 시도 중, CONNECTING 상태 | 영구 설정(`set_param -P`), OST pool, 새 OST 등록 등 MGS가 필요한 작업이 실패할 수 있음 |

## 3. 방안 비교

| 방안 | 내용 | 파괴적 작업 | 하드웨어 추가 |
|---|---|---|---|
| A | jetson0–3에 client 마운트만 추가. OST는 그대로 3개 | 없음 (마운트 해제로 원복) | 없음 |
| A' | A + 역할 재배치: stage 노드 = jetson1–3 (로컬 OST 보유), jetson = 제어·수집·플래너, jetson0 = MDS | 없음 | 없음 |
| B | README와 같은 5-OST 구성: jetson에 NVMe 장착 후 OST 추가, jetson0는 NVMe 재분할 후 OST 추가 | jetson0 MDT 재포맷 → 파일 시스템 재구축 (기존 데이터 약 150GB 백업 필요) | jetson용 NVMe 1개 |
| C | 현재 분리형 구성 유지, 관찰 실험의 비교 기준으로만 사용 | 없음 | 없음 |

### 방안 A / A' 절차 (작성만 함)

1. (권장 선행) 서버 MGS 주소 정정. 대상 노드에서 해당 target을 잠시 내려야 한다.
   ```bash
   # MDT (jetson0) — MGS와 같은 노드
   umount /mnt/lustre/mdt0
   tunefs.lustre --erase-param mgsnode --mgsnode=192.168.0.50@tcp /dev/nvme0n1p2
   mount -t lustre /dev/nvme0n1p2 /mnt/lustre/mdt0
   # OST (jetson1–3) — 노드별로 순차 진행
   umount /mnt/lustre/ost<N>
   tunefs.lustre --erase-param mgsnode --mgsnode=192.168.0.50@tcp /dev/nvme0n1
   mount -t lustre /dev/nvme0n1 /mnt/lustre/ost<N>
   ```
2. 서버 노드에 client 마운트
   ```bash
   mkdir -p /mnt/lustrefs
   mount -t lustre 192.168.0.50@tcp:/lustrefs /mnt/lustrefs
   lctl set_param llite.*.max_cached_mb=512     # 비영구, 8GB 노드 보호
   ```
3. 되돌리기: `umount /mnt/lustrefs`

### 방안 B 절차 요약 (작성만 함)

1. 기존 데이터(약 150GB) 백업
2. jetson에 NVMe 장착 → `mkfs.lustre --ost --fsname=lustrefs --index=3 --mgsnode=192.168.0.50@tcp /dev/nvme0n1`
3. jetson0 NVMe 재분할: MGT 8GB / MDT 약 50GB / OST 나머지 → MGT·MDT 재포맷, 파일 시스템 재구축
4. 모든 노드에 client 마운트
5. 되돌리기: 사실상 불가 (재구축)

## 4. 위험

| 위험 | 해당 방안 | 대응 |
|---|---|---|
| client와 OSS를 같은 노드에 둘 때 메모리 압박에 의한 hang | A, A', B | client 캐시 상한(512MB 이하), C3 안정성 시험 후 진행 |
| GUI(graphical.target)가 메모리 약 0.5–1GB 사용 | 전부 | 실험 기간 multi-user.target으로 전환 검토 (사용자 승인 필요) |
| zram 스왑 3.8GB가 메모리 압박 측정에 영향 | 전부 | 실험 조건으로 고정·기록, 비활성화 여부 결정 필요 |
| MGS 미연결 상태에서 설정 변경 실패 | 전부 | 1단계에서 MGS 주소 정정 |
| 재구축 중 데이터 손실 | B | 백업 후 진행 |

## 5. README 설계에 주는 영향

| 항목 | A' 적용 시 |
|---|---|
| N0–N4 대응 | stage 노드는 jetson1–3 (로컬 OST 보유). jetson은 제어·수집·플래너 (README의 N0 역할), jetson0는 MDS 전용 또는 4번째 stage (로컬 OST 없음) |
| 파이프라인 stage 수 | 3-stage(jetson1–3)이면 Qwen3-4B FP16 stage당 LG 4개(약 2.4GB, 양 끝 stage는 임베딩 포함 약 3.2GB). 메모리 실측(C5) 후 결정 |
| OST0 mirror (연산 없는 노드의 복제본) | 연산 없는 노드의 OST가 없음 → 가중치·봉인 pack의 mirror를 인접 stage 노드 OST에 둠 |
| 장애 대체 노드 | jetson(로컬 OST 없음)이 대체 stage를 맡고 원격으로 로드, 또는 2-stage 재분할 |
| KV pack 로컬 배치 | stage 노드(jetson1–3)는 가능. jetson0를 stage로 쓰면 그 stage는 원격만 가능 |

## 6. 추천

1. **지금:** 방안 A'로 진행한다. 파괴적 작업 없이 "스토리지 서버 = 연산 노드" 조건을 jetson1–3에서 바로 만들 수 있다. 선행 작업으로 MGS 주소를 정정한다.
2. **비교 기준:** 현재 분리형 구성(방안 C)을 관찰 실험의 비교 기준으로 함께 쓴다(client 전용 노드 jetson 기준 측정).
3. **방안 B 판단:** A'에서 O1–O4를 측정한 뒤, 5-OST 구성이 필요하다고 판단될 때 NVMe 추가와 재구축 일정을 따로 정한다.
4. **실험 전 결정 필요:** GUI 비활성화 여부, zram 설정, PyTorch 설치 방식.
