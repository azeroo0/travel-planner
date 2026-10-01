"""주제가 분명한 aspect의 evidence에 그 주제의 단어가 있는지 확인한다.

모델이 리뷰가 말하지 않은 주제(예: 주차)를 지어내면 근거로 엉뚱한 구절("엘리베이터를 타고 내려가던 중")을 붙인다.
주제가 분명한 aspect는 근거 구절에 그 주제의 단어가 있어야 하므로, 없으면 지어낸 것으로 본다.

기준
- aspect의 뜻에서 어휘를 뽑았고 test는 보지 않고 학습 데이터 라벨의 오탈락률(주제 단어가 없는데 라벨이 맞는 경우)로 정했다.
  train 라벨에서 오탈락률이 8% 이하인 aspect만 넣었다 (rest_facilities 61%, view_quality 16%, bed_comfort 10%, stay_duration 9%는 표현이 다양해 뺐다).
- portion·serving_speed는 오탈락률은 낮지만 어휘가 너무 넓어("많", "바로") 걸러 내지 못하므로 뺐다.
- 목록을 넓히거나 aspect를 더할 때는 학습 라벨의 오탈락률을 다시 재고, 평가 결과를 보고 맞추지 않는다.
"""

from __future__ import annotations

import re
from typing import Final

TOPIC_KEYWORDS: Final[dict[str, re.Pattern[str]]] = {
    "parking_availability": re.compile("주차|차를|차량|차 |자가용|발렛"),
    "parking_experience": re.compile("주차|차를|차량|차 |자가용|발렛"),
    "photo_spots": re.compile("사진|포토|인생|촬영|카메라|찍"),
    "freshness": re.compile("신선|싱싱|재료|비린|상한|냉동"),
    "waiting_time": re.compile("웨이팅|대기|기다|줄|오래 걸|바로 입장|바로 앉|자리"),
    "noise_level": re.compile("조용|시끄|소음|북적|한적|고요|떠들|시끌|음악|소리"),
    "toilet_facilities": re.compile("화장실"),
    "breakfast_quality": re.compile("조식|아침|뷔페"),
    "weather_sensitivity": re.compile("날씨|비 |비가|햇|더위|더운|추위|추운|바람|실내|야외|그늘|우산|덥|춥"),
    "slope_stairs": re.compile("계단|언덕|경사|오르막|가파|비탈|오르|내리막"),
    "family_friendly": re.compile("가족|아이|애기|어린이|아기|유모차|키즈|부모|아들|딸"),
    "bathroom_quality": re.compile("욕실|샤워|화장실|수압|욕조|세면|비데|온수|배수|물"),
}


def mentions_topic(aspect: str, evidence: str) -> bool:
    """주제 규칙이 없는 aspect는 항상 통과하고, 있으면 evidence에 주제 단어가 있어야 통과한다."""
    pattern = TOPIC_KEYWORDS.get(aspect)
    return pattern is None or bool(pattern.search(evidence))
