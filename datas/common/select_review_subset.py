"""실제 리뷰 test에서 사람이 검수할 리뷰를 카테고리 비율에 맞춰 고른다.

승인 도구(review_gold.py)는 파일 순서대로 보여 주므로, 146건을 순서대로 하다 멈추면 앞쪽 카테고리에 치우친다.
이 스크립트는 이미 검수한 리뷰를 세고, 카테고리별 목표(--targets)까지 모자란 만큼만 고정 seed로 무작위로 골라
카테고리가 번갈아 나오는 검수 대기 파일을 만든다. 파일은 gold.jsonl과 같은 폴더에 둬야 결과가 이어진다.

- 초안 라벨이 빈 리뷰는 전체 비율만큼 섞는다. 모델이 없는 aspect를 만드는지 보는 데 필요하다.
- 400자를 넘는 긴 리뷰는 확인이 오래 걸려 추가분에서 --max-long건까지만 넣는다.

  uv run python datas/common/select_review_subset.py
  uv run python datas/common/review_gold.py datasets/v2/test_real_queue.jsonl --reviewer <이름>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LONG_REVIEW_CHARS = 400
CATEGORY_ORDER = ("hotel", "restaurant", "attraction")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def parse_targets(text: str) -> dict[str, int]:
    return {name: int(count) for name, count in (item.split("=") for item in text.split(","))}


def rank(review_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{review_id}".encode()).hexdigest()


def quotas(targets: dict[str, int], approved: Counter) -> dict[str, int]:
    """카테고리별로 이미 승인한 수를 뺀 만큼만 더 고른다."""
    return {name: max(targets[name] - approved[name], 0) for name in CATEGORY_ORDER}


def pick_for_category(pool: list[dict[str, Any]], quota: int, empty_share: float, seed: int, long_left: list[int]) -> list[dict[str, Any]]:
    """한 카테고리에서 quota개를 고른다. 초안이 빈 리뷰는 전체 비율만큼 넣고, 긴 리뷰는 남은 허용량 안에서만 넣는다."""
    ranked = sorted(pool, key=lambda record: rank(record["review_id"], seed))
    empties = [r for r in ranked if not r["label"]["aspects"]]
    filled = [r for r in ranked if r["label"]["aspects"]]
    want_empty = min(round(quota * empty_share), len(empties))
    chosen: list[dict[str, Any]] = []
    for group, limit in ((empties, want_empty), (filled, quota - want_empty)):
        taken = 0
        for record in group:
            if taken >= limit:
                break
            if len(record["review"]) > LONG_REVIEW_CHARS:
                if long_left[0] <= 0:
                    continue
                long_left[0] -= 1
            chosen.append(record)
            taken += 1
    return chosen


def interleave(groups: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """카테고리가 번갈아 나오게 늘어놓아 중간에 멈춰도 한쪽으로 치우치지 않게 한다."""
    ordered: list[dict[str, Any]] = []
    depth = max((len(items) for items in groups.values()), default=0)
    for index in range(depth):
        for name in CATEGORY_ORDER:
            if index < len(groups[name]):
                ordered.append(groups[name][index])
    return ordered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=ROOT / "datasets/v2/test_real.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/v2/test_real_queue.jsonl")
    parser.add_argument("--targets", default="hotel=15,restaurant=20,attraction=15", help="카테고리별 승인 목표 수 (이미 승인한 것 포함)")
    parser.add_argument("--max-long", type=int, default=3, help="추가로 넣을 400자 초과 리뷰의 최대 수")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = read_jsonl(args.input)
    gold = {row["review_id"]: row for row in read_jsonl(args.input.with_name("gold.jsonl"))}
    discarded = {row["review_id"] for row in read_jsonl(args.input.with_name("discarded.jsonl"))}
    decided = set(gold) | discarded
    approved = Counter(row["category"] for row in gold.values())
    targets = parse_targets(args.targets)
    need = quotas(targets, approved)

    pool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if record["review_id"] not in decided:
            pool[record["category"]].append(record)
    empty_share = sum(not r["label"]["aspects"] for r in records) / len(records)

    long_left = [args.max_long]
    picked = {name: pick_for_category(pool[name], need[name], empty_share, args.seed, long_left) for name in CATEGORY_ORDER}
    queue = interleave(picked) + [row for row in records if row["review_id"] in gold]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(record, ensure_ascii=False) + "\n" for record in queue)

    added = [r for items in picked.values() for r in items]
    print(f"이미 승인 {sum(approved.values())}건 {dict(approved)} / 추가 {len(added)}건 {dict(Counter(r['category'] for r in added))}")
    print(f"추가분 중 초안이 빈 리뷰 {sum(not r['label']['aspects'] for r in added)}건, 400자 초과 {sum(len(r['review']) > LONG_REVIEW_CHARS for r in added)}건")
    print(f"검수 대기 파일: {args.output} ({len(queue)}건: 대기 {len(added)} + 승인됨 {len(queue) - len(added)})")


if __name__ == "__main__":
    main()
