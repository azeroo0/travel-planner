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

# aspect 목록과 attribute 표가 어긋나면 import 시점에 바로 알 수 있게 한다
for _category, _aspects in ASPECTS.items():
    if set(ATTRIBUTES[_category]) != _aspects:
        raise ValueError(f"{_category}: ASPECTS와 ATTRIBUTES의 aspect가 다릅니다")


class Aspect(TypedDict):
    category: str  # ASPECTS[레코드의 카테고리] 중 하나
    attribute: str  # ATTRIBUTES[카테고리][aspect] 중 하나
    sentiment: Sentiment
    evidence: str  # 리뷰 원문에 그대로 있는 부분 문자열


class Label(TypedDict):
    traveler_context: list[TravelerContext]
    aspects: list[Aspect]
