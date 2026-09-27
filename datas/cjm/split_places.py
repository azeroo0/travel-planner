"""장소를 학습/검증/테스트로 나누고, 테스트 장소의 Silver 리뷰를 Gold 검수 대기 파일로 뽑는다.

리뷰가 아니라 장소 단위로 나눈다. 같은 장소의 리뷰가 학습과 테스트에 함께 들어가면
모델이 추출 능력이 아니라 장소를 외워서 맞힐 수 있기 때문이다.
출처가 달라 place_id가 다른 같은 장소(같은 지역에서 도로명 주소나 이름이 같은 곳)는
한 묶음으로 보고 같은 쪽에 넣는다. 같은 건물의 다른 가게가 묶일 수 있지만 누수보다 안전하다.

카테고리 × 지역마다 같은 비율(학습 80 / 검증 10 / 테스트 10)로 나눈다.
분할은 out/split.json에 한 번 저장하면 고정한다. 모든 실험이 같은 분할을 쓴다.

사용법:
  uv run python datas/cjm/split_places.py datas/cjm/out/runs/silver_v1/silver.jsonl
  → out/split.json                       (없을 때만 만든다)
  → out/runs/silver_v1/test/silver.jsonl  (테스트 장소 리뷰 = Gold 검수 대기)
  uv run python datas/cjm/review_gold.py datas/cjm/out/runs/silver_v1/test/silver.jsonl --reviewer sunub
"""

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Final, Iterator

from label_check import load_places

HERE: Final = Path(__file__).parent
SPLITS: Final = ("train", "val", "test")
RATIOS: Final = {"val": 0.1, "test": 0.1}  # 나머지는 train
ROAD_ADDRESS: Final = re.compile(r"([가-힣0-9]+(?:로|길))\s+(\d+(?:-\d+)?)")


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
    return first["category"], first["district"]


def split_groups(groups: list[list[dict]], rng: random.Random) -> dict[str, str]:
    """층마다 묶음을 섞어 앞에서부터 test, val, 나머지 train으로 배정한다."""
    by_stratum: dict[tuple[str, str], list[list[dict]]] = defaultdict(list)
    for group in sorted(groups, key=lambda g: min(place["place_id"] for place in g)):
        by_stratum[stratum(group)].append(group)

    assignment: dict[str, str] = {}
    for key in sorted(by_stratum):
        shuffled = by_stratum[key][:]
        rng.shuffle(shuffled)
        n_test = round(len(shuffled) * RATIOS["test"])
        n_val = round(len(shuffled) * RATIOS["val"])
        for index, group in enumerate(shuffled):
            split = "test" if index < n_test else "val" if index < n_test + n_val else "train"
            assignment |= {place["place_id"]: split for place in group}
    return assignment


def load_or_make_split(path: Path, places: dict[str, dict], seed: int) -> dict[str, str]:
    if path.exists():
        print(f"기존 분할을 씁니다: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    groups = group_places(list(places.values()))
    merged = sum(1 for group in groups if len(group) > 1)
    print(f"장소 {len(places)}곳 → 묶음 {len(groups)}개 (여러 장소가 묶인 것 {merged}개)")
    assignment = split_groups(groups, random.Random(seed))
    path.write_text(json.dumps(assignment, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    print(f"새 분할을 저장했습니다: {path}")
    return assignment


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


def print_counts(title: str, counts: Counter, categories: list[str]) -> None:
    print(f"\n{title}")
    print(f"  {'':12}" + "".join(f"{split:>8}" for split in SPLITS))
    for category in categories:
        print(f"  {category:12}" + "".join(f"{counts[category, split]:>8}" for split in SPLITS))


def main() -> None:
    parser = argparse.ArgumentParser(description="장소 단위 분할과 Gold 검수 대기 파일 만들기")
    parser.add_argument("silver", type=Path, help="make_silver가 만든 silver.jsonl")
    parser.add_argument("--places", type=Path, default=HERE / "out", help="places_*.json 폴더")
    parser.add_argument("--split", type=Path, default=HERE / "out" / "split.json", help="분할 파일 (있으면 그대로 씀)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    places = load_places(args.places)
    assignment = load_or_make_split(args.split, places, args.seed)
    records = read_jsonl(args.silver)

    unknown = [record["review_id"] for record in records if record["place_id"] not in assignment]
    if unknown:
        print(f"⚠️  분할에 없는 장소의 리뷰 {len(unknown)}건은 뺍니다: {unknown[:5]}")

    categories = sorted({place["category"] for place in places.values()})
    place_counts = Counter((places[pid]["category"], split) for pid, split in assignment.items() if pid in places)
    review_counts = Counter((r["category"], assignment[r["place_id"]]) for r in records if r["place_id"] in assignment)
    print_counts("장소 수", place_counts, categories)
    print_counts("Silver 리뷰 수", review_counts, categories)

    write_test_queue(records, assignment, args.silver.parent / "test" / "silver.jsonl")
    print("\n다음 단계 (Gold 검수):")
    print(f"  uv run python datas/cjm/review_gold.py {args.silver.parent / 'test' / 'silver.jsonl'} --reviewer <이름>")


if __name__ == "__main__":
    main()
