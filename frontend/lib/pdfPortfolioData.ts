/**
 * PDF 포트폴리오·성과·자산배분·거시지표 섹션 어댑터
 * store 데이터를 PDF 렌더링 shape으로 변환한다. pdfTaxData.ts와 동일한 패턴.
 *
 * 추적성: 모든 값은 useDashboardStore의 실시간 데이터 소스다.
 *   - 자산배분 → Portfolio.allocation(백엔드 실데이터) 또는 11종 계산 단위 폴백
 *   - 거시지표 → MacroIndicator.direction/change (MacroTicker가 올린 실데이터)
 *   - 성과지표 → Portfolio.metrics (calculate 응답)
 */
import type { Portfolio, MacroIndicator } from "@/lib/mockData";
import { pctOfAumLabel } from "@/lib/formatKrw";
import { formatSharpe } from "@/lib/sharpe";
import {
  BACKEND_ASSET_COLORS,
  toCalcUnitAllocation,
} from "@/lib/assetMapping";

const TEXT = "#111827";
const UP = "#F04452";
const BRAND = "#0050D6";

// ── 자산 배분 ──────────────────────────────────────────────────────────────────

export type PdfAssetSlice = { label: string; weight: number; color: string };

/**
 * 포트폴리오 자산 배분 슬라이스.
 * PortfolioSection과 동일하게 pf.allocation(백엔드 실데이터) 우선,
 * 없으면 11종 계산 단위(toCalcUnitAllocation) 폴백. 비중 0 항목 제외.
 */
export function buildPdfAllocation(pf: Portfolio): PdfAssetSlice[] {
  if (pf.allocation?.length) {
    return pf.allocation
      .filter((a) => a.weight > 0)
      .map((a) => ({
        label: a.name,
        weight: a.weight,
        color: BACKEND_ASSET_COLORS[a.asset_class] ?? "#8899AA",
      }));
  }
  /*
    11종 계산 단위를 그대로 쓴다. 예전에는 6분류(toDisplayAllocation)로 접었는데
    그 분류는 세제 기준이라 리츠·금·인프라펀드가 전부 "분리과세" 한 조각이 됐다.
    대체자산을 제안에 넣어 놓고 리포트에는 이름이 안 나오는 상태였다.
    화면 도넛(components/portfolio/AssetDonut)과 같은 분류를 쓴다.
  */
  return toCalcUnitAllocation(
    pf.weights ?? ({} as Parameters<typeof toCalcUnitAllocation>[0]),
  ).filter((d) => d.weight > 0);
}

// ── 거시지표 ──────────────────────────────────────────────────────────────────

export type PdfMacroCell = {
  label: string;
  value: string;
  changeText: string;
  arrow: "▲" | "▼" | null;
  color: string;
};

/** change 문자열에서 숫자만 파싱해 0 여부 판단 */
function isZeroOrNeutral(m: MacroIndicator): boolean {
  if ((m as { direction: string }).direction === "neutral") return true;
  const num = parseFloat(m.change.replace(/[^0-9.-]/g, ""));
  return isNaN(num) || num === 0;
}

/**
 * 거시지표 셀.
 * 변화량 0(또는 neutral) → 삼각형 없이 검은색.
 * 상승 → ▲ 빨강 / 하락 → ▼ 파랑.
 */
export function buildPdfMacroCell(m: MacroIndicator): PdfMacroCell {
  const neutral = isZeroOrNeutral(m);
  const isUp = m.direction === "up";
  return {
    label: m.label,
    value: m.value,
    changeText: m.change,
    arrow: neutral ? null : isUp ? "▲" : "▼",
    color: neutral ? TEXT : isUp ? UP : BRAND,
  };
}

// ── 성과 지표 ─────────────────────────────────────────────────────────────────

export type PdfPerfRow = {
  label: string;
  vals: string[];
  /** 세후 수익률 행은 UP(빨강)으로 표시 */
  upColor?: string;
};

function fmtMdd(pct: number | null | undefined, label: string | null | undefined): string {
  if (pct == null) return "-";
  const arrow = pct !== 0 ? "▼" : "";
  return `${arrow}${pct}%\n(${label ?? "-"})`;
}

/** 변동성 표기 — 화면처럼 원화 병기를 붙인다. 방향이 없는 지표라 삼각형은 없다. */
function fmtVol(pct: number | null | undefined, label: string | undefined): string {
  if (pct == null) return "-";
  return `${pct}%\n(${label ?? "-"})`;
}

function fmtAfterTax(pct: number | null | undefined, label: string | null | undefined): string {
  if (pct == null) return "-";
  const arrow = pct !== 0 ? "▲" : "";
  return `${arrow}${pct}%\n(${label ?? "-"})`;
}

/**
 * 성과 지표 비교 행.
 * - 0 값: 삼각형·기호 없음
 * - 세후 수익률: upColor = UP(빨강) override
 * - 모든 값이 "-"인 행은 필터링
 */
export function buildPdfPerfRows(
  portfolios: Portfolio[],
  aumEokwon: number,
): PdfPerfRow[] {
  const cur = portfolios.find((p) => p.id === "current");
  const a = portfolios.find((p) => p.id === "a");
  const b = portfolios.find((p) => p.id === "b");
  if (!cur || !a || !b) return [];

  const fmtN = (v: number | null | undefined): string =>
    v == null ? "-" : String(v);

  /*
    원화 병기는 화면과 같은 규칙으로 만든다 — 백엔드 실계산 값이 있으면 그것을,
    없으면 비율 × 고객 총자산으로 계산한다. 폴백이 없어 프론트만으로 돌 때
    PDF 의 금액이 "-" 로 비어 나오고 있었다(화면에는 폴백이 있다).
  */
  const amount = (
    label: string | undefined,
    pct: number,
    prefix: "±" | "-" | "+",
  ): string | undefined => label ?? pctOfAumLabel(pct, aumEokwon, prefix);

  /*
    순서는 화면 지표 격자와 같다 — 왼쪽 열(수익)·오른쪽 열(위험)을 위에서부터
    번갈아 읽은 순서다. 같은 값을 두 곳이 다른 차례로 보여주면 대조가 어렵다.
  */
  const rows: PdfPerfRow[] = [
    {
      label: "세후 수익률",
      upColor: UP,
      vals: [
        fmtAfterTax(
          cur.metrics.afterTaxReturnPct,
          amount(
            cur.metrics.afterTaxAmountLabel,
            cur.metrics.afterTaxReturnPct,
            cur.metrics.afterTaxReturnPct < 0 ? "-" : "+",
          ),
        ),
        fmtAfterTax(
          a.metrics.afterTaxReturnPct,
          amount(
            a.metrics.afterTaxAmountLabel,
            a.metrics.afterTaxReturnPct,
            a.metrics.afterTaxReturnPct < 0 ? "-" : "+",
          ),
        ),
        fmtAfterTax(
          b.metrics.afterTaxReturnPct,
          amount(
            b.metrics.afterTaxAmountLabel,
            b.metrics.afterTaxReturnPct,
            b.metrics.afterTaxReturnPct < 0 ? "-" : "+",
          ),
        ),
      ],
    },
    {
      label: "최대낙폭 (MDD)",
      vals: [
        fmtMdd(cur.metrics.mddPct, amount(cur.metrics.mddAmountLabel, cur.metrics.mddPct, "-")),
        fmtMdd(a.metrics.mddPct, amount(a.metrics.mddAmountLabel, a.metrics.mddPct, "-")),
        fmtMdd(b.metrics.mddPct, amount(b.metrics.mddAmountLabel, b.metrics.mddPct, "-")),
      ],
    },
    {
      label: "기대수익률 (연)",
      vals: [
        `${cur.metrics.expectedReturnPct}%`,
        `${a.metrics.expectedReturnPct}%`,
        `${b.metrics.expectedReturnPct}%`,
      ],
    },
    {
      label: "변동성 (표준편차)",
      vals: [
        fmtVol(cur.metrics.volatilityPct, amount(cur.metrics.volatilityAmountLabel, cur.metrics.volatilityPct, "±")),
        fmtVol(a.metrics.volatilityPct, amount(a.metrics.volatilityAmountLabel, a.metrics.volatilityPct, "±")),
        fmtVol(b.metrics.volatilityPct, amount(b.metrics.volatilityAmountLabel, b.metrics.volatilityPct, "±")),
      ],
    },
    {
      label: "샤프 지수",
      vals: [
        formatSharpe(cur.metrics.sharpe),
        formatSharpe(a.metrics.sharpe),
        formatSharpe(b.metrics.sharpe),
      ],
    },
    {
      label: "소르티노 지수",
      vals: [
        fmtN(cur.metrics.sortino),
        fmtN(a.metrics.sortino),
        fmtN(b.metrics.sortino),
      ],
    },
  ];

  return rows.filter((row) =>
    row.vals.some((v) => v !== "-" && !v.startsWith("-\n")),
  );
}
