"""Silver 리뷰를 사람이 브라우저에서 검수해 Gold로 만든다.

silver.jsonl 옆에 결과를 쓴다.
  gold.jsonl        사람이 원문과 대조해 승인한 리뷰 (tier: gold)
  discarded.jsonl   리뷰 자체가 부자연스러워 버린 리뷰

승인할 때 고친 라벨도 label_check의 Silver 검사를 다시 통과해야 한다.
Gold 레코드에는 원래 Silver 라벨(silver_label)을 남겨, 나중에 Silver 품질(정밀도·재현율)을 잰다.
결정은 언제든 바꿀 수 있고, 바꿀 때마다 두 파일을 다시 쓴다.

사용법:
  uv run python datas/common/review_gold.py datas/cjm/out/runs/pilot/test/silver.jsonl --reviewer sunub
  → 브라우저에서 http://127.0.0.1:8765 이 열린다. 끝내려면 터미널에서 Ctrl+C.
"""

import argparse
import json
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Final

from label_check import check_record
from paths import load_places
from schema import (
    ASPECT_NAMES_KO,
    ATTRIBUTES,
    CATEGORY_NAMES_KO,
    SENTIMENTS,
    TRAVELER_CONTEXTS,
    TRAVELER_NAMES_KO,
    VALUE_NAMES_KO,
)

HERE: Final = Path(__file__).parent
PAGE: Final = HERE / "review_gold.html"
SENTIMENT_NAMES_KO: Final = {"positive": "긍정", "negative": "부정", "neutral": "중립"}


# ---------- 파일 ----------


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    """임시 파일에 다 쓴 뒤 바꿔 끼운다. 쓰다가 멈춰도 원래 파일이 깨지지 않는다."""
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(path)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------- 검수 상태 ----------


@dataclass
class ReviewSession:
    silver: dict[str, dict]  # review_id → Silver 레코드 (파일 순서 유지)
    places: dict[str, dict]
    gold_path: Path
    discarded_path: Path
    reviewer: str
    gold: dict[str, dict] = field(default_factory=dict)
    discarded: dict[str, dict] = field(default_factory=dict)

    def status(self, review_id: str) -> str:
        if review_id in self.gold:
            return "gold"
        if review_id in self.discarded:
            return "discarded"
        return "pending"

    def item(self, record: dict) -> dict:
        """화면에 보낼 리뷰 한 건. Gold로 승인했으면 고친 라벨을, 아니면 Silver 라벨을 보여준다."""
        review_id = record["review_id"]
        decided = self.gold.get(review_id) or self.discarded.get(review_id) or {}
        return {
            "review_id": review_id,
            "category": record["category"],
            "review": record["review"],
            "label": self.gold[review_id]["label"] if review_id in self.gold else record["label"],
            "silver_label": record["label"],
            "generation": record.get("generation"),
            "place": self.places.get(record["place_id"]),
            "status": self.status(review_id),
            "note": decided.get("decision", {}).get("note", ""),
        }

    def items(self) -> list[dict]:
        return [self.item(record) for record in self.silver.values()]

    def decision(self, note: str) -> dict:
        return {"reviewer": self.reviewer, "reviewed_at": now(), "note": note}

    def approve(self, review_id: str, label: dict, note: str) -> list[str]:
        """라벨을 Gold로 승인한다. 문제 목록을 돌려주고, 비어 있을 때만 저장한다."""
        silver = self.silver[review_id]
        gold = {**silver, "label": label, "tier": "gold", "silver_label": silver["label"]}
        errors = check_record(gold, self.places.get(silver["place_id"]))
        if errors:
            return errors
        gold["decision"] = {**self.decision(note), "edited": label != silver["label"]}
        self.discarded.pop(review_id, None)
        self.gold[review_id] = gold
        self.save()
        return []

    def discard(self, review_id: str, note: str) -> None:
        self.gold.pop(review_id, None)
        self.discarded[review_id] = {**self.silver[review_id], "decision": self.decision(note)}
        self.save()

    def reset(self, review_id: str) -> None:
        self.gold.pop(review_id, None)
        self.discarded.pop(review_id, None)
        self.save()

    def save(self) -> None:
        write_jsonl(self.gold_path, list(self.gold.values()))
        write_jsonl(self.discarded_path, list(self.discarded.values()))


def open_session(silver_path: Path, reviewer: str) -> ReviewSession:
    session = ReviewSession(
        silver={record["review_id"]: record for record in read_jsonl(silver_path)},
        places=load_places(),
        gold_path=silver_path.with_name("gold.jsonl"),
        discarded_path=silver_path.with_name("discarded.jsonl"),
        reviewer=reviewer,
    )
    session.gold = {record["review_id"]: record for record in read_jsonl(session.gold_path)}
    session.discarded = {record["review_id"]: record for record in read_jsonl(session.discarded_path)}
    return session


def schema_for_page() -> dict:
    """화면이 드롭다운을 만들 때 쓰는 허용값과 한국어 이름."""
    return {
        "attributes": ATTRIBUTES,
        "sentiments": sorted(SENTIMENTS),
        "travelers": sorted(TRAVELER_CONTEXTS),
        "names": {
            "category": CATEGORY_NAMES_KO,
            "aspect": ASPECT_NAMES_KO,
            "value": VALUE_NAMES_KO,
            "traveler": TRAVELER_NAMES_KO,
            "sentiment": SENTIMENT_NAMES_KO,
        },
    }


# ---------- 웹 서버 ----------


def make_handler(session: ReviewSession) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/":
                self.send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self.send_json(HTTPStatus.OK, {
                    "reviewer": session.reviewer,
                    "schema": schema_for_page(),
                    "items": session.items(),
                })  # fmt: skip
            else:
                self.send_json(HTTPStatus.NOT_FOUND, {"errors": ["없는 주소"]})

        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            review_id = body.get("review_id")
            if review_id not in session.silver:
                self.send_json(HTTPStatus.BAD_REQUEST, {"errors": [f"없는 review_id: {review_id!r}"]})
                return

            note = str(body.get("note", "")).strip()
            errors: list[str] = []
            if self.path == "/api/approve":
                errors = session.approve(review_id, body.get("label"), note)
            elif self.path == "/api/discard":
                session.discard(review_id, note)
            elif self.path == "/api/reset":
                session.reset(review_id)
            else:
                errors = ["없는 주소"]

            if errors:
                self.send_json(HTTPStatus.BAD_REQUEST, {"errors": errors})
                return
            record = session.silver[review_id]
            self.send_json(HTTPStatus.OK, {"item": session.item(record)})

        def send_json(self, status: HTTPStatus, data: dict) -> None:
            self.send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

        def send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:  # 요청마다 찍히는 로그를 끈다
            pass

    return Handler


def print_summary(session: ReviewSession) -> None:
    total = len(session.silver)
    print(f"Gold {len(session.gold)}건 → {session.gold_path}")
    print(f"버림 {len(session.discarded)}건 → {session.discarded_path}")
    print(f"남은 검수 {total - len(session.gold) - len(session.discarded)}건 / 전체 {total}건")


def main() -> None:
    parser = argparse.ArgumentParser(description="Silver 리뷰를 브라우저에서 검수해 Gold 만들기")
    parser.add_argument("silver", type=Path, help="make_silver가 만든 silver.jsonl")
    parser.add_argument("--reviewer", required=True, help="검수자 이름 (Gold 레코드에 남는다)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true", help="브라우저를 자동으로 열지 않음")
    args = parser.parse_args()

    session = open_session(args.silver, args.reviewer)
    if not session.silver:
        raise SystemExit(f"검수할 리뷰가 없습니다: {args.silver}")

    # 127.0.0.1로만 열어서 같은 컴퓨터에서만 접속할 수 있다
    server = HTTPServer(("127.0.0.1", args.port), make_handler(session))
    url = f"http://127.0.0.1:{args.port}"
    print(f"검수 화면: {url}  (끝내려면 Ctrl+C)")
    print_summary(session)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print_summary(session)


if __name__ == "__main__":
    main()
