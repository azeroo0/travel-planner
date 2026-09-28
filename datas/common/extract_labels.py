"""합성 리뷰에 로컬 gemma4(Ollama)로 라벨을 단다.

라벨은 두 곳에서 나온다.
  1. 리뷰 근거: 모델이 리뷰를 읽고 aspect·attribute·sentiment·evidence를 뽑는다.
     모델에게는 리뷰만 보여주고, 생성 계획(generation 필드)은 보여주지 않는다.
  2. 장소 정보 근거: 리뷰가 말하지 않은 aspect 중 규칙이 정해진 것만 코드가 붙인다
     (docs/annotation-guideline.md 5절). 정해진 규칙이라 모델보다 코드가 정확하다.

결과는 입력 레코드에 label 필드를 더한 JSONL이다. 그다음 label_check로 Silver를 가린다.

사용법:
  uv run python datas/common/extract_labels.py datas/cjm/out/generated/pilot_restaurant.jsonl \\
      --out datas/cjm/out/generated/pilot_restaurant.labeled.jsonl
  uv run python datas/common/label_check.py datas/cjm/out/generated/pilot_restaurant.labeled.jsonl \\
      --out datas/cjm/out/generated/pilot_restaurant.silver.jsonl
"""

import argparse
import json
from pathlib import Path
from typing import Final

import requests

from ollama_client import DEFAULT_MODEL, chat_json, check_ollama
from paths import load_places
from schema import (
    ASPECT_NAMES_KO,
    ATTRIBUTES,
    CATEGORY_NAMES_KO,
    SENTIMENTS,
    TRAVELER_CONTEXTS,
    TRAVELER_NAMES_KO,
    VALUE_NAMES_KO,
)

TEMPERATURE: Final = 0.0  # 라벨은 매번 같은 답이 나와야 하므로 무작위성을 끈다
SEED: Final = 0

EXAMPLE: Final = """\
리뷰: 부모님이랑 갔는데 웨이팅이 40분이나 됐어요. 그래도 회는 정말 신선했고 양은 보통이었어요.
JSON: {"traveler_context": ["parents"], "aspects": [
  {"category": "waiting_time", "attribute": "long", "sentiment": "negative", "evidence": "웨이팅이 40분이나 됐어요"},
  {"category": "freshness", "attribute": "fresh", "sentiment": "positive", "evidence": "회는 정말 신선했고"},
  {"category": "portion", "attribute": "normal", "sentiment": "neutral", "evidence": "양은 보통이었어요"}]}"""


# ---------- 1. 리뷰 근거 라벨 (모델) ----------


def label_schema(category: str) -> dict:
    """모델 출력 모양을 강제하는 JSON 스키마. aspect·값 목록을 이 카테고리 것으로 좁힌다."""
    table = ATTRIBUTES[category]
    values = sorted({value for allowed in table.values() for value in allowed})
    aspect = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": sorted(table)},
            "attribute": {"type": "string", "enum": values},
            "sentiment": {"type": "string", "enum": sorted(SENTIMENTS)},
            "evidence": {"type": "string"},
        },
        "required": ["category", "attribute", "sentiment", "evidence"],
    }
    return {
        "type": "object",
        "properties": {
            "traveler_context": {"type": "array", "items": {"type": "string", "enum": sorted(TRAVELER_CONTEXTS)}},
            "aspects": {"type": "array", "items": aspect},
        },
        "required": ["traveler_context", "aspects"],
    }


def describe_aspects(category: str) -> list[str]:
    lines = []
    for name, allowed in ATTRIBUTES[category].items():
        values = " / ".join(f"{value}({VALUE_NAMES_KO[value]})" for value in allowed)
        lines.append(f"- {name} ({ASPECT_NAMES_KO[name]}): {values}")
    return lines


def build_prompt(review: str, category: str) -> str:
    travelers = " / ".join(f"{key}({TRAVELER_NAMES_KO[key]})" for key in sorted(TRAVELER_CONTEXTS))
    return "\n".join([
        f"다음은 {CATEGORY_NAMES_KO[category]}에 대한 여행 리뷰입니다. 리뷰에서 정보를 뽑아 JSON으로 정리하세요.",
        "",
        "[리뷰]",
        review,
        "",
        "[aspect와 허용 attribute]",
        *describe_aspects(category),
        "",
        f"[traveler_context 허용값] {travelers}",
        "",
        "[규칙]",
        "1. 리뷰가 실제로 말한 aspect만 뽑습니다. 리뷰에 근거가 있는 것만 넣습니다.",
        "2. evidence는 그 판단을 담은 가장 짧은 구절을 리뷰에서 한 글자도 바꾸지 않고 그대로 복사합니다.",
        "3. attribute는 상태, sentiment는 평가(positive/negative/neutral)입니다.",
        "   웨이팅이 길었지만 만족했다면 long + positive입니다. 평가 없이 사실만 말하면 neutral입니다.",
        "4. 가운데 값(average, moderate, medium, normal)은 '보통', '무난'처럼 적혀 있을 때만 씁니다.",
        "5. 한 aspect에 긍정과 부정이 섞이면 aspect를 두 개로 나눕니다.",
        "6. traveler_context는 누구와 갔는지 적혀 있을 때만 넣고, 없으면 빈 리스트입니다.",
        "7. 주차는 두 aspect로 나눕니다 (그 카테고리에 있는 aspect일 때).",
        "   parking_availability는 주차장이 있는지, 자리가 충분한지입니다.",
        "   parking_experience는 주차하기가 쉬웠는지입니다 (자리 찾기, 진입로, 좁은 공간).",
        "   '주차 편했어요' → parking_experience / easy",
        "   '자리 찾느라 한참 돌았어요' → parking_experience / difficult",
        "   '주차장이 없어요' → parking_availability / unavailable",
        "   '주차 자리가 몇 대 안 돼요' → parking_availability / limited",
        "",
        "[예시]",
        EXAMPLE,
    ])  # fmt: skip


def extract_review_label(review: str, category: str, model: str) -> dict:
    return chat_json(
        build_prompt(review, category),
        model=model,
        schema=label_schema(category),
        temperature=TEMPERATURE,
        seed=SEED,
    )


# ---------- 2. 장소 정보 근거 라벨 (규칙) ----------

# 가이드라인 5절. TourAPI 분류 코드(class_code) 앞 4자리로 판단한다 (초안).
# 실내·실외가 섞인 분류(EX05 온천·치유의숲, EX07 체험, VE01 전망대, VE02 테마파크·아쿠아리움,
# LS01 루지·아이스링크·걷기길)는 표에 넣지 않아서 장소 정보 라벨을 달지 않는다.
WEATHER_BY_CLASS: Final[dict[str, str]] = {
    # 실외 → high
    "EX03": "high",  # 어촌 체험마을
    "HS01": "high",  # 정자·향교
    "HS03": "high",  # 사찰
    "NA01": "high",  # 산·숲·계곡
    "NA02": "high",  # 해변
    "NA04": "high",  # 휴양림·수목원
    "NA05": "high",  # 해안 산책로·걷기길
    "VE03": "high",  # 공원
    "VE04": "high",  # 마을·거리
    "VE05": "high",  # 관광특구
    "AC05": "high",  # 캠핑·글램핑
    "LS02": "high",  # 서핑·요트 등 수상레저
    # 실내 → low
    "EX06": "low",  # 영화 촬영소·영화의전당
    "VE06": "low",  # 공연장
    "VE07": "low",  # 미술관·전시관
    "VE09": "low",  # 도서관·문화원
    "VE10": "low",  # 체육문화센터
    "VE12": "low",  # 서점·자료실
}

# 분류로 체류 시간을 추정한다 (초안). 분명한 분류만 넣고, 애매한 분류는 라벨을 달지 않는다.
STAY_BY_CLASS: Final[dict[str, str]] = {
    "VE01": "short",  # 전망대
    "HS01": "short",  # 정자·향교
    "VE07": "medium",  # 미술관·전시관
    "EX06": "medium",  # 영화 촬영소·영화의전당
    "NA04": "long",  # 휴양림·수목원
    "AC05": "long",  # 캠핑·글램핑
}


def parking_value(text: str) -> str | None:
    """TourAPI 주차 문구를 available/unavailable로 바꾼다. 판단이 어려우면 None."""
    if "불가" in text or "없음" in text:  # "주차 불가능"에도 "가능"이 들어 있어서 먼저 본다
        return "unavailable"
    if "가능" in text or "있음" in text:
        return "available"
    return None


def place_fact_aspect(name: str, value: str, field: str, fact: object) -> dict:
    """장소 정보 근거 라벨. 장소 정보만으로는 평가를 알 수 없어서 sentiment는 neutral이다."""
    return {"category": name, "attribute": value, "sentiment": "neutral", "evidence": f"place:{field}={fact}"}


def class_label(facts: dict, name: str, table: dict[str, str]) -> dict | None:
    """class_code 앞 4자리가 표에 있으면 그 값으로 라벨을 만든다. evidence에는 전체 코드를 남긴다."""
    class_code = str(facts.get("class_code", ""))
    value = table.get(class_code[:4])
    if value is None:
        return None
    return place_fact_aspect(name, value, "class_code", class_code)


def weather_label(facts: dict) -> dict | None:
    return class_label(facts, "weather_sensitivity", WEATHER_BY_CLASS)


def stay_label(facts: dict) -> dict | None:
    return class_label(facts, "stay_duration", STAY_BY_CLASS)


def parking_label(facts: dict) -> dict | None:
    parking = facts.get("parking")
    value = parking_value(str(parking)) if parking else None
    if value is None:
        return None
    return place_fact_aspect("parking_availability", value, "parking", parking)


# aspect → 장소 정보로 라벨을 만드는 규칙
PLACE_RULES: Final = {
    "weather_sensitivity": weather_label,
    "stay_duration": stay_label,
    "parking_availability": parking_label,
}


def place_labels(place: dict, mentioned: set[str]) -> list[dict]:
    """리뷰가 말하지 않은 aspect 중 이 카테고리에 있고 규칙이 있는 것만 장소 정보로 라벨을 만든다."""
    labels: list[dict] = []
    for name, rule in PLACE_RULES.items():
        if name in mentioned or name not in ATTRIBUTES[place["category"]]:
            continue
        label = rule(place["facts"])
        if label is not None:
            labels.append(label)
    return labels


# ---------- 레코드 처리 ----------


def label_record(record: dict, place: dict | None, model: str) -> dict:
    label = extract_review_label(record["review"], record["category"], model)
    if place is not None:
        mentioned = {aspect["category"] for aspect in label["aspects"]}
        label["aspects"] += place_labels(place, mentioned)
    return {**record, "label": label, "labeling": {"model": model, "temperature": TEMPERATURE, "seed": SEED}}


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_done_ids(out_path: Path) -> set[str]:
    return {record["review_id"] for record in read_jsonl(out_path)} if out_path.exists() else set()


def extract(records: list[dict], places: dict[str, dict], model: str, out_path: Path) -> None:
    done = load_done_ids(out_path)
    todo = [record for record in records if record["review_id"] not in done]
    print(f"리뷰 {len(records)}건 중 이미 라벨을 단 {len(records) - len(todo)}건은 건너뛰고 {len(todo)}건을 처리합니다.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with open(out_path, "a", encoding="utf-8") as out:
        for number, record in enumerate(todo, start=1):
            try:
                labeled = label_record(record, places.get(record["place_id"]), model)
            except (requests.RequestException, KeyError, ValueError) as e:  # 한 건 실패는 건너뛴다
                failures.append(f"{record['review_id']}: {type(e).__name__}: {e}")
                continue
            out.write(json.dumps(labeled, ensure_ascii=False) + "\n")
            out.flush()
            if number % 10 == 0 or number == len(todo):
                print(f"  {number}/{len(todo)}")

    print(f"완료: {len(todo) - len(failures)}건 저장 → {out_path}")
    if failures:
        print(f"⚠️  실패 {len(failures)}건 (같은 명령을 다시 실행하면 이 건들만 다시 시도합니다)")
        for failure in failures:
            print(f"  - {failure}")


def main() -> None:
    parser = argparse.ArgumentParser(description="합성 리뷰에 라벨 달기 (로컬 Ollama)")
    parser.add_argument("reviews", type=Path, help="generate_reviews가 만든 JSONL")
    parser.add_argument("--out", type=Path, required=True, help="라벨을 붙인 JSONL (이미 있으면 이어서 씀)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()

    check_ollama(args.model)
    extract(read_jsonl(args.reviews), load_places(), args.model, args.out)


if __name__ == "__main__":
    main()
