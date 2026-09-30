---
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
