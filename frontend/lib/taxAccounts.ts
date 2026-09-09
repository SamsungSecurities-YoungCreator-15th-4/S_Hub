/**
 * 절세계좌(ISA · 연금저축 · IRP) 한도·세액공제·적합성 계산.
 *
 * 왜 프론트인가: 여기 쓰이는 값은 전부 법으로 정해진 상수라 조회할 외부 소스가 없다.
 * 백엔드 `app/portfolio/tax_advice.py` 가 하던 판정과 같은 규칙이며, 데모 모드에서는
 * 백엔드를 부르지 않아(`portfolioTax: null`) 카드 금액이 계속 비어 있었다.
 *
 * 단위는 **만원**. 화면 입력·표시가 만원이라 원 단위로 올리면 반올림 자리가 어긋난다.
 *
 * 백엔드와 다른 점 하나: 백엔드 기본 세액공제율은 13.2%(고소득 구간) 한 값이다.
 * 총급여 5,500만원 이하는 16.5%인데 그 분기를 호출부가 넘겨 주지 않으면 낮은 쪽으로
 * 계산된다. 여기서는 총급여로 직접 판정한다.
 */

export interface TaxAccountAssumptions {
  /** ISA 연간 납입한도 */
  isaAnnualLimitManwon: number;
  /** ISA 순소득 비과세 한도 — 일반형 */
  isaGeneralTaxFreeManwon: number;
  /** ISA 순소득 비과세 한도 — 서민형 */
  isaSeogminTaxFreeManwon: number;
  /** 서민형 요건 — 총급여 기준(이하) */
  isaSeogminSalaryThresholdManwon: number;
  /** 서민형 요건 — 종합소득금액 기준(이하) */
  isaSeogminComprehensiveIncomeThresholdManwon: number;
  /** ISA 비과세 초과분 분리과세율 */
  isaExcessRate: number;
  /** ISA 의무보유기간(년) */
  isaMandatoryHoldingYears: number;
  /** ISA 총 납입한도 */
  isaTotalLimitManwon: number;
  /** 한도 누적 산식에서 경과연수에 걸리는 상한 */
  isaAccrualYearsCap: number;
  /** 연금저축+IRP 합산 세액공제 한도 */
  pensionCombinedLimitManwon: number;
  /** 연금저축 단독 세액공제 한도 */
  pensionOwnLimitManwon: number;
  /** 세액공제율 — 총급여 기준 이하 */
  pensionCreditRateLow: number;
  /** 세액공제율 — 총급여 기준 초과 */
  pensionCreditRateHigh: number;
  /** 세액공제율이 갈리는 총급여 경계 */
  pensionCreditSalaryThresholdManwon: number;
  /** 연금 수령 개시 가능 연령 */
  pensionReceiveAge: number;
  /** 이자·배당 원천징수 세율(지방소득세 포함) */
  withholdingRate: number;
  /**
   * ⚠️ 가정값. ISA 계좌 잔액이 연간 만들어 내는 **이자·배당** 수익률이다.
   * 자산별 소득수익률이 프론트에 없어 하나로 뭉뚱그렸다. 법정 상수가 아니므로
   * 화면에 가정임을 반드시 밝힐 것. 자산별 값이 생기면 이 상수를 지우고 대체한다.
   */
  isaAssumedIncomeYield: number;
}

/** 2026년 기준. 값을 고칠 때 화면의 출처 표기도 함께 고칠 것. */
export const ASSUMPTIONS: TaxAccountAssumptions = {
  isaAnnualLimitManwon: 2_000,
  isaGeneralTaxFreeManwon: 200,
  isaSeogminTaxFreeManwon: 400,
  isaSeogminSalaryThresholdManwon: 5_000,
  isaSeogminComprehensiveIncomeThresholdManwon: 3_800,
  isaExcessRate: 0.099,
  isaMandatoryHoldingYears: 3,
  isaTotalLimitManwon: 10_000,
  isaAccrualYearsCap: 4,
  pensionCombinedLimitManwon: 900,
  pensionOwnLimitManwon: 600,
  pensionCreditRateLow: 0.165,
  pensionCreditRateHigh: 0.132,
  pensionCreditSalaryThresholdManwon: 5_500,
  pensionReceiveAge: 55,
  withholdingRate: 0.154,
  isaAssumedIncomeYield: 0.03,
};

/**
 * 연금계좌 세액공제율. 총급여 5,500만원(종합소득금액 4,500만원) 이하면 16.5%.
 *
 * 총급여를 모르면 낮은 쪽(13.2%)을 쓴다. 모르는 것을 유리하게 가정하지 않는다.
 */
export function pensionCreditRate(salaryManwon: number | null | undefined): number {
  const a = ASSUMPTIONS;
  if (salaryManwon == null || !Number.isFinite(salaryManwon)) return a.pensionCreditRateHigh;
  return salaryManwon <= a.pensionCreditSalaryThresholdManwon
    ? a.pensionCreditRateLow
    : a.pensionCreditRateHigh;
}

export interface TaxAccountInput {
  /** 연간 총급여(만원) — 세액공제율 분기 */
  salaryManwon?: number | null;
  /**
   * ISA **누적** 납입금액(만원). 조특법 제91조의18 제3항 제5호 산식의 "누적 납입금액"이다.
   * 당해 납입액이 아니다 — 한도가 해마다 새로 쌓이는 구조라 누적으로 세야 한다.
   */
  isaUsedManwon: number;
  /**
   * ISA 가입 후 경과연수. 한도는 1월 1일에 새로 쌓이므로 가입일이 아니라
   * 해가 몇 번 바뀌었는지가 기준이다. 미지정이면 0(가입 첫해)으로 본다.
   */
  isaYearsSinceOpen?: number | null;
  /** 연금저축+IRP 당해 납입액(만원) */
  pensionUsedManwon: number;
  /**
   * 그중 연금저축에 들어간 금액(만원). 연금저축은 단독 한도가 600만원이라 합산
   * 900만원과 따로 봐야 한다. 미지정이면 기납입액이 연금저축부터 찼다고 본다.
   */
  pensionSavingsUsedManwon?: number | null;
  /** 종합소득금액(만원) — ISA 서민형 판정용. 근로소득만 있으면 생략해도 된다. */
  comprehensiveIncomeManwon?: number | null;
  /**
   * 직전 3년 중 한 번이라도 금융소득종합과세 대상이었는가. 서민형은 비대상자만
   * 가입할 수 있다. 미지정이면 대상이었던 적 없음으로 본다.
   */
  financialIncomeTaxpayerLast3Years?: boolean | null;
  /** 나이 — 연금 수령요건 게이팅 */
  age: number;
  /** 투자기간(년) — lock-up 게이팅 (IPS Time) */
  horizonYears: number;
  /** ISA 기존 개설 여부 */
  isaOpened: boolean;
  /** ISA 의무보유 잔여기간(년). 미지정이면 미개설은 3년, 개설은 0년으로 본다. */
  isaYearsUntilLiquid?: number | null;
}

export type IsaType = "general" | "seogmin";

export interface IsaTypeVerdict {
  type: IsaType;
  /** 순소득 비과세 한도(만원) */
  taxFreeManwon: number;
  /** 왜 이 유형인지 — 화면에 근거를 대기 위한 한 줄 */
  reason: string;
}

/**
 * ISA 서민형 판정. 요건은 "근로소득 5,000만원 이하 **또는** 종합소득금액 3,800만원
 * 이하"이고, 여기에 "직전 3년간 금융소득종합과세 대상이 아니었을 것"이 붙는다.
 *
 * 소득을 모르면 일반형으로 본다. 모르는 것을 유리하게 가정하지 않는다.
 */
export function isaTypeOf(input: TaxAccountInput): IsaTypeVerdict {
  const a = ASSUMPTIONS;
  const general: IsaTypeVerdict = {
    type: "general",
    taxFreeManwon: a.isaGeneralTaxFreeManwon,
    reason: "일반형",
  };

  if (input.financialIncomeTaxpayerLast3Years === true) {
    return { ...general, reason: "직전 3년 금융소득종합과세 대상이라 서민형 제외" };
  }

  const salary = input.salaryManwon;
  const comprehensive = input.comprehensiveIncomeManwon;
  const bySalary = salary != null && Number.isFinite(salary) && salary <= a.isaSeogminSalaryThresholdManwon;
  const byComprehensive =
    comprehensive != null &&
    Number.isFinite(comprehensive) &&
    comprehensive <= a.isaSeogminComprehensiveIncomeThresholdManwon;

  if (bySalary || byComprehensive) {
    return {
      type: "seogmin",
      taxFreeManwon: a.isaSeogminTaxFreeManwon,
      reason: bySalary
        ? `총급여 ${salary!.toLocaleString()}만원 ≤ ${a.isaSeogminSalaryThresholdManwon.toLocaleString()}만원`
        : `종합소득금액 ${comprehensive!.toLocaleString()}만원 ≤ ${a.isaSeogminComprehensiveIncomeThresholdManwon.toLocaleString()}만원`,
    };
  }

  return salary != null
    ? {
        ...general,
        reason: `총급여 ${salary.toLocaleString()}만원 > ${a.isaSeogminSalaryThresholdManwon.toLocaleString()}만원`,
      }
    : { ...general, reason: "소득 정보가 없어 일반형으로 봄" };
}

export interface AccountState {
  /** 남은 납입 한도(만원) */
  headroomManwon: number;
  /** 적합 여부 */
  eligible: boolean;
  /** 부적합 사유. 적합하면 null. */
  reason: string | null;
  /** 인출·해지가 자유로워지기까지 남은 기간(년) */
  lockupYears: number;
}

/**
 * 연금계좌 적합성 — 만 55세 전이고 투자기간이 수령까지 남은 기간보다 짧으면 부적합.
 *
 * 경계는 **미만**이다. 33세·투자기간 22년이면 55−33 = 22 이고 22 < 22 가 거짓이라
 * 적합으로 본다. 21년이면 부적합이다. 백엔드 tax_advice.py 와 같은 판정이다.
 */
export function pensionAccount(input: TaxAccountInput): AccountState {
  const a = ASSUMPTIONS;
  const headroom = Math.max(a.pensionCombinedLimitManwon - Math.max(input.pensionUsedManwon, 0), 0);
  const yearsToReceive = Math.max(a.pensionReceiveAge - input.age, 0);

  // 수령 요건은 "만 55세 이상 + 가입 후 5년 경과" 둘 다다. 다만 55세까지 5년 이상
  // 남은 나이에서는 나이 요건이 항상 더 늦게 충족되므로 여기서는 나이만 본다.
  // 만 50세 이후 신규 가입을 다루게 되면 가입연차 조건을 함께 넣어야 한다.
  let reason: string | null = null;
  if (input.age < a.pensionReceiveAge && input.horizonYears < yearsToReceive) {
    reason = `투자기간 ${input.horizonYears}년 < 연금 수령까지 ${yearsToReceive}년`;
  } else if (headroom <= 0) {
    reason = "당해 세액공제 한도 소진";
  }

  return { headroomManwon: headroom, eligible: reason === null, reason, lockupYears: yearsToReceive };
}

/**
 * ISA 적합성과 잔여 한도.
 *
 * 한도는 조특법 제91조의18 제3항 제5호의 누적 산식을 따른다.
 *
 *   연간 납입한도 = 2,000만원 × [1 + 가입 후 경과연수(4년 이상이면 4년)] − 누적 납입금액
 *
 * 조문에 "이월"이라는 단어는 없다. 채우지 못한 한도가 다음 해로 넘어가는 효과가
 * 이 산식에서 나온다. 경과연수가 4년에서 멈추므로 누적 상한은 총 1억원이다.
 *
 * 기준은 가입일이 아니라 **1월 1일**이다. 작년에 가입해 800만원을 넣었다면 올해
 * 한도는 2,000 − 800 = 1,200 이 아니라 2,000 × 2 − 800 = 3,200만원이다.
 *
 * ⚠️ 금융위원회 주요정책문답(fsc.go.kr/po020201/27339)은 "연간 한도를 채우지 못한
 *    금액의 이월은 없음"이라고 적어 두었는데, 2016년 도입 당시 Q&A 가 그대로 남아
 *    있는 것이다(같은 페이지가 의무가입기간을 5년으로 쓴다). 현행이 아니다.
 *
 * 적합성은 별개다 — 투자기간이 잔여 의무보유기간보다 짧으면 부적합.
 */
export function isaAccount(input: TaxAccountInput): AccountState {
  const a = ASSUMPTIONS;
  const used = Math.max(input.isaUsedManwon, 0);
  const elapsed = Math.min(
    Math.max(input.isaYearsSinceOpen ?? 0, 0),
    a.isaAccrualYearsCap,
  );
  const accrued = a.isaAnnualLimitManwon * (1 + elapsed);
  // 두 캡은 같은 것의 다른 표현이다 — 경과연수가 4에서 멈추므로 accrued 는 최대
  // 2,000 × 5 = 10,000 이라 총한도 캡이 실제로 선택되는 경우는 없다. 상수 중 하나가
  // 바뀌었을 때 조용히 어긋나지 않도록 방어로 남긴다.
  const headroom = Math.max(
    Math.min(accrued - used, a.isaTotalLimitManwon - used),
    0,
  );
  const lockup =
    input.isaYearsUntilLiquid != null && Number.isFinite(input.isaYearsUntilLiquid)
      ? Math.max(input.isaYearsUntilLiquid, 0)
      : input.isaOpened
        ? 0
        : a.isaMandatoryHoldingYears;

  let reason: string | null = null;
  if (lockup > 0 && input.horizonYears < lockup) {
    reason = `투자기간 ${input.horizonYears}년 < ISA 잔여 의무보유 ${lockup}년`;
  } else if (headroom <= 0) {
    reason = "당해 납입한도 소진";
  }

  return { headroomManwon: headroom, eligible: reason === null, reason, lockupYears: lockup };
}

export interface AllocationPlan {
  /** 연금계좌 납입액(만원) — 연금저축 + IRP */
  pensionManwon: number;
  /** 그중 연금저축 몫(만원). 단독 한도 600만원에 걸린다. */
  pensionSavingsManwon: number;
  /** 연금저축 단독 한도의 잔여분(만원). 합산 한도와 다르므로 카드가 따로 표기해야 한다. */
  pensionSavingsRoomManwon: number;
  /** 그중 IRP 몫(만원). 연금저축 단독 한도를 넘는 금액이 여기로 간다. */
  irpManwon: number;
  /** ISA 납입액(만원) */
  isaManwon: number;
  /** 두 계좌 한도를 넘어 일반계좌로 가는 금액(만원) */
  generalManwon: number;
  /** 연금 세액공제 환급액(만원) */
  pensionSavingManwon: number;
  /** 적용된 세액공제율 */
  pensionRate: number;
  /** ISA 절감액(만원) — 가정 수익률 기반 */
  isaSavingManwon: number;
  /** ISA 유형과 그 근거 */
  isaType: IsaTypeVerdict;
  /** 두 절감액의 합(만원) */
  totalSavingManwon: number;
  /** 목표 시점에 손댈 수 없는 금액(만원) — 연금에 넣어 잠긴 누적액 */
  lockedAtTargetManwon: number;
  /** 목표 시점에 쓸 수 있는 누적 납입액(만원) */
  liquidAtTargetManwon: number;
  pension: AccountState;
  isa: AccountState;
}

/**
 * 연 납입여력을 연금과 ISA 에 나눠 넣었을 때의 절감액과 유동성.
 *
 * `pensionRequestManwon` 만큼 연금에 먼저 넣고, 남는 돈을 ISA 한도까지, 그래도
 * 남으면 일반계좌로 본다. 부적합 계좌에는 배정하지 않는다.
 *
 * ISA 절감액은 **신규 납입분만이 아니라 계좌 잔액 전체**가 만드는 이자·배당에
 * 걸린다. 기납입액을 더해서 계산하는 이유다. 다만 그 수익률은 가정값이다.
 *
 * 유동성은 목표 시점(`targetYears`)까지의 **누적 납입액** 기준이다. 기존 보유자산은
 * 넣지 않는다 — 그쪽은 매도 시점과 평가손익에 좌우되므로 여기서 단정할 수 없다.
 */
export function allocationPlan(
  input: TaxAccountInput,
  annualContributionManwon: number,
  pensionRequestManwon: number,
  targetYears: number,
): AllocationPlan {
  const a = ASSUMPTIONS;
  const pension = pensionAccount(input);
  const isa = isaAccount(input);

  const budget = Math.max(annualContributionManwon, 0);
  const toPension = pension.eligible
    ? Math.min(Math.max(pensionRequestManwon, 0), pension.headroomManwon, budget)
    : 0;
  const toIsa = isa.eligible ? Math.min(budget - toPension, isa.headroomManwon) : 0;
  const toGeneral = Math.max(budget - toPension - toIsa, 0);

  const rate = pensionCreditRate(input.salaryManwon);
  const pensionSaving = toPension * rate;

  /*
   * 연금저축은 단독 한도가 600만원이라 합산 900만원과 따로 봐야 한다. 900만원을
   * 전부 연금저축에 넣으면 600만원까지만 공제되므로, 초과분은 IRP 로 보낸다.
   * 화면이 두 카드로 나뉘어 있어 이 분배를 말해 주지 않으면 PB 가 "연금저축에
   * 900만원"이라고 안내하게 된다.
   */
  const savingsUsed =
    input.pensionSavingsUsedManwon != null && Number.isFinite(input.pensionSavingsUsedManwon)
      ? Math.max(input.pensionSavingsUsedManwon, 0)
      : Math.min(Math.max(input.pensionUsedManwon, 0), a.pensionOwnLimitManwon);
  const savingsRoom = Math.max(a.pensionOwnLimitManwon - savingsUsed, 0);
  const toPensionSavings = Math.min(toPension, savingsRoom);
  const toIrp = toPension - toPensionSavings;

  // ISA 안 vs 밖 — 같은 이자·배당에 붙는 세금 차이. 비과세 한도는 유형이 정한다.
  const isaType = isaTypeOf(input);
  const isaBalance = Math.max(input.isaUsedManwon, 0) + toIsa;
  const income = isaBalance * a.isaAssumedIncomeYield;
  const taxOutside = income * a.withholdingRate;
  const taxInside = Math.max(income - isaType.taxFreeManwon, 0) * a.isaExcessRate;
  const isaSaving = Math.max(taxOutside - taxInside, 0);

  const years = Math.max(targetYears, 0);
  // ISA 의무보유가 목표 시점 뒤에 풀리면 그 돈도 목표 시점에는 못 쓴다.
  // (의무보유는 납입분별이 아니라 계좌 단위이므로 개설 시점 하나로 갈린다.)
  const isaLiquidByTarget = isa.lockupYears <= years;
  const locked = (toPension + (isaLiquidByTarget ? 0 : toIsa)) * years;
  const liquid = ((isaLiquidByTarget ? toIsa : 0) + toGeneral) * years;

  return {
    pensionManwon: toPension,
    pensionSavingsManwon: toPensionSavings,
    pensionSavingsRoomManwon: savingsRoom,
    irpManwon: toIrp,
    isaManwon: toIsa,
    generalManwon: toGeneral,
    pensionSavingManwon: pensionSaving,
    pensionRate: rate,
    isaSavingManwon: isaSaving,
    isaType,
    totalSavingManwon: pensionSaving + isaSaving,
    lockedAtTargetManwon: locked,
    liquidAtTargetManwon: liquid,
    pension,
    isa,
  };
}

/**
 * 목표 시점의 필요액을 지키면서 연금에 넣을 수 있는 최대 납입액(만원).
 *
 * 닫힌 식으로 풀지 않고 allocationPlan 을 그대로 호출해 탐색한다. 유동액 규칙이
 * 한 곳에만 있어야 하기 때문이다 — 상한을 따로 유도하면 ISA 의무보유가 목표 시점
 * 뒤에 풀리는 고객에서 두 계산이 갈린다. 그때 "연금을 N만원으로 낮추면 맞춰집니다"가
 * 맞출 수 없는 수치가 되고, PB 가 그대로 고객에게 말하게 된다.
 *
 * 어떤 배분으로도 필요액을 못 채우면 null 이다. 연금을 0으로 해도 모자라는 경우가
 * 실제로 있다 — 남는 돈이 목표 시점에 안 풀리는 ISA 로 흘러갈 때가 그렇다.
 */
export function maxPensionKeepingNeed(
  input: TaxAccountInput,
  annualContributionManwon: number,
  needManwon: number,
  targetYears: number,
  stepManwon = 10,
): number | null {
  const budget = Math.max(annualContributionManwon, 0);
  const ceiling = Math.min(pensionAccount(input).headroomManwon, budget);
  const step = Math.max(stepManwon, 1);

  const meetsNeed = (p: number) =>
    allocationPlan(input, budget, p, targetYears).liquidAtTargetManwon + 1e-9 >= needManwon;

  let best: number | null = null;
  for (let p = 0; p <= ceiling + 1e-9; p += step) {
    if (meetsNeed(p)) best = p;
  }
  // 한도가 step 의 배수가 아니면 끝점이 빠진다. 끝점도 확인한다.
  if (ceiling % step !== 0 && meetsNeed(ceiling)) best = ceiling;
  return best;
}
