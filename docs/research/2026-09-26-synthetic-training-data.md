# 합성 학습 데이터 생성 조사 (취향 프로필 · 취향 문장 · 일정 SFT · DPO 쌍)

> `docs/init-plan.md`의 2-6 데이터 목록, 4 학습, 5 평가, 7-4 GPU 타임라인을 기준으로 조사했어요. 모든 근거는 1차 출처(논문 원문·초록, 공식 문서, 소스 코드)에 링크를 달았고, 확인하지 못한 내용은 **미확인**으로 적었어요. 본문의 `[n]`은 맨 아래 출처 목록 번호예요.
>
> 조사일: 2026-09-26 · 대상 계획: 부산 · 3일 · GPU 1장 · Qwen 계열 8B Instruct + QLoRA

---

## 1. 요약 (핵심 권고)

| # | 권고 | 관련 절 | 근거 요지 |
| --- | --- | --- | --- |
| 1 | **시험 프로필 50개를 먼저 뽑아요.** pace × walking 9칸에 5~6개씩 할당하고, 무작위 시드 여러 개 중 **쌍(pairwise) 커버리지가 가장 높은 조합**을 고정해요. 학습 400개는 칸별 할당 + 무작위로 충분해요 | 2-6, 5-1 | 조합 테스트는 소수 변수의 상호작용을 적은 표본으로 덮는 방법이에요 [[1]](https://csrc.nist.gov/pubs/sp/800/142/final). 가정한 수준 수로 모의 실험하면 무작위 400개는 쌍의 약 99.9%를 덮지만 무작위 50개는 약 86%만 덮어요 (자체 계산, 3-2절) |
| 2 | **불가능한 조합만 막고, 드문 조합은 비율 상한(예: 5%)으로 남겨요.** 대신 프로필마다 Model 1 후보가 12개·음식점 3곳 이상 나오는지 **실행 가능성 검사**를 먼저 해요 | 2-6, 7-6 | 실행 불가능한 프로필은 75점·위반 0 기준을 못 넘어 SFT 정답이 안 생겨요 (계획 내부 논리) |
| 3 | **취향 문장은 "라벨 먼저" 방식으로 만들어요.** 코드가 언급 필드·값·표현 유형·말투·길이를 먼저 정하고 LLM은 문장만 써요. 속성(말투, 이유, 길이, 페르소나)을 프롬프트에 넣어 다양성을 확보해요 | 4-2 | SGD는 시뮬레이터가 만든 의미 구조를 사람이 문장으로 바꿔 라벨을 그대로 보존했어요 [[5]](https://arxiv.org/abs/1909.05855). 속성을 준 프롬프트가 단순 클래스 프롬프트보다 편향이 적고 성능이 좋았어요 [[6]](https://arxiv.org/abs/2306.15895) |
| 4 | **왕복 검증은 "추출"이 아니라 "라벨 확인" 프롬프트로 하고, 부정 유형은 자동 폐기 대신 사람 검수로 보내요.** 부정어 = low라는 지름길을 막기 위해 부정 형태로 high를 말하는 문장도 30% 섞어요 | 4-2, 5-2 | 왕복 일관성 필터는 합성 QA에서 효과가 있었어요 [[9]](https://arxiv.org/abs/1906.05416). 반면 LLM은 부정에 둔감하고 표면 단서에 의존해요 [[12]](https://arxiv.org/abs/2306.08189) [[13]](https://arxiv.org/abs/2310.15941). 같은 Base로 추출해 걸러내면 Base가 이미 맞히는 쉬운 문장만 남아요 |
| 5 | **일정 샘플 수 N은 10개 시험 실행의 채택률로 정해요.** 1개 샘플 채택률 p가 0.25 미만이면 처음부터 N=8로 생성해요. 같은 방문지 조합은 1개로 셉니다 | 4-1, 7-4 | RFT는 k=3에서도 SFT보다 약 2점 높았고, k를 늘릴수록 이득이 줄었어요. 이득은 "서로 다른 풀이 수"에 달려 있었어요 [[20]](https://arxiv.org/html/2308.01825) |
| 6 | **탐색 출신과 LLM 출신의 표면 차이를 없애요.** 모든 정답·쌍 JSON을 같은 직렬화 코드로 다시 써요. 점수 차가 작으면(예: 3점 이내) LLM 샘플을 우선해요 | 4-1, 4-3 | 전문가(탐색) 출력을 모방 학습하는 것은 Expert Iteration 계열의 표준 방식이에요 [[24]](https://arxiv.org/abs/1705.08439) [[34]](https://arxiv.org/abs/2402.14083). 다만 DPO에서는 출처 말투가 쉬운 구분 단서가 돼요 |
| 7 | **DPO rejected는 SFT 어댑터가 만든 샘플에서 뽑아요.** 9/29 15–17시 서빙 창에서 vLLM에 올라간 SFT 어댑터로 학습 프로필 400개 × 4개를 생성하면 GPU 시간을 거의 추가로 쓰지 않아요 | 4-3, 7-4 | on-policy 샘플을 쓰는 선호 학습이 더 좋았어요 [[40]](https://arxiv.org/abs/2404.14367). RS-DPO와 Self-Rewarding도 현재 정책 샘플에서 보상 차로 쌍을 만들어요 [[42]](https://arxiv.org/html/2402.10038) [[37]](https://arxiv.org/html/2401.10020) |
| 8 | **DPO에 SFT(NLL) 항을 더하고, ref가 SFT 어댑터인지 0단계에서 확인해요.** `loss_type=["sigmoid","sft"]`, lr 약 1e-5, `max_length`는 명시해요. 첫 스텝에서 `rewards/chosen ≈ 0`, loss ≈ 0.693이면 ref가 SFT예요 | 4-3, 4-4 | NLL 항이 "결정적"이었고 DPO만 쓰면 chosen 확률이 떨어졌어요 [[39]](https://arxiv.org/html/2404.19733). TRL은 `loss_type` 목록 조합을 지원하고, 어댑터 학습 lr로 약 1e-5를 권해요 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer) |

---

## 2. 질문 1 · 취향 프로필 450개 (학습 400 / 시험 50)

### 2-1. 근거

| 방법 | 내용 | 우리 문제에 맞는 정도 |
| --- | --- | --- |
| 조합(t-way) 테스트 · covering array | NIST는 "모든 변수가 모든 결함에 관여하지 않고, 대부분의 결함은 소수 변수의 상호작용 때문"이라는 전제로 t-way 조합 테스트를 제안해요. 제약 조건과 비용 절충도 다뤄요 [[1]](https://csrc.nist.gov/pubs/sp/800/142/final) | 높음. 필드가 모두 범주형이고, 시험 세트가 작아서 쌍 커버리지가 의미 있어요 |
| 라틴 하이퍼큐브 (LHS) | 각 차원을 n개 구간으로 나누고 구간마다 정확히 1점을 둬요 (McKay et al., Technometrics 1979). `strength=2`는 직교 배열 기반이지만 n=p²(p는 소수), d ≤ p+1 제약이 있어요 [[2]](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html) | 낮음. 연속 변수용이고, 범주형에서는 "주변 분포 할당"과 사실상 같아요 |
| 층화 분할 | `train_test_split(stratify=...)`는 층 비율을 학습·시험에 같게 유지해요 [[3]](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html) | 높음. pace × walking 칸을 층으로 쓰면 돼요 |
| 조합 일반화 분할 | CFQ는 원자(개별 값) 분포는 같게, 조합 분포는 다르게 나눠 조합 일반화를 측정해요 [[4]](https://arxiv.org/abs/1912.09713) | 선택 사항. 3일 범위에서는 결과 해석만 참고해요 |

**자체 모의 계산 (근거가 아닌 참고값):** 필드 수준을 companion 5, pace 3, walking 3, budget 3, 식이 4(없음 60%), 관심사 4개 × 3, 요일 7, 권역 7(auto 50%)로 가정하면 값 쌍은 867개예요. 무작위 400개는 평균 99.9%(최소 99.7%)를 덮고, 무작위 50개는 평균 86%(최소 82%)만 덮어요. 후보 200개 중 새 쌍을 가장 많이 덮는 것을 고르는 탐욕 방식으로 50개를 뽑으면 약 99%를 덮어요. companion 값 목록이 확정되면 B가 다시 계산해요.

### 2-2. 우리 계획에 적용

**생성 순서**

| 순서 | 할 일 | 규칙 |
| --- | --- | --- |
| 1 | 시험 50개 먼저 생성 | pace × walking 9칸에 6개씩 5칸, 5개씩 4칸 (합 50). 시드 1,000개로 뽑아 **쌍 커버리지 최대**인 시드를 고정해요. 권역 z1~z6는 각 3개 이상, 요일은 각 4개 이상 나오게 해요 |
| 2 | 학습 400개 생성 | 9칸에 44~45개씩 할당하고 나머지 필드는 아래 분포로 무작위예요. 시험 프로필과 **모든 필드가 같은 프로필**은 다시 뽑아요 |
| 3 | 실행 가능성 검사 | 프로필마다 Model 1을 돌려 후보 12개 미만, 식이 조건을 만족하는 음식점 3곳 미만이면 같은 칸 안에서 다시 뽑아요. 탈락률을 기록해요 |
| 4 | 고정 | `data/profiles/{train,test}.jsonl`에 시드와 함께 저장하고, 이후 모든 단계는 이 파일만 읽어요 (6-4) |

**필드 분포 (출발값)**

| 필드 | 분포 | 이유 |
| --- | --- | --- |
| pace × walking | 9칸 균등 | 계획대로예요 |
| companion | 균등 | 값 목록은 B가 확정해요 |
| budget | 균등 | |
| dietary_restrictions | 없음 60%, 나머지 3종 균등 | 실제 사용자 대부분은 제한이 없을 것이라는 가정이에요 (미확인) |
| interests | 4개 독립 균등, 단 4개 모두 같은 값은 10% 이하 | 모두 high/low이면 Preference Fit이 변별력을 잃어요 |
| day_of_week | 토·일 각 20%, 평일 각 12% | 칩 기본값이 토요일이고, 월요일 휴무 같은 위반 사례도 학습에 들어가야 해요 |
| zone | auto 50%, z1~z6 각 약 8.3% | 계획대로예요 |

**상관 제약: 막지 말고 상한을 둬요**

| 유형 | 예 | 처리 |
| --- | --- | --- |
| 논리적으로 불가능 | 식이 제한 목록에 "없음"과 다른 값이 함께 있음 | 생성 단계에서 금지 |
| 드물지만 가능한 조합 | family + packed + walking high | 금지하지 않고 **전체의 5% 이하**로 제한해요. 실제 사용자도 입력할 수 있어서 서비스 입력 분포에서 빠지면 안 돼요 |
| 실행 불가능 | 권역 후보 부족, 식이 조건 음식점 부족 | 3단계 실행 가능성 검사로 걸러요 |

**누수 방지 규칙 (추가)**

| 누수 경로 | 규칙 |
| --- | --- |
| 채점 검증 세트(3-4, 20세트) | 학습 프로필에서만 뽑아요. 시험 프로필로 가중치를 조정하면 시험 점수가 채점기에 맞춰져요 |
| Few-shot 예시 | 관광공사 코스만 써요. 시험 프로필 결과를 예시로 쓰지 않아요 |
| 취향 문장 (P1) | 학습 프로필 400개로만 만들어요. 취향 시험 30문장은 팀원이 따로 써요 (계획대로) |

**계획 수정 제안:** 2-6 표의 "취향 프로필" 행에 "시험 50개를 먼저 쌍 커버리지 기준으로 고정하고, 실행 가능성 검사를 통과한 프로필만 사용"을 추가해요. 7-5 9/28 오전 B 작업에 "실행 가능성 검사"를 넣되, C의 Model 1이 오후에 나오므로 검사는 **Model 1 완성 직후(9/28 오후)** 에 돌려요.

---

## 3. 질문 2 · 취향 문장 약 2,000쌍 (P1)

### 3-1. 근거

| 주제 | 근거 |
| --- | --- |
| 라벨 먼저 생성 | SGD는 시뮬레이터가 대화 개요(의미 구조)를 먼저 만들고 크라우드 작업자가 자연어로 바꿨어요. 이 방식은 "시뮬레이터에서 얻은 모든 주석을 보존하고, 수집 후 추가 주석이 필요 없다"고 해요 [[5]](https://arxiv.org/abs/1909.05855) |
| 속성 조건 생성 | AttrPrompt는 길이·스타일 같은 속성을 준 프롬프트가 단순 클래스 조건 프롬프트보다 지역 편향 등이 적고, 비용의 5%로 같은 성능을 냈다고 보고해요 [[6]](https://arxiv.org/abs/2306.15895) |
| 페르소나 조건 | Persona Hub는 다양한 페르소나를 넣어 합성 데이터의 관점을 다양하게 만들어요 [[7]](https://arxiv.org/abs/2406.20094) |
| 유사도 중복 제거 | Self-Instruct는 기존 지시와 ROUGE-L 유사도가 0.7 미만일 때만 새 지시를 추가했어요 [[8]](https://arxiv.org/html/2212.10560). 중복 제거는 암기를 줄이고 학습·시험 겹침을 줄여요 [[15]](https://arxiv.org/abs/2107.06499). 임베딩 기반 중복 제거도 있어요 [[16]](https://arxiv.org/abs/2303.09540) |
| 왕복 일관성 필터 | 생성한 질문을 다시 풀어 답이 일치하는 것만 남기는 방식으로 합성 QA 데이터 품질을 높였어요 [[9]](https://arxiv.org/abs/1906.05416) |
| LLM 생성 NLU 데이터의 한계 | 의도가 서로 비슷하면 LLM이 인접 의도의 문장을 만드는 문제가 있었고, LLM 분류기로 거르는 방법을 제안했어요 [[10]](https://arxiv.org/abs/2204.01959). 과제·사례의 주관성이 높을수록 합성 데이터 효과가 떨어졌어요 [[11]](https://arxiv.org/abs/2310.07849) |
| 부정 표현 | LLM은 부정의 존재에 둔감하고, 부정 아래 추론을 못 한다고 보고됐어요 [[12]](https://arxiv.org/abs/2306.08189). 부정 문장에서 표면 단서에 의존하고, 부정 문장으로 미세 조정해도 일반화가 부족했어요 [[13]](https://arxiv.org/abs/2310.15941) |
| 자기 생성 데이터 위험 | 생성 데이터로 재귀적으로 학습하면 원래 분포의 꼬리가 사라져요 (model collapse) [[14]](https://arxiv.org/abs/2305.17493). 우리는 1회 생성이라 재귀는 아니지만, 분포가 좁아지는 방향은 같아요 |
| 디코딩 설정 | vLLM `SamplingParams`는 `n`, `seed`, `temperature`, `top_p`, `min_p`, `presence_penalty` 등을 제공해요 [[18]](https://docs.vllm.ai/en/latest/api/vllm/sampling_params.html). 구조화 출력은 `StructuredOutputsParams(json=..., choice=...)`로 강제할 수 있어요 [[17]](https://docs.vllm.ai/en/latest/features/structured_outputs.html). Qwen3-8B는 기본이 사고 모드이고 `enable_thinking=False`로 끄며, 비사고 모드 권장값은 T 0.7, top_p 0.8, top_k 20이에요 [[19]](https://huggingface.co/Qwen/Qwen3-8B) |

### 3-2. 우리 계획에 적용

**생성 단위: 코드가 "문장 명세"를 먼저 만들어요**

```json
{
  "spec_id": "s_0001", "profile_id": "p_0123",
  "mention": {"walking_tolerance": "low", "interests.food": "high"},
  "type": "indirect",
  "style": {"register": "해요체", "length": "1문장", "persona": "무릎이 안 좋은 60대 부모님과 가는 자녀", "reason": true},
  "label": {"walking_tolerance": "low", "interests": {"nature": null, "food": "high", "culture": null, "shopping": null}}
}
```

| 항목 | 규칙 |
| --- | --- |
| 언급 필드 수 | 1개 40%, 2개 40%, 3개 20%. 5개 필드(walking + 관심사 4개)가 언급되는 횟수를 균등하게 맞춰요 |
| 값 | 언급 필드 값은 프로필 값을 따라요 |
| 유형 × 값 | **간접 표현은 low/high만** 써요. medium은 간접으로 말하면 사람도 라벨이 갈려서(주관성 [[11]](https://arxiv.org/abs/2310.07849)) 직접 표현("적당히", "너무 많지 않게")으로만 만들어요 |
| 부정 20% 내부 구성 | 70%: 부정 → low ("쇼핑은 관심 없어요"), 30%: 부정 형태로 high/medium ("바다는 절대 빼면 안 돼요", "오래 걷는 것도 전혀 문제없어요"). 부정어가 나오면 무조건 low라는 표면 단서 학습을 막기 위해서예요 [[13]](https://arxiv.org/abs/2310.15941) |
| 이중 부정 | "걷는 게 싫진 않아요"처럼 값이 모호한 문장은 학습에서 빼요 |
| 말투·길이 | 해요체 / 반말 / 메모체("걷기 적게, 맛집 위주") × 1문장 / 2문장을 균등 할당해요 |
| 페르소나 | companion·요일 같은 프로필 값으로 짧은 상황 문구를 만들어 넣어요 (예: "주말에 초등학생 아이 둘과") |

**생성 프롬프트 구조 (Base 8B, 사고 모드 끔)**

```text
[system] 여행자가 여행 앱에 입력할 한국어 문장을 한 개 씁니다. 지정한 항목만 드러내고, 다른 항목은 드러내지 않습니다.
         항목 이름(walking_tolerance, high 등)이나 점수를 문장에 쓰지 않습니다.
[user]   상황: {persona}
         드러낼 항목: 걷기 부담 = 적게 걷고 싶음 / 음식 관심 = 매우 높음
         표현 방식: 간접 (이유나 상황으로 돌려 말하기)
         말투: 해요체, 길이: 1문장
         예시: {유형별 예시 풀에서 무작위 2개}
[assistant] 문장만 출력
```

| 설정 | 값 |
| --- | --- |
| 예시 풀 | 팀원 5명이 유형별로 각 4문장씩 써서 **60문장 풀**을 만들고, 명세마다 무작위 2개를 넣어요. 같은 예시가 반복되면 문장 모양이 좁아져요 |
| 디코딩 | T 0.9, top_p 0.95, `n=2`, `seed` 고정. 두 후보 중 필터를 통과한 것 1개를 써요. (T 0.9는 출발값이며 근거로 정한 값이 아니에요) |
| 초과 생성 | 명세를 목표의 1.5배(직접 1,200 / 간접 1,200 / 부정 600) 만들어요. 필터 탈락을 감안해요 |

**품질 필터 (순서대로)**

| 단계 | 규칙 | 탈락 처리 |
| --- | --- | --- |
| 1. 형식 | 5~80자, 한국어 비율 80% 이상, 줄바꿈 없음, 라벨 누출 단어(`walking`, `high`, `low`, `medium`, `null`, 점수 숫자) 없음 | 폐기 |
| 2. 부정 검사 | 부정 유형은 부정 형태소(안, 않, 없, 싫, 별로, 말고, 빼고, 못, 절대) 포함, 직접·간접 유형은 미포함이 원칙. 단 부정 형태 high 문장은 예외 목록으로 관리해요 | 폐기 |
| 3. 왕복 확인 | Base 8B에 **문장 + 주장된 라벨**을 주고 필드마다 `맞음/틀림/언급없음`을 `choice`로 강제해 답하게 해요 [[17]](https://docs.vllm.ai/en/latest/features/structured_outputs.html). 언급 필드가 `틀림`이거나, 비언급 필드가 `맞음`(= 언급됨)으로 나오면 탈락 후보예요 | 직접·간접: 폐기. **부정: 폐기하지 않고 사람 검수 대기열** |
| 4. 중복 | 공백·문장부호 제거 후 완전 중복 제거. 같은 라벨 안에서 문자 3-gram Jaccard 0.7 이상이면 하나만 남겨요 (Self-Instruct의 0.7 기준 [[8]](https://arxiv.org/html/2212.10560)을 문자 단위로 옮긴 값이에요) | 폐기 |
| 5. 사람 검수 | 계획의 100개 무작위 검수 + 3단계 부정 대기열에서 최대 100개 | 유형별 오류 20% 초과 시 프롬프트 수정 (계획대로) |

**왜 "추출"이 아니라 "라벨 확인"인가:** Base Few-shot 추출은 P1의 비교 대상이에요 (5-2). 같은 추출기로 걸러내면 Base가 이미 맞히는 문장만 남고, 학습된 어댑터가 Base를 넘을 여지가 줄어요. 라벨을 주고 맞는지 묻는 쪽이 문제가 쉬워서 덜 걸러내요. 이 판단은 추론이고 직접 검증한 논문은 찾지 못했어요 (**미확인**). 대신 **유형별 탈락률을 기록**하고, 한 유형의 탈락률이 40%를 넘으면 필터가 그 유형을 편향되게 지우고 있다고 보고 해당 유형의 탈락 문장 30개를 사람이 확인해요.

**분할:** 학습 1,800 / 검증 200은 **프로필 단위(group split)** 로 나눠요. 같은 프로필의 문장이 양쪽에 있으면 검증 점수가 부풀려져요 [[15]](https://arxiv.org/abs/2107.06499).

**자기 생성 위험 대응:** 사람이 쓴 60문장 예시 풀로 표현을 넓히고, 평가는 사람이 쓴 30문장으로만 해요 (5-2 그대로). 학습 데이터 다양성은 고유 문자 3-gram 비율로 유형별로 기록해 결과 문서에 적어요.

**GPU 시간:** 3,000 명세 × `n=2` 짧은 문장 생성과 3,000건 라벨 확인은 출력이 짧아 9/28 17–19시 2시간 안에 들어갈 것으로 보여요. 실제 처리량은 **미확인**이고 사전 준비의 10개 시험 실행에서 실측해요.

**계획 수정 제안 (4-2 표):**
- "품질 확인" 행에 3단계 왕복 확인(라벨 확인형, `choice` 강제)과 4단계 중복 제거를 추가해요.
- "문장 구성" 행에 "간접은 low/high만, 부정의 30%는 부정 형태 high/medium"을 추가해요.
- "분할" 행을 "프로필 단위로 1,800 / 200"으로 바꿔요.
- 7-3 사전 준비에 "팀원별 예시 12문장 작성(20분)"을 추가해요.

---

## 4. 질문 3 · 일정 SFT 데이터 (Best-of-N + 규칙 채점 선별)

### 4-1. 근거

**방법 계열: 우리 방식은 "규칙 보상 1회 ReST-EM + 탐색 전문가 주입"이에요.**

| 방법 | 핵심 | 우리와의 관계 |
| --- | --- | --- |
| STaR [[21]](https://arxiv.org/abs/2203.14465) | Few-shot으로 근거를 생성하고 정답에 이른 것만 모아 미세 조정, 반복해요 | Few-shot 생성 → 걸러서 SFT가 같아요 |
| RFT [[20]](https://arxiv.org/html/2308.01825) | 질문당 k=100개(T=0.7)를 만들고 정답·계산 검증 후, **서로 다른 방정식 목록마다 1개**만 남겨요. k=3에서도 SFT보다 약 2점 높았고 k를 두 배로 늘릴 때마다 이득이 줄었어요. 7B는 35.9% → 41.7%였어요. 여러 모델의 샘플을 합치면 LLaMA-7B가 49.3%였어요 [[20]](https://arxiv.org/abs/2308.01825) | N 선택, 중복 제거, **출처 혼합** 근거 |
| ReST [[22]](https://arxiv.org/abs/2308.08998) | Grow(정책에서 샘플 생성) → Improve(보상으로 걸러 오프라인 학습) | 1회 Grow + 1회 Improve예요 |
| ReST-EM [[23]](https://arxiv.org/abs/2312.06585) | 이진 피드백으로 거른 자기 샘플로 학습하면 사람 데이터만 쓴 것보다 좋았지만, 반복하면 과적합이 생겼어요 | 우리는 1회만 해서 반복 과적합 위험은 작아요 |
| Expert Iteration [[24]](https://arxiv.org/abs/1705.08439) | 트리 탐색이 더 나은 정책을 찾고, 신경망이 그것을 일반화해요 | 규칙 탐색 결과를 정답으로 쓰는 근거예요 |
| Searchformer [[34]](https://arxiv.org/abs/2402.14083) | A* 탐색 결과·과정을 Transformer에 학습시켰어요 | 해답만 학습하는 것보다 탐색 과정 학습이 데이터 효율적이었다는 보고예요. 우리는 해답만 학습해요 |
| LIMA [[25]](https://arxiv.org/abs/2305.11206) | 정제한 1,000개로 SFT했어요 | 적은 고품질 데이터 근거 |
| QLoRA [[26]](https://arxiv.org/abs/2305.14314) | 작은 고품질 데이터셋 QLoRA 미세 조정으로 좋은 결과를 냈어요 | 같은 근거 |
| AlpaGasus [[27]](https://arxiv.org/abs/2307.08701) | 52k에서 걸러낸 9k로 학습한 모델이 더 좋았어요 | 양보다 선별 |

**여행 계획 도메인**

| 연구 | 발견 |
| --- | --- |
| TravelPlanner [[28]](https://arxiv.org/abs/2402.01622) | GPT-4 최종 통과율 0.6%. 정보를 미리 준 sole-planning에서도 GPT-4-Turbo Direct 4.4%였어요. 개별 제약은 맞춰도 여러 제약을 동시에 지키지 못했어요 [[28]](https://arxiv.org/html/2402.01622) |
| LLM-Modulo [[32]](https://arxiv.org/abs/2405.20625) | 비평기(critic)로 검증·재요청하는 구조로 GPT-4-Turbo가 약 1.1% → 약 5.1%가 됐어요 |
| 형식 검증 도구 결합 [[33]](https://arxiv.org/abs/2404.11891) | 계획 문제를 충족 가능성 문제로 바꿔 솔버로 풀면 TravelPlanner 93.9%였어요 |
| TRIP-PAL [[30]](https://arxiv.org/abs/2406.10196) | LLM은 정보를 구조로 바꾸고, 자동 계획기가 제약 충족을 보장해요. LLM 단독보다 좋았어요 |
| ItiNera [[29]](https://arxiv.org/abs/2402.07204) | LLM은 요청 분해·POI 선택, 공간 최적화가 순서 결정을 맡아요 |
| TravelAgent [[31]](https://arxiv.org/abs/2409.08069) | 도구·추천·계획·기억 모듈로 나눈 LLM 여행 계획 시스템이에요 |

→ 우리 구조(후보 제한 + 코드 검증 + 규칙 탐색 대체)는 이 흐름과 맞아요. 이 연구들은 "LLM 단독 생성은 제약을 자주 깬다"는 점에서 일치해요. 그래서 Base 샘플의 채택률이 낮을 수 있고, N과 탐색 비율을 미리 정해 둬야 해요.

**보상 해킹 (규칙 채점기 과최적화)**

| 근거 | 내용 |
| --- | --- |
| Gao et al. [[36]](https://arxiv.org/abs/2210.10760) | 대리 보상을 너무 최적화하면 실제 품질이 떨어져요 (Goodhart). Best-of-n의 KL은 `log n − (n−1)/n`으로 계산돼요 [[36]](https://arxiv.org/pdf/2210.10760) |
| 적용 | N=4이면 약 0.64 nats, N=8이면 약 1.20 nats로 최적화 압력이 약해요. 반면 **규칙 탐색은 탐색 공간 전체에서 Model 2 최고점을 고르므로** 채점기 허점을 가장 많이 이용하는 출처예요 |

**분포 차이**

| 근거 | 내용 |
| --- | --- |
| SDFT [[35]](https://arxiv.org/abs/2402.13669) | 과제 데이터와 모델 분포의 차이가 미세 조정 성능 저하(망각)의 주원인이고, 모델 자신의 분포로 다시 쓴 데이터가 이를 줄였어요 |
| 적용 | 우리 어댑터는 일정 JSON 전용이라 일반 능력 망각은 중요하지 않아요. 다만 탐색 출력(항상 10:00 출발, 최근접 순서)은 Base 출력과 모양이 달라서, 탐색 출신이 많으면 어댑터는 "탐색 흉내"를 배워요. 그 경우 SFT 결과가 규칙 탐색 기준선을 넘기 어려워요 |

**몇 개면 충분한가:** 좁은 JSON 과제의 QLoRA SFT에 필요한 정확한 개수를 제시한 1차 출처는 찾지 못했어요 (**미확인**). LIMA 1,000개 [[25]](https://arxiv.org/abs/2305.11206), RFT의 "서로 다른 풀이 수가 성능을 좌우" [[20]](https://arxiv.org/html/2308.01825)를 근거로, 300~400개 + 프로필당 서로 다른 정답 추가가 현실적인 방향이에요.

### 4-2. 우리 계획에 적용

**N 결정 규칙 (9/28 오후 10개 시험 실행에서)**

| 측정 | 계산 | 결정 |
| --- | --- | --- |
| 샘플 1개 채택률 p = (검증 통과 · 75점 이상 · 위반 0) / 전체 | 프로필 커버리지 ≈ 1 − (1 − p)^N (샘플 독립 가정, 실제로는 상관이 있어 이보다 낮아요) | p ≥ 0.25 → N=4 (커버리지 약 68% 이상) · p < 0.25 → **처음부터 N=8** |
| 예 | p=0.2 → N=4: 59%, N=8: 83% | 재생성보다 처음부터 8개가 GPU 시간이 적게 들어요 |

- vLLM에서 `n=N`으로 한 요청에 여러 샘플을 받으면 프롬프트(후보 12개 + 행렬)를 공유해요 [[18]](https://docs.vllm.ai/en/latest/api/vllm/sampling_params.html). 출력이 짧은 JSON이라 N=8도 9/28 14–17시 창에 들어갈 가능성이 높아요. 실측 전까지는 **미확인**이에요.
- Self-Rewarding도 N=4, T=0.7로 후보를 만들었어요 [[37]](https://arxiv.org/html/2401.10020). T=0.7은 Qwen3 비사고 모드 권장값과도 같아요 [[19]](https://huggingface.co/Qwen/Qwen3-8B).
- **사고 모드:** Qwen3 계열이면 생성·학습·서빙·평가 모두 `enable_thinking=False`로 통일해요 [[19]](https://huggingface.co/Qwen/Qwen3-8B). 한 곳이라도 다르면 형식 통과율이 흔들려요.

**선별 규칙 (4-1 보강)**

| # | 규칙 | 근거 |
| --- | --- | --- |
| 1 | 검증 실패 폐기 (계획대로) | |
| 2 | **방문지 집합이 같은 샘플은 1개로 합쳐요** | RFT의 서로 다른 풀이 기준 [[20]](https://arxiv.org/html/2308.01825) |
| 3 | 최고점 1개, 75점 이상 · 위반 0 (계획대로) | |
| 4 | **동점 처리:** 탐색 결과와 최고 LLM 샘플의 차이가 3점 이내이고 둘 다 기준을 넘으면 LLM 샘플을 골라요 | 탐색 편중과 채점기 과최적화 완화 [[36]](https://arxiv.org/abs/2210.10760) |
| 5 | **정규화:** 정답 JSON을 코드로 다시 직렬화해요 (키 순서, 공백, 시각 `HH:MM` 고정) | 출처별 표면 차이 제거 |
| 6 | 부족하면 (300개 미만): 먼저 **프로필당 두 번째 정답**(방문지 집합이 다르고 기준 통과)을 추가하고, 그래도 부족하면 70점으로 낮춰요 | RFT: 서로 다른 정답 추가가 도움 [[20]](https://arxiv.org/html/2308.01825) · 품질 기준을 먼저 낮추지 않아요 |
| 7 | 출처 비율 기록, 탐색 과반이면 대응 (계획대로) | |
| 8 | **사람 확인 20개:** B가 선별된 정답 20개를 보고 "점수는 높은데 이상한 일정"이 있는지 봐요 (20분) | 채점기 허점 조기 발견 [[36]](https://arxiv.org/abs/2210.10760) |

**학습 설정 확인 (4-4 보강)**

| 항목 | 확인 내용 | 근거 |
| --- | --- | --- |
| `max_length` | TRL `SFTConfig`의 기본값은 **1024**, 자르기는 `keep_start`예요. 프롬프트가 길면 **끝의 assistant JSON이 잘려요**. 2,048을 명시하고, 학습 전 최대 토큰 길이를 출력해 확인해요 | [[48]](https://huggingface.co/docs/trl/main/en/sft_trainer) |
| assistant 토큰 loss | `assistant_only_loss=True`는 채팅 템플릿에 `{% generation %}` 표시가 필요하고, Qwen3 같은 알려진 계열은 TRL이 자동으로 패치해요. 첫 배치의 라벨 마스크를 출력해 확인해요 | [[48]](https://huggingface.co/docs/trl/main/en/sft_trainer) |
| 검증 분할 | 10% 검증은 프로필 단위로 나눠요 (두 번째 정답을 쓰면 특히 중요해요) | |

**계획 수정 제안 (4-1):** 선별 규칙에 2(방문지 집합 중복 제거), 4(3점 이내 LLM 우선), 5(JSON 정규화), 6(부족 시 두 번째 정답 → 그다음 70점), 8(사람 20개 확인)을 추가해요. "탐색 출신이 과반이면 Base 8개로 재생성" 대신 **"10개 시험 실행의 p로 N을 먼저 정함"** 으로 바꿔요. 7-6의 "학습 데이터 부족" 대응 순서도 같이 바꿔요.

---

## 5. 질문 4 · 점수 기반 DPO 쌍 (P2)

### 5-1. 근거

| 주제 | 근거 |
| --- | --- |
| DPO | 보상 모델을 따로 학습하지 않고 분류 손실 하나로 선호를 학습해요 [[38]](https://arxiv.org/abs/2305.18290). TRL 문서는 실제로는 "선호 응답 확률을 올리기보다 비선호 응답 확률을 낮추는 방식으로" 목표가 달성되는 경우가 많다고 설명해요 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer) |
| on-policy 데이터 | 선호 학습은 on-policy 샘플을 쓰거나 특정 응답의 확률을 내리는 방법이 더 좋았어요 [[40]](https://arxiv.org/abs/2404.14367) |
| 현재 정책 샘플로 쌍 만들기 | RS-DPO: SFT 모델에서 프롬프트당 k=16개를 만들고, 보상 차(시그모이드 정규화)가 임계값을 넘는 쌍만 써요 [[42]](https://arxiv.org/html/2402.10038). Self-Rewarding: N=4, T=0.7 후보 중 최고점과 최저점을 쌍으로 하고 동점이면 버려요 [[37]](https://arxiv.org/html/2401.10020) |
| NLL 항 | Iterative RPO: 정답/오답 풀이로 쌍을 만들고 DPO에 NLL 항(α=1)을 더했어요. NLL이 "결정적"이었고, GSM8K에서 DPO만 쓰면 61.8%, NLL을 더하면 73.1%였어요. DPO만 쓰면 chosen 확률이 학습 중 떨어졌어요 [[39]](https://arxiv.org/html/2404.19733) |
| 비슷한 쌍의 위험 | 쌍의 편집 거리가 작으면 DPO가 선호 응답 확률까지 낮출 수 있어요 [[44]](https://arxiv.org/abs/2402.13228). 임베딩이 비슷한 쌍이 likelihood displacement를 일으키고, 그런 쌍을 거르면 완화돼요 [[45]](https://arxiv.org/abs/2410.08847) |
| rejected 선택 | 샘플 수를 늘릴 때 최저점을 rejected로 쓰면 성능이 떨어졌고, 보상 분포의 μ − 2σ 위치가 좋았어요 [[43]](https://arxiv.org/abs/2502.16825). 우리처럼 N=4면 최저점과 μ − 2σ 차이가 크지 않아요 (추론) |
| 선호 강도 | ODPO는 점수 차에 비례한 offset을 둬요. 데이터가 적을 때 특히 좋았어요 [[46]](https://arxiv.org/abs/2402.10571). 현재 TRL `loss_type` 목록에는 ODPO가 없어요 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer) |
| reference 없는 방법 | SimPO는 평균 로그확률을 보상으로 쓰고 목표 margin γ를 둬요 [[47]](https://arxiv.org/abs/2405.14734). ORPO는 SFT와 선호 학습을 한 단계로 합쳐요 [[41]](https://arxiv.org/abs/2403.07691). 둘 다 P0 SFT → P2 DPO 구조를 바꾸므로 3일 범위에는 권하지 않아요 |
| TRL 설정 | `DPOConfig` 기본값: `beta=0.1`, `learning_rate=1e-6`, `max_length=1024`, `loss_type=["sigmoid"]`. `loss_type` 목록 + `loss_weights`로 여러 손실을 섞을 수 있고 `"sft"`가 있어요. 어댑터 학습 시 lr 약 1e-5를 권해요. `precompute_ref_log_probs=True`는 ref 모델을 메모리에 두지 않게 해요 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer) |
| TRL PEFT ref 처리 | 현재 main 소스는 이미 학습된 어댑터가 있는 `PeftModel`을 `ref_model=None`으로 넘기면 `"ref"` 어댑터를 복사해 **SFT 어댑터를 reference로** 써요. 새 어댑터면 어댑터를 끈 Base가 reference예요 [[50]](https://github.com/huggingface/trl/blob/main/trl/trainer/dpo_trainer.py). 최신 릴리스는 v1.14.0(2026-09-25)이에요 [[51]](https://github.com/huggingface/trl/releases/tag/v1.14.0). 설치 버전이 같은 동작인지는 **미확인**이라 아래 0단계 확인이 필요해요 |

### 5-2. 우리 계획의 off-policy 문제

| 문제 | 설명 |
| --- | --- |
| chosen·rejected 모두 SFT 모델 출력이 아님 | Base와 탐색 출력이에요. SFT 이후 어댑터는 이미 Base의 흔한 실수를 덜 하므로, Base의 최저점 샘플은 **SFT가 이미 거의 만들지 않는 실수**예요. 이걸 밀어내도 개선 여지가 작아요 [[40]](https://arxiv.org/abs/2404.14367) |
| 출처 말투가 구분 단서 | chosen이 탐색 출신(10:00 출발, 최근접 순서)이고 rejected가 Base 출신이면, 품질보다 "출처 모양"으로 구분하는 쉬운 길이 생겨요 (추론) |
| chosen = SFT 정답 | SFT가 이미 학습한 정답이라 chosen 쪽 신호가 작고, DPO가 chosen 확률까지 낮추는 위험이 있어요 [[39]](https://arxiv.org/html/2404.19733) [[44]](https://arxiv.org/abs/2402.13228) |

### 5-3. 가장 싼 대응: 서빙 창에서 on-policy 샘플 생성

7-4의 **9/29 15:00–17:00**에는 vLLM이 SFT 어댑터(`itin`)를 올린 상태예요. 이때 A가 학습 프로필 400개 × `n=4`(T=0.7)를 배치 요청으로 보내면 on-policy 샘플이 생겨요. 출력이 짧아 E의 연결 확인을 크게 방해하지 않을 것으로 보여요 (**미확인**, 요청 수를 나눠 보내요). 서빙은 bf16, 학습은 4bit라 완전한 on-policy는 아니지만 Base 샘플보다 훨씬 가까워요.

**쌍 구성 규칙 (4-3 대체안)**

| # | 규칙 |
| --- | --- |
| 1 | 후보 = SFT 샘플 4개 (검증 통과만) + 기존 SFT 정답 1개. 모두 같은 코드로 JSON 정규화 |
| 2 | chosen = 후보 중 최고점, 단 75점 이상 · 위반 0. **SFT 샘플이 기준을 넘으면 SFT 샘플을 우선**해요 (3점 이내면 SFT 샘플) |
| 3 | rejected = **SFT 샘플 중** 최저점. 검증 통과 필수 |
| 4 | 점수 차 15점 이상 (계획대로). 추가로 **방문지 집합이 완전히 같은 쌍은 제외**해요 (시각만 다른 쌍은 편집 거리가 작아요 [[44]](https://arxiv.org/abs/2402.13228) [[45]](https://arxiv.org/abs/2410.08847)) |
| 5 | 쌍이 150개 미만이면 기존 계획(Base 최저점 rejected)으로 부족분을 채우고, 결과 문서에 출처별 개수를 적어요 |
| 6 | 16:00에 D가 채점·쌍 생성(CPU)을 끝내고, 17:00 DPO를 시작해요 |

**DPO 설정 (4-4 보강)**

```python
from trl import DPOConfig
args = DPOConfig(
    loss_type=["sigmoid", "sft"],   # DPO + NLL (Iterative RPO 방식)
    loss_weights=[1.0, 1.0],        # RPO는 α=1을 썼어요. 출발값이에요
    beta=0.1,                       # TRL 기본값, RPO GSM8K도 0.1
    learning_rate=1e-5,             # TRL 어댑터 권장 ≈1e-5 (계획 2e-5보다 낮춤)
    num_train_epochs=1,
    max_length=2048,                # 기본 1024면 JSON이 잘려요
    precompute_ref_log_probs=True,
)
# model = AutoPeftModelForCausalLM.from_pretrained("itin-sft", is_trainable=True, quantization_config=bnb_config)
# DPOTrainer(model=model, ref_model=None, args=args, ...)
```

- `"sft"` 손실이 `loss_type` 목록 조합으로 지원되는 것은 문서로 확인했어요 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer). 가중치 1.0은 RPO의 α=1 [[39]](https://arxiv.org/html/2404.19733)을 옮긴 값이고 우리 과제에서 검증된 값은 아니에요.
- **0단계 확인:** ref가 SFT 어댑터이고 정책도 SFT에서 시작하면 첫 스텝의 로그비는 0이라서 `rewards/chosen`, `rewards/rejected`가 0 근처, DPO 손실이 ln 2 ≈ 0.693이어야 해요 (DPO 식에서 유도 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer)). 0에서 크게 벗어나면 ref가 Base로 잡힌 것이므로 멈추고 버전을 확인해요.
- **학습 중 감시:** `logps/chosen`이 계속 떨어지면 likelihood displacement 신호예요 [[45]](https://arxiv.org/abs/2410.08847). `rewards/accuracies`가 첫 수십 스텝에 1.0에 붙으면 쌍이 너무 쉬운 것(출처 모양 구분)일 수 있어요.

**계획 수정 제안 (4-3):**
- "쌍" 행: rejected를 "9/29 15–17시 SFT 어댑터 샘플 중 최저점"으로 바꾸고, 부족분만 Base 샘플로 채워요.
- "쌍 조건" 행: "방문지 집합이 같은 쌍 제외"를 추가해요.
- "reference" 행: "첫 스텝 `rewards/*` ≈ 0 확인"을 추가해요.
- 4-4 DPO 열: lr 2e-5 → 1e-5, `loss_type=["sigmoid","sft"]`, `max_length=2048` 명시를 추가해요.
- 7-4 9/29 15:00–17:00 행에 "SFT 어댑터로 학습 프로필 400 × 4 샘플 생성 (A)", 7-5 9/29 D 열에 "16시 on-policy 쌍 생성"을 추가해요.
- "한계" 행은 "대부분 on-policy, 부족분은 off-policy"로 고쳐요.

---

## 6. 위험과 한계

| 위험 | 내용 | 대응 |
| --- | --- | --- |
| 채점기 = 선별기 = 평가기 | SFT·DPO 데이터를 Model 2로 고르고 Model 2로 평가해요. 점수 상승은 채점기 과최적화일 수 있어요 [[36]](https://arxiv.org/abs/2210.10760) | 5-1 블라인드 비교 유지, 선별 정답 20개 사람 확인 (4-2 규칙 8) |
| 탐색 편중 | 탐색이 정답 대부분이면 SFT ≈ 규칙 탐색 흉내가 되고 기준선을 넘기 어려워요 | N을 p로 먼저 결정, 3점 이내 LLM 우선, 출처 비율 공개 |
| 같은 Base가 생성·필터·기준선 | 취향 문장 생성, 라벨 확인, P1 비교 대상이 모두 같은 Base예요. 분포가 좁고 Base가 틀리는 표현이 빠질 수 있어요 [[14]](https://arxiv.org/abs/2305.17493) | 사람이 쓴 예시 풀, 부정 유형 사람 검수, 유형별 탈락률 기록, 평가는 사람 문장으로만 |
| 부정 일반화 | 부정 문장으로 학습해도 일반화가 부족하다는 보고가 있어요 [[13]](https://arxiv.org/abs/2310.15941) | 5-2 결과를 유형별(직접/간접/부정)로 나눠 보고해요 |
| 4bit 학습 · bf16 서빙 | 서빙 창 on-policy 샘플도 학습 정책과 정확히 같지 않아요 | 한계로 적어요 |
| 쌍 부족 | on-policy 쌍이 15점 차 조건에서 적을 수 있어요 | 부족분 Base로 채우고 개수 공개. ODPO처럼 차이에 비례한 가중은 TRL에 없어서 하지 않아요 [[49]](https://huggingface.co/docs/trl/main/en/dpo_trainer) |
| TRL 버전 차이 | PEFT ref 처리 방식이 버전마다 다를 수 있어요 (**미확인**) | 0단계 `rewards/*` ≈ 0 확인 |
| 수치 출발값 | T 0.9, Jaccard 0.7, 비율 상한 5%, 3점 이내 우선, NLL 가중 1.0은 근거를 옮기거나 추정한 값이에요 | 10개 시험 실행 결과로 한 번만 조정해요 |
| 필요 데이터 수 | 좁은 JSON 과제 QLoRA SFT의 적정 개수는 1차 근거가 없어요 (**미확인**) | 검증 loss와 형식 통과율로 판단해요 |
| 모의 커버리지 수치 | 2-1의 99.9% / 86% / 99%는 가정한 수준 수로 한 자체 계산이에요 | companion 확정 후 다시 계산해요 |

---

## 7. 출처 목록

1. Kuhn, Kacker, Lei. *Practical Combinatorial Testing*. NIST SP 800-142, 2010. https://csrc.nist.gov/pubs/sp/800/142/final
2. SciPy `scipy.stats.qmc.LatinHypercube` 문서 (McKay et al., Technometrics 1979 인용). https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html
3. scikit-learn `train_test_split` 문서. https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.train_test_split.html
4. Keysers et al. *Measuring Compositional Generalization: A Comprehensive Method on Realistic Data*. ICLR 2020. https://arxiv.org/abs/1912.09713
5. Rastogi, Zang, Sunkara, Gupta, Khaitan. *Towards Scalable Multi-domain Conversational Agents: The Schema-Guided Dialogue Dataset*. 2019. https://arxiv.org/abs/1909.05855
6. Yu et al. *Large Language Model as Attributed Training Data Generator: A Tale of Diversity and Bias*. NeurIPS 2023. https://arxiv.org/abs/2306.15895
7. Ge et al. *Scaling Synthetic Data Creation with 1,000,000,000 Personas*. 2024. https://arxiv.org/abs/2406.20094
8. Wang et al. *Self-Instruct: Aligning Language Models with Self-Generated Instructions*. 2022. https://arxiv.org/abs/2212.10560 (본문: https://arxiv.org/html/2212.10560)
9. Alberti, Andor, Pitler, Devlin, Collins. *Synthetic QA Corpora Generation with Roundtrip Consistency*. 2019. https://arxiv.org/abs/1906.05416
10. Sahu et al. *Data Augmentation for Intent Classification with Off-the-shelf Large Language Models*. 2022. https://arxiv.org/abs/2204.01959
11. Li, Zhu, Lu, Yin. *Synthetic Data Generation with Large Language Models for Text Classification: Potential and Limitations*. 2023. https://arxiv.org/abs/2310.07849
12. Truong, Baldwin, Verspoor, Cohn. *Language models are not naysayers: An analysis of language models on negation benchmarks*. 2023. https://arxiv.org/abs/2306.08189
13. García-Ferrero et al. *This is not a Dataset: A Large Negation Benchmark to Challenge Large Language Models*. EMNLP 2023. https://arxiv.org/abs/2310.15941
14. Shumailov et al. *The Curse of Recursion: Training on Generated Data Makes Models Forget*. 2023. https://arxiv.org/abs/2305.17493
15. Lee et al. *Deduplicating Training Data Makes Language Models Better*. ACL 2022. https://arxiv.org/abs/2107.06499
16. Abbas et al. *SemDeDup: Data-efficient learning at web-scale through semantic deduplication*. 2023. https://arxiv.org/abs/2303.09540
17. vLLM 문서 · Structured Outputs. https://docs.vllm.ai/en/latest/features/structured_outputs.html
18. vLLM 문서 · SamplingParams. https://docs.vllm.ai/en/latest/api/vllm/sampling_params.html
19. Qwen3-8B 모델 카드. https://huggingface.co/Qwen/Qwen3-8B
20. Yuan et al. *Scaling Relationship on Learning Mathematical Reasoning with Large Language Models*. 2023. https://arxiv.org/abs/2308.01825 (본문: https://arxiv.org/html/2308.01825)
21. Zelikman, Wu, Mu, Goodman. *STaR: Bootstrapping Reasoning With Reasoning*. 2022. https://arxiv.org/abs/2203.14465
22. Gulcehre et al. *Reinforced Self-Training (ReST) for Language Modeling*. 2023. https://arxiv.org/abs/2308.08998
23. Singh et al. *Beyond Human Data: Scaling Self-Training for Problem-Solving with Language Models*. TMLR, 2023. https://arxiv.org/abs/2312.06585
24. Anthony, Tian, Barber. *Thinking Fast and Slow with Deep Learning and Tree Search*. 2017. https://arxiv.org/abs/1705.08439
25. Zhou et al. *LIMA: Less Is More for Alignment*. 2023. https://arxiv.org/abs/2305.11206
26. Dettmers, Pagnoni, Holtzman, Zettlemoyer. *QLoRA: Efficient Finetuning of Quantized LLMs*. 2023. https://arxiv.org/abs/2305.14314
27. Chen et al. *AlpaGasus: Training A Better Alpaca with Fewer Data*. 2023. https://arxiv.org/abs/2307.08701
28. Xie et al. *TravelPlanner: A Benchmark for Real-World Planning with Language Agents*. ICML 2024. https://arxiv.org/abs/2402.01622 (본문: https://arxiv.org/html/2402.01622)
29. Tang et al. *ITINERA: Integrating Spatial Optimization with Large Language Models for Open-domain Urban Itinerary Planning*. EMNLP 2024 Industry. https://arxiv.org/abs/2402.07204
30. de la Rosa et al. *TRIP-PAL: Travel Planning with Guarantees by Combining Large Language Models and Automated Planners*. 2024. https://arxiv.org/abs/2406.10196
31. Chen et al. *TravelAgent: An AI Assistant for Personalized Travel Planning*. 2024. https://arxiv.org/abs/2409.08069
32. Gundawar et al. *Robust Planning with LLM-Modulo Framework: Case Study in Travel Planning*. 2024. https://arxiv.org/abs/2405.20625
33. Hao, Chen, Zhang, Fan. *Large Language Models Can Solve Real-World Planning Rigorously with Formal Verification Tools*. 2024. https://arxiv.org/abs/2404.11891
34. Lehnert et al. *Beyond A\*: Better Planning with Transformers via Search Dynamics Bootstrapping*. 2024. https://arxiv.org/abs/2402.14083
35. Yang et al. *Self-Distillation Bridges Distribution Gap in Language Model Fine-Tuning*. ACL 2024. https://arxiv.org/abs/2402.13669
36. Gao, Schulman, Hilton. *Scaling Laws for Reward Model Overoptimization*. 2022. https://arxiv.org/abs/2210.10760 (PDF: https://arxiv.org/pdf/2210.10760)
37. Yuan et al. *Self-Rewarding Language Models*. ICML 2024. https://arxiv.org/abs/2401.10020 (본문: https://arxiv.org/html/2401.10020)
38. Rafailov et al. *Direct Preference Optimization: Your Language Model is Secretly a Reward Model*. 2023. https://arxiv.org/abs/2305.18290
39. Pang et al. *Iterative Reasoning Preference Optimization*. 2024. https://arxiv.org/abs/2404.19733 (본문: https://arxiv.org/html/2404.19733)
40. Tajwar et al. *Preference Fine-Tuning of LLMs Should Leverage Suboptimal, On-Policy Data*. ICML 2024. https://arxiv.org/abs/2404.14367
41. Hong, Lee, Thorne. *ORPO: Monolithic Preference Optimization without Reference Model*. 2024. https://arxiv.org/abs/2403.07691
42. Khaki et al. *RS-DPO: A Hybrid Rejection Sampling and Direct Preference Optimization Method for Alignment of Large Language Models*. 2024. https://arxiv.org/abs/2402.10038 (본문: https://arxiv.org/html/2402.10038)
43. Xiao et al. *Finding the Sweet Spot: Preference Data Construction for Scaling Preference Optimization*. 2025. https://arxiv.org/abs/2502.16825
44. Pal et al. *Smaug: Fixing Failure Modes of Preference Optimisation with DPO-Positive*. 2024. https://arxiv.org/abs/2402.13228
45. Razin et al. *Unintentional Unalignment: Likelihood Displacement in Direct Preference Optimization*. ICLR 2025. https://arxiv.org/abs/2410.08847
46. Amini, Vieira, Cotterell. *Direct Preference Optimization with an Offset*. 2024. https://arxiv.org/abs/2402.10571
47. Meng, Xia, Chen. *SimPO: Simple Preference Optimization with a Reference-Free Reward*. NeurIPS 2024. https://arxiv.org/abs/2405.14734
48. Hugging Face TRL 문서 · SFT Trainer (`SFTConfig`). https://huggingface.co/docs/trl/main/en/sft_trainer
49. Hugging Face TRL 문서 · DPO Trainer (`DPOConfig`). https://huggingface.co/docs/trl/main/en/dpo_trainer
50. TRL 소스 `trl/trainer/dpo_trainer.py` (main, 2026-09-26 확인). https://github.com/huggingface/trl/blob/main/trl/trainer/dpo_trainer.py
51. TRL 릴리스 v1.14.0 (2026-09-25). https://github.com/huggingface/trl/releases/tag/v1.14.0
