from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ModelMode = Literal["base", "lora", "qlora"]
TrainMode = Literal["lora", "qlora"]


@dataclass(frozen=True)
class ModelConfig:
    mode: ModelMode
    model_id: str


@dataclass(frozen=True)
class TrainConfig:
    mode: TrainMode
    model_id: str

    train_file: Path
    split_file: Path
    gold_file: Path
    output_path: Path

    # 재현성을 위해 seed 값을 설정
    seed: int = 42
    # 입력 리뷰와 출력 JSON을 합친 최대 토큰의 길이를 제한한다.
    max_seq_length: int = 2048
    # 학습 설정
    num_train_epochs: int = 3
    learning_rate: float = 2e-4
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    # gradient accumulation 은 작은 batch를 여러 번 계산한 뒤 gradient 를 합쳐 한 번 업데이트하는 방법입니다. 메모리를 절약하면서 큰 batch와 비슷한 학습 효과를 얻을 수 있습니다.
    # gpu 메모리가 부족할 때여러 step 의 gradient 을 모은 뒤 한 번에 업데이트하는 방법이다.
    gradient_accumulation_steps: int = 16
    # 학습 초기에 learning rate를 바로 최대값으로 사용하지 않고 서서히 증가시키는 비율입니다.
    warmup_ratio: float = 0.05

    # LoRA 설정
    # Rank: LoRA가 학습할 추가 행렬의 표현 크기입니다. 값이 커질수록 표현력은 늘지만 학습 파라미터와 과적합 위험도 증가합니다.
    lora_r: int = 16
    # LoRA 업데이트의 scaling 값입니다.
    lora_alpha: int = 32
    lora_dropout: float = 0.05

    # 저장과 평가 주기
    save_total_limit: int = 2
    logging_steps: int = 10
