"""Base/LoRA/QLoRA 출력의 블라인드 Human Evaluation 파일 생성·집계."""

import argparse
import json
import random
from collections import Counter
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", nargs="+", required=True, help="name=JSONL")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    models = {}
    for value in args.predictions:
        name, _, path = value.partition("=")
        models[name] = {json.loads(line)["review_id"]: json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()}
    ids = sorted(set.intersection(*(set(rows) for rows in models.values())))
    rng = random.Random(args.seed)
    output = []
    for review_id in ids:
        order = list(models)
        rng.shuffle(order)
        first = models[order[0]][review_id]
        output.append({"review_id": review_id, "review": first.get("review", ""), "a": {"model": order[0], "label": first.get("label")}, "b": {"model": order[1], "label": models[order[1]][review_id].get("label")}, "scores": {"a": {}, "b": {}, "preference": ""}})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in output) + "\n", encoding="utf-8")
    print(f"Human Evaluation 입력 {len(output)}건 → {args.out}")


def aggregate(path: Path) -> dict:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    preference = Counter(row.get("scores", {}).get("preference") for row in rows)
    return {"items": len(rows), "preference": dict(preference)}


if __name__ == "__main__":
    main()
