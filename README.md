# TripFit 부산 리뷰 QLoRA 프로젝트

> **TEAM INTRO · TripFit**

## 비에이 투어 리뷰 분석에서 부산 장소 리뷰 분석으로

**사람이 수많은 리뷰를 읽고 선택에 필요한 정보를 찾는 작업**을 AI가 구조화하도록 만들고, 대상을 부산의 **호텔·식당·관광지**로 확장합니다.

> **한 문장:** 부산 장소 리뷰를 **Context / Aspect / Attribute / Sentiment / Evidence**로 구조화하는 능력을 LoRA·QLoRA로 학습하고 Base 모델과 비교한다.

## 목차

1. [비에이 투어 리뷰 분석](#1-비에이-투어-리뷰-분석)
2. [부산 확장](#2-부산에서는-이렇게-바꾼다)
3. [학습 Task](#3-lora--qlora가-배우는-것)
4. [라벨](#4-카테고리별-라벨)
5. [데이터셋](#5-리뷰가-부족하면-데이터셋은)
6. [실험](#6-실험)
7. [팀 할 일](#7-그래서-우리-팀이-해야-할-일)
8. [향후 확장](#8-향후-확장--llm이-역으로-질문해서-여행을-구체화)

---

## 1. 비에이 투어 리뷰 분석

| 👤 사람이 하던 일 | 🤖 AI가 대신할 일 |
| --- | --- |
| 비슷한 비에이 투어들의 상세정보와 후기를 읽고 일정, 사진시간, 이동 편의, 가이드 등의 특징을 직접 찾아 비교. | 리뷰를 읽어 상품 선택에 필요한 특징·평가·근거를 일정한 구조로 추출. **최종 선택은 사용자가 함.** |

```
비에이 Tour A/B/C 리뷰
        ↓
   LoRA / QLoRA
        ↓
Context / Aspect / Attribute / Sentiment / Evidence
        ↓
   상품별 Review Profile
        ↓
사용자 조건과 비교
```

---

## 2. 부산에서는 이렇게 바꾼다

| ❌ MVP에서 빼는 것 | ✅ MVP에서 하는 것 |
| --- | --- |
| 부산 하루 일정 자동 생성 | 호텔·식당·관광지 리뷰 분석 |
| 실시간 위치·이동시간 계산 | 의사결정 속성 추출 |
| 장소 정보를 모델에게 암기시키기 | 장소별 Review Profile 생성 |
| | Base vs LoRA vs QLoRA 비교 |

```
           부산 장소 리뷰
                │
      ┌─────────┼─────────┐
      ▼         ▼         ▼
    🏨 호텔    🍚 식당    🌊 관광지
      └─────────┼─────────┘
                ▼
          LoRA / QLoRA
                ▼
       리뷰 → 구조화 정보
                ▼
       장소 Review Profile
                ▼
       사용자 조건과 비교
```

> ※ 위치·이동시간·일정 생성은 [향후 확장](#8-향후-확장--llm이-역으로-질문해서-여행을-구체화) 기능입니다.

---

## 3. LoRA / QLoRA가 배우는 것

**장소 자체를 외우는 게 아닙니다.** 처음 보는 리뷰에서도 같은 방식으로 정보를 추출하는 방법을 학습합니다.

**입력 리뷰**

> “부모님과 갔는데 사진은 정말 잘 나오지만 언덕이 많아서 힘들었어요.”

**출력**

```json
{
  "traveler_context": ["parents"],
  "aspects": [
    {"category": "photo_spots", "attribute": "good", "sentiment": "positive", "evidence": "사진은 정말 잘 나오지만"},
    {"category": "walking_burden", "attribute": "high", "sentiment": "negative", "evidence": "언덕이 많아서 힘들었어요"}
  ]
}
```

| 구성 요소 | 질문 | 예시 값 |
| --- | --- | --- |
| **Context** | 누가 / 어떤 상황? | `parents`, `couple` |
| **Aspect + Attribute** | 무엇에 대한 말이며 특성은? | `walking_burden` → `high` |
| **Sentiment + Evidence** | 평가는 어떻고 근거는? | `negative` + 원문 근거 |

---

## 4. 카테고리별 라벨

| 🏨 호텔 `hotel` | 🍽️ 식당 `restaurant` | 🏖️ 관광지 `attraction` |
| --- | --- | --- |
| `cleanliness` · 청결 | `food_quality` · 음식 맛/품질 | `scenery` · 경관/풍경 |
| `noise_level` · 소음 | `freshness` · 신선도 | `photo_spots` · 사진 촬영 만족도 |
| `bed_comfort` · 침대/침구 편안함 | `portion` · 음식 양 | `walking_burden` · 걷기 부담 |
| `room_size` · 객실 크기 | `waiting_time` · 웨이팅 시간 | `slope_stairs` · 언덕/계단 부담 |
| `bathroom_quality` · 욕실/수압 | `serving_speed` · 음식 제공 속도 | `activity_variety` · 볼거리/즐길거리 |
| `room_condition` · 객실/시설 상태 | `staff_service` · 직원 친절/응대 | `stay_duration` · 체류할 만한 정도 |
| `view_quality` · 객실 전망 | `cleanliness` · 매장/식기 청결 | `rest_facilities` · 휴식시설 |
| `staff_service` · 직원 친절/응대 | `atmosphere` · 매장 분위기 | `toilet_facilities` · 화장실 편의 |
| `breakfast_quality` · 조식 품질 | `noise_level` · 매장 소음 | `weather_sensitivity` · 날씨 영향 |
| `amenities` · 편의/부대시설 | `seating_comfort` · 좌석/공간 편의 | `parking_experience` · 실제 주차 경험 |
| `parking_experience` · 실제 주차 경험 | `family_friendly` · 가족 동반 적합도 | |
| `location_access` · 역/교통 접근성 | `parking_experience` · 실제 주차 경험 | |

> **참고:** aspect별 허용값(attribute, sentiment, traveler_context)은 [`datas/common/schema.py`](datas/common/schema.py), 라벨링 규칙은 [`docs/annotation-guideline.md`](docs/annotation-guideline.md)가 기준입니다. 둘 다 파일럿 어노테이션 후 확정하는 초안입니다.

---

## 5. 리뷰가 부족하면 데이터셋은?

```
소량의 실제 부산 리뷰
        ↓
표현 / 자주 등장하는 Aspect 확인
        ↓
Annotation Guideline 확정
        ↓
실제 리뷰 라벨 + 합성 리뷰 생성
        ↓
사람이 확인한 데이터 = GOLD
AI가 자동 생성한 데이터 = SILVER
        ↓
      SFT Dataset
```

### Gold와 Silver의 정의

| | 🥇 Gold Dataset | 🥈 Silver Dataset |
| --- | --- | --- |
| **정의** | 사람이 최종적으로 정답을 확인·수정·승인한 데이터 | Teacher LLM이 Annotation Guideline에 따라 자동 생성·라벨링한 데이터 |
| **특징** | Teacher LLM이 초안을 만들었더라도 사람이 원본 리뷰와 비교해 오류를 수정하고 최종 승인하면 Gold가 됨 | 대량 구축에는 유리하지만 전체를 사람이 최종 검수하지 않았기 때문에 Gold와 같은 신뢰도로 취급하지 않음 |
| **용도** | 학습 + 채점 기준(Test Set) | 학습 데이터 양 확장 |

### 5-1. Gold는 어떻게 만드는가?

```
원본 리뷰
"부모님과 갔는데 호텔이 정말 조용하고
깨끗했어요. 역에서는 조금 멀었어요."
        ↓
Teacher LLM이 Label 초안 생성
        ↓
Context / Aspect / Attribute / Sentiment / Evidence
        ↓
사람이 원본과 비교
        ↓
오류 수정 + 최종 승인
        ↓
GOLD DATA
```

**사람이 원본과 비교할 때 확인하는 항목**

- [ ] Aspect가 맞는가?
- [ ] Attribute가 맞는가?
- [ ] Sentiment가 맞는가?
- [ ] Evidence가 실제 원문에 있는가?
- [ ] 리뷰에 없는 내용을 만들지 않았는가?

**Gold 예시**

> “부모님과 갔는데 호텔이 정말 조용하고 깨끗했어요. 역에서는 조금 멀었어요.”

```json
{
  "traveler_context": ["parents"],
  "aspects": [
    {"category": "noise_level", "attribute": "quiet", "sentiment": "positive", "evidence": "호텔이 정말 조용하고"},
    {"category": "cleanliness", "attribute": "clean", "sentiment": "positive", "evidence": "깨끗했어요"},
    {"category": "location_access", "attribute": "poor", "sentiment": "negative", "evidence": "역에서는 조금 멀었어요"}
  ]
}
```

> **핵심:** 누가 처음 만들었느냐보다 **사람이 최종 정답을 검수하고 승인했느냐**가 Gold의 기준입니다.

### 5-2. Silver는 어떻게 만드는가?

```
Raw / Synthetic Reviews
        ↓
Annotation Guideline + Teacher LLM
        ↓
대량 자동 라벨링
        ↓
Context / Aspect / Attribute / Sentiment / Evidence
        ↓
자동 형식 검사
        ↓
SILVER DATA
```

**Silver 자동 검사**

1. JSON 형식 확인
2. 허용된 Aspect인지 확인
3. Attribute / Sentiment 값 확인
4. Evidence가 원문에 실제 존재하는지 확인
5. 필수 필드 누락 확인

> [!WARNING]
> **Silver의 위험**
>
> “웨이팅 1시간이나 해서 정말 행복했네요^^”
>
> Teacher가 비꼼을 이해하지 못하고 `positive`로 잘못 라벨링할 수 있습니다. 이런 오류가 대량으로 들어가면 LoRA/QLoRA도 잘못된 패턴을 학습할 수 있습니다.

### 5-3. Gold와 Silver는 이렇게 비교한다

| 실험 A · Gold Only | 실험 B · Gold + Silver |
| --- | --- |
| Gold Train → LoRA / QLoRA → **Gold Test** | Gold Train + Silver Train → LoRA / QLoRA → **동일한 Gold Test** |
| 사람이 검수한 고품질 데이터만 학습했을 때의 성능 | Teacher LLM으로 데이터 양을 늘린 것이 실제 성능 향상으로 이어지는지 확인 |

| 학습 데이터 | Aspect | Attribute | Sentiment | Evidence | JSON |
| --- | --- | --- | --- | --- | --- |
| **Gold Only** | 측정 | 측정 | 측정 | 측정 | 측정 |
| **Gold + Silver** | 측정 | 측정 | 측정 | 측정 | 측정 |

> **팀이 기억할 핵심**
>
> - **Gold** = 채점 기준으로 믿을 수 있도록 **사람이 최종 보증한 데이터**
> - **Silver** = 데이터 양을 늘리기 위해 **Teacher LLM이 자동 생성한 데이터**
>
> Silver를 많이 만들었다고 자동으로 좋은 데이터셋이 되는 것은 아닙니다. **동일한 Gold Test Set에서 Gold Only와 Gold + Silver를 비교**하여 Silver 추가가 실제로 도움이 됐는지 검증합니다.

### 5-4. 합성 리뷰 원칙

소량의 실제 리뷰를 참고해 다양한 표현을 만들 수 있지만 **Synthetic Review라고 명확히 구분**합니다. 합성 데이터를 실제 이용자 리뷰라고 취급하지 않습니다.

---

## 6. 실험

| 모델 | 조건 | 측정 |
| --- | --- | --- |
| **Base** | 파인튜닝 없음 | 기준 성능 |
| **LoRA** | 동일 SFT Dataset | Aspect / Attribute / Sentiment / Evidence / JSON |
| **QLoRA** | 동일 SFT Dataset | 동일 성능 + VRAM / 학습시간 / Adapter 크기 |

> **연구 질문:** Base보다 LoRA/QLoRA가 **처음 보는 부산 장소 리뷰에서도** 선택에 필요한 정보를 더 정확하고 일관된 구조로 추출하는가?

---

## 7. 그래서 우리 팀이 해야 할 일

| 순서 | 할 일 | 내용 |
| :---: | --- | --- |
| 1 | **실제 리뷰 조금 확보** | 호텔·식당·관광지 리뷰를 소량 확보해서 실제 표현을 먼저 본다. |
| 2 | **Pilot Annotation** | 같은 리뷰를 팀원이 라벨링하며 기준을 맞춘다. |
| 3 | **라벨 기준 확정** | 카테고리별 Aspect / Attribute / Sentiment / Evidence 규칙을 문서화한다. |
| 4 | **Gold + Silver 제작** | Teacher LLM으로 초안을 만들고 사람이 검수한다. 합성 리뷰는 별도 표시한다. |
| 5 | **Base → LoRA → QLoRA** | 같은 Task·Label·Train/Test 조건으로 학습하고 비교한다. |
| 6 | **Review Profile + 데모** | 모델 결과를 Python/SQL로 집계해 장소 특징과 근거 리뷰를 비교해서 보여준다. |

> **팀이 기억할 한 문장**
>
> 우리는 부산 장소를 외워 추천하는 AI가 아니라, **사람이 호텔·식당·관광지 리뷰를 하나씩 읽으며 특징과 장단점을 찾던 작업을 LoRA/QLoRA로 자동화**하는 서비스를 만든다.

---

## 8. 향후 확장 — LLM이 역으로 질문해서 여행을 구체화

> **현재 MVP는 “리뷰를 잘 읽는 AI”**
>
> 이번 단계에서는 호텔·식당·관광지 리뷰를 구조화하고, 장소별 Review Profile을 만드는 데 집중합니다. 그 다음 단계에서는 이 데이터를 기반으로 **대화형 개인 여행 플래너**로 확장할 수 있습니다.

```
사용자  "부산 여행 일정 짜줘"
        ↓
LLM     "누구와 여행하시나요?"
        ↓
사용자  "부모님이랑 가요"
        ↓
LLM     "많이 걷는 일정은 괜찮으신가요?
         아니면 이동이 편한 곳 위주가 좋으신가요?"
        ↓
사용자  "많이 걷는 건 힘들어요"
        ↓
LLM     "관광지, 맛집, 바다 중
         어떤 걸 가장 중요하게 생각하세요?"
        ↓
사용자  "바다랑 맛집이요"
        ↓
취향이 충분히 구체화됨
        ↓
장소 DB + Review Profile
        ↓
Google Maps API (장소 위치 / 거리 / 이동시간 / 지도)
        ↓
개인화 일정 생성
        ↓
가능한 일정인지 코드 검증
        ↓
지도 동선이 포함된 최종 여행 일정
```

### 8-1. 왜 역질문이 필요한가?

1. **사용자는 처음부터 다 말하지 않음** — “부산 여행 짜줘” 한 문장만으로는 동행자, 걷기, 예산, 관심사 등을 알 수 없습니다.
2. **필요한 것만 질문** — 모든 항목을 설문처럼 묻지 않고, 일정 결과를 실제로 바꿀 수 있는 조건만 추가로 질문합니다.
3. **리뷰 데이터가 답변 근거가 됨** — “부모님과 걷기 힘들어요”라고 하면 `walking_burden` 리뷰 분석 결과를 일정 선택에 활용할 수 있습니다.

### 8-2. 대화하면서 Preference Profile을 채운다

**처음**

```json
{
  "companions": null,
  "budget": null,
  "walking_tolerance": null,
  "interests": null,
  "pace": null
}
```

**몇 번 대화한 뒤**

```json
{
  "companions": ["parents"],
  "budget": "medium",
  "walking_tolerance": "low",
  "interests": ["food", "ocean"],
  "pace": "relaxed"
}
```

### 8-3. LLM 혼자 일정을 만드는 것은 아니다

```
                 역할 분담

LLM
├─ 사용자 말 이해
├─ 부족한 조건 판단
├─ 자연스럽게 역질문
└─ 후보를 이용해 일정 구성

Review QLoRA
└─ 호텔 / 식당 / 관광지 리뷰 구조화

DB / 코드
├─ 실제 장소
├─ 위치 / 좌표
├─ 영업시간
├─ 가격 등 객관 정보
└─ 후보 필터링

Google Maps API  [확장]
├─ 장소 검색 및 위치 확인
├─ 위도·경도 / 지도 표시
├─ 장소 간 거리·이동시간 계산
└─ 최종 일정 동선 시각화

Validator
├─ 영업시간 확인
├─ 이동 가능한지 확인
├─ 일정 겹침 확인
└─ 불가능한 일정 제거
```

**대화 예시**

> **사용자:** “부모님이랑 부산 하루 여행하고 싶어.”
> **LLM:** “부모님이 오래 걷는 건 괜찮으신가요?”
> **사용자:** “많이 걷는 건 힘들어.”
> **LLM:** “바다 풍경, 맛집, 문화 관광 중 어떤 걸 가장 중요하게 생각하세요?”
> **사용자:** “바다랑 맛집.”
>
> **시스템:** 관광지 리뷰의 `walking_burden`, `scenery`와 식당의 `food_quality`, `waiting_time` 등을 이용해 후보를 좁힌 뒤 일정 생성.

### 8-4. 프로젝트 발전 단계

| 단계 | 구현 내용 | 핵심 기술 |
| --- | --- | --- |
| **현재 MVP** | 부산 리뷰에서 선택에 필요한 특징 추출 | Base / LoRA / QLoRA |
| **확장 1** | 사용자 취향과 Review Profile을 이용한 장소 비교 | Preference + DB |
| **확장 2** | LLM이 부족한 조건만 역질문하여 취향 구체화 | 대화형 LLM |
| **확장 3** | Google Maps API로 장소 위치·거리·이동시간을 계산해 일정 생성 | Google Maps API + Planner |
| **확장 4** | 일정이 현실적으로 가능한지 자동 검증 및 수정 | Validator + 재생성 |

### 8-5. Google Maps API는 어디에 쓰나?

| 📍 장소 정보 연결 | 🚗 현실적인 이동 계산 |
| --- | --- |
| 호텔·식당·관광지의 실제 위치를 연결하고 지도에서 장소를 확인합니다. | 장소 A → B → C 사이의 거리와 예상 이동시간을 받아 일정 계산에 사용합니다. |
| `장소 검색` `좌표` `지도 표시` | `거리` `이동시간` `동선` |

```
예) 사용자가 원하는 후보

해운대 관광지
      │  Google Maps API · 이동시간 계산
      ▼
광안리 식당
      │  Google Maps API · 이동시간 계산
      ▼
부산 호텔

          ↓

LLM이 단순히 "이 세 곳이 좋아요"라고 끝내는 것이 아니라

09:30 관광지 방문
   ↓ 이동 약 ○분
12:00 식당
   ↓ 이동 약 ○분
14:00 다음 장소

처럼 실제 이동시간을 반영한 일정 후보를 만들 수 있음
```

### 8-6. 역할을 섞지 않는 것이 중요

| 구성요소 | 담당 역할 |
| --- | --- |
| **Review QLoRA** | 리뷰에서 장소의 경험적 특징을 추출 |
| **대화형 LLM** | 부족한 조건을 역질문하고 사용자의 취향을 구체화 |
| **장소 DB** | 호텔·식당·관광지의 객관적 정보를 저장 |
| **Google Maps API** | 실제 위치·거리·이동시간·지도 동선을 제공 |
| **Planner** | 취향 + 리뷰 특징 + 이동정보를 바탕으로 일정 후보 구성 |
| **Validator** | 시간 충돌·과도한 이동 등 현실성 검사 |

### 8-7. 최종 확장 구조

```
사용자
  ↓
LLM 역질문
"누구와 가나요?"
"많이 걸어도 괜찮나요?"
"맛집/바다/문화 중 뭐가 중요한가요?"
  ↓
Preference Profile
  ↓
┌──────────────────────────────┐
│ 부산 장소 DB                 │
│ + QLoRA Review Profile       │
│ + Google Maps 이동 정보      │
└──────────────┬───────────────┘
               ↓
          후보 장소 선정
               ↓
          일정 순서 구성
               ↓
     Google Maps 이동시간 반영
               ↓
          Validator 검사
               ↓
   개인화 일정 + 지도 동선 + 근거
```

> **최종적으로 만들고 싶은 모습**
>
> “어디 갈까요?”만 묻는 추천 AI가 아니라, **사용자에게 필요한 질문을 스스로 던지고**, 부산의 실제 장소 정보와 리뷰에서 얻은 경험 정보를 함께 사용해 **그 사람에게 맞는 현실적인 여행 계획을 만들어주는 대화형 여행 AI**로 확장한다.

---

<sub>TripFit · 부산 관광 리뷰 구조화 프로젝트 · Team Introduction</sub>
