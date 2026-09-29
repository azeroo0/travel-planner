"""Base·LoRA·QLoRA 리뷰 분석 결과를 동일한 Gold Set으로 평가한다.

예시:
  python -m travel_planner.knk.evaluate_models \
    --gold datas/knk/out/runs/pilot/test/gold.jsonl \
    --prediction base=predictions/base.jsonl \
    --prediction lora=predictions/lora.jsonl \
    --prediction qlora=predictions/qlora.jsonl \
    --out evaluation/results.json

각 prediction JSONL은 review_id와 label 필드를 포함해야 한다.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import evaluate_records
from .wandb_logging import log_evaluation_report


def read_jsonl(path: Path) -> tuple[dict[str, dict], int]:
    records: dict[str, dict] = {}
    invalid = 0
    with path.open(encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict) or not isinstance(record.get("review_id"), str):
                    invalid += 1
                    continue
                records[record["review_id"]] = record
            except json.JSONDecodeError:
                invalid += 1
    return records, invalid


def parse_prediction(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("예상 형식: model_name=prediction.jsonl")
    return name, Path(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Base/LoRA/QLoRA 리뷰 분석 결과 평가")
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--prediction", type=parse_prediction, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--wandb-project")
    parser.add_argument("--wandb-run-name", default="knk-review-evaluation")
    args = parser.parse_args()

    gold, gold_invalid = read_jsonl(args.gold)
    report: dict[str, Any] = {
        "gold_path": str(args.gold),
        "gold_records": len(gold),
        "gold_invalid_lines": gold_invalid,
        "models": {},
    }
    for name, path in args.prediction:
        predictions, invalid = read_jsonl(path)
        result = evaluate_records(gold, predictions)
        result["prediction_path"] = str(path)
        result["invalid_lines"] = invalid
        report["models"][name] = result
        print(
            f"{name}: aspect F1={result['aspect']['f1']:.4f}, "
            f"evidence={result['evidence_in_source_rate']:.4f}, "
            f"record exact={result['record_exact_match']:.4f}"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"결과 저장: {args.out}")
    if args.wandb_project:
        log_evaluation_report(report, project=args.wandb_project, run_name=args.wandb_run_name)
        print(f"W&B 기록 완료: {args.wandb_project}/{args.wandb_run_name}")


if __name__ == "__main__":
    main()
