"""W&B·Golden Set·Judge·Human 결과를 하나의 최종 판단 리포트로 합친다."""

import argparse
import json
from pathlib import Path


def read(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    p=argparse.ArgumentParser(); p.add_argument("--metrics",type=Path,required=True); p.add_argument("--judge",type=Path); p.add_argument("--human",type=Path); p.add_argument("--out",type=Path,required=True); args=p.parse_args()
    result=json.loads(args.metrics.read_text(encoding="utf-8"))
    if args.judge and args.judge.exists():
        rows=read(args.judge); result["judge"]={"items":len(rows),"preference":{}}
        for row in rows: result["judge"]["preference"][row.get("judge",{}).get("preference","invalid")]=result["judge"]["preference"].get(row.get("judge",{}).get("preference","invalid"),0)+1
    if args.human and args.human.exists():
        rows=read(args.human); result["human"]={"items":len(rows),"preference":{}}
        for row in rows: result["human"]["preference"][row.get("scores",{}).get("preference","")]=result["human"]["preference"].get(row.get("scores",{}).get("preference",""),0)+1
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(f"최종 리포트 → {args.out}")

if __name__ == "__main__": main()
