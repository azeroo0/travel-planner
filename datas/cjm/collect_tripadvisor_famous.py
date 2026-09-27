"""해운대구·기장군의 유명 장소를 영어 이름으로 찾아 Tripadvisor 한국어 리뷰를 장소별로 모은다 (평가용).

Tripadvisor 카탈로그는 영어 이름 중심이라 한국어 이름 검색(collect_tripadvisor.py)과
평점순 지역 검색(collect_tripadvisor_area.py)으로는 리뷰가 많은 곳을 찾기 어려웠다.
그래서 리뷰가 많은 대표 장소를 목록(FAMOUS)으로 정해 영어 이름으로 찾는다.
검색 결과 주소에 해운대·기장이 없으면 버린다.

결과는 기존 데이터와 섞이지 않게 out/real/tripadvisor_famous/ 에만 둔다 (커밋 금지).
  locations.json          목록 장소 → Location ID, 우리 장소(place_id·split) 대조 결과, 리뷰 수집 여부
  reviews.jsonl           한국어 원문 리뷰 한 줄에 하나
  reviews_by_place.json   장소별로 묶은 리뷰 (reviews.jsonl에서 만듦, 호출 없음)
작성자 정보는 저장하지 않고, 평가에만 쓴다.
과금은 다른 Tripadvisor 스크립트와 같은 누적 파일로 합산한다.

사용법:
  uv run python datas/cjm/collect_tripadvisor_famous.py --dry-run
  uv run python datas/cjm/collect_tripadvisor_famous.py --max-billable 130
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Final, NamedTuple

import requests
from dotenv import load_dotenv

from collect_tripadvisor import (
    HERE,
    LIFETIME_FREE,
    LIFETIME_LIMIT,
    OUT_DIR,
    SEARCH_INTERVAL,
    SEARCH_SIZE,
    Budget,
    StopRun,
    allow_locations,
    call,
    fetch_reviews,
    load_usage,
    primary_korean,
)
from collect_tripadvisor_area import match_our_place
from label_check import load_places

FAMOUS_DIR: Final = OUT_DIR / "tripadvisor_famous"
LOCATIONS_PATH: Final = FAMOUS_DIR / "locations.json"
REVIEWS_PATH: Final = FAMOUS_DIR / "reviews.jsonl"
BY_PLACE_PATH: Final = FAMOUS_DIR / "reviews_by_place.json"
SPLIT_PATH: Final = HERE / "out" / "split.json"
DISTRICT_NAMES: Final = {"haeundae": ("해운대", "haeundae"), "gijang": ("기장", "gijang")}
TA_CATEGORY: Final = {"hotel": "HOTEL", "restaurant": "RESTAURANT", "attraction": "ATTRACTION"}


class Famous(NamedTuple):
    key: str  # 목록 안에서 장소를 가리키는 이름
    query: str  # Tripadvisor 검색어 (영어)
    name_ko: str
    category: str
    district: str


FAMOUS: Final = [
    # 해운대구 관광지
    Famous("haeundae_beach", "Haeundae Beach", "해운대해수욕장", "attraction", "haeundae"),
    Famous("dongbaekseom", "Dongbaekseom Island", "동백섬", "attraction", "haeundae"),
    Famous("nurimaru", "Nurimaru APEC House", "누리마루 APEC하우스", "attraction", "haeundae"),
    Famous("the_bay_101", "The Bay 101", "더베이101", "attraction", "haeundae"),
    Famous("busan_x_the_sky", "Busan X the Sky", "부산엑스더스카이", "attraction", "haeundae"),
    Famous("blueline_park", "Haeundae Blueline Park", "해운대 블루라인파크", "attraction", "haeundae"),
    Famous("sea_life", "SEA LIFE Busan Aquarium", "씨라이프 부산아쿠아리움", "attraction", "haeundae"),
    Famous("cinema_center", "Busan Cinema Center", "영화의전당", "attraction", "haeundae"),
    Famous("shinsegae_centum", "Shinsegae Centum City", "신세계 센텀시티", "attraction", "haeundae"),
    Famous("spa_land", "Spa Land Centum City", "스파랜드 센텀시티", "attraction", "haeundae"),
    Famous("dalmaji", "Dalmaji Hill", "달맞이길", "attraction", "haeundae"),
    Famous("songjeong_beach", "Songjeong Beach", "송정해수욕장", "attraction", "haeundae"),
    Famous("cheongsapo", "Cheongsapo", "청사포", "attraction", "haeundae"),
    Famous("haeundae_market", "Haeundae Traditional Market", "해운대시장", "attraction", "haeundae"),
    # 기장군 관광지
    Famous("haedong_yonggungsa", "Haedong Yonggungsa Temple", "해동용궁사", "attraction", "gijang"),
    Famous("lotte_world_busan", "Lotte World Adventure Busan", "롯데월드 어드벤처 부산", "attraction", "gijang"),
    Famous("lotte_outlet_gijang", "Lotte Premium Outlets Dongbusan", "롯데프리미엄아울렛 동부산점", "attraction", "gijang"),
    Famous("ilgwang_beach", "Ilgwang Beach", "일광해수욕장", "attraction", "gijang"),
    Famous("jukseong_church", "Jukseong Cathedral", "죽성성당", "attraction", "gijang"),
    Famous("ahopsan_forest", "Ahopsan Forest", "아홉산숲", "attraction", "gijang"),
    Famous("science_museum", "National Science Museum Busan", "국립부산과학관", "attraction", "gijang"),
    Famous("jangansa", "Jangansa Temple", "장안사", "attraction", "gijang"),
    Famous("gijang_market", "Gijang Market", "기장시장", "attraction", "gijang"),
    # 해운대구 호텔
    Famous("park_hyatt", "Park Hyatt Busan", "파크 하얏트 부산", "hotel", "haeundae"),
    Famous("signiel", "Signiel Busan", "시그니엘 부산", "hotel", "haeundae"),
    Famous("paradise", "Paradise Hotel Busan", "파라다이스 호텔 부산", "hotel", "haeundae"),
    Famous("westin_josun", "The Westin Josun Busan", "웨스틴 조선 부산", "hotel", "haeundae"),
    Famous("grand_josun", "Grand Josun Busan", "그랜드 조선 부산", "hotel", "haeundae"),
    Famous("novotel", "Novotel Ambassador Busan", "노보텔 앰배서더 부산", "hotel", "haeundae"),
    # 기장군 호텔
    Famous("hilton_busan", "Hilton Busan", "힐튼 부산", "hotel", "gijang"),
    # 식당
    Famous("geumsu_bokguk", "Geumsu Bokguk Haeundae", "금수복국 해운대본점", "restaurant", "haeundae"),
    Famous("haeundae_amso_galbi", "Haeundae Amso Galbi", "해운대암소갈비집", "restaurant", "haeundae"),
]


# ---------- 상태 ----------


def load_locations() -> dict[str, dict]:
    """목록 key → {"location_id", "tripadvisor_name", "address", "place_id", "split", "fetched"}"""
    return json.loads(LOCATIONS_PATH.read_text(encoding="utf-8")) if LOCATIONS_PATH.exists() else {}


def save_locations(locations: dict[str, dict]) -> None:
    LOCATIONS_PATH.write_text(json.dumps(locations, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------- 1. 검색 ----------


def address_text(location: dict) -> str:
    return " ".join(address.get("formatted", "") for address in location.get("addresses", []))


def in_district(location: dict, district: str) -> bool:
    return any(name in address_text(location).lower() for name in DISTRICT_NAMES[district])


def primary_name(location: dict) -> str:
    return next((n["value"] for n in location.get("names", []) if n.get("primary")), "")


def search_famous(place: Famous, budget: Budget) -> dict | None:
    """주소가 해당 구·군인 첫 결과를 고른다. 없으면 None."""
    budget.reserve(SEARCH_SIZE)
    time.sleep(SEARCH_INTERVAL)
    try:
        page = call("GET", "/catalog/locations/search", params={
            "query": place.query,
            "category": TA_CATEGORY[place.category],
            "country_code": "KR",
            "geo_name": "Busan",
            "size": SEARCH_SIZE,
        })  # fmt: skip
    except requests.RequestException as e:
        budget.failed(SEARCH_SIZE)
        print(f"  ⚠️ 검색 실패 {place.query}: {e}")
        return None
    results = [item["location"] for item in page.get("data", [])]
    budget.succeeded(len(results))
    return next((location for location in results if in_district(location, place.district)), None)


def summarize(place: Famous, location: dict | None, places: list[dict], split: dict[str, str]) -> dict:
    if location is None:
        return {"location_id": None, "fetched": True}  # 못 찾은 곳은 다시 검색하지 않는다
    coords = location.get("coordinates") or {}
    ours = match_our_place(
        {"lat": coords.get("latitude"), "lng": coords.get("longitude"), "category": place.category}, places, split
    )
    return {
        "location_id": location["id"],
        "tripadvisor_name": primary_name(location),
        "address": address_text(location),
        "place_id": ours.get("place_id"),
        "split": ours.get("split"),
        "fetched": False,
    }


def search_step(locations: dict[str, dict], budget: Budget) -> None:
    places = list(load_places(HERE / "out").values())
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8")) if SPLIT_PATH.exists() else {}
    todo = [place for place in FAMOUS if place.key not in locations]
    print(f"\n[1/3] 검색 {len(todo)}곳 (이미 찾은 {len(FAMOUS) - len(todo)}곳은 건너뜀)")
    for place in todo:
        location = search_famous(place, budget)
        locations[place.key] = summarize(place, location, places, split)
        save_locations(locations)
        found = locations[place.key]
        print(f"  {'✓' if location else '·'} {place.name_ko} → {found.get('tripadvisor_name', '')} {found['location_id'] or ''}")


# ---------- 2·3. 허용 목록과 리뷰 ----------


def pending(locations: dict[str, dict]) -> dict[int, list[Famous]]:
    """리뷰를 아직 안 받은 Location ID → 목록 장소들. 같은 ID는 한 번만 호출한다."""
    groups: dict[int, list[Famous]] = {}
    for place in FAMOUS:
        found = locations.get(place.key, {})
        if found.get("location_id") and not found["fetched"]:
            groups.setdefault(found["location_id"], []).append(place)
    return groups


def to_record(place: Famous, found: dict, review: dict) -> dict | None:
    text = primary_korean(review.get("text"))
    if text is None:
        return None
    return {
        "review_id": f"ta_{review['id']}",
        "famous_key": place.key,
        "name_ko": place.name_ko,
        "category": place.category,
        "district": place.district,
        "place_id": found["place_id"],  # 우리 장소와 겹치지 않으면 None
        "split": found["split"],
        "synthetic": False,
        "source": "tripadvisor",
        "collection": "famous",
        "tripadvisor_location_id": found["location_id"],
        "review": text,
        "title": primary_korean(review.get("title")),
        "rating": review.get("rating"),
        "trip_type": review.get("trip_type"),
        "published": review.get("publish_ts"),
    }  # 작성자 정보(user)는 저장하지 않는다


def reviews_step(locations: dict[str, dict], budget: Budget, skip_allowlist: bool) -> None:
    todo = pending(locations)
    if skip_allowlist:
        print("\n[2/3] 허용 목록 추가 건너뜀 (--skip-allowlist)")
    else:
        print(f"\n[2/3] 허용 목록 추가 {len(todo)}곳 (무료, 한 번에)")
        allow_locations(list(todo))

    print(f"\n[3/3] 리뷰 {len(todo)}곳")
    with open(REVIEWS_PATH, "a", encoding="utf-8") as out:
        for location_id, same in todo.items():
            reviews = fetch_reviews(location_id, budget)
            for place in same:
                locations[place.key]["fetched"] = True  # 실패해도 다시 호출하지 않는다 (중복 과금 방지)
            save_locations(locations)
            if reviews is None:
                continue
            place = same[0]
            records = [r for r in (to_record(place, locations[place.key], review) for review in reviews) if r]
            for record in records:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            print(f"  {place.name_ko}: 받은 {len(reviews)}건 중 한국어 원문 {len(records)}건")


# ---------- 장소별 묶기 (호출 없음) ----------


def write_by_place(locations: dict[str, dict]) -> None:
    records = [json.loads(line) for line in open(REVIEWS_PATH, encoding="utf-8")] if REVIEWS_PATH.exists() else []
    grouped = []
    for place in FAMOUS:
        found = locations.get(place.key, {})
        reviews = [r for r in records if r["famous_key"] == place.key]
        grouped.append({
            "famous_key": place.key,
            "name_ko": place.name_ko,
            "category": place.category,
            "district": place.district,
            "tripadvisor_location_id": found.get("location_id"),
            "tripadvisor_name": found.get("tripadvisor_name"),
            "place_id": found.get("place_id"),
            "split": found.get("split"),
            "review_count": len(reviews),
            "reviews": [{k: r[k] for k in ("review_id", "review", "title", "rating", "trip_type", "published")} for r in reviews],
        })  # fmt: skip
    BY_PLACE_PATH.write_text(json.dumps(grouped, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n장소별 묶음 → {BY_PLACE_PATH}")
    for district in DISTRICT_NAMES:
        rows = [g for g in grouped if g["district"] == district]
        print(f"  {district}: 장소 {len(rows)}곳, 리뷰 있는 곳 {sum(1 for g in rows if g['review_count'])}곳, "
              f"한국어 리뷰 {sum(g['review_count'] for g in rows)}건")


# ---------- 실행 ----------


def print_plan(locations: dict[str, dict]) -> None:
    searches = sum(1 for place in FAMOUS if place.key not in locations)
    fetches = searches + len(pending(locations))
    print(f"목록 {len(FAMOUS)}곳: 검색 {searches}번 (최대 {searches * SEARCH_SIZE}건) + 리뷰 최대 {fetches}번")
    print(f"예상 최대 과금 {searches * SEARCH_SIZE + fetches}건 / 누적 {load_usage()}건 / "
          f"누적 상한 {LIFETIME_LIMIT}건 (무료 {LIFETIME_FREE}건)")


def main() -> None:
    parser = argparse.ArgumentParser(description="해운대·기장 유명 장소의 Tripadvisor 한국어 리뷰 (평가용, 커밋 금지)")
    parser.add_argument("--max-billable", type=int, default=130, help="이번 실행의 과금 상한")
    parser.add_argument("--dry-run", action="store_true", help="호출 없이 계획만 출력")
    parser.add_argument("--skip-allowlist", action="store_true", help="허용 목록 없이 리뷰를 부른다 (필요 없는 계정인지 확인용)")
    args = parser.parse_args()

    load_dotenv(HERE.parent.parent / ".env")
    FAMOUS_DIR.mkdir(parents=True, exist_ok=True)
    locations = load_locations()
    print_plan(locations)
    if args.dry_run:
        return
    if not os.environ.get("TRIPADVISOR_API_KEY"):
        raise SystemExit(".env에 TRIPADVISOR_API_KEY가 없습니다.")

    budget = Budget(args.max_billable)
    try:
        search_step(locations, budget)
        reviews_step(locations, budget, args.skip_allowlist)
    except StopRun as e:
        print(f"\n⛔ {e}")
    write_by_place(locations)
    print(f"\n이번 실행 과금 {budget.billable}건 / 누적 {load_usage()}건")


if __name__ == "__main__":
    main()
