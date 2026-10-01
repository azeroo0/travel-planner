# 배포 전 확인 목록

이 폴더(`deploy/`)는 저장소에서 추적하지 않는 배포 준비 영역입니다. 아래를 확인한 뒤 올리세요.

## 올리는 것
`deploy/tripfit-busan-review-qwen3-4b-qlora-v3/` 폴더 전체 (약 47MB)

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
hf repo create <사용자명>/tripfit-busan-review-qwen3-4b-qlora-v3 --private
hf upload <사용자명>/tripfit-busan-review-qwen3-4b-qlora-v3 deploy/tripfit-busan-review-qwen3-4b-qlora-v3 .
```

토큰은 채팅이나 파일에 적지 마세요.

## 다시 만들기
`uv run python deploy/build_hf_folder.py`
