"""팀원 폴더의 원본 JSON을 공통 형식으로 바꿔 datas/<이니셜>/out/ 에 쓴다.

원본은 datas/<이니셜>/in/ 에 두는 것을 권한다 (in/·out/ 모두 커밋하지 않는다).
out/ 밖이면 하위 폴더 어디에 있어도 읽는다.
원본 JSON은 팀원마다 모양이 달라도 된다. 흔히 쓰는 필드 이름을 알아서 맞춰 읽는다.
  - 파일 하나가 장소 목록([...])이어도, {"places": [...]}처럼 목록을 품은 객체여도 된다.
  - 장소 필드: place_id / location_id / contentid, name / title, category / contenttypeid,
    address / addr1, lat / latitude / mapy, lng / longitude / mapx, phone / tel,
    지역: district / regions / region (예: "해운대구", "광안리")
  - 장소 안에 reviews: [...]가 있으면 실제 리뷰로 함께 옮긴다 (text / review / content).

결과 (공통 형식, schema.Place):
  datas/<이니셜>/out/places_{hotel,restaurant,attraction}.json
  datas/<이니셜>/out/real_reviews.jsonl        실제 리뷰 (synthetic: false)
out/ 아래 파일과 cache 폴더는 원본으로 읽지 않는다. 원본이 없는 팀원은 건너뛰고 out/을 건드리지 않는다.

사용법:
  uv run python datas/common/normalize.py lkh     # 한 명
  uv run python datas/common/normalize.py         # 모든 팀원
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Final, Iterator

from paths import member_dir, members
from schema import CATEGORIES, DISTRICT_NAMES_KO, district_of

# 필드 이름 후보. 앞에 있는 것부터 찾는다
ID_FIELDS: Final = ("place_id", "location_id", "contentid", "content_id", "UC_SEQ", "id")
NAME_FIELDS: Final = ("name", "title", "MAIN_TITLE", "place_name")
CATEGORY_FIELDS: Final = ("category", "contenttypeid", "content_type_id", "type")
ADDRESS_FIELDS: Final = ("address", "addr1", "ADDR1", "road_address")
LAT_FIELDS: Final = ("lat", "latitude", "mapy", "LAT")
LNG_FIELDS: Final = ("lng", "lon", "longitude", "mapx", "LNG")
PHONE_FIELDS: Final = ("phone", "tel", "CNTCT_TEL")
REGION_FIELDS: Final = ("district", "regions", "region", "GUGUN_NM")
REVIEW_TEXT_FIELDS: Final = ("text", "review", "content", "body")
MAPPED: Final = {*ID_FIELDS, *NAME_FIELDS, *CATEGORY_FIELDS, *ADDRESS_FIELDS, *LAT_FIELDS, *LNG_FIELDS,
                 *PHONE_FIELDS, *REGION_FIELDS, "reviews", "facts", "sources"}  # fmt: skip

# 어떤 ID 필드였는지로 출처를 정한다. place_id는 이미 "<출처>:<ID>" 형식이라고 본다
SOURCE_BY_ID_FIELD: Final = {"location_id": "tripadvisor", "contentid": "tourapi", "content_id": "tourapi", "UC_SEQ": "busan"}

CATEGORY_WORDS: Final = {
    "hotel": {"hotel", "hotels", "숙박", "숙소", "호텔", "32", "accommodation", "lodging"},
    "restaurant": {"restaurant", "restaurants", "음식점", "식당", "맛집", "39", "food"},
    "attraction": {"attraction", "attractions", "관광지", "명소", "12", "14", "28"},
}

# 주소가 없을 때 쓰는 동네 이름 → 구·군
NEIGHBORHOODS: Final = {
    "광안": "suyeong", "민락": "suyeong", "수영": "suyeong",
    "해운대": "haeundae", "센텀": "haeundae", "송정": "haeundae", "달맞이": "haeundae", "청사포": "haeundae", "해리단길": "haeundae",
    "기장": "gijang", "오시리아": "gijang", "일광": "gijang", "정관": "gijang",
    "서면": "busanjin", "전포": "busanjin", "부산진": "busanjin",
    "남포": "jung", "광복": "jung", "자갈치": "jung", "중앙동": "jung",
    "영도": "yeongdo", "태종대": "yeongdo",
    "송도": "seo", "암남": "seo",
    "다대포": "saha", "감천": "saha",
    "동래": "dongnae", "온천장": "dongnae",
    "부산역": "dong", "초량": "dong",
    "용호": "nam", "이기대": "nam", "대연": "nam", "경성대": "nam",
    "연산": "yeonje", "사상": "sasang", "금정": "geumjeong", "범어사": "geumjeong", "강서": "gangseo", "화명": "buk",
}  # fmt: skip


# ---------- 원본 읽기 ----------


def source_files(member: str) -> list[Path]:
    root = member_dir(member)
    return sorted(p for p in root.rglob("*.json") if "out" not in p.relative_to(root).parts and "cache" not in p.parts)


def records_in(data: object) -> Iterator[dict]:
    """목록이면 원소를, 객체면 안에 든 목록의 원소를(없으면 객체 자체를) 돌려준다."""
    if isinstance(data, list):
        yield from (item for item in data if isinstance(item, dict))
    elif isinstance(data, dict):
        lists = [value for value in data.values() if isinstance(value, list) and value and isinstance(value[0], dict)]
        if lists:
            for items in lists:
                yield from records_in(items)
        else:
            yield data


# ---------- 필드 맞추기 ----------


def first(record: dict, fields: tuple[str, ...]) -> tuple[str | None, object]:
    """후보 필드 중 값이 있는 첫 필드의 (이름, 값)."""
    for field in fields:
        value = record.get(field)
        if value not in (None, "", []):
            return field, value
    return None, None


def to_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def to_category(value: object) -> str | None:
    word = str(value).strip().lower()
    return next((category for category, words in CATEGORY_WORDS.items() if word in words), None)


def region_texts(record: dict) -> list[str]:
    texts: list[str] = []
    for field in REGION_FIELDS:
        value = record.get(field)
        texts += [str(v) for v in value] if isinstance(value, list) else [str(value)] if value else []
    return texts


def to_district(record: dict, address: str) -> str | None:
    """주소 → 지역 필드(구·군 이름이나 영문 id) → 동네 이름 순서로 찾는다."""
    found = district_of(address)
    for text in region_texts(record):
        if found:
            break
        found = text if text in DISTRICT_NAMES_KO else district_of(text)
        found = found or next((d for hint, d in NEIGHBORHOODS.items() if hint in text), None)
    return found


def to_place_id(record: dict, member: str) -> tuple[str | None, str]:
    """(place_id, 출처). 출처를 앞에 붙여 팀 전체에서 겹치지 않게 한다."""
    field, value = first(record, ID_FIELDS)
    if value is None:
        return None, member
    if field == "place_id" and ":" in str(value):
        return str(value), str(value).split(":", 1)[0]
    source = SOURCE_BY_ID_FIELD.get(field or "", member)
    return f"{source}:{value}", source


def to_facts(record: dict) -> dict[str, str | int]:
    """facts가 있으면 그대로, 없으면 나머지 단순 값 필드를 사실로 둔다."""
    if isinstance(record.get("facts"), dict):
        return record["facts"]
    return {key: value for key, value in record.items()
            if key not in MAPPED and isinstance(value, (str, int, float, bool)) and value != ""}  # fmt: skip


def to_place(record: dict, member: str) -> tuple[dict | None, str]:
    """(장소, 문제). 장소를 만들 수 없으면 (None, 이유)."""
    place_id, source = to_place_id(record, member)
    _, name = first(record, NAME_FIELDS)
    _, raw_category = first(record, CATEGORY_FIELDS)
    category = to_category(raw_category) if raw_category is not None else None
    if not place_id or not name or not category:
        return None, f"ID·이름·카테고리 중 없는 것이 있음 (카테고리 원본: {raw_category!r})"

    _, address = first(record, ADDRESS_FIELDS)
    address = str(address or "")
    _, phone = first(record, PHONE_FIELDS)
    return {
        "place_id": place_id,
        "category": category,
        "district": to_district(record, address),
        "name": str(name).strip(),
        "address": address,
        "lat": to_float(first(record, LAT_FIELDS)[1]),
        "lng": to_float(first(record, LNG_FIELDS)[1]),
        "phone": str(phone) if phone else None,
        "sources": record.get("sources") or [source],
        "facts": to_facts(record),
    }, ""


def to_review(review: dict, place: dict, index: int) -> dict | None:
    _, text = first(review, REVIEW_TEXT_FIELDS)
    if not isinstance(text, str) or not text.strip():
        return None
    source = place["sources"][0]
    review_id = review.get("review_id") or review.get("id")
    status = str(review.get("translation_status", ""))
    return {
        "review_id": f"{source}_{review_id}" if review_id else f"{place['place_id']}#{index}",
        "place_id": place["place_id"],
        "category": place["category"],
        "synthetic": False,
        "source": source,
        "review": text.strip(),
        "title": review.get("title"),
        "rating": review.get("rating"),
        "trip_type": review.get("trip_type"),
        "published": review.get("published_date") or review.get("publish_ts") or review.get("date"),
        "language": review.get("language"),
        "translated": "translat" in status or bool(review.get("source_language") not in (None, review.get("language"))),
    }


# ---------- 한 팀원 처리 ----------


def normalize_member(member: str) -> None:
    files = source_files(member)
    if not files:
        print(f"[{member}] 원본 JSON이 없어 건너뜁니다 (out/은 그대로 둡니다)")
        return

    places: dict[str, dict] = {}
    reviews: dict[str, dict] = {}
    problems: Counter[str] = Counter()
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:  # 한 파일이 깨져도 나머지는 처리한다
            problems[f"{path.name}: 읽을 수 없음 ({type(e).__name__})"] += 1
            continue
        for record in records_in(data):
            place, problem = to_place(record, member)
            if place is None:
                problems[f"{path.name}: {problem}"] += 1
                continue
            places.setdefault(place["place_id"], place)  # 같은 장소가 여러 파일에 있으면 처음 것을 쓴다
            for index, raw in enumerate(record.get("reviews") or []):
                review = to_review(raw, places[place["place_id"]], index) if isinstance(raw, dict) else None
                if review:
                    reviews[review["review_id"]] = review

    write_member(member, list(places.values()), list(reviews.values()))
    print_summary(member, files, list(places.values()), list(reviews.values()), problems)


def write_member(member: str, places: list[dict], reviews: list[dict]) -> None:
    out = member_dir(member) / "out"
    out.mkdir(exist_ok=True)
    by_category: dict[str, list[dict]] = defaultdict(list)
    for place in places:
        by_category[place["category"]].append(place)
    for category in CATEGORIES:
        path = out / f"places_{category}.json"
        path.write_text(json.dumps(by_category[category], ensure_ascii=False, indent=2), encoding="utf-8")
    if reviews:
        with open(out / "real_reviews.jsonl", "w", encoding="utf-8") as f:
            for review in reviews:
                f.write(json.dumps(review, ensure_ascii=False) + "\n")


def print_summary(member: str, files: list[Path], places: list[dict], reviews: list[dict], problems: Counter) -> None:
    categories = Counter(place["category"] for place in places)
    districts = Counter(place["district"] or "알 수 없음" for place in places)
    print(f"[{member}] 원본 {len(files)}개 파일 → 장소 {len(places)}곳 {dict(categories)}, 실제 리뷰 {len(reviews)}건")
    print(f"  지역: {dict(districts.most_common())}")
    translated = sum(1 for review in reviews if review["translated"])
    if translated:
        print(f"  번역된 리뷰 {translated}건 (translated: true로 표시)")
    for problem, count in problems.most_common(10):
        print(f"  ⚠️ {count}건 건너뜀 — {problem}")


def main() -> None:
    parser = argparse.ArgumentParser(description="팀원 원본 JSON → 공통 형식 (datas/<이니셜>/out/)")
    parser.add_argument("members", nargs="*", help="팀원 이니셜. 없으면 모든 팀원")
    args = parser.parse_args()
    for member in args.members or members():
        normalize_member(member)


if __name__ == "__main__":
    main()
