"""이미 저장된 JSONL에서 "<0xEB><0x8B><0x9C>" 같은 바이트 조각을 한글로 되돌린다.

ollama_client가 새 결과는 풀어서 돌려주지만, 그 전에 만든 파일에는 조각이 남아 있다.
datas/<이니셜>/out/ 아래의 *.jsonl만 고친다. 백업 폴더(이름에 .bak이 있는 폴더)와 로그는 기록이라 두고,
고치기 전 원본은 out/_backup/byte_tokens/<같은 경로>에 복사한다.
UTF-8로 풀리지 않는 조각은 그대로 둔다 (label_check가 계속 거른다).

사용법:
  uv run python datas/common/fix_byte_tokens.py --dry-run   # 고칠 파일과 건수만 본다
  uv run python datas/common/fix_byte_tokens.py
"""

import argparse
import json
import shutil
from pathlib import Path
from typing import Final

from ollama_client import BYTE_TOKENS, decode_strings
from paths import member_out, members

BACKUP_DIR: Final = Path("_backup") / "byte_tokens"


def target_files(out_dir: Path) -> list[Path]:
    files = []
    for path in sorted(out_dir.rglob("*.jsonl")):
        parts = path.relative_to(out_dir).parts
        if any(".bak" in part for part in parts) or parts[:2] == BACKUP_DIR.parts:
            continue
        files.append(path)
    return files


def fix_lines(path: Path) -> tuple[list[str], int, int]:
    """(고친 줄 목록, 고친 조각 수, 풀리지 않고 남은 조각 수)."""
    lines, fixed, left = [], 0, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        before = len(BYTE_TOKENS.findall(line))
        if before:
            line = json.dumps(decode_strings(json.loads(line)), ensure_ascii=False)
            remaining = len(BYTE_TOKENS.findall(line))
            fixed, left = fixed + before - remaining, left + remaining
        lines.append(line)
    return lines, fixed, left


def fix_file(path: Path, out_dir: Path, dry_run: bool) -> None:
    lines, fixed, left = fix_lines(path)
    if not fixed:
        return
    print(f"  {path.relative_to(out_dir.parent.parent)}: {fixed}곳 고침, 풀리지 않는 조각 {left}곳")
    if dry_run:
        return
    backup = out_dir / BACKUP_DIR / path.relative_to(out_dir)
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="저장된 JSONL의 <0x..> 바이트 조각을 한글로 되돌리기")
    parser.add_argument("--dry-run", action="store_true", help="파일을 바꾸지 않고 고칠 곳만 보여준다")
    args = parser.parse_args()

    for member in members():
        out_dir = member_out(member)
        if not out_dir.is_dir():
            continue
        for path in target_files(out_dir):
            try:
                fix_file(path, out_dir, args.dry_run)
            except (OSError, json.JSONDecodeError) as e:  # 한 파일이 실패해도 나머지는 고친다
                print(f"  ⚠️  {path}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
