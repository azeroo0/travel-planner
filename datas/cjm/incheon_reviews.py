"""인천관광공사 가맹점 리뷰(실제 리뷰)를 골라 Silver 라벨링 입력을 만들고, 라벨 후 긍정 쏠림을 줄인다.

부산 데이터와 섞이지 않게 모든 결과를 out/real/incheon/ 에만 둔다 (커밋 금지).
places_*.json에 장소를 쓰지 않으므로 load_places()와 팀 공유 분할(split.json)에 인천 장소가 들어가지 않는다.
그래서 인천 리뷰는 부산 Gold 테스트셋에 절대 들어가지 않고, 레코드마다 region="incheon", split="train"이다.
학습 데이터를 만들 때 이 파일을 넣고 빼는 것으로 "인천 포함 / 미포함" 실험을 나눈다.

  reviews.jsonl                 고른 리뷰 (라벨 없음)
  runs/<run>/labeled.jsonl      label 단계 결과 (공통 extract_labels의 프롬프트를 그대로 쓰고 요청만 병렬로 보낸다)
  runs/<run>/silver.jsonl       label_check.py 결과
  runs/<run>/silver_balanced.jsonl   긍정만 있는 리뷰의 비율을 제한한 최종 Silver

고르는 규칙 (select):
  1. 카테고리: 맛집·카페 → restaurant, 관광·체험 → attraction, 숙소 → hotel. 쇼핑 등은 뺀다.
     분류가 빠진 행은 같은 이름의 다른 행에서 분류를 가져온다.
  2. 한글이 없거나 너무 짧은 리뷰, 여러 번 똑같이 올라온 문장(스탬프투어 보상용 템플릿)을 뺀다.
  3. 리뷰를 단서로 나눈다: not_positive(아쉬움·불만·보통) > rich(드문 aspect나 aspect 여러 개) > plain.
  4. 장소 한 곳당 최대 --max-per-place건. 단서가 많은 리뷰부터 채운다.
  5. 카테고리마다 plain은 --plain-share 비율까지만 남긴다.

사용법:
  uv run python datas/cjm/incheon_reviews.py select
  OLLAMA_URL=http://localhost:11435 uv run python datas/cjm/incheon_reviews.py label --run silver_v1 --workers 4
  uv run python datas/common/label_check.py datas/cjm/out/real/incheon/runs/silver_v1/labeled.jsonl \\
      --out datas/cjm/out/real/incheon/runs/silver_v1/silver.jsonl
  uv run python datas/cjm/incheon_reviews.py balance --run silver_v1
"""

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Final

import requests

HERE: Final = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "common"))  # 팀 공통 모듈(datas/common)을 가져온다

import extract_labels  # noqa: E402
import label_check  # noqa: E402
from ollama_client import DEFAULT_MODEL, OLLAMA_URL, check_ollama  # noqa: E402

IN_DIR: Final = HERE / "in"
OUT_DIR: Final = HERE / "out" / "real" / "incheon"
REVIEWS_PATH: Final = OUT_DIR / "reviews.jsonl"
SOURCE_PREFIX: Final = "인천관광공사_가맹점 리뷰정보"
SOURCE: Final = "incheon_tour_merchant"

MIN_CHARS: Final = 10  # "좋아요" 같은 리뷰는 달 aspect가 없다
TEMPLATE_REPEATS: Final = 3  # 이만큼 똑같이 올라온 문장은 템플릿으로 보고 모두 뺀다

# 인천 분류 앞부분 → 우리 카테고리. 없는 분류(쇼핑 등)는 뺀다
CATEGORY_BY_PREFIX: Final = (("맛집", "restaurant"), ("카페", "restaurant"), ("관광", "attraction"),
                             ("체험", "attraction"), ("숙소", "hotel"))  # fmt: skip

# 긍정이 아닌 평가 단서 (불만·아쉬움·보통)
NOT_POSITIVE: Final = re.compile(
    r"아쉽|아쉬|(?<!종류)별로|불친절|비싸|실망|최악|불편|더럽|지저분|시끄|좁아|좁고|좁은|오래 기다|기다려야"
    r"|느려|느리|늦게|짜요|짰|싱거|싱겁|비추|그닥|그저 그|보통|무난|그럭저럭"
)
# aspect 단서. food·atmosphere·staff는 흔해서 하나만 있으면 plain으로 본다
ASPECT_CUES: Final[dict[str, re.Pattern]] = {
    "food": re.compile(r"맛있|맛나|맛이|존맛|맛없"),
    "atmosphere": re.compile(r"분위기|인테리어|감성"),
    "staff": re.compile(r"친절|사장님|직원"),
    "portion": re.compile(r"양이|양도|푸짐"),
    "waiting": re.compile(r"웨이팅|대기|줄[이을]"),
    "parking": re.compile(r"주차"),
    "clean": re.compile(r"깨끗|청결"),
    "noise": re.compile(r"조용|시끄"),
    "seat": re.compile(r"좌석|자리|넓[어고은]"),
    "scenery": re.compile(r"바다|야경|노을|전망|뷰"),
    "photo": re.compile(r"사진|포토"),
    "walking": re.compile(r"걷|산책|계단|언덕|오르막"),
    "toilet": re.compile(r"화장실"),
    "stay": re.compile(r"시간이|한참|금방"),
    "traveler": re.compile(r"혼자|아이|아들|딸|애들|부모님|엄마|아빠|남편|와이프|남자친구|여자친구|친구[들와랑]|데이트"),
}
COMMON_CUES: Final = {"food", "atmosphere", "staff"}
BUCKET_ORDER: Final = ("not_positive", "rich", "plain")


# ---------- 읽기 ----------


def source_path() -> Path:
    """macOS 파일명은 NFD라서 NFC로 맞춰 비교한다."""
    for path in IN_DIR.iterdir():
        if unicodedata.normalize("NFC", path.name).startswith(SOURCE_PREFIX):
            return path
    raise SystemExit(f"{IN_DIR}에 {SOURCE_PREFIX}*.csv가 없습니다")


def read_rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{"place": row[0], "review": row[1], "date": row[2]} for row in list(csv.reader(f))[1:]]


def category_of(label: str) -> str | None:
    return next((category for prefix, category in CATEGORY_BY_PREFIX if label.startswith(prefix)), None)


def split_place(place: str) -> tuple[str, str]:
    """'신신분식::맛집·분식' → ('신신분식', '맛집·분식'). 분류가 없으면 ''."""
    name, _, label = place.partition("::")
    return name.strip(), label.strip()


def labels_by_name(rows: list[dict]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for row in rows:
        name, label = split_place(row["place"])
        if label:
            labels.setdefault(name, label)
    return labels


# ---------- 거르기 ----------


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_usable(text: str) -> bool:
    return len(text) >= MIN_CHARS and bool(re.search(r"[가-힣]", text))


def to_candidate(row: dict, labels: dict[str, str]) -> dict | None:
    name, label = split_place(row["place"])
    label = label or labels.get(name, "")
    category = category_of(label)
    if category is None:
        return None
    return {"name": name, "source_label": label, "category": category,
            "review": clean_text(row["review"]), "date": row["date"]}  # fmt: skip


def filter_candidates(rows: list[dict], stats: Counter) -> list[dict]:
    labels = labels_by_name(rows)
    repeats = Counter(clean_text(row["review"]) for row in rows)
    seen: set[str] = set()
    kept: list[dict] = []
    for row in rows:
        candidate = to_candidate(row, labels)
        reason = drop_reason(candidate, repeats, seen)
        stats[reason or "kept"] += 1
        if reason is None:
            seen.add(candidate["review"])
            kept.append(candidate)
    return kept


def drop_reason(candidate: dict | None, repeats: Counter, seen: set[str]) -> str | None:
    if candidate is None:
        return "drop_category"
    if not is_usable(candidate["review"]):
        return "drop_short_or_no_hangul"
    if repeats[candidate["review"]] >= TEMPLATE_REPEATS:
        return "drop_template"
    if candidate["review"] in seen:
        return "drop_duplicate"
    return None


# ---------- 단서로 나누고 고르기 ----------


def bucket_of(text: str) -> str:
    if NOT_POSITIVE.search(text):
        return "not_positive"
    cues = {name for name, pattern in ASPECT_CUES.items() if pattern.search(text)}
    return "rich" if len(cues) >= 2 or cues - COMMON_CUES else "plain"


def cap_per_place(candidates: list[dict], max_per_place: int, rng: random.Random) -> list[dict]:
    """장소마다 단서 순서(not_positive → rich → plain)로 채우고, 같은 층 안에서는 무작위로 고른다."""
    by_place: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        by_place[candidate["name"]].append(candidate)
    selected: list[dict] = []
    for name in sorted(by_place):
        reviews = by_place[name]
        rng.shuffle(reviews)
        reviews.sort(key=lambda c: BUCKET_ORDER.index(c["bucket"]))
        selected += reviews[:max_per_place]
    return selected


def cap_plain(selected: list[dict], plain_share: float, rng: random.Random) -> list[dict]:
    """카테고리마다 plain이 전체의 plain_share를 넘지 않게 줄인다."""
    kept: list[dict] = []
    for category in sorted({c["category"] for c in selected}):
        rows = [c for c in selected if c["category"] == category]
        informative = [c for c in rows if c["bucket"] != "plain"]
        plain = [c for c in rows if c["bucket"] == "plain"]
        limit = int(len(informative) * plain_share / (1 - plain_share))
        kept += informative + rng.sample(plain, min(limit, len(plain)))
    return kept


def to_record(candidate: dict) -> dict:
    digest = hashlib.sha1(f"{candidate['name']}\n{candidate['review']}".encode()).hexdigest()[:12]
    return {
        "review_id": f"incheon_{digest}",
        "place_id": f"{SOURCE}:{candidate['name']}",
        "category": candidate["category"],
        "synthetic": False,
        "region": "incheon",
        "split": "train",  # 부산 Gold 테스트셋과 겹치지 않게 학습에만 쓴다
        "source": SOURCE,
        "place_name": candidate["name"],
        "source_label": candidate["source_label"],
        "published": candidate["date"],
        "sampling_bucket": candidate["bucket"],
        "review": candidate["review"],
    }


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_table(title: str, counts: Counter, rows: list[str], cols: tuple[str, ...]) -> None:
    print(f"\n{title}")
    print(f"  {'':12}" + "".join(f"{col:>14}" for col in cols) + f"{'total':>8}")
    for row in rows:
        total = sum(counts[row, col] for col in cols)
        print(f"  {row:12}" + "".join(f"{counts[row, col]:>14}" for col in cols) + f"{total:>8}")


def select(args: argparse.Namespace) -> None:
    rows = read_rows(source_path())
    stats: Counter = Counter()
    candidates = filter_candidates(rows, stats)
    for candidate in candidates:
        candidate["bucket"] = bucket_of(candidate["review"])

    rng = random.Random(args.seed)
    selected = cap_plain(cap_per_place(candidates, args.max_per_place, rng), args.plain_share, rng)
    selected.sort(key=lambda c: (c["category"], c["name"], c["date"]))
    write_jsonl([to_record(c) for c in selected], REVIEWS_PATH)

    print(f"원본 {len(rows)}행: " + ", ".join(f"{key} {count}" for key, count in sorted(stats.items())))
    categories = sorted({c["category"] for c in candidates})
    print_table("거른 뒤 후보", Counter((c["category"], c["bucket"]) for c in candidates), categories, BUCKET_ORDER)
    print_table("최종 선택", Counter((c["category"], c["bucket"]) for c in selected), categories, BUCKET_ORDER)
    print(f"\n장소 {len({c['name'] for c in selected})}곳, 리뷰 {len(selected)}건 → {REVIEWS_PATH}")


# ---------- 라벨 (병렬 요청) ----------


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def label_one(record: dict, model: str) -> dict:
    """공통 extract_labels와 같은 프롬프트로 라벨을 단다. 인천 장소는 장소 정보가 없어서 place=None이다."""
    return extract_labels.label_record(record, None, model)


def label(args: argparse.Namespace) -> None:
    """요청을 --workers개씩 동시에 보낸다. 서버도 OLLAMA_NUM_PARALLEL로 그만큼 받아야 빨라진다."""
    run_dir = OUT_DIR / "runs" / args.run
    labeled_path = run_dir / "labeled.jsonl"
    records = read_jsonl(args.reviews)
    done = extract_labels.load_done_ids(labeled_path)
    todo = [record for record in records if record["review_id"] not in done]
    print(f"리뷰 {len(records)}건 중 {len(done & {r['review_id'] for r in records})}건은 건너뛰고 "
          f"{len(todo)}건을 {args.workers}개씩 동시에 처리합니다 ({OLLAMA_URL}).")  # fmt: skip

    check_ollama(args.model)
    run_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with ThreadPoolExecutor(args.workers) as pool, open(labeled_path, "a", encoding="utf-8") as out:
        futures = {pool.submit(label_one, record, args.model): record["review_id"] for record in todo}
        for number, future in enumerate(as_completed(futures), start=1):
            try:
                out.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
                out.flush()
            except (requests.RequestException, KeyError, ValueError) as e:  # 한 건 실패는 건너뛴다
                failures.append(f"{futures[future]}: {type(e).__name__}: {e}")
            if number % 50 == 0 or number == len(todo):
                print(f"  {number}/{len(todo)}", flush=True)

    print(f"완료: {len(todo) - len(failures)}건 저장 → {labeled_path}")
    if failures:
        print(f"⚠️  실패 {len(failures)}건 (같은 명령을 다시 실행하면 이 건들만 다시 시도합니다)")
        for failure in failures:
            print(f"  - {failure}")
    label_check.check_file(labeled_path, {}, run_dir / "silver.jsonl")


# ---------- 라벨 후 긍정 쏠림 줄이기 ----------


def is_positive_only(record: dict) -> bool:
    """aspect가 모두 positive인 리뷰. aspect가 없는 리뷰는 과잉 추출을 막는 예시라 따로 본다."""
    sentiments = {aspect["sentiment"] for aspect in record["label"]["aspects"]}
    return sentiments == {"positive"}


def balance(args: argparse.Namespace) -> None:
    run_dir = OUT_DIR / "runs" / args.run
    records = read_jsonl(run_dir / "silver.jsonl")
    rng = random.Random(args.seed)
    kept: list[dict] = []
    for category in sorted({r["category"] for r in records}):
        rows = [r for r in records if r["category"] == category]
        positive = [r for r in rows if is_positive_only(r)]
        others = [r for r in rows if not is_positive_only(r)]
        limit = int(len(others) * args.positive_share / (1 - args.positive_share))
        kept += others + rng.sample(positive, min(limit, len(positive)))
        print(f"{category}: 긍정만 {len(positive)}건 중 {min(limit, len(positive))}건, 나머지 {len(others)}건 유지")

    out_path = run_dir / "silver_balanced.jsonl"
    write_jsonl(kept, out_path)
    sentiments = Counter(a["sentiment"] for r in kept for a in r["label"]["aspects"])
    print(f"\n최종 {len(kept)}건 / aspect 감성 분포: {dict(sentiments)} → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="인천 가맹점 리뷰로 Silver 만들기: 고르기 → 라벨 → 긍정 쏠림 줄이기")
    parser.add_argument("--seed", type=int, default=42)
    sub = parser.add_subparsers(dest="command", required=True)

    select_parser = sub.add_parser("select", help="원본 CSV에서 라벨링할 리뷰 고르기")
    select_parser.add_argument("--max-per-place", type=int, default=10, help="장소 한 곳당 최대 리뷰 수")
    select_parser.add_argument("--plain-share", type=float, default=0.4, help="카테고리별 plain 리뷰 최대 비율")

    label_parser = sub.add_parser("label", help="로컬 Ollama로 라벨을 달고 Silver 검사까지 한다")
    label_parser.add_argument("--run", required=True, help="결과를 모을 이름. out/real/incheon/runs/<run>/")
    label_parser.add_argument("--reviews", type=Path, default=REVIEWS_PATH, help="라벨을 달 리뷰 JSONL")
    label_parser.add_argument("--workers", type=int, default=4, help="동시에 보낼 요청 수")
    label_parser.add_argument("--model", default=DEFAULT_MODEL)

    balance_parser = sub.add_parser("balance", help="Silver에서 긍정만 있는 리뷰의 비율 제한")
    balance_parser.add_argument("--run", required=True, help="out/real/incheon/runs/<run>/silver.jsonl")
    balance_parser.add_argument("--positive-share", type=float, default=0.5, help="긍정만 있는 리뷰 최대 비율")

    args = parser.parse_args()
    commands = {"select": select, "label": label, "balance": balance}
    commands[args.command](args)


if __name__ == "__main__":
    main()
