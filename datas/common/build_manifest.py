"""datasets/v2/ 의 파일 수, 정리 결과, 실제 리뷰 test의 aspect 분포를 manifest.json에 기록한다.

clean_silver.py와 build_real_test.py를 실행한 뒤에 돌린다.
  uv run python datas/common/build_manifest.py
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "datasets/v2"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def real_test_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    support = Counter((r["category"], a["category"]) for r in rows for a in r["label"]["aspects"])
    return {
        "synthetic": False,
        "tier": "silver (사람 검수 전 초안)",
        "labeler": "claude-sonnet-5-5",
        "reviews": len(rows),
        "places": len({r["place_id"] for r in rows}),
        "reviews_without_aspects": sum(not r["label"]["aspects"] for r in rows),
        "aspect_count": sum(support.values()),
        "sentiment": dict(Counter(a["sentiment"] for r in rows for a in r["label"]["aspects"])),
        "translated_reviews": sum(r["source"]["translation_status"] == "translated_to_korean" for r in rows),
        "aspect_support": {f"{c}/{a}": n for (c, a), n in support.most_common()},
    }


def synthetic_test_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    times = sorted(datetime.fromisoformat(r["decision"]["reviewed_at"]) for r in rows)
    gaps = [(later - earlier).total_seconds() for earlier, later in zip(times, times[1:])]
    return {
        "records": len(rows),
        "median_seconds_between_reviews": statistics.median(gaps),
        "reviews_within_5s": sum(gap <= 5 for gap in gaps),
        "edited": sum(r["decision"]["edited"] for r in rows),
        "note": "검수 시간 간격이 짧아 원문 대조 여부를 확인할 수 없다. 재검수 전까지 합성 test 점수는 참고용으로만 쓴다.",
    }


def main() -> None:
    train, validation = read_jsonl(V2 / "train.jsonl"), read_jsonl(V2 / "validation.jsonl")
    real = read_jsonl(V2 / "test_real.jsonl")
    manifest = {
        "dataset_name": "busan_review_sft_v2",
        "derived_from": ["datasets/ (busan_review_sft_v1)", "tripadvisor_reviews.xlsx"],
        "created_by": [
            "datas/common/clean_silver.py",
            "datas/common/normalize_evidence.py",
            "datas/common/build_real_test.py",
            "datas/common/build_manifest.py",
        ],
        "files": {"train.jsonl": len(train), "validation.jsonl": len(validation), "test_real.jsonl": len(real)},
        "cleaning": json.loads((V2 / "clean_report.json").read_text(encoding="utf-8")),
        "test_normalized": "datasets/v2/test_normalized.jsonl: Gold test의 evidence 경계만 맞춘 사본. label_raw에 원본이 있고 사람 승인 전까지 Gold 대신 쓰지 않는다",
        "test_real": real_test_summary(real),
        "synthetic_test_audit": synthetic_test_audit(read_jsonl(ROOT / "datasets/test.jsonl")),
        "known_limits": [
            "test_real은 광안리·수영구·남구 중심이고 146건이라 aspect별 정답 수가 적다",
            "test_real은 78%가 기계번역 문장이다",
            "test_real 라벨은 초안이라 사람이 승인하기 전에는 Gold가 아니다",
            "train의 근거 약한 추론 라벨 같은 노이즈는 자동 규칙으로 걸러지지 않았다",
            "evidence 경계 규칙은 validation의 첫 어절 빈도로 정했고 test는 보지 않았다",
        ],
    }
    (V2 / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["files"], ensure_ascii=False))


if __name__ == "__main__":
    main()
