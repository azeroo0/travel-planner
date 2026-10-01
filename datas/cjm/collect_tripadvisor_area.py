"""Tripadvisor에 등록된 해운대구·기장군 장소를 지역으로 찾아 한국어 리뷰를 받는다 (평가용).

우리 장소 목록(TourAPI 등)과 따로 모은다. 이름으로 매칭하는 방식(collect_tripadvisor.py)은
한국어 이름 검색이 잘 되지 않아서, Tripadvisor 쪽에서 지역 범위로 장소를 찾는다.
수집 뒤 좌표로 우리 장소와 대조해, 겹치면 place_id와 분할(split)을 붙인다 (호출 없음).

약관·보관 조건은 collect_tripadvisor.py와 같다: out/real/ 에만 두고(커밋 금지),
작성자 정보는 저장하지 않으며, 평가에만 쓴다.
과금도 같은 누적 파일(tripadvisor_usage.json)로 합산해 두 스크립트를 합쳐 누적 상한을 지킨다.

호출을 통제하려고 두 단계로 나눠 실행한다.
  1) --step search : 지역 × 카테고리 검색 (결과 장소 수만큼 과금, 한 번 한 검색은 다시 하지 않음)
  2) --step reviews: 카테고리별 리뷰가 많은 곳 N곳 → 허용 목록 추가(무료) → 리뷰 1번씩

사용법:
  uv run python datas/cjm/collect_tripadvisor_area.py --step search --dry-run
  uv run python datas/cjm/collect_tripadvisor_area.py --step search --max-billable 120
  uv run python datas/cjm/collect_tripadvisor_area.py --step reviews --per-category 10 --max-billable 30
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Final

import requests
from dotenv import load_dotenv

from collect_tripadvisor import (
    HERE,
    LIFETIME_FREE,
    LIFETIME_LIMIT,
    MATCH_RADIUS_KM,
    OUT_DIR,
    SEARCH_INTERVAL,
    Budget,
    StopRun,
    allow_locations,
    call,
    distance_km,
    fetch_reviews,
    load_usage,
    primary_korean,
)
from paths import SPLIT_PATH, load_places

STATE_PATH: Final = OUT_DIR / "tripadvisor_area.json"
REVIEWS_PATH: Final = OUT_DIR / "tripadvisor_area_reviews.jsonl"
PAGE_SIZE: Final = 20  # 최대값. 과금은 돌려받은 장소 수만큼이다

# 사각형 범위는 50㎢를 넘으면 400이라, 지역마다 중심 한 곳 + 반경(최대 8km)으로 찾는다.
# 경계 밖(수영구, 금정구, 울산)도 섞이므로 주소로 한 번 더 거른다
AREAS: Final = {
    "haeundae": {"lat": 35.17, "lon": 129.16, "radius": 6, "names": ("해운대", "haeundae")},  # 센텀·송정·반송까지
    "gijang": {"lat": 35.24, "lon": 129.22, "radius": 8, "names": ("기장", "gijang")},  # 오시리아·일광·정관까지
}
CATEGORIES: Final = {"HOTEL": "hotel", "RESTAURANT": "restaurant", "ATTRACTION": "attraction"}


# ---------- 상태 파일 ----------


def load_state() -> dict:
    """searches: 끝낸 검색 키 목록 / locations: Location ID → 요약 / allowlisted: 허용 목록에 넣은 ID"""
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"searches": [], "locations": {}, "allowlisted": []}


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def search_keys() -> list[tuple[str, str, str]]:
    return [(f"{district}:{category}:p1", district, category) for district in AREAS for category in CATEGORIES]


# ---------- 1단계: 지역 검색 ----------


def in_district(location: dict, district: str) -> bool:
    texts = " ".join(address.get("formatted", "") for address in location.get("addresses", [])).lower()
    return any(name in texts for name in AREAS[district]["names"])


def display_name(location: dict) -> str:
    names = location.get("names", [])
    korean = next((n["value"] for n in names if n.get("language") == "ko"), None)
    return korean or next((n["value"] for n in names if n.get("primary")), "") or str(location["id"])


def summarize(location: dict, district: str, category: str) -> dict:
    coords = location.get("coordinates") or {}
    rating = location.get("overall_rating") or {}
    return {
        "name": display_name(location),
        "district": district,
        "category": CATEGORIES[category],
        "lat": coords.get("latitude"),
        "lng": coords.get("longitude"),
        "review_count": rating.get("count") or 0,
        "fetched": False,
    }


def search_area(key: str, district: str, category: str, state: dict, budget: Budget) -> None:
    area = {k: v for k, v in AREAS[district].items() if k != "names"}
    budget.reserve(PAGE_SIZE)
    time.sleep(SEARCH_INTERVAL)
    try:
        page = call("GET", "/catalog/locations/nearby", params={
            **area, "unit": "KM", "category": category,
            "locale": "ko-KR",  # 지역까지 붙인 값이어야 한다 ("ko"는 400)
            "size": PAGE_SIZE, "page": 1,
        })  # fmt: skip
    except requests.RequestException as e:
        budget.failed(PAGE_SIZE)
        print(f"  ⚠️ {key} 검색 실패: {e}")
        state["searches"].append(key)  # 실패해도 다시 호출하지 않는다
        save_state(state)
        return

    results = [item["location"] for item in page.get("data", [])]
    budget.succeeded(len(results))
    kept = [location for location in results if in_district(location, district)]
    for location in kept:
        state["locations"].setdefault(str(location["id"]), summarize(location, district, category))
    state["searches"].append(key)
    save_state(state)
    print(f"  {key}: 결과 {len(results)}곳 중 {AREAS[district]['names'][0]} 주소 {len(kept)}곳")


def search_step(state: dict, budget: Budget) -> None:
    todo = [key for key in search_keys() if key[0] not in state["searches"]]
    print(f"\n지역 검색 {len(todo)}번 (이미 한 {len(search_keys()) - len(todo)}번은 건너뜀)")
    for key, district, category in todo:
        search_area(key, district, category, state, budget)


# ---------- 2단계: 리뷰 ----------


def pick_targets(state: dict, per_category: int) -> list[str]:
    """카테고리마다 리뷰 수가 많은 곳부터 고른다. 이미 리뷰를 받은 곳은 뺀다."""
    targets: list[str] = []
    for category in CATEGORIES.values():
        ids = [i for i, loc in state["locations"].items() if loc["category"] == category and not loc["fetched"]]
        ids.sort(key=lambda i: state["locations"][i]["review_count"], reverse=True)
        targets += ids[:per_category]
    return targets


def match_our_place(location: dict, places: list[dict], split: dict[str, str]) -> dict:
    """좌표 300m 안의 같은 카테고리 우리 장소가 있으면 place_id와 분할을 돌려준다 (호출 없음)."""
    if location["lat"] is None:
        return {}
    nearby = [
        (distance_km(location["lat"], location["lng"], p["lat"], p["lng"]), p)
        for p in places
        if p["category"] == location["category"] and p["lat"] and 34 < p["lat"] < 36
    ]
    close = [(d, p) for d, p in nearby if d <= MATCH_RADIUS_KM]
    if not close:
        return {}
    place = min(close, key=lambda pair: pair[0])[1]
    return {"place_id": place["place_id"], "split": split.get(place["place_id"])}


def to_record(location_id: str, location: dict, review: dict, ours: dict) -> dict | None:
    text = primary_korean(review.get("text"))
    if text is None:
        return None
    return {
        "review_id": f"ta_{review['id']}",
        "place_id": ours.get("place_id"),  # 우리 장소와 겹치지 않으면 None
        "split": ours.get("split"),
        "category": location["category"],
        "district": location["district"],
        "synthetic": False,
        "source": "tripadvisor",
        "tripadvisor_location_id": int(location_id),
        "tripadvisor_name": location["name"],
        "review": text,
        "title": primary_korean(review.get("title")),
        "rating": review.get("rating"),
        "trip_type": review.get("trip_type"),
        "published": review.get("publish_ts"),
    }  # 작성자 정보(user)는 저장하지 않는다


def allow_step(targets: list[str], state: dict) -> None:
    new = [int(i) for i in targets if int(i) not in state["allowlisted"]]
    print(f"\n허용 목록 추가: {len(new)}곳 (무료, 한 번에)")
    allow_locations(new)  # 실패하면 StopRun으로 멈춰서 리뷰 호출을 하지 않는다
    state["allowlisted"] += new
    save_state(state)


def reviews_step(targets: list[str], state: dict, budget: Budget) -> None:
    places = list(load_places("cjm").values())
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8")) if SPLIT_PATH.exists() else {}
    print(f"\n리뷰 받기: {len(targets)}곳")
    with open(REVIEWS_PATH, "a", encoding="utf-8") as out:
        for location_id in targets:
            location = state["locations"][location_id]
            reviews = fetch_reviews(int(location_id), budget)
            location["fetched"] = True  # 실패해도 다시 호출하지 않는다 (중복 과금 방지)
            save_state(state)
            if reviews is None:
                continue
            ours = match_our_place(location, places, split)
            records = [r for r in (to_record(location_id, location, review, ours) for review in reviews) if r]
            for record in records:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            print(f"  {location['name']} ({location['review_count']}): 받은 {len(reviews)}건 중 한국어 원문 {len(records)}건"
                  f"{' · 우리 장소 ' + ours['place_id'] + ' / ' + str(ours['split']) if ours else ''}")


# ---------- 실행 ----------


def print_plan(step: str, state: dict, per_category: int) -> int:
    if step == "search":
        searches = sum(1 for key in search_keys() if key[0] not in state["searches"])
        cost = searches * PAGE_SIZE
        print(f"지역 검색 {searches}번, 최대 과금 {cost}건")
    else:
        cost = len(pick_targets(state, per_category))
        print(f"리뷰 {cost}곳, 최대 과금 {cost}건 (허용 목록 추가는 무료)")
    print(f"누적 {load_usage()}건 / 누적 상한 {LIFETIME_LIMIT}건 (무료 {LIFETIME_FREE}건)")
    return cost


def main() -> None:
    parser = argparse.ArgumentParser(description="Tripadvisor 해운대·기장 지역 리뷰 수집 (평가용, 커밋 금지)")
    parser.add_argument("--step", required=True, choices=["search", "reviews"])
    parser.add_argument("--per-category", type=int, default=10, help="reviews 단계에서 카테고리별 장소 수")
    parser.add_argument("--max-billable", type=int, required=True, help="이번 실행의 과금 상한")
    parser.add_argument("--dry-run", action="store_true", help="호출 없이 계획만 출력")
    args = parser.parse_args()

    load_dotenv(HERE.parent.parent / ".env")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    print_plan(args.step, state, args.per_category)
    if args.dry_run:
        return
    if not os.environ.get("TRIPADVISOR_API_KEY"):
        raise SystemExit(".env에 TRIPADVISOR_API_KEY가 없습니다.")

    budget = Budget(args.max_billable)
    try:
        if args.step == "search":
            search_step(state, budget)
        else:
            targets = pick_targets(state, args.per_category)
            allow_step(targets, state)
            reviews_step(targets, state, budget)
    except StopRun as e:
        print(f"\n⛔ {e}")
    print(f"\n이번 실행 과금 {budget.billable}건 / 누적 {load_usage()}건")


if __name__ == "__main__":
    main()
