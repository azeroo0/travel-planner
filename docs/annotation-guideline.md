# 라벨링 가이드라인 (초안)

사람과 Teacher LLM이 같은 리뷰에 같은 라벨을 달도록 하는 규칙입니다.
허용값 목록은 [`src/travel_planner/schema.py`](../src/travel_planner/schema.py)가 기준이고,
이 문서는 **그 값을 언제 어떻게 고르는지**를 정합니다. 파일럿 어노테이션 후 확정합니다.

## 1. 레코드 형식

JSONL 한 줄이 리뷰 한 건입니다.

```json
{
  "review_id": "r_000001",
  "place_id": "tourapi:2805408",
  "category": "restaurant",
  "synthetic": true,
  "tier": "silver",
  "review": "부모님이랑 갔는데 웨이팅이 40분이나 됐어요. 그래도 모밀은 정말 시원하고 맛있었어요.",
  "label": {
    "traveler_context": ["parents"],
    "aspects": [
      {"category": "waiting_time", "attribute": "long", "sentiment": "negative", "evidence": "웨이팅이 40분이나 됐어요"},
      {"category": "food_quality", "attribute": "good", "sentiment": "positive", "evidence": "모밀은 정말 시원하고 맛있었어요"}
    ]
  }
}
```

- `place_id`는 `collect_places.py` 결과(`datas/cjm/out/places_*.json`)의 장소와 연결됩니다.
- `category`는 장소의 카테고리이고, `aspects[].category`는 그 카테고리의 aspect 중 하나입니다.
- `tier`는 자동 검사를 통과하면 `silver`, 사람이 원문과 대조해 승인하면 `gold`입니다.

## 2. 근거는 두 가지

| 근거 | `evidence` 값 | 언제 |
|---|---|---|
| 리뷰 원문 | 원문에 그대로 있는 구절 | 리뷰가 그 aspect를 말할 때 |
| 장소 정보 | `place:<필드>=<값>` (예: `place:content_type_id=14`) | 리뷰가 말하지 않고, 아래 5절의 규칙이 있을 때 |

**리뷰가 우선입니다.** 장소 정보로는 실외인 곳이라도 리뷰에 "지붕이 있어서 비 와도 괜찮았어요"라고 적혀 있으면 리뷰를 따릅니다.

## 3. 리뷰 근거 라벨 규칙

### evidence

- 원문을 **한 글자도 바꾸지 않고** 잘라 옵니다. 띄어쓰기, 맞춤법 오류, 이모티콘까지 그대로 둡니다.
- 그 판단을 혼자서도 전달하는 **가장 짧은 연속 구절**을 고릅니다. 문장 전체가 필요할 때만 문장 전체를 씁니다.
  - "웨이팅이 40분이나 됐어요" (O) / "40분" (X, 무엇이 40분인지 모름) / 문장 전체 (X, 다른 내용까지 포함)
- 떨어진 두 구절을 `...`로 이어 붙이지 않습니다. 필요하면 aspect를 두 개 답니다.

### attribute와 sentiment

- **attribute는 상태, sentiment는 평가**입니다. 둘을 따로 판단합니다.
  - "40분 기다렸는데 기다린 보람이 있었어요" → `waiting_time` / `long` / `positive`
- 가운데 값(`average`, `moderate`, `medium`, `normal`)은 "보통", "무난", "그럭저럭"처럼 **그렇게 적혀 있을 때만** 씁니다.
- `neutral`은 평가 없이 사실만 말할 때 씁니다. 예: "주차장은 건물 뒤에 있어요" → `parking_availability` / `available` / `neutral`
- 한 aspect 안에 긍정과 부정이 섞이면 **aspect를 두 개로 나눕니다.**
  - "맛은 있는데 좀 짜요" → `food_quality` / `good` / `positive` + `food_quality` / `poor` / `negative`

### 같은 aspect가 여러 번 나올 때

- 같은 판단(attribute와 sentiment가 모두 같음)을 반복하면 **가장 분명한 구절 하나**만 답니다.
- 판단이 다르면 각각 답니다.

### 표현별 처리

| 표현 | 처리 | 예 |
|---|---|---|
| 부정문 | 뜻대로 라벨을 달고, evidence에는 부정어까지 포함 | "안 시끄러웠어요" → `noise_level` / `quiet` / `positive` |
| 반어 | 문맥상 실제 의미로 라벨을 달고, 사람 검수 때 확인 | 불만 문맥의 "참 친절하시더라고요^^" → `staff_service` / `unfriendly` / `negative` |
| 비교 | 비교 결과를 상태로 봄 | "옆집보다 양이 많아요" → `portion` / `large` |
| 기대 대비 | 기대보다 어땠는지를 상태로 봄 | "생각보다 방이 넓었어요" → `room_size` / `spacious` / `positive` |
| 추측·전언 | 직접 경험이 아니면 달지 않음 | "주말엔 줄이 길다던데" → 없음 |

## 4. traveler_context

- 리뷰에 **누구와 갔는지 적혀 있을 때만** 답니다. "우리 갔어요"만으로는 `couple`로 달지 않습니다.
- 여러 개 가능합니다. "부모님이랑 아이 데리고" → `["parents", "family_with_kids"]`
- 언급이 없으면 `[]`입니다.

| 값 | 단서 예 |
|---|---|
| `solo` | 혼자, 혼행 |
| `couple` | 남자친구, 여자친구, 와이프, 남편, 데이트 |
| `friends` | 친구들, 동기들 |
| `family_with_kids` | 아이, 애기, 초등학생 딸 |
| `parents` | 부모님, 엄마 아빠 모시고 |

## 5. 장소 정보 근거 라벨 규칙

리뷰가 해당 aspect를 말하지 않을 때, **아래 규칙이 있는 aspect만** 장소 정보로 답니다.
sentiment는 장소 정보만으로는 평가를 알 수 없으므로 `neutral`입니다.

| aspect | 장소 정보 | 규칙 | 상태 |
|---|---|---|---|
| `weather_sensitivity` | `content_type_id` | 12 관광지 → `high` (실외), 28 레포츠 → `high` (실외), 14 문화시설 → `low` (실내) | 초안. 분류 코드(`class_code`)로 예외를 보정할 예정 (실내 관광지 등) |
| `parking_availability` | `parking` | "가능", "있음" → `available` / "불가", "없음" → `unavailable` / 대수가 적거나 조건부 → `limited` | TourAPI 주차 필드를 실제로 받은 뒤 값 형태를 보고 확정 |
| `stay_duration` | 규모 필드 (미정) | 규모가 크면 `long` | TourAPI `detailIntro2`의 규모 필드를 확인한 뒤 확정 |

예:

```json
{"category": "weather_sensitivity", "attribute": "low", "sentiment": "neutral", "evidence": "place:content_type_id=14"}
```

## 6. aspect별 메모

- `scenery`: 경관의 **종류**입니다. 바다와 야경을 함께 말하면 aspect를 두 개(`sea`, `night_view`) 답니다.
- `amenities`: 편의·부대시설이 **있는지 없는지**만 봅니다. 수영장이 좋았다는 평가는 sentiment에 담습니다.
- `stay_duration`: 잠깐 들르기(`short`) / 1~2시간(`medium`) / 반나절 이상(`long`). "오래 걸렸어요", "다 보려면 한참 걸려요"도 `long`입니다.
- `weather_sensitivity`: 야외라서 날씨 영향을 받으면 `high`, 실내라 상관없으면 `low`입니다.
- `family_friendly`: 아이 의자, 놀이 공간, "애들이랑 가기 좋아요" 같은 표현이 단서입니다.
- `parking_availability`와 `parking_experience`: 주차장이 **있는지**는 availability, 주차가 **쉬웠는지**(자리 찾기, 좁음 등)는 experience입니다.

## 7. 검수 (Silver → Gold)

사람은 다음을 원문과 대조해 확인하고, 모두 맞으면 `tier`를 `gold`로 바꿉니다.

- [ ] 리뷰가 말한 aspect를 빠뜨리지 않았는가
- [ ] 리뷰에 없는 aspect를 지어내지 않았는가 (장소 정보 근거는 5절 규칙에 맞는가)
- [ ] attribute와 sentiment가 이 문서의 규칙에 맞는가
- [ ] evidence가 판단을 담은 가장 짧은 구절인가
- [ ] traveler_context가 리뷰에 적힌 것만 담았는가
