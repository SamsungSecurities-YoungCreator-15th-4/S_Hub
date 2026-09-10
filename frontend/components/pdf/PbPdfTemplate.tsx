/**
 * PB용 PDF 템플릿 — A4 세로(794×1123px) 5페이지.
 * 구조: 표지 → 시장현황&IPS → 포트폴리오 비교 → 절세 최적화 → AI 인사이트
 */

import { STRESS_SCENARIOS, runStress } from "@/lib/stressScenarios";
import {
  CITATIONS,
  CVAR_CONTRIBUTIONS,
  CVAR_CONTRIBUTION_NOTE,
  DISCLAIMERS,
  IPS_CONFLICTS,
  IPS_CONFLICT_NOTE,
  REPORT_AS_OF,
  REPORT_META,
  REPRODUCIBILITY_HASHES,
  REPRODUCIBILITY_NOTE,
  RISK_METRICS,
  VERIFICATIONS,
  VERIFICATION_NOTE,
  formatWon,
} from "@/lib/mock/symphonyReport";
import { useDashboardStore } from "@/lib/store";
import { useViewedPortfolio } from "@/lib/viewedPortfolio";
import { useTaxPlan } from "@/lib/taxPlan";
import { deriveAdviceCards } from "@/lib/taxAdviceCards";
import { buildPdfAllocation, buildPdfMacroCell, buildPdfPerfRows } from "@/lib/pdfPortfolioData";
import {
  buildPdfTaxEffect,
  extractTaxOptimizerEntry,
  buildPdfTaxFlow,
  extractPortfolioTaxEntry,
} from "@/lib/pdfTaxData";

// ── 상수 ────────────────────────────────────────────────────────
const W = 794;
const H = 1123;
const BRAND = "#0050D6";
const BRAND_DARK = "#003FA8";
const BRAND_LIGHT = "#EAF1FF";
const BRAND_MID = "#C9DBFF";
const UP = "#F04452";
const TEXT = "#111827";
const MUTED = "#6B7280";
const BORDER = "#E5E7EB";
const BG_ALT = "#FAFAFA";

/** 현재 대시보드에서 선택된 고객(없으면 첫 고객)을 store 에서 읽는다. */
function useSelectedCustomer() {
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  return customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
}

// 절세 계좌 배치 — 기준값(한도) 및 차트 최대값
// 출처: 조세특례제한법 §91의18(ISA), 소득세법 §59의3(연금·IRP)
const ACCOUNT_CHART_MAX = 2000;
const ACCOUNT_PDF = [
  {
    key: "isa",
    name: "ISA",
    refManwon: 2000,
    caption: "납입 한도 100% 활용 · 비과세 200만 + 초과분 9.9% 분리과세",
  },
  {
    key: "pension",
    name: "연금저축 + IRP",
    refManwon: 900,
    caption: "세액공제 한도 소진 · 공제율 16.5% → 환급 148만",
  },
  {
    key: "general",
    name: "일반계좌",
    refManwon: 3000,
    caption: "국내·해외 ETF 중심으로 금융소득종합과세 구간 회피",
  },
];

// 거시지표 한국어 레이블 (ClientPdfTemplate 동일)
const MACRO_DESC: Record<string, string> = {
  기준금리: "미국 기준금리",
  "미 10Y": "미국 장기금리",
  "원/달러": "원/달러 환율",
  KOSPI: "국내 주식 (KOSPI)",
  "S&P500": "미국 주식 (S&P500)",
  CPI: "미국 CPI",
};

// ── 날짜 유틸 ────────────────────────────────────────────────────
function getToday() {
  const d = new Date();
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
}

function getNow() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ── 공통 컴포넌트 ────────────────────────────────────────────────
function PageFooter({ page, total }: { page: number; total: number }) {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 24,
        left: 40,
        right: 40,
        borderTop: `1px solid ${BORDER}`,
        paddingTop: 8,
      }}
    >
      <div
        style={{
          position: "relative",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span style={{ fontSize: 10, color: MUTED }}>
          내부 기밀 자료
        </span>
        <span
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            textAlign: "center",
            fontSize: 10,
            color: MUTED,
          }}
        >
          Page {page} / {total}
        </span>
        <span style={{ fontSize: 10, color: MUTED }}>
          {getToday()} {getNow()}
        </span>
      </div>
    </div>
  );
}

function SectionBar() {
  return (
    <div
      style={{
        width: 4,
        height: 18,
        background: BRAND,
        borderRadius: 2,
        marginRight: 10,
        flexShrink: 0,
      }}
    />
  );
}

function PageHeader({
  pageNum,
  title,
  subtitle,
}: {
  pageNum: string;
  title: string;
  subtitle: string;
}) {
  const customer = useSelectedCustomer();
  return (
    <div
      style={{
        background: `linear-gradient(90deg, ${BRAND_DARK} 0%, ${BRAND} 100%)`,
        padding: "19px 40px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div>
        <div style={{ fontSize: 18, fontWeight: 800, color: "white" }}>
          {pageNum} {title}
        </div>
        <div
          style={{
            fontSize: 13,
            color: "rgba(255,255,255,0.75)",
            marginTop: 2,
          }}
        >
          {subtitle}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: "white" }}>
          {customer.name}
        </div>
        <div style={{ fontSize: 12, color: "rgba(255,255,255,0.7)" }}>
          {customer.pbCode}
        </div>
      </div>
    </div>
  );
}

function AssetBar({
  label,
  pct,
  color,
  /** 제안 조정 열이 붙어 4열이 되면 한 열이 좁아진다. 라벨을 줄여 막대를 살린다. */
  compact = false,
}: {
  label: string;
  pct: number;
  color: string;
  compact?: boolean;
}) {
  return (
    <div
      // 11종으로 늘면서 한 열이 11줄이 된다. 줄 간격을 좁혀 페이지를 넘기지 않게 한다.
      style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}
    >
      <span
        style={{
          width: compact ? 48 : 60,
          fontSize: compact ? 9 : 10,
          color: MUTED,
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: 7,
          background: "#F3F4F6",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: color,
            borderRadius: 4,
          }}
        />
      </div>
      <span
        style={{
          width: compact ? 24 : 26,
          fontSize: compact ? 10 : 11,
          fontWeight: 700,
          textAlign: "right" as const,
          color,
        }}
      >
        {pct}%
      </span>
    </div>
  );
}

// ── 페이지 1: 표지 ───────────────────────────────────────────────
function CoverPage() {
  const customer = useSelectedCustomer();
  const today = getToday();
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const storePortfolios = useDashboardStore((s) => s.portfolios);
  const taxEffect = buildPdfTaxEffect(extractTaxOptimizerEntry(useDashboardStore((s) => s.taxOptimizer), selectedPortfolioId));
  /*
    표지의 "선택 포트폴리오"도 확정 대상을 따른다 — 조정하고 확정했는데 표지만
    조정 전 제안 이름이면 본문 4열과 표지가 서로 다른 안을 가리킨다.
  */
  const { base: viewedBase, isAdjusted } = useViewedPortfolio();
  const selectedPortfolioName = isAdjusted
    ? `${viewedBase?.name ?? "안정 추구"} (조정)`
    : (storePortfolios.find((p) => p.id === selectedPortfolioId)?.name ??
      "안정 추구");
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 420,
          background:
            "linear-gradient(135deg, #003FA8 0%, #0050D6 55%, #2C7BFF 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          top: 340,
          left: -60,
          right: -60,
          height: 120,
          background: "white",
          borderRadius: "50% 50% 0 0 / 60px 60px 0 0",
        }}
      />
      <div style={{ position: "relative", padding: "44px 52px 0" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 50,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo.png"
              alt=""
              style={{ width: 36, height: 36, borderRadius: 9, objectFit: "cover" }}
            />
            <div>
              <div
                style={{
                  fontSize: 16,
                  fontWeight: 800,
                  color: "white",
                  letterSpacing: 0.5,
                }}
              >
                S.ymphony
              </div>
            </div>
          </div>
          <span
            style={{
              background: "rgba(255,255,255,0.15)",
              border: "1px solid rgba(255,255,255,0.25)",
              color: "rgba(255,255,255,0.92)",
              fontSize: 11,
              fontWeight: 700,
              padding: "5px 13px",
              borderRadius: 20,
              whiteSpace: "nowrap" as const,
            }}
          >
            PB 내부용
          </span>
        </div>
        <div
          style={{
            fontSize: 44,
            fontWeight: 900,
            color: "white",
            lineHeight: 1.2,
            marginBottom: 20,
            marginTop: 60,
          }}
        >
          포트폴리오
          <br />
          분석 <span style={{ color: BRAND_MID }}>리포트</span>
        </div>
        <div
          style={{
            fontSize: 14,
            color: "rgba(255,255,255,0.65)",
            fontWeight: 400,
          }}
        >
          PB 상담 보조 자료
        </div>
      </div>

      <div style={{ position: "relative", padding: "72px 52px 0" }}>
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 14,
            padding: "24px 28px",
            marginBottom: 60,
            marginTop: 56,
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: BRAND,
              letterSpacing: 1.5,
              marginBottom: 10,
            }}
          >
            CLIENT
          </div>
          <div
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: TEXT,
              marginBottom: 6,
            }}
          >
            {customer.name} 고객
          </div>
          <div style={{ fontSize: 12, color: MUTED, fontWeight: 500 }}>
            {customer.pbCode} · {customer.aumLabel}
          </div>
        </div>
        <div style={{ display: "flex" }}>
          {[
            { label: "보고서 일자", value: today },
            { label: "기준 시각", value: `${getNow()} 기준` },
            { label: "선택 포트폴리오", value: selectedPortfolioName },
            {
              label: "예상 연간 절세",
              value: `+${taxEffect.annualSavingManwon.toLocaleString()}만원/년`,
            },
          ].map((item, i) => (
            <div
              key={item.label}
              style={{
                flex: 1,
                paddingLeft: i > 0 ? 20 : 0,
                borderLeft: i > 0 ? `1px solid ${BORDER}` : "none",
                marginLeft: i > 0 ? 20 : 0,
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  color: MUTED,
                  letterSpacing: 0.8,
                  marginBottom: 5,
                }}
              >
                {item.label}
              </div>
              <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          bottom: 36,
          left: 52,
          right: 52,
          background: "#F9FAFB",
          border: `1px solid ${BORDER}`,
          borderRadius: 10,
          padding: "14px 18px",
        }}
      >
        <p style={{ fontSize: 13, color: MUTED, lineHeight: 1.7, margin: 0 }}>
          본 자료는 PB 상담 보조를 위한 내부 기밀 자료입니다. 본 보고서의 분석
          내용, 포트폴리오 제안 및 시뮬레이션 결과는 시장 데이터와 AI 분석을
          기반으로 작성되었으며, 최종 투자 판단은 고객의 투자 목적·위험
          성향·세무·법률 상황을 종합적으로 고려하여 결정되어야 합니다. 무단
          배포를 금합니다.
        </p>
      </div>
    </div>
  );
}

// ── 페이지 2: 시장 현황 & IPS ────────────────────────────────────
function MarketIpsPage() {
  const customer = useSelectedCustomer();
  const ips = useDashboardStore((s) => s.ips);
  // 상단바와 동일한 실시간 시장 지표(store). 미로드 시엔 목 기준값으로 초기화돼 있다.
  const macroIndicators = useDashboardStore((s) => s.macroIndicators);
  const IPS_ROWS = [
    {
      key: "GOAL",
      korean: "투자 목적",
      tag: "복합",
      tagColor: "#6B7280",
      detail: ips.goal ?? "",
      show: !!ips.goal?.trim(),
    },
    {
      key: "ASSET",
      korean: "운용 자산",
      tag: customer.aumLabel,
      tagColor: "#F59E0B",
      detail: customer.aumLabel,
      show: true,
    },
    {
      key: "RETURN",
      korean: "목표 수익률",
      tag: `${ips.returnPct}%`,
      tagColor: "#10B981",
      detail: `연 ${ips.returnPct}% 목표 (세후 기준)`,
      show: true,
    },
    {
      key: "RISK",
      korean: "위험 성향",
      tag: ips.risk,
      tagColor: "#F59E0B",
      detail: ips.risk,
      show: true,
    },
    {
      key: "TIME",
      korean: "투자 기간",
      tag: `${ips.timeYears}년`,
      tagColor: BRAND,
      detail: `${ips.timeYears}년 운용 기준`,
      show: true,
    },
    {
      key: "TAX",
      korean: "세금",
      tag: "종합과세",
      tagColor: UP,
      detail: ips.tax ?? "",
      show: !!ips.tax?.trim(),
    },
    {
      key: "LIQUID",
      korean: "유동성",
      tag: ips.liquidity,
      tagColor: "#F59E0B",
      detail: ips.liquidity,
      show: true,
    },
    {
      key: "LEGAL",
      korean: "법적 제약",
      tag: "검토필요",
      tagColor: UP,
      detail: ips.legal ?? "",
      show: !!ips.legal?.trim(),
    },
    {
      key: "UNIQUE",
      korean: "특수 사항",
      tag: "복합",
      tagColor: "#6B7280",
      detail: ips.unique,
      show: !!ips.unique?.trim(),
    },
  ].filter((r) => r.show);
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="①"
        title="시장 현황 &amp; 고객 IPS 요약"
        subtitle="Market Overview &amp; Investment Policy Statement"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            주요 시장 지표
          </div>
        </div>

        <div
          style={{
            display: "flex",
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            overflow: "hidden",
            marginBottom: 48,
          }}
        >
          {macroIndicators.map((m, idx) => {
            const cell = buildPdfMacroCell(m);
            return (
              <div
                key={m.label}
                style={{
                  flex: 1,
                  padding: "12px 10px",
                  borderRight:
                    idx < macroIndicators.length - 1
                      ? `1px solid ${BORDER}`
                      : "none",
                  background: "white",
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: MUTED,
                    fontWeight: 600,
                    marginBottom: 5,
                  }}
                >
                  {MACRO_DESC[m.label] ?? m.label}
                </div>
                <div
                  style={{
                    fontSize: 17,
                    fontWeight: 900,
                    color: TEXT,
                    lineHeight: 1.1,
                    marginBottom: 5,
                  }}
                >
                  {cell.value}
                </div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: cell.color,
                  }}
                >
                  {cell.arrow ? `${cell.arrow} ` : ""}{cell.changeText}
                </div>
              </div>
            );
          })}
        </div>

        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            고객 IPS 요약
          </div>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
          }}
        >
          <colgroup>
            <col style={{ width: 140 }} />
            <col />
          </colgroup>
          <thead>
            <tr style={{ background: BRAND }}>
              <th
                style={{
                  padding: "9px 12px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "white",
                }}
              >
                항목
              </th>
              <th
                style={{
                  padding: "9px 12px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: "white",
                }}
              >
                세부 내용
              </th>
            </tr>
          </thead>
          <tbody>
            {IPS_ROWS.map((row, i) => (
              <tr
                key={row.key}
                style={{
                  borderBottom: `1px solid ${BORDER}`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td style={{ padding: "9px 12px" }}>
                  <div style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>
                    {row.key}
                  </div>
                  <div style={{ fontSize: 11, color: MUTED }}>{row.korean}</div>
                </td>
                <td
                  style={{
                    padding: "9px 12px",
                    fontSize: 11,
                    color: TEXT,
                    lineHeight: 1.55,
                  }}
                >
                  {row.detail}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <PageFooter page={2} total={7} />
    </div>
  );
}

// ── 페이지 3: 포트폴리오 비교 ────────────────────────────────────
function PortfolioPage() {
  const storePortfolios = useDashboardStore((s) => s.portfolios);
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const aumEokwon =
    (customers.find((c) => c.id === selectedCustomerId) ?? customers[0])?.aumEokwon ?? 50;

  // 훅은 early return 앞에서 호출(react-hooks/rules-of-hooks).
  /*
    강조·계산 대상은 지금 확정 대상인 안이다 — PB 가 제안 조정으로 손본 뒤 확정했는데
    리포트가 조정 전 안을 보여주면 승인한 것과 다른 문서가 나간다.
  */
  const { viewed: adjustedPf, isAdjusted } = useViewedPortfolio();
  const adjusted = isAdjusted ? adjustedPf : null;

  const current = storePortfolios.find((p) => p.id === "current");
  const portA = storePortfolios.find((p) => p.id === "a");
  const portB = storePortfolios.find((p) => p.id === "b");
  if (!current || !portA || !portB) return null;

  const selId: "a" | "b" = selectedPortfolioId === "b" ? "b" : "a";

  /*
    조정하지 않았으면 "제안 조정" 열은 선택한 제안과 같은 값이라 같은 것을 두 번
    보여주게 된다. 손댔을 때만 넷째 열을 세운다.
  */
  const cols = [
    { key: "current", p: current, alloc: buildPdfAllocation(current), label: "현재 포트폴리오", badge: "", badgeColor: "#6B7280", headerColor: "#6B7280", selected: false },
    { key: "a", p: portA, alloc: buildPdfAllocation(portA), label: "안정 추구", badge: "", badgeColor: BRAND, headerColor: BRAND, selected: !isAdjusted && selId === "a" },
    { key: "b", p: portB, alloc: buildPdfAllocation(portB), label: "수익 추구", badge: "", badgeColor: "#2C7BFF", headerColor: "#2C7BFF", selected: !isAdjusted && selId === "b" },
    ...(adjusted
      ? [{ key: "adjusted", p: adjusted, alloc: buildPdfAllocation(adjusted), label: "제안 조정", badge: "", badgeColor: BRAND_DARK, headerColor: BRAND_DARK, selected: true }]
      : []),
  ];

  /*
    buildPdfPerfRows 는 스토어의 세 안만 계산한다. 조정안은 별도로 한 번 더 돌려
    같은 행 순서·같은 서식으로 넷째 값을 만든 뒤 각 행에 이어 붙인다.
  */
  const basePerfRows = buildPdfPerfRows(storePortfolios, aumEokwon);
  /*
    buildPdfPerfRows 는 current·a·b 세 자리가 다 차야 계산한다. 조정안 하나만
    넣을 수는 없어 a·b 두 자리에 같은 조정안을 넣고 그중 한 칸만 꺼내 쓴다.
  */
  const adjustedPerfRows =
    adjusted && current
      ? buildPdfPerfRows(
          [current, { ...adjusted, id: "a" }, { ...adjusted, id: "b" }],
          aumEokwon,
        )
      : null;
  const perfRows = adjustedPerfRows
    ? basePerfRows.map((row, i) => ({
        ...row,
        vals: [...row.vals, adjustedPerfRows[i].vals[1]],
      }))
    : basePerfRows;


  // ── Stress Test ─────────────────────────────────────────────────
  // 화면 카드(StressTestSection)와 같은 runStress 를 쓴다 — 리포트 숫자가
  // 대시보드와 어긋날 수 없게 계산 경로를 하나로 묶는다.
  //
  // 이전에는 isStressMode(백엔드 stress 엔드포인트) 기준이었으나, 금리·환율
  // 슬라이더가 없어지면서 그 플래그를 켤 경로가 사라져 섹션 자체가 렌더되지
  // 않았다. 시나리오가 자산군 충격 기반이므로 금리·환율 열도 충격 가정으로 바꾼다.
  // 스트레스는 비중만 있으면 계산되므로 조정안이 있으면 그 비중으로 낸다.
  const selectedPf = adjusted ?? (selId === "a" ? portA : portB);
  const stressTotalKrw = aumEokwon * 100_000_000;

  const fmtLoss = (lossKrw: number): { text: string; color: string } => {
    const eok = lossKrw / 100_000_000;
    if (Math.abs(eok) < 0.001) return { text: "0.0억원", color: TEXT };
    return { text: `▼ -${Math.abs(eok).toFixed(1)}억원`, color: BRAND };
  };

  // 예상 평가손익은 선택한 포트폴리오(selId) 기준으로 표시한다.
  //
  // 강조 행은 손실이 가장 큰 시나리오다. 예전에는 화면 카드에서 고른 시나리오
  // (store 의 stressScenarioKey)를 따랐는데, 그 카드가 대시보드에서 빠지면서
  // 값을 세울 경로가 사라져 늘 "현재(충격 없음)" 에 고정돼 있었다. 고를 사람이
  // 없으면 리포트가 스스로 정해야 하고, 그 기준은 최악이 맞다 — 여기서 새로
  // 정하지 않고 화면과 같은 runStress 로 계산해 고른다.
  const stressLosses = STRESS_SCENARIOS.map((sc) => ({
    sc,
    loss: runStress(selectedPf.weights, stressTotalKrw, sc),
  }));
  // lossKrw 는 양수가 손실이다(lib/stressScenarios.ts StressLoss).
  const worstKey = stressLosses.reduce((worst, row) =>
    row.loss.lossKrw > worst.loss.lossKrw ? row : worst,
  ).sc.key;

  const stressRows = [
    {
      name: "현재 (충격 없음)",
      shock: "—",
      pnl: { text: "기준", color: MUTED },
      selected: false,
    },
    ...stressLosses.map(({ sc, loss }) => ({
      name: sc.label,
      shock: sc.shockSummary,
      pnl: fmtLoss(loss.lossKrw),
      selected: sc.key === worstKey,
    })),
  ];

  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="②"
        title="포트폴리오 비교 분석"
        subtitle="자산별 성과 지표 및 Stress Test 결과"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 16 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            자산 배분 비교
          </div>
        </div>

        <div style={{ display: "flex", gap: isAdjusted ? 8 : 12, marginBottom: 22 }}>
          {cols.map(({ key, alloc, label, badge, badgeColor, selected }) => (
            <div
              key={key}
              style={{
                flex: 1,
                border: selected ? `2px solid ${BRAND}` : `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: isAdjusted ? "12px 10px" : "13px 14px",
                background: "white",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 11,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>
                  {label}
                </span>
                {badge && (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: badgeColor,
                      background: `${badgeColor}18`,
                      padding: "2px 8px",
                      borderRadius: 10,
                    }}
                  >
                    {badge}
                  </span>
                )}
              </div>
              {alloc.map((slice) => (
                <AssetBar
                  key={slice.label}
                  label={slice.label}
                  pct={Math.round(slice.weight)}
                  color={slice.color}
                  compact={isAdjusted}
                />
              ))}
            </div>
          ))}
        </div>

        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 16 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            성과 지표 비교
          </div>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            tableLayout: "fixed",
            marginBottom: 22,
          }}
        >
          <colgroup>
            <col style={{ width: 150 }} />
            {cols.map((c) => (
              <col key={c.key} />
            ))}
          </colgroup>
          <thead>
            <tr style={{ background: BG_ALT }}>
              <th
                style={{
                  padding: "8px 10px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  borderBottom: `2px solid ${BORDER}`,
                }}
              >
                지표
              </th>
              {cols.map((c) => (
                <th
                  key={c.key}
                  style={{
                    padding: "8px 10px",
                    textAlign: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    color: c.headerColor,
                    borderBottom: `2px solid ${c.headerColor}`,
                  }}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {perfRows.map((row, i) => (
              <tr
                key={row.label}
                style={{
                  borderBottom: `1px solid ${BORDER}`,
                  background: i % 2 === 0 ? "white" : BG_ALT,
                }}
              >
                <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>
                  {row.label}
                </td>
                {row.vals.map((v, j) => (
                  <td
                    key={j}
                    style={{
                      padding: "8px 10px",
                      textAlign: "center",
                      fontSize: 11,
                      fontWeight: j === 0 ? 500 : 700,
                      color: row.upColor ?? cols[j].headerColor,
                      whiteSpace: "pre-line" as const,
                      lineHeight: 1.4,
                      background: cols[j].selected ? `${BRAND}0D` : "inherit",
                    }}
                  >
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>

        {stressRows.length > 0 && (
          <>
            <div
              style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
            >
              <SectionBar />
              <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
                Stress Test
                {/* 어느 안의 손실인지 밝힌다 — 리스크 리포트의 같은 이름 표는
                    현재 포트폴리오를 보므로 값이 다른 것이 정상이다. */}
                <span
                  style={{ marginLeft: 8, fontSize: 11, fontWeight: 700, color: MUTED }}
                >
                  {selectedPf.name} 기준
                </span>
              </div>
            </div>

            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                tableLayout: "fixed",
              }}
            >
              <colgroup>
                <col style={{ width: 180 }} />
                <col />
                <col style={{ width: 130 }} />
              </colgroup>
              <thead>
                <tr style={{ background: BG_ALT }}>
                  {["시나리오", "충격 가정", "예상 평가손익"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "7px 10px",
                        textAlign: "left",
                        fontSize: 11,
                        fontWeight: 700,
                        color: TEXT,
                        borderBottom: `1.5px solid #D1D5DB`,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {stressRows.map((row, i) => (
                  <tr
                    key={row.name}
                    style={{
                      borderBottom: `1px solid #D1D5DB`,
                      // 대시보드에서 고른 시나리오를 리포트에서도 알아볼 수 있게 강조한다.
                      background: row.selected
                        ? `${BRAND}0D`
                        : i % 2 === 0
                          ? "white"
                          : BG_ALT,
                    }}
                  >
                    <td
                      style={{
                        padding: "8px 10px",
                        fontSize: 11,
                        fontWeight: 700,
                        color: row.selected ? BRAND : TEXT,
                      }}
                    >
                      {row.name}
                    </td>
                    <td style={{ padding: "8px 10px", fontSize: 11, color: TEXT }}>
                      {row.shock}
                    </td>
                    <td
                      style={{
                        padding: "8px 10px",
                        fontSize: 11,
                        fontWeight: 700,
                        color: row.pnl.color,
                      }}
                    >
                      {row.pnl.text}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <PageFooter page={3} total={7} />
    </div>
  );
}

// ── 페이지 4: 절세 최적화 전략 ──────────────────────────────────
function TaxPage() {
  const customer = useSelectedCustomer();
  const taxOptimizerMap = useDashboardStore((s) => s.taxOptimizer);
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  // 절세 계좌 배치 바는 절세 화면(AccountAllocation)과 같이 확정 대상 안을 따른다.
  const { viewed: selectedPf } = useViewedPortfolio();
  const selectedAllocSlices = selectedPf ? buildPdfAllocation(selectedPf) : [];
  const taxOptimizerEntry = extractTaxOptimizerEntry(taxOptimizerMap, selectedPortfolioId);
  const taxEffect = buildPdfTaxEffect(taxOptimizerEntry);
  /*
   * 카드와 총액은 화면(절세 제안 탭)과 같은 함수를 부른다. 예전에는 리포트만
   * mockData 를 읽어, 화면이 "약 +97만원" 을 말할 때 여기에는 자리표시 문구인
   * "분석 후 계산" 이 인쇄됐다.
   */
  const { plan } = useTaxPlan();
  const taxAdvice = deriveAdviceCards(
    plan,
    taxOptimizerEntry?.strategy_cards?.cards ?? null,
  );
  const portfolioTaxMap = useDashboardStore((s) => s.portfolioTax);
  const aumEokwon = customer.aumEokwon ?? 0;
  const portfolioTaxEntry = extractPortfolioTaxEntry(portfolioTaxMap, selectedPortfolioId);
  const taxFlow = buildPdfTaxFlow(taxOptimizerEntry, aumEokwon, portfolioTaxEntry);
  // 계좌별 사용액 계산 (AccountAllocation 동일 로직)
  const accountRows = ACCOUNT_PDF.filter((acct) => acct.key !== "general").map(
    (acct) => {
      const accData = taxEffect.accounts.find((a) => a.name === acct.name);
      const used =
        accData?.used != null
          ? accData.used
          : Math.round(acct.refManwon * 0.45);
      return { ...acct, used };
    },
  );

  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="③"
        title="절세 최적화 전략"
        subtitle="세금 효과 시뮬레이터"
      />

      <div style={{ padding: "20px 40px 80px", wordBreak: "keep-all" }}>
        {/* 연간 절세 효과 하이라이트 */}
        <div
          style={{
            background: `linear-gradient(135deg, ${BRAND_DARK} 0%, ${BRAND} 60%, #2C7BFF 100%)`,
            borderRadius: 12,
            padding: "16px 24px",
            marginBottom: 20,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <div
              style={{
                color: "rgba(255,255,255,0.7)",
                fontSize: 11,
                fontWeight: 600,
                marginBottom: 4,
              }}
            >
              연간 절세 효과 ({selectedPf?.name ?? "안정 추구"} 기준 ·{" "}
              {customer.aumLabel})
            </div>
            <div
              style={{
                color: "white",
                fontSize: 34,
                fontWeight: 900,
                lineHeight: 1,
              }}
            >
              + {taxEffect.annualSavingManwon.toLocaleString()}만원
            </div>
          </div>
          <div style={{ textAlign: "right", maxWidth: 260 }}>
            <div
              style={{
                color: "rgba(255,255,255,0.65)",
                fontSize: 11,
                lineHeight: 1.7,
              }}
            >
              {taxEffect.subNote}
            </div>
          </div>
        </div>

        {/* 섹션 1: 절세 전략 비교 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 12 }}
        >
          <SectionBar />
          <div style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
            절세 전략 비교{taxFlow ? ` (${taxFlow.pretaxLabel})` : ""}
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, marginBottom: 20 }}>
          {/* 세금 효과 비교 테이블 */}
          <div
            style={{
              flex: 1.1,
              border: `1px solid ${BORDER}`,
              borderRadius: 10,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div
              style={{
                background: BG_ALT,
                padding: "6px 12px",
                fontSize: 11,
                fontWeight: 800,
                color: TEXT,
                borderBottom: `1px solid ${BORDER}`,
              }}
            >
              세금 효과 비교
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${BORDER}` }}>
                  {["구분", "세후 수익", "절세액", "비고"].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: "5px 8px",
                        fontSize: 10,
                        fontWeight: 700,
                        color: MUTED,
                        textAlign: "center",
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {taxFlow ? (
                  taxFlow.rows.map((row, i) => (
                    <tr
                      key={row.label}
                      style={{
                        borderBottom: `1px solid ${BORDER}`,
                        background: "white",
                      }}
                    >
                      <td
                        style={{
                          padding: "7px 8px",
                          fontSize: 11,
                          fontWeight: 700,
                          color: TEXT,
                        }}
                      >
                        {row.label}
                      </td>
                      <td
                        style={{
                          padding: "7px 8px",
                          fontSize: 10,
                          textAlign: "center",
                          color: TEXT,
                        }}
                      >
                        세후 {row.afterTaxManwon.toLocaleString()}만원
                      </td>
                      <td
                        style={{
                          padding: "7px 8px",
                          fontSize: 10,
                          textAlign: "center",
                          fontWeight: 700,
                          color: UP,
                        }}
                      >
                        {row.taxManwon.toLocaleString()}만
                      </td>
                      <td
                        style={{
                          padding: "7px 8px",
                          fontSize: 10,
                          textAlign: "center",
                          color: MUTED,
                        }}
                      >
                        {i === 0 ? "기준" : "절세 적용"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td
                      colSpan={4}
                      style={{
                        padding: "14px 8px",
                        textAlign: "center",
                        fontSize: 11,
                        color: MUTED,
                      }}
                    >
                      분석 후 확인할 수 있습니다
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <div
              style={{
                padding: "7px 12px",
                background: BG_ALT,
                borderTop: `1px solid ${BORDER}`,
                marginTop: "auto",
              }}
            >
              <div style={{ fontSize: 10, color: MUTED, lineHeight: 1.7 }}>
                ✓ 세후 수익률 {taxEffect.afterTaxReturn.from} →{" "}
                {taxEffect.afterTaxReturn.to} (
                {taxEffect.afterTaxReturn.delta})<br />✓ 실효세 절감{" "}
                {taxEffect.effectiveTax.from} → {taxEffect.effectiveTax.to} (
                {taxEffect.effectiveTax.delta})
              </div>
            </div>
          </div>

          {/* 절세 계좌 배치 최적화 — 대시보드 동일 레이아웃 */}
          <div
            style={{
              flex: 1,
              border: `1px solid ${BORDER}`,
              borderRadius: 10,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                background: BG_ALT,
                padding: "6px 12px",
                fontSize: 11,
                fontWeight: 800,
                color: TEXT,
                borderBottom: `1px solid ${BORDER}`,
              }}
            >
              절세 계좌 배치 최적화
            </div>
            <div style={{ padding: "12px 14px 10px" }}>
              {/* 전체 계좌 세그먼트 바 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    width: 68,
                    flexShrink: 0,
                    textAlign: "right" as const,
                    paddingRight: 8,
                    fontSize: 10,
                    fontWeight: 800,
                    color: "#4E5968",
                  }}
                >
                  전체 계좌
                </span>
                <div
                  style={{
                    flex: 1,
                    height: 10,
                    display: "flex",
                    overflow: "hidden",
                    borderRadius: 4,
                    marginRight: 47,
                  }}
                >
                  {selectedAllocSlices.map((slice) => (
                    <div
                      key={slice.label}
                      style={{
                        width: `${Math.round(slice.weight)}%`,
                        height: "100%",
                        background: slice.color,
                      }}
                    />
                  ))}
                </div>
              </div>
              {/* 세그먼트 범례 */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap" as const,
                  gap: "2px 6px",
                  marginLeft: 68,
                  marginBottom: 10,
                }}
              >
                {selectedAllocSlices.map((slice) => (
                  <span
                    key={slice.label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 3,
                      fontSize: 9,
                      color: MUTED,
                      fontWeight: 600,
                    }}
                  >
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: 1,
                        background: slice.color,
                        display: "inline-block",
                        flexShrink: 0,
                      }}
                    />
                    {slice.label} {Math.round(slice.weight)}%
                  </span>
                ))}
              </div>
              {/* Y축 + 바 영역 */}
              <div style={{ display: "flex", gap: 0 }}>
                {/* Y축 레이블 */}
                <div style={{ width: 68, flexShrink: 0 }}>
                  {accountRows.map((acct, idx) => (
                    <div
                      key={acct.name}
                      style={{
                        height: 30,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "flex-end",
                        paddingRight: 8,
                        marginBottom: idx < accountRows.length - 1 ? 14 : 0,
                        fontSize: 10,
                        fontWeight: 800,
                        color: "#4E5968",
                        textAlign: "right" as const,
                        lineHeight: 1.2,
                      }}
                    >
                      {acct.name}
                    </div>
                  ))}
                </div>
                {/* 바 영역 */}
                <div style={{ flex: 1 }}>
                  {accountRows.map((acct, idx) => {
                    const refPct = (acct.refManwon / ACCOUNT_CHART_MAX) * 100;
                    const usedPct = (acct.used / ACCOUNT_CHART_MAX) * 100;
                    const usedColor = idx === 0 ? "#0064FF" : "#3D8BFF";
                    return (
                      <div
                        key={acct.name}
                        style={{
                          marginBottom: idx < accountRows.length - 1 ? 14 : 0,
                        }}
                      >
                        {/* 기준값 바 (회색, 위) + 값 */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            marginBottom: 4,
                          }}
                        >
                          <div
                            style={{
                              flex: 1,
                              height: 13,
                              background: "#F3F4F6",
                              borderRadius: 4,
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${refPct}%`,
                                height: "100%",
                                background: "#D1D5DB",
                                borderRadius: 4,
                              }}
                            />
                          </div>
                          <span
                            style={{
                              width: 42,
                              fontSize: 9,
                              fontWeight: 600,
                              color: MUTED,
                              textAlign: "right" as const,
                              flexShrink: 0,
                            }}
                          >
                            {acct.refManwon.toLocaleString()}만
                          </span>
                        </div>
                        {/* 사용액 바 (파란색, 아래) + 값 */}
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                          }}
                        >
                          <div
                            style={{
                              flex: 1,
                              height: 13,
                              background: "#F3F4F6",
                              borderRadius: 4,
                              overflow: "hidden",
                            }}
                          >
                            <div
                              style={{
                                width: `${usedPct}%`,
                                height: "100%",
                                background: usedColor,
                                borderRadius: 4,
                              }}
                            />
                          </div>
                          <span
                            style={{
                              width: 42,
                              fontSize: 9,
                              fontWeight: 800,
                              color: usedColor,
                              textAlign: "right" as const,
                              flexShrink: 0,
                            }}
                          >
                            {acct.used.toLocaleString()}만
                          </span>
                        </div>
                      </div>
                    );
                  })}
                  {/* X축 틱 */}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginTop: 6,
                    }}
                  >
                    {["0", "500만", "1천만", "1500만", "2천만"].map((t) => (
                      <span
                        key={t}
                        style={{
                          fontSize: 8.5,
                          color: "#B0B8C1",
                          fontWeight: 600,
                        }}
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              {/* 범례 (하단) */}
              <div style={{ display: "flex", gap: 14, marginTop: 10 }}>
                {[
                  { color: "#0064FF", label: "ISA 사용액" },
                  { color: "#3D8BFF", label: "연금 사용액" },
                  { color: "#D1D5DB", label: "기준값" },
                ].map((l) => (
                  <div
                    key={l.label}
                    style={{ display: "flex", alignItems: "center", gap: 5 }}
                  >
                    <div
                      style={{
                        width: 10,
                        height: 10,
                        background: l.color,
                        borderRadius: 2,
                      }}
                    />
                    <span
                      style={{ fontSize: 9.5, color: MUTED, fontWeight: 700 }}
                    >
                      {l.label}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* 섹션 2: 절세 제안 6개 카드 (전략 요약만 — 상품은 하단 표 참조) */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 12 }}
        >
          <SectionBar />
          <div style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
            절세 제안
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 10,
            marginBottom: 10,
          }}
        >
          {taxAdvice.cards.map((card) => (
            <div
              key={card.title}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "12px 14px",
                background: "white",
              }}
            >
              {/* 헤더: 제목만 */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 8,
                }}
              >
                <span style={{ fontSize: 12, fontWeight: 800, color: TEXT }}>
                  {card.title}
                </span>
              </div>
              {/* 배분 요약 — 화면 카드의 첫 줄과 같은 문장이다. */}
              {card.summary && (
                <p
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    color: TEXT,
                    margin: "0 0 5px 0",
                  }}
                >
                  {card.summary}
                </p>
              )}
              {/* 본문 */}
              <p
                style={{
                  fontSize: 11,
                  color: MUTED,
                  lineHeight: 1.65,
                  margin: "0 0 6px 0",
                }}
              >
                {card.body}
              </p>
              {/* 태그 */}
              <div style={{ fontSize: 10, color: "#9CA3AF", marginBottom: 5 }}>
                {card.tag}
              </div>
              {/* 절세액 — 태그 아래 */}
              {card.saving && (
                <span style={{ fontSize: 13, fontWeight: 900, color: UP }}>
                  {card.saving}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* 총 절세 효과 요약 바 */}
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 7,
            padding: "7px 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: BRAND_DARK,
              whiteSpace: "nowrap",
            }}
          >
            {taxAdvice.totalLabel}
          </span>
          <span
            style={{
              fontSize: 11,
              fontWeight: 900,
              color: BRAND_DARK,
              whiteSpace: "nowrap",
              flexShrink: 0,
            }}
          >
            {taxAdvice.totalSaving}
          </span>
        </div>
      </div>

      <PageFooter page={4} total={7} />
    </div>
  );
}

// ── 페이지 5: AI 인사이트 ────────────────────────────────────────
function AiPage() {
  const insightResult = useDashboardStore((s) => s.insightResult);
  if (!insightResult) return null;
  const answer = insightResult.data.answer;
  const question = insightResult.data.question?.trim();
  // 한 질의가 같은 문서의 여러 청크를 인용해 제목이 중복될 수 있다. 출처 목록은 문서당
  // 한 번만 적는 게 보편적이고, 중복을 그대로 두면 페이지를 넘쳐 깨지므로 제목 기준으로
  // 중복을 제거하고 안전하게 상한을 둔다(렌더 마크업은 그대로).
  const citationSources = (() => {
    const seen = new Set<string>();
    const unique: { title: string; date: string | null }[] = [];
    for (const src of insightResult.data.citations) {
      const key = (src.title ?? "").trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      unique.push({ title: src.title, date: src.date ?? null });
      if (unique.length >= 8) break;
    }
    return unique;
  })();
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="⑦"
        title="AI 인사이트"
        subtitle="RAG 기반 포트폴리오 분석 · 시장 환경 대응 제안"
      />

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        {/* AI 인사이트 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 20 }}
        >
          <SectionBar />
          <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
            AI 인사이트
          </div>
        </div>

        <div
          style={{
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            padding: "16px 20px",
            background: BG_ALT,
            marginBottom: 36,
          }}
        >
          {/* Q. — 사용자가 입력한 질문 (있을 때만) */}
          {question && (
            <div
              style={{
                display: "flex",
                gap: 8,
                alignItems: "flex-start",
                marginBottom: 12,
                paddingBottom: 12,
                borderBottom: `1px solid ${BORDER}`,
              }}
            >
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 900,
                  color: BRAND,
                  flexShrink: 0,
                  lineHeight: 1.5,
                }}
              >
                Q.
              </span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: TEXT,
                  lineHeight: 1.6,
                  paddingTop: 1,
                }}
              >
                {question}
              </span>
            </div>
          )}
          {/* A. — AI 답변 */}
          <div
            style={{
              display: "flex",
              gap: 8,
              alignItems: "flex-start",
            }}
          >
            <span
              style={{
                fontSize: 14,
                fontWeight: 900,
                color: TEXT,
                flexShrink: 0,
                lineHeight: 1.5,
              }}
            >
              A.
            </span>
            <span
              style={{
                fontSize: 12,
                color: "#374151",
                lineHeight: 1.75,
                paddingTop: 1,
              }}
            >
              {answer}
            </span>
          </div>
        </div>

        {/* 인용이 없으면 제목·표 헤더까지 통째로 생략한다 */}
        {citationSources.length > 0 && (
          <>
            <div
              style={{ display: "flex", alignItems: "center", marginBottom: 16 }}
            >
              <SectionBar />
              <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
                출처 / 인용 목록
              </div>
            </div>

            <table style={{ width: "100%", borderCollapse: "collapse" as const }}>
              <thead>
                <tr style={{ background: BG_ALT }}>
                  <th
                    style={{
                      padding: "7px 12px",
                      textAlign: "left" as const,
                      fontSize: 11,
                      fontWeight: 700,
                      color: MUTED,
                      borderBottom: `1px solid ${BORDER}`,
                    }}
                  >
                    파일명
                  </th>
                  <th
                    style={{
                      padding: "7px 12px",
                      textAlign: "left" as const,
                      fontSize: 11,
                      fontWeight: 700,
                      color: MUTED,
                      borderBottom: `1px solid ${BORDER}`,
                      width: 110,
                    }}
                  >
                    발행일자
                  </th>
                </tr>
              </thead>
              <tbody>
                {citationSources.map((src, i) => (
                  <tr
                    key={src.title}
                    style={{
                      borderBottom: `1px solid ${BORDER}`,
                      background: i % 2 === 0 ? "white" : BG_ALT,
                    }}
                  >
                    <td
                      style={{
                        padding: "8px 12px",
                        fontSize: 11,
                        color: TEXT,
                        fontWeight: 600,
                      }}
                    >
                      {src.title}
                    </td>
                    <td style={{ padding: "8px 12px", fontSize: 11, color: MUTED }}>
                      {src.date}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <PageFooter page={7} total={7} />
    </div>
  );
}

// ── 페이지 5·6: S.ymphony 리스크 리포트 ─────────────────────────
//
// "자세히" 화면(components/dashboard/ReportDetailModal)이 보여 주는 내용을
// 그대로 싣는다. PB 리포트는 근거·검증·재현성까지 남기는 문서라 전부 넣는다.
// 값의 출처는 lib/mock/symphonyReport.ts 하나이며 여기서 계산하지 않는다.

const RTH: React.CSSProperties = {
  padding: "7px 10px",
  textAlign: "left",
  fontSize: 10.5,
  fontWeight: 700,
  color: MUTED,
  background: BG_ALT,
  borderBottom: `1px solid ${BORDER}`,
};
const RTD: React.CSSProperties = {
  padding: "7px 10px",
  fontSize: 10.5,
  fontWeight: 600,
  color: TEXT,
  borderBottom: `1px solid ${BORDER}`,
};

function ReportSection({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 9 }}>
        <SectionBar />
        <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>{title}</div>
      </div>
      {children}
      {note && (
        <p style={{ margin: "7px 0 0", fontSize: 10, color: MUTED, lineHeight: 1.6 }}>
          {note}
        </p>
      )}
    </div>
  );
}

function RiskReportPage() {
  const contributionTotal = CVAR_CONTRIBUTIONS.reduce(
    (acc, r) => acc + r.weightPct,
    0,
  );
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="⑤"
        title="S.ymphony 리스크 리포트"
        subtitle={`IPS 충돌 검사 · VaR/CVaR · 손실 기여도 · 기준일 ${REPORT_AS_OF}`}
      />

      <div style={{ padding: "22px 40px 80px", wordBreak: "keep-all" }}>
        <ReportSection
          title={`IPS 충돌 검사 ${IPS_CONFLICTS.length}건`}
          note={IPS_CONFLICT_NOTE}
        >
          {IPS_CONFLICTS.map((c) => (
            <div
              key={c.rule}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 8,
                padding: "9px 11px",
                marginBottom: 7,
                background: BG_ALT,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  marginBottom: 3,
                }}
              >
                <span
                  style={{
                    fontSize: 9,
                    fontWeight: 800,
                    color: "#92400E",
                    background: "#FEF3C7",
                    padding: "2px 6px",
                    borderRadius: 4,
                  }}
                >
                  {c.severity.toUpperCase()}
                </span>
                <span style={{ fontSize: 11.5, fontWeight: 800, color: TEXT }}>
                  {c.message}
                </span>
                <span style={{ fontSize: 9, color: MUTED }}>{c.rule}</span>
              </div>
              <div style={{ fontSize: 10.5, color: TEXT, marginBottom: 2 }}>
                관측값 {c.observed} · 기준값 {c.threshold}
              </div>
              <div style={{ fontSize: 10, color: MUTED }}>{c.basis}</div>
            </div>
          ))}
        </ReportSection>

        <ReportSection
          title={`VaR / CVaR 신뢰수준 ${REPORT_META.confidenceLevelPct}% · ${formatWon(REPORT_META.totalValuationKrw)} 기준`}
        >
          <table
            style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}
          >
            <colgroup>
              <col style={{ width: 130 }} />
              <col />
              <col />
              <col style={{ width: 165 }} />
            </colgroup>
            <thead>
              <tr>
                <th style={RTH}>지표</th>
                <th style={{ ...RTH, textAlign: "right" }}>비율</th>
                <th style={{ ...RTH, textAlign: "right" }}>금액</th>
                <th style={{ ...RTH, textAlign: "right" }}>90% 신뢰구간</th>
              </tr>
            </thead>
            <tbody>
              {RISK_METRICS.map((m) => (
                <tr key={m.label}>
                  <td style={{ ...RTD, fontWeight: 800 }}>{m.label}</td>
                  <td style={{ ...RTD, textAlign: "right" }}>
                    {m.ratioPct.toFixed(2)}%
                  </td>
                  <td style={{ ...RTD, textAlign: "right", color: BRAND }}>
                    -{formatWon(m.amountKrw)}
                  </td>
                  <td style={{ ...RTD, textAlign: "right", color: MUTED }}>
                    {m.ciPct[0].toFixed(2)}% ~ {m.ciPct[1].toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>

        <ReportSection
          title={`CVaR 자산군 기여도 합계 ${contributionTotal.toFixed(1)}%`}
          note={CVAR_CONTRIBUTION_NOTE}
        >
          <table
            style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}
          >
            <tbody>
              {CVAR_CONTRIBUTIONS.map((r) => (
                <tr key={r.label}>
                  <td style={{ ...RTD, fontWeight: 700 }}>{r.label}</td>
                  <td style={{ ...RTD, textAlign: "right" }}>
                    {r.weightPct.toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>
      </div>

      <PageFooter page={5} total={7} />
    </div>
  );
}

function EvidencePage() {
  const passed = VERIFICATIONS.filter((v) => v.passed).length;
  return (
    <div
      data-pdf-page=""
      style={{
        width: W,
        height: H,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <PageHeader
        pageNum="⑥"
        title="근거 · 검증 · 재현성"
        subtitle={`인용 ${CITATIONS.length}건 · 검증 ${passed}/${VERIFICATIONS.length} 통과 · 엔진 ${REPORT_META.engineVersion}`}
      />

      <div style={{ padding: "22px 40px 80px", wordBreak: "keep-all" }}>
        <ReportSection title={`인용·출처 ${CITATIONS.length}건`}>
          <table
            style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}
          >
            <colgroup>
              <col style={{ width: 26 }} />
              <col />
              <col style={{ width: 175 }} />
            </colgroup>
            <thead>
              <tr>
                <th style={RTH}>#</th>
                <th style={RTH}>출처</th>
                <th style={RTH}>인용 위치</th>
              </tr>
            </thead>
            <tbody>
              {CITATIONS.map((c) => (
                <tr key={c.no}>
                  <td style={{ ...RTD, color: MUTED }}>{c.no}</td>
                  <td style={RTD}>{c.source}</td>
                  <td style={{ ...RTD, color: MUTED }}>{c.locator}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>

        <ReportSection
          title={`검증 항목 ${passed}/${VERIFICATIONS.length} 통과`}
          note={VERIFICATION_NOTE}
        >
          <table
            style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}
          >
            <colgroup>
              <col style={{ width: 62 }} />
              <col />
            </colgroup>
            <tbody>
              {VERIFICATIONS.map((v) => (
                <tr key={v.label}>
                  <td
                    style={{
                      ...RTD,
                      fontWeight: 800,
                      color: v.passed ? BRAND : UP,
                    }}
                  >
                    {v.passed ? "통과" : "미통과"}
                  </td>
                  <td style={RTD}>{v.label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>

        <ReportSection title="재현성 해시" note={REPRODUCIBILITY_NOTE}>
          <table
            style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}
          >
            <colgroup>
              <col style={{ width: 140 }} />
              <col />
            </colgroup>
            <tbody>
              {REPRODUCIBILITY_HASHES.map((h) => (
                <tr key={h.label}>
                  <td style={{ ...RTD, fontWeight: 700 }}>{h.label}</td>
                  <td
                    style={{
                      ...RTD,
                      fontFamily: "monospace",
                      fontSize: 9,
                      color: MUTED,
                      wordBreak: "break-all",
                    }}
                  >
                    {h.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReportSection>

        <ReportSection title="면책">
          {DISCLAIMERS.map((d) => (
            <p
              key={d.code}
              style={{ margin: "0 0 5px", fontSize: 10, color: MUTED, lineHeight: 1.7 }}
            >
              · {d.text}
            </p>
          ))}
        </ReportSection>
      </div>

      <PageFooter page={6} total={7} />
    </div>
  );
}

// ── 메인 ────────────────────────────────────────────────────────
export default function PbPdfTemplate() {
  return (
    <div>
      <CoverPage />
      <MarketIpsPage />
      <PortfolioPage />
      <TaxPage />
      <RiskReportPage />
      <EvidencePage />
      <AiPage />
    </div>
  );
}
