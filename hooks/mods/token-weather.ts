/**
 * Mod 2 — token-weather.ts
 *
 * Compact weather gauge on 1 line:
 * `☀️ Clear` → `⛅ Cloudy` → `⛈️ Storm` → `🚨 Compact soon`
 * based on the context window ratio.
 *
 * Thresholds calibrated on the `crew-mates` context-efficiency policy
 * (crew alert threshold at 150k / 200k = 75%):
 * - < 50%  : ☀️ Clear
 * - 50-74% : ⛅ Cloudy
 * - 75-89% : ⛈️ Storm
 * - >= 90% : 🚨 Compact soon
 *
 * 100% local / 0-token.
 */

import {
  crewRuntimeState,
  crewUiState,
  extractTurnUsage,
  formatCompactTokens,
  renderBar,
  type ModRegistrar,
  addBandSegments,
} from './shared.ts';

const CREW_RESET_TOKENS = 150_000;
const WEATHER_PINK = '#ff69b4';

export type WeatherStageLabel = '☀️ Clear' | '⛅ Cloudy' | '⛈️ Storm' | '🚨 Compact soon';

export interface TokenWeatherSnapshot {
  label: WeatherStageLabel;
  ratio: number;
  percent: number;
  contextTokens: number;
  contextWindow: number;
  color: string;
  bold: boolean;
  line: string;
}

export interface TokenWeatherState {
  contextTokens: number;
  contextWindow: number;
  warnedCompactSoon: boolean;
}

export const tokenWeatherState: TokenWeatherState = {
  contextTokens: 0,
  contextWindow: 200_000,
  warnedCompactSoon: false,
};

export function computeTokenWeather(
  contextTokens = tokenWeatherState.contextTokens,
  contextWindow = tokenWeatherState.contextWindow,
): TokenWeatherSnapshot {
  const rawWindow = contextWindow > 0 ? contextWindow : 200_000;
  // The gauge always targets at most the crew reset threshold (150k), whatever the real window.
  const safeWindow = Math.min(rawWindow, CREW_RESET_TOKENS);
  const safeTokens = Number.isFinite(contextTokens) ? Math.max(0, contextTokens) : 0;
  const ratio = Math.min(1, safeTokens / safeWindow);
  const percent = Math.floor(ratio * 100);

  let label: WeatherStageLabel = '☀️ Clear';
  let color = 'green';
  let bold = false;

  if (ratio >= 0.9) {
    label = '🚨 Compact soon';
    color = 'red';
    bold = true;
  } else if (ratio >= 0.75) {
    label = '⛈️ Storm';
    color = 'yellow';
    bold = false;
  } else if (ratio >= 0.5) {
    label = '⛅ Cloudy';
    color = 'cyan';
    bold = false;
  }

  const bar = renderBar(ratio, 8);
  const usedFmt = formatCompactTokens(safeTokens);
  const maxFmt = formatCompactTokens(safeWindow);
  const line = `${label} ${bar} ${usedFmt}/${maxFmt} (${percent}%)`;

  return {
    label,
    ratio,
    percent,
    contextTokens: safeTokens,
    contextWindow: safeWindow,
    color,
    bold,
    line,
  };
}

/** Short version for the band: `☀️19% 39k/200k` (tier emoji, percentage, tokens). */
export function formatWeatherCompact(snap: TokenWeatherSnapshot = computeTokenWeather()): string {
  return `${snap.label.split(' ')[0]} ${snap.percent}%  ${formatCompactTokens(snap.contextTokens)}/${formatCompactTokens(snap.contextWindow)}`;
}

export function registerTokenWeather(on: ModRegistrar): void {
  on('turn.complete', async ($, e, next) => {
    const usage = extractTurnUsage(e as Record<string, unknown>);
    if (usage.contextTokens > 0) {
      tokenWeatherState.contextTokens = usage.contextTokens;
      tokenWeatherState.contextWindow = usage.contextWindow;
      crewRuntimeState.lastContextTokens = usage.contextTokens;
      crewRuntimeState.lastContextWindow = usage.contextWindow;
    }

    const snap = computeTokenWeather();
    if (snap.label === '🚨 Compact soon' && !tokenWeatherState.warnedCompactSoon) {
      tokenWeatherState.warnedCompactSoon = true;
      $.ui.toast(`🚨 Context window at ${snap.percent}% — run /compact or /clear soon.`);
    } else if (snap.ratio < 0.75) {
      tokenWeatherState.warnedCompactSoon = false;
    }

    $.ui.invalidate('ui.render');
    return next(e);
  });

  on('ui.render', { component: 'AbovePrompt' }, async (_$, e, next) => {
    const prev = await next(e);
    if (!crewUiState.bands.weather) return prev;

    const snap = computeTokenWeather();
    return addBandSegments(prev, {
      slot: 'right',
      color: WEATHER_PINK,
      bold: snap.bold,
      text: formatWeatherCompact(snap),
    });
  });
}

export const register = registerTokenWeather;
