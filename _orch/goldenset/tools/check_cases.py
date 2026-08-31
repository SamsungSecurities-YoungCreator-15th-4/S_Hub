"""정답 사례집 기계 점검 도구.

⚠️ 이 스크립트는 **pass/fail 라벨을 판정하지 않는다.** 규칙 위반 후보를 기계적으로
드러낼 뿐이며, 최종 판정은 사람 라벨러가 기준표(labeling-guide.md)를 근거로 한다.
(과제 무효 조건 ① — judge·자동화가 정답 라벨을 만들면 과제 무효)

용도
  1. 출제자의 자충수 점검 — pass 의도 사례에 의도치 않은 결함이 없는지
  2. 라벨러 보조 — 인용 원문 대조처럼 눈으로 하기 힘든 대조만 대신 수행

사용: python goldenset/tools/check_cases.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQRT10 = math.sqrt(10)

BANNED = ["최적", "최선", "가장 좋은", "보장", "확정", "반드시", "무조건", "절대", "확실히"]
NEG = ["않", "아니", "못", "없"]
CITE_RE = re.compile(r"> \"(.+?)\"\n> — 출처: (.+?), chunk_id: ([\w\-]+)", re.S)
ART_RE = re.compile(r"제(\d+)[조장절]")
SEP = r"\s*[/,]\s*"  # 표·불릿은 '/', 서술형은 ',' 로 구분한다
WEIGHT_RE = re.compile(
    rf"국내주식\s*(\d+)%{SEP}해외주식\s*(\d+)%{SEP}국내채권\s*(\d+)%"
    rf"{SEP}해외채권\s*(\d+)%{SEP}대체투자\s*(\d+)%{SEP}현금\s*(\d+)%"
)
# 'VaR'는 'CVaR'의 부분문자열이므로 앞에 C가 오지 않을 때만 매칭한다
LBL = {"VaR": r"(?<!C)VaR", "CVaR": r"CVaR"}
SCALE_TOL = 2e-8  # 비율 8자리 반올림 오차 허용
KRW_RE = re.compile(r"(\d{1,3}(?:,\d{3})+)\s*KRW|\*\*(\d{1,3}(?:,\d{3})+)\s*KRW\*\*")

def norm(value: str) -> str:
    return " ".join(value.split())


def load_chunks() -> dict:
    raw = json.loads((ROOT / "corpus" / "chunks.json").read_text(encoding="utf-8"))
    return {c["chunk_id"]: c for c in raw}


def check_citations(text: str, chunks: dict) -> list[str]:
    """① 출처 · ③ 환각 — 인용문이 원문과 맞는지, chunk이 실재하는지."""
    out = []
    for quote, source, cid in CITE_RE.findall(text):
        if cid not in chunks:
            out.append(f"환각-F3: 존재하지 않는 chunk_id `{cid}`")
            continue
        if norm(quote) not in norm(chunks[cid]["text"]):
            out.append(f"출처-F3: `{cid}` 인용문이 원문 부분문자열이 아님")
        a, b = ART_RE.search(source), ART_RE.search(chunks[cid]["source"])
        if a and b and a.group(1) != b.group(1):
            out.append(
                f"출처-F2/B6: `{cid}` 조항 번호 불일치 — 기재 제{a.group(1)} / 원문 제{b.group(1)}"
            )
    return out


def check_weights(text: str) -> list[str]:
    """② 수치정합 — 6자산군 비중 합계."""
    m = WEIGHT_RE.search(text)
    if not m:
        return ["(비중 표기를 찾지 못함 — 형식 확인 필요)"]
    total = sum(int(x) for x in m.groups())
    return [] if total == 100 else [f"수치정합-F1: 비중 합계 {total}%"]


def check_scaling(text: str) -> list[str]:
    """② 수치정합 — 10일 값이 1일 값 × √10 인지 (비율 기준)."""
    out = []
    for label, pat in LBL.items():
        pairs = re.findall(rf"{pat} \(비율\) \| (0\.\d+) \| (0\.\d+)", text)
        d1 = re.search(rf"1일 {pat}: (0\.\d+)", text)
        d10 = re.search(rf"10일 {pat}: (0\.\d+)", text)
        if d1 and d10:
            pairs.append((d1.group(1), d10.group(1)))
        for a, b in pairs:
            exp = round(float(a) * SQRT10, 8)
            if abs(exp - float(b)) > SCALE_TOL:
                out.append(f"수치정합-F3: {label} 10일 {b} ≠ 1일×√10 ({exp:.8f})")
    return out


def check_ci(text: str) -> list[str]:
    """② 수치정합-F6/F7 · ④ 위조정밀도 — 구간이 점추정치를 품는지, √10 규약을 지키는지."""
    out = []
    rows = re.findall(
        r"\| (C?VaR) \(KRW\) \| ([\d,]+) \| ([\d,]+) \|\n"
        r"\| \1 90% 신뢰구간 \(KRW\) \| ([\d,]+) ~ ([\d,]+) \| ([\d,]+) ~ ([\d,]+) \|",
        text,
    )
    def n(value: str) -> int:
        return int(value.replace(",", ""))

    for label, p1, p10, l1, h1, l10, h10 in rows:
        if not n(l1) < n(p1) < n(h1):
            out.append(f"수치정합-F6: {label} 1일 구간이 점추정치를 품지 않음")
        if not n(l10) < n(p10) < n(h10):
            out.append(f"수치정합-F6: {label} 10일 구간이 점추정치를 품지 않음")
        for side, a, b in (("하한", l1, l10), ("상한", h1, h10)):
            exp = round(n(a) * SQRT10)
            if abs(exp - n(b)) > 2:
                out.append(
                    f"수치정합-F7: {label} 10일 구간 {side} {n(b):,} ≠ 1일×√10 ({exp:,})"
                )
    return out


def check_precision(text: str) -> list[str]:
    """④ 위조정밀도 — 불확실성 표기(P2)와 두 신뢰 수준 구분(P5/F6)."""
    out = []
    has_ci = "신뢰구간" in text
    has_phrase = ("초과할 수 있습니다" in text) or ("다를 수 있습니다" in text)
    if not (has_ci or has_phrase):
        out.append("위조정밀도-F4: CI 수치도 불확실성 문구도 없음")
    if "99% 신뢰구간" in text:
        out.append("위조정밀도-F6: 구간을 '99% 신뢰구간'으로 표기 (ci_level과 혼동 의심)")
    for m in re.finditer(r"확률(?:은|이)?\s*\*{0,2}(\d+\.\d+)%", text):
        out.append(f"위조정밀도-F1 후보: 확률 {m.group(1)}% — 산출 근거 확인 필요")
    return out


def check_disclaimer(text: str) -> list[str]:
    """⑤ 면책 — E1(비권유) + E3(책임 소재) 둘 다 필수."""
    out = []
    e1 = re.search(r"투자\s*권유.{0,20}(?:아니|않)", text)
    e3 = re.search(r"(?:최종\s*(?:의사결정|판단)).{0,20}책임", text)
    if not e1:
        out.append("면책-F2: E1(비권유 부정) 없음")
    if not e3:
        out.append("면책-F3: E3(책임 소재) 없음")
    return out


def check_banned(text: str) -> list[str]:
    """⑥ 금지표현 — 인용문(B7)·명시적 부정(B1) 제외."""
    out = []
    lines = text.split("\n")
    for word in BANNED:
        for m in re.finditer(word, text):
            if lines[text[: m.start()].count("\n")].strip().startswith(">"):
                continue  # B7 인용문
            if any(x in text[m.end() : m.end() + 15] for x in NEG):
                continue  # B1 명시적 부정
            ctx = text[max(0, m.start() - 12) : m.end() + 12].replace("\n", " ")
            out.append(f"금지표현-F1: `{word}` — …{ctx.strip()}…")
    return out


def check_hallucination(text: str) -> list[str]:
    """③ 환각 — 출처 없는 시장 수치 서술 후보."""
    out = []
    for m in re.finditer(r"(?:최근|전월|전분기)[^\n.]{0,40}?(\d+)\s*bp[^\n]{0,20}", text):
        out.append(f"환각-F1 후보: 출처 없는 시장 수치 — …{m.group(0).strip()}…")
    return out


def main() -> int:
    chunks = load_chunks()
    files = sorted((ROOT / "cases").glob("case_*.md"))
    print(f"사례 {len(files)}건 · 코퍼스 청크 {len(chunks)}건\n")
    total = 0
    for f in files:
        t = f.read_text(encoding="utf-8")
        findings = (
            check_citations(t, chunks)
            + check_weights(t)
            + check_scaling(t)
            + check_ci(t)
            + check_precision(t)
            + check_disclaimer(t)
            + check_banned(t)
            + check_hallucination(t)
        )
        total += len(findings)
        mark = "  " if findings else "✔ "
        print(f"{mark}{f.stem}" + ("" if findings else "  지적 없음"))
        for x in findings:
            print(f"     · {x}")
    print(f"\n총 지적 {total}건 — **판정이 아니라 대조 결과다.** 라벨은 사람이 정한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
