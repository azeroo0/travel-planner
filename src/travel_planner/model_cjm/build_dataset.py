"""cjm과 sang의 부산 Silver를 전략 A SFT 데이터셋으로 통합한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "artifacts/datasets/busan_review_sft_v1"
DEFAULT_SPLIT = ROOT / "datas/common/split.json"
SANG_SILVER = sorted(
    (ROOT / "datas/sang/out/runs").glob("silver_2000_*/silver.jsonl")
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def review_only_label(label: dict[str, Any]) -> tuple[dict[str, Any], int]:
    aspects = label.get("aspects", [])
    kept = [aspect for aspect in aspects if not aspect.get("evidence", "").startswith("place:")]
    return {**label, "aspects": kept}, len(aspects) - len(kept)


def stable_sang_split(place_id: str, category: str, place_ids: list[str], seed: int) -> str:
    ordered = sorted(
        place_ids,
        key=lambda value: hashlib.sha256(f"{seed}:{category}:{value}".encode()).hexdigest(),
    )
    index = ordered.index(place_id)
    count = len(ordered)
    if count >= 3 and index < max(1, round(count * 0.1)):
        return "test"
    if count >= 3 and index < max(2, round(count * 0.2)):
        return "val"
    if count == 2 and index == 0:
        return "test"
    return "train"


def assign_sang_splits(rows: list[dict[str, Any]], seed: int) -> dict[str, str]:
    places_by_category: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        places_by_category[row["category"]].add(row["place_id"])
    assignment: dict[str, str] = {}
    for category, place_ids in places_by_category.items():
        ids = sorted(place_ids)
        for place_id in ids:
            assignment[place_id] = stable_sang_split(place_id, category, ids, seed)
    return assignment


def enrich_and_filter(
    rows: list[dict[str, Any]],
    source_member: str,
    split: dict[str, str],
    allowed_splits: set[str],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    result: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    for row in rows:
        row_split = split.get(row["place_id"])
        if row_split not in allowed_splits:
            stats["excluded_test_or_unassigned"] += 1
            continue
        label, removed = review_only_label(row["label"])
        stats["removed_place_aspects"] += removed
        result.append(
            {
                **row,
                "label": label,
                "split": row_split,
                "source_member": source_member,
            }
        )
    return result, stats


def deduplicate(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []
    removed = 0
    for row in rows:
        key = (row["place_id"], row["review"].strip())
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        result.append(row)
    return result, removed


def main(output_dir: Path, seed: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_split = json.loads(DEFAULT_SPLIT.read_text(encoding="utf-8"))

    cjm_rows = read_jsonl(ROOT / "datas/cjm/out/runs/silver_v1/silver.jsonl")
    sang_rows = [row for path in SANG_SILVER for row in read_jsonl(path)]
    sang_split = assign_sang_splits(sang_rows, seed)
    combined_split = {**existing_split, **sang_split}

    cjm_train_val, cjm_stats = enrich_and_filter(
        cjm_rows,
        "cjm",
        combined_split,
        {"train", "val"},
    )
    sang_train_val, sang_stats = enrich_and_filter(
        sang_rows,
        "sang",
        combined_split,
        {"train", "val"},
    )

    train_rows, duplicate_train = deduplicate(
        [row for row in cjm_train_val + sang_train_val if row["split"] == "train"]
    )
    val_rows, duplicate_val = deduplicate(
        [row for row in cjm_train_val + sang_train_val if row["split"] == "val"]
    )

    gold_test = read_jsonl(ROOT / "datas/cjm/out/runs/silver_v1/test/gold.jsonl")
    gold_test, gold_stats = enrich_and_filter(
        gold_test,
        "cjm",
        combined_split,
        {"test"},
    )
    for row in gold_test:
        row["tier"] = "gold"

    write_jsonl(output_dir / "train.jsonl", train_rows)
    write_jsonl(output_dir / "validation.jsonl", val_rows)
    write_jsonl(output_dir / "test.jsonl", gold_test)
    (output_dir / "split.json").write_text(
        json.dumps(combined_split, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "dataset_name": "busan_review_sft_v1",
        "strategy": "A_review_only",
        "sources": {
            "cjm": "datas/cjm/out/runs/silver_v1/silver.jsonl",
            "sang": [str(path.relative_to(ROOT)) for path in SANG_SILVER],
            "gold_test": "datas/cjm/out/runs/silver_v1/test/gold.jsonl",
        },
        "excluded": [
            "cjm backup",
            "knk Incheon data",
            "Silver records assigned to test split",
            "place-derived aspects from labels",
        ],
        "seed": seed,
        "counts": {
            "train": len(train_rows),
            "validation": len(val_rows),
            "test_gold": len(gold_test),
        },
        "category_counts": {
            split_name: dict(Counter(row["category"] for row in rows))
            for split_name, rows in {
                "train": train_rows,
                "validation": val_rows,
                "test_gold": gold_test,
            }.items()
        },
        "source_counts": {
            split_name: dict(Counter(row["source_member"] for row in rows))
            for split_name, rows in {
                "train": train_rows,
                "validation": val_rows,
                "test_gold": gold_test,
            }.items()
        },
        "processing": {
            "cjm": dict(cjm_stats),
            "sang": dict(sang_stats),
            "gold_test": dict(gold_stats),
            "duplicate_train_removed": duplicate_train,
            "duplicate_validation_removed": duplicate_val,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest["counts"], ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the unified Busan SFT dataset")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    main(args.output_dir, args.seed)
