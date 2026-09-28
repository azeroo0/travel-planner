"""팀 전체 장소를 학습/검증/테스트로 나누고, 테스트 장소의 Silver 리뷰를 Gold 검수 대기 파일로 뽑는다.

리뷰가 아니라 장소 단위로 나눈다. 같은 장소의 리뷰가 학습과 테스트에 함께 들어가면
모델이 추출 능력이 아니라 장소를 외워서 맞힐 수 있기 때문이다.
출처가 달라 place_id가 다른 같은 장소(같은 지역에서 도로명 주소나 이름이 같은 곳)는
한 묶음으로 보고 같은 쪽에 넣는다. 같은 건물의 다른 가게가 묶일 수 있지만 누수보다 안전하다.

분할은 팀 전체가 datas/common/split.json 하나를 공유한다 (모든 실험이 같은 테스트셋을 쓴다).
  - 이미 배정된 장소는 절대 바꾸지 않는다. 그래서 이미 검수한 Gold가 그대로 유지된다.
  - 새 장소가 이미 배정된 장소와 같은 묶음이면 그 분할을 따른다.
  - 나머지 새 장소는 카테고리 × 지역마다 학습 80 / 검증 10 / 테스트 10으로 나눈다.
    층마다 난수를 따로 만들어서, 다른 지역 장소가 늘어나도 기존 층의 배정이 흔들리지 않는다.

사용법:
  uv run python datas/common/split_places.py                                # 분할만 갱신
  uv run python datas/common/split_places.py --member cjm --run silver_v1   # + 테스트 검수 대기 파일
  → datas/cjm/out/runs/silver_v1/test/silver.jsonl
"""

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Final, Iterator

from paths import SPLIT_PATH, load_places, member_out
from schema import CATEGORIES

SPLITS: Final = ("train", "val", "test")
RATIOS: Final = {"val": 0.1, "test": 0.1}  # 나머지는 train
ROAD_ADDRESS: Final = re.compile(r"([가-힣0-9]+(?:로|길))\s+(\d+(?:-\d+)?)")
UNKNOWN_DISTRICT: Final = "unknown"


# ---------- 같은 장소 묶기 ----------


def road_key(address: str) -> str | None:
    """'부산광역시 해운대구 구남로8번길 38 (우동)' → '구남로8번길 38'. 도로명 주소가 아니면 None."""
    address = re.sub(r"\s+(\d+번길)", r"\1", re.split(r"[(,]", address)[0])  # '반송로 571번길' → '반송로571번길'
    match = ROAD_ADDRESS.search(address)
    return f"{match[1]} {match[2]}" if match else None


def name_key(name: str) -> str:
    """'해광사(한,영,중간,중번,일)' → '해광사'. 괄호 안과 공백을 지우고 소문자로 맞춘다."""
    return re.sub(r"\(.*?\)|\s", "", name).lower()


def same_place_keys(place: dict) -> Iterator[tuple[str, str, str]]:
    road = road_key(place["address"] or "")
    if road:
        yield ("road", place["district"], road)
    name = name_key(place["name"])
    if name:
        yield ("name", place["district"], name)


def group_places(places: list[dict]) -> list[list[dict]]:
    """키가 하나라도 같은 장소끼리 묶는다 (union-find)."""
    parent = {place["place_id"]: place["place_id"] for place in places}

    def root(place_id: str) -> str:
        while parent[place_id] != place_id:
            place_id = parent[place_id]
        return place_id

    first_with_key: dict[tuple[str, str, str], str] = {}
    for place in places:
        for key in same_place_keys(place):
            other = first_with_key.setdefault(key, place["place_id"])
            parent[root(place["place_id"])] = root(other)

    groups: dict[str, list[dict]] = defaultdict(list)
    for place in places:
        groups[root(place["place_id"])].append(place)
    return list(groups.values())


# ---------- 분할 ----------


def stratum(group: list[dict]) -> tuple[str, str]:
    """묶음의 층: place_id가 가장 앞서는 장소의 (카테고리, 지역)."""
    first = min(group, key=lambda place: place["place_id"])
    return first["category"], first["district"] or UNKNOWN_DISTRICT


def split_new_groups(groups: list[list[dict]], seed: int) -> dict[str, str]:
    """층마다 묶음을 섞어 앞에서부터 test, val, 나머지 train으로 배정한다."""
    by_stratum: dict[tuple[str, str], list[list[dict]]] = defaultdict(list)
    for group in sorted(groups, key=lambda g: min(place["place_id"] for place in g)):
        by_stratum[stratum(group)].append(group)

    assignment: dict[str, str] = {}
    for key, stratum_groups in by_stratum.items():
        rng = random.Random(f"{seed}:{key[0]}:{key[1]}")  # 층마다 따로: 다른 층이 늘어도 영향 없음
        rng.shuffle(stratum_groups)
        n_test = round(len(stratum_groups) * RATIOS["test"])
        n_val = round(len(stratum_groups) * RATIOS["val"])
        for index, group in enumerate(stratum_groups):
            split = "test" if index < n_test else "val" if index < n_test + n_val else "train"
            assignment |= {place["place_id"]: split for place in group}
    return assignment


def inherited_split(group: list[dict], existing: dict[str, str]) -> str | None:
    """묶음 안에 이미 배정된 장소가 있으면 그 분할. 여러 개면 가장 많은 쪽."""
    splits = [existing[place["place_id"]] for place in group if place["place_id"] in existing]
    return Counter(splits).most_common(1)[0][0] if splits else None


def update_split(places: dict[str, dict], existing: dict[str, str], seed: int) -> dict[str, str]:
    """기존 배정은 그대로 두고, 아직 배정되지 않은 장소만 배정한다."""
    groups = group_places(list(places.values()))
    assignment = dict(existing)
    fresh: list[list[dict]] = []
    for group in groups:
        new = [place for place in group if place["place_id"] not in existing]
        if not new:
            continue
        split = inherited_split(group, existing)
        if split:
            assignment |= {place["place_id"]: split for place in new}
        else:
            fresh.append(new)
    assignment |= split_new_groups(fresh, seed)
    added = len(assignment) - len(existing)
    print(f"장소 {len(places)}곳 → 묶음 {len(groups)}개 / 기존 배정 {len(existing)}곳 유지, 새로 배정 {added}곳")
    return assignment


def load_split() -> dict[str, str]:
    return json.loads(SPLIT_PATH.read_text(encoding="utf-8")) if SPLIT_PATH.exists() else {}


def save_split(assignment: dict[str, str]) -> None:
    SPLIT_PATH.write_text(json.dumps(assignment, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"분할 저장: {SPLIT_PATH}")


# ---------- 리뷰 나누기 ----------


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_test_queue(records: list[dict], assignment: dict[str, str], out_path: Path) -> None:
    test = [{**record, "split": "test"} for record in records if assignment.get(record["place_id"]) == "test"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for record in test:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"\nGold 검수 대기 {len(test)}건 → {out_path}")


def print_counts(title: str, counts: Counter) -> None:
    print(f"\n{title}")
    print(f"  {'':12}" + "".join(f"{split:>8}" for split in SPLITS))
    for category in CATEGORIES:
        print(f"  {category:12}" + "".join(f"{counts[category, split]:>8}" for split in SPLITS))


def write_run_queue(member: str, run: str, assignment: dict[str, str]) -> None:
    run_dir = member_out(member) / "runs" / run
    records = read_jsonl(run_dir / "silver.jsonl")
    unknown = [record["review_id"] for record in records if record["place_id"] not in assignment]
    if unknown:
        print(f"⚠️  분할에 없는 장소의 리뷰 {len(unknown)}건은 뺍니다: {unknown[:5]}")
    counts = Counter((r["category"], assignment[r["place_id"]]) for r in records if r["place_id"] in assignment)
    print_counts(f"{member}/{run} Silver 리뷰 수", counts)
    write_test_queue(records, assignment, run_dir / "test" / "silver.jsonl")
    print("\n다음 단계 (Gold 검수):")
    print(f"  uv run python datas/common/review_gold.py {run_dir / 'test' / 'silver.jsonl'} --reviewer <이름>")


def main() -> None:
    parser = argparse.ArgumentParser(description="팀 전체 장소 분할과 Gold 검수 대기 파일 만들기")
    parser.add_argument("--member", help="검수 대기 파일을 만들 팀원 이니셜")
    parser.add_argument("--run", help="make_silver 실행 이름 (--member와 함께)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if bool(args.member) != bool(args.run):
        parser.error("--member와 --run은 함께 써야 합니다")

    places = load_places()
    assignment = update_split(places, load_split(), args.seed)
    save_split(assignment)
    print_counts("팀 전체 장소 수", Counter((places[pid]["category"], s) for pid, s in assignment.items() if pid in places))

    if args.member:
        write_run_queue(args.member, args.run, assignment)


if __name__ == "__main__":
    main()
