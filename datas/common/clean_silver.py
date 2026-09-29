"""합성 Silver 학습 데이터를 라벨링 가이드라인 기준으로 정리한다.

datasets/train.jsonl, validation.jsonl을 읽어 datasets/v2/ 에 정리본을 쓴다. 원본은 고치지 않는다.
test(Gold)는 이 스크립트가 건드리지 않는다.

정리 규칙 (모두 결정적이고, 사람 검수 없이 적용해도 라벨 의미가 바뀌지 않는 것만 넣었다):
1. 한 리뷰 안에서 (category, attribute, sentiment)가 같은 aspect는 하나만 남긴다.
   가이드라인 3절 "같은 판단을 반복하면 가장 분명한 구절 하나만"에 따라 evidence가 가장 짧은 것을 남긴다.
2. 한 장소의 리뷰는 train에서 최대 --max-per-place 건만 남긴다. 특정 장소가 학습을 지배하는 것을 막는다.
   남길 리뷰는 (seed, review_id) 해시 순으로 고르므로 다시 실행해도 같다.
3. 규칙 1 이후 aspect가 없는 리뷰는 뺀다.
4. evidence의 자르는 경계를 normalize_evidence.py의 기준으로 맞춘다. 바뀐 레코드에는 원래 label을 label_raw로 남긴다.
   (label_raw는 감사용이라 학습 입력에 들어가지 않는다. 학습은 label만 쓴다.)
5. 호텔의 cleanliness와 room_condition을 unify_labels.py의 기준으로 나눈다. train·validation에만 적용하고
   Gold test는 고치지 않으며, 기준을 적용하면 바뀔 test 라벨 수만 보고서에 남긴다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from normalize_evidence import normalize_label
from unify_labels import unify_label

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "datasets"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def dedupe_aspects(aspects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """같은 (category, attribute, sentiment)는 evidence가 가장 짧은 하나만 남기고 원래 순서를 지킨다."""
    shortest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for aspect in aspects:
        key = (aspect["category"], aspect["attribute"], aspect["sentiment"])
        if key not in shortest or len(aspect["evidence"]) < len(shortest[key]["evidence"]):
            shortest[key] = aspect
    kept_ids = {id(aspect) for aspect in shortest.values()}
    return [aspect for aspect in aspects if id(aspect) in kept_ids]


def normalize_record(record: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """evidence 경계를 맞춘 레코드와 바뀐 evidence 수를 돌려준다. 바뀐 게 있으면 원래 label을 label_raw에 남긴다."""
    label, changed = normalize_label(record["label"], record["review"])
    if not changed:
        return record, 0
    return {**record, "label": label, "label_raw": record["label"]}, changed


def clean_record(record: dict[str, Any]) -> tuple[dict[str, Any], int, int, int]:
    """경계 정규화, 호텔 라벨 통일, 중복 제거를 차례로 적용한다. (레코드, 제거한 중복, 바뀐 evidence, 바뀐 aspect)를 돌려준다."""
    normalized, changed = normalize_record(record)
    label, relabeled = unify_label(normalized["label"], normalized["category"])
    kept = dedupe_aspects(label["aspects"])
    cleaned = {**normalized, "label": {**label, "aspects": kept}}
    if relabeled and "label_raw" not in cleaned:
        cleaned["label_raw"] = record["label"]
    return cleaned, len(label["aspects"]) - len(kept), changed, relabeled


def cap_per_place(rows: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    by_place: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_place[row["place_id"]].append(row)
    keep: set[str] = set()
    for place_rows in by_place.values():
        ordered = sorted(
            place_rows,
            key=lambda row: hashlib.sha256(f"{seed}:{row['review_id']}".encode()).hexdigest(),
        )
        keep.update(row["review_id"] for row in ordered[:limit])
    return [row for row in rows if row["review_id"] in keep]


def clean_split(rows: list[dict[str, Any]], max_per_place: int | None, seed: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    cleaned_rows = []
    removed_duplicates = normalized_evidence = relabeled_condition = 0
    for row in rows:
        cleaned, removed, changed, relabeled = clean_record(row)
        removed_duplicates += removed
        normalized_evidence += changed
        relabeled_condition += relabeled
        if cleaned["label"]["aspects"]:
            cleaned_rows.append(cleaned)
    dropped_empty = len(rows) - len(cleaned_rows)
    if max_per_place is not None:
        cleaned_rows = cap_per_place(cleaned_rows, max_per_place, seed)
    stats = {
        "input_reviews": len(rows),
        "output_reviews": len(cleaned_rows),
        "removed_duplicate_aspects": removed_duplicates,
        "normalized_evidence": normalized_evidence,
        "relabeled_hotel_condition": relabeled_condition,
        "dropped_empty_reviews": dropped_empty,
        "dropped_by_place_cap": len(rows) - dropped_empty - len(cleaned_rows),
    }
    return cleaned_rows, stats


def normalize_test(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Gold test는 고치지 않고, evidence 경계만 맞춘 별도 사본을 만든다. 사람이 승인하기 전에는 Gold 대신 쓰지 않는다."""
    normalized_rows, changed_total = [], 0
    for row in rows:
        normalized, changed = normalize_record(row)
        changed_total += changed
        normalized_rows.append({**normalized, "evidence_normalization": "pending_approval"} if changed else normalized)
    return normalized_rows, changed_total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=DATASETS)
    parser.add_argument("--output", type=Path, default=DATASETS / "v2")
    parser.add_argument("--max-per-place", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report: dict[str, Any] = {"max_per_place": args.max_per_place, "seed": args.seed}
    for name, cap in (("train", args.max_per_place), ("validation", None)):
        rows, stats = clean_split(read_jsonl(args.input / f"{name}.jsonl"), cap, args.seed)
        write_jsonl(args.output / f"{name}.jsonl", rows)
        stats["categories"] = dict(Counter(row["category"] for row in rows))
        stats["max_reviews_per_place"] = max(Counter(row["place_id"] for row in rows).values())
        report[name] = stats
        print(name, json.dumps(stats, ensure_ascii=False))
    test_rows, changed = normalize_test(read_jsonl(args.input / "test.jsonl"))
    write_jsonl(args.output / "test_normalized.jsonl", test_rows)
    test_would_relabel = sum(unify_label(row["label"], row["category"])[1] for row in test_rows)
    report["test_normalized"] = {"reviews": len(test_rows), "normalized_evidence": changed, "hotel_labels_the_rule_would_change_but_did_not": test_would_relabel}
    print("test_normalized", json.dumps(report["test_normalized"], ensure_ascii=False))
    (args.output / "clean_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
