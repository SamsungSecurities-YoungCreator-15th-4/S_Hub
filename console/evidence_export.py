"""Streamlit 실행 state를 R4 감사 증거 ZIP으로 변환하는 UI 어댑터."""

from __future__ import annotations

import io
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine.evidence.schema import BUNDLE_FILENAMES, BUNDLE_HASH_FILENAME
from scripts.engine.make_evidence_bundle import make_bundle


@dataclass(frozen=True)
class EvidenceDownload:
    """Streamlit ``download_button``에 전달할 감사 번들."""

    filename: str
    data: bytes
    bundle_hash: str
    run_id: str


def _safe_run_id(state: dict) -> str:
    """trace_id를 파일명에 안전한 실행 ID로 정규화한다."""
    raw = state.get("trace_id")
    if not isinstance(raw, str) or not raw.strip():
        raw = ((state.get("metrics") or {}).get("meta") or {}).get(
            "computation_hash"
        )
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw or "unknown-run")).strip("-.")
    return f"ui-{value or 'unknown-run'}"


def _zip_bundle(bundle_dir: Path) -> bytes:
    """계약 파일만 이름순으로 ZIP에 넣어 불필요한 로컬 파일 유입을 막는다."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in sorted(BUNDLE_FILENAMES):
            path = bundle_dir / filename
            if not path.is_file():
                raise RuntimeError(f"감사 번들 필수 파일 누락: {filename}")
            archive.writestr(filename, path.read_bytes())
    return output.getvalue()


def build_evidence_download(
    state: dict,
    *,
    generated_at: str | None = None,
    calibration: object = None,
) -> EvidenceDownload:
    """성공·Hard Stop 최종 state 모두에서 다운로드 가능한 증거 ZIP을 만든다.

    Streamlit 세션에서 한 번 생성한 결과를 보관하는 호출을 전제로 한다. 실제 생성
    시각은 감사 메타데이터이므로 벽시계를 사용하되, 테스트와 재현 검증에서는
    ``generated_at``을 주입할 수 있다.
    """
    if not isinstance(state, dict) or not isinstance(state.get("report"), dict):
        raise ValueError("최종 report가 포함된 state가 필요합니다.")

    run_id = _safe_run_id(state)
    created_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    with tempfile.TemporaryDirectory(prefix="symphony-evidence-") as temp_dir:
        bundle_dir = make_bundle(
            state,
            Path(temp_dir) / run_id,
            run_id=run_id,
            generated_at=created_at,
            calibration=calibration,
        )
        bundle_hash = (bundle_dir / BUNDLE_HASH_FILENAME).read_text(
            encoding="utf-8"
        ).strip()
        data = _zip_bundle(bundle_dir)

    return EvidenceDownload(
        filename=f"symphony-evidence-{run_id}.zip",
        data=data,
        bundle_hash=bundle_hash,
        run_id=run_id,
    )
