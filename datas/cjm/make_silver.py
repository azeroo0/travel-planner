"""합성 리뷰 생성 → 라벨 추출 → Silver 검사를 한 번에 실행한다.

한 번의 실행(run)은 폴더 하나에 결과를 모은다.
  out/runs/<run>/reviews.jsonl   생성한 합성 리뷰 (라벨 없음)
  out/runs/<run>/labeled.jsonl   라벨을 붙인 리뷰
  out/runs/<run>/silver.jsonl    자동 검사를 통과한 리뷰 (tier: silver)

세 단계 모두 이어서 실행할 수 있다. 중간에 멈춰도 같은 명령을 다시 실행하면
이미 만든 리뷰와 라벨은 건너뛴다. Silver 검사는 매번 labeled.jsonl 전체를 다시 본다.

사용법:
  uv run python datas/cjm/make_silver.py --run pilot --category hotel restaurant attraction --count 34
  uv run python datas/cjm/review_gold.py datas/cjm/out/runs/pilot/silver.jsonl   # 다음 단계: Gold 검수
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import extract_labels
import generate_reviews
import label_check
from ollama_client import DEFAULT_MODEL, check_ollama
from schema import ATTRIBUTES

HERE: Final = Path(__file__).parent
RUNS_DIR: Final = HERE / "out" / "runs"


@dataclass(frozen=True)
class RunPaths:
    reviews: Path
    labeled: Path
    silver: Path


def run_paths(run: str) -> RunPaths:
    run_dir = RUNS_DIR / run
    return RunPaths(
        reviews=run_dir / "reviews.jsonl",
        labeled=run_dir / "labeled.jsonl",
        silver=run_dir / "silver.jsonl",
    )


def generate_step(args: argparse.Namespace, paths: RunPaths) -> None:
    for category in args.category:
        print(f"\n[1/3] {category} 리뷰 생성")
        places = generate_reviews.load_places(args.places, category)
        plans = generate_reviews.make_plans(places, category, args.count, args.max_per_place, args.seed)
        generate_reviews.generate(plans, args.model, paths.reviews)


def label_step(args: argparse.Namespace, paths: RunPaths, places: dict[str, dict]) -> None:
    print("\n[2/3] 라벨 추출")
    reviews = extract_labels.read_jsonl(paths.reviews)
    extract_labels.extract(reviews, places, args.model, paths.labeled)


def check_step(paths: RunPaths, places: dict[str, dict]) -> None:
    print("\n[3/3] Silver 검사")
    label_check.check_file(paths.labeled, places, paths.silver)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="합성 리뷰로 Silver 데이터 만들기 (로컬 Ollama)")
    parser.add_argument("--run", required=True, help="결과를 모을 이름. out/runs/<run>/ 에 저장")
    parser.add_argument("--category", nargs="+", required=True, choices=sorted(ATTRIBUTES))
    parser.add_argument("--count", type=int, required=True, help="카테고리마다 만들 리뷰 수")
    parser.add_argument("--places", type=Path, default=HERE / "out", help="places_*.json 폴더")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-per-place", type=int, default=10, help="장소 한 곳당 최대 리뷰 수")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = run_paths(args.run)
    places = label_check.load_places(args.places)

    check_ollama(args.model)
    generate_step(args, paths)
    label_step(args, paths, places)
    check_step(paths, places)

    print("\n다음 단계 (Gold 검수):")
    print(f"  uv run python datas/cjm/review_gold.py {paths.silver}")


if __name__ == "__main__":
    main()
