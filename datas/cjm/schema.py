from typing import Final, Literal, TypedDict

Category = Literal["hotel", "restaurant", "attraction"]

HotelAspect = Literal[
    "cleanliness",
    "noise_level",
    "bed_comfort",
    "room_size",
    "bathroom_quality",
    "room_condition",
    "view_quality",
    "staff_service",
    "breakfast_quality",
    "amenities",
    "parking_availability",
    "parking_experience",
]
RestaurantAspect = Literal[
    "food_quality",
    "freshness",
    "portion",  # 리뷰에 양 이야기가 없으면 라벨을 달지 않는다 (집계 단계에서 '보통'으로 보여준다)
    "waiting_time",
    "serving_speed",
    "staff_service",
    "cleanliness",
    "atmosphere",
    "noise_level",
    "seating_comfort",
    "family_friendly",
    "parking_availability",
    "parking_experience",
]
AttractionAspect = Literal[
    "scenery",  # attribute는 SceneryType 중 하나
    "photo_spots",
    "walking_burden",
    "slope_stairs",
    "activity_variety",
    "stay_duration",
    "rest_facilities",
    "toilet_facilities",
    "weather_sensitivity",
    "parking_availability",
    "parking_experience",
]

# 관광지 scenery의 attribute는 경치의 좋고 나쁨이 아니라 종류를 나타낸다
SceneryType = Literal["sea", "mountain", "city", "river", "night_view"]
SCENERY_TYPES: Final[frozenset[str]] = frozenset(SceneryType.__args__)

ASPECTS: Final[dict[Category, frozenset[str]]] = {
    "hotel": frozenset(HotelAspect.__args__),
    "restaurant": frozenset(RestaurantAspect.__args__),
    "attraction": frozenset(AttractionAspect.__args__),
}


# ---------- 초안: 파일럿 어노테이션 후 확정한다 ----------

# 평가. 한 aspect 안에 긍정과 부정이 섞이면 aspect를 두 개로 나눠 단다.
Sentiment = Literal["positive", "negative", "neutral"]
SENTIMENTS: Final[frozenset[str]] = frozenset(Sentiment.__args__)

# 누구와 갔는지. 리뷰에 적힌 경우에만 달고(추측 금지), 여러 개 가능, 없으면 빈 리스트.
TravelerContext = Literal["solo", "couple", "friends", "family_with_kids", "parents"]
TRAVELER_CONTEXTS: Final[frozenset[str]] = frozenset(TravelerContext.__args__)

# attribute는 평가(sentiment)가 아니라 상태를 적는다.
# 가운데 값(average, moderate, medium, normal)은 리뷰에 "보통/무난"이라고 적혀 있을 때만 쓴다.
QUALITY: Final = ("good", "average", "poor")  # 한 가지 물리적 기준으로 나누기 어려운 aspect용
CLEAN: Final = ("clean", "average", "dirty")
NOISE: Final = ("quiet", "moderate", "noisy")
COMFORT: Final = ("comfortable", "average", "uncomfortable")
STAFF: Final = ("friendly", "average", "unfriendly")
BURDEN: Final = ("low", "medium", "high")
FACILITY: Final = ("sufficient", "lacking")
PARKING_AVAILABILITY: Final = ("available", "limited", "unavailable")
PARKING_EXPERIENCE: Final = ("easy", "average", "difficult")

ATTRIBUTES: Final[dict[Category, dict[str, tuple[str, ...]]]] = {
    "hotel": {
        "cleanliness": CLEAN,
        "noise_level": NOISE,
        "bed_comfort": COMFORT,
        "room_size": ("spacious", "average", "cramped"),
        "bathroom_quality": QUALITY,
        "room_condition": ("well_kept", "average", "worn"),
        "view_quality": QUALITY,
        "staff_service": STAFF,
        "breakfast_quality": QUALITY,
        "amenities": ("available", "unavailable"),  # 편의·부대시설이 있다고/없다고 말한 경우
        "parking_availability": PARKING_AVAILABILITY,
        "parking_experience": PARKING_EXPERIENCE,
    },
    "restaurant": {
        "food_quality": QUALITY,
        "freshness": ("fresh", "average", "not_fresh"),
        "portion": ("large", "normal", "small"),
        "waiting_time": ("none", "short", "long"),
        "serving_speed": ("fast", "average", "slow"),
        "staff_service": STAFF,
        "cleanliness": CLEAN,
        "atmosphere": QUALITY,
        "noise_level": NOISE,
        "seating_comfort": COMFORT,
        "family_friendly": ("suitable", "unsuitable"),
        "parking_availability": PARKING_AVAILABILITY,
        "parking_experience": PARKING_EXPERIENCE,
    },
    "attraction": {
        "scenery": tuple(SceneryType.__args__),
        "photo_spots": QUALITY,
        "walking_burden": BURDEN,
        "slope_stairs": BURDEN,
        "activity_variety": ("many", "average", "few"),
        # 잠깐 들르기 / 1~2시간 / 반나절 이상. "오래 걸렸어요"처럼 시간이 길었다는 표현도 long.
        # 리뷰에 언급이 없으면 TourAPI 규모 정보로 판단한다 (규모가 크면 long).
        "stay_duration": ("short", "medium", "long"),
        "rest_facilities": FACILITY,
        "toilet_facilities": FACILITY,
        # 야외면 high, 실내면 low. 리뷰에 언급이 없으면 TourAPI의 장소 종류로 판단한다.
        "weather_sensitivity": ("high", "low"),
        "parking_availability": PARKING_AVAILABILITY,
        "parking_experience": PARKING_EXPERIENCE,
    },
}

# ---------- 한국어 이름: 생성·라벨링 프롬프트와 문서에서 쓴다 ----------

CATEGORY_NAMES_KO: Final[dict[Category, str]] = {
    "hotel": "숙소",
    "restaurant": "식당",
    "attraction": "관광지",
}

ASPECT_NAMES_KO: Final[dict[str, str]] = {
    "cleanliness": "청결",
    "noise_level": "소음",
    "bed_comfort": "침대/침구 편안함",
    "room_size": "객실 크기",
    "bathroom_quality": "욕실/수압",
    "room_condition": "객실/시설 상태",
    "view_quality": "객실 전망",
    "staff_service": "직원 친절/응대",
    "breakfast_quality": "조식 품질",
    "amenities": "편의/부대시설 유무",
    "parking_availability": "주차 가능 여부",
    "parking_experience": "실제 주차 경험",
    "food_quality": "음식 맛/품질",
    "freshness": "신선도",
    "portion": "음식 양",
    "waiting_time": "웨이팅 시간",
    "serving_speed": "음식 제공 속도",
    "atmosphere": "매장 분위기",
    "seating_comfort": "좌석/공간 편의",
    "family_friendly": "가족 동반 적합도",
    "scenery": "경관 종류",
    "photo_spots": "사진 촬영 만족도",
    "walking_burden": "걷기 부담",
    "slope_stairs": "언덕/계단 부담",
    "activity_variety": "볼거리/즐길거리",
    "stay_duration": "체류 시간",
    "rest_facilities": "휴식시설",
    "toilet_facilities": "화장실 편의",
    "weather_sensitivity": "날씨 영향",
}

VALUE_NAMES_KO: Final[dict[str, str]] = {
    "good": "좋음", "average": "보통", "poor": "나쁨",
    "clean": "깨끗함", "dirty": "지저분함",
    "quiet": "조용함", "moderate": "보통", "noisy": "시끄러움",
    "comfortable": "편안함", "uncomfortable": "불편함",
    "friendly": "친절함", "unfriendly": "불친절함",
    "low": "낮음", "medium": "보통", "high": "높음",
    "sufficient": "충분함", "lacking": "부족함",
    "available": "있음", "limited": "제한적", "unavailable": "없음",
    "easy": "쉬움", "difficult": "어려움",
    "spacious": "넓음", "cramped": "좁음",
    "well_kept": "관리 잘 됨", "worn": "낡음",
    "fresh": "신선함", "not_fresh": "신선하지 않음",
    "large": "많음", "normal": "보통", "small": "적음",
    "none": "없음", "short": "짧음", "long": "김",
    "fast": "빠름", "slow": "느림",
    "suitable": "적합함", "unsuitable": "적합하지 않음",
    "sea": "바다", "mountain": "산", "city": "도시", "river": "강", "night_view": "야경",
    "many": "많음", "few": "적음",
}  # fmt: skip

TRAVELER_NAMES_KO: Final[dict[str, str]] = {
    "solo": "혼자",
    "couple": "연인 또는 배우자",
    "friends": "친구들",
    "family_with_kids": "아이를 데리고 간 가족",
    "parents": "부모님",
}

# ---------- 정의끼리 어긋나면 import 시점에 바로 알 수 있게 한다 ----------

for _category, _aspects in ASPECTS.items():
    if set(ATTRIBUTES[_category]) != _aspects:
        raise ValueError(f"{_category}: ASPECTS와 ATTRIBUTES의 aspect가 다릅니다")
    if _aspects - set(ASPECT_NAMES_KO):
        raise ValueError(f"{_category}: 한국어 이름이 없는 aspect {_aspects - set(ASPECT_NAMES_KO)}")
    for _values in ATTRIBUTES[_category].values():
        if set(_values) - set(VALUE_NAMES_KO):
            raise ValueError(f"한국어 이름이 없는 attribute 값 {set(_values) - set(VALUE_NAMES_KO)}")
if set(TRAVELER_CONTEXTS) != set(TRAVELER_NAMES_KO):
    raise ValueError("TRAVELER_CONTEXTS와 TRAVELER_NAMES_KO가 다릅니다")


class Aspect(TypedDict):
    category: str  # ASPECTS[레코드의 카테고리] 중 하나
    attribute: str  # ATTRIBUTES[카테고리][aspect] 중 하나
    sentiment: Sentiment
    evidence: str  # 리뷰 원문에 그대로 있는 부분 문자열


class Label(TypedDict):
    traveler_context: list[TravelerContext]
    aspects: list[Aspect]
