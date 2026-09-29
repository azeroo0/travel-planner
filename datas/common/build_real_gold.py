"""사람이 승인한 실제 리뷰 라벨로 평가용 test_real_gold.jsonl을 만든다.

review_gold.py가 남긴 gold.jsonl 중 검수 대기 파일(test_real_queue.jsonl)에 있는 리뷰만 쓴다.
사람이 승인한 라벨에 학습 데이터와 같은 기준만 기계적으로 적용한다. 뜻은 바꾸지 않는다.
- evidence의 끝 문장부호와 앞의 군더더기 부사를 뗀다 (normalize_evidence.py)
- 같은 (category, attribute, sentiment)는 evidence가 가장 짧은 하나만 남긴다 (가이드라인 3절)
바뀐 레코드는 사람이 승인한 원래 label을 label_raw로 남긴다.
같은 aspect와 attribute에 sentiment가 둘 다 달린 리뷰는 고치지 않고 알려 준다. 사람이 판단할 일이기 때문이다.

  uv run python datas/common/build_real_gold.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from clean_silver import dedupe_aspects
from normalize_evidence import normalize_label
from schema import ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS

ROOT = Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def problems(record: dict[str, Any]) -> list[str]:
    """스키마 허용값과 evidence 원문 일치를 어기는 곳."""
    found = [f"허용되지 않은 traveler_context: {c}" for c in record["label"]["traveler_context"] if c not in TRAVELER_CONTEXTS]
    for aspect in record["label"]["aspects"]:
        allowed = ATTRIBUTES[record["category"]].get(aspect["category"])
        if allowed is None or aspect["attribute"] not in allowed:
            found.append(f"허용되지 않은 aspect·attribute: {aspect['category']}/{aspect['attribute']}")
        if aspect["sentiment"] not in SENTIMENTS:
            found.append(f"허용되지 않은 sentiment: {aspect['sentiment']}")
        if aspect["evidence"] not in record["review"]:
            found.append(f"evidence가 원문에 없음: {aspect['evidence']!r}")
    return found


def conflicting_sentiments(label: dict[str, Any]) -> list[tuple[str, str]]:
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for aspect in label["aspects"]:
        seen[(aspect["category"], aspect["attribute"])].add(aspect["sentiment"])
    return [key for key, sentiments in seen.items() if len(sentiments) > 1]


def finalize(record: dict[str, Any]) -> dict[str, Any]:
    human = record["label"]
    label, _ = normalize_label(human, record["review"])
    label = {**label, "aspects": dedupe_aspects(label["aspects"])}
    result = {**record, "label": label, "split": "test_real_gold"}
    if label != human:
        result["label_raw"] = human
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--queue", type=Path, default=ROOT / "datasets/v2/test_real_queue.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "datasets/v2/test_real_gold.jsonl")
    args = parser.parse_args()

    queue_ids = {row["review_id"] for row in read_jsonl(args.queue)}
    gold = [row for row in read_jsonl(args.queue.with_name("gold.jsonl")) if row["review_id"] in queue_ids]
    discarded = {row["review_id"] for row in read_jsonl(args.queue.with_name("discarded.jsonl"))} & queue_ids
    pending = queue_ids - {row["review_id"] for row in gold} - discarded
    if pending:
        print(f"아직 승인하지 않은 리뷰 {len(pending)}건이 있습니다. 승인한 {len(gold)}건으로만 만듭니다.")

    failures = [f"{row['review_id']}: {message}" for row in gold for message in problems(row)]
    if failures:
        raise SystemExit("승인된 라벨에 문제가 있습니다:\n" + "\n".join(failures))

    rows = [finalize(row) for row in gold]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        file.writelines(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)

    human_aspects = sum(len(row["label"]["aspects"]) for row in gold)
    final_aspects = sum(len(row["label"]["aspects"]) for row in rows)
    print(f"저장: {args.output} ({len(rows)}건, 버린 리뷰 {len(discarded)}건)")
    print("카테고리:", dict(Counter(row["category"] for row in rows)))
    print(f"aspect 수: 사람이 승인 {human_aspects} → 정규화·중복 제거 후 {final_aspects}, aspect가 없는 리뷰 {sum(not r['label']['aspects'] for r in rows)}건")
    print(f"초안에서 사람이 수정한 리뷰 {sum(row['decision']['edited'] for row in gold)}건 / {len(gold)}건")
    for row in rows:
        conflicts = conflicting_sentiments(row["label"])
        if conflicts:
            print(f"확인 필요: {row['review_id']} 같은 aspect·attribute에 sentiment가 둘 다 달림 {conflicts}")


if __name__ == "__main__":
    main()
