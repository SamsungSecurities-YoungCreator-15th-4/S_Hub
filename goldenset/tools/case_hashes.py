"""사례 본문 해시(`case_content_sha256`) 생성·검증.

무엇을 해시하는가
  frontmatter를 **제외한 본문만** 해시한다. frontmatter에는 정답(`label`,
  `fail_axes`, `trap_type`, `rationale`)이 들어 있고, 그것은 judge가 보는
  내용이 아니다. 따라서 해시는 **judge에게 보이는 것과 정확히 같은 범위**를
  덮는다.

왜 필요한가
  v1과 v2가 **같은 사례**를 채점했는지 증명한다. 사례를 몰래 고쳐 v2 점수를
  올리는 경로를 막는 유일한 기계적 장치다. `v1-freeze` 커밋 SHA가 "언제"를
  증명한다면, 이 해시는 "무엇을"을 증명한다.

성질 (테스트로 고정)
  · 라벨을 바꿔도 해시는 변하지 않는다  → 정답이 해시에 섞이지 않았다는 증거
  · 본문을 한 글자 바꾸면 해시가 변한다  → 사례 무단 수정 탐지

사용:
  python goldenset/tools/case_hashes.py            # 검증 (CI용, 기록과 대조)
  python goldenset/tools/case_hashes.py --write    # 기록 갱신 (사례 수정 시)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "cases"
HASHES = ROOT / "case_hashes.json"

FM_RE = re.compile(r"^---\n.*?\n---\n(.*)$", re.S)


def content_hash(text: str) -> str:
    """frontmatter를 버리고 본문만 해시한다.

    개행 차이로 해시가 흔들리지 않도록 CRLF를 정규화하고 양끝 공백을 제거한다.
    """
    m = FM_RE.match(text)
    body = m.group(1) if m else text
    normalized = body.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute() -> dict[str, str]:
    return {
        p.stem: content_hash(p.read_text(encoding="utf-8"))
        for p in sorted(CASES.glob("case_*.md"))
    }


def load() -> dict:
    if not HASHES.exists():
        return {}
    return json.loads(HASHES.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="기록을 갱신한다 (사례를 정당하게 수정했을 때만)")
    args = ap.parse_args()

    current = compute()
    if not current:
        print("사례가 없습니다.")
        return 1

    if args.write:
        HASHES.write_text(
            json.dumps(
                {
                    "algorithm": "sha256",
                    "scope": "frontmatter 제외 본문만 — 정답 라벨은 해시에 포함되지 않는다",
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "hashes": current,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"✅ {len(current)}건 기록: {HASHES}")
        print("   ⚠️ v1 실행 이후 이 파일이 바뀌면 v1/v2 비교가 무효다. 커밋 diff로 반드시 검토할 것.")
        return 0

    recorded = load().get("hashes") or {}
    if not recorded:
        print(f"기록이 없습니다. 먼저 --write 로 생성하세요: {HASHES}")
        return 1

    added = sorted(set(current) - set(recorded))
    removed = sorted(set(recorded) - set(current))
    changed = sorted(k for k in set(current) & set(recorded) if current[k] != recorded[k])

    if not (added or removed or changed):
        print(f"✅ 사례 {len(current)}건 전부 기록과 일치 — 동결 이후 본문 변경 없음")
        return 0

    print("❌ 사례 본문이 기록과 다릅니다\n")
    for k in changed:
        print(f"  · 변경됨: {k}")
    for k in added:
        print(f"  · 추가됨: {k}")
    for k in removed:
        print(f"  · 삭제됨: {k}")
    print(
        "\nv1 실행 이후라면 v1/v2 비교가 무효가 됩니다. 정당한 수정이면"
        "\n--write 로 갱신하고 그 사유를 labeling-guide.md §4에 기록하세요."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
