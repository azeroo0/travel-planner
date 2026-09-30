"""이 adapter와 후처리를 함께 쓰는 예제. 저장소 없이 이 폴더만으로 돈다.

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
