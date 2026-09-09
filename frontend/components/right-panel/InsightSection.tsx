"use client";

import { useState } from "react";
import { ExternalLink, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import DataSourceBadge from "@/components/common/DataSourceBadge";
import HelpTooltip from "@/components/common/HelpTooltip";

const INSIGHT_HELP =
  "투자하면서 궁금한 내용을 AI에게 직접 물어보고 답을 받을 수 있습니다. " +
  "금리·세금·종목 등을 질문할 수 있으며 답변의 근거와 출처도 함께 확인할 수 있습니다.";
import { buildDashboardInsightContext } from "@/lib/dashboardInsightContext";
import {
  type InsightCitation,
  detectFinancialQuery,
  fetchDartInsight,
  fetchRagInsight,
} from "@/lib/api";
import { useDashboardStore } from "@/lib/store";
import { lookupDocument } from "@/lib/documentLinks";

/** 우측 하단: AI 인사이트 검색(RAG /rag/insight 실연결) + 결과 + 요약 + 출처/인용 */
export default function InsightSection() {
  const {
    customers,
    portfolios,
    ips,
    consultationId,
    liveBase,
    scenario,
    selectedCustomerId,
    selectedPortfolioId,
    insightResult,
    setInsightResult,
    helpMode,
  } = useDashboardStore();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const result = insightResult;

  const selectedCustomer =
    customers.find((customer) => customer.id === selectedCustomerId) ??
    customers[0];
  const portfolioName = portfolios.find(
    (p) => p.id === selectedPortfolioId,
  )?.name;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim();
    if (!q || loading) return;
    setLoading(true);
    try {
      const financial = detectFinancialQuery(q);
      const res = financial
        ? await fetchDartInsight(financial.corpName)
        : await fetchRagInsight(q, {
            consultationId: consultationId || undefined,
            riskProfile: ips.risk,
            selectedPortfolio: portfolioName,
            dashboard: buildDashboardInsightContext({
              selectedCustomer,
              selectedPortfolioId,
              ips,
              scenario,
              liveBase,
            }),
          });
      setInsightResult(res);
    } finally {
      setLoading(false);
    }
  }

  const showInitial = result === null;
  const source = showInitial ? null : result.source;
  const note = showInitial ? null : result.note;
  const isEmpty = !showInitial && result.source === "empty";
  const answer = showInitial ? "" : result.data.answer;
  const summary = showInitial
    ? ""
    : result.data.summary || answer.split("\n\n")[0] || answer;
  const citations: InsightCitation[] = showInitial ? [] : result.data.citations;

  return (
    <Card className="flex flex-1 flex-col gap-0 p-3.5 min-h-0">
      {/* 헤더 */}
      <div className="mb-2.5 flex shrink-0 items-center justify-between">
        <HelpTooltip text={INSIGHT_HELP} placement="bottom">
          <p className="cursor-default text-[14px] font-bold">
            <span
              className={
                helpMode
                  ? "rounded border border-brand/40 bg-brand/[0.06] px-1"
                  : ""
              }
            >
              AI 인사이트
            </span>
          </p>
        </HelpTooltip>
        {source && <DataSourceBadge source={source} note={note ?? undefined} />}
      </div>

      {/* 검색 폼 */}
      <form className="mb-2.5 flex shrink-0 gap-1.5" onSubmit={handleSubmit}>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="예: 재무제표, RAG 문서, 분석 결과 요약"
          className="h-8 text-[13px] md:text-[13px]"
          disabled={loading}
        />
        <Button
          type="submit"
          size="sm"
          className="font-bold"
          /* 빈 질의는 handleSubmit 이 조용히 return 하므로(:56) 버튼에서 막는다 —
             누르고도 아무 일이 없으면 고장으로 읽힌다. */
          disabled={loading || query.trim() === ""}
        >
          {loading ? <Loader2 className="size-3.5 animate-spin" /> : "검색"}
        </Button>
      </form>

      {/*
        분석 결과 : 분석 요약 : 출처 = 2:1:1 로 고정한다.
        세 칸 모두 항상 렌더한다 — 검색 전후로 칸이 생겼다 사라지면 화면이 흔들리고,
        출처가 들어올 자리를 미리 보여 주는 편이 읽기 쉽다.
        각 칸은 flex-basis 0 이라 높이가 비율대로 나뉘고, 내용이 넘치면 칸 안에서
        스크롤한다(아래 overflow-y-auto + min-h-0). min-h 도 같은 2:1:1 로 둬서
        창이 짧아져도 비율이 먼저 깨지지 않게 한다.
      */}
      <div className="flex flex-1 flex-col gap-2.5 min-h-0">
        {/* 분석 결과 */}
        <div className="flex flex-[2] flex-col rounded-xl border border-brand/15 bg-brand/5 p-3 min-h-[120px]">
          <div className="mb-2 flex shrink-0 items-center gap-1.5">
            <Sparkles className="size-3 text-brand" />
            <span className="text-[13px] font-extrabold tracking-wide text-brand-dark">
              분석 결과
            </span>
            {result?.data?.asOf && (
              <span className="ml-auto text-[9px] font-semibold text-muted-foreground/70">
                기준{" "}
                {new Date(result.data.asOf).toLocaleString("ko-KR", {
                  timeZone: "Asia/Seoul",
                })}
              </span>
            )}
          </div>
          <div className="flex-1 overflow-y-auto pr-1 min-h-0">
            {showInitial ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                질문을 입력하세요
              </p>
            ) : isEmpty ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                {note ?? "관련 문서를 찾지 못했습니다."}
              </p>
            ) : (
              <p className="whitespace-pre-line text-[13px] font-medium leading-relaxed text-foreground">
                {answer}
              </p>
            )}
          </div>
        </div>

        {/* 분석 요약 */}
        <div className="flex flex-[1] flex-col rounded-xl border border-brand/15 bg-brand/5 p-3 min-h-[60px]">
          <div className="mb-2 flex shrink-0 items-center gap-1.5">
            <Sparkles className="size-3 text-brand" />
            <span className="text-[13px] font-extrabold tracking-wide text-brand-dark">
              분석 요약
            </span>
          </div>
          <div className="flex-1 overflow-y-auto pr-1 min-h-0">
            {showInitial || isEmpty ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                요약 정보가 없습니다.
              </p>
            ) : (
              <p className="whitespace-pre-line text-[13px] font-medium leading-relaxed text-foreground">
                {summary}
              </p>
            )}
          </div>
        </div>

        {/* 출처 / 인용 목록 */}
        <div className="flex flex-[1] flex-col min-h-[60px]">
          <p className="mb-1 shrink-0 text-[14px] font-bold">출처 / 인용 목록</p>
          <div className="flex-1 overflow-y-auto min-h-0">
            {citations.length === 0 ? (
              <p className="text-[13px] font-medium text-muted-foreground">
                인용된 문서가 없습니다.
              </p>
            ) : (
              citations.map((src, i) => {
                const docInfo = lookupDocument(src.title);
                const displayDate = docInfo?.date ?? src.date;
                const inner = (
                  <>
                    <ExternalLink
                      className={`size-3 shrink-0 ${docInfo ? "text-brand" : "text-muted-foreground/70"}`}
                    />
                    <span className="flex-1 truncate text-[13px] font-semibold text-muted-foreground/90">
                      {src.title}
                    </span>
                    {displayDate && (
                      <span className="shrink-0 text-[8.5px] font-semibold tabular-nums text-muted-foreground/70">
                        {displayDate}
                      </span>
                    )}
                  </>
                );
                return docInfo ? (
                  <a
                    key={`${src.title}-${i}`}
                    href={docInfo.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 border-b border-muted py-1.5 last:border-none hover:bg-brand/5 rounded transition-colors"
                  >
                    {inner}
                  </a>
                ) : (
                  <div
                    key={`${src.title}-${i}`}
                    className="flex items-center gap-2 border-b border-muted py-1.5 last:border-none"
                  >
                    {inner}
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
