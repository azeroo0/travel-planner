"""SFT 학습과 추론에서 함께 사용하는 리뷰 추출 prompt.

전략 A에서는 모델이 리뷰 원문에서 직접 확인할 수 있는 정보만 추출한다.
장소 fact 기반 라벨(``place:<field>=<value>``)은 이 prompt의 학습 대상이
아니며, 별도의 장소 fact 후처리 단계에서 추가한다.
"""

from __future__ import annotations

from typing import Final


CATEGORIES: Final[frozenset[str]] = frozenset({"hotel", "restaurant", "attraction"})


def build_system_message() -> str:
    """모델의 역할과 리뷰 기반 추출 규칙을 정의한다."""
    return "\n".join(
        [
            "당신은 한국어 여행 리뷰에서 구조화 정보를 추출하는 모델입니다.",
            "입력된 category에 맞춰 리뷰 원문에 직접 근거가 있는 정보만 추출하세요.",
            "리뷰에 없는 내용은 장소의 유명세, 상식, 추측으로 보완하지 마세요.",
            "장소 정보나 외부 지식에 기반한 aspect는 출력하지 마세요.",
            "응답은 반드시 하나의 JSON 객체만 출력하세요.",
            "Markdown 코드 블록, 설명 문장, 주석은 출력하지 마세요.",
            "JSON의 최상위 필드는 traveler_context와 aspects만 사용하세요.",
            "각 aspect에는 category, attribute, sentiment, evidence를 포함하세요.",
            "attribute는 리뷰에 나타난 상태이고 sentiment는 그 상태에 대한 평가입니다.",
            "evidence는 판단을 뒷받침하는 가장 짧은 연속 구절을 원문 그대로 복사하세요.",
            "evidence를 요약하거나 맞춤법을 고치거나 문장을 새로 만들지 마세요.",
            "동행자가 명시되지 않았다면 traveler_context는 빈 배열로 출력하세요.",
            "허용되지 않은 값이나 리뷰에 근거가 없는 aspect는 출력하지 마세요.",
        ]
    )


def build_user_message(category: str, review: str) -> str:
    """category와 리뷰 원문만 모델 입력으로 만든다."""
    if category not in CATEGORIES:
        raise ValueError(f"지원하지 않는 category입니다: {category!r}")
    if not isinstance(review, str) or not review.strip():
        raise ValueError("review는 비어 있지 않은 문자열이어야 합니다")

    return f"[category]\n{category}\n\n[review]\n{review}"


def build_prompt(category: str, review: str) -> list[dict[str, str]]:
    """SFTTrainer와 inference가 공통으로 사용하는 chat prompt를 만든다."""
    return [
        {
            "role": "system",
            "content": build_system_message(),
        },
        {
            "role": "user",
            "content": build_user_message(category, review),
        },
    ]
