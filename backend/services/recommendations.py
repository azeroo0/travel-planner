"""스크랩한 장소를 사용자 요구사항에 맞춰 순위 매긴다.

LLM이 장소를 고르지 않는다. 요구사항 문장은 aspect 가중치로 해석하고, 각 장소의 점수는
그 장소 리뷰에 달린 구조화 라벨(review_annotations)로만 계산한다.

요구사항 해석은 두 방법을 합친다 (요구사항 30문장 비교 실험에서 F1 0.764, 부정 오류 0, 동행 정확도 100%).
  - 중요한 aspect·신경 쓰지 않는 aspect: 파인튜닝 모델(Ollama). 스크랩한 장소의 카테고리별로 병렬 호출하고,
    neutral로 나온 aspect는 "신경 쓰지 않음"으로 보고 뺀다.
  - 동행 유형(부모님·아이·연인·친구·혼자): 키워드 규칙으로 찾고 관련 aspect 가중치를 더한다.
  - 모델을 쓸 수 없으면(미설정·장애·시간 초과·JSON 오류) 키워드 규칙만으로 해석한다.

  goodness(aspect) = 100 × (긍정 + 0.5 × 중립) / 언급 수, 언급이 적으면 50(중립) 쪽으로 당긴다
  fit(장소)        = 50 + Σ w × (goodness − 50) / Σ w   (장소 리뷰에 언급된 aspect만)

요구사항과 관련된 리뷰가 있는 장소(matched)를 먼저 fit 순으로, 없는 장소는 리뷰 전반 만족도로 그 뒤에 둔다.
"""

import asyncio
import json
import re
from collections import defaultdict

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients.ollama_client import OllamaClient
from backend.core.config import get_settings
from backend.repositories import recommendations as recommendation_repository
from backend.schemas.recommendations import (
    AspectScore,
    AspectWeight,
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    SkippedScrap,
)

ASPECT_LABELS = {
    "activity_variety": "즐길 거리", "amenities": "부대시설", "atmosphere": "분위기",
    "bathroom_quality": "욕실", "bed_comfort": "침구", "breakfast_quality": "조식",
    "cleanliness": "청결", "family_friendly": "아이 동반 편의", "food_quality": "맛",
    "freshness": "신선도", "noise_level": "조용함", "parking_availability": "주차 공간",
    "parking_experience": "주차 편의", "photo_spots": "사진 명소", "portion": "양",
    "rest_facilities": "쉴 곳", "room_condition": "객실 상태", "room_size": "객실 크기",
    "scenery": "경치", "seating_comfort": "좌석", "serving_speed": "음식 나오는 속도",
    "slope_stairs": "경사·계단", "staff_service": "직원 친절", "stay_duration": "머무는 시간",
    "toilet_facilities": "화장실", "view_quality": "전망", "waiting_time": "웨이팅",
    "walking_burden": "걷기 부담", "weather_sensitivity": "날씨 영향",
}

# (요구사항 키워드 정규식, 대표 키워드, {aspect: 가중치}). 프론트 lib/fit.ts의 가중치를 DB aspect 이름에 맞췄다.
KEYWORD_RULES: list[tuple[str, str, dict[str, float]]] = [
    # 동행
    (r"부모님|어르신|어머니|아버지|엄마|아빠|효도", "부모님",
     {"walking_burden": 2, "slope_stairs": 2, "rest_facilities": 2, "toilet_facilities": 1}),
    (r"아이|아기|애들|유모차|어린이|키즈|자녀", "아이",
     {"family_friendly": 3, "walking_burden": 1.5, "slope_stairs": 1.5, "toilet_facilities": 1.5}),
    (r"연인|커플|데이트|기념일|여자\s?친구|남자\s?친구|신혼", "연인",
     {"atmosphere": 2, "scenery": 1.5, "photo_spots": 1.5, "view_quality": 1.5}),
    (r"친구들?(?:이랑|과|와|끼리)", "친구", {"activity_variety": 1.5, "food_quality": 1}),
    (r"혼자|혼행|혼밥", "혼자", {"seating_comfort": 1, "noise_level": 1}),
    # 이동 부담
    (r"걷기\s?(?:힘들|싫|어렵)|많이\s?(?:못\s?)?걷|다리가?\s?아프|무릎|계단|언덕|오르막|경사", "걷기 부담",
     {"walking_burden": 4, "slope_stairs": 4}),
    # 원하는 것
    (r"바다|오션|해변|경치|풍경|야경|전망|뷰", "경치·전망", {"scenery": 3, "view_quality": 3}),
    (r"맛집|맛있|음식|먹거리", "맛", {"food_quality": 3, "freshness": 1}),
    (r"신선|싱싱|회\b|해산물", "신선도", {"freshness": 3}),
    (r"사진|인생샷|포토", "사진", {"photo_spots": 3}),
    (r"조용|한적|소음|시끄", "조용함", {"noise_level": 3.5}),
    (r"휴식|쉬고|쉴|편하게|여유", "휴식", {"rest_facilities": 2, "bed_comfort": 2, "seating_comfort": 1.5}),
    (r"깨끗|청결|위생", "청결", {"cleanliness": 3, "bathroom_quality": 1}),
    (r"친절|서비스", "친절", {"staff_service": 2.5}),
    (r"넓은|넓었|방\s?크기|좁", "공간", {"room_size": 2.5, "seating_comfort": 1}),
    (r"조식|아침\s?식사", "조식", {"breakfast_quality": 3}),
    (r"양이?\s?많|푸짐|배부르", "양", {"portion": 2.5}),
    (r"분위기|감성|인테리어", "분위기", {"atmosphere": 2.5}),
    (r"볼거리|즐길\s?거리|체험|할\s?거리|놀거리", "즐길 거리", {"activity_variety": 3}),
    (r"화장실", "화장실", {"toilet_facilities": 2.5}),
    (r"침대|침구|잠자리", "침구", {"bed_comfort": 3}),
    # 피하고 싶은 것
    (r"웨이팅|기다리|대기|줄\s?서|오래\s?걸", "웨이팅", {"waiting_time": 4, "serving_speed": 1.5}),
    (r"주차|차\s?가지고|자차|운전", "주차", {"parking_availability": 3, "parking_experience": 3}),
    (r"사람\s?많|붐비|혼잡|북적", "혼잡", {"waiting_time": 1, "noise_level": 1.5}),
    (r"날씨|비\s?오|우천|더위|추위", "날씨", {"weather_sensitivity": 2.5}),
]

# 카테고리별 허용 aspect (common/common/schema.py의 ASPECTS와 같다). 모델 출력은 이 목록으로 거른다.
CATEGORY_ASPECTS: dict[str, frozenset[str]] = {
    "hotel": frozenset({"room_condition", "view_quality", "cleanliness", "noise_level", "staff_service", "room_size",
                        "bed_comfort", "amenities", "bathroom_quality", "breakfast_quality",
                        "parking_availability", "parking_experience"}),
    "restaurant": frozenset({"food_quality", "atmosphere", "seating_comfort", "portion", "staff_service", "cleanliness",
                             "freshness", "serving_speed", "waiting_time", "family_friendly", "noise_level",
                             "parking_availability", "parking_experience"}),
    "attraction": frozenset({"walking_burden", "activity_variety", "scenery", "rest_facilities", "photo_spots",
                             "toilet_facilities", "stay_duration", "weather_sensitivity", "slope_stairs",
                             "parking_availability", "parking_experience"}),
}
COMPANION_KEYWORDS = {"부모님", "아이", "연인", "친구", "혼자"}  # KEYWORD_RULES 중 동행 유형 규칙의 대표 키워드
MODEL_WEIGHT = 3.0  # 모델이 중요하다고 본 aspect 하나의 가중치
MODEL_SOURCE = "요구사항 해석 모델"

SHRINK = 2  # 언급이 적은 aspect를 중립(50) 쪽으로 당기는 강도. 언급 2건이면 절반만 반영
STRENGTH_MIN, CAUTION_MAX = 60.0, 40.0


class ScrapNotFound(Exception):
    def __init__(self, scrap_ids: list[int]):
        self.scrap_ids = scrap_ids


def label(aspect: str) -> str:
    return ASPECT_LABELS.get(aspect, aspect)


# 키워드 뒤 같은 절에 이 표현이 있으면 "신경 쓰지 않는다"는 뜻으로 보고 가중치에서 뺀다.
# "웨이팅 없는 곳"처럼 없기를 바라는 요구는 살려야 하므로 '없' 하나만으로는 부정으로 보지 않는다.
NEGATION = re.compile(
    r"필요\s?(?:가\s?)?(?:없|하지\s?않)|상관\s?없|관심\s?없|신경\s?(?:안|쓰지\s?않)|중요하지\s?않"
    r"|안\s?\S*도\s?(?:돼|되|괜찮)|(?:없어|빼)도\s?(?:돼|되|괜찮)"
)
# 절 경계: 문장부호, 줄바꿈, 절을 잇는 어미("~고 ", "~는데", "~지만", "~면서")
CLAUSE_END = re.compile(r"[.!?,\n]|고\s|는데|지만|면서")


def _negated(text: str, end: int) -> bool:
    boundary = CLAUSE_END.search(text, end)
    clause = text[end:boundary.end() if boundary else len(text)]
    return bool(NEGATION.search(clause))


def _keyword_matches(text: str) -> list[tuple[str, dict[str, float], bool]]:
    """(대표 키워드, 가중치 규칙, 부정 여부). 같은 키워드가 여러 번 나오면 한 번이라도 부정이 아니면 살린다."""
    matches = []
    for pattern, keyword, rule in KEYWORD_RULES:
        found = list(re.finditer(pattern, text))
        if found:
            matches.append((keyword, rule, all(_negated(text, m.end()) for m in found)))
    return matches


def ignored_keywords(text: str) -> list[str]:
    return [keyword for keyword, _, negated in _keyword_matches(text) if negated]


def parse_requirements(text: str) -> list[AspectWeight]:
    weights: dict[str, float] = defaultdict(float)
    keywords: dict[str, list[str]] = defaultdict(list)
    for keyword, rule, negated in _keyword_matches(text):
        if not negated:
            for aspect, weight in rule.items():
                weights[aspect] += weight
                if keyword not in keywords[aspect]:
                    keywords[aspect].append(keyword)
    return sorted(
        (AspectWeight(aspect=a, label=label(a), weight=w, keywords=keywords[a]) for a, w in weights.items()),
        key=lambda item: (-item.weight, item.aspect),
    )


def companion_weights(text: str) -> list[AspectWeight]:
    """키워드 규칙 중 동행 유형 규칙만 적용한 가중치."""
    weights: dict[str, float] = defaultdict(float)
    keywords: dict[str, list[str]] = defaultdict(list)
    for keyword, rule, negated in _keyword_matches(text):
        if keyword in COMPANION_KEYWORDS and not negated:
            for aspect, weight in rule.items():
                weights[aspect] += weight
                keywords[aspect].append(keyword)
    return [AspectWeight(aspect=a, label=label(a), weight=w, keywords=keywords[a]) for a, w in weights.items()]


def _model_aspects(text: str, category: str) -> tuple[set[str], set[str]] | None:
    """모델 출력 한 건 → (중요 aspect, 신경 쓰지 않는 aspect). JSON이 아니면 None."""
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1]) if 0 <= start < end else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return None
    important, ignored = set(), set()
    for item in data.get("aspects", []) if isinstance(data.get("aspects"), list) else []:
        if not isinstance(item, dict) or item.get("category") not in CATEGORY_ASPECTS[category]:
            continue
        if item.get("sentiment") == "neutral":
            ignored.add(item["category"])
        elif item.get("sentiment") in {"positive", "negative"}:
            important.add(item["category"])
    return important, ignored


async def model_interpretation(text: str, categories: list[str], client: OllamaClient | None = None) -> tuple[set[str], set[str]] | None:
    """스크랩 장소의 카테고리별로 파인튜닝 모델에 요구사항을 넣어 (중요, 무시) aspect를 모은다. 쓸 수 없으면 None."""
    from backend.services.analysis import SYSTEM_PROMPT

    settings = get_settings()
    categories = [c for c in categories if c in CATEGORY_ASPECTS]
    if not settings.ollama_model or not categories:
        return None
    client = client or OllamaClient()

    async def ask(category: str) -> tuple[set[str], set[str]] | None:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"[카테고리]\n{category}\n\n[리뷰]\n{text}"},
        ]
        try:
            return _model_aspects(await client.chat(settings.ollama_model, messages), category)
        except httpx.HTTPError:
            return None

    try:
        results = await asyncio.wait_for(asyncio.gather(*(ask(c) for c in categories)),
                                         timeout=settings.recommendation_model_timeout_seconds)
    except TimeoutError:
        return None
    results = [r for r in results if r is not None]
    if not results:
        return None
    important = set().union(*(r[0] for r in results))
    ignored = set().union(*(r[1] for r in results))
    return important - ignored, ignored


async def interpret_requirements(text: str, categories: list[str], client: OllamaClient | None = None) -> tuple[list[AspectWeight], list[str], str]:
    """(가중치, 신경 쓰지 않는 항목, 해석 방식 "model" | "keywords")."""
    model = await model_interpretation(text, categories, client)
    if model is None:
        return parse_requirements(text), ignored_keywords(text), "keywords"
    important, ignored = model
    weights: dict[str, AspectWeight] = {
        a: AspectWeight(aspect=a, label=label(a), weight=MODEL_WEIGHT, keywords=[MODEL_SOURCE]) for a in important
    }
    for companion in companion_weights(text):
        if companion.aspect in weights:
            weights[companion.aspect].weight += companion.weight
            weights[companion.aspect].keywords += companion.keywords
        elif companion.aspect not in ignored:
            weights[companion.aspect] = companion
    ordered = sorted(weights.values(), key=lambda item: (-item.weight, item.aspect))
    return ordered, sorted(label(a) for a in ignored), "model"


def goodness(counts: dict[str, int]) -> tuple[float, int]:
    """(0~100 만족도, 언급 수)."""
    mentions = sum(counts.values())
    if not mentions:
        return 50.0, 0
    raw = 100 * (counts.get("positive", 0) + 0.5 * counts.get("neutral", 0)) / mentions
    return 50 + (raw - 50) * mentions / (mentions + SHRINK), mentions


def _reason(strengths: list[AspectScore], cautions: list[AspectScore], matched: bool) -> str:
    good = ", ".join(s.label for s in strengths[:2])
    bad = ", ".join(c.label for c in cautions[:2])
    subject = "요구사항과 관련해" if matched else "리뷰 전반에서"
    if good and bad:
        return f"{subject} {good} 평가가 좋지만 {bad}은(는) 아쉽다는 리뷰가 있어요."
    if good:
        return f"{subject} {good} 평가가 좋아요."
    if bad:
        return f"{subject} {bad}에 대한 아쉬운 리뷰가 있어요."
    return "요구사항과 관련된 리뷰가 적어 판단 근거가 부족해요."


async def recommend(session: AsyncSession, *, user_id: int, request: RecommendationRequest) -> RecommendationResponse:
    scrap_ids = list(dict.fromkeys(request.scrap_ids))
    scraps = {s.scrap_id: s for s in await recommendation_repository.user_scraps(session, user_id=user_id, scrap_ids=scrap_ids)}
    missing = [scrap_id for scrap_id in scrap_ids if scrap_id not in scraps]
    if missing:
        raise ScrapNotFound(missing)

    # 스크랩 → 장소. 리뷰 스크랩은 그 리뷰의 장소를 쓰고, 장소를 알 수 없는 외부 링크는 제외한다.
    review_place = await recommendation_repository.review_places(
        session, [s.review_id for s in scraps.values() if s.place_id is None and s.review_id is not None],
    )
    place_scraps: dict[int, list[int]] = {}
    skipped: list[SkippedScrap] = []
    for scrap_id in scrap_ids:
        scrap = scraps[scrap_id]
        place_id = scrap.place_id or review_place.get(scrap.review_id)
        if place_id is None:
            skipped.append(SkippedScrap(scrap_id=scrap_id, reason="장소 정보가 없는 스크랩이라 추천에서 제외했어요."))
        else:
            place_scraps.setdefault(place_id, []).append(scrap_id)

    place_ids = list(place_scraps)
    if not place_ids:
        return RecommendationResponse(requirements=request.requirements, interpreter="keywords",
                                      weights=parse_requirements(request.requirements),
                                      ignored_keywords=ignored_keywords(request.requirements), items=[], skipped=skipped)

    info = await recommendation_repository.places(session, place_ids)
    categories = sorted({category for _, category in info.values()})
    weights, ignored, interpreter = await interpret_requirements(request.requirements, categories)
    reviews = await recommendation_repository.review_counts(session, place_ids)
    evidence = await recommendation_repository.evidence(session, place_ids)
    counts: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(dict))
    for place_id, aspect, sentiment, count in await recommendation_repository.sentiment_counts(session, place_ids):
        counts[place_id][aspect][sentiment] = count

    items: list[RecommendationItem] = []
    for place_id in place_ids:
        place_counts = counts[place_id]
        # 요구사항 aspect 중 이 장소 리뷰에 언급된 것만 쓴다. 하나도 없으면 전체 aspect를 같은 가중치로 본다.
        applicable = {w.aspect: w.weight for w in weights if w.aspect in place_counts}
        matched = bool(applicable)
        used = applicable or {aspect: 1.0 for aspect in place_counts}

        scores: list[tuple[AspectScore, float]] = []
        for aspect, weight in used.items():
            value, mentions = goodness(place_counts[aspect])
            sentiment = "positive" if value >= 50 else "negative"
            score = AspectScore(aspect=aspect, label=label(aspect), goodness=round(value, 1), mentions=mentions,
                                evidence=evidence.get((place_id, aspect, sentiment)))
            scores.append((score, weight))

        total = sum(weight for _, weight in scores)
        fit = 50 + sum(weight * (s.goodness - 50) for s, weight in scores) / total if total else 50.0
        strengths = [s for s, w in sorted(scores, key=lambda x: -x[1] * (x[0].goodness - 50)) if s.goodness >= STRENGTH_MIN][:3]
        cautions = [s for s, w in sorted(scores, key=lambda x: -x[1] * (50 - x[0].goodness)) if s.goodness <= CAUTION_MAX][:3]
        name, category = info.get(place_id, (None, "unknown"))
        items.append(RecommendationItem(
            rank=0, place_id=place_id, place_name=name, category=category, scrap_ids=place_scraps[place_id],
            fit=round(fit, 1), matched=matched, review_count=reviews.get(place_id, 0),
            reason=_reason(strengths, cautions, matched), strengths=strengths, cautions=cautions,
        ))

    # 요구사항과 관련된 리뷰가 있는 장소를 먼저, 그 안에서 fit 순. 관련 리뷰가 없는 장소는 리뷰 전반 점수로 뒤에 둔다.
    items.sort(key=lambda item: (not item.matched, -item.fit, -item.review_count, item.place_id))
    for rank, item in enumerate(items, start=1):
        item.rank = rank
    return RecommendationResponse(requirements=request.requirements, interpreter=interpreter, weights=weights,
                                  ignored_keywords=ignored, items=items, skipped=skipped)
