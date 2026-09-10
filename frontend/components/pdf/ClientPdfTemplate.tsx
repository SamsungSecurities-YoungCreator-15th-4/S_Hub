/**
 * 고객용 PDF 템플릿 — A4 세로(794×1123px) 고정, 5페이지.
 * 구조: 표지 → 시장&IPS → 포트폴리오 비교&지표 → 절세&계좌 → 위험 점검
 */

import {
  STRESS_SCENARIOS,
  formatKrwLoss,
  runStress,
} from "@/lib/stressScenarios";
import { DISCLAIMERS } from "@/lib/mock/symphonyReport";
import { evaluateIpsConflicts } from "@/lib/ipsConflicts";
import { useSymphonySubject } from "@/lib/symphonySubject";
import { useDashboardStore } from "@/lib/store";
import { deriveTaxFlowRows, useTaxFlow, useTaxPlan } from "@/lib/taxPlan";
import { deriveAdviceCards } from "@/lib/taxAdviceCards";
import { useViewedPortfolio } from "@/lib/viewedPortfolio";
import { formatSharpe } from "@/lib/sharpe";
import {
  buildPdfAllocation,
  buildPdfMacroCell,
} from "@/lib/pdfPortfolioData";
import {
  buildPdfTaxEffect,
  pdfTaxEffectFromDerived,
  extractTaxOptimizerEntry,
  buildPdfTaxFlow,
  pdfTaxFlowFromDerived,
  extractPortfolioTaxEntry,
} from "@/lib/pdfTaxData";

/** 현재 대시보드에서 선택된 고객(없으면 첫 고객)을 store 에서 읽는다. */
function useSelectedCustomer() {
  const customers = useDashboardStore((s) => s.customers);
  const selectedCustomerId = useDashboardStore((s) => s.selectedCustomerId);
  return customers.find((c) => c.id === selectedCustomerId) ?? customers[0];
}

// 절세 계좌 배치 — 한도 폴백값(백엔드·프론트 계산이 없을 때만 쓴다)
// 출처: 조세특례제한법 §91의18(ISA), 소득세법 §59의3(연금·IRP)
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


const BRAND = "#0050D6";
const BRAND_DARK = "#1A4BAF";
const BRAND_LIGHT = "#EFF4FF";
const BRAND_MID = "#DBEAFE";
const UP = "#F04452";
const TEXT = "#111827";
const MUTED = "#6B7280";
const BORDER = "#E5E7EB";
const BG_ALT = "#FAFAFA";

const getTodayShort = () =>
  new Date()
    .toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    })
    .replace(/\. /g, ".")
    .replace(/\.$/, "");

const getNow = () => {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

// ── 공통 헬퍼 ──────────────────────────────────────────────────

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
        <span style={{ fontSize: 10, color: MUTED }}>고객 안내 자료</span>
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
        <span style={{ fontSize: 10, color: MUTED }}>{getTodayShort()}</span>
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

// ── Page 1: 표지 ────────────────────────────────────────────────

function CoverPage() {
  const C = useSelectedCustomer();
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  const storePortfolios = useDashboardStore((s) => s.portfolios);
  /*
   * 표지의 "예상 연간 절세" 도 본문과 같은 계산을 따른다 — 표지만 mock 상수를
   * 인쇄하면 같은 문서 안에서 두 숫자가 갈린다.
   */
  const coverFlow = useTaxFlow();
  const taxEffect = pdfTaxEffectFromDerived(
    buildPdfTaxEffect(
      extractTaxOptimizerEntry(
        useDashboardStore((s) => s.taxOptimizer),
        selectedPortfolioId,
      ),
    ),
    coverFlow ? deriveTaxFlowRows(coverFlow) : null,
    coverFlow,
  );
  /*
    표지의 "선택 포트폴리오"도 확정 대상을 따른다 — 본문은 조정안인데 표지만
    조정 전 제안 이름이면 같은 문서 안에서 두 안을 가리키게 된다.
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
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 상단 그라디언트 배너 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 420,
          background:
            "linear-gradient(135deg, #1A4BAF 0%, #0050D6 55%, #2C7BFF 100%)",
        }}
      />

      {/* 물결 곡선 장식 */}
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

      {/* 배너 내용 */}
      <div style={{ position: "relative", padding: "44px 52px 0" }}>
        {/* 로고 영역 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 32,
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.png"
            alt=""
            style={{
              width: 36,
              height: 36,
              borderRadius: 9,
              objectFit: "cover",
            }}
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

        {/* 부제 */}
        <div
          style={{
            fontSize: 13,
            color: "rgba(255,255,255,0.85)",
            marginBottom: 60,
            fontWeight: 500,
          }}
        >
          고객님의 소중한 자산을 위한 맞춤형 포트폴리오 분석 보고서입니다.
        </div>

        {/* 메인 타이틀 */}
        <div
          style={{
            fontSize: 44,
            fontWeight: 900,
            color: "white",
            lineHeight: 1.2,
            marginBottom: 8,
          }}
        >
          투자 포트폴리오
          <br />
          분석 보고서
        </div>
      </div>

      {/* 흰색 영역 콘텐츠 */}
      <div style={{ position: "relative", padding: "72px 52px 0" }}>
        {/* 고객 카드 */}
        <div
          style={{
            background: BRAND_LIGHT,
            border: `1px solid ${BRAND_MID}`,
            borderRadius: 14,
            padding: "24px 28px",
            marginBottom: 60,
            marginTop: 90,
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
            PREPARED FOR
          </div>
          <div
            style={{
              fontSize: 34,
              fontWeight: 700,
              color: TEXT,
              marginBottom: 6,
            }}
          >
            {C.name} 고객님
          </div>
          <div style={{ fontSize: 12, color: MUTED, fontWeight: 500 }}>
            {C.aumLabel} · {C.pbCode}
          </div>
        </div>

        {/* 요약 스탯 행 */}
        <div style={{ display: "flex" }}>
          {[
            { label: "보고서 일자", value: getTodayShort() },
            { label: "기준 시각", value: `${getNow()} 기준` },
            { label: "선택 포트폴리오", value: selectedPortfolioName },
            {
              label: taxEffect.headlineLabel ?? "예상 연간 절세",
              value: `+${taxEffect.annualSavingManwon.toLocaleString()}만원`,
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

      {/* 면책 고지 — 페이지 하단 절대 위치 */}
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
        <p style={{ fontSize: 12, color: MUTED, lineHeight: 1.7, margin: 0 }}>
          본 보고서는 상담 내용, 고객 IPS, 시장 데이터 및 AI 분석 결과를
          바탕으로 고객의 투자 목적과 제약조건을 정리하고, 이에 적합한
          포트폴리오 방향을 제안하기 위해 작성되었습니다. 본 자료는 PB 상담을
          보조하기 위한 참고자료이며, 최종 투자 판단은 고객의 투자 목적, 위험
          선호도, 세무·법률 상황을 종합적으로 고려하여 결정되어야 합니다.
        </p>
      </div>
    </div>
  );
}

// ── Page 2: 시장 환경 & IPS ─────────────────────────────────────

// 거시지표 한국어 설명
const MACRO_DESC: Record<
  string,
  { name: string; dir: string; explain: string }
> = {
  기준금리: {
    name: "기준금리",
    dir: "인하",
    explain: "금리가 내리면 채권 가격은 올라가는 경향이 있어요",
  },
  "미 10Y": {
    name: "미국 장기금리",
    dir: "하락",
    explain: "미국 채권 금리. 해외 투자 수익에 영향을 줍니다",
  },
  "원/달러": {
    name: "원/달러 환율",
    dir: "상승",
    explain: "환율 상승 시 해외 자산 원화 환산 가치가 높아져요",
  },
  KOSPI: {
    name: "국내 주식 (KOSPI)",
    dir: "상승",
    explain: "국내 대형주 호름. 국내 주식 비중에 영향을 줍니다",
  },
  "S&P500": {
    name: "미국 주식 (S&P500)",
    dir: "상승",
    explain: "미국 대표 지수. 해외성장주·배당주 투자의 핵심 지표입니다",
  },
  CPI: {
    name: "미국 CPI",
    dir: "하락",
    explain: "소비자물가 지수. 금리 방향 결정의 핵심 지표입니다",
  },
};

function MarketIpsPage() {
  const customer = useSelectedCustomer();
  const ips = useDashboardStore((s) => s.ips);
  // 상단바와 동일한 실시간 시장 지표(store). 미로드 시엔 목 기준값으로 초기화돼 있다.
  const macroIndicators = useDashboardStore((s) => s.macroIndicators);
  const IPS_ITEMS = [
    {
      tag: "Goal",
      label: "투자 목적",
      value: ips.goal,
      sub: "투자 목적과 기간을 고려한 맞춤 전략을 수립합니다",
      show: !!ips.goal?.trim(),
    },
    {
      tag: "Asset",
      label: "운용 자산",
      value: customer.aumLabel,
      sub: "전체 운용 가능 자산 기준",
      show: true,
    },
    {
      tag: "Return",
      label: "목표 수익률",
      value: `연 ${ips.returnPct}%\n(세후 기준)`,
      sub: "변동성 최소화하면서 세후 목표 수익률 달성",
      show: true,
    },
    {
      tag: "Risk",
      label: "위험 성향",
      value: ips.risk,
      sub: "급격한 손실(MDD -15% 이내)을 허용하지 않는 안정적 운용 선호",
      show: true,
    },
    {
      tag: "Time",
      label: "투자 기간",
      value: `${ips.timeYears}년`,
      sub: "장기 운용 기준이나 유동성 필요 시 단기 자금은 별도 운용",
      show: true,
    },
    {
      tag: "Tax",
      label: "세금 상황",
      value: ips.tax,
      sub: "절세 계좌(ISA·연금저축·IRP) 적극 활용 권장",
      show: !!ips.tax?.trim(),
    },
    {
      tag: "Liquidity",
      label: "유동성 필요",
      value: ips.liquidity,
      sub: "단기 필요자금은 IPS Unique 에 기재된 금액·시점 기준",
      show: true,
    },
    {
      tag: "Legal",
      label: "법적 제약",
      value: ips.legal,
      sub: "IPS Legal 에 기재된 제약 기준",
      show: !!ips.legal?.trim(),
    },
    {
      tag: "Unique",
      label: "특별 사항",
      value: ips.unique,
      sub: "",
      show: !!ips.unique?.trim(),
    },
  ].filter((item) => item.show);

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 페이지 헤더 바 */}
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
            ① 지금의 시장 환경과 나의 투자 목표
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            시장 현황 쉽게 이해하기 · 내 투자 방향 확인하기
          </div>
        </div>
      </div>

      <div style={{ padding: "28px 40px 80px", wordBreak: "keep-all" }}>
        {/* 섹션 1: 시장 현황 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            지금 시장은 어떤 상황인가요?
          </div>
        </div>

        {/* 대시보드 동일 — 한 줄 콤팩트 스트립 */}
        <div
          style={{
            display: "flex",
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            overflow: "hidden",
            marginBottom: 28,
          }}
        >
          {macroIndicators.map((m, idx) => {
            const desc = MACRO_DESC[m.label];
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
                  {desc?.name ?? m.label}
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
                  {cell.arrow ? `${cell.arrow} ` : ""}
                  {cell.changeText}
                </div>
              </div>
            );
          })}
        </div>

        {/* 섹션 2: IPS */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            나의 투자 목표 요약 (IPS)
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: 10,
            marginBottom: 16,
          }}
        >
          {IPS_ITEMS.map((item) => (
            <div
              key={item.label}
              style={{
                background: "white",
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "12px 14px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginBottom: 6,
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 800,
                    background: BRAND,
                    color: "white",
                    borderRadius: 4,
                    padding: "2px 6px",
                    letterSpacing: 0.5,
                  }}
                >
                  {item.tag}
                </span>
                <span style={{ fontSize: 11, color: MUTED, fontWeight: 600 }}>
                  {item.label}
                </span>
              </div>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 900,
                  color: TEXT,
                  lineHeight: 1.3,
                  whiteSpace: "pre-line",
                  wordBreak: "keep-all",
                }}
              >
                {item.value}
              </div>
            </div>
          ))}
        </div>
      </div>

      <PageFooter page={2} total={5} />
    </div>
  );
}

// ── Page 3: 포트폴리오 비교 & 지표 설명 ───────────────────────────

const METRIC_CARDS = [
  {
    num: "①",
    title: "기대수익률",
    en: "Expected Return",
    body: "1년 동안 예상되는 평균 수익의 비율입니다. 높을수록 더 많은 이익을 기대할 수 있습니다.",
    example: "6.4%라면 1억원 투자 시 연 640만원 기대",
  },
  {
    num: "②",
    title: "변동성 (표준편차)",
    en: "Volatility / Std. Dev.",
    body: "수익률이 평균에서 얼마나 흔들리는지를 나타냅니다. 낮을수록 안정적인 투자입니다.",
    example: "12.5%라면 평균 수익에서 ±12.5% 오내릴 수 있음",
  },
  {
    num: "③",
    title: "샤프 지수",
    en: "Sharpe Ratio",
    body: "위험 한 단위당 얼마나 수익을 얻는지 나타냅니다. 높을수록 효율적인 포트폴리오입니다.",
    example: "0.61은 0.43보다 좋음: 같은 위험으로 더 많이 버는 구조",
  },
  {
    num: "④",
    title: "소르티노 지수",
    en: "Sortino Ratio",
    body: "하락 위험(손실이 나는 변동)만을 기준으로 한 효율성 지표입니다. 높을수록 손실 방어력이 좋습니다.",
    example: "샤프와 달리 하락만 위험으로 봄: 손실 방어력 측정",
  },
  {
    num: "⑤",
    title: "최대낙폭 (MDD)",
    en: "Maximum Drawdown",
    body: "투자 기간 중 고점 대비 가장 많이 떨어진 최대 손실 폭입니다. 낮을수록 안전합니다.",
    example: "-11.2%라면 보유 자산의 11.2%까지 평가손실이 났던 구간이 있었다는 뜻",
  },
  {
    num: "⑥",
    title: "세후 수익률",
    en: "After-Tax Return",
    body: "세금을 납부한 후 실제 고객님 손에 남는 수익률입니다. 종합과세 고려 시 이 수치가 핵심입니다.",
    example: "5.5% = 세금 납부 후 실수령 수익률 (절세 효과 포함)",
  },
];

function PortfolioPage() {
  // 훅은 early return 앞에서 호출(react-hooks/rules-of-hooks).
  const storePortfolios = useDashboardStore((s) => s.portfolios);
  const C = useSelectedCustomer();
  const portCurrent = storePortfolios.find((p) => p.id === "current");
  /*
    고객 문서에는 확정 대상인 안 하나만 싣는다. 조정했으면 조정안이다 —
    상담에서 함께 손본 비중과 다른 문서를 건네지 않기 위해서다.
  */
  const { viewed: selectedPf } = useViewedPortfolio();
  if (!portCurrent || !selectedPf) return null;
  const cur = portCurrent.metrics;
  const sel = selectedPf.metrics;
  const assetLabelsSelected = buildPdfAllocation(selectedPf).map(
    (s) => `${s.label} ${Math.round(s.weight)}%`,
  );
  // 선택 포트폴리오의 현재 대비 연간 세후수익 개선액(만원).
  const afterTaxImproveManwon = Math.round(
    (((sel.afterTaxReturnPct ?? 0) - (cur.afterTaxReturnPct ?? 0)) / 100) *
      (C?.aumEokwon ?? 0) *
      10000,
  );

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* 페이지 헤더 바 */}
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
            ② 포트폴리오 비교 &amp; 주요 지표 쉽게 이해하기
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            현재 vs 고객 선택 포트폴리오 · 6가지 핵심 지표 설명
          </div>
        </div>
      </div>

      <div style={{ padding: "24px 40px 80px", wordBreak: "keep-all" }}>
        {/* 섹션 1: 성과 비교 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            포트폴리오별 성과 한눈에 보기 (5년 분석 기준)
          </div>
        </div>

        {/* 현재 포트폴리오 */}
        <div
          style={{
            border: `1px solid ${BORDER}`,
            borderRadius: 10,
            padding: "16px 20px",
            marginBottom: 14,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
              현재 포트폴리오
            </div>
            <div style={{ fontSize: 10, color: MUTED }}>현재 구성 기준</div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(6, 1fr)",
              gap: 8,
            }}
          >
            {[
              {
                label: "기대수익률",
                value: `연 ${cur.expectedReturnPct}%`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "샤프지수",
                value: formatSharpe(cur.sharpe),
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "소르티노",
                value: cur.sortino != null ? `${cur.sortino}` : "-",
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "세후수익률",
                value: `${cur.afterTaxReturnPct !== 0 ? "▲" : ""}${cur.afterTaxReturnPct}%`,
                color: UP,
                sub: cur.afterTaxAmountLabel ?? null,
                subColor: UP,
              },
              {
                label: "변동성",
                value: `${cur.volatilityPct}%`,
                color: TEXT,
                sub: cur.volatilityAmountLabel ?? null,
                subColor: MUTED,
              },
              {
                label: "MDD",
                value: `${cur.mddPct !== 0 ? "▼" : ""}${cur.mddPct}%`,
                color: BRAND,
                sub: cur.mddAmountLabel ?? null,
                subColor: BRAND,
              },
            ].map((s) => (
              <div key={s.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, color: MUTED, marginBottom: 4 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 15, fontWeight: 900, color: s.color }}>
                  {s.value}
                </div>
                {s.sub && (
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: s.subColor,
                      marginTop: 2,
                    }}
                  >
                    {s.sub}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 제안 포트폴리오 */}
        <div
          style={{
            border: `1.5px solid ${BRAND}`,
            borderRadius: 10,
            padding: "16px 20px",
            background: "white",
            marginBottom: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 800, color: BRAND }}>
              {selectedPf.name}
            </div>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(6, 1fr)",
              gap: 8,
              marginBottom: 10,
            }}
          >
            {[
              {
                label: "기대수익률",
                value: `연 ${sel.expectedReturnPct}%`,
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "샤프지수",
                value: formatSharpe(sel.sharpe),
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "소르티노",
                value: sel.sortino != null ? `${sel.sortino}` : "-",
                color: TEXT,
                sub: null,
                subColor: MUTED,
              },
              {
                label: "세후수익률",
                value: `${sel.afterTaxReturnPct !== 0 ? "▲" : ""}${sel.afterTaxReturnPct}%`,
                color: UP,
                sub: sel.afterTaxAmountLabel ?? null,
                subColor: UP,
              },
              {
                label: "변동성",
                value: `${sel.volatilityPct}%`,
                color: TEXT,
                sub: sel.volatilityAmountLabel ?? null,
                subColor: MUTED,
              },
              {
                label: "MDD",
                value: `${sel.mddPct !== 0 ? "▼" : ""}${sel.mddPct}%`,
                color: BRAND,
                sub: sel.mddAmountLabel ?? null,
                subColor: BRAND,
              },
            ].map((s) => (
              <div key={s.label} style={{ textAlign: "center" }}>
                <div style={{ fontSize: 10, color: MUTED, marginBottom: 4 }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 15, fontWeight: 900, color: s.color }}>
                  {s.value}
                </div>
                {s.sub && (
                  <div
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      color: s.subColor,
                      marginTop: 2,
                    }}
                  >
                    {s.sub}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* 자산 배분 태그 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              flexWrap: "wrap",
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 700, color: MUTED }}>
              자산 배분 구성
            </span>
            {assetLabelsSelected.map((t: string) => (
              <span
                key={t}
                style={{
                  fontSize: 10,
                  background: "white",
                  border: `1px solid ${BRAND_MID}`,
                  color: BRAND,
                  borderRadius: 5,
                  padding: "2px 7px",
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}
              >
                {t}
              </span>
            ))}
          </div>
        </div>

        {/* 개선 인사이트 한 줄 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 14px",
            marginBottom: 48,
            background: "#F9FAFB",
            borderLeft: `3px solid ${BRAND}`,
            borderRadius: "0 6px 6px 0",
          }}
        >
          <span style={{ fontSize: 11, color: MUTED }}>
            {selectedPf.name} 선택 시 현재 대비 연간 세후수익
          </span>
          <span style={{ fontSize: 13, fontWeight: 800, color: BRAND }}>
            {afterTaxImproveManwon >= 0 ? "+" : ""}
            {afterTaxImproveManwon.toLocaleString()}만원 개선
          </span>
          <span style={{ fontSize: 10, color: MUTED }}>예상됩니다.</span>
        </div>

        {/* 섹션 2: 지표 설명 */}
        <div
          style={{ display: "flex", alignItems: "center", marginBottom: 28 }}
        >
          <SectionBar />
          <div style={{ fontSize: 14, fontWeight: 800, color: TEXT }}>
            핵심 투자 지표 6가지
          </div>
        </div>

        <div
          style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}
        >
          {METRIC_CARDS.map((c) => (
            <div
              key={c.title}
              style={{
                border: `1px solid ${BORDER}`,
                borderRadius: 10,
                padding: "14px 16px",
                background: "white",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                <span style={{ fontSize: 13, fontWeight: 800, color: TEXT }}>
                  {c.title}
                </span>
              </div>
              <p
                style={{
                  fontSize: 11,
                  color: TEXT,
                  lineHeight: 1.6,
                  margin: "0 0 8px",
                }}
              >
                {c.body}
              </p>
            </div>
          ))}
        </div>
      </div>

      <PageFooter page={3} total={5} />
    </div>
  );
}

// ── Page 4: 절세 최적화 전략 (PB용 동일) ────────────────────────

function TaxPage() {
  const C = useSelectedCustomer();
  const taxOptimizerMap = useDashboardStore((s) => s.taxOptimizer);
  const selectedPortfolioId = useDashboardStore((s) => s.selectedPortfolioId);
  // 절세 계좌 배치 바는 확정 대상인 안의 자산배분을 따른다(조정했으면 조정안).
  const { viewed: selectedPf } = useViewedPortfolio();
  const selectedAllocSlices = selectedPf ? buildPdfAllocation(selectedPf) : [];
  const taxOptimizerEntry = extractTaxOptimizerEntry(
    taxOptimizerMap,
    selectedPortfolioId,
  );
  const taxEffectBase = buildPdfTaxEffect(taxOptimizerEntry);
  /*
   * 카드와 총액은 화면(절세 제안 탭)과 같은 함수를 부른다. 예전에는 리포트만
   * mockData 를 읽어, 화면이 "약 +97만원" 을 말할 때 여기에는 자리표시 문구인
   * "분석 후 계산" 이 인쇄됐다.
   */
  const { plan, customer: taxCustomer } = useTaxPlan();
  const taxAdvice = deriveAdviceCards(
    plan,
    taxOptimizerEntry?.strategy_cards?.cards ?? null,
  );
  const portfolioTaxMap = useDashboardStore((s) => s.portfolioTax);
  const aumEokwon = C.aumEokwon ?? 0;
  const portfolioTaxEntry = extractPortfolioTaxEntry(
    portfolioTaxMap,
    selectedPortfolioId,
  );
  /*
   * 백엔드 흐름이 없으면 화면과 같은 프론트 계산으로 채운다. 예전에는 여기서
   * null 이 되어 표가 통째로 "분석 후 확인할 수 있습니다" 로 비었는데, 데모
   * 픽스처에는 portfolioTax·taxOptimizer 가 없어 시연에서는 늘 그 상태였다.
   */
  const frontFlow = useTaxFlow();
  const derivedFlow = frontFlow ? deriveTaxFlowRows(frontFlow) : null;
  const taxFlow =
    buildPdfTaxFlow(taxOptimizerEntry, aumEokwon, portfolioTaxEntry) ??
    pdfTaxFlowFromDerived(derivedFlow);
  /*
   * 머리 배너·세후수익률·실효세도 같은 계산에서 가져온다. 예전에는 이 셋만 mock
   * 상수로 남아, 같은 페이지의 비교표가 240만 → 252만 을 말하는데 요약은
   * "1,620 → 540만(-66.7%)" 을, 배너는 "+1,080만원" 을 인쇄했다.
   */
  const taxEffect = pdfTaxEffectFromDerived(
    taxEffectBase,
    derivedFlow,
    frontFlow,
  );
  /*
   * 사용액이 없을 때 한도의 45% 를 채워 그리고 있었다. 어느 고객이든 막대가 절반쯤
   * 차 보이는데 그 숫자는 아무 데서도 나오지 않은 값이다. 고객 레코드의 기납입액을
   * 쓴다 — 화면의 계좌 배치 막대가 읽는 값과 같다.
   *
   * 캡션의 공제율·환급액도 배분 계산에서 가져온다. 문구에 박아 두면 총급여 5,500만원을
   * 넘는 고객(13.2%)에게도 16.5% 라고 인쇄된다.
   */
  /*
   * 계좌 배치 막대. 화면(AccountAllocation)과 같은 모델을 쓴다.
   *
   * 두 계좌의 한도는 성격이 다르다 — ISA 는 조특법 §91의18 ③5 의 누적 한도라
   * 미사용분이 해마다 쌓이고, 연금은 소득세법 §59의3 의 그 해 세액공제 한도다.
   * 예전에는 둘을 0~2,000만원 한 축에 그려, 이월분이 쌓인 고객이 "한도 소진"
   * 으로 보였다.
   *
   * mock 의 accounts 에도 used 가 들어 있어(ISA 2,000 · 연금 900) 그대로 두면
   * 어느 고객이든 꽉 채워 쓴 것으로 그려진다. 백엔드 응답이 있을 때만 그 값을
   * 쓰고, 없으면 고객 레코드의 기납입액을 쓴다.
   */
  const accountRows = ACCOUNT_PDF.filter((acct) => acct.key !== "general").map(
    (acct) => {
      const accData = taxEffect.accounts.find((a) => a.name === acct.name);
      const isIsa = acct.key === "isa";
      const fallbackUsed = isIsa
        ? (taxCustomer?.isaUsedManwon ?? 0)
        : (taxCustomer?.pensionUsedManwon ?? 0);
      const used = taxOptimizerEntry
        ? (accData?.used ?? fallbackUsed)
        : fallbackUsed;
      // 누적 한도 = 이미 넣은 돈 + 아직 넣을 수 있는 돈. 산식은 lib/taxAccounts.ts.
      const limitManwon =
        isIsa && plan ? used + plan.isa.headroomManwon : acct.refManwon;
      const isaYears = taxCustomer?.isaYearsSinceOpen;
      const basis = isIsa
        ? isaYears != null && isaYears > 0
          ? `ISA 는 가입 ${isaYears + 1}년차 누적 한도`
          : "ISA 는 누적 한도"
        : "올해";
      const caption = !plan
        ? acct.caption
        : isIsa
          ? `비과세 ${plan.isaType.taxFreeManwon}만원(${plan.isaType.type === "seogmin" ? "서민형" : "일반형"}) · 초과분 9.9% 분리과세`
          : `세액공제 ${(plan.pensionRate * 100).toFixed(1)}% → 환급 ${plan.pensionSavingManwon.toLocaleString()}만`;
      return { ...acct, used, limitManwon, basis, caption };
    },
  );

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
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
            ③ 절세 최적화 전략
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            세금 효과 시뮬레이터 · 절세 계좌 배치도 · 절세 제안
          </div>
        </div>
      </div>

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
              {taxEffect.headlineLabel ?? "연간 절세 효과"} (
              {selectedPf?.name ?? "안정 추구"} 기준 ·{" "}
              {C.aumLabel})
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
                  {/*
                    이 칸에 들어가는 값은 그 해에 내는 세금이지 절감액이 아니다.
                    "절세액 240만" 은 240만원을 아꼈다는 말로 읽힌다.
                  */}
                  {["구분", "세후 수익", "금융소득세", "비고"].map((h) => (
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
                  taxFlow.rows.map((row) => (
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
                        {row.note}
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
                {taxEffect.afterTaxReturn.to} ({taxEffect.afterTaxReturn.delta})
                <br />✓ 금융소득세 {taxEffect.effectiveTax.from} →{" "}
                {taxEffect.effectiveTax.to} ({taxEffect.effectiveTax.delta})
                {/*
                  화면 머리말과 같은 분해다. 총액만 적으면 절반이 다른 세목(근로
                  소득세 환급)이라는 사실이 묻히고, 전환으로 세금이 늘었다는 것도
                  이 줄에서만 보인다.
                */}
                {derivedFlow && (
                  <>
                    <br />✓ {taxFlow?.totalLabel} +
                    {derivedFlow.totalSavingManwon.toLocaleString()}만원: 금융소득
                    +{derivedFlow.breakdown.financialManwon.toLocaleString()}만 (세전
                    +{derivedFlow.breakdown.pretaxGainManwon.toLocaleString()} ·{" "}
                    {derivedFlow.breakdown.switchTaxManwon >= 0
                      ? "전환 세금 −"
                      : "전환 세금 절감 +"}
                    {Math.abs(
                      derivedFlow.breakdown.switchTaxManwon,
                    ).toLocaleString()}{" "}
                    · ISA 절감 +
                    {derivedFlow.breakdown.isaCutManwon.toLocaleString()}) · 근로소득세
                    환급 +{derivedFlow.breakdown.refundManwon.toLocaleString()}만
                  </>
                )}
              </div>
            </div>
          </div>

          {/* 절세 계좌 배치 최적화 */}
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
              {/*
                화면(계좌 배치 활용도)과 같은 모델이다. 두 계좌의 한도는 성격이
                달라(ISA 는 누적, 연금은 그 해 기준) 한 축에 놓을 수 없다. 각자
                자기 한도 대비 비율로 그리고 금액은 옆에 적는다.
              */}
              <div>
                {accountRows.map((acct, idx) => {
                  const pct =
                    acct.limitManwon > 0
                      ? (acct.used / acct.limitManwon) * 100
                      : 0;
                  const color = idx === 0 ? "#0064FF" : "#3D8BFF";
                  return (
                    <div
                      key={acct.name}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        marginBottom: idx < accountRows.length - 1 ? 12 : 0,
                      }}
                    >
                      <span
                        style={{
                          width: 68,
                          flexShrink: 0,
                          fontSize: 10,
                          fontWeight: 800,
                          color: "#4E5968",
                          textAlign: "right" as const,
                          lineHeight: 1.2,
                        }}
                      >
                        {acct.name}
                      </span>
                      <div
                        style={{
                          flex: 1,
                          height: 14,
                          margin: "0 8px",
                          background: "#E9EDF3",
                          borderRadius: 4,
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            width: `${Math.min(Math.max(pct, 0), 100)}%`,
                            height: "100%",
                            background: color,
                            borderRadius: 4,
                          }}
                        />
                      </div>
                      <span
                        style={{
                          flexShrink: 0,
                          fontSize: 9.5,
                          fontWeight: 600,
                          color: MUTED,
                          whiteSpace: "nowrap" as const,
                        }}
                      >
                        <b style={{ color: TEXT, fontWeight: 800 }}>
                          {acct.used.toLocaleString()}
                        </b>
                        {" / "}
                        {acct.limitManwon.toLocaleString()}만원
                        <b style={{ color, fontWeight: 800, marginLeft: 4 }}>
                          {pct.toFixed(0)}%
                        </b>
                      </span>
                    </div>
                  );
                })}
              </div>
              {/*
                8,000 과 900 이 같은 성격의 숫자로 읽히지 않게 한 줄로 밝힌다.
              */}
              <p
                style={{
                  margin: "10px 0 0 0",
                  fontSize: 9,
                  fontWeight: 600,
                  color: MUTED,
                  lineHeight: 1.5,
                }}
              >
                {accountRows[0]?.basis}: 미사용분이 해마다 쌓인다 · 연금은 올해
                세액공제 한도
              </p>
            </div>
          </div>
        </div>

        {/* 섹션 2: 절세 제안 */}
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
              <div style={{ fontSize: 10, color: "#9CA3AF", marginBottom: 5 }}>
                {card.tag}
              </div>
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

      <PageFooter page={4} total={5} />
    </div>
  );
}

// ── Page 5: 위험 점검 ────────────────────────────────────────────
//
// "자세히" 리포트에서 고객이 읽을 수 있는 것만 골라 싣는다.
//   스트레스 시나리오 — 화면 카드와 같은 runStress 로 계산해 숫자가 어긋나지 않는다
//   IPS 충돌 검사     — 무엇이 왜 걸리는지. 룰 ID·정책 파일명은 빼고 문장만 남긴다
//   면책             — 고객에게 나가는 문서라 필수다
//
// VaR·CVaR·손실 기여도·검증 항목·재현성 해시는 싣지 않는다. 설명 없이는 읽히지
// 않거나(VaR 99% 1일), 내부 품질 관리라 고객 문서에 들어갈 성격이 아니다.
// PB 리포트에는 전부 들어간다.

function RiskCheckPage() {
  const C = useSelectedCustomer();
  // 스트레스는 비중만 있으면 계산되므로 조정안 비중을 그대로 쓴다.
  const { viewed: selectedPf } = useViewedPortfolio();
  const { baselineWeights } = useSymphonySubject();
  if (!C || !selectedPf) return null;

  const totalKrw = (C.aumEokwon ?? 0) * 100_000_000;
  const rows = STRESS_SCENARIOS.map((sc) => ({
    label: sc.label,
    shock: sc.shockSummary,
    loss: runStress(selectedPf.weights, totalKrw, sc),
  }));
  /*
    확인 항목도 이 안을 기준으로 판정한다 — 스트레스는 옮겨 갈 안으로 재고
    확인 항목만 상담 전 비중으로 적으면 한 페이지가 두 포트폴리오를 말한다.
  */
  // 고객용 문서의 이 칸 제목이 "확인이 필요한 항목" 이라, 이 안에서 이미 풀린
  // 항목은 싣지 않는다. 해소 내역은 PB 용 리포트가 남긴다.
  const conflicts = evaluateIpsConflicts({
    weights: selectedPf.weights,
    baselineWeights,
    nearTermNeedManwon: C.nearTermNeedManwon ?? 0,
    nearTermNeedYears: C.nearTermNeedYears ?? null,
    nearTermNeedLabel: C.nearTermNeedLabel,
    totalKrw,
  }).filter((c) => c.status === "violation");

  return (
    <div
      data-pdf-page=""
      style={{
        width: 794,
        height: 1123,
        fontFamily: "Pretendard, Apple SD Gothic Neo, sans-serif",
        background: "white",
        position: "relative",
        overflow: "hidden",
      }}
    >
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
            ④ 위험 점검
          </div>
          <div
            style={{
              fontSize: 13,
              color: "rgba(255,255,255,0.75)",
              marginTop: 2,
            }}
          >
            과거 충격 국면에서의 손실 추정 · 확인이 필요한 항목
          </div>
        </div>
      </div>

      <div style={{ padding: "22px 40px 80px", wordBreak: "keep-all" }}>
        <div style={{ display: "flex", alignItems: "center", marginBottom: 10 }}>
          <SectionBar />
          <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
            이런 일이 다시 오면
          </div>
        </div>
        <p style={{ margin: "0 0 12px", fontSize: 11, color: MUTED, lineHeight: 1.7 }}>
          과거에 있었던 시장 충격을 참조해, {selectedPf.name} 구성이 같은 상황을
          만났을 때 줄어들 수 있는 금액입니다. 정밀한 재현이 아니라 방향과 크기를
          맞춘 대표 시나리오입니다.
        </p>

        <table
          style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}
        >
          <colgroup>
            <col style={{ width: 120 }} />
            <col />
            <col style={{ width: 200 }} />
          </colgroup>
          <thead>
            <tr>
              <th
                style={{
                  padding: "8px 10px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  background: BG_ALT,
                  borderBottom: `1px solid ${BORDER}`,
                }}
              >
                시나리오
              </th>
              <th
                style={{
                  padding: "8px 10px",
                  textAlign: "left",
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  background: BG_ALT,
                  borderBottom: `1px solid ${BORDER}`,
                }}
              >
                충격 가정
              </th>
              <th
                style={{
                  padding: "8px 10px",
                  textAlign: "right",
                  fontSize: 11,
                  fontWeight: 700,
                  color: MUTED,
                  background: BG_ALT,
                  borderBottom: `1px solid ${BORDER}`,
                }}
              >
                줄어들 수 있는 금액
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label}>
                <td
                  style={{
                    padding: "10px",
                    fontSize: 12,
                    fontWeight: 800,
                    color: TEXT,
                    borderBottom: `1px solid ${BORDER}`,
                  }}
                >
                  {r.label}
                </td>
                <td
                  style={{
                    padding: "10px",
                    fontSize: 10.5,
                    color: MUTED,
                    borderBottom: `1px solid ${BORDER}`,
                  }}
                >
                  {r.shock}
                </td>
                <td
                  style={{
                    padding: "10px",
                    textAlign: "right",
                    borderBottom: `1px solid ${BORDER}`,
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 900, color: BRAND }}>
                    &minus;{formatKrwLoss(r.loss.lossKrw)}
                  </div>
                  <div style={{ fontSize: 10, color: MUTED, marginTop: 2 }}>
                    &minus;{formatKrwLoss(r.loss.lossKrwLow)} ~ &minus;
                    {formatKrwLoss(r.loss.lossKrwHigh)}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            margin: "26px 0 10px",
          }}
        >
          <SectionBar />
          <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>
            확인이 필요한 항목
          </div>
        </div>

        {conflicts.map((c) => (
          <div
            key={c.rule}
            style={{
              border: `1px solid ${BORDER}`,
              borderRadius: 8,
              padding: "11px 13px",
              marginBottom: 8,
              background: BG_ALT,
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 800, color: TEXT, marginBottom: 3 }}>
              {c.message}
            </div>
            <div style={{ fontSize: 11, color: TEXT }}>
              {c.observed} · 기준 {c.threshold}
              {c.previousObserved ? ` (상담 전 ${c.previousObserved})` : ""}
            </div>
          </div>
        ))}
        <p style={{ margin: "6px 0 0", fontSize: 10.5, color: MUTED, lineHeight: 1.7 }}>
          위 항목은 투자를 막는 사유가 아니라, 담당 PB 와 함께 확인하고 조정할 지점입니다.
        </p>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            margin: "26px 0 10px",
          }}
        >
          <SectionBar />
          <div style={{ fontSize: 15, fontWeight: 800, color: TEXT }}>유의사항</div>
        </div>
        {DISCLAIMERS.map((d) => (
          <p
            key={d.code}
            style={{ margin: "0 0 6px", fontSize: 10.5, color: MUTED, lineHeight: 1.7 }}
          >
            · {d.text}
          </p>
        ))}
      </div>

      <PageFooter page={5} total={5} />
    </div>
  );
}

// ── 최종 export ─────────────────────────────────────────────────

export default function ClientPdfTemplate() {
  return (
    <>
      <CoverPage />
      <MarketIpsPage />
      <PortfolioPage />
      <TaxPage />
      <RiskCheckPage />
    </>
  );
}
