# TripFit 부산 리뷰 구조화 (Qwen3-4B QLoRA v3)

부산 호텔·식당·관광지 리뷰에서 aspect(주제), attribute(상태), sentiment(평가), evidence(근거 구절), 동행자를 JSON으로 뽑는 모델입니다.
Qwen3-4B-Instruct-2507에 QLoRA로 학습한 adapter를 합쳐 GGUF(Q4_K_M)로 만든 것입니다.

## 사용법

시스템 메시지는 모델에 들어 있으니 **사용자 메시지만** 아래 형식으로 보냅니다.

```
[category]
hotel

[review]
객실이 깨끗하고 직원분들도 친절했어요.
```

`category`는 `hotel`, `restaurant`, `attraction` 중 하나입니다.

```bash
ollama run sunub/qwen3-tripfit:qlora-v3
```

출력은 JSON입니다.

```json
{"traveler_context": [], "aspects": [{"category": "cleanliness", "attribute": "clean", "sentiment": "positive", "evidence": "객실이 깨끗하고"}]}
```

## ⚠️ 후처리를 함께 써야 합니다

이 모델은 리뷰가 말하지 않은 주제(예: 주차)까지 정답의 약 1.5배를 만들어 냅니다. 실제 리뷰 50건에서 후처리 없이 Aspect F1 0.52, **후처리를 적용하면 0.62**였습니다.
후처리 코드(잘린 JSON 복구, 스키마·근거 확인, 주제 단어 확인, 중복 제거)는 Hugging Face 저장소 `sunub/tripfit-busan-review-qwen3-4b-qlora-v3`의 `inference/tripfit_postprocess.py`에 있습니다.

## 한계

- 학습 데이터는 전부 **합성 리뷰**입니다.
- **관광지 성능이 낮습니다**(Aspect F1 0.29 안팎). 호텔 0.70, 식당 0.79입니다.
- 평가는 사람이 승인한 실제 리뷰 50건이라 ±0.05 안팎의 오차가 있습니다.
- 위 수치는 Hugging Face의 adapter로 잰 값입니다. 이 GGUF(양자화) 모델의 수치는 재평가 후 이 페이지에 기입해야 합니다.

## 라이선스

Base 모델(Qwen3-4B-Instruct-2507)의 라이선스를 따릅니다.
