# Ollama 배포 준비

Ollama에는 adapter만 올릴 수 없어서 **Base에 합친 전체 모델을 GGUF로 만들어** 올린다.
이 폴더는 그 준비물이다. 팀원이 올린 [hinoonyaso/exaone-tripfit](https://ollama.com/hinoonyaso/exaone-tripfit)는 EXAONE 모델이라 별개이고, 이 모델은 내 계정 아래에 올린다.

| | 이름 |
|---|---|
| 팀원(EXAONE) | `hinoonyaso/exaone-tripfit:qlora-v2` (1.5GB, README 없음) |
| 이 모델(Qwen3) | `sunub/qwen3-tripfit:qlora-v3` (Q4_K_M 2.3GB) |

올리려면 ollama.com의 `sunub` 계정에 이 컴퓨터의 공개키가 등록돼 있어야 한다 (아래 7단계).

## 순서 (저장소 루트에서)

**1. 병합** — adapter를 bf16 Base에 합쳐 `deploy/ollama/merged/`에 저장 (Base가 없으면 약 8GB를 받는다)
```bash
uv run python deploy/ollama/merge_adapter.py
```

**2. GGUF 변환** (llama.cpp의 변환 스크립트)
```bash
uv run --with gguf --with sentencepiece python /opt/homebrew/bin/convert_hf_to_gguf.py deploy/ollama/merged --outfile deploy/ollama/tripfit-qwen3-4b-v3-f16.gguf --outtype f16
```

**3. 양자화**
```bash
llama-quantize deploy/ollama/tripfit-qwen3-4b-v3-f16.gguf deploy/ollama/tripfit-qwen3-4b-v3-q4_k_m.gguf Q4_K_M
```
Q4_K_M은 약 2.5GB로 가장 작다. 품질이 걱정되면 Q5_K_M이나 Q8_0(더 큼)으로 만들어 재평가한 뒤 고른다.

**4. Modelfile 만들기** — 시스템 메시지는 학습 코드에서 가져오고 프롬프트 형식이 학습과 같은지 검사한다
```bash
uv run python deploy/ollama/make_modelfile.py --gguf tripfit-qwen3-4b-v3-q4_k_m.gguf
```

**5. 로컬에 만들고 시험**
```bash
cd deploy/ollama && ollama create sunub/qwen3-tripfit:qlora-v3 -f Modelfile
```
```bash
ollama run sunub/qwen3-tripfit:qlora-v3
```
`ollama run`으로 시험할 때 사용자 메시지는 `[category]\nhotel\n\n[review]\n객실이 깨끗했어요.` 형식이어야 한다.

**6. 재평가 (올리기 전에 반드시)** — 병합과 양자화를 거쳤으므로 성능이 유지되는지 실제 리뷰 50건으로 확인한다
```bash
uv run python -m evaluation.run_pipeline --config evaluation/config.ollama.example.json --out evaluation/runs/ollama --skip-judge
```
후처리를 적용한 Aspect F1이 0.62 안팎이어야 한다. 크게 낮으면 더 큰 양자화(Q5_K_M, Q8_0)로 다시 만든다.
이 설정에는 팀원 모델(`hinoonyaso/exaone-tripfit:qlora-v2`)도 들어 있다. 그 모델을 재려면 먼저 `ollama pull`이 필요하다(1.5GB).

**7. 올리기** — ollama.com 계정에 이 컴퓨터의 공개키를 등록해야 한다 (`cat ~/.ollama/id_ed25519.pub`를 ollama.com 설정의 키에 붙여넣기)
```bash
ollama push sunub/qwen3-tripfit:qlora-v3
```
올린 뒤 ollama.com의 모델 페이지 README에 `MODEL_PAGE.md`의 내용을 붙여 넣는다.

## 주의
- **후처리는 Ollama 모델 밖에 있다.** 호출하는 쪽에서 `inference/tripfit_postprocess.py`(Hugging Face 저장소)나 저장소의 `postprocess.py`를 적용해야 한다. 안 쓰면 F1이 0.52 수준이다.
- 프롬프트 형식은 학습과 같아야 한다. Modelfile의 TEMPLATE과 SYSTEM은 `make_modelfile.py`가 학습 코드와 글자 그대로 같은지 검사한다.
- `merged/`와 `*.gguf`는 크기가 커서 커밋하지 않는다 (`.gitignore`).
