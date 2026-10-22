# 추가 Motivation 실험 계획 (M7–M14)

> 작성: 2026-10-22. 3장 M1–M6 이후의 실측 계획이다. 구성은 비파괴 방안 A'(jetson1–3 = 저장+연산 stage, jetson = 제어·수집, jetson0 = MDS + 플래너)를 따른다.
> 도구: `experiments/motivation/` (노드 내부 샘플러, LLM 요청 프로브, activation 전달 프로브, 실험별 실행 스크립트)
> 결과: `results/motivation/<실험>/`

## 1. 무엇을 더 보여야 하는가

M1–M6는 두 가지를 보였다. 데이터 위치가 접근 시간을 15–22배 바꾼다(M2, M3). Lustre 캐시가 8GB 메모리를 잠식한다(M4). 논문 주장을 세우려면 아래 세 가지가 더 필요하다.

1. **원 IFLustre의 전제가 엣지에서도 성립한다.** 이것이 없으면 "IFLustre 확장"이 아니라 새 시스템이 된다. OSS 공유 간섭, 가장 느린 OSS의 지배, 시점 지연의 이득, 읽기 기반 재배치의 이득, 소파일의 한계를 엣지에서 다시 측정한다.
2. **하이퍼컨버지드 구성에서 새 간섭이 생긴다.** IFLustre는 OSS 사이의 간섭만 본다. 같은 노드의 저장 I/O와 LLM 연산, NIC를 함께 쓰는 저장 I/O와 pipeline activation, 저장 캐시와 LLM 메모리 사이의 간섭을 측정한다.
3. **IFLustre의 결정 방식만으로는 부족하다.** IFLustre는 OSS 부하만 보고, 앱 이름별 과거 로그로 시작 시 한 번 결정한다. 소비 위치와 연산 부하를 무시한 배치가 TTFT를 얼마나 늘리는지 작은 end-to-end 실험으로 보인다.

## 2. IFLustre 이점의 계승

| 원 IFLustre 정책·관찰 | 엣지(A')에서의 형태 | 증명 실험 | CoStripe 반영 |
|---|---|---|---|
| Interference-free allocation (OSS 공유 회피) | OSS마다 1GbE NIC가 상한이다. 두 흐름이 한 OSS를 공유하면 각자 절반이 된다 | M7 | 동시 흐름을 서로 다른 OSS로 분산 |
| 가장 느린 OSS가 성능을 결정 | 여러 OST에 걸친 파일은 바쁜 stage 노드의 OST가 전체 속도를 정한다 | M7 | stripe count 1 + 소비 노드 배치 |
| Throughput-aware allocation (많은 OSS 사용) | 단일 client는 자기 NIC가 상한(M1). 다수 client의 총합은 OSS 수만큼 늘어난다 | M7 | 흐름 단위 분산, 파일 단위 striping은 사용하지 않음 |
| Runtime-aware allocation (대기 vs 공유) | 체크포인트·복제·수집 시점 prefill 쓰기가 KV 복원과 겹치면 TTFT가 늘어난다 | M11 | 백그라운드 I/O의 시점 지연과 TBF 속도 제한 |
| Read-aware relocation (IoTJ) | 반복 읽히는 KV pack은 소비 노드 OST로 옮기면 이후 7–12배 빨라진다 | M12 | 재사용 횟수 기반 migrate/mirror |
| 소파일 관찰 (IoTJ) | IoT 레코드를 파일 단위로 쓰면 MDS 요청이 병목이고 striping은 효과가 없다 | M13 | pack append 저장 |
| (확장) 간섭 범위: 같은 노드 연산 | 저장 I/O가 같은 노드의 prefill·decode를 늦춘다. 반대 방향도 측정 | M8 | 비용 모델 β_k |
| (확장) 간섭 범위: 네트워크 | 저장 I/O가 stage 사이 activation 전달을 늦춘다 | M9 | 비용 모델 A_k, U_k |
| (확장) 간섭 범위: 메모리 | 캐시와 KV 복원이 LLM 메모리를 압박한다 | M10 | 메모리 제약, 캐시 상한 |

IFLustre 이점 유지는 평가에서도 확인한다. LLM이 없는 IoT 수집 워크로드(원 IFLustre의 6종 데이터셋)에서 CoStripe가 IFLustre(B2)보다 나빠지지 않아야 한다. 연산 부하가 0이면 CoStripe 비용 모델은 IFLustre와 같은 결정을 내려야 한다(README 4.9.3).

## 3. 실험 상세

| ID | 질문 | 구성 | 조건 | 측정 | 필요 조건 | 소요 |
|---|---|---|---|---|---|---|
| M7 | OSS 공유 간섭과 가장 느린 OSS가 엣지에서도 나타나는가 | client 3개(jetson, jetson1, jetson3)가 동시에 fio | (a) 세 흐름이 같은 OST (b) 서로 다른 OST (c) 3-stripe 파일 읽기 + 한 OST에 다른 흐름 | 흐름별·총 처리량 | jetson1–3 client 마운트 | 15분 |
| M8 | 같은 노드의 저장 I/O가 LLM prefill·decode를 얼마나 늦추는가, 반대로 LLM이 I/O를 얼마나 늦추는가 | jetson1 llama-server(Q4_K_M, 모델 로컬 디스크) | idle / 원격 읽기·쓰기(jetson → OST0000) / 로컬 direct·buffered 읽기·쓰기 | prefill tok/s, decode tok/s, 토큰 간격 p99, fio 처리량, CPU·EMC·GPU | 원격 조건: 없음. 로컬 조건: jetson1 client 마운트 | 원격 15분, 로컬 20분 |
| M9 | 저장 I/O가 stage 사이 activation 전달을 얼마나 늦추는가 | jetson1 → jetson2 TCP 전달 (prefill 2k·8k 묶음, decode 5KiB 토큰 메시지 20Hz) | idle / jetson2 수신 링크 공유 / jetson1 송신 링크 공유 / 둘 다 | 전달 시간, 왕복 p50·p99, fio 처리량 | 없음 | 10분 |
| M10 | 저장 캐시와 KV 복원이 LLM 메모리를 압박하면 어떻게 되는가 | jetson1 llama-server 상주 + 같은 노드 buffered 읽기 | 캐시 상한 기본 / 512MB / direct I/O | decode tok/s, TTFT, 회수(kswapd, direct reclaim), zram 사용, OOM 여부 | jetson1 client 마운트, 메모리 압박 시험 승인 | 20분 |
| M11 | 백그라운드 쓰기의 시점 지연(runtime-aware)이 KV 복원을 보호하는가 | jetson3: 주기적 KV slot 복원(4k, 576MiB) + 체크포인트 쓰기(1GiB) | 동시 / 복원 후 지연 / TBF 속도 제한 | 복원 시간 분포, 체크포인트 완료 시간 | jetson3 client 마운트 | 20분 |
| M12 | 읽기 기반 재배치(read-aware relocation)가 KV에서 언제 이득인가 | jetson1: 원격 OST에 있는 KV를 k번 재사용 | 항상 원격 / 매번 재계산 / 첫 사용 후 `lfs migrate`로 로컬 이동 | 누적 시간, 손익분기 재사용 횟수, migrate 중 간섭 | jetson1 client 마운트 | 15분 |
| M13 | IoT 레코드를 파일 단위로 쓰는 것과 pack에 붙이는 것의 차이 | jetson(client) | 레코드당 파일 / 256KiB 창 파일 / pack append, stripe count 1·3 | 레코드/s, MB/s, 레코드당 MDS 요청 | 없음 | 5분 |
| M14 | 소비 위치·연산 부하를 무시한 배치가 TTFT를 얼마나 늘리는가 (작은 end-to-end) | jetson1–3 각자 llama-server, 컨텍스트 12개를 Zipf로 요청, jetson이 수집 쓰기 | KV 배치: Lustre 기본 할당 / IFLustre식 OSS 부하 기반 / 소비 노드 배치 | TTFT p50·p99, 처리량, 노드별 I/O | jetson1–3 client 마운트, 프로토타입 `kv_router.py` | 40분 |

## 4. 진행 상황 (2026-10-22)

| 실험 | 상태 | 결과 요약 |
|---|---|---|
| M1 재측정 | 완료 | stripe 1–3 쓰기 93MB/s, 읽기 115–118MB/s. 레이아웃과 OSS별 송수신량으로 분산 확인 |
| M7 | 완료 | OSS 하나 공유 시 합계 120MB/s, 분산 시 303(읽기)·243(쓰기)MB/s. 붐비는 OST 하나가 3-stripe 쓰기를 25% 늦춤 |
| M8 원격 조건 | 일부 완료 | 원격 읽기: prefill −1.3%, decode −0.6%. 원격 쓰기: jetson1 멈춤(F7)으로 측정 못 함 |
| M9 | 완료 | activation 전달 2.0배(수신 링크 공유), 4.1배(송신 링크 공유). decode 메시지 왕복 0.6 → 4.6ms |
| M10 | 중단 | 측정 중 jetson1 멈춤. 감시 기록으로 메모리 소진(MemAvailable 41MB, zram 3.4GB) 확인 |
| M11 | 완료 | KV 복원 663ms → 동시 체크포인트 932ms(+41%), 100MB/s 제한 696ms, 지연 679ms(+2%) |
| M12 | 완료 | 원격 KV 5회 사용: 재계산 35.1초, 원격 유지 27.3초, 첫 사용 후 이동 14.8초 |
| M13 | 완료 | 레코드당 파일 약 220 rec/s, pack 6,642 rec/s(30배), MDS 요청 1/1,500 |
| M8 로컬, M10 재측정, M14 | 대기 | 메모리 보호(`memguard.sh`)를 켜고 실행. 실행 권한 확인 필요 |

## 5. 실행 순서

1. **지금 실행 (마운트 추가 없음):** M9, M8 원격 조건, M13
2. **A' 적용 후 (jetson1–3 client 마운트, `max_cached_mb=512` 비영구 설정, 끝나면 umount):** M7, M8 로컬 조건, M11, M12
3. **별도 승인 후:** M10 (메모리 압박 시험)
4. **프로토타입 후:** M14

## 6. 프로토타입 범위

| 단계 | 내용 | 용도 |
|---|---|---|
| 측정 도구 (완료) | `sampler.py`(노드 내부 1초 샘플, F6 대응), `llm_probe.py`(prefill·decode·토큰 간격), `act_probe.py`(activation 전달 모사) | M7–M13 |
| KV 라우터 (예정) | 컨텍스트별 KV slot 파일을 정책에 따라 OST에 두고, 요청을 컨텍스트 담당 노드로 보내 복원 후 응답 | M14, 평가의 B0·B2·CoStripe 비교 축소판 |
| 3-stage 모사 (검토) | llama.cpp RPC 백엔드로 layer를 jetson1–3에 나눠 올림. PyTorch 런타임 전에 pipeline 간섭을 미리 확인 | O3 예비 측정 |
