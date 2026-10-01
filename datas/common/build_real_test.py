"""실제 수집한 Tripadvisor 리뷰(tripadvisor_reviews.xlsx)를 실제 리뷰 test 형식으로 바꾼다.

라벨은 real_test_draft.py의 초안을 쓴다. 초안은 Claude가 쓴 것이라 tier는 silver이고,
사람이 review_gold.py로 원문과 대조해 승인한 뒤에만 gold가 된다.
초안이 스키마 허용값과 원문 일치 검사(evidence가 리뷰에 그대로 있는지)를 통과하지 못하면 쓰지 않고 실패한 항목을 보여 준다.

openpyxl이 프로젝트 의존성이 아니므로 다음처럼 실행한다.
  uv run --with openpyxl python datas/common/build_real_test.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from real_test_draft import DRAFT  # noqa: E402
from schema import ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS  # noqa: E402

ROOT = HERE.parents[1]
LABELER = "claude-sonnet-5-5 (초안, 사람 검수 전)"


def read_reviews(path: Path) -> list[dict[str, Any]]:
    sheet = openpyxl.load_workbook(path, read_only=True)["Reviews"]
    rows = sheet.iter_rows(values_only=True)
    header = next(rows)
    return [dict(zip(header, row)) for row in rows]


def problems(category: str, review: str, contexts: list[str], aspects: list[dict[str, str]]) -> list[str]:
    found = [f"허용되지 않은 traveler_context: {c}" for c in contexts if c not in TRAVELER_CONTEXTS]
    for aspect in aspects:
        allowed = ATTRIBUTES[category].get(aspect["category"])
        if allowed is None:
            found.append(f"{category}에 없는 aspect: {aspect['category']}")
        elif aspect["attribute"] not in allowed:
            found.append(f"{aspect['category']}에 없는 attribute: {aspect['attribute']}")
        if aspect["sentiment"] not in SENTIMENTS:
            found.append(f"허용되지 않은 sentiment: {aspect['sentiment']}")
        if aspect["evidence"] not in review:
            found.append(f"evidence가 원문에 없음: {aspect['evidence']!r}")
    return found


def to_record(index: int, row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    category = row["category"].lower()
    contexts, drafts = DRAFT[index]
    aspects = [
        {"category": name, "attribute": attribute, "sentiment": sentiment, "evidence": evidence}
        for name, attribute, sentiment, evidence in drafts
    ]
    review = row["text"]
    record = {
        "review_id": f"ta_{row['review_id']}",
        "place_id": f"tripadvisor:{row['location_id']}",
        "category": category,
        "synthetic": False,
        "review": review,
        "label": {"traveler_context": contexts, "aspects": aspects},
        "labeling": {"model": LABELER},
        "tier": "silver",
        "split": "test_real",
        "source_member": "tripadvisor",
        "source": {
            "language": row["source_language"],
            "translation_status": row["translation_status"],
            "rating": int(row["rating"]),
            "trip_type": row["trip_type"],
            "travel_date": row["travel_date"],
        },
    }
    return record, problems(category, review, contexts, aspects)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--xlsx", type=Path, default=ROOT / "tripadvisor_reviews.xlsx")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/v2/test_real.jsonl")
    args = parser.parse_args()

    rows = read_reviews(args.xlsx)
    missing = sorted(set(range(len(rows))) - set(DRAFT))
    if missing or len(DRAFT) != len(rows):
        sys.exit(f"초안이 {len(rows)}건과 맞지 않습니다. 누락: {missing}")

    records, failures = [], []
    for index, row in enumerate(rows):
        record, found = to_record(index, row)
        records.append(record)
        failures.extend(f"[{index}] {message}" for message in found)
    if failures:
        sys.exit("초안 검사 실패:\n" + "\n".join(failures))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in records)

    aspects = Counter((r["category"], a["category"]) for r in records for a in r["label"]["aspects"])
    print(f"{len(records)}건 저장: {args.output}")
    print("aspect 없는 리뷰:", sum(not r["label"]["aspects"] for r in records))
    print("aspect 수:", sum(aspects.values()), "종류:", len(aspects))
    print("sentiment:", dict(Counter(a["sentiment"] for r in records for a in r["label"]["aspects"])))


if __name__ == "__main__":
    main()
