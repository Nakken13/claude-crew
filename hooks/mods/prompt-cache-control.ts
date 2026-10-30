/**
 * Mod 1 — prompt-cache-control.ts
 *
 * Affiche au-dessus du prompt un timer de TTL du cache (5 min / 1h) et les compteurs
 * `cache_read_input_tokens` / `cache_creation_input_tokens`.
 * Alerte visuelle immédiate si le cache expire (< 60s).
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  extractTurnUsage,
  formatCompactTokens,
  formatCountdownClock,
  type ModRegistrar,
} from './shared.ts';

export interface PromptCacheControlState {
  ttlSeconds: number;
  lastRefreshAtMs: number | null;
  lastCacheReadTokens: number;
  lastCacheCreationTokens: number;
  sessionCacheReadTokens: number;
  sessionCacheCreationTokens: number;
  alertedExpiringForRefreshMs: number | null;
}

export const promptCacheState: PromptCacheControlState = {
  ttlSeconds: 300,
  lastRefreshAtMs: null,
  lastCacheReadTokens: 0,
  lastCacheCreationTokens: 0,
  sessionCacheReadTokens: 0,
  sessionCacheCreationTokens: 0,
  alertedExpiringForRefreshMs: null,
};

export interface FormattedCacheStatus {
  visible: boolean;
  ttlLabel: '5 min' | '1h';
  remainingSeconds: number;
  isWarm: boolean;
  isExpiringSoon: boolean;
  isExpired: boolean;
  hitRatePercent: number;
  color: string;
  bold: boolean;
  line: string;
}

export function computePromptCacheStatus(nowMs = Date.now()): FormattedCacheStatus {
  const ttlLabel: '5 min' | '1h' = promptCacheState.ttlSeconds >= 3600 ? '1h' : '5 min';

  if (promptCacheState.lastRefreshAtMs === null) {
    return {
      visible: true,
      ttlLabel,
      remainingSeconds: 0,
      isWarm: false,
      isExpiringSoon: false,
      isExpired: false,
      hitRatePercent: 0,
      color: 'gray',
      bold: false,
      line: `🧊 Cache (${ttlLabel}) --:-- | cache_read: 0 · cache_creation: 0`,
    };
  }

  const elapsedSec = Math.max(0, Math.floor((nowMs - promptCacheState.lastRefreshAtMs) / 1000));
  const remainingSeconds = Math.max(0, promptCacheState.ttlSeconds - elapsedSec);
  const isExpired = remainingSeconds === 0;
  const isExpiringSoon = remainingSeconds > 0 && remainingSeconds < 60;
  const isWarm = remainingSeconds >= 60;

  const totalCache =
    promptCacheState.sessionCacheReadTokens + promptCacheState.sessionCacheCreationTokens;
  const hitRatePercent =
    totalCache > 0
      ? Math.floor((promptCacheState.sessionCacheReadTokens / totalCache) * 100)
      : 0;

  const clock = formatCountdownClock(remainingSeconds);
  const readFmt = formatCompactTokens(promptCacheState.lastCacheReadTokens);
  const writeFmt = formatCompactTokens(promptCacheState.lastCacheCreationTokens);

  let prefix = `🔥 Cache (${ttlLabel}) ${clock}`;
  let color = 'green';
  let bold = false;

  if (isExpiringSoon) {
    prefix = `⚠️ CACHE EXPIRE <60s (${ttlLabel}) ${clock}`;
    color = remainingSeconds <= 20 ? 'red' : 'yellow';
    bold = true;
  } else if (isExpired) {
    prefix = `❄️ Cache expiré (${ttlLabel}) 00:00`;
    color = 'gray';
    bold = false;
  }

  const line = `${prefix} | cache_read: ${readFmt} · cache_creation: ${writeFmt} (hit ${hitRatePercent}%)`;

  return {
    visible: true,
    ttlLabel,
    remainingSeconds,
    isWarm,
    isExpiringSoon,
    isExpired,
    hitRatePercent,
    color,
    bold,
    line,
  };
}

let countdownInterval: ReturnType<typeof setInterval> | null = null;

function stopCountdownTimer(): void {
  if (countdownInterval !== null) {
    clearInterval(countdownInterval);
    countdownInterval = null;
  }
}

export function registerPromptCacheControl(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    const envTtl = $.env.get('CLAUDE_CACHE_TTL');
    if (envTtl && (envTtl.toLowerCase() === '1h' || envTtl === '3600')) {
      promptCacheState.ttlSeconds = 3600;
    }

    stopCountdownTimer();
    countdownInterval = setInterval(() => {
      if (promptCacheState.lastRefreshAtMs === null) return;
      const status = computePromptCacheStatus(Date.now());
      if (
        status.isExpiringSoon &&
        promptCacheState.alertedExpiringForRefreshMs !== promptCacheState.lastRefreshAtMs
      ) {
        promptCacheState.alertedExpiringForRefreshMs = promptCacheState.lastRefreshAtMs;
        $.ui.toast(
          `⚠️ Prompt cache expire dans ${status.remainingSeconds}s (< 60s) — lancez votre tour ou /compact !`,
        );
      }
      if (status.remainingSeconds > 0 || Date.now() - promptCacheState.lastRefreshAtMs < (promptCacheState.ttlSeconds + 2) * 1000) {
        $.ui.invalidate('ui.render');
      }
    }, 1000);
    (countdownInterval as unknown as { unref?: () => void })?.unref?.();

    return next(e);
  });

  on('turn.complete', async ($, e, next) => {
    const envTtl = $.env.get('CLAUDE_CACHE_TTL');
    const usage = extractTurnUsage(e as Record<string, unknown>, envTtl);

    promptCacheState.ttlSeconds = usage.ttlSeconds;
    promptCacheState.lastCacheReadTokens = usage.cacheReadInputTokens;
    promptCacheState.lastCacheCreationTokens = usage.cacheCreationInputTokens;
    promptCacheState.sessionCacheReadTokens += usage.cacheReadInputTokens;
    promptCacheState.sessionCacheCreationTokens += usage.cacheCreationInputTokens;

    crewRuntimeState.totalCacheReadTokens = promptCacheState.sessionCacheReadTokens;
    crewRuntimeState.totalCacheCreationTokens = promptCacheState.sessionCacheCreationTokens;

    if (
      usage.cacheReadInputTokens > 0 ||
      usage.cacheCreationInputTokens > 0 ||
      usage.inputTokens > 0
    ) {
      promptCacheState.lastRefreshAtMs = Date.now();
      promptCacheState.alertedExpiringForRefreshMs = null;
    }

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('session.end', async (_$, e, next) => {
    stopCountdownTimer();
    return next(e);
  });

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.cache) return prev;

    const status = computePromptCacheStatus(Date.now());
    const { Box, Text } = $.ui.resolve(e);

    return Box({
      flexDirection: 'column',
      children: [
        ...(prev ? [prev] : []),
        Box({
          flexDirection: 'row',
          paddingX: 1,
          children: [
            Text({
              color: status.color,
              bold: status.bold,
              dimColor: status.remainingSeconds === 0 && promptCacheState.lastRefreshAtMs === null,
              children: [status.line],
            }),
          ],
        }),
      ],
    });
  });
}

export const register = registerPromptCacheControl;
