"""장소 정보를 조건으로 로컬 gemma4(Ollama)에게 합성 리뷰를 쓰게 한다.

라벨은 달지 않는다. 라벨은 다음 단계에서 리뷰만 보고 따로 단다.
어떤 aspect를 어떤 상태로 넣으라고 시켰는지(생성 계획)는 레코드의 generation 필드에 남겨,
나중에 라벨과 비교하는 분석에 쓴다.

사용법 (보통은 make_silver.py가 대신 부른다):
  uv run python datas/common/generate_reviews.py --member cjm --category restaurant --count 20 \\
      --out datas/cjm/out/generated/pilot_restaurant.jsonl

같은 --seed로 다시 실행하면 이미 만든 review_id는 건너뛰고 이어서 만든다.
"""

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import requests

from label_check import is_broken
from ollama_client import DEFAULT_MODEL, chat_json, check_ollama
from paths import load_places
from schema import (
    ASPECT_NAMES_KO,
    ATTRIBUTES,
    CATEGORY_NAMES_KO,
    DISTRICT_NAMES_KO,
    TRAVELER_CONTEXTS,
    TRAVELER_NAMES_KO,
    VALUE_NAMES_KO,
)

TEMPERATURE: Final = 0.9  # 높게 둬서 리뷰 문장이 다양하게 나오게 한다
MAX_ATTEMPTS: Final = 3  # 텍스트가 깨지면 seed를 바꿔 다시 만든다
RETRY_SEED_STEP: Final = 1_000_000_000  # 다시 만들 때 seed에 더한다. 계획 seed와 겹치지 않을 만큼 크게

# 프롬프트에 보여줄 장소 정보. 여기에 없는 facts(content_type_id 등 내부 코드)는 보여주지 않는다.
FACT_NAMES_KO: Final[dict[str, str]] = {
    "menu": "대표 메뉴",
    "menu_more": "그 밖의 메뉴",
    "hours": "이용 시간",
    "holiday": "휴무일",
    "fee": "요금",
    "parking": "주차",
    "parking_fee": "주차 요금",
    "facilities": "편의·부대시설",
    "transport": "교통",
    "lodging_type": "숙박 업종",
    "rooms": "객실 수",
    "room_type": "객실 유형",
    "checkin": "체크인",
    "checkout": "체크아웃",
    "kids_facility": "어린이 놀이방",
    "takeout": "포장",
    "baby_carriage": "유모차 대여",
    "experience": "체험 안내",
    "age_range": "체험 가능 연령",
}

# 리뷰 길이와 말투를 섞어 문체가 한쪽으로 몰리지 않게 한다
LENGTHS: Final = ("짧게 1~2문장", "3~4문장", "5~6문장으로 자세하게")
TONES: Final = ("존댓말", "편한 반말", "존댓말에 이모티콘을 조금 섞어서")
ASPECT_COUNTS: Final = (1, 2, 2, 3, 3, 4)  # 리뷰 하나에 담을 aspect 수. 2~3개가 가장 흔하게

REVIEW_SCHEMA: Final = {
    "type": "object",
    "properties": {"review": {"type": "string"}},
    "required": ["review"],
}


@dataclass(frozen=True)
class ReviewPlan:
    review_id: str
    place: dict
    traveler: str | None  # None이면 동행을 언급하지 않게 한다
    aspects: list[tuple[str, str]]  # (aspect, attribute)
    length: str
    tone: str
    seed: int


# ---------- 생성 계획 ----------


def places_of(member: str, category: str) -> list[dict]:
    """팀원 한 명의 장소 중 한 카테고리. 파일에 적힌 순서를 지켜서 같은 seed면 같은 계획이 나온다."""
    places = [place for place in load_places(member).values() if place["category"] == category]
    if not places:
        raise SystemExit(f"{member}의 {category} 장소가 없습니다. datas/{member}/out/places_{category}.json을 확인하세요.")
    return places


def assign_places(places: list[dict], count: int, max_per_place: int, rng: random.Random) -> list[dict]:
    """장소를 섞은 뒤 돌아가며 배정한다. 그래서 장소별 리뷰 수 차이는 최대 1이다."""
    if len(places) * max_per_place < count:
        raise SystemExit(
            f"장소 {len(places)}곳 × 장소당 최대 {max_per_place}건으로는 {count}건을 만들 수 없습니다. "
            "--max-per-place를 늘리거나 --count를 줄이세요."
        )
    order = places[:]
    rng.shuffle(order)
    return [order[i % len(order)] for i in range(count)]


def make_plan(review_id: str, place: dict, rng: random.Random, seed: int) -> ReviewPlan:
    table = ATTRIBUTES[place["category"]]
    aspect_names = rng.sample(sorted(table), rng.choice(ASPECT_COUNTS))
    travelers = sorted(TRAVELER_CONTEXTS) + [None, None]  # 약 30%는 동행 언급 없음
    return ReviewPlan(
        review_id=review_id,
        place=place,
        traveler=rng.choice(travelers),
        aspects=[(name, rng.choice(table[name])) for name in aspect_names],
        length=rng.choice(LENGTHS),
        tone=rng.choice(TONES),
        seed=seed,
    )


def make_plans(places: list[dict], category: str, count: int, max_per_place: int, seed: int) -> list[ReviewPlan]:
    """같은 seed면 항상 같은 계획이 나온다. 이어서 실행할 때도 계획이 바뀌지 않는다."""
    rng = random.Random(seed)
    assigned = assign_places(places, count, max_per_place, rng)
    return [
        make_plan(f"syn_{category}_{seed}_{index:05d}", place, rng, seed * 100_000 + index)
        for index, place in enumerate(assigned)
    ]


# ---------- 프롬프트 ----------


def describe_place(place: dict) -> list[str]:
    lines = [
        f"- 이름: {place['name']}",
        f"- 종류: {CATEGORY_NAMES_KO[place['category']]}",
        f"- 주소: {place['address']}",
    ]
    for key, label in FACT_NAMES_KO.items():
        if key in place["facts"]:
            lines.append(f"- {label}: {place['facts'][key]}")
    return lines


def describe_experience(plan: ReviewPlan) -> list[str]:
    lines = [f"- {ASPECT_NAMES_KO[name]}: {VALUE_NAMES_KO[value]}" for name, value in plan.aspects]
    if plan.traveler:
        lines.append(f"- 동행: {TRAVELER_NAMES_KO[plan.traveler]} (리뷰에 누구와 갔는지 드러나게)")
    else:
        lines.append("- 동행: 누구와 갔는지는 언급하지 않음")
    return lines


def region_of(place: dict) -> str:
    district = DISTRICT_NAMES_KO.get(place.get("district") or "")
    return f"부산 {district}" if district else "부산"


def build_prompt(plan: ReviewPlan) -> str:
    return "\n".join([
        f"당신은 {region_of(plan.place)} 여행을 다녀온 한국인 여행자입니다.",
        "아래 장소에 대한 솔직한 방문 리뷰를 한국어로 한 편 써 주세요.",
        "",
        "[장소]",
        *describe_place(plan.place),
        "",
        "[리뷰에 담을 경험]",
        *describe_experience(plan),
        "",
        "[작성 규칙]",
        f"- 길이: {plan.length}",
        f"- 말투: {plan.tone}",
        "- 각 경험은 실제 여행자가 쓰는 일상적인 말로 풀어 씁니다. 항목 이름은 내용을 알려주는 메모입니다.",
        "  예) '걷기 부담: 높음' → '한참 걸어야 해서 다리가 아팠어요'",
        "  예) '신선도: 신선하지 않음' → '회가 좀 물컹하고 비린 맛이 났어요'",
        "  예) '음식 양: 많음' → '둘이서 다 못 먹을 만큼 푸짐했어요'",
        "- '보통'인 경험은 '보통이에요', '무난했어요'처럼 그대로 드러냅니다.",
        "- 메뉴·시설 이름은 장소 정보에 있는 것만 씁니다.",
        "- 제목, 별점, 해시태그 없이 리뷰 본문만 씁니다.",
        '- {"review": "리뷰 본문"} 형식의 JSON으로만 답합니다.',
    ])  # fmt: skip


# ---------- 생성 호출 ----------


def write_review(prompt: str, model: str, seed: int) -> tuple[str, int]:
    """(리뷰, 실제로 쓴 seed). 텍스트가 깨지면 seed를 바꿔 MAX_ATTEMPTS번까지 다시 만든다."""
    for attempt in range(MAX_ATTEMPTS):
        used_seed = seed + attempt * RETRY_SEED_STEP
        answer = chat_json(prompt, model=model, schema=REVIEW_SCHEMA, temperature=TEMPERATURE, seed=used_seed)
        review = answer["review"].strip()
        if not review:
            raise ValueError("빈 리뷰")
        if not is_broken(review):
            return review, used_seed
    raise ValueError(f"{MAX_ATTEMPTS}번 모두 텍스트가 깨짐 (<0x..>)")


# ---------- 저장 ----------


def to_record(plan: ReviewPlan, review: str, model: str, seed: int) -> dict:
    return {
        "review_id": plan.review_id,
        "place_id": plan.place["place_id"],
        "category": plan.place["category"],
        "synthetic": True,
        "review": review,
        "generation": {
            "model": model,
            "seed": seed,  # 실제로 쓴 seed. 다시 만든 경우 계획 seed + RETRY_SEED_STEP의 배수
            "traveler_context": plan.traveler,
            "aspects": [{"category": name, "attribute": value} for name, value in plan.aspects],
            "length": plan.length,
            "tone": plan.tone,
        },
    }


def load_done_ids(out_path: Path) -> set[str]:
    if not out_path.exists():
        return set()
    with open(out_path, encoding="utf-8") as f:
        return {json.loads(line)["review_id"] for line in f if line.strip()}


def generate(plans: list[ReviewPlan], model: str, out_path: Path) -> None:
    done = load_done_ids(out_path)
    todo = [plan for plan in plans if plan.review_id not in done]
    print(f"계획 {len(plans)}건 중 이미 만든 {len(plans) - len(todo)}건은 건너뛰고 {len(todo)}건을 만듭니다.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with open(out_path, "a", encoding="utf-8") as out:
        for number, plan in enumerate(todo, start=1):
            try:
                review, used_seed = write_review(build_prompt(plan), model, plan.seed)
            except (requests.RequestException, KeyError, ValueError) as e:  # 한 건 실패는 건너뛴다
                failures.append(f"{plan.review_id}: {type(e).__name__}: {e}")
                continue
            out.write(json.dumps(to_record(plan, review, model, used_seed), ensure_ascii=False) + "\n")
            out.flush()  # 중간에 멈춰도 여기까지는 파일에 남는다
            if number % 10 == 0 or number == len(todo):
                print(f"  {number}/{len(todo)}")

    print(f"완료: {len(todo) - len(failures)}건 저장 → {out_path}")
    if failures:
        print(f"⚠️  실패 {len(failures)}건 (같은 명령을 다시 실행하면 이 건들만 다시 시도합니다)")
        for failure in failures:
            print(f"  - {failure}")


def main() -> None:
    parser = argparse.ArgumentParser(description="장소 정보로 합성 리뷰 생성 (로컬 Ollama)")
    parser.add_argument("--member", required=True, help="장소를 가져올 팀원 이니셜 (datas/<이니셜>/out)")
    parser.add_argument("--category", required=True, choices=sorted(ATTRIBUTES))
    parser.add_argument("--count", type=int, required=True, help="만들 리뷰 수")
    parser.add_argument("--out", type=Path, required=True, help="결과 JSONL (이미 있으면 이어서 씀)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-place", type=int, default=20, help="장소 한 곳당 최대 리뷰 수")
    args = parser.parse_args()

    check_ollama(args.model)
    places = places_of(args.member, args.category)
    plans = make_plans(places, args.category, args.count, args.max_per_place, args.seed)
    generate(plans, args.model, args.out)


if __name__ == "__main__":
    main()
