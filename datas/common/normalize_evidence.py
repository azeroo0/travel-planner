"""evidence의 자르는 경계를 한 기준으로 맞춘다.

Silver 라벨러가 만든 evidence는 마침표를 넣기도 빼기도 하고, 문장 앞의 "전반적으로" 같은 부사를 넣기도 빼기도 한다.
모델이 그 들쭉날쭉한 기준을 그대로 배워 evidence 완전일치 점수가 낮아지므로, 다음 두 가지만 자동으로 맞춘다.
1. 끝의 문장부호(. ! ? , ~ …)와 공백을 뗀다. 끝의 이모티콘은 가이드라인대로 원문 그대로 둔다.
2. 앞의 군더더기 부사(LEADING_FILLERS)를 뗀다. 목록은 validation의 첫 어절 빈도를 보고 정했다 (test는 보지 않았다).
   "생각보다"처럼 라벨의 뜻을 바꾸는 말과 "좀"처럼 정도를 나타내는 말은 뗀 뒤에 뜻이 달라지므로 넣지 않았다.

결과는 항상 원문에 그대로 있는 비어 있지 않은 구절이고, 그렇지 못하면 원래 evidence를 돌려준다.
"""

from __future__ import annotations

from typing import Any, Final

TRAILING_PUNCTUATION: Final = ".!?,~…"
LEADING_FILLERS: Final = ("전반적으로는", "전반적으로", "전체적으로는", "전체적으로", "솔직히", "그래도")
MIN_LENGTH: Final = 3


def strip_leading_filler(evidence: str) -> str:
    for filler in LEADING_FILLERS:
        if evidence.startswith(filler + " "):
            return evidence[len(filler):].lstrip(" ,")
    return evidence


def strip_trailing_punctuation(evidence: str) -> str:
    return evidence.rstrip().rstrip(TRAILING_PUNCTUATION).rstrip()


def normalize_evidence(evidence: str, review: str) -> str:
    normalized = strip_trailing_punctuation(strip_leading_filler(evidence.strip()))
    if len(normalized) < MIN_LENGTH or normalized not in review:
        return evidence
    return normalized


def normalize_label(label: dict[str, Any], review: str) -> tuple[dict[str, Any], int]:
    """label의 evidence를 정규화한 새 label과 바뀐 evidence 수를 돌려준다."""
    aspects = []
    changed = 0
    for aspect in label["aspects"]:
        evidence = normalize_evidence(aspect["evidence"], review)
        changed += evidence != aspect["evidence"]
        aspects.append({**aspect, "evidence": evidence})
    return {**label, "aspects": aspects}, changed
