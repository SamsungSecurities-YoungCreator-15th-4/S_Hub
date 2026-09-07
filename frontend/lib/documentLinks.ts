export interface DocumentInfo {
  url: string;
  date: string; // YYYY-MM-DD 혹은 YYYY-MM 포맷
}

export const DOCUMENT_LINKS: Record<string, DocumentInfo> = {
  // ── House view ────────────────────────────────────────────
  "samsung bond 202408": {
    url: "https://drive.google.com/file/d/1wA7DchiC_Z8sbweW-jYOKFmJGbWsqZIF/view?usp=drive_link",
    date: "2024-08",
  },
  "samsung bond 202409 check": {
    url: "https://drive.google.com/file/d/1Hr9_dlZgz4oE8H9JtaFmWGKrvWxYzoen/view?usp=drive_link",
    date: "2024-09",
  },
  "samsung bond 202409 outlook": {
    url: "https://drive.google.com/file/d/1XnmaukMW3QvSA3Qw4fXhxKPzR-EVX8LW/view?usp=drive_link",
    date: "2024-09",
  },
  "samsung bond 202502": {
    url: "https://drive.google.com/file/d/1BcLdtph0nDco6Ni6f4CmW7i7C7-_zvpK/view?usp=drive_link",
    date: "2025-02",
  },
  "samsung equity 202510": {
    url: "https://drive.google.com/file/d/1Vq9-Fhrs41SNiMG_-_zdylTNPfmLsMxp/view?usp=drive_link",
    date: "2025-10",
  },
  "samsung equity 202511": {
    url: "https://drive.google.com/file/d/1Bk8cUFuCUWHxJAWIzRXyT5ot8As-HqE7/view?usp=drive_link",
    date: "2025-11",
  },

  // ── macro ─────────────────────────────────────────
  "bok framework 2026": {
    url: "https://drive.google.com/file/d/1lDbSUGPUqXVlabsgAxqSsMMAfMvbrS25/view?usp=drive_link",
    date: "2026",
  },
  "bok mpd 202601": {
    url: "https://drive.google.com/file/d/1GL2KFnAcaQc4ej1G6ZUonqmHnGQKkGDh/view?usp=drive_link",
    date: "2026-01",
  },
  "bok mpd 202602": {
    url: "https://drive.google.com/file/d/1izSJlSbwBjCEXj-t91y0r3QjQYmfg86V/view?usp=drive_link",
    date: "2026-02",
  },
  "bok mpd 202604": {
    url: "https://drive.google.com/file/d/1Stlx8uf8LGtp-kra2hCDP7QrAHdLtHob/view?usp=drive_link",
    date: "2026-04",
  },
  "bok mpd 202605": {
    url: "https://drive.google.com/file/d/1p6gnsakJOw_xLMyzvPLAcNSICbWcKEAB/view?usp=drive_link",
    date: "2026-05",
  },
  "fed fomc 202601": {
    url: "https://drive.google.com/file/d/1rsxMXDcRJMPIzvNfV4VO_3K87rHLzYtY/view?usp=drive_link",
    date: "2026-01",
  },
  "fed fomc 202604": {
    url: "https://drive.google.com/file/d/1Hv6FvyASKsJGvtLSSwHJSEXUgLe0wZ6J/view?usp=drive_link",
    date: "2026-04",
  },

  // ── tax ─────────────────────────────────────────────
  "nts building 2026": {
    url: "https://drive.google.com/file/d/1kWXRZP4imDBlcDY992TmiFQXrniRPXz8/view?usp=drive_link",
    date: "2026",
  },
  "nts inherit 2026": {
    url: "https://drive.google.com/file/d/1wqJsR2s-Iic4Xl9sBKi0ScmHGWBEeC3o/view?usp=drive_link",
    date: "2026",
  },
  "nts sme 2026": {
    url: "https://drive.google.com/file/d/1vImDqjtTRb1CM_aetuwA8xY-GFa-aZMI/view?usp=drive_link",
    date: "2026",
  },
  "nts taxguide 2026 vol1": {
    url: "https://drive.google.com/file/d/1TXmWB3c_z9JLsojkfyywTTIqtYZFnRKY/view?usp=drive_link",
    date: "2026",
  },
  "nts taxguide 2026 vol2 errata": {
    url: "https://drive.google.com/file/d/12dZRCtqXr2FK57MALfxAyM9kgKBMwCyZ/view?usp=drive_link",
    date: "2026",
  },
  "nts taxguide 2026 vol2": {
    url: "https://drive.google.com/file/d/1Oa86Ywi9qFW52RDMf7-Q7RDXFJylm-hT/view?usp=drive_link",
    date: "2026",
  },
};

/**
 * 인용 제목 → 문서 링크 조회.
 *
 * 위 키는 파일명 stem(`_`→공백)만 담고 있는데, 백엔드가 실제로 내려보내는
 * `document.title` 은 `backend/scripts/ingest_documents.py` 의 humanize_title()
 * 결과라 `"<stem> (<source_type>)"` 형태로 source_type 접미사가 붙는다.
 * (같은 함수의 독스트링 예시는 접미사 없는 형태로 적혀 있어 서로 어긋나 있다.)
 *
 * 어느 형태로 들어와도 같은 문서를 찾도록 정확 일치 → 접미사 제거 순으로 조회한다.
 * 접미사를 떼는 정규식은 마지막 괄호 묶음만 지우므로 제목 중간의 괄호는 보존한다.
 */
export function lookupDocument(title: string): DocumentInfo | undefined {
  const exact = DOCUMENT_LINKS[title];
  if (exact) return exact;
  const stripped = title.replace(/\s*\([^()]*\)\s*$/, "").trim();
  return stripped === title ? undefined : DOCUMENT_LINKS[stripped];
}
