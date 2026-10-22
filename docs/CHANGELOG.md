# 변경 이력

> README의 변경 이력과 이전 설계에서 바뀐 내용, 완료한 점검 항목을 모은다.

## 1. 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-10-22 | README 정리: 상세 자료를 `docs/related_work.md`, `docs/motivation_details.md`, `docs/design_details.md`, `docs/experiment_plan.md`, `docs/CHANGELOG.md`로 옮기고 본문을 요약 중심으로 재구성 |
| 2026-10-22 | M8·M10·M14를 `--cache-ram 0`으로 재측정해 반영. M14(KV 배치 정책별 TTFT) 절과 그림 추가, 3.15–3.17절 재배열 |
| 2026-10-22 | 연구 방향 수정: 저장 I/O의 LLM 연산 감속은 3% 이내로 작아 주장에서 제외. 간섭을 공유 자원(OSS, NIC, 메모리)과 쓰기 시점으로 재정의하고 위치·배치 중심으로 문제, 비용 모델, ③, 실험 계획, 예상 반론 갱신 |
| 2026-10-22 | 3장에 M7(OSS 공유), M10(jetson1 멈춤 분석), M11(runtime-aware), M12(read-aware relocation) 추가, 3.8–3.16절로 재배열 |
| 2026-10-22 | 3장에 M8(원격 I/O와 LLM), M9(NIC 공유), M13(소파일과 pack), IFLustre 계승 표 추가. M1 striping 재측정 |
| 2026-10-22 | 설계를 비파괴 구성 A'로 변경: jetson1–3 = 저장+연산 3-stage, jetson = 제어·수집·대체 stage, jetson0 = MDS + 플래너. 용어 정리(설비 → 데이터 스트림, 질의 → 요청, 불변 객체 표현 삭제) |
| 2026-10-22 | 3장 Motivation(테스트베드 실측, 그림 7종) 신설, 이후 장 번호 한 칸씩 이동. 5-OST 방안 제외 |
| 2026-10-22 | P0 점검 결과 반영: 실제 구성(4.1.2), 메모리 실측(4.1.4), 판단 실험 결과와 연구 중심 조정(8.3), 미결 사항 갱신. 상세는 `docs/testbed.md`, `docs/hyperconverged_plan.md`, `results/p0/summary.md` |
| 2026-10-22 | 용어 변경: "소비 stage", "소비 노드", "소비 위치"를 "사용 노드"(그 데이터를 읽어 쓰는 노드)로 통일 |
| 2026-10-21 | 의미 기반 content-addressed KV 저장소로 ② 재설계: 스트림 단위 이어 쓰기 컨텍스트, 수집 시점 prefill, 이름(내용)·위치(비용 모델)·정책(IoT 의미) 분리, pack 저장, 규칙 기반 압축, 상위 LG LoRA와 경계 activation 기반 부분 재생성. CAS 배경과 KV 사전 계산 관련 연구 추가, O7·S7·B8·C10·C11 추가, 현재 실제 구성(jetson0–3, jetson) 기록, 예상 반론과 판단 기준 추가 |
| 2026-10-21 | 논문 제목(가제)과 시스템 이름 CoStripe 확정 |
| 2026-10-21 | 대상 장비를 Orin Nano 8GB × 5, 1GbE로 변경. Qwen3-4B FP16, 서빙 파이프라인 공동 학습, N0 역할 재정의 |
| 2026-10-21 | 논문 구조로 재구성, 관련 연구 확장 |
| 2026-10-21 | 연구 설계 초안 작성 (AGX Orin 64GB 가정, Qwen3-32B) |

## 2. 설계 변경 요약 (초기 설계 대비)

| 항목 | 이전 설계 | 현재 설계 | 이유 |
|---|---|---|---|
| 대상 장비 | AGX Orin 64GB 가정 | Orin Nano 8GB × 5, 1GbE | 실제 장비 |
| 서빙 모델 | Qwen3-32B FP16 | Qwen3-4B FP16 (약 8.0GB), 3-stage, LG 12개 | 8GB 노드 1대에 들어가지 않고 3대에 나누면 노드당 2.4–3.2GB |
| KV 재사용 | 요청 시점 prefix 해시 재사용 | 스트림 단위 이어 쓰기 컨텍스트 + 수집 시점 prefill + content-addressed 객체 | 슬라이딩 윈도우에서 prefix 재사용이 깨짐 |
| KV 저장 단위 | (prefix, LG) 파일에 chunk append | (컨텍스트, LG, epoch) 단위 pack 파일 + 내용 주소 검증 | 메타데이터 비용 감소, 위치 독립성 |
| 적응 학습 | 전체 layer LoRA | 상위 LG(기본 LG9–11)에만 LoRA | 하위 LG의 KV가 어댑터 버전과 무관하게 유효 |
| KV 재생성 | 고려 없음 | 상위 LG 입력 activation을 저장해 두고 상위 LG만 다시 계산 | 어댑터 전환 시 재계산 비용 약 75% 감소 |
| 노드 역할 | 5-OST, N0 = 제어 + 플래너 + 전체 가중치 mirror | 비파괴 구성 A': jetson1–3 = OSS + 서빙 stage, jetson(N0) = 제어·수집·대체 stage, jetson0(NM) = MDS + 플래너 | 기존 Lustre를 다시 만들지 않는다. 5-OST 구성은 장치 추가와 MDT 재구축이 필요해 제외 |
| 간섭 분석 | 메모리 대역폭 | 공유 자원(OSS, NIC, 노드 메모리)과 쓰기 시점. 저장 I/O의 LLM 연산 감속은 주장에서 제외 | 실측(3장): 연산 감속 3% 이내, OSS·NIC·메모리 공유와 배치는 2–10배 차이 또는 노드 정지 |

## 3. 완료한 점검·결정 항목

- [x] 노드별 Super 여부, JetPack, 전력 모드 (5대 모두 Super, L4T R36.4.4, 25W)
- [x] 노드별 NVMe 장착 여부, 모델, 용량 (jetson0–3 장착, jetson 없음). raw 대역폭은 Lustre 외 파일 시스템이 없어 미측정
- [x] OS 설치 위치 (5대 모두 microSD)
- [x] zram 설정 (6 × 635MB = 3.8GB) — 실험 중 유지·비활성화 여부는 미결
- [x] 유선·무선 경로와 LNet NID 인터페이스 (데이터 경로는 유선, 서버 MGS 연결은 무선 IP로 설정되어 끊김)
- [x] 유선 NIC 실측 대역폭 (약 930Mb/s, jetson 송신만 약 725Mb/s)
- [x] Lustre 버전, 백엔드, 기능 지원, `max_cached_mb` 기본값 (2.17.0, ldiskfs, C1 통과, 3,810MB)
- [x] 5-OST 구성(방안 B)은 제외
- [x] 비파괴 구성 A' 채택 (2026-10-22): jetson1–3 = 저장+연산 3-stage, jetson = 제어·수집·대체 stage, jetson0 = MDS + 플래너. 4장 설계를 3-stage 기준으로 갱신함
- [x] jetson1–3 client 마운트 적용 (비영구, 캐시 상한 512MB). 재부팅하면 사라지므로 노드가 재시작되면 다시 마운트해야 한다
- [x] 논문 제목과 시스템 이름: CoStripe (가제, 투고 전 최종 확인)
- [x] jetson1 멈춤(F7) 원인 확인: llama-server의 호스트 RAM prompt cache(기본 8GiB)와 같은 노드 Lustre I/O의 메모리 소진. `--cache-ram 0`과 메모리 보호로 M8, M10, M14 재측정(멈춤 없음)
