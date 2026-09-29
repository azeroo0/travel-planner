# TripFit 평가 파이프라인

이 폴더의 파이프라인은 팀원이 서로 다른 Base/LoRA/QLoRA 모델을 학습했더라도 동일한 Gold Test Set에 대해 직접 추론하고, 같은 JSONL 형식으로 저장한 뒤 같은 기준으로 비교합니다. 모델은 1개부터 5개까지 등록할 수 있습니다.

## 준비

`config.example.json`을 복사해 `config.json`을 만들고, 다섯 모델의 `model_id`, `mode`, `adapter_path`를 실제 값으로 바꿉니다.

```bash
cp evaluation/config.example.json evaluation/config.json
```

`mode`는 `base`, `lora`, `qlora` 중 하나입니다. LoRA/QLoRA는 반드시 학습된 adapter 경로를 지정해야 합니다. 설정 파일의 상대 경로는 설정 파일이 있는 `evaluation/` 폴더를 기준으로 해석합니다.

GPT Judge를 사용하려면 `evaluation/.env.example`을 복사해 `evaluation/.env`를 만들고 API Key를 입력합니다.

```bash
cp evaluation/.env.example evaluation/.env
# evaluation/.env 안의 OPENAI_API_KEY 값을 실제 Key로 변경
```

실행 시 `evaluation/.env`를 자동으로 읽습니다. 이미 셸 환경 변수에 `OPENAI_API_KEY`가 있으면 셸 환경 변수 값을 우선하며, 다른 파일을 사용하려면 `--env-file`을 지정합니다.

## 실행

모델을 직접 로드해 다섯 개 prediction JSONL을 만들고, 자동 평가와 인간 평가 HTML을 생성합니다.

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --out evaluation/runs/2026-09-29
```

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --out evaluation/runs/2026-09-29 \
  --env-file /path/to/team-evaluation.env
```

생성물은 다음과 같습니다.

```text
evaluation/runs/2026-09-29/
├── predictions/<model>.jsonl
├── automatic_metrics.json
├── judge_results.jsonl
├── human_review.html
├── run_manifest.json
└── report.html
```

`report.html`은 자동 평가 요약과 인간 평가 링크를 보여줍니다. `human_review.html`은 모델 쌍을 A/B로 보여주며, 정확성·완전성·Evidence 근거성·유용성·선호·메모를 입력하고 JSONL로 다운로드할 수 있습니다.

같은 모델을 여러 test로 평가하려면 `--gold`로 config의 `gold`를 덮어씁니다. 결과 폴더는 test마다 나눕니다.

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --gold datasets/v2/test_real.jsonl \
  --out evaluation/runs/2026-09-29-real \
  --skip-judge
```

추론은 학습과 같은 `prompt.build_prompt`를 씁니다. `model_id`는 adapter를 학습한 Base와 정확히 같아야 합니다 (adapter의 `adapter_config.json`에 `base_model_name_or_path`가 있습니다). 8GB GPU에서는 Base 모델에 `"load_in_4bit": true`를 지정해야 올라갑니다.

GPT Judge를 실행하지 않고 자동 평가와 인간 평가만 만들려면 다음처럼 실행합니다.

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --out evaluation/runs/2026-09-29 \
  --skip-judge
```

이미 생성된 prediction JSONL을 재사용하려면 다음 옵션을 사용합니다.

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --out evaluation/runs/2026-09-29 \
  --skip-inference
```

### GPT Judge 실행

Judge는 리뷰 1건과 모델 1개마다 API를 한 번씩 부릅니다. 리뷰가 172건이고 모델이 2개면 344회입니다. 사용할 수 있는 모델은 `gpt-5-mini`, `gpt-4o-mini`, `gpt-4.1-mini`이고, `config.json`의 `judge.model` 또는 `--judge-model`로 고릅니다. GPT-5 계열에는 temperature를 보내지 않습니다.

1. 호출 없이 횟수만 확인합니다.

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --out evaluation/runs/calibration \
  --skip-inference --judge-limit 20 --judge-dry-run
```

2. 소량(20건)으로 응답 형식과 점수를 확인합니다. `--judge-limit`은 파일 앞부분이 아니라 고정 seed로 카테고리가 섞이게 뽑습니다.

```bash
uv run python -m evaluation.run_pipeline \
  --config evaluation/config.json \
  --out evaluation/runs/calibration \
  --skip-inference --judge-limit 20
```

3. 문제가 없으면 `--judge-limit` 없이 같은 `--out`으로 다시 실행합니다. 결과는 `judge_results_<모델>.jsonl`에 호출마다 이어 쓰고, 이미 받은 항목은 건너뛰므로 2번의 20건에는 비용을 다시 쓰지 않습니다. 중간에 멈춰도 같은 명령으로 이어집니다.

- 제한(429)·서버 오류·시간 초과는 4번까지 재시도하고, 그래도 실패한 항목은 건너뛰어 `errors`로 셉니다. 연속 5번 실패하면 멈춥니다. 키 오류 같은 4xx는 바로 멈춥니다.
- Judge가 JSON이 아닌 답을 준 경우는 0점이 아니라 점수 없음으로 두어 평균에서 제외하고 `errors`로 셉니다.
- 다른 Judge 모델로 다시 보려면 `--judge-model gpt-4.1-mini`처럼 지정합니다. 결과 파일이 모델별로 나뉩니다.

## 후처리와 오류 분석

추론 결과는 `travel_planner.model_cjm.postprocess`가 정리합니다. 잘린 JSON에서 끝까지 쓰인 aspect만 건져 오고, 스키마에 없는 값과 원문에 없는 evidence를 버리고, 같은 라벨의 중복을 없앱니다. 정리 전 label은 `raw_label`에 남으므로 `automatic_metrics.json`의 `raw_schema_valid_rate`가 모델이 실제로 스키마를 지킨 비율이고, `schema_valid_rate`는 후처리 뒤 값이라 높게 나옵니다. `json_success_rate`는 복구 전 기준이라 복구한 레코드 수는 `salvaged_records`로 따로 봅니다.

이미 만든 예측 파일도 GPU 없이 다시 정리할 수 있습니다.

```bash
uv run python -m travel_planner.model_cjm.postprocess \
  --input evaluation/runs/qwen-real/predictions/qwen3_4b_qlora_v2.jsonl \
  --output evaluation/runs/qwen-real/predictions_postprocessed.jsonl
```

오류를 유형별로 세려면 다음처럼 실행합니다. 없는 aspect를 만든 경우, 정답이 빈 리뷰에서 만든 경우, 스키마 위반, 놓침을 나눠 보여 줍니다.

```bash
uv run python -m evaluation.error_analysis \
  --gold datasets/v2/test_real.jsonl \
  --predictions evaluation/runs/qwen-real/predictions/qwen3_4b_qlora_v2.jsonl \
  --out evaluation/runs/qwen-real/error_analysis.json
```

## 평가 기준

자동 평가는 기존 Gold 기준과 동일하게 다음을 계산합니다.

- Aspect Precision/Recall/F1: `category + attribute + sentiment` 일치
- Evidence 포함 F1: 위 결과에 Evidence까지 정확히 일치
- Traveler Context F1
- Evidence 다중 정답 F1: 위 결과에서 예측 evidence가 사람이 그 aspect에 단 evidence 중 하나와 글자 IoU 0.5 이상 겹치면 일치. 긴 실제 리뷰는 같은 판단을 뒷받침하는 문장이 여럿이라, `test_real_gold`처럼 `label_raw`에 원래 evidence가 남은 Gold에서만 엄격 지표와 달라진다 (합성 test는 IoU 지표와 같다)
- Evidence 원문 포함 비율
- Record Exact Match
- JSON 성공률
- Schema Validity 비율

GPT Judge는 Gold Label과 모델 Label을 함께 보고 correctness, completeness, evidence grounding, evidence minimality, schema adherence를 `pass/partial/fail`과 0~1 점수로 평가합니다. Judge 결과는 자동 정량 지표를 대체하지 않고 보완 지표로 사용합니다.

💡 Evidence grounding은 모델이 제시한 근거가 실제 리뷰에 있고 선택한 aspect를 뒷받침하는지를 뜻합니다.

## 주의

- 설정 파일은 모델을 1개 이상 5개 이하로 요구합니다. 모델이 1개면 자동 지표·GPT Judge를 단독 평가하고, 인간 평가 화면에서는 Gold와 후보 모델을 비교합니다.
- 다섯 모델은 한 번에 하나씩 로드되어 GPU 메모리를 재사용합니다.
- `--skip-inference`를 사용하면 기존 prediction 파일이 반드시 존재해야 합니다.
- Test Set을 보고 모델 설정이나 checkpoint를 고르면 안 됩니다. checkpoint는 Validation Set에서 선택한 뒤 Test Set은 마지막에 한 번만 사용해야 합니다.
- GPT Judge 응답이 실패해도 자동 평가와 인간 평가 파일은 생성되며, `run_manifest.json`에 상태가 기록됩니다.
