"""Hugging Face에 올릴 배포 폴더를 만든다. 올릴 파일만 모으고 나머지는 두고 온다.

  uv run python deploy/build_hf_folder.py

만드는 것
  deploy/tripfit-busan-review-qwen3-4b-qlora-v3/   ← 이 폴더만 올린다
    README.md                     model card
    adapter_config.json, adapter_model.safetensors
    inference/                    저장소 없이 돌아가는 프롬프트·후처리·예제
  deploy/CHECKLIST.md             올리기 전에 사람이 확인할 것 (올리는 폴더 밖에 둔다)

adapter의 checkpoint-*, training_args.bin, tokenizer 사본, 자동 생성 README는 넣지 않는다.
후처리 코드는 저장소의 원본에서 생성하므로 원본이 바뀌면 이 스크립트를 다시 실행한다.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datas.common.schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS  # noqa: E402
from datas.common.topic_keywords import TOPIC_KEYWORDS  # noqa: E402

SOURCE = ROOT / "models/qwen3_4b_qlora_busan_v3"
NAME = "tripfit-busan-review-qwen3-4b-qlora-v3"
TARGET = ROOT / "deploy" / NAME
ADAPTER_FILES = ("adapter_config.json", "adapter_model.safetensors")

MODEL_CARD = """---
language:
- ko
base_model: Qwen/Qwen3-4B-Instruct-2507
library_name: peft
pipeline_tag: text-generation
tags:
- lora
- qlora
- peft
- korean
- review-analysis
- information-extraction
---

# TripFit 부산 리뷰 구조화 (Qwen3-4B QLoRA v3)

부산의 호텔·식당·관광지 리뷰에서 **aspect(주제), attribute(상태), sentiment(평가), evidence(근거 구절)** 와
동행자(traveler_context)를 JSON으로 뽑는 **LoRA adapter**입니다. 원본 모델 [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
위에 붙여서 씁니다.

*English: a QLoRA adapter for Qwen3-4B-Instruct-2507 that extracts aspect / attribute / sentiment / evidence records from Korean travel reviews of Busan. Post-processing is required for the reported results.*

## ⚠️ 먼저 읽어 주세요

- **후처리를 함께 써야 합니다.** 실제 리뷰에서 후처리 없이는 이 모델이 정답의 약 1.5배를 지어냅니다(리뷰가 말하지 않은 주차 같은 aspect에 관계없는 구절을 근거로 붙입니다). 후처리는 `inference/tripfit_postprocess.py`에 있습니다.
- **학습 데이터는 전부 합성 리뷰입니다.** 실제 사용자가 쓴 리뷰가 아닙니다.
- **관광지는 성능이 낮습니다**(아래 표). 호텔·식당 리뷰에서 더 믿을 만합니다.
- 평가는 **사람이 승인한 실제 리뷰 50건**으로 했습니다. 표본이 작아 **±0.05 안팎의 오차**가 있으니 작은 차이는 믿지 마세요.

## 입력과 출력

입력은 장소 카테고리(`hotel` · `restaurant` · `attraction`)와 리뷰 원문입니다. 학습 때 쓴 프롬프트(`inference/tripfit_prompt.py`)를 그대로 써야 합니다.

```json
{"traveler_context": ["couple"],
 "aspects": [{"category": "cleanliness", "attribute": "clean", "sentiment": "positive", "evidence": "객실이 깨끗해서"}]}
```

- `evidence`는 리뷰 원문에 그대로 있는 구절입니다.
- 허용되는 aspect와 attribute는 카테고리마다 다릅니다(호텔 12종, 식당 13종, 관광지 11종).

## 사용 방법

```bash
pip install -r inference/requirements.txt
python inference/example.py --adapter . --category hotel --review "객실이 깨끗하고 직원분들도 친절했어요."
```

`example.py`는 Base 모델과 이 adapter를 불러와 생성하고 후처리까지 적용합니다. GPU가 작으면 `--load-in-4bit`를 쓰세요(평가도 4비트 NF4로 했습니다).
tokenizer는 Base 모델 것을 씁니다.

## 학습

| 항목 | 값 |
|---|---|
| Base | Qwen3-4B-Instruct-2507 |
| 방식 | QLoRA (4bit NF4), r=16, alpha=32, dropout 0.05, 대상 q/k/v/o_proj |
| 데이터 | 합성 부산 리뷰 2,578건 (호텔 567 · 식당 1,104 · 관광지 907), 검증 371건 |
| 하이퍼파라미터 | 3 epoch, lr 2e-4, 유효 batch 16, warmup 5%, seed 42 |
| 데이터 처리 | 중복 aspect 제거, 장소당 최대 15건, evidence 경계 정규화, 호텔 cleanliness·room_condition 라벨 통일 |

합성 리뷰는 로컬 LLM(`gemma4:e4b`)이 생성하고 같은 모델이 라벨링했습니다. 실제 리뷰(Tripadvisor 번역문)는 학습에 쓰지 않고 **평가에만** 썼습니다.

## 평가

사람이 원문과 대조해 승인한 **실제 리뷰 50건**(호텔 15 · 식당 20 · 관광지 15, 정답 aspect 143개)에서 잰 값입니다.
Aspect 지표는 category + attribute + sentiment가 모두 맞아야 정답입니다.

| | Precision | Recall | **F1** |
|---|---:|---:|---:|
| 후처리 없음 | 0.435 | 0.650 | 0.521 |
| **후처리 적용 (권장)** | 0.611 | 0.636 | **0.623** |

| 후처리 적용 후 | 값 |
|---|---:|
| Evidence F1 (글자 겹침 IoU 0.5 이상) | 0.445 |
| Evidence F1 (사람이 단 근거 여러 개 중 하나와 겹침) | 0.486 |
| Traveler Context F1 | 0.462 |
| 호텔 / 식당 / 관광지 Aspect F1 | 0.700 / 0.792 / **0.289** |
| JSON 성공률 · 후처리 전 스키마 준수율 | 100% · 98% |

- 같은 조건에서 비교한 다른 모델들(Qwen v2 0.605, 팀원 모델 0.596 · 0.574)과의 **차이는 통계적으로 구분되지 않았습니다**(부트스트랩 95% 신뢰구간이 0을 포함).
- LLM Judge(GPT-4.1-mini) 평균 0.465는 후처리 전 예측으로 잰 값이고, 같은 예측도 실행마다 ±0.02~0.03 흔들립니다.
- 합성 리뷰로 잰 점수는 실제 성능과 크게 달라서(같은 계열 모델 v2 기준 합성 0.78, 실제 0.52~0.62) 참고하지 마세요. 이 v3 adapter는 합성 test로 다시 재지 않았습니다.
- 평가 리뷰의 상당수(약 78%)가 외국어 리뷰의 기계번역문이라 원래 한국어 리뷰와 분포가 다를 수 있습니다.

## 알려진 한계

- **관광지**: Aspect F1이 0.3 안팎입니다. `scenery`의 종류, `slope_stairs`와 `walking_burden`의 경계 같은 라벨 기준이 모호한 부분이 있습니다.
- **attribute · sentiment**: aspect 이름이 맞은 것 중 sentiment는 약 80%, attribute는 약 86%만 맞았습니다(이전 버전 v2로 잰 값).
- 리뷰가 언급하지 않은 주제를 근거 없이 만드는 경향이 있고, 후처리가 그중 주제가 분명한 12개 aspect(주차, 사진 명소, 신선도, 대기시간, 소음, 화장실, 조식, 날씨, 계단, 가족 적합, 욕실 등)만 걸러 냅니다. `scenery`, `amenities`, `activity_variety` 같은 일반적인 aspect의 근거 없는 출력은 남습니다.
- 동행자(`traveler_context`)는 리뷰에 적힌 경우에만 답해야 하지만 추측해서 채우는 경우가 있습니다.
- 부산 광안리·수영구·남구 중심의 소수 리뷰로 평가했습니다. 다른 지역과 문체에서는 성능이 다를 수 있습니다.
- 리뷰 한 건의 결과를 그대로 사용자에게 보여주는 용도로는 권하지 않습니다. 장소별로 집계하는 용도에 적합합니다.

## 라이선스와 데이터

이 adapter는 Base 모델의 라이선스를 이어받습니다(Base 모델 페이지를 확인하세요).
학습 데이터는 합성이고, 평가에 쓴 실제 리뷰 원문은 재배포할 수 없어 공개하지 않습니다.
"""

CHECKLIST = """# 배포 전 확인 목록

이 폴더(`deploy/`)는 저장소에서 추적하지 않는 배포 준비 영역입니다. 아래를 확인한 뒤 올리세요.

## 올리는 것
`deploy/{name}/` 폴더 전체 (약 47MB)

- `README.md`, `adapter_config.json`, `adapter_model.safetensors`, `inference/`

## 올리지 않은 것 (의도)
| 파일 | 이유 |
|---|---|
| `checkpoint-*` | 학습 중간 산출물. 크고 필요 없음 |
| `training_args.bin`, `train_config.json` | 학습 내부 설정. 필요한 값은 model card에 적음 |
| `tokenizer.json`, `tokenizer_config.json`, `chat_template.jinja` | Base 모델의 사본. Base에서 받으면 됨 |
| 자동 생성된 `README.md` | `licence: license` 같은 빈 항목뿐이라 새 model card로 대체 |
| `datasets/v2/test_real*.jsonl` | Tripadvisor 리뷰 원문과 검수자 이름이 들어 있어 재배포 부적합 |

## 사람이 확인할 것
- [ ] **라이선스**: Base(Qwen3-4B-Instruct-2507)의 라이선스를 페이지에서 직접 확인. 확인되면 model card 머리말에 `license:` 항목을 추가
- [ ] **합성 데이터 생성 모델(`gemma4:e4b`)의 이용 조건**: 생성물을 다른 모델 학습에 쓰는 것에 제한이 없는지
- [ ] **model card의 수치**: 실제 리뷰 50건 기준이고 오차 ±0.05라는 문구가 유지되는지
- [ ] 처음에는 **비공개(private)** 저장소로 올려 확인한 뒤 공개할지 결정
- [ ] **Hugging Face 사용자명과 저장소 이름** 결정 (아래 명령의 `<사용자명>`)
- [ ] 올린 뒤 **깨끗한 환경에서 Hub의 adapter로 실제 리뷰 Gold 50건을 다시 평가**해서 같은 점수(후처리 적용 시 Aspect F1 0.62 안팎)가 나오는지 확인 (GPU 컴퓨터)

## 올리는 명령 (사용자님이 직접 실행)
```bash
hf auth login
hf repo create <사용자명>/{name} --private
hf upload <사용자명>/{name} deploy/{name} .
```

토큰은 채팅이나 파일에 적지 마세요.

## 다시 만들기
`uv run python deploy/build_hf_folder.py`
"""

EXAMPLE = '''"""이 adapter와 후처리를 함께 쓰는 예제. 저장소 없이 이 폴더만으로 돈다.

  python inference/example.py --adapter . --category hotel --review "객실이 깨끗하고 직원분들도 친절했어요."
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

BASE_MODEL = "Qwen/Qwen3-4B-Instruct-2507"


def main() -> None:
    parser = argparse.ArgumentParser(description="TripFit 리뷰 구조화 예제")
    parser.add_argument("--adapter", default=".", help="adapter 폴더 또는 Hugging Face 저장소 이름")
    parser.add_argument("--category", choices=("hotel", "restaurant", "attraction"), required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--load-in-4bit", action="store_true", help="4bit(NF4)로 올린다. 평가도 이 방식이었다")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    from tripfit_postprocess import build_label
    from tripfit_prompt import build_prompt

    if torch.cuda.is_available():
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        kwargs = {"device_map": "auto", "dtype": dtype}
    elif torch.backends.mps.is_available():  # Apple Silicon
        dtype = torch.bfloat16
        kwargs = {"device_map": {"": "mps"}, "dtype": dtype}
    else:  # CPU
        dtype = torch.float32
        kwargs = {"dtype": dtype}
    if args.load_in_4bit:
        if not torch.cuda.is_available():
            sys.exit("--load-in-4bit는 CUDA GPU에서만 됩니다. 이 옵션 없이 다시 실행하세요.")
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=dtype
        )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = PeftModel.from_pretrained(AutoModelForCausalLM.from_pretrained(BASE_MODEL, **kwargs), args.adapter).eval()

    prompt = tokenizer.apply_chat_template(
        build_prompt(args.category, args.review), tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to(model.device)
    with torch.inference_mode():
        output = model.generate(**inputs, do_sample=False, max_new_tokens=args.max_new_tokens, use_cache=True)
    raw = tokenizer.decode(output[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()

    result = build_label(raw, args.category, args.review)  # 잘린 JSON 복구, 스키마·근거 확인, 중복 제거
    print(json.dumps(result["label"], ensure_ascii=False, indent=2))
    if result.get("postprocess_dropped"):
        print("후처리로 버린 것:", result["postprocess_dropped"], file=sys.stderr)


if __name__ == "__main__":
    main()
'''

REQUIREMENTS = """transformers>=5.17.0
peft>=0.21.0
torch>=2.14.0
accelerate>=1.15.0
# 4bit로 올릴 때만 필요 (CUDA GPU)
bitsandbytes>=0.50.2
"""


def standalone_postprocess() -> str:
    """저장소의 postprocess.py에서 저장소 안 import 두 개를 값으로 바꿔 혼자 돌아가는 파일을 만든다."""
    source = (ROOT / "src/travel_planner/model_cjm/postprocess.py").read_text(encoding="utf-8")
    aspects = {name: sorted(values) for name, values in ASPECTS.items()}
    schema = (
        "# 저장소의 datas/common/schema.py에서 생성한 허용값\n"
        f"ASPECTS = {{name: frozenset(values) for name, values in {aspects!r}.items()}}\n"
        f"ATTRIBUTES = {ATTRIBUTES!r}\n"
        f"SENTIMENTS = frozenset({sorted(SENTIMENTS)!r})\n"
        f"TRAVELER_CONTEXTS = frozenset({sorted(TRAVELER_CONTEXTS)!r})\n"
    )
    patterns = {name: pattern.pattern for name, pattern in TOPIC_KEYWORDS.items()}
    topics = (
        "# 저장소의 datas/common/topic_keywords.py에서 생성한 주제 단어\n"
        f"TOPIC_KEYWORDS = {{name: re.compile(pattern) for name, pattern in {patterns!r}.items()}}\n\n\n"
        "def mentions_topic(aspect: str, evidence: str) -> bool:\n"
        "    pattern = TOPIC_KEYWORDS.get(aspect)\n"
        "    return pattern is None or bool(pattern.search(evidence))\n"
    )
    schema_import = "from datas.common.schema import ASPECTS, ATTRIBUTES, SENTIMENTS, TRAVELER_CONTEXTS\n"
    topic_import = "from datas.common.topic_keywords import mentions_topic\n"
    assert schema_import in source and topic_import in source, "postprocess.py의 import가 바뀌었습니다"
    return source.replace(schema_import, schema).replace(topic_import, topics)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    (TARGET / "inference").mkdir(parents=True)

    for name in ADAPTER_FILES:
        shutil.copy2(SOURCE / name, TARGET / name)
        assert sha256(SOURCE / name) == sha256(TARGET / name), f"{name} 복사 검증 실패"

    (TARGET / "README.md").write_text(MODEL_CARD, encoding="utf-8")
    (TARGET / "inference/tripfit_postprocess.py").write_text(standalone_postprocess(), encoding="utf-8")
    shutil.copy2(ROOT / "src/travel_planner/model_cjm/prompt.py", TARGET / "inference/tripfit_prompt.py")
    (TARGET / "inference/example.py").write_text(EXAMPLE, encoding="utf-8")
    (TARGET / "inference/requirements.txt").write_text(REQUIREMENTS, encoding="utf-8")
    (ROOT / "deploy/CHECKLIST.md").write_text(CHECKLIST.replace("{name}", NAME), encoding="utf-8")

    total = 0
    for path in sorted(TARGET.rglob("*")):
        if path.is_file():
            size = path.stat().st_size
            total += size
            print(f"  {path.relative_to(TARGET)}  ({size / 1024:.1f} KB)")
    print(f"합계 {total / 1024 / 1024:.1f} MB → {TARGET}")


if __name__ == "__main__":
    main()
