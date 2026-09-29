# 어디갈건호 API 명세서

Sep 29, 2026 · @Dorothy

## 개요

어디갈건호 프론트엔드(Next.js)가 호출할 FastAPI 백엔드의 초안 명세입니다. 현재 프론트는 `lib/api.ts`와 `data/*.ts`의 Mock 데이터로 동작하며, 이 명세는 그 Mock을 실제 API로 교체하기 위한 계약입니다. 엔드포인트와 필드는 프론트 타입(`types/*.ts`)과 PostgreSQL 스키마(`db/initdb/01_schema.sql`)를 기준으로 정했습니다.

- **Base URL**: `/api` (Next.js에서 FastAPI로 프록시)
- **형식**: 요청·응답 모두 `application/json`, UTF-8
- **필드 표기**: snake\_case (`types/review.ts`의 방침을 따름)
- **인증**: 조회 API는 인증 없이 호출 가능, 사용자·스크랩 API는 `Authorization: Bearer <access_token>` 필요
- **ID**: DB의 BIGINT를 그대로 정수로 반환

### 공통 에러 응답

성공 시에는 리소스를 그대로 반환하고, 실패 시에는 아래 형식으로 반환합니다.

```json
{ "error": { "code": "PLACE_NOT_FOUND", "message": "장소를 찾을 수 없습니다." } }
```

| HTTP | code 예시 | 의미 |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | 필수 필드 누락, 허용되지 않은 값 |
| 401 | `UNAUTHORIZED` | 토큰 없음 또는 만료 |
| 403 | `FORBIDDEN` | 다른 사용자의 리소스 접근 |
| 404 | `PLACE_NOT_FOUND`, `SCRAP_NOT_FOUND` | 리소스 없음 |
| 409 | `ALREADY_EXISTS` | 이메일 중복, 중복 스크랩 |
| 503 | `MODEL_UNAVAILABLE` | 분석 모델이 로드되지 않음 |

### 목록 페이지네이션

목록 API는 `?page=1&size=20`(최대 100)을 받고 `{ "items": [...], "page": 1, "size": 20, "total": 132 }`를 반환합니다.

## 장소 API

장소 탐색(`/discover`)과 장소 상세(`/places/[id]`) 화면이 사용합니다. 모두 인증 없이 호출합니다.

| Method | Path | 설명 | 대체할 Mock |
| --- | --- | --- | --- |
| GET | `/api/places` | 장소 목록 | `data/places.ts` |
| GET | `/api/places/{place_id}` | 장소 상세 + 이미지·태그 | `data/places.ts` |
| GET | `/api/places/{place_id}/profile` | Place Review Profile(Aspect 집계) | `data/profiles.ts` |
| GET | `/api/places/{place_id}/evidence` | Aspect별 근거 리뷰 | `data/reviews.ts` |

### GET /api/places

| Query | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `category` | `hotel` \| `restaurant` \| `attraction` | 아니오 | 카테고리 필터 |
| `region` | `haeundae` \| `gwangan` \| `seomyeon` \| `wondo` \| `west` | 아니오 | 지역 코드(`regions.region_code`) |
| `q` | string | 아니오 | 장소명 부분 검색 |
| `page`, `size` | int | 아니오 | 페이지네이션 |

응답 `200`: `Place` 목록(페이지 형식).

```json
{
  "items": [
    {
      "place_id": 12,
      "name": "감천문화마을",
      "category": "attraction",
      "region": "west",
      "district": "사하구",
      "address": "부산 사하구 감내항로 203",
      "latitude": 35.0975,
      "longitude": 129.0106,
      "summary": "사진은 좋지만 언덕·계단이 많은 마을",
      "main_image_url": "https://...",
      "review_count": 184
    }
  ],
  "page": 1, "size": 20, "total": 132
}
```

### GET /api/places/{place\_id}

응답 `200`: `Place` 필드에 `images`(`image_url`, `is_main`, `sort_order`)와 `tags`(`category`, `tag_name`)가 추가됩니다. 없는 ID면 `404 PLACE_NOT_FOUND`.

### GET /api/places/{place\_id}/profile

리뷰 구조화 결과(`review_annotations`)를 장소 단위로 집계한 값입니다. `share`는 해당 polarity로 언급한 리뷰 비율(%), `ratio`와 `context_satisfaction`도 %입니다.

```json
{
  "place_id": 12,
  "aspects": [
    { "aspect": "photo_spots", "polarity": "positive", "share": 82, "mentions": 97 },
    { "aspect": "walking_burden", "polarity": "negative", "share": 64, "mentions": 71 }
  ],
  "contexts": [ { "context": "couple", "ratio": 38 }, { "context": "parents", "ratio": 12 } ],
  "context_satisfaction": { "couple": 88, "parents": 54 }
}
```

### GET /api/places/{place\_id}/evidence

| Query | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `aspect` | string | 예 | 예: `walking_burden` |
| `sentiment` | `positive` \| `negative` \| `neutral` | 아니오 | 감성 필터 |
| `context` | TravelerContext | 아니오 | 동행 유형 필터 |
| `limit` | int | 아니오 | 기본 5, 최대 20 |

응답 `200`: 리뷰 원문과 근거 구간. 프론트의 `[[ ]]` 표기 대신 문자 위치(`evidence_start`, `evidence_end`)를 내려줍니다.

```json
[
  {
    "review_id": 5531,
    "text": "부모님과 갔는데 언덕이 많아서 힘들었어요.",
    "context": "parents",
    "sentiment": "negative",
    "evidence_start": 9,
    "evidence_end": 23
  }
]
```

## 리뷰 분석·추천 API

리뷰 분석기(`/analyzer`)와 추천(`/recommendations`), 실험실(`/lab`) 화면이 사용합니다. 모두 인증 없이 호출합니다.

| Method | Path | 설명 | 대체할 Mock |
| --- | --- | --- | --- |
| POST | `/api/analyze` | 리뷰 한 건을 모델로 구조화 | `lib/api.ts`의 `analyzeReview` |
| GET | `/api/recommendations` | 사용자 조건에 맞는 장소 순위 | `lib/fit.ts` |
| GET | `/api/experiments` | Base/LoRA/QLoRA 평가 지표 | `data/experiments.ts` |

### POST /api/analyze

요청 본문 (`AnalyzeRequest`)

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `review` | string | 예 | 리뷰 원문, 1\~2000자 |
| `category` | `hotel` \| `restaurant` \| `attraction` | 예 | 리뷰 대상 카테고리 |
| `model` | `base` \| `lora` \| `qlora` | 예 | 사용할 모델 |

응답 `200` (`AnalysisResult`)

```json
{
  "traveler_context": ["parents"],
  "aspects": [
    { "category": "photo_spots", "attribute": "good", "sentiment": "positive", "evidence": "사진은 정말 잘 나오지만" },
    { "category": "walking_burden", "attribute": "high", "sentiment": "negative", "evidence": "언덕이 많아서 힘들었어요" }
  ]
}
```

- `aspects[].category`는 장소 카테고리가 아니라 Aspect 이름입니다(프론트 타입 명칭을 그대로 둠).
- 허용 Aspect·Attribute 값은 `common/common/schema.py`의 `ASPECTS`, `ATTRIBUTES`를 따릅니다.
- 모델 출력이 JSON 파싱에 실패하면 `422 MODEL_OUTPUT_INVALID`, 모델이 로드되지 않았으면 `503 MODEL_UNAVAILABLE`.

### GET /api/recommendations

프론트 URL 쿼리(`/recommendations?with=parents&walk=low&pri=sea,food&avoid=waiting`)를 그대로 받습니다. LLM이 장소를 고르지 않고, Place Review Profile에 조건별 가중치를 적용해 Fit 점수를 계산합니다.

| Query | 값 | 필수 |
| --- | --- | --- |
| `with` | `solo` \| `friends` \| `couple` \| `parents` \| `kids` | 아니오 |
| `walk` | `ok` \| `moderate` \| `low` | 아니오 |
| `pri` | `sea`, `food`, `photo`, `culture`, `rest`, `quiet` (쉼표 구분) | 아니오 |
| `avoid` | `waiting`, `stairs`, `noise`, `parking`, `crowd` (쉼표 구분) | 아니오 |
| `category` | `hotel` \| `restaurant` \| `attraction` | 아니오 |
| `limit` | int, 기본 10 | 아니오 |

응답 `200`: `fit` 내림차순 `FitResult` 목록.

```json
[
  {
    "place": { "place_id": 31, "name": "해동용궁사", "category": "attraction", "region": "haeundae" },
    "fit": 78,
    "reason": "바다 경치는 좋지만 계단이 많다는 리뷰가 있어요",
    "strengths": [ { "aspect": "scenery", "polarity": "positive", "share": 91, "weight": 5, "delta": 12 } ],
    "cautions": [ { "aspect": "slope_stairs", "polarity": "negative", "share": 58, "weight": 4, "delta": -7 } ]
  }
]
```

### GET /api/experiments

응답 `200`: 평가 파이프라인(`evaluation/`)의 `automatic_metrics.json`을 화면용으로 정리한 `ExperimentMetricRow` 목록. `scores`의 키는 `base`, `lora_gold`, `qlora_gold`, `lora_gs`, `qlora_gs`입니다.

```json
[ { "metric": "Aspect F1", "unit": "f1", "scores": { "base": 0.21, "lora_gold": 0.58, "qlora_gold": 0.55, "lora_gs": 0.63, "qlora_gs": 0.61 } } ]
```

## 사용자·인증 API

`users` 테이블 기준입니다. 비밀번호는 해시(`password_hash`)로만 저장하고 응답에 포함하지 않습니다.

| Method | Path | 인증 | 설명 |
| --- | --- | --- | --- |
| POST | `/api/auth/signup` | — | 회원가입 |
| POST | `/api/auth/login` | — | 로그인, 토큰 발급 |
| GET | `/api/users/me` | 필요 | 내 정보 |
| PATCH | `/api/users/me` | 필요 | 이름·비밀번호 변경 |

### POST /api/auth/signup

요청: `{ "email": "a@example.com", "password": "8자 이상", "name": "홍길동" }`

응답 `201`: `User`. 이메일이 이미 있으면 `409 ALREADY_EXISTS`.

### POST /api/auth/login

요청: `{ "email": "a@example.com", "password": "..." }`

응답 `200`:

```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600, "user": { "user_id": 1, "email": "a@example.com", "name": "홍길동", "role": "member" } }
```

이메일 또는 비밀번호가 틀리면 구분 없이 `401 UNAUTHORIZED`.

### GET /api/users/me, PATCH /api/users/me

응답 `200`: `User`. PATCH는 `name`, `password` 중 보낸 필드만 변경하고 `updated_at`을 갱신합니다. `role`은 변경할 수 없습니다.

## 스크랩 API

`scraps`, `scrap_contents` 테이블 기준입니다. 모두 인증이 필요하며, 본인 스크랩만 조회·삭제할 수 있습니다(다른 사용자 것은 `404`).

| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/api/scraps` | 스크랩 생성 |
| GET | `/api/scraps` | 내 스크랩 목록 |
| GET | `/api/scraps/{scrap_id}` | 스크랩 상세 + 본문 |
| PATCH | `/api/scraps/{scrap_id}` | 제목 변경 |
| DELETE | `/api/scraps/{scrap_id}` | 삭제(본문도 함께 삭제) |

### POST /api/scraps

`place_id`, `review_id`, `source_url` 중 **최소 하나**는 있어야 합니다(DB 제약 `ck_scraps_target`). 없으면 `400 INVALID_REQUEST`.

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `place_id` | int | 조건부 | 스크랩할 장소 |
| `review_id` | int | 조건부 | 스크랩할 리뷰 |
| `source_url` | string, 최대 1000자 | 조건부 | 외부 링크 |
| `title` | string, 최대 300자 | 아니오 | 표시 제목 |

`source_type`은 서버가 정합니다. `source_url`만 있으면 `external`, 그 외에는 기본값 `internal`입니다. `status`는 기본값 `ready`로 시작합니다.

응답 `201`:

```json
{
  "scrap_id": 7,
  "user_id": 1,
  "place_id": 12,
  "review_id": null,
  "source_url": null,
  "title": "감천문화마을",
  "source_type": "internal",
  "status": "ready",
  "created_at": "2026-09-29T14:20:00",
  "updated_at": "2026-09-29T14:20:00"
}
```

### GET /api/scraps

| Query | 설명 |
| --- | --- |
| `source_type` | `internal` \| `external` 필터 |
| `page`, `size` | 페이지네이션, `created_at` 최신순 |

### GET /api/scraps/{scrap\_id}

`Scrap` 필드에 `content`가 추가됩니다. 본문이 아직 없으면 `null`입니다.

```json
"content": { "content_text": "...", "extraction_method": "html_parse", "fetched_at": "2026-09-29T14:21:03" }
```

### DELETE /api/scraps/{scrap\_id}

응답 `204`. `scrap_contents`는 FK `ON DELETE CASCADE`로 함께 삭제됩니다.

## 데이터 모델

응답 객체별 출처 테이블과 프론트 타입의 대응입니다. 집계 객체(`PlaceProfile`, `FitResult`)는 테이블이 아니라 서버가 계산합니다.

| 응답 객체 | DB 테이블 | 프론트 타입 |
| --- | --- | --- |
| `Place` | `places` + `place_categories` + `districts` + `regions` + 대표 `place_images` | `types/place.ts` `Place` |
| `PlaceDetail` | 위 + `place_images`, `place_tags`/`tags` | — (신규) |
| `PlaceProfile` | `review_annotations` + `aspects` + `review_companions` 집계 | `types/place.ts` `PlaceProfile` |
| `EvidenceReview` | `reviews` + `review_annotations` + `companion_types` | `types/review.ts` `EvidenceReview` |
| `AnalysisResult` | 없음(모델 추론 결과) | `types/review.ts` `AnalysisResult` |
| `FitResult` | `PlaceProfile` + 요청 조건 계산 | `types/place.ts` `FitResult` |
| `ExperimentMetricRow` | 없음(`evaluation/runs/*/automatic_metrics.json`) | `types/experiment.ts` |
| `User` | `users` (`password_hash` 제외) | — (신규) |
| `Scrap` | `scraps` (+ 상세에서 `scrap_contents`) | — (신규) |

공통 enum 값

| 이름 | 값 |
| --- | --- |
| Category | `hotel`, `restaurant`, `attraction` |
| Sentiment | `positive`, `negative`, `neutral` |
| TravelerContext | `solo`, `friends`, `couple`, `parents`, `kids`, `family` |
| ModelId | `base`, `lora`, `qlora` |
| Region | `haeundae`, `gwangan`, `seomyeon`, `wondo`, `west` |

## 미정 사항

구현 전에 팀이 정해야 할 항목입니다.

- [ ] **필드 표기 통일**: `types/review.ts`는 snake\_case지만 `types/place.ts`는 camelCase(`reviewCount`, `placeId`, `contextSatisfaction`)입니다. 이 명세는 snake\_case로 적었으므로 프론 타입을 바꿀지, API에서 camelCase로 내릴지 정해야 합니다.
- [ ] **`user_scraps`와 `scraps` 중복**: 두 테이블 모두 장소 스크랩을 담을 수 있습니다. 이 명세는 `scraps`만 사용합니다.
- [ ] **중복 스크랩**: `scraps`에는 `(user_id, place_id)` UNIQUE가 없어 같은 장소를 여러 번 저장할 수 있습니다. 막을지(`409`) 정해야 합니다.
- [ ] **인증 방식**: JWT Bearer로 가정했습니다. 쿠키 세션이나 소셜 로그인이 필요하면 인증 섹션을 바꿔야 합니다.
- [ ] **분석 모델**: 프론 주석은 Qwen3-8B, 평가 설정(`evaluation/config.json`)은 Qwen3-4B QLoRA입니다. `/api/analyze`가 올릴 모델과 GPU 메모리 예산을 정해야 합니다.
- [ ] **Region 코드**: 프론의 `haeundae` 등 5개 코드가 `regions.region_code`에 같은 값으로 적재돼 있어야 합니다.
- [ ] **`family` 동행 유형**: 타입에는 있지만 추천 조건 폼(`COMPANIONS`)에는 없습니다.
