"""End-to-end TripFit evaluation helpers."""

from __future__ import annotations

import gc
import hashlib
import html
import itertools
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable

from .metrics import evaluate_records

MODES = {"base", "lora", "qlora", "ollama"}


def _resolve_path(value: str | None, base_dir: Path) -> str | None:
    if value is None:
        return None
    path = Path(value)
    return str(path if path.is_absolute() else (base_dir / path).resolve())


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    models = config.get("models")
    if not isinstance(models, list) or not 1 <= len(models) <= 5:
        raise ValueError("models에는 평가할 모델을 1개 이상 5개 이하로 지정해야 합니다")
    names: set[str] = set()
    normalized_models = []
    for index, model in enumerate(models):
        if not isinstance(model, dict):
            raise ValueError(f"models[{index}]는 객체여야 합니다")
        name, model_id, mode = model.get("name"), model.get("model_id"), model.get("mode", "base")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"models[{index}].name이 필요합니다")
        if name in names:
            raise ValueError(f"모델 이름이 중복됩니다: {name}")
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError(f"models[{index}].model_id가 필요합니다")
        if mode not in MODES:
            raise ValueError(f"지원하지 않는 mode입니다: {mode}")
        adapter_path = model.get("adapter_path")
        if mode in {"lora", "qlora"} and not adapter_path:
            raise ValueError(f"{name}: {mode} 모델에는 adapter_path가 필요합니다")
        if mode in {"base", "ollama"} and adapter_path:
            raise ValueError(f"{name}: {mode} 모델에는 adapter_path를 지정하지 않습니다")
        names.add(name)
        normalized_models.append({
            "name": name,
            "model_id": model_id,
            "mode": mode,
            "adapter_path": adapter_path,
            "max_new_tokens": int(model.get("max_new_tokens", 512)),
            "load_in_4bit": bool(model.get("load_in_4bit", False)),
            # ollama 모드 전용: model_id는 Ollama 모델 이름이고 base_url은 서버 주소, prompt는 요청 프롬프트 형식이다
            "base_url": model.get("base_url", "http://localhost:11434"),
            "prompt": model.get("prompt", "tripfit"),
        })
    gold = config.get("gold")
    if not isinstance(gold, str) or not gold.strip():
        raise ValueError("gold 경로가 필요합니다")
    normalized = dict(config)
    normalized["gold"] = gold
    normalized["models"] = normalized_models
    normalized.setdefault("judge", {})
    return normalized


def load_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("설정 파일의 최상위 값은 객체여야 합니다")
    config = validate_config(raw)
    base_dir = path.parent.resolve()
    config["gold"] = _resolve_path(config["gold"], base_dir)
    for model in config["models"]:
        model["adapter_path"] = _resolve_path(model.get("adapter_path"), base_dir)
    return config


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number} JSON 오류: {error}") from error
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} 레코드는 객체여야 합니다")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_prediction_record(record: dict[str, Any], model_name: str) -> dict[str, Any]:
    label = record.get("label")
    if not isinstance(label, dict):
        label = record.get("prediction")
    valid = isinstance(label, dict) and bool(record.get("json_valid", True))
    if not isinstance(label, dict):
        label = {"traveler_context": [], "aspects": []}
    return {
        "review_id": record.get("review_id"),
        "place_id": record.get("place_id"),
        "category": record.get("category"),
        "review": record.get("review", ""),
        "model_name": model_name,
        "raw_output": record.get("raw_output", ""),
        "label": label,
        "json_valid": valid,
        "inference_error": None if valid else "invalid_json",
        # 후처리 전 label과 후처리 내역. 모델이 스키마를 얼마나 어겼는지는 raw_label로 잰다.
        **{key: record[key] for key in ("raw_label", "salvaged", "postprocess_dropped") if key in record},
    }


def run_model(model_config: dict[str, Any], gold_path: Path, output_path: Path) -> dict[str, Any]:
    """Run one model using the repository inference implementation."""
    temporary_path = output_path.with_suffix(".raw.jsonl")
    if model_config["mode"] == "ollama":
        from travel_planner.model_cjm.ollama_infer import predict_ollama

        failed = predict_ollama(
            model=model_config["model_id"],
            input_file=gold_path,
            output_file=temporary_path,
            base_url=model_config["base_url"],
            prompt=model_config["prompt"],
            max_new_tokens=model_config["max_new_tokens"],
        )
        rows = [normalize_prediction_record(row, model_config["name"]) for row in read_jsonl(temporary_path)]
        write_jsonl(output_path, rows)
        temporary_path.unlink(missing_ok=True)
        return {"model": model_config["name"], "records": len(rows), "failed_requests": failed, "prediction_path": str(output_path)}

    from travel_planner.model_cjm.infer import predict

    predict(
        model_id=model_config["model_id"],
        mode=model_config["mode"],
        input_file=gold_path,
        output_file=temporary_path,
        adapter_path=model_config.get("adapter_path"),
        max_new_tokens=model_config["max_new_tokens"],
        load_in_4bit=model_config["load_in_4bit"],
    )
    rows = [normalize_prediction_record(row, model_config["name"]) for row in read_jsonl(temporary_path)]
    write_jsonl(output_path, rows)
    temporary_path.unlink(missing_ok=True)
    gc.collect()
    return {"model": model_config["name"], "records": len(rows), "prediction_path": str(output_path)}


def _by_id(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["review_id"]): row for row in rows if row.get("review_id") is not None}


def evaluate_prediction_files(gold_rows: list[dict[str, Any]], prediction_paths: dict[str, Path]) -> dict[str, Any]:
    gold = _by_id(gold_rows)
    results: dict[str, Any] = {"gold_records": len(gold), "models": {}}
    for model_name, path in prediction_paths.items():
        result = evaluate_records(gold, _by_id(read_jsonl(path)))
        result["prediction_path"] = str(path)
        results["models"][model_name] = result
    return results


def _judge_prompt(review: str, category: str, gold: dict[str, Any], candidate: dict[str, Any]) -> str:
    return f"""You are a strict evaluator for Korean travel-review extraction.
Compare the candidate with the human-approved gold label. Judge meaning, not length.
Evidence must be a verbatim substring of the review and support the claimed aspect.
Return JSON only with this shape:
{{"pass": true, "score": 0.0, "correctness": "pass|partial|fail", "completeness": "pass|partial|fail", "evidence_grounding": "pass|partial|fail", "evidence_minimality": "pass|partial|fail", "schema_adherence": "pass|fail", "error_tags": [], "reason": "short reason"}}

Category: {category}
Review: {review}
Gold: {json.dumps(gold, ensure_ascii=False)}
Candidate: {json.dumps(candidate, ensure_ascii=False)}
Score 1.0 means fully correct, 0.5 partially correct, and 0.0 materially incorrect.
"""


def _extract_json_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def _supports_temperature(model: str) -> bool:
    """GPT-5 계열과 o 시리즈 추론 모델은 temperature를 기본값(1)만 허용한다."""
    name = model.lower()
    return not (name.startswith("gpt-5") or re.match(r"o\d", name))


class JudgeCallError(RuntimeError):
    """재시도해도 Judge 호출이 실패했다."""


JUDGE_RETRY_STATUS = {429, 500, 502, 503, 504}
JUDGE_MAX_ATTEMPTS = 4
JUDGE_MAX_CONSECUTIVE_FAILURES = 5
JUDGE_SAMPLE_SEED = 42


def _retry_delay(attempt: int, response: Any) -> float:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    try:
        return min(float(retry_after), 60.0) if retry_after else min(2.0 ** attempt, 30.0)
    except ValueError:
        return min(2.0 ** attempt, 30.0)


def _post_with_retry(url: str, headers: dict[str, str], payload: dict[str, Any]) -> Any:
    """제한(429)·서버 오류·시간 초과만 재시도한다. 그 밖의 4xx(키 오류, 지원하지 않는 인자)는 바로 실패시킨다."""
    import requests

    last_error = "알 수 없는 오류"
    for attempt in range(JUDGE_MAX_ATTEMPTS):
        response = None
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=300)
        except (requests.Timeout, requests.ConnectionError) as error:
            last_error = type(error).__name__
        else:
            if response.status_code not in JUDGE_RETRY_STATUS:
                response.raise_for_status()
                return response
            last_error = f"HTTP {response.status_code}"
        time.sleep(_retry_delay(attempt, response))
    raise JudgeCallError(f"{JUDGE_MAX_ATTEMPTS}번 시도했지만 실패했습니다: {last_error}")


def call_openai_judge(*, model: str, review: str, category: str, gold: dict[str, Any], candidate: dict[str, Any], api_key: str, base_url: str = "https://api.openai.com/v1/chat/completions") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Return only valid JSON."},
            {"role": "user", "content": _judge_prompt(review, category, gold, candidate)},
        ],
    }
    if _supports_temperature(model):
        payload["temperature"] = 0
    response = _post_with_retry(base_url, {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, payload)
    content = response.json()["choices"][0]["message"]["content"]
    # 파싱에 실패한 응답은 0점이 아니라 점수 없음으로 둔다. 모델 탓이 아니라 Judge 응답 문제이기 때문이다.
    return _extract_json_object(content) or {"pass": None, "score": None, "error_tags": ["invalid_judge_json"], "raw": content[:500]}


def _judge_ok(result: dict[str, Any]) -> bool:
    return result.get("score") is not None


def sample_review_ids(review_ids: list[str], limit: int | None, seed: int = JUDGE_SAMPLE_SEED) -> list[str]:
    """limit개를 고정 seed로 골라 원래 순서를 지킨다. 파일 앞부분만 자르면 한 카테고리만 뽑히기 때문이다.

    limit이 커질수록 앞서 뽑은 리뷰가 그대로 포함되어, 소량 확인에서 받은 결과를 전체 실행이 이어 쓴다.
    """
    if limit is None or limit >= len(review_ids):
        return list(review_ids)
    ranked = sorted(review_ids, key=lambda review_id: hashlib.sha256(f"{seed}:{review_id}".encode()).hexdigest())
    chosen = set(ranked[:limit])
    return [review_id for review_id in review_ids if review_id in chosen]


def _read_done_judgements(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    if not path.exists():
        return {}
    rows = read_jsonl(path)
    return {(row["review_id"], row["model"]): row for row in rows if _judge_ok(row["judge"])}


def summarize_judge(rows: list[dict[str, Any]], model_names: list[str], failed: dict[str, int]) -> dict[str, Any]:
    summary = {name: {"items": 0, "pass_rate": 0.0, "mean_score": 0.0, "errors": failed.get(name, 0)} for name in model_names}
    for row in rows:
        item = summary[row["model"]]
        item["items"] += 1
        item["pass_rate"] += float(bool(row["judge"].get("pass")))
        item["mean_score"] += float(row["judge"]["score"])
    for item in summary.values():
        if item["items"]:
            item["pass_rate"] /= item["items"]
            item["mean_score"] /= item["items"]
    return summary


def run_judge(*, gold_rows: list[dict[str, Any]], prediction_paths: dict[str, Path], model: str, api_key: str, output_path: Path,
              limit: int | None = None, dry_run: bool = False) -> dict[str, Any]:
    """리뷰 x 모델마다 Judge를 한 번씩 부른다.

    결과는 호출마다 output_path에 이어 쓰고, 다시 실행하면 이미 받은 것은 건너뛴다 (같은 호출에 비용을 다시 쓰지 않는다).
    호출이 재시도 끝에 실패한 항목은 건너뛰고 errors로 센다. 연속으로 실패하면 서비스 문제로 보고 멈춘다.
    """
    gold = _by_id(gold_rows)
    predictions = {name: _by_id(read_jsonl(path)) for name, path in prediction_paths.items()}
    review_ids = sample_review_ids(list(gold), limit)
    done = _read_done_judgements(output_path)
    todo = [(review_id, name) for review_id in review_ids for name in predictions if (review_id, name) not in done]
    if dry_run:
        return {"planned_calls": len(todo), "already_done": len(review_ids) * len(predictions) - len(todo), "reviews": len(review_ids)}

    failed: dict[str, int] = {name: 0 for name in predictions}
    consecutive = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as sink:
        for index, (review_id, name) in enumerate(todo, start=1):
            gold_row = gold[review_id]
            candidate = predictions[name].get(review_id, {}).get("label", {"traveler_context": [], "aspects": []})
            try:
                result = call_openai_judge(model=model, review=gold_row.get("review", ""), category=gold_row.get("category", ""),
                                           gold=gold_row.get("label", {}), candidate=candidate, api_key=api_key)
            except JudgeCallError as error:
                failed[name] += 1
                consecutive += 1
                print(f"[judge {index}/{len(todo)}] 실패 {name} {review_id}: {error}", flush=True)
                if consecutive >= JUDGE_MAX_CONSECUTIVE_FAILURES:
                    raise JudgeCallError(f"연속 {consecutive}번 실패해서 멈춥니다. 같은 명령을 다시 실행하면 이어서 진행합니다") from error
                continue
            consecutive = 0
            if not _judge_ok(result):
                failed[name] += 1
                print(f"[judge {index}/{len(todo)}] 응답 해석 실패 {name} {review_id}", flush=True)
                continue
            sink.write(json.dumps({"review_id": review_id, "model": name, "judge": result}, ensure_ascii=False) + "\n")
            sink.flush()
            print(f"[judge {index}/{len(todo)}] {name} {review_id}", flush=True)

    wanted = set(review_ids)
    rows = [row for row in _read_done_judgements(output_path).values() if row["review_id"] in wanted and row["model"] in predictions]
    return summarize_judge(rows, list(prediction_paths), failed)


def build_human_rows(gold_rows: list[dict[str, Any]], prediction_paths: dict[str, Path]) -> list[dict[str, Any]]:
    gold = _by_id(gold_rows)
    predictions = {name: _by_id(read_jsonl(path)) for name, path in prediction_paths.items()}
    rows = []
    for review_id, gold_row in gold.items():
        if len(predictions) == 1:
            model_name = next(iter(predictions))
            rows.append({
                "review_id": review_id,
                "review": gold_row.get("review", ""),
                "category": gold_row.get("category", ""),
                "gold_label": gold_row.get("label", {}),
                "left_model": "Gold",
                "right_model": model_name,
                "left_label": gold_row.get("label", {}),
                "right_label": predictions[model_name].get(review_id, {}).get("label", {}),
                "scores": {},
            })
            continue
        for left, right in itertools.combinations(predictions, 2):
            rows.append({
                "review_id": review_id,
                "review": gold_row.get("review", ""),
                "category": gold_row.get("category", ""),
                "gold_label": gold_row.get("label", {}),
                "left_model": left,
                "right_model": right,
                "left_label": predictions[left].get(review_id, {}).get("label", {}),
                "right_label": predictions[right].get(review_id, {}).get("label", {}),
                "scores": {},
            })
    return rows


def _json_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c")


def build_human_review_html(rows: list[dict[str, Any]], model_names: list[str]) -> str:
    payload = _json_script(rows)
    return """<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>TripFit Human Evaluation</title><style>body{font-family:system-ui,sans-serif;background:#f5f7fb;color:#172033;margin:0}main{max-width:1200px;margin:32px auto;padding:0 20px}.bar,.card{background:#fff;border:1px solid #dfe5ef;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 4px 16px #1720330d}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}pre{white-space:pre-wrap;background:#f7f9fc;padding:14px;border-radius:10px;max-height:420px;overflow:auto}button,select{font:inherit;padding:9px 12px;border:1px solid #c8d2e2;border-radius:9px;background:#fff}button{cursor:pointer;background:#1c5fd4;color:#fff;border:0;margin-right:8px}label{margin-right:12px}.muted{color:#66738a}.score{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style></head><body><main><h1>TripFit 인간 평가</h1><div class=\"bar\"><span id=\"progress\"></span> <button onclick=\"previous()\">이전</button><button onclick=\"next()\">다음</button><button onclick=\"downloadResults()\">결과 다운로드</button></div><section id=\"item\"></section></main><script>""" + payload + r""";const rows=JSON.parse(document.currentScript.previousSibling.textContent);let index=0;const answers=rows.map(r=>r.scores||{});function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function opts(v){return ['','pass','partial','fail'].map(x=>`<option value="${x}" ${x===v?'selected':''}>${x||'선택'}</option>`).join('')}function render(){const r=rows[index],a=answers[index];document.querySelector('#progress').textContent=`${index+1} / ${rows.length} · ${r.review_id} · ${r.left_model} vs ${r.right_model}`;document.querySelector('#item').innerHTML=`<div class="card"><h2>리뷰</h2><p>${esc(r.review)}</p><p class="muted">category: ${esc(r.category)}</p></div><div class="grid"><div class="card"><h2>A · ${esc(r.left_model)}</h2><pre>${esc(JSON.stringify(r.left_label,null,2))}</pre></div><div class="card"><h2>B · ${esc(r.right_model)}</h2><pre>${esc(JSON.stringify(r.right_label,null,2))}</pre></div></div><div class="card"><h2>평가</h2><div class="score"><label>정확성 <select data-k="correctness">${opts(a.correctness)}</select></label><label>완전성 <select data-k="completeness">${opts(a.completeness)}</select></label><label>Evidence 근거성 <select data-k="evidence">${opts(a.evidence)}</select></label><label>유용성 <select data-k="usefulness">${opts(a.usefulness)}</select></label><label>선호 <select data-k="preference"><option value="">선택</option><option>A</option><option>B</option><option>tie</option></select></label></div><p><label>메모 <input data-k="note" size="70" value="${esc(a.note||'')}"></label></p></div>`;document.querySelectorAll('[data-k]').forEach(el=>{el.value=a[el.dataset.k]||'';el.onchange=()=>{a[el.dataset.k]=el.value}})}function next(){if(index<rows.length-1){index++;render()}}function previous(){if(index>0){index--;render()}}function downloadResults(){const blob=new Blob([rows.map((r,i)=>JSON.stringify({...r,scores:answers[i]})).join('\n')+'\n'],{type:'application/jsonl'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='human_review_results.jsonl';a.click()}render();</script></body></html>"""


def build_report_html(metrics: dict[str, Any], human_review_filename: str) -> str:
    rows = []
    for name, result in metrics.get("models", {}).items():
        rows.append(f"<tr><td>{html.escape(name)}</td><td>{result.get('aspect', {}).get('f1', 0):.4f}</td><td>{result.get('aspect_with_evidence', {}).get('f1', 0):.4f}</td><td>{result.get('evidence_in_source_rate', 0):.4f}</td><td>{result.get('record_exact_match', 0):.4f}</td><td>{result.get('json_success_rate', 0):.4f}</td><td>{result.get('schema_valid_rate', 0):.4f}</td></tr>")
    judge = metrics.get("judge", {})
    judge_rows = []
    for name, result in judge.get("results", {}).items():
        judge_rows.append(f"<tr><td>{html.escape(name)}</td><td>{result.get('pass_rate', 0):.4f}</td><td>{result.get('mean_score', 0):.4f}</td><td>{result.get('items', 0)}</td><td>{result.get('errors', 0)}</td></tr>")
    judge_section = "<p>GPT Judge를 실행하지 않았습니다.</p>"
    if judge_rows:
        judge_section = f"<table><thead><tr><th>모델</th><th>Pass Rate</th><th>평균 점수</th><th>샘플 수</th><th>Judge 오류</th></tr></thead><tbody>{''.join(judge_rows)}</tbody></table>"
    return f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>TripFit Evaluation Report</title><style>body{{font-family:system-ui,sans-serif;background:#f5f7fb;color:#172033;margin:0}}main{{max-width:1180px;margin:32px auto;padding:0 20px}}.card{{background:#fff;border:1px solid #dfe5ef;border-radius:14px;padding:20px;margin:16px 0;box-shadow:0 4px 16px #1720330d}}table{{border-collapse:collapse;width:100%;background:#fff}}th,td{{border-bottom:1px solid #e6ebf2;padding:12px;text-align:left}}th{{background:#eef3fa}}a{{color:#165bc4}}</style></head><body><main><h1>TripFit 평가 리포트</h1><div class=\"card\"><p>Gold records: {metrics.get('gold_records', 0)}</p><p>인간 평가: <a href=\"{html.escape(human_review_filename)}\">human_review.html 열기</a></p></div><div class=\"card\"><h2>자동 정량 평가</h2><table><thead><tr><th>모델</th><th>Aspect F1</th><th>Evidence 포함 F1</th><th>Evidence 원문 포함</th><th>Record Exact</th><th>JSON 성공</th><th>Schema Valid</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><div class=\"card\"><h2>GPT Judge</h2>{judge_section}</div><div class=\"card\"><h2>해석</h2><p>최종 모델 선택은 Aspect F1 하나가 아니라 구조화 정확도, Evidence 근거성, JSON 안정성, GPT Judge와 인간 평가 결과를 함께 확인해야 합니다.</p></div></main></body></html>"""


def build_human_review_html_v2(rows: list[dict[str, Any]]) -> str:
    """Build the final human-review UI with embedded JSON data."""
    payload = _json_script(rows)
    return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TripFit 인간 평가</title>
<style>body{font-family:system-ui,sans-serif;background:#f5f7fb;color:#172033;margin:0}main{max-width:1180px;margin:32px auto;padding:0 20px}.card{background:#fff;border:1px solid #dfe5ef;border-radius:14px;padding:18px;margin:14px 0;box-shadow:0 4px 16px #1720330d}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}pre{white-space:pre-wrap;background:#f7f9fc;padding:14px;border-radius:10px;max-height:420px;overflow:auto}button,select,input{font:inherit;padding:9px 12px;border:1px solid #c8d2e2;border-radius:9px;background:#fff}button{cursor:pointer;background:#1c5fd4;color:#fff;border:0;margin-right:8px}.muted{color:#66738a}.score{display:flex;gap:12px;flex-wrap:wrap}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style>
</head><body><main><h1>TripFit 인간 평가</h1><div class="card"><span id="progress"></span> <button id="prev">이전</button><button id="next">다음</button><button id="download">결과 다운로드</button></div><section id="item"></section>
<script id="data" type="application/json">__PAYLOAD__</script><script>
const rows=JSON.parse(document.getElementById('data').textContent);let index=0;const answers=rows.map(r=>r.scores||{});
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const opts=v=>['','pass','partial','fail'].map(x=>`<option value="${x}" ${x===v?'selected':''}>${x||'선택'}</option>`).join('');
function render(){const r=rows[index],a=answers[index];document.getElementById('progress').textContent=`${index+1} / ${rows.length} · ${r.review_id} · ${r.left_model} vs ${r.right_model}`;document.getElementById('item').innerHTML=`<div class="card"><h2>리뷰</h2><p>${esc(r.review)}</p><p class="muted">category: ${esc(r.category)}</p></div><div class="grid"><div class="card"><h2>A · ${esc(r.left_model)}</h2><pre>${esc(JSON.stringify(r.left_label,null,2))}</pre></div><div class="card"><h2>B · ${esc(r.right_model)}</h2><pre>${esc(JSON.stringify(r.right_label,null,2))}</pre></div></div><div class="card"><h2>평가</h2><div class="score"><label>정확성 <select data-k="correctness">${opts(a.correctness)}</select></label><label>완전성 <select data-k="completeness">${opts(a.completeness)}</select></label><label>Evidence <select data-k="evidence">${opts(a.evidence)}</select></label><label>유용성 <select data-k="usefulness">${opts(a.usefulness)}</select></label><label>선호 <select data-k="preference"><option value="">선택</option><option>A</option><option>B</option><option>tie</option></select></label></div><p><label>메모 <input data-k="note" size="60" value="${esc(a.note||'')}"></label></p></div>`;document.querySelectorAll('[data-k]').forEach(el=>{el.value=a[el.dataset.k]||'';el.onchange=()=>a[el.dataset.k]=el.value})}
document.getElementById('prev').onclick=()=>{if(index){index--;render()}};document.getElementById('next').onclick=()=>{if(index<rows.length-1){index++;render()}};document.getElementById('download').onclick=()=>{const blob=new Blob([rows.map((r,i)=>JSON.stringify({...r,scores:answers[i]})).join('\\n')+'\\n'],{type:'application/jsonl'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='human_review_results.jsonl';a.click()};render();
</script></main></body></html>""".replace("__PAYLOAD__", payload)


def build_human_review_html(rows: list[dict[str, Any]], model_names: list[str] | None = None) -> str:
    return build_human_review_html_v2(rows)
