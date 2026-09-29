"""리뷰 분석 결과를 LLM Judge로 A/B 평가한다.

Judge는 평가 대상 모델과 분리하고 temperature 0으로 실행한다.
"""

import argparse
import json
from pathlib import Path


PROMPT = """너는 리뷰 분석 라벨의 품질을 평가하는 심사자다.
리뷰 원문과 두 모델의 분석 결과를 보고 각 답변을 1~5점으로 평가하라.
기준: correctness(라벨 정확성), evidence(원문 근거성), completeness(빠뜨리지 않음),
format(공통 JSON 규격 준수), usefulness(사람이 사용하기 좋은 정도).
evidence 점수는 모델 출력의 evidence가 리뷰 원문에 실제로 존재하는지 우선 확인한다.
JSON만 출력하라: {"a":{"correctness":1,"evidence":1,"completeness":1,"format":1,"usefulness":1,"reason":""},"b":{...},"preference":"a|b|tie"}
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--model", required=True, help="Judge 모델 ID")
    p.add_argument("--base-url", default="http://localhost:11434")
    args = p.parse_args()
    import requests
    output = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        row = json.loads(line)
        prompt = PROMPT + f"\n리뷰: {row['review']}\n답변 A: {json.dumps(row['a']['label'],ensure_ascii=False)}\n답변 B: {json.dumps(row['b']['label'],ensure_ascii=False)}"
        response = requests.post(f"{args.base_url}/api/chat", json={"model":args.model,"stream":False,"format":"json","options":{"temperature":0},"messages":[{"role":"user","content":prompt}]}, timeout=300)
        response.raise_for_status()
        row["judge"] = json.loads(response.json()["message"]["content"])
        output.append(row)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(json.dumps(row,ensure_ascii=False) for row in output)+"\n",encoding="utf-8")
    print(f"LLM Judge {len(output)}건 → {args.out}")


if __name__ == "__main__": main()
