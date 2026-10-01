"""[임시] 튜닝 전 원본 모델과 튜닝 모델의 추천 결과 비교.

DB의 리뷰를 세 조건으로 다시 라벨링해 파일에 저장하고(DB에는 쓰지 않는다), 서비스와 같은 적합도 계산
(recommendations.score_places)을 조건별 라벨에 적용한다. 세 조건은 모델과 프롬프트만 다르고 검증 규칙은 같다.

  base         원본 exaone3.5:2.4b + 학습 프롬프트
  base_labels  원본 exaone3.5:2.4b + 학습 프롬프트 + 카테고리별 허용 라벨 목록
  tuned        튜닝 모델(OLLAMA_MODEL) + 학습 프롬프트

라벨링:  uv run python -m backend.services.model_compare [조건 ...]
"""

import asyncio
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.clients.ollama_client import OllamaClient
from backend.core.config import get_settings
from backend.schemas.recommendations import PlaceRecommendationQuery
from backend.services import recommendations as recommendation_service
from backend.services.analysis import SYSTEM_PROMPT

LABEL_DIR = Path("datas/model_compare/out")  # datas/*/out/은 커밋하지 않는다
BASE_MODEL = "exaone3.5:2.4b"
SENTIMENTS = {"positive", "negative", "neutral"}

CONDITIONS = {
    "base": {"name": "원본", "detail": "exaone3.5:2.4b · 학습 프롬프트"},
    "base_labels": {"name": "원본 + 라벨 목록", "detail": "exaone3.5:2.4b · 허용 라벨 목록 추가"},
    "tuned": {"name": "튜닝 (QLoRA)", "detail": "exaone-tripfit:qlora-v2 · 학습 프롬프트"},
}


async def load_vocab(session: AsyncSession) -> tuple[dict[str, dict[str, set[str]]], list[str]]:
    """({카테고리: {aspect: 허용 attribute}}, 동행 유형 코드)."""
    rows = await session.execute(text(
        "select pc.category_code, a.aspect_name, av.value_name from aspects a"
        " join place_categories pc using (category_id)"
        " join aspect_values av on av.aspect_id = a.aspect_id and av.is_active where a.is_active"
    ))
    vocab: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for category, aspect, value in rows:
        vocab[category][aspect].add(value)
    companions = (await session.execute(text(
        "select companion_code from companion_types where is_active order by companion_type_id"
    ))).scalars().all()
    return vocab, list(companions)


def _system_prompt(condition: str, category: str, vocab: dict[str, dict[str, set[str]]], companions: list[str]) -> str:
    if condition != "base_labels":
        return SYSTEM_PROMPT
    aspects = "\n".join(f"- {aspect}: {', '.join(sorted(values))}" for aspect, values in sorted(vocab[category].items()))
    return (f"{SYSTEM_PROMPT}\n\n[허용 값]\n카테고리 {category}의 category(aspect)와 attribute:\n{aspects}\n"
            f"sentiment: positive, negative, neutral\ntraveler_context: {', '.join(companions)}")


def validate(output: str, review: str, category: str, vocab: dict[str, dict[str, set[str]]], companions: list[str]) -> dict:
    """서비스 라벨과 같은 자동 검증: JSON, 허용 aspect·attribute·sentiment, evidence가 원문에 그대로 있는지."""
    start, end = output.find("{"), output.rfind("}")
    try:
        data = json.loads(output[start:end + 1]) if 0 <= start < end else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return {"parse_ok": False, "aspects": [], "rejected": {}, "traveler_context": []}
    aspects, rejected = [], defaultdict(int)
    for item in data.get("aspects") if isinstance(data.get("aspects"), list) else []:
        if not isinstance(item, dict):
            rejected["not_object"] += 1
        elif item.get("category") not in vocab[category]:
            rejected["unknown_aspect"] += 1
        elif item.get("attribute") not in vocab[category][item["category"]]:
            rejected["unknown_attribute"] += 1
        elif item.get("sentiment") not in SENTIMENTS:
            rejected["unknown_sentiment"] += 1
        elif not isinstance(item.get("evidence"), str) or not item["evidence"].strip() or item["evidence"] not in review:
            rejected["evidence_not_in_review"] += 1
        else:
            aspects.append({key: item[key] for key in ("category", "attribute", "sentiment", "evidence")})
    contexts = data.get("traveler_context") if isinstance(data.get("traveler_context"), list) else []
    return {"parse_ok": True, "aspects": aspects, "rejected": dict(rejected),
            "traveler_context": [c for c in contexts if c in companions]}


def _label_path(condition: str) -> Path:
    return LABEL_DIR / f"labels_{condition}.json"


async def label_reviews(condition: str) -> None:
    """리뷰 전체를 한 조건으로 라벨링한다. 이미 저장된 리뷰는 건너뛰어 중간에 멈춰도 이어서 할 수 있다."""
    from backend.db.session import get_sessionmaker

    model = BASE_MODEL if condition.startswith("base") else get_settings().ollama_model
    path = _label_path(condition)
    path.parent.mkdir(parents=True, exist_ok=True)
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"model": model, "reviews": {}}
    client = OllamaClient()
    async with get_sessionmaker()() as session:
        vocab, companions = await load_vocab(session)
        reviews = (await session.execute(text(
            "select r.review_id, r.place_id, pc.category_code, r.review_text from reviews r"
            " join places p using (place_id) join place_categories pc using (category_id)"
            " where not r.is_synthetic order by r.review_id"
        ))).all()
    started = time.time()
    for done, (review_id, place_id, category, review) in enumerate(reviews, start=1):
        if str(review_id) in saved["reviews"]:
            continue
        messages = [
            {"role": "system", "content": _system_prompt(condition, category, vocab, companions)},
            {"role": "user", "content": f"[카테고리]\n{category}\n\n[리뷰]\n{review}"},
        ]
        try:
            output = await client.chat(model, messages)
        except httpx.HTTPError as error:
            output = f"<error: {error}>"
        saved["reviews"][str(review_id)] = {
            "place_id": place_id, "category": category, "raw": output,
            **validate(output, review, category, vocab, companions),
        }
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[{condition}] {done}/{len(reviews)} review {review_id} ({time.time() - started:.0f}s)", flush=True)


def _load(condition: str) -> dict | None:
    path = _label_path(condition)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


async def compare(session: AsyncSession, query: PlaceRecommendationQuery) -> list[dict]:
    """조건마다 라벨 통계와 서비스와 같은 방식으로 계산한 추천 목록(근거 구절 포함)."""
    candidates = await recommendation_service.all_candidates(session, query.category)
    names = {place.place_id: place for place in candidates}
    results = []
    for key, info in CONDITIONS.items():
        data = _load(key)
        if data is None:
            results.append({"key": key, **info, "ready": False, "stats": None, "items": []})
            continue
        counts: dict[int, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        evidence: dict[tuple[int, str], list[dict]] = defaultdict(list)
        totals: dict[int, int] = defaultdict(int)
        for review_id, review in data["reviews"].items():
            place_id = review["place_id"]
            totals[place_id] += 1
            for aspect in review["aspects"]:
                counts[place_id][aspect["category"]][aspect["sentiment"]] += 1
                evidence[(place_id, aspect["category"])].append(
                    {"review_id": int(review_id), "sentiment": aspect["sentiment"], "text": aspect["evidence"]})
        scored = recommendation_service.score_places(
            [names[p] for p in names if p in counts], counts, totals, query)
        weights = recommendation_service.condition_weights(query)
        reviews = list(data["reviews"].values())
        results.append({
            "key": key, **info, "ready": True,
            "stats": {
                "reviews": len(reviews),
                "parse_ok": sum(r["parse_ok"] for r in reviews),
                "labels": sum(len(r["aspects"]) for r in reviews),
                "rejected": sum(sum(r["rejected"].values()) for r in reviews),
            },
            "items": [{
                "place": {"place_id": item.place.place_id, "name": item.place.name,
                          "category": item.place.category, "region": item.place.region},
                "fit": item.fit,
                "reason": item.reason,
                # 적합도 계산에 쓰인 aspect의 근거 구절 (조건이 없으면 모든 aspect)
                "evidence": [
                    {"aspect": aspect, "label": recommendation_service.label(aspect), **e}
                    for aspect in (weights or counts[item.place.place_id])
                    for e in evidence.get((item.place.place_id, aspect), [])
                ],
            } for item in scored],
        })
    return results


async def _main(conditions: list[str]) -> None:
    # DB 엔진이 처음 쓴 이벤트 루프에 묶이므로 조건마다 asyncio.run을 새로 부르지 않고 한 루프에서 돈다.
    for name in conditions:
        await label_reviews(name)


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:] or list(CONDITIONS)))
