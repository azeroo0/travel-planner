# TripFit

Fine-tunes a model with LoRA/QLoRA to turn Busan hotel, restaurant, and
attraction reviews into structured Context / Aspect / Attribute / Sentiment /
Evidence records, and compares Base, LoRA, and QLoRA on the same data.
Python >= 3.12, managed with `uv` from the repository root; package code lives in
`src/travel_planner/`. Loading a model, training, and applying an adapter are
separate steps that each need an explicit request.

`README.md` defines the current scope. `docs/init-plan.md` describes an earlier
itinerary-planner design; where the two disagree, follow `README.md`.

<!--
This file is loaded into every conversation, so each line has to earn its tokens.
Leave out what the tests or pyproject.toml already check, and inline invariants
instead of pointing at README.md.

English, not Korean: this is input on every turn, and English tokenizes cheaper.
Replies, 💡 explanations and commit messages stay Korean.
-->

## Working agreement

- A prompt that asks how, why, or which is better is a **discussion**. Explain the
  proposed solution first; change code only after explicit acceptance.
- Keep the diff inside the requested scope. No drive-by formatting, no unrelated
  refactoring.
- Investigate a failure's root cause before retrying it.
- Add dependencies with `uv add`, so `pyproject.toml` and `uv.lock` change together.
- **Explain core terms every time:** Whenever a response introduces a technical term or core concept the user may not know, briefly define it in 1–2 sentences before moving on. Do not assume the term is familiar because it appeared earlier in the conversation. Prefix the explanation with `💡` (for example, `💡 LoRA: 원본 모델 가중치는 고정한 채 작은 저랭크 행렬만 학습해 모델을 조정하는 기법입니다.`).

## MVP scope

- In scope: review extraction, per-place Review Profiles aggregated in
  Python/SQL, and the Base vs LoRA vs QLoRA comparison.
- Future extensions, built only on explicit request: itinerary generation,
  location and travel-time calculation (Google Maps API), the clarifying-question
  planner, and a Validator.
- The model learns an extraction skill for unseen reviews; place facts belong in
  a database, never in training targets.

## Data invariants

- Output shape: `{"traveler_context": [...], "aspects": [{"category",
  "attribute", "sentiment", "evidence"}]}`. Every `evidence` is a verbatim span
  of the source review, and nothing absent from the review is labeled.
- The per-category aspect list in `README.md` is a draft; pilot annotation
  settles it. Ask before adding, renaming, or removing a category.
- **Gold** is data a person compared against the source and approved, whoever
  drafted it. **Silver** is Teacher-LLM output that passed only automatic checks
  (JSON, allowed aspect, attribute/sentiment values, evidence in source, required
  fields). Keep the tier on every record.
- The test set is Gold only and shared by every experiment: Gold-only vs
  Gold + Silver, and Base vs LoRA vs QLoRA on the same task, labels, and split.
- Mark synthetic reviews as synthetic; they never count as real user reviews.
- Split policy, scoring thresholds, and training hyperparameters are open
  decisions: ask, rather than invent.

## Verification

No test suite or linter is configured yet. Until one is, run the changed code
with `uv run` and report what you ran and its output.

## Commits

Follow the `commit` skill.
