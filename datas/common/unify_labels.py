"""호텔의 cleanliness와 room_condition을 뜻으로 나눠 라벨을 일관되게 맞춘다.

Silver 라벨러가 같은 "깨끗하다"를 어떨 땐 cleanliness로, 어떨 땐 room_condition으로 달아서
(학습 데이터의 호텔 evidence 중 깨끗/깔끔이 든 것의 42%가 room_condition이었다) 모델이 그 불일치를 그대로 배웠다.
기준은 다음과 같다. docs/annotation-guideline.md의 3절에도 적어 두었다.

- cleanliness   더럽거나 깨끗한 정도 (깨끗·깔끔·청결·쾌적·더럽·지저분·얼룩·곰팡이·먼지)
- room_condition 시설이 낡았거나 잘 갖춰진 정도 (낡음·노후·리모델링·수리·고장·세련·모던)

evidence에 청결 표현만 있으면 cleanliness로, 시설 상태 표현만 있으면 room_condition으로 옮긴다.
두 표현이 함께 있으면 애매하므로 그대로 둔다. sentiment는 바꾸지 않고, attribute만 새 aspect의 값으로 바꾼다.
"""

from __future__ import annotations

import re
from typing import Any, Final

CLEAN_WORDS: Final = re.compile("깨끗|깔끔|청결|쾌적|말끔|정갈|위생|더럽|더러|지저분|불결|얼룩|곰팡이|먼지")
DIRTY_WORDS: Final = re.compile("더럽|더러|지저분|불결|얼룩|곰팡이|먼지|(깨끗|깔끔|청결)\\S{0,4}\\s?(않|못|아쉬)")
CONDITION_WORDS: Final = re.compile("낡|오래된|오래돼|노후|허름|낙후|리모델링|수리|고장|세련|모던|고급스")

ROOM_TO_CLEAN: Final = {"well_kept": "clean", "average": "average", "worn": "dirty"}
CLEAN_TO_ROOM: Final = {"clean": "well_kept", "average": "average", "dirty": "worn"}


def to_cleanliness(aspect: dict[str, Any]) -> dict[str, Any]:
    attribute = "dirty" if DIRTY_WORDS.search(aspect["evidence"]) else ROOM_TO_CLEAN[aspect["attribute"]]
    return {**aspect, "category": "cleanliness", "attribute": attribute}


def to_room_condition(aspect: dict[str, Any]) -> dict[str, Any]:
    return {**aspect, "category": "room_condition", "attribute": CLEAN_TO_ROOM[aspect["attribute"]]}


def unify_aspect(aspect: dict[str, Any]) -> dict[str, Any]:
    evidence = aspect["evidence"]
    has_clean, has_condition = bool(CLEAN_WORDS.search(evidence)), bool(CONDITION_WORDS.search(evidence))
    if aspect["category"] == "room_condition" and has_clean and not has_condition:
        return to_cleanliness(aspect)
    if aspect["category"] == "cleanliness" and has_condition and not has_clean:
        return to_room_condition(aspect)
    return aspect


def unify_label(label: dict[str, Any], place_category: str) -> tuple[dict[str, Any], int]:
    """호텔 label의 두 aspect를 기준에 맞춘 새 label과 바뀐 aspect 수를 돌려준다. 호텔이 아니면 그대로다."""
    if place_category != "hotel":
        return label, 0
    aspects = [unify_aspect(aspect) for aspect in label["aspects"]]
    changed = sum(new is not old for new, old in zip(aspects, label["aspects"]))
    return {**label, "aspects": aspects}, changed
