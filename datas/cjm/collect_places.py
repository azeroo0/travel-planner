"""해운대구·기장군의 호텔·식당·관광지 장소 목록을 카테고리별 JSON으로 정리한다.

출처
  1. TourAPI (한국관광공사)           호텔·식당·관광지
  2. 부산광역시 명소 API              관광지
  3. 부산광역시 맛집 API              식당
  4. 해운대구·기장군 숙박업 현황 CSV  호텔

결과: out/places_{hotel,restaurant,attraction}.json
주차 가능 여부(facts.parking)는 TourAPI detailIntro2에서만 받는다. 장소 1곳당 1회 호출한다.

한 출처·요청·레코드가 실패해도 전체를 멈추지 않는다. 실패한 부분만 빼고 저장한 뒤,
무엇을 건너뛰었는지 마지막에 요약해서 보여준다.
"""

import csv
import hashlib
import json
import os
import re
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Final, Literal, TypedDict

import requests
from dotenv import load_dotenv

load_dotenv()

HERE: Final = Path(__file__).parent
OUT_DIR: Final = HERE / "out"

Category = Literal["hotel", "restaurant", "attraction"]
District = Literal["haeundae", "gijang"]
CATEGORIES: Final[tuple[Category, ...]] = ("hotel", "restaurant", "attraction")


class Place(TypedDict):
    place_id: str
    category: Category
    district: District
    name: str
    address: str
    lat: float | None
    lng: float | None
    phone: str | None
    sources: list[str]
    facts: dict[str, str | int]


# ---------- 실패 처리 ----------


class QuotaExceeded(RuntimeError):
    """하루 호출 한도 초과. 같은 API의 남은 요청도 모두 실패하므로 그 API는 더 부르지 않는다."""


# 건너뛰어도 되는 오류: API·네트워크 오류, 필드 누락, 값 형식 문제, 파일 문제.
# NameError 같은 코드 버그는 넣지 않아서, 버그는 그대로 드러나게 한다.
SKIPPABLE: Final = (RuntimeError, KeyError, ValueError, TypeError, OSError, csv.Error)

WARNINGS: list[str] = []


def warn(where: str, reason: object) -> None:
    WARNINGS.append(f"{where}: {reason}")


def describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"


def convert_each(
    raws: Iterable[dict],
    to_place: Callable[[dict], Place | None],
    where: str,
) -> list[Place]:
    """원본 레코드를 하나씩 Place로 바꾼다.

    형식이 잘못된 레코드는 경고를 남기고 건너뛰고, None(대상 지역 밖)은 조용히 버린다.
    """
    places: list[Place] = []
    for index, raw in enumerate(raws):
        try:
            place = to_place(raw)
        except SKIPPABLE as e:
            warn(f"{where} {index}번째 레코드", describe(e))
            continue
        if place is not None:
            places.append(place)
    return places


# ---------- 공통 유틸 ----------


def clean(text: object) -> str | None:
    """앞뒤 공백을 지우고, 빈 문자열이면 None으로 바꾼다."""
    if text is None:
        return None
    text = str(text).strip()
    return text or None


def clean_phone(text: object) -> str | None:
    phone = clean(text)
    return phone.replace(" ", "") if phone else None


def district_of(text: str) -> District | None:
    if "해운대구" in text:
        return "haeundae"
    if "기장군" in text:
        return "gijang"
    return None


def pick_facts(item: dict, fields: dict[str, str]) -> dict[str, str | int]:
    """원본 필드 이름을 우리 필드 이름으로 바꾸면서 빈 값은 버린다."""
    facts: dict[str, str | int] = {}
    for source_key, our_key in fields.items():
        value = clean(item.get(source_key))
        if value:
            facts[our_key] = value
    return facts


def get_json(url: str, params: dict) -> dict:
    """GET 요청 후 JSON을 돌려준다.

    requests의 기본 오류 메시지에는 URL(API 키 포함)이 들어가므로, 직접 만든 메시지로 바꿔 던진다.
    """
    try:
        res = requests.get(url, params=params, timeout=10)
    except requests.RequestException as e:
        raise RuntimeError(f"요청 실패 ({type(e).__name__})") from None
    if res.status_code == 429:
        raise QuotaExceeded("하루 호출 한도 초과 (HTTP 429)")
    if not res.ok:
        raise RuntimeError(f"HTTP {res.status_code}")
    try:
        return res.json()
    except ValueError:
        raise RuntimeError("응답이 JSON이 아님") from None


# ---------- 출처 1: TourAPI ----------

# (카테고리, contentTypeId): 관광지 12, 문화시설 14, 레포츠 28은 모두 attraction
TOUR_CONTENT_TYPES: Final[list[tuple[Category, int]]] = [
    ("hotel", 32),
    ("restaurant", 39),
    ("attraction", 12),
    ("attraction", 14),
    ("attraction", 28),
]
SIGUNGU: Final[dict[District, str]] = {"haeundae": "350", "gijang": "710"}
ROWS_PER_PAGE: Final = 100
MAX_PAGES: Final = 20  # 무한 루프 안전장치: 해운대·기장은 조합당 2페이지면 충분


# contentTypeId별로 detailIntro2의 주차 필드 이름이 다르다
PARKING_FIELDS: Final[dict[int, str]] = {
    32: "parkinglodging",
    39: "parkingfood",
    12: "parking",
    14: "parkingculture",
    28: "parkingleports",
}


def tourapi_get(operation: str, params: dict) -> dict:
    """TourAPI 공통 파라미터를 붙여 요청하고, 결과 코드를 확인한 뒤 body를 돌려준다."""
    data = get_json(
        f"{os.environ['TOUR_API_BASE_URL']}/{operation}",
        {
            "serviceKey": os.environ["TOUR_API_KEY"],
            "MobileOS": "ETC",
            "MobileApp": "TripFit",
            "_type": "json",
            **params,
        },
    )
    header = data["response"]["header"]
    if header["resultCode"] != "0000":
        raise RuntimeError(f"TourAPI 오류: {header['resultMsg']}")
    return data["response"]["body"]


def fetch_tourapi_page(content_type: int, sigungu: str, page: int) -> dict:
    """areaBasedList2 한 페이지를 요청한다."""
    return tourapi_get(
        "areaBasedList2",
        {
            "lDongRegnCd": "26",  # 부산광역시
            "lDongSignguCd": sigungu,
            "contentTypeId": content_type,
            "numOfRows": ROWS_PER_PAGE,
            "pageNo": page,
        },
    )


def fetch_tourapi_intro(content_id: str, content_type: int) -> dict:
    """detailIntro2로 장소 한 곳의 소개 정보(주차, 영업시간 등)를 받는다."""
    body = tourapi_get("detailIntro2", {"contentId": content_id, "contentTypeId": content_type})
    items = body["items"]["item"] if body["items"] else []
    if not items:
        raise RuntimeError("소개 정보가 비어 있음")
    return items[0]


def iter_tourapi_items(content_type: int, sigungu: str) -> Iterator[dict]:
    """모든 페이지를 차례로 받아 item을 하나씩 내보낸다."""
    for page in range(1, MAX_PAGES + 1):
        body = fetch_tourapi_page(content_type, sigungu, page)
        items = body["items"]["item"] if body["items"] else []
        yield from items

        # body["numOfRows"]는 "이번에 받은 개수"라서 종료 조건에 쓰면 안 된다
        if not items or page * ROWS_PER_PAGE >= body["totalCount"]:
            return
        time.sleep(0.2)
    raise RuntimeError(f"{MAX_PAGES}페이지를 넘었습니다")


def fetch_tourapi_items(content_type: int, sigungu: str, where: str) -> list[dict]:
    """한 조합의 item을 모두 받는다. 도중에 실패하면 그때까지 받은 것만 돌려준다."""
    items: list[dict] = []
    try:
        for item in iter_tourapi_items(content_type, sigungu):
            items.append(item)
    except QuotaExceeded:
        raise  # 한도 초과는 load_tourapi가 받아서 TourAPI 전체를 멈춘다
    except SKIPPABLE as e:
        warn(where, f"{describe(e)} → {len(items)}건까지만 사용")
    return items


def tourapi_to_place(item: dict, category: Category, district: District) -> Place:
    return {
        "place_id": f"tourapi:{item['contentid']}",
        "category": category,
        "district": district,
        "name": item["title"].strip(),
        "address": item["addr1"].strip(),
        "lat": float(item["mapy"]) if item["mapy"] else None,
        "lng": float(item["mapx"]) if item["mapx"] else None,
        "phone": clean_phone(item["tel"]),
        "sources": ["tourapi"],
        "facts": pick_facts(item, {"contenttypeid": "content_type_id", "lclsSystm3": "class_code"}),
    }


def load_tourapi() -> list[Place]:
    places: list[Place] = []
    for (category, content_type), (district, sigungu) in product(TOUR_CONTENT_TYPES, SIGUNGU.items()):
        where = f"TourAPI {category}({content_type})/{district}"
        try:
            items = fetch_tourapi_items(content_type, sigungu, where)
        except QuotaExceeded as e:
            warn("TourAPI", f"{e} → 남은 TourAPI 요청을 모두 건너뜀")
            break
        places += convert_each(items, lambda item: tourapi_to_place(item, category, district), where)
    return places


def add_tourapi_parking(places: list[Place]) -> None:
    """TourAPI 장소마다 detailIntro2를 불러 facts["parking"]을 채운다. 장소 1곳당 1회 호출한다."""
    for place in places:
        content_type = int(place["facts"]["content_type_id"])
        field = PARKING_FIELDS[content_type]
        where = f"TourAPI 주차 정보 {place['place_id']}"
        try:
            intro = fetch_tourapi_intro(place["place_id"].removeprefix("tourapi:"), content_type)
        except QuotaExceeded as e:
            warn("TourAPI 주차 정보", f"{e} → 남은 장소는 주차 정보 없이 저장")
            return
        except SKIPPABLE as e:
            warn(where, describe(e))
            continue

        if field not in intro:  # 필드 이름이 바뀌었거나 잘못됐으면 여기서 드러난다
            warn(where, f"응답에 {field} 필드가 없음")
            continue
        parking = clean(intro[field])
        if parking:
            place["facts"]["parking"] = parking
        time.sleep(0.1)


# ---------- 출처 2·3: 부산광역시 명소·맛집 API ----------


@dataclass(frozen=True)
class BusanApi:
    source: str  # place_id 접두어이자 sources 값
    category: Category
    url_env: str
    key_env: str
    root: str  # 응답 JSON 최상위 키
    fact_fields: dict[str, str]  # 원본 필드 → facts 키


BUSAN_APIS: Final = [
    BusanApi(
        source="busan_attraction",
        category="attraction",
        url_env="ATTRACTION_URL",
        key_env="ATTRACTION_API_KEY",
        root="getAttractionKr",
        fact_fields={
            "USAGE_DAY_WEEK_AND_TIME": "hours",
            "HLDY_INFO": "holiday",
            "USAGE_AMOUNT": "fee",
            "TRFC_INFO": "transport",
            "MIDDLE_SIZE_RM1": "facilities",
        },
    ),
    BusanApi(
        source="busan_food",
        category="restaurant",
        url_env="POPULAR_RESTAURANT_URL",
        key_env="POPULAR_RESTAURANT_API_KEY",
        root="getFoodKr",
        fact_fields={"RPRSNTV_MENU": "menu", "USAGE_DAY_WEEK_AND_TIME": "hours"},
    ),
]


def fetch_busan_items(api: BusanApi) -> list[dict]:
    """부산 전체 항목을 한 번에 받는다. 구 단위 필터 파라미터가 없어서 받은 뒤 거른다."""
    data = get_json(
        os.environ[api.url_env],
        {
            "ServiceKey": os.environ[api.key_env],
            "numOfRows": 1000,  # 맛집은 437건이라 300이면 잘린다
            "pageNo": 1,
            "resultType": "json",
        },
    )
    body = data[api.root]
    if body["header"]["code"] != "00":
        raise RuntimeError(f"API 오류: {body['header']['message']}")

    items = body["item"]
    if len(items) < body["totalCount"]:
        warn(api.source, f"{body['totalCount']}건 중 {len(items)}건만 받음 → 받은 것만 사용")
    return items


def busan_to_place(item: dict, api: BusanApi) -> Place | None:
    district = district_of(item["GUGUN_NM"])
    if district is None:
        return None

    address = item["ADDR1"].strip()
    if not address.startswith("부산"):  # 맛집 API는 "강서구 ..."처럼 시 이름이 빠져 있다
        address = f"부산광역시 {address}"
    return {
        "place_id": f"{api.source}:{item['UC_SEQ']}",
        "category": api.category,
        "district": district,
        "name": item["MAIN_TITLE"].strip(),
        "address": address,
        "lat": item["LAT"] or None,
        "lng": item["LNG"] or None,
        "phone": clean_phone(item["CNTCT_TEL"]),
        "sources": [api.source],
        "facts": pick_facts(item, api.fact_fields),
    }


def load_busan_api(api: BusanApi) -> list[Place]:
    try:
        items = fetch_busan_items(api)
    except SKIPPABLE as e:
        warn(api.source, f"{describe(e)} → 이 출처 전체를 건너뜀")
        return []
    return convert_each(items, lambda item: busan_to_place(item, api), api.source)


# ---------- 출처 4: 숙박업 현황 CSV ----------

# 해운대구 파일은 CP949, 기장군 파일은 UTF-8이다. 열 구성도 서로 조금 다르다.
LODGING_CSVS: Final[list[tuple[Path, str]]] = [
    (HERE / "부산광역시 해운대구_숙박업 현황_20260615.csv", "cp949"),
    (HERE / "부산광역시_기장군_숙박업소현황_20260623.csv", "utf-8-sig"),
]


def read_csv(path: Path, encoding: str) -> list[dict[str, str]]:
    with open(path, encoding=encoding, newline="") as f:
        return list(csv.DictReader(f))


def lodging_to_place(row: dict[str, str]) -> Place | None:
    name = row["업소명"].strip()
    address = row["영업소 주소(도로명)"].strip()
    district = district_of(address)
    if district is None:
        return None

    facts = pick_facts(row, {"업종명": "lodging_type"})  # 기장군 파일에만 있다
    rooms = (row.get("객실수") or "").strip()  # 해운대구 파일에만 있다
    if rooms.isdigit():
        facts["rooms"] = int(rooms)

    # CSV에는 고정 ID가 없어서, 이름과 주소로 다시 실행해도 같은 ID를 만든다
    digest = hashlib.sha1(f"{name}|{address}".encode()).hexdigest()[:10]
    return {
        "place_id": f"lodging_csv:{digest}",
        "category": "hotel",
        "district": district,
        "name": name,
        "address": address,
        "lat": None,
        "lng": None,
        "phone": clean_phone(row["소재지전화"]),
        "sources": ["lodging_csv"],
        "facts": facts,
    }


def load_lodging_csvs() -> list[Place]:
    places: list[Place] = []
    for path, encoding in LODGING_CSVS:
        try:
            rows = read_csv(path, encoding)
        except SKIPPABLE as e:
            warn(path.name, f"{describe(e)} → 이 파일 전체를 건너뜀")
            continue
        places += convert_each(rows, lodging_to_place, path.name)
    return places


# ---------- 중복 제거 ----------


def normalize(text: str) -> str:
    """비교용으로 공백·괄호·구두점을 지우고 소문자로 바꾼다."""
    return re.sub(r"[\s()\[\]·,.\-]", "", text).lower()


def dedup_key(place: Place) -> tuple[str, str, str]:
    # "해운대로 620, 해운대 롯데캐슬 (우동)" → "해운대로 620"처럼 도로명 주소 앞부분만 쓴다
    base_address = re.split(r",|\(", place["address"])[0]
    return (place["category"], normalize(place["name"]), normalize(base_address))


def merge_into(kept: Place, duplicate: Place) -> None:
    """kept는 그대로 두고, duplicate의 출처와 facts 중 kept에 없는 것만 보탠다."""
    for source in duplicate["sources"]:
        if source not in kept["sources"]:
            kept["sources"].append(source)
    for key, value in duplicate["facts"].items():
        kept["facts"].setdefault(key, value)


def dedup(places: list[Place]) -> list[Place]:
    """같은 장소는 먼저 들어온 레코드를 남긴다. 그래서 입력 순서가 곧 출처 우선순위다."""
    merged: dict[tuple[str, str, str], Place] = {}
    for place in places:
        key = dedup_key(place)
        if key in merged:
            merge_into(merged[key], place)
        else:
            merged[key] = place
    return list(merged.values())


# ---------- 저장·요약 ----------


def write_by_category(places: list[Place]) -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for category in CATEGORIES:
        rows = sorted(
            (p for p in places if p["category"] == category),
            key=lambda p: p["place_id"],
        )
        out_path = OUT_DIR / f"places_{category}.json"
        out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{category}: {len(rows)}건 → {out_path.name}")


def print_warnings() -> None:
    if not WARNINGS:
        print("\n경고 없음")
        return
    print(f"\n⚠️  경고 {len(WARNINGS)}건 (해당 부분은 빼고 저장함)")
    for message in WARNINGS:
        print(f"  - {message}")


# ---------- 실행 ----------


def main() -> None:
    # 좌표가 있는 API 출처를 앞에 둬서, 중복일 때 API 레코드가 남도록 한다
    places = load_tourapi()
    add_tourapi_parking(places)  # 주차 정보는 TourAPI에만 있다
    for api in BUSAN_APIS:
        places += load_busan_api(api)
    places += load_lodging_csvs()

    if places:
        unique = dedup(places)
        print(f"수집 {len(places)}건 → 중복 제거 후 {len(unique)}건")
        write_by_category(unique)
    else:
        print("수집된 데이터가 없어 저장하지 않습니다.")  # 기존 결과 파일을 빈 파일로 덮어쓰지 않는다

    print_warnings()


if __name__ == "__main__":
    main()
