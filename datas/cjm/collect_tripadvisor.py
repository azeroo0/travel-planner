"""Tripadvisor Terra API로 우리 장소의 실제 한국어 리뷰를 받아 평가용으로 저장한다.

⚠️ Tripadvisor 약관(3.1.2 AI·ML 이용 금지, 캐싱 정책: Location ID 외 저장 금지)은
리뷰를 저장하거나 AI 평가에 쓰는 것을 허용하지 않는다. 팀이 위험을 알고 정한 내부 실험용이라서:
  - 결과는 out/real/ 에만 두고 .gitignore로 커밋을 막는다. 공개 저장소에 올리지 않는다.
  - 작성자 정보(user)는 저장하지 않는다.
  - 학습에는 쓰지 않고, 실제 리뷰 테스트셋(평가)에만 쓴다.

과금 (Discover 패키지): 계정 평생 첫 1,000 billable entity가 무료다.
  카탈로그 검색은 돌려받은 장소 수만큼, 리뷰는 호출 한 번에 1건이다. 허용 목록(allowlist) 호출은 무료다.
  --max-billable을 넘기기 전에 멈춘다. 장소 매칭과 리뷰 수집 여부를 저장해 두므로,
  다시 실행하면 이미 처리한 장소에는 호출하지 않는다.

순서: 카탈로그 검색으로 장소 ID 찾기 → 허용 목록에 추가 → 리뷰 받기

사용법:
  uv run python datas/cjm/collect_tripadvisor.py --dry-run           # 호출 없이 예상 과금만 출력
  uv run python datas/cjm/collect_tripadvisor.py --max-places 60 --max-billable 300
"""

import argparse
import json
import math
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import requests
from dotenv import load_dotenv

from label_check import load_places

HERE: Final = Path(__file__).parent
OUT_DIR: Final = HERE / "out" / "real"
MATCHES_PATH: Final = OUT_DIR / "tripadvisor_locations.json"  # place_id → Location ID (약관상 저장 허용)
REVIEWS_PATH: Final = OUT_DIR / "tripadvisor_reviews.jsonl"
USAGE_PATH: Final = OUT_DIR / "tripadvisor_usage.json"  # 실행을 여러 번 해도 누적 과금을 잃지 않게 파일에 남긴다
SPLIT_PATH: Final = HERE / "out" / "split.json"

BASE_URL: Final = "https://terra.tripadvisor.com/api"
SEARCH_SIZE: Final = 3  # 검색은 돌려받은 수만큼 과금되므로 후보를 3개로 줄인다
REVIEW_PAGE_SIZE: Final = 20  # 리뷰는 호출당 1건 과금이라 한 번에 최대로 받는다
SEARCH_INTERVAL: Final = 1.1  # 검색 계열은 초당 1회 제한
MATCH_RADIUS_KM: Final = 0.3
MAX_CONSECUTIVE_FAILURES: Final = 3
LIFETIME_FREE: Final = 1000  # Discover 패키지의 계정 평생 무료 billable entity
LIFETIME_LIMIT: Final = 900  # 무료 한도보다 여유를 두고 멈춘다. 이 값은 절대 1,000 이상으로 올리지 않는다
CATEGORIES: Final = {"hotel": "HOTEL", "restaurant": "RESTAURANT", "attraction": "ATTRACTION"}
CATEGORY_ORDER: Final = ("attraction", "hotel", "restaurant")  # 관광지가 Tripadvisor에 등록돼 있을 가능성이 높다


class StopRun(RuntimeError):
    """과금 상한, 인증 오류, 호출 제한처럼 더 호출하면 안 되는 상황."""


# ---------- 호출과 과금 ----------


def load_usage() -> int:
    return json.loads(USAGE_PATH.read_text(encoding="utf-8"))["billable"] if USAGE_PATH.exists() else 0


@dataclass
class Budget:
    """이번 실행 상한과 계정 누적 상한을 함께 지킨다. 과금은 쓰자마자 파일에 남긴다."""

    max_billable: int
    used_before: int = field(default_factory=load_usage)
    billable: int = 0
    consecutive_failures: int = 0

    def reserve(self, cost: int) -> None:
        """호출하기 전에, 최악의 과금(cost)을 더해도 두 상한 안인지 확인한다."""
        if self.billable + cost > self.max_billable:
            raise StopRun(f"이번 실행 상한 {self.max_billable}건에 닿아 멈춥니다 (이번 실행 {self.billable}건)")
        if self.used_before + self.billable + cost > LIFETIME_LIMIT:
            raise StopRun(f"누적 상한 {LIFETIME_LIMIT}건(무료 {LIFETIME_FREE}건)에 닿아 멈춥니다 "
                          f"(누적 {self.used_before + self.billable}건)")

    def spend(self, cost: int) -> None:
        self.billable += cost
        USAGE_PATH.write_text(json.dumps({"billable": self.used_before + self.billable}), encoding="utf-8")

    def succeeded(self, cost: int) -> None:
        self.spend(cost)
        self.consecutive_failures = 0

    def failed(self, reserved: int) -> None:
        """실패한 호출이 과금됐는지 알 수 없으므로 예약한 만큼 썼다고 본다 (보수적으로)."""
        self.spend(reserved)
        self.consecutive_failures += 1
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            raise StopRun(f"연속 {MAX_CONSECUTIVE_FAILURES}번 실패해서 멈춥니다")


def call(method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
    res = requests.request(
        method,
        f"{BASE_URL}{path}",
        params={"version": 1, **(params or {})},
        json=body,
        headers={"X-API-Key": os.environ["TRIPADVISOR_API_KEY"], "Accept": "application/json"},
        timeout=30,
    )
    if 400 <= res.status_code < 500:
        # 잘못된 요청·키·권한·호출 제한은 다음 호출도 실패하므로 첫 번째에서 멈춘다.
        # 4xx는 과금되지 않고 처리되지도 않아서, 완료로 기록하지 않는다 (요청을 고친 뒤 다시 할 수 있다)
        raise StopRun(f"HTTP {res.status_code} {path}: {res.text[:300]}")
    res.raise_for_status()
    return res.json()


# ---------- 장소 매칭 ----------


def name_key(name: str) -> str:
    return re.sub(r"\(.*?\)|\s", "", name).lower()


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이의 거리 (하버사인 공식)."""
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def is_same_place(place: dict, location: dict) -> bool:
    """좌표가 있으면 300m 안인지, 없으면 이름이 같은지로 판단한다."""
    coords = location.get("coordinates") or {}
    if place["lat"] and coords.get("latitude") is not None:
        return distance_km(place["lat"], place["lng"], coords["latitude"], coords["longitude"]) <= MATCH_RADIUS_KM
    ours = name_key(place["name"])
    return any(ours and ours == name_key(name.get("value", "")) for name in location.get("names", []))


def search_location(place: dict, budget: Budget) -> int | None:
    budget.reserve(SEARCH_SIZE)
    time.sleep(SEARCH_INTERVAL)
    try:
        page = call("GET", "/catalog/locations/search", params={
            "query": re.sub(r"\(.*?\)", "", place["name"]).strip(),
            "category": CATEGORIES[place["category"]],
            "country_code": "KR",
            "geo_name": "Busan",
            "size": SEARCH_SIZE,
        })  # fmt: skip
    except requests.RequestException as e:
        budget.failed(SEARCH_SIZE)
        print(f"  ⚠️ 검색 실패 {place['name']}: {e}")
        return None
    results = [item["location"] for item in page.get("data", [])]
    budget.succeeded(len(results))
    match = next((location for location in results if is_same_place(place, location)), None)
    if match is None:
        print(f"    (검색 결과 {len(results)}개, 같은 장소 없음)")
    return match["id"] if match else None


# ---------- 허용 목록과 리뷰 ----------


def allow_locations(location_ids: list[int]) -> None:
    """리뷰를 받으려면 Location ID가 허용 목록에 있어야 한다. 이 호출은 과금되지 않는다."""
    if not location_ids:
        return
    try:
        call("POST", "/allowlist", body={"operation_type": "APPEND", "allowlist": location_ids})
    except requests.RequestException as e:  # 허용 목록 없이는 리뷰 호출이 모두 404라서 멈춘다
        raise StopRun(f"허용 목록 추가 실패: {e}")


def primary_korean(texts: list[dict]) -> str | None:
    """번역문이 아니라 한국어로 직접 쓴 원문만 쓴다."""
    for text in texts or []:
        if text.get("primary") and text.get("language") == "ko" and text.get("value", "").strip():
            return text["value"].strip()
    return None


def fetch_reviews(location_id: int, budget: Budget) -> list[dict] | None:
    budget.reserve(1)
    try:
        page = call("GET", f"/locations/{location_id}/reviews", params={"language": "ko", "size": REVIEW_PAGE_SIZE})
    except requests.RequestException as e:
        budget.failed(1)
        print(f"  ⚠️ 리뷰 실패 {location_id}: {e}")
        return None
    budget.succeeded(1)
    return page.get("data", [])


def to_record(place: dict, location_id: int, review: dict) -> dict | None:
    text = primary_korean(review.get("text"))
    if text is None:
        return None
    return {
        "review_id": f"ta_{review['id']}",
        "place_id": place["place_id"],
        "category": place["category"],
        "synthetic": False,
        "source": "tripadvisor",
        "tripadvisor_location_id": location_id,
        "review": text,
        "title": primary_korean(review.get("title")),
        "rating": review.get("rating"),
        "trip_type": review.get("trip_type"),
        "published": review.get("publish_ts"),
    }  # 작성자 정보(user)는 저장하지 않는다


# ---------- 진행 상태 ----------


def load_matches() -> dict[str, dict]:
    """place_id → {"location_id": int | None, "fetched": bool}"""
    return json.loads(MATCHES_PATH.read_text(encoding="utf-8")) if MATCHES_PATH.exists() else {}


def save_matches(matches: dict[str, dict]) -> None:
    MATCHES_PATH.write_text(json.dumps(matches, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def pick_candidates(places: dict[str, dict], splits: set[str], max_places: int) -> list[dict]:
    """정한 분할의 장소만, 관광지 → 호텔 → 식당, 같은 카테고리에선 TourAPI 출처(유명한 곳)를 먼저 고른다."""
    split = json.loads(SPLIT_PATH.read_text(encoding="utf-8")) if SPLIT_PATH.exists() else None
    if split is None:
        print("⚠️ out/split.json이 없어 분할과 상관없이 고릅니다. split_places.py를 먼저 실행하는 것이 좋습니다.")
    chosen = [place for place in places.values() if split is None or split.get(place["place_id"]) in splits]
    chosen.sort(key=lambda p: (CATEGORY_ORDER.index(p["category"]), "tourapi" not in p["sources"], p["place_id"]))
    return chosen[:max_places]


# ---------- 실행 ----------


def match_step(candidates: list[dict], matches: dict[str, dict], budget: Budget) -> None:
    todo = [place for place in candidates if place["place_id"] not in matches]
    print(f"\n[1/3] 장소 검색: {len(todo)}곳 (이미 찾은 {len(candidates) - len(todo)}곳은 건너뜀)")
    for place in todo:
        location_id = search_location(place, budget)
        matches[place["place_id"]] = {"location_id": location_id, "fetched": False}
        save_matches(matches)
        print(f"  {'✓' if location_id else '·'} {place['name']} → {location_id}")


def pending_locations(candidates: list[dict], matches: dict[str, dict]) -> dict[int, list[dict]]:
    """리뷰를 아직 안 받은 Location ID → 그 ID에 매칭된 장소들. 같은 ID는 한 번만 호출하려고 묶는다."""
    groups: dict[int, list[dict]] = {}
    for place in candidates:
        match = matches.get(place["place_id"], {})
        if match.get("location_id") and not match["fetched"]:
            groups.setdefault(match["location_id"], []).append(place)
    return groups


def mark_fetched(places: list[dict], matches: dict[str, dict]) -> None:
    for place in places:
        matches[place["place_id"]]["fetched"] = True  # 실패해도 다시 호출하지 않는다 (중복 과금 방지)
    save_matches(matches)


def reviews_step(candidates: list[dict], matches: dict[str, dict], budget: Budget) -> None:
    todo = pending_locations(candidates, matches)
    print(f"\n[2/3] 허용 목록 추가: {len(todo)}곳")
    allow_locations(list(todo))

    print(f"\n[3/3] 리뷰 받기: {len(todo)}곳")
    with open(REVIEWS_PATH, "a", encoding="utf-8") as out:
        for location_id, places in todo.items():
            reviews = fetch_reviews(location_id, budget)
            mark_fetched(places, matches)
            if reviews is None:
                continue
            place = places[0]  # 같은 곳이 출처별로 여러 번 있으면 첫 장소에 붙인다
            records = [r for r in (to_record(place, location_id, review) for review in reviews) if r]
            for record in records:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            print(f"  {place['name']}: 받은 {len(reviews)}건 중 한국어 원문 {len(records)}건")


def print_plan(candidates: list[dict], matches: dict[str, dict]) -> None:
    searches = sum(1 for place in candidates if place["place_id"] not in matches)
    unmatched = sum(1 for place in candidates if place["place_id"] not in matches)
    fetches = unmatched + len(pending_locations(candidates, matches))
    print(f"후보 {len(candidates)}곳: 검색 {searches}번 (최대 {searches * SEARCH_SIZE}건 과금) + 리뷰 최대 {fetches}번")
    used = load_usage()
    print(f"예상 최대 과금 {searches * SEARCH_SIZE + fetches}건 / 지금까지 누적 {used}건 / 누적 상한 {LIFETIME_LIMIT}건 (무료 {LIFETIME_FREE}건)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tripadvisor 실제 리뷰 수집 (평가용, 커밋 금지)")
    parser.add_argument("--places", type=Path, default=HERE / "out", help="places_*.json 폴더")
    parser.add_argument("--splits", nargs="+", default=["test"], help="대상 분할 (기본: test)")
    parser.add_argument("--max-places", type=int, default=60)
    parser.add_argument("--max-billable", type=int, default=300, help="이번 실행의 과금 상한")
    parser.add_argument("--dry-run", action="store_true", help="호출 없이 예상 과금만 출력")
    args = parser.parse_args()

    load_dotenv(HERE.parent.parent / ".env")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    candidates = pick_candidates(load_places(args.places), set(args.splits), args.max_places)
    matches = load_matches()
    print_plan(candidates, matches)
    if args.dry_run:
        return
    if not os.environ.get("TRIPADVISOR_API_KEY"):
        raise SystemExit(".env에 TRIPADVISOR_API_KEY가 없습니다.")

    budget = Budget(args.max_billable)
    try:
        match_step(candidates, matches, budget)
        reviews_step(candidates, matches, budget)
    except StopRun as e:
        print(f"\n⛔ {e}")
    print(f"\n이번 실행 과금 {budget.billable}건. 결과 → {REVIEWS_PATH} (커밋 금지)")


if __name__ == "__main__":
    main()
