import { fmtSaving } from "@/lib/formatKrw";
import { TAX_ADVICE } from "@/lib/mockData";
import type { AllocationPlan } from "@/lib/taxAccounts";
import type { StressTaxStrategyCard } from "@/lib/api";

/** 화면이 보여 주는 3대 절세계좌. 총액 합산 범위도 이 둘로 맞춘다. */
const MASS_TAX_SOURCE_KEYS = ["isa", "pension_credit"] as const;

export type AdviceCard = (typeof TAX_ADVICE.cards)[number] & {
  /** 잔여 한도·배분액 — 카드에 항상 보인다. */
  summary: string;
  /** 제도 설명·판정 근거 — 화면에서는 가이드 툴팁, 리포트에서는 본문. */
  explain: string[];
  /** "약 +18만원" 같은 절감액 표기. 해당 없으면 빈 문자열. */
  saving: string;
  applicable: boolean;
};

/**
 * 절세 제안 카드 세 장과 총액.
 *
 * 화면(TaxSection)과 리포트(PbPdfTemplate·ClientPdfTemplate)가 같은 함수를 부른다.
 * 예전에는 이 계산이 화면 컴포넌트 안에만 있어서, 리포트는 mockData 의 자리표시
 * 문구("분석 후 계산")를 그대로 인쇄했다.
 */
export function deriveAdviceCards(
  plan: AllocationPlan | null,
  liveCards: StressTaxStrategyCard[] | null,
): { cards: AdviceCard[]; totalSaving: string; totalLabel: string } {
  const liveByKey = new Map(liveCards?.map((card) => [card.key, card]) ?? []);

  /*
   * 카드마다 따로 폴백하면 백엔드가 일부만 내려줄 때 한 줄에 백엔드 숫자와 프론트
   * 계산이 나란히 뜨는데 화면에는 구분이 없다. 어느 하나라도 오면 전부 백엔드 경로로
   * 간다 — 출처가 섞이느니 비어 있는 편이 추적 가능하다.
   */
  const useLive = (liveCards?.length ?? 0) > 0;

  /**
   * 백엔드 응답이 없을 때(데모·연결 실패) 프론트 계산을 같은 모양으로 돌려준다.
   * 예전에는 이 자리가 비어 카드 세 장이 금액 없이 설명문만 남았다.
   */
  const fromPlan = (card: (typeof TAX_ADVICE.cards)[number]) => {
    if (!plan) return null;
    const isIsa = card.sourceKey === "isa";
    const account = isIsa ? plan.isa : plan.pension;
    // 연금계좌는 한 덩어리로 계산하지만 배분은 카드별로 다르다 — 연금저축은 단독
    // 한도 600만원까지, 넘는 금액은 IRP 로 간다. 카드마다 제 몫을 말해야 PB 가
    // "연금저축에 900만원"처럼 안내하지 않는다.
    const allocated = isIsa
      ? plan.isaManwon
      : card.key === "irp"
        ? plan.irpManwon
        : plan.pensionSavingsManwon;
    /*
     * 카드마다 걸리는 한도가 다르다. 연금저축에는 단독 한도 600만원이 따로 있고,
     * IRP 는 연금저축과 900만원 통을 나눠 쓴다. 그래서 IRP 의 소진 여부는 자기
     * 배분액이 아니라 **연금 배분 합계**로 판단해야 한다 — irpManwon 으로 재면
     * "900 중 300" 이 되어 600만원이 남은 것처럼 읽히는데, 그 600만원은 옆 카드
     * (연금저축)가 이미 쓴 돈이다.
     */
    const cap = isIsa
      ? { limit: plan.isa.headroomManwon, used: plan.isaManwon, full: "한도 소진", left: "잔여" }
      : card.key === "irp"
        ? {
            limit: plan.pension.headroomManwon,
            used: plan.pensionManwon,
            full: `합산 ${plan.pension.headroomManwon.toLocaleString()}만원 소진`,
            left: "합산 한도 잔여",
          }
        : {
            limit: plan.pensionSavingsRoomManwon,
            used: plan.pensionSavingsManwon,
            full: "단독 한도 소진",
            left: "단독 한도 잔여",
          };
    const remaining = Math.max(cap.limit - cap.used, 0);
    const capText =
      remaining > 0 ? `${cap.left} ${remaining.toLocaleString()}만원` : cap.full;

    return {
      applicable: account.eligible,
      reason: account.reason,
      allocatedManwon: allocated,
      capText,
      headroomManwon: account.headroomManwon,
      savingManwon: isIsa ? plan.isaSavingManwon : plan.pensionSavingManwon,
      note: isIsa
        ? `이 고객은 ${plan.isaType.type === "seogmin" ? "서민형" : "일반형"}: 비과세 ${plan.isaType.taxFreeManwon}만원 (${plan.isaType.reason})`
        : card.key === "irp"
          ? "연금저축 단독 한도 600만원 초과분이 여기로 배분"
          : "연금저축 단독 한도는 600만원",
    };
  };

  // 화면은 Mass 고객의 3대 절세계좌만 보여 준다. 연금저축·IRP는 pension_credit
  // 합산 계산을 공유하므로 연금저축 카드에만 금액을 표시한다.
  const cards = TAX_ADVICE.cards.map((copy) => {
    const live = liveByKey.get(copy.sourceKey);
    const calc = useLive ? null : fromPlan(copy);

    const applicable = live?.applicable ?? calc?.applicable ?? true;
    const reason = live?.reason ?? live?.ineligibleReason ?? calc?.reason ?? null;
    const transferManwon = live?.transferableManwon ?? calc?.headroomManwon ?? null;

    /*
     * 카드에는 이 고객의 숫자와 결론만 두고, 제도 설명은 가이드 툴팁으로 보낸다.
     * 세 장이 나란히 서는 자리라 제도 문장까지 본문에 두면 읽히지 않는다.
     * 가이드가 OFF 여도 숫자는 남아야 하므로 둘을 섞지 않는다.
     *
     *   summary — 잔여 한도·배분액 (항상 카드에 보인다)
     *   explain — 제도 설명·판정 근거 (가이드 ON 일 때 hover 로 뜬다)
     */
    let summary: string;
    let explain: string[] = copy.helpLines;

    if (!applicable && reason) {
      summary = "적용 불가";
      explain = [reason];
    } else if (calc) {
      // 배분액이 답이라 앞에, 한도는 맥락이라 뒤에 둔다.
      summary =
        calc.allocatedManwon > 0
          ? `${calc.allocatedManwon.toLocaleString()}만원 배분 · ${calc.capText}`
          : `배분 없음 · ${calc.capText}`;
      // 판정 근거(일반형/서민형, 연금저축 단독 한도)도 설명 쪽이다.
      explain = [...copy.helpLines, calc.note];
    } else if (transferManwon != null) {
      summary =
        copy.sourceKey === "isa"
          ? `이전 가능액 ${transferManwon.toLocaleString()}만원`
          : `합산 잔여 활용 가능액 ${transferManwon.toLocaleString()}만원`;
    } else {
      summary = "";
    }

    /*
     * ⚠️ 두 값의 의미가 다르다.
     *     live.combined_contribution_manwon — 백엔드가 계산한 **납입액**
     *     calc.savingManwon                 — 프론트가 계산한 **절감액**
     * 그런데 같은 "+N만원" 절세액 슬롯에 들어간다. 백엔드가 붙으면 900만원 납입이
     * "+900만원 절세"로 보인다. live 쪽 표기는 이 PR 이전부터의 동작이라 여기서
     * 바꾸지 않지만, 백엔드를 연동할 때 반드시 손봐야 하는 자리다.
     * (아래 총액도 같은 문제를 갖는다.)
     */
    const liveContributionManwon = live?.applicable
      ? live.combined_contribution_manwon
      : 0;
    const calcSavingManwon = calc?.applicable ? calc.savingManwon : 0;
    const shownManwon = live ? liveContributionManwon : calcSavingManwon;

    const saving =
      copy.savingRole === "included"
        ? shownManwon > 0
          ? copy.saving
          : ""
        : shownManwon > 0
          ? `약 +${fmtSaving(shownManwon)}만원`
          : "";

    return { ...copy, summary, explain, saving, applicable };
  });

  // 기존 6종 combined_total에는 화면에서 제외한 전략도 들어 있다. 표시 총액은
  // ISA와 pension_credit을 각각 한 번만 합산해 3개 카드와 계산 범위를 맞춘다.
  // ⚠️ 위와 같은 의미 불일치 — live 쪽은 납입액 합, 프론트 쪽은 절감액 합이다.
  const massTotalManwon = useLive
    ? MASS_TAX_SOURCE_KEYS.reduce(
        (sum, key) =>
          sum + (liveByKey.get(key)?.combined_contribution_manwon ?? 0),
        0,
      )
    : (plan?.totalSavingManwon ?? null);
  const totalSaving =
    massTotalManwon != null
      ? `약 +${fmtSaving(massTotalManwon)}만원`
      : TAX_ADVICE.totalSaving;

  return { cards, totalSaving, totalLabel: TAX_ADVICE.totalLabel };
}
