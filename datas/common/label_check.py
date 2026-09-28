"""Teacher LLM이 만든 라벨 레코드가 Silver 조건을 통과하는지 검사한다.

Silver 조건: JSON 형식, 필수 필드, 허용된 aspect, attribute·sentiment·traveler_context 값,
evidence가 리뷰 원문 또는 인용한 장소 정보(place:<필드>=<값>)에 있는지.
규칙은 docs/annotation-guideline.md, 허용값은 schema.py를 따른다.

장소 정보는 팀 전체의 datas/<이니셜>/out/places_*.json에서 찾는다.

사용법:
  uv run python datas/common/label_check.py labeled.jsonl --out silver.jsonl
"""

import argparse
import json
from pathlib import Path
from typing import Final

from paths import load_places
from schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS

REQUIRED_FIELDS: Final = ("review_id", "place_id", "category", "synthetic", "review", "label")
ASPECT_FIELDS: Final = ("category", "attribute", "sentiment", "evidence")
PLACE_PREFIX: Final = "place:"


# ---------- evidence ----------


def check_place_evidence(evidence: str, place: dict | None) -> str | None:
    """`place:<필드>=<값>`이 실제 장소 정보와 맞는지 본다. 문제가 없으면 None."""
    if place is None:
        return "place_id에 해당하는 장소 정보가 없음"
    field, sep, value = evidence.removeprefix(PLACE_PREFIX).partition("=")
    if not sep:
        return f"place:<필드>=<값> 형식이 아님: {evidence!r}"

    facts = {**place, **place.get("facts", {})}  # 최상위 필드(district 등)와 facts를 함께 본다
    if field not in facts:
        return f"장소 정보에 {field} 필드가 없음"
    if str(facts[field]) != value:
        return f"장소 정보는 {field}={facts[field]!r}인데 {value!r}로 인용함"
    return None


def check_evidence(evidence: object, review: str, place: dict | None) -> str | None:
    if not isinstance(evidence, str) or not evidence.strip():
        return "evidence가 비어 있음"
    if evidence.startswith(PLACE_PREFIX):
        return check_place_evidence(evidence, place)
    if evidence not in review:
        return f"리뷰 원문에 없는 evidence: {evidence!r}"
    return None


# ---------- aspect · 레코드 ----------


def check_aspect(aspect: dict, category: str, review: str, place: dict | None) -> list[str]:
    missing = [field for field in ASPECT_FIELDS if field not in aspect]
    if missing:
        return [f"aspect 필드 누락: {missing}"]

    name = aspect["category"]
    if name not in ASPECTS[category]:
        return [f"{category}에 없는 aspect: {name}"]

    errors: list[str] = []
    if aspect["attribute"] not in ATTRIBUTES[category][name]:
        errors.append(f"{name}: 허용되지 않은 attribute {aspect['attribute']!r}")
    if aspect["sentiment"] not in SENTIMENTS:
        errors.append(f"{name}: 허용되지 않은 sentiment {aspect['sentiment']!r}")
    evidence_error = check_evidence(aspect["evidence"], review, place)
    if evidence_error:
        errors.append(f"{name}: {evidence_error}")
    return errors


def check_label(label: object, category: str, review: str, place: dict | None) -> list[str]:
    if not isinstance(label, dict):
        return ["label이 객체가 아님"]
    contexts = label.get("traveler_context")
    aspects = label.get("aspects")
    if not isinstance(contexts, list) or not isinstance(aspects, list):
        return ["label에 traveler_context와 aspects 리스트가 필요함"]

    errors = [f"허용되지 않은 traveler_context: {c!r}" for c in contexts if c not in TRAVELER_CONTEXTS]
    for aspect in aspects:
        if not isinstance(aspect, dict):
            errors.append("aspect가 객체가 아님")
            continue
        errors += check_aspect(aspect, category, review, place)
    return errors


def check_record(record: dict, place: dict | None) -> list[str]:
    """레코드의 문제 목록을 돌려준다. 빈 리스트면 Silver 조건을 통과한 것이다."""
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        return [f"필수 필드 누락: {missing}"]

    category = record["category"]
    if category not in ASPECTS:
        return [f"알 수 없는 카테고리: {category!r}"]

    errors: list[str] = []
    if not isinstance(record["synthetic"], bool):
        errors.append("synthetic은 true/false여야 함")
    if not isinstance(record["review"], str) or not record["review"].strip():
        errors.append("review가 비어 있음")
        return errors
    if place is not None and place["category"] != category:
        errors.append(f"장소 카테고리는 {place['category']}인데 레코드는 {category}")
    return errors + check_label(record["label"], category, record["review"], place)


# ---------- 파일 처리 ----------


def check_line(line: str, places: dict[str, dict]) -> tuple[dict | None, list[str]]:
    """JSONL 한 줄을 파싱하고 검사한다. (레코드, 문제 목록)을 돌려준다."""
    try:
        record = json.loads(line)
    except json.JSONDecodeError as e:
        return None, [f"JSON 형식 오류: {e.msg}"]
    if not isinstance(record, dict):
        return None, ["레코드가 JSON 객체가 아님"]
    return record, check_record(record, places.get(record.get("place_id")))


def check_file(records_path: Path, places: dict[str, dict], out_path: Path) -> None:
    """통과한 레코드만 tier를 붙여 out_path에 쓰고, 탈락 이유를 요약해 출력한다."""
    passed = 0
    failures: list[str] = []
    with open(records_path, encoding="utf-8") as src, open(out_path, "w", encoding="utf-8") as dst:
        for line_no, line in enumerate(src, start=1):
            if not line.strip():
                continue
            record, errors = check_line(line, places)
            if errors:
                failures.append(f"{line_no}행: " + " / ".join(errors))
                continue
            if record.get("tier") != "gold":  # 사람이 승인한 Gold는 그대로 둔다
                record["tier"] = "silver"
            dst.write(json.dumps(record, ensure_ascii=False) + "\n")
            passed += 1

    print(f"통과 {passed}건 → {out_path}")
    print(f"탈락 {len(failures)}건")
    for failure in failures:
        print(f"  - {failure}")


def main() -> None:
    parser = argparse.ArgumentParser(description="라벨 레코드의 Silver 조건 검사")
    parser.add_argument("records", type=Path, help="검사할 JSONL 파일")
    parser.add_argument("--out", type=Path, required=True, help="통과한 레코드를 쓸 JSONL 파일")
    args = parser.parse_args()

    check_file(args.records, load_places(), args.out)


if __name__ == "__main__":
    main()
