"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { CONSULT_LOG, IPS_DEFAULT, type ConsultMessage } from "@/lib/mockData";
import { useDashboardStore } from "@/lib/store";
import type { SttRealtimeStatus } from "@/lib/useSttRealtime";

/**
 * 상담 내역 재생 — 좌측 "실시간 녹음" 버튼이 쓰는 훅.
 *
 * PB 가 화면이 아니라 고객을 보면서 상담한다는 것을 보여주는 것이 목적이라,
 * 발화가 타임스탬프 순서대로 하나씩 쌓이는 흐름만 재현한다. 인식 정확도를
 * 보이는 기능이 아니므로 음성 입력은 다루지 않는다.
 *
 * `useSttRealtime` 과 반환 모양을 맞춰 두어 호출부(Sidebar)와
 * `SttRecordingModal` 이 그대로 붙는다. 다만 마이크는 열지 않는다 —
 * `getUserMedia` 를 부르면 브라우저 권한 팝업이 뜨고, 그 팝업이 뜬 순간
 * 발표 화면이 끊긴다. 그래서 `analyserRef` 는 항상 null 이고 파형은
 * 음량이 아니라 고정 진폭으로 그려진다.
 */

/** 재생 배속. 원본 상담이 약 2분이라 실제 속도로 두면 발표가 늘어진다. */
const PLAYBACK_SPEED = 6;

/** 가상 시계를 굴리는 주기(ms). 화면 갱신 빈도이자 정지 반응 지연의 상한이다. */
const TICK_MS = 100;

/** 버튼을 누르고 첫 발화가 뜨기까지의 준비 구간(ms). */
const CONNECTING_MS = 700;

/** "00:07" → 7. 형식이 어긋나면 null 이라 해당 항목을 건너뛴다. */
function parseTimeToSeconds(time: string): number | null {
  const m = /^(\d{1,2}):(\d{2})$/.exec(time.trim());
  if (!m) return null;
  const minutes = Number(m[1]);
  const seconds = Number(m[2]);
  if (!Number.isFinite(minutes) || !Number.isFinite(seconds)) return null;
  return minutes * 60 + seconds;
}

type Cue = { at: number; message: ConsultMessage };

/** 타임스탬프를 못 읽는 항목은 빼고, 재생 순서대로 정렬한다. */
function buildCues(log: ConsultMessage[]): Cue[] {
  return log
    .map((message) => {
      const at = parseTimeToSeconds(message.time);
      return at == null ? null : { at, message };
    })
    .filter((cue): cue is Cue => cue !== null)
    .sort((a, b) => a.at - b.at);
}

export function useConsultPlayback() {
  const [status, setStatus] = useState<SttRealtimeStatus>("idle");
  const [isPaused, setIsPaused] = useState(false);

  // 모달의 파형 컴포넌트가 요구하는 형태만 맞춘다. 마이크를 열지 않으므로 항상 null 이다.
  const analyserRef = useRef<AnalyserNode | null>(null);

  const setTranscript = useDashboardStore((s) => s.setTranscript);
  const setIps = useDashboardStore((s) => s.setIps);

  const cuesRef = useRef<Cue[]>([]);
  const nextIndexRef = useRef(0);
  const playedRef = useRef<ConsultMessage[]>([]);
  const virtualSecondsRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  /** 돌고 있는 타이머를 모두 끊는다. 언마운트·정지·재시작이 전부 여기를 지난다. */
  const clearTimers = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  // 언마운트 시 정리 — 모달을 닫은 채로 타이머만 남아 store 를 계속 건드리는 것을 막는다.
  useEffect(() => clearTimers, [clearTimers]);

  const finish = useCallback(() => {
    clearTimers();
    // 시연에서는 녹음 길이와 무관하게 종료 시 확정 상담 전체를 남긴다.
    // 발표자가 첫 발화 전에 종료하거나 중간에 끊어도 상담 내역의 결과가 달라지지 않는다.
    playedRef.current = [...CONSULT_LOG];
    setTranscript(playedRef.current, "fallback");
    // Asset은 선택 고객의 운용자산을 그대로 표시한다. 나머지 Goal/RRTTLLU는
    // 이 고정 상담에서 추출한 값으로 채워 전사와 IPS 조율기가 함께 확정되게 한다.
    setIps({
      goal: IPS_DEFAULT.goal,
      returnPct: IPS_DEFAULT.returnPct,
      risk: IPS_DEFAULT.risk,
      timeYears: IPS_DEFAULT.timeYears,
      tax: IPS_DEFAULT.tax,
      liquidity: IPS_DEFAULT.liquidity,
      legal: IPS_DEFAULT.legal,
      unique: IPS_DEFAULT.unique,
    });
    setIsPaused(false);
    setStatus("stopping");
    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      setStatus("done");
    }, 400);
  }, [clearTimers, setIps, setTranscript]);

  const tick = useCallback(() => {
    virtualSecondsRef.current += (TICK_MS / 1000) * PLAYBACK_SPEED;

    const cues = cuesRef.current;
    let appended = false;
    while (
      nextIndexRef.current < cues.length &&
      cues[nextIndexRef.current].at <= virtualSecondsRef.current
    ) {
      playedRef.current = [
        ...playedRef.current,
        cues[nextIndexRef.current].message,
      ];
      nextIndexRef.current += 1;
      appended = true;
    }

    // 재생된 분량만 올린다 — 아직 나오지 않은 발화가 화면에 미리 뜨면 흐름이 깨진다.
    if (appended) setTranscript(playedRef.current, "fallback");

    if (nextIndexRef.current >= cues.length) {
      clearTimers();
      // 마지막 전사가 나와도 recording 상태와 팝업은 그대로 유지한다.
      // 사용자가 종료 버튼을 눌렀을 때만 finish가 실행되어 팝업이 닫힌다.
    }
  }, [clearTimers, setTranscript]);

  const runInterval = useCallback(() => {
    if (intervalRef.current !== null) return;
    intervalRef.current = setInterval(tick, TICK_MS);
  }, [tick]);

  const start = useCallback(() => {
    clearTimers();
    cuesRef.current = buildCues(CONSULT_LOG);
    nextIndexRef.current = 0;
    playedRef.current = [];
    virtualSecondsRef.current = 0;
    setIsPaused(false);
    // 빈 상태에서 시작해야 발화가 쌓이는 것이 보인다.
    setTranscript([], "empty");

    if (cuesRef.current.length === 0) {
      setStatus("done");
      return;
    }

    setStatus("connecting");
    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      setStatus("recording");
      runInterval();
    }, CONNECTING_MS);
  }, [clearTimers, runInterval, setTranscript]);

  const pause = useCallback(() => {
    if (intervalRef.current === null) return;
    clearInterval(intervalRef.current);
    intervalRef.current = null;
    setIsPaused(true);
  }, []);

  const resume = useCallback(() => {
    setIsPaused(false);
    runInterval();
  }, [runInterval]);

  /** 종료 — 재생 지점과 무관하게 고정 상담 전체를 상담 내역에 확정한다. */
  const stop = useCallback(() => {
    finish();
  }, [finish]);

  const reset = useCallback(() => {
    clearTimers();
    setIsPaused(false);
    setStatus("idle");
  }, [clearTimers]);

  return {
    status,
    errorMsg: null as string | null,
    isPaused,
    analyserRef,
    start,
    stop,
    pause,
    resume,
    reset,
  };
}
