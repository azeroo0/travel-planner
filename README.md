<div align="center">

<img src="https://raw.githubusercontent.com/sunub/travel-planner/main/frontend/public/logo.png" alt="어디갈건호?" width="260" />

# 🐵 어디갈건호? (TripFit)

**어디 갈지 고민될 땐, 리뷰한테 물어봐요.**

부산 호텔·식당·관광지 리뷰를 AI가 읽고, 내 조건에 맞는 장소를 **근거 문장과 함께** 추천해 주는 서비스

[🤗 Hugging Face 어댑터](https://huggingface.co/sunub/tripfit-busan-review-qwen3-4b-qlora-v3) ·
[🦙 Ollama · Qwen3](https://ollama.com/bsc5672/qwen3-tripfit) ·
[🦙 Ollama · EXAONE](https://ollama.com/hinoonyaso/exaone-tripfit) ·
[📊 평가 보고서](docs/evaluation/2026-09-29-base-vs-qlora.md) ·
[🔌 API 명세서](frontend/어디갈건호%20API%20명세서.md)

</div>

<br />

## 📌 서비스 소개

- 🗣️ **자연어로 조건 입력** — "부모님과 가고, 걷기는 적게, 바다는 보고 싶어요"처럼 말하면 됩니다.
- 🧠 **리뷰를 구조화** — 파인튜닝한 Qwen3-4B(QLoRA)가 리뷰에서 **Context · Aspect · Attribute · Sentiment · Evidence**를 뽑습니다.
- 📈 **장소별 Review Profile** — 청결·주차·소음·접근성·서비스 등 항목별 긍정/부정 비율을 DB에서 집계합니다.
- 🔎 **근거 리뷰 확인** — 항목을 누르면 모델이 뽑은 **근거 문장이 원문에서 강조**되어 보입니다. 최종 선택은 사용자가 합니다.

## 🎯 프로젝트를 시작하게 된 계기

1. 별점만으로는 장소의 실제 특징을 알기 어렵습니다.
2. 사용자가 수많은 리뷰를 직접 읽어야 합니다.
3. 청결·주차·소음·접근성·서비스 정보가 자연어 문장 속에 흩어져 있고, 번역체·길이 제각각의 리뷰가 섞여 있습니다.

> 비에이 투어 리뷰를 사람이 읽고 비교하던 작업을 AI가 구조화하도록 만들고, 대상을 **부산의 호텔·식당·관광지**로 확장했습니다.
> AI는 장소를 외워 추천하지 않습니다. **리뷰를 읽고 근거를 정리**하며, 순위는 DB에 쌓인 라벨을 코드로 계산합니다.

<br />

## ✨ 서비스 둘러보기

### 1️⃣ 조건을 말하면 리뷰가 장소를 추천한다

| 시작 · 자연어로 조건 입력 | 대화 · 동행·걷기·원하는 점 질문 | 추천 · 조건에 맞는 장소와 적합도 |
| :---: | :---: | :---: |
| <img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/service-01-start.png" width="220" /> | <img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/service-02-chat.png" width="220" /> | <img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/service-03-recommend.png" width="220" /> |

### 2️⃣ 리뷰 분석과 근거 문장을 함께 보여준다

| 장소 상세 · aspect별 감성 비율과 건수 | 근거 리뷰 · 모델이 뽑은 evidence를 원문에서 강조 |
| :---: | :---: |
| <img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/service-04-detail.png" width="220" /> | <img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/service-05-evidence.png" width="420" /> |

### 3️⃣ 모델은 이런 결과를 만든다

**입력**

```
[category]
attraction

[review]
부모님과 갔는데 사진은 정말 잘 나오지만 언덕이 많아서 힘들었어요.
```

**출력**

```json
{
  "traveler_context": ["parents"],
  "aspects": [
    {"category": "photo_spots", "attribute": "good", "sentiment": "positive", "evidence": "사진은 정말 잘 나오지만"},
    {"category": "slope_stairs", "attribute": "high", "sentiment": "negative", "evidence": "언덕이 많아서 힘들었어요"}
  ]
}
```

| 구성 요소 | 의미 | 예시 |
| --- | --- | --- |
| Context | 누가 / 어떤 상황 (리뷰에 적힌 경우만) | `parents`, `couple`, `friends`, `solo`, `family_with_kids` |
| Aspect · Attribute | 무엇에 대한 말이며 어떤 상태인가 | `slope_stairs` → `high` |
| Sentiment | 그 상태에 대한 평가 | `positive` / `negative` / `neutral` |
| Evidence | 판단 근거가 된 **원문 그대로의 구절** | `"언덕이 많아서 힘들었어요"` |

> 허용 값은 [`datas/common/schema.py`](datas/common/schema.py), 라벨링 규칙은 [`docs/annotation-guideline.md`](docs/annotation-guideline.md)가 기준입니다. (호텔 12 · 식당 13 · 관광지 11개 aspect)

<br />

## 📊 모델 성능과 배포

### 최종 모델: Qwen3-4B-Instruct-2507 + QLoRA v3 + 후처리

사람이 원문과 대조해 승인한 **실제 리뷰 50건**(호텔 15 · 식당 20 · 관광지 15, 정답 aspect 143개) 기준입니다.

| 모델 | Precision | Recall | Aspect F1 |
| --- | ---: | ---: | ---: |
| **Qwen v3 (최종)** | 0.611 | 0.636 | **0.623** |
| Qwen v2 | 0.571 | 0.643 | 0.605 |
| yny | 0.628 | 0.566 | 0.596 |
| sang-adapter | 0.533 | 0.622 | 0.574 |

- 50건 표본과 부트스트랩 95% 신뢰구간이 겹쳐 **모델 간 차이는 통계적으로 확실하지 않아**, 성능·동행 유형·출력 안정성·재현성을 종합해 v3를 선택했습니다.
- 호텔 0.70 · 식당 0.79 · **관광지 0.29**. 관광지는 라벨 기준이 모호해 가장 낮습니다.
- **0.623은 후처리를 포함한 값**입니다. 후처리 전 0.521 → 후 0.623(+0.10)이며, QLoRA 자체의 향상이 아닙니다.
- 파인튜닝 효과(EXAONE-2.4B, 합성 Gold 172건): Base + 라벨 목록 **0.355** → QLoRA **0.806**.

### 배포된 모델

| 모델 | 플랫폼 | Base | 형태 | 실행 |
| --- | --- | --- | --- | --- |
| [`sunub/tripfit-busan-review-qwen3-4b-qlora-v3`](https://huggingface.co/sunub/tripfit-busan-review-qwen3-4b-qlora-v3) | 🤗 Hugging Face | Qwen3-4B-Instruct-2507 | LoRA 어댑터 (약 47MB) | `python inference/example.py --adapter . --category hotel --review "..."` |
| [`bsc5672/qwen3-tripfit`](https://ollama.com/bsc5672/qwen3-tripfit) | 🦙 Ollama | Qwen3-4B-Instruct-2507 | 병합 + GGUF Q4_K_M (약 2.5GB) | `ollama run bsc5672/qwen3-tripfit:qlora-v3` |
| [`hinoonyaso/exaone-tripfit`](https://ollama.com/hinoonyaso/exaone-tripfit) | 🦙 Ollama | EXAONE-3.5-2.4B-Instruct | 병합 + GGUF q4_k_m (약 1.5GB) | `ollama run hinoonyaso/exaone-tripfit:qlora-v2` |

> [!IMPORTANT]
> **후처리는 모델 밖에 있습니다.** Ollama 모델에는 후처리가 들어 있지 않으므로 호출하는 쪽에서 `postprocess`(HF 저장소의 `inference/tripfit_postprocess.py` 또는 [`postprocess.py`](src/travel_planner/model_cjm/postprocess.py))를 적용해야 합니다. 쓰지 않으면 F1이 0.52 수준입니다.

> [!CAUTION]
> 학습 데이터는 전부 **합성 리뷰**이고, 평가 리뷰의 약 78%가 기계번역문입니다. Qwen3 GGUF(양자화) 모델의 재평가 수치는 아직 없습니다. 리뷰 한 건을 그대로 보여주는 용도보다 **장소별 집계**에 적합합니다.

<br />

## 🔥 핵심 기술적 도전

### 1. 실제 리뷰를 모을 수 없어 합성 리뷰로 학습했다
Tripadvisor는 로봇·스크래퍼·AI 시스템의 서면 허가 없는 수집을, Airbnb는 봇·크롤러 사용을 약관으로 금지하고 수집 기간도 짧았습니다. **소량의 실제 리뷰를 참고해 합성 리뷰를 생성**해 학습하고, **평가만 사람이 검수한 실제 리뷰(Human Gold)** 로 했습니다. 합성 리뷰는 `is_synthetic`으로 표시하며 실제 리뷰로 취급하지 않습니다.

| 데이터 | 건수 | 성격 | 용도 |
| --- | ---: | --- | --- |
| Train / Validation | 2,578 / 371 | 합성 + 자동 검사 통과 (Silver) | 학습 / 체크포인트 선택 |
| Synthetic Test | 172 | 합성, 사람 승인 | 참고용 |
| 실제 리뷰 초안 | 146 | 실제 + Claude 초안 | 검수 전 중간 단계 |
| **Human Gold** | **50** | **실제, 사람이 원문과 대조해 승인** | **최종 채점 기준** |

> **Gold**는 사람이 최종 승인한 데이터(누가 초안을 썼든 무관), **Silver**는 Teacher LLM(gemma4:e4b)이 만들고 *자동 검사만* 통과한 데이터입니다. 모든 레코드에 등급을 남기고, 테스트 셋은 Gold만 씁니다. 자세한 제작 과정은 [`datas/common/README.md`](datas/common/README.md)를 참고하세요.

### 2. 합성 test 0.78 → 실제 리뷰 0.52, 높은 학습 성능이 일반화를 보장하지 않았다
Train loss 0.91 → 0.027, 검증 token accuracy 0.985로 학습은 안정적이었지만 실제 리뷰에서는 Aspect F1이 0.26 떨어졌습니다. **합성 test는 참고용으로 격하하고, 실제 Gold 50건을 최종 기준**으로 바꿨습니다.

### 3. 모델이 말하지 않은 aspect를 만들어 낸다 → 재학습보다 원인별 후처리
리뷰당 평균 aspect 수가 정답 2.86, 합성 3.53, **예측 4.28**이었습니다. 라벨 불일치(`cleanliness` vs `room_condition`)와 근거 문장 표현 차이도 원인이었습니다.

```
Review → Qwen3-4B + QLoRA v3 → Raw JSON
       → [후처리] JSON 복구 → 스키마 검증 → 근거 검증 → 주제 단어 검증 → 중복 제거
       → 구조화된 리뷰 데이터 → 추천 서비스
```

예) 모델이 `parking_easy`를 출력했지만 근거가 "위치를 찾기 쉬웠다"라서 주차 단어가 없으면 **제거**합니다.

### 4. 관광지 라벨 기준이 모호하다 (미해결)
같은 문장("역사 장소에 대해 알 수 있어서 좋았다")도 사람마다 다른 분류로 봅니다. `scenery` 종류, `slope_stairs`와 `walking_burden`의 경계 등 가이드라인 보강이 필요합니다.

### 5. 추천이 LLM 변덕에 좌우되지 않게 했다
순위는 DB의 `review_annotations`를 Python으로 계산하고, 모델은 **추천 이유 문장과 요구사항 해석**만 맡습니다. 모델 장애·시간 초과·JSON 오류 시 키워드 규칙/라벨 기반 문장으로 대체됩니다.

```
goodness(aspect) = 100 × (긍정 + 0.5 × 중립) / 언급 수     (언급이 적으면 50 쪽으로 당김)
fit(장소)        = 50 + Σ w × (goodness − 50) / Σ w        (장소 리뷰에 언급된 aspect만)
```

### 6. 8GB GPU 학습과 Ollama 배포
4-bit QLoRA + batch 1 × gradient accumulation 16으로 8GB GPU에서 4B 모델을 학습했습니다. Ollama는 어댑터만 올릴 수 없어 **병합 → GGUF 변환 → Q4_K_M 양자화**를 거쳤고, Modelfile의 프롬프트가 학습 프롬프트와 글자까지 같은지 스크립트로 검사합니다 ([`deploy/ollama/README.md`](deploy/ollama/README.md)).

<br />

## 🛠 기술 스택

| 분류 | 기술 스택 | 참고 |
| --- | --- | --- |
| **Frontend** | ![Next.js](https://img.shields.io/badge/Next.js_15-000000?style=flat-square&logo=nextdotjs&logoColor=white) ![React](https://img.shields.io/badge/React_19-61DAFB?style=flat-square&logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) | App Router, `/api/*`를 FastAPI로 rewrite |
| **Backend** | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat-square&logo=python&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white) ![JWT](https://img.shields.io/badge/JWT-000000?style=flat-square&logo=jsonwebtokens&logoColor=white) | asyncpg, argon2 비밀번호 해시 |
| **DB** | ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white) | 장소·리뷰·`review_annotations` ([스키마](docs/db_schema.sql)) |
| **Model** | ![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white) ![Hugging Face](https://img.shields.io/badge/PEFT_/_Transformers-FFD21E?style=flat-square&logo=huggingface&logoColor=black) ![Qwen](https://img.shields.io/badge/Qwen3--4B-6A4CFF?style=flat-square) ![EXAONE](https://img.shields.io/badge/EXAONE--3.5--2.4B-A50034?style=flat-square) | QLoRA (4-bit NF4, r=16, α=32) |
| **Serving** | ![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square&logo=ollama&logoColor=white) | GGUF Q4_K_M |
| **Data** | ![Gemma](https://img.shields.io/badge/gemma4:e4b-4285F4?style=flat-square&logo=google&logoColor=white) | 합성 리뷰·Silver 라벨링 (Teacher LLM), TourAPI·부산시 API 장소 |
| **Tooling** | ![uv](https://img.shields.io/badge/uv-DE5FE9?style=flat-square&logo=uv&logoColor=white) ![W&B](https://img.shields.io/badge/Weights_&_Biases-FFBE00?style=flat-square&logo=weightsandbiases&logoColor=black) | 의존성 관리, 학습 추적 |

<br />

## 🏗 프로젝트 아키텍처

```
[오프라인]  TourAPI·부산시 API 장소 + 합성/실제 리뷰
              ▼
           Teacher LLM 라벨 → 자동 검사(Silver) → 사람 검수(Gold)
              ▼
           SFT 데이터셋 → QLoRA 학습 → 어댑터 → 병합·GGUF → Ollama 배포

[온라인]    사용자
              ▼
           Next.js 프론트엔드
              ▼  /api/v1
           FastAPI 백엔드
              ├─ auth · users · scraps      JWT 인증, 스크랩
              ├─ places                     장소 목록·상세, Review Profile, 근거 리뷰
              ├─ recommendations            조건 → 적합도 순위 + 추천 이유
              ├─ analyze                    리뷰 1건 실시간 구조화 (base / lora / qlora)
              └─ experiments · model-compare  평가 지표, 모델별 추천 비교
              │                      │
              ▼                      ▼
         PostgreSQL              Ollama 서버
```

<details>
<summary><b>추천 요청 처리 흐름 (펼치기)</b></summary>

`GET /api/v1/recommendations?with=parents&walk=low&pri=sea,food&avoid=waiting&category=attraction`

1. 조건(동행·걷기·원하는 것·피할 것)을 키워드 규칙으로 `{aspect: 가중치}`로 변환 (예: 부모님 → `walking_burden`, `slope_stairs`, `rest_facilities`)
2. DB `review_annotations`에서 장소별 (aspect, sentiment) 개수 집계
3. aspect별 만족도 → 장소 적합도 `fit` 계산, 40 미만 제외, 순위화
4. (선택) Ollama 모델이 장소 리뷰 3건으로 추천 이유 1문장 작성, 실패 시 라벨 기반 문장

스크랩 장소를 자연어 요구사항으로 비교하는 `POST /api/v1/recommendations`는 파인튜닝 모델이 "중요한 aspect / 신경 쓰지 않는 aspect"를, 키워드 규칙이 동행 유형을 해석합니다(요구사항 30문장 실험에서 F1 0.764, 동행 정확도 100%). 모델을 쓸 수 없으면 키워드 규칙만 씁니다. 구현: [`backend/services/recommendations.py`](backend/services/recommendations.py)

</details>

<details>
<summary><b>환경 변수 (펼치기)</b></summary>

[`.env.example`](.env.example)을 `.env`로 복사해 채웁니다.

| 변수 | 용도 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL (asyncpg) |
| `JWT_SECRET` | 로그인 토큰 서명 키 (32자 이상) |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | 모델 서버 주소, 서비스가 쓰는 QLoRA 모델 이름 |
| `OLLAMA_MODEL_BASE`, `OLLAMA_MODEL_LORA` | `/analyze`에서 모델을 바꿔 비교할 때 |
| `RECOMMENDATION_MODEL_TIMEOUT_SECONDS` | 요구사항 해석 제한 시간, 넘기면 키워드 규칙으로 대체 |
| `EXPERIMENTS_METRICS_PATH` | `/experiments`가 읽을 평가 결과 JSON |
| `API_SERVER_URL` (프론트) | Next.js가 프록시할 FastAPI 주소 |

</details>

<br />

## 📁 폴더 구조

```
travel-planner
├── backend/            FastAPI 서버
│   ├── api/            라우터 (auth, places, recommendations, analyze …)
│   ├── services/       추천·분석·프로필 로직
│   ├── repositories/   DB 조회
│   ├── models/         SQLAlchemy 모델
│   └── clients/        Ollama 클라이언트
├── frontend/           Next.js 프론트엔드 (app/, components/, lib/)
├── src/travel_planner/model_cjm/   학습·추론·후처리 (train, infer, postprocess, prompt)
├── datas/common/       데이터 도구 (스키마, 수집, 합성, 라벨, 검사, 검수, 분할)
├── datasets/v2/        학습·검증·테스트 데이터셋과 manifest
├── evaluation/         평가 파이프라인 (자동 지표, Judge, 인간 평가, 지연 측정)
├── deploy/             HF 어댑터 폴더, Ollama 병합·GGUF·Modelfile
├── docs/               라벨링 가이드, DB 스키마, 평가 보고서
└── tests/              추천·프론트 계약 테스트
```

<br />

## 🚀 실행 방법

Python 3.12 이상, [`uv`](https://docs.astral.sh/uv/)를 쓰며 모든 명령은 저장소 루트에서 실행합니다.

```bash
# 백엔드
uv sync
cp .env.example .env        # DATABASE_URL, JWT_SECRET, OLLAMA_* 채우기
uv run uvicorn backend.main:app --reload
```

```bash
# 프론트엔드
cd frontend && npm install
API_SERVER_URL=http://127.0.0.1:8000 npm run dev
```

```bash
# 같은 Gold Test로 모델 비교
uv run python -m evaluation.run_pipeline --config evaluation/config.json --out evaluation/runs/<실행 이름>
```

모델 로드·학습·어댑터 적용은 각각 별도 단계입니다. 상세 절차는 [`evaluation/README.md`](evaluation/README.md), [`deploy/ollama/README.md`](deploy/ollama/README.md), [`datas/common/README.md`](datas/common/README.md)를 참고하세요.

<br />

## 🔮 향후 확장

현재 범위는 **리뷰 구조화 · Review Profile · 조건 기반 추천 · 모델 비교**입니다. 아래는 요청 시에만 구현하는 확장입니다.

| 단계 | 내용 | 핵심 기술 |
| --- | --- | --- |
| 확장 1 | 사용자 취향 Profile과 Review Profile로 장소 비교 | Preference + DB |
| 확장 2 | LLM이 부족한 조건만 역질문해 취향 구체화 | 대화형 LLM |
| 확장 3 | 거리·이동시간을 반영한 일정 생성 | Google Maps API + Planner |
| 확장 4 | 일정의 현실성 자동 검증·수정 | Validator + 재생성 |

개선 과제: 관광지 라벨 기준 재정립, 실제 Gold 확대, LoRA(16bit) 조건 비교, GGUF 재평가, 후처리가 못 거르는 일반 aspect(`scenery`, `amenities`, `activity_variety`) 대응.

<br />

## 👥 팀 소개

부산을 다섯 구역으로 나눠 구역별로 데이터를 모으고, 모델도 나눠 학습했습니다.

<table align="center">
  <tr>
    <td align="center" width="190"><img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/member1.png" width="110" /><br /><b>최정민</b><br /><sub>팀장</sub></td>
    <td align="center" width="190"><img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/member2.png" width="110" /><br /><b>이건호</b><br /><sub>Backend</sub></td>
    <td align="center" width="190"><img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/member3.png" width="110" /><br /><b>김나경</b><br /><sub>Frontend</sub></td>
    <td align="center" width="190"><img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/member4.png" width="110" /><br /><b>윤아영</b><br /><sub>Frontend</sub></td>
    <td align="center" width="190"><img src="https://raw.githubusercontent.com/sunub/travel-planner/main/docs/images/member5.png" width="110" /><br /><b>남상기</b><br /><sub>Backend</sub></td>
  </tr>
</table>

| 이름 | 역할 | 학습 모델 | 담당 구역 |
| --- | --- | --- | --- |
| 최정민 | 팀장 | Qwen | 해운대 · 기장 |
| 이건호 | 백엔드 | Gemma | 광안리 · 수영 |
| 김나경 | 프론트엔드 | Gemma | 서면 · 동래 |
| 윤아영 | 프론트엔드 | EXAONE | 원도심 · 영도 · 서구 |
| 남상기 | 백엔드 | EXAONE | 서부산 · 북부 · 사하 |

<br />

<div align="center"><sub>어디갈건호? · TripFit — 부산 관광 리뷰 구조화 프로젝트</sub></div>
