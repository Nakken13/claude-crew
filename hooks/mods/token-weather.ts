/**
 * Mod 2 — token-weather.ts
 *
 * Jauge météo compacte sur 1 ligne :
 * `☀️ Clear` → `⛅ Cloudy` → `⛈️ Storm` → `🚨 Compact soon`
 * basée sur le ratio de la fenêtre de contexte.
 *
 * Seuils calibrés sur la politique d'efficience de contexte de `crew-mates`
 * (seuil d'alerte crew à 150k / 200k = 75%) :
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
  const safeWindow = contextWindow > 0 ? contextWindow : 200_000;
  const safeTokens = Math.max(0, contextTokens);
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
      $.ui.toast(`🚨 Fenêtre de contexte à ${snap.percent}% — lancez /compact ou /clear bientôt.`);
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
      color: snap.color,
      bold: snap.bold,
      text: snap.line,
    });
  });
}

export const register = registerTokenWeather;
