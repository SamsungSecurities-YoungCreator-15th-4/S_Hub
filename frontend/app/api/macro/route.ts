/**
 * GET /api/macro — 헤더 거시지표 6종.
 *
 * 백엔드(`/api/macro-indicators`)를 대체한다. 야후 엔드포인트는 CORS 헤더를 주지
 * 않아 브라우저에서 직접 못 부르므로, Next 서버(Node)에서 도는 이 라우트가 대신 받는다.
 *
 * 6종 중 4종만 실시간이다.
 *   실시간  미 10Y(^TNX) · 원/달러(KRW=X) · KOSPI(^KS11) · S&P 500(^GSPC)
 *   발표값  미국 기준금리 · 미국 CPI  — 야후에 없는 지표라 발표 때 손으로 갱신한다.
 *           `isStatic: true` 로 내보내면 화면이 등락 대신 "발표 기준"으로 표시한다.
 *
 * 실시간 조회에 실패한 지표는 조용히 감추지 않고 `isFallback: true` 를 달아
 * "지연 시세"로 표시되게 한다. 값이 없는 것과 못 받은 것을 구분하기 위함이다.
 */
import { NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** 야후 조회 결과를 이 시간만큼 재사용한다. 헤더는 5분마다 자동 갱신되므로 그보다 짧게 잡는다. */
const CACHE_TTL_MS = 60 * 1000;

/**
 * 발표 때만 바뀌는 지표 — 값을 고칠 때 `asOf` 와 `source` 도 반드시 함께 고칠 것.
 * "이 숫자 어디서 왔습니까"에 답할 수 있어야 한다.
 */
const ANNOUNCED = {
  baseRate: {
    /**
     * 연방기금금리 목표범위의 **상단**. 범위가 3.50~3.75% 이면 3.75 를 넣는다.
     * 국내 보도 관행이 상단 표기이므로 그에 맞춘다 — 갱신할 때 하단으로 넣지 말 것.
     */
    price: 3.75,
    /** 직전 FOMC 대비 변화(%p). 인하면 음수. 4.00% → 3.75% 이므로 -0.25. */
    change: -0.25,
    asOf: "2026-07 FOMC",
    source: "FOMC 목표범위 3.50~3.75% (상단 기준)",
  },
  cpi: {
    /** 전년 동월 대비 상승률(%). */
    price: 3.4,
    /** 직전 발표(6월 3.5%) 대비 변화(%p). */
    change: -0.1,
    asOf: "2026-07",
    source: "미국 노동통계국 CPI 전년비",
  },
} as const;

const TICKERS = {
  treasuryYield: "^TNX",
  krwUsd: "KRW=X",
  kospi: "^KS11",
  sp500: "^GSPC",
} as const;

type Live = { price: number; change: number; changePct: number };
type Cache = { at: number; body: unknown };
type LastGood = Partial<Record<keyof typeof TICKERS, Live>>;

// 개발 중 핫리로드로 모듈이 다시 평가돼도 남아 있게 globalThis 에 둔다.
const g = globalThis as unknown as { __macroCache?: Cache; __macroLastGood?: LastGood };

/**
 * 야후에서 한 종목의 현재가와 **전일 종가**를 가져온다.
 *
 * ⚠️ `meta.chartPreviousClose` 를 쓰면 안 된다. 그건 전일 종가가 아니라 조회 구간
 *    직전의 종가라, range=5d 로 부르면 5일치 변동이 하루치로 찍힌다.
 *    (실측: KOSPI 가 -40.87 이어야 하는데 +118.72 로 나왔다.)
 *    그래서 일봉 배열에서 직접 마지막 두 개를 뽑는다.
 */
async function quote(ticker: string): Promise<Live> {
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}` +
    `?range=1mo&interval=1d`;
  const res = await fetch(url, {
    // User-Agent 가 없으면 야후가 403 을 주는 경우가 있다.
    headers: { "User-Agent": "Mozilla/5.0 (compatible; SHubDashboard/1.0)" },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const json = (await res.json()) as {
    chart?: {
      result?: {
        meta?: { regularMarketPrice?: number };
        indicators?: { quote?: { close?: (number | null)[] }[] };
      }[];
    };
  };
  const r = json.chart?.result?.[0];
  const bars = (r?.indicators?.quote?.[0]?.close ?? []).filter(
    (v): v is number => typeof v === "number" && Number.isFinite(v) && v > 0,
  );
  if (bars.length < 2) throw new Error("일봉 부족");

  const last = bars[bars.length - 1];
  const live = r?.meta?.regularMarketPrice;
  let price = typeof live === "number" && Number.isFinite(live) ? live : last;

  // 장중이면 마지막 봉이 '오늘 진행 중' 봉이라 현재가와 같다 → 전일은 그 앞 봉.
  // 장이 닫혀 마지막 봉이 이미 확정된 경우도 같은 규칙으로 맞는다.
  const sameAsLast = Math.abs(price - last) / Math.max(Math.abs(last), 1e-9) < 1e-6;
  let prev = sameAsLast ? bars[bars.length - 2] : last;

  // ^TNX 는 시기에 따라 수익률을 10배(43.8)로 주기도 하고 그대로(4.38) 주기도 한다.
  // 10년물이 20%를 넘을 일은 없으므로 그 선을 기준으로 되돌린다.
  if (ticker === "^TNX" && price > 20) {
    price /= 10;
    prev /= 10;
  }

  return {
    price,
    change: price - prev,
    changePct: prev !== 0 ? ((price - prev) / prev) * 100 : 0,
  };
}

export async function GET(request: Request) {
  const force = new URL(request.url).searchParams.get("force") === "true";

  const cached = g.__macroCache;
  if (!force && cached && Date.now() - cached.at < CACHE_TTL_MS) {
    return NextResponse.json(cached.body);
  }

  const lastGood: LastGood = g.__macroLastGood ?? {};

  const entries = await Promise.all(
    (Object.entries(TICKERS) as [keyof typeof TICKERS, string][]).map(
      async ([key, ticker]) => {
        try {
          const live = await quote(ticker);
          lastGood[key] = live;
          return [key, { ...live, isFallback: false }] as const;
        } catch {
          // types.ts 의 isFallback 계약: "실시간 조회 실패 → 마지막 확인값".
          // 0 으로 채우면 화면이 "—"에 "지연 시세"를 붙여 앞뒤가 안 맞는다.
          // 한 번도 못 받았을 때만 0 이고, 그 경우 화면은 "—" 로 찍는다.
          const prev = lastGood[key];
          return [
            key,
            prev
              ? { ...prev, isFallback: true }
              : { price: 0, change: 0, changePct: 0, isFallback: true },
          ] as const;
        }
      },
    ),
  );
  g.__macroLastGood = lastGood;

  const body = {
    ...Object.fromEntries(entries),
    baseRate: { ...ANNOUNCED.baseRate, changePct: 0, isStatic: true },
    cpi: { ...ANNOUNCED.cpi, changePct: 0, isStatic: true },
    fetchedAt: new Date().toISOString(),
  };

  g.__macroCache = { at: Date.now(), body };
  return NextResponse.json(body);
}
