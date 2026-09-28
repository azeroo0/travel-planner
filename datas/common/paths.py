"""팀 데이터 폴더 규칙. 모든 공통 도구가 경로를 여기서 가져간다.

  datas/
    common/            공통 코드와 팀 공유 분할(split.json)
    <이니셜>/          팀원 한 명의 원본 데이터 (JSON 등, 형식은 자유)
      out/             공통 형식 결과. places_*.json, real_reviews.jsonl, runs/<실행 이름>/

테스트할 때는 환경 변수 TRIPFIT_DATAS로 datas 폴더 위치를 바꿀 수 있다.
"""

import json
import os
from pathlib import Path
from typing import Final

COMMON: Final = Path(__file__).parent
DATAS: Final = Path(os.environ.get("TRIPFIT_DATAS", COMMON.parent))
SPLIT_PATH: Final = DATAS / "common" / "split.json"  # 팀 전체가 공유하는 장소 분할. 커밋한다
NOT_MEMBERS: Final = {"common", "__pycache__"}


def member_dir(member: str) -> Path:
    path = DATAS / member
    if member in NOT_MEMBERS or not path.is_dir():
        raise SystemExit(f"팀원 폴더가 없습니다: {path} (있는 폴더: {', '.join(members()) or '없음'})")
    return path


def member_out(member: str) -> Path:
    return member_dir(member) / "out"


def members() -> list[str]:
    """datas/ 아래의 팀원 폴더 이름 (common 제외)."""
    return sorted(p.name for p in DATAS.iterdir() if p.is_dir() and p.name not in NOT_MEMBERS and not p.name.startswith("."))


def load_places(member: str | None = None) -> dict[str, dict]:
    """place_id → 장소. member를 주면 그 팀원 것만, 안 주면 팀 전체의 out/places_*.json을 읽는다."""
    names = [member] if member else members()
    places: dict[str, dict] = {}
    for name in names:
        for path in sorted((DATAS / name / "out").glob("places_*.json")):
            for place in json.loads(path.read_text(encoding="utf-8")):
                places[place["place_id"]] = place
    return places
