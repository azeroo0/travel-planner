"""준비된 Silver/Gold 레코드를 SFT Dataset으로 변환한다."""

from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset

from .prompt import build_prompt


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def serialize_label(label: dict) -> str:
    return json.dumps(label, ensure_ascii=False, separators=(",", ":"))


def to_sft_example(record: dict) -> dict:
    return {
        "prompt": build_prompt(category=record["category"], review=record["review"]),
        "completion": [{"role": "assistant", "content": serialize_label(record["label"])}],
    }


def build_train_validation_records(silver_file: Path, split_file: Path) -> tuple[list[dict], list[dict]]:
    silver_records = read_jsonl(silver_file)
    split = json.loads(split_file.read_text(encoding="utf-8"))
    train_records: list[dict] = []
    validation_records: list[dict] = []

    for record in silver_records:
        place_split = split.get(record["place_id"])
        if place_split == "train":
            train_records.append(record)
        elif place_split == "val":
            validation_records.append(record)
        elif place_split != "test":
            raise ValueError(f"split.json에 없는 place_id입니다: {record['place_id']}")

    return train_records, validation_records


def build_test_records(gold_file: Path) -> list[dict]:
    records = read_jsonl(gold_file)
    for record in records:
        if record.get("tier") != "gold":
            raise ValueError(f"Gold test 파일에 Gold가 아닌 레코드가 있습니다: {record['review_id']}")
    return records


def remove_duplicate_reviews(records: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    unique_records: list[dict] = []
    for record in records:
        key = (record["place_id"], record["review"].strip())
        if key not in seen:
            seen.add(key)
            unique_records.append(record)
    return unique_records


def convert_to_dataset(records: list[dict]) -> Dataset:
    return Dataset.from_list([to_sft_example(record) for record in records])


def load_sft_dataset(path: Path) -> Dataset:
    """이미 train/validation으로 확정된 JSONL을 SFT Dataset으로 읽는다."""
    records = remove_duplicate_reviews(read_jsonl(path))
    return convert_to_dataset(records)


def load_training_datasets(
    train_file: Path,
    validation_file: Path,
) -> tuple[Dataset, Dataset]:
    return load_sft_dataset(train_file), load_sft_dataset(validation_file)
