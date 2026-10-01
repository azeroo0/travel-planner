"""W&B 기록 보조 함수."""
import json
from pathlib import Path
from typing import Any

def read_training_state(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8")).get("log_history", [])

def log_training_state(state_path: Path, *, project: str, run_name: str, config: dict[str, Any] | None = None) -> None:
    import wandb
    run = wandb.init(project=project, name=run_name, config=config or {})
    for row in read_training_state(state_path):
        metrics = {k: v for k, v in row.items() if k not in {"step", "epoch"}}
        if metrics: wandb.log(metrics, step=row.get("step"))
    run.summary["training_state_path"] = str(state_path)
    run.finish()

def log_evaluation_report(report: dict[str, Any], *, project: str, run_name: str) -> None:
    import wandb
    run = wandb.init(project=project, name=run_name, job_type="evaluation")
    table = wandb.Table(columns=["model", "aspect_f1", "evidence_rate", "record_exact_match"])
    for model, result in report["models"].items():
        f1 = result["aspect"]["f1"]; evidence = result["evidence_in_source_rate"]; exact = result["record_exact_match"]
        table.add_data(model, f1, evidence, exact)
        run.summary[f"{model}/aspect_f1"] = f1
        run.summary[f"{model}/evidence_in_source_rate"] = evidence
        run.summary[f"{model}/record_exact_match"] = exact
    run.log({"model_comparison": table})
    run.summary["gold_records"] = report["gold_records"]
    run.finish()
