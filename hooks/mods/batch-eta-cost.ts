/**
 * Mod 10 — batch-eta-cost.ts (Estimation de fin)
 *
 * Calcule la vitesse moyenne d'exécution des tâches terminées du batch en cours
 * pour afficher une estimation temps réel :
 * `⏱️ Fin estimée : ~8 min (~45k tokens restants)`
 *
 * Persiste localement les métriques des tâches complétées dans
 * `.claude/crew-batch-metrics.json` (aucun appel LLM, 100% local / 0-token).
 */

import {
  crewRuntimeState,
  extractTurnUsage,
  filterCrewTaskSlugs,
  formatCompactTokens,
  formatEtaMinutes,
  joinPath,
  parseClaudeBatch,
  type ModRegistrar,
} from './shared.ts';

export const BATCH_METRICS_REL_PATH = '.claude/crew-batch-metrics.json';

export interface CompletedTaskMetric {
  slug: string;
  batchKey: string;
  durationMs: number;
  tokensUsed: number;
  completedAtMs: number;
}

export interface InFlightTaskMetric {
  slug: string;
  batchKey: string;
  startedAtMs: number;
  tokensUsed: number;
}

export interface BatchMetricsFile {
  completedTasks: CompletedTaskMetric[];
  inFlightTasks: Record<string, InFlightTaskMetric>;
}

export interface BatchEtaSnapshot {
  batchKey: string | null;
  remainingTasksCount: number;
  estimatedRemainingMs: number | null;
  estimatedRemainingTokens: number | null;
  isComplete: boolean;
  line: string | null;
}

export const batchEtaState: {
  metrics: BatchMetricsFile;
  snapshot: BatchEtaSnapshot;
} = {
  metrics: {
    completedTasks: [],
    inFlightTasks: {},
  },
  snapshot: {
    batchKey: null,
    remainingTasksCount: 0,
    estimatedRemainingMs: null,
    estimatedRemainingTokens: null,
    isComplete: false,
    line: null,
  },
};

export function parseBatchMetrics(jsonText: string): BatchMetricsFile {
  if (!jsonText || !jsonText.trim()) {
    return { completedTasks: [], inFlightTasks: {} };
  }
  try {
    const parsed = JSON.parse(jsonText) as Partial<BatchMetricsFile>;
    const completedTasks = Array.isArray(parsed.completedTasks)
      ? parsed.completedTasks.filter(
          (item): item is CompletedTaskMetric =>
            Boolean(
              item &&
                typeof item.slug === 'string' &&
                typeof item.durationMs === 'number' &&
                typeof item.tokensUsed === 'number',
            ),
        )
      : [];
    const inFlightTasks =
      parsed.inFlightTasks && typeof parsed.inFlightTasks === 'object'
        ? parsed.inFlightTasks
        : {};
    return { completedTasks, inFlightTasks };
  } catch {
    return { completedTasks: [], inFlightTasks: {} };
  }
}

export function computeBatchEta(params: {
  batchKey: string | null;
  batchTotalTasks: number;
  batchDoneTasks: number;
  activeTaskSlug: string | null;
  activeTaskDone: number;
  activeTaskTotal: number;
  metrics: BatchMetricsFile;
  nowMs?: number;
}): BatchEtaSnapshot {
  const {
    batchKey,
    batchTotalTasks,
    batchDoneTasks,
    activeTaskSlug,
    activeTaskDone,
    activeTaskTotal,
    metrics,
    nowMs = Date.now(),
  } = params;

  if (!batchKey || batchTotalTasks <= 0) {
    return {
      batchKey: null,
      remainingTasksCount: 0,
      estimatedRemainingMs: null,
      estimatedRemainingTokens: null,
      isComplete: false,
      line: null,
    };
  }

  const remainingWholeTasks = Math.max(0, batchTotalTasks - batchDoneTasks);
  if (remainingWholeTasks === 0) {
    const doneLine = '⏱️ Fin estimée : terminé ✅ (0 token restant)';
    return {
      batchKey,
      remainingTasksCount: 0,
      estimatedRemainingMs: 0,
      estimatedRemainingTokens: 0,
      isComplete: true,
      line: doneLine,
    };
  }

  // Prefer completed tasks from the active batch; fall back to historical completed tasks across batches
  const batchCompleted = metrics.completedTasks.filter((t) => t.batchKey === batchKey);
  const samplePool = batchCompleted.length > 0 ? batchCompleted : metrics.completedTasks;

  let avgDurationMs: number | null = null;
  let avgTokens: number | null = null;

  if (samplePool.length > 0) {
    const sumDur = samplePool.reduce((acc, t) => acc + Math.max(1_000, t.durationMs), 0);
    const sumTok = samplePool.reduce((acc, t) => acc + Math.max(0, t.tokensUsed), 0);
    avgDurationMs = sumDur / samplePool.length;
    avgTokens = sumTok / samplePool.length;
  } else if (activeTaskSlug && activeTaskDone > 0 && activeTaskTotal > 0) {
    // Bootstrap estimate from current task's checkbox progress when 0 tasks in batch are finished yet
    const inflight = metrics.inFlightTasks[activeTaskSlug];
    if (inflight) {
      const ratio = activeTaskDone / activeTaskTotal;
      const elapsed = Math.max(5_000, nowMs - inflight.startedAtMs);
      avgDurationMs = elapsed / ratio;
      avgTokens = inflight.tokensUsed / ratio;
    }
  }

  if (avgDurationMs === null || avgTokens === null) {
    return {
      batchKey,
      remainingTasksCount: remainingWholeTasks,
      estimatedRemainingMs: null,
      estimatedRemainingTokens: null,
      isComplete: false,
      line: `⏱️ Fin estimée : calibration (${remainingWholeTasks} tâche(s) restante(s))`,
    };
  }

  // Account for partial completion of the currently running task
  const activeTaskFractionDone =
    activeTaskSlug && activeTaskTotal > 0
      ? Math.min(0.95, Math.max(0, activeTaskDone / activeTaskTotal))
      : 0;
  const effectiveRemainingTasks = Math.max(0.05, remainingWholeTasks - activeTaskFractionDone);

  const estimatedRemainingMs = Math.round(avgDurationMs * effectiveRemainingTasks);
  const estimatedRemainingTokens = Math.round(avgTokens * effectiveRemainingTasks);

  const etaFmt = formatEtaMinutes(estimatedRemainingMs);
  const tokFmt = formatCompactTokens(estimatedRemainingTokens);
  const line = `⏱️ Fin estimée : ${etaFmt} (~${tokFmt} tokens restants)`;

  return {
    batchKey,
    remainingTasksCount: remainingWholeTasks,
    estimatedRemainingMs,
    estimatedRemainingTokens,
    isComplete: false,
    line,
  };
}

export function registerBatchEtaCost(on: ModRegistrar): void {
  on('session.start', async ($, e, next) => {
    const projectRoot = $.env.get('CLAUDE_PROJECT_DIR') || crewRuntimeState.projectRoot || '.';
    const mainRoot = crewRuntimeState.mainRoot || projectRoot;

    const rawMetrics = await $.fs
      .read(joinPath(mainRoot, BATCH_METRICS_REL_PATH))
      .catch(() => '');
    batchEtaState.metrics = parseBatchMetrics(rawMetrics);

    const nowMs = Date.now();
    if (
      crewRuntimeState.activeTaskSlug &&
      !batchEtaState.metrics.inFlightTasks[crewRuntimeState.activeTaskSlug]
    ) {
      batchEtaState.metrics.inFlightTasks[crewRuntimeState.activeTaskSlug] = {
        slug: crewRuntimeState.activeTaskSlug,
        batchKey: crewRuntimeState.activeBatchKey || 'default',
        startedAtMs: nowMs,
        tokensUsed: 0,
      };
    }

    const snap = computeBatchEta({
      batchKey: crewRuntimeState.activeBatchKey,
      batchTotalTasks: crewRuntimeState.activeBatchTotalTasks,
      batchDoneTasks: crewRuntimeState.activeBatchDoneTasks,
      activeTaskSlug: crewRuntimeState.activeTaskSlug,
      activeTaskDone: crewRuntimeState.activeTaskDone,
      activeTaskTotal: crewRuntimeState.activeTaskTotal,
      metrics: batchEtaState.metrics,
      nowMs,
    });
    batchEtaState.snapshot = snap;
    crewRuntimeState.etaSummaryLine = snap.line;

    return next(e);
  });

  on('turn.complete', async ($, e, next) => {
    const projectRoot = crewRuntimeState.projectRoot || '.';
    const mainRoot = crewRuntimeState.mainRoot || projectRoot;
    const nowMs = Date.now();

    const rawMetrics = await $.fs
      .read(joinPath(mainRoot, BATCH_METRICS_REL_PATH))
      .catch(() => '');
    const metrics = parseBatchMetrics(rawMetrics);
    // Merge in-memory metrics so nothing is lost if disk write was skipped
    for (const [slug, inf] of Object.entries(batchEtaState.metrics.inFlightTasks)) {
      if (!metrics.inFlightTasks[slug]) metrics.inFlightTasks[slug] = inf;
    }

    const usage = extractTurnUsage(e as Record<string, unknown>);
    const turnTokens =
      usage.inputTokens +
      usage.outputTokens +
      usage.cacheCreationInputTokens +
      Math.round(usage.cacheReadInputTokens * 0.1);

    const activeSlug = crewRuntimeState.activeTaskSlug;
    const activeBatch = crewRuntimeState.activeBatchKey || 'default';

    if (activeSlug) {
      const existing = metrics.inFlightTasks[activeSlug] || {
        slug: activeSlug,
        batchKey: activeBatch,
        startedAtMs: crewRuntimeState.sessionStartedAtMs || nowMs,
        tokensUsed: 0,
      };
      existing.batchKey = activeBatch;
      existing.tokensUsed += turnTokens;
      metrics.inFlightTasks[activeSlug] = existing;
    }

    // Check if any previously in-flight task has been closed (struck in CLAUDE_BATCH.md or removed from open dirs)
    const batchMd =
      (await $.fs.read(joinPath(projectRoot, 'crew/CLAUDE_BATCH.md')).catch(() => '')) ||
      (await $.fs.read(joinPath(mainRoot, 'crew/CLAUDE_BATCH.md')).catch(() => ''));
    const parsedBatch = parseClaudeBatch(batchMd);
    const closedInBatch = new Set<string>();
    for (const sec of parsedBatch.sections) {
      for (const t of sec.tasks) {
        if (t.closed) closedInBatch.add(t.slug);
      }
    }

    const openSlugs = new Set<string>([
      ...filterCrewTaskSlugs(await $.fs.list(joinPath(mainRoot, 'crew/TODO')).catch(() => [])),
      ...filterCrewTaskSlugs(
        await $.fs.list(joinPath(mainRoot, 'crew/CURRENT_TASKS')).catch(() => []),
      ),
      ...(projectRoot !== mainRoot
        ? filterCrewTaskSlugs(
            await $.fs.list(joinPath(projectRoot, 'crew/CURRENT_TASKS')).catch(() => []),
          )
        : []),
      ...filterCrewTaskSlugs(await $.fs.list(joinPath(mainRoot, 'crew/PAUSED')).catch(() => [])),
    ]);

    let dirty = Boolean(activeSlug && turnTokens > 0);
    for (const [slug, inflight] of Object.entries({ ...metrics.inFlightTasks })) {
      if (closedInBatch.has(slug) || !openSlugs.has(slug)) {
        metrics.completedTasks.push({
          slug,
          batchKey: inflight.batchKey,
          durationMs: Math.max(1_000, nowMs - inflight.startedAtMs),
          tokensUsed: Math.max(turnTokens, inflight.tokensUsed),
          completedAtMs: nowMs,
        });
        if (metrics.completedTasks.length > 100) {
          metrics.completedTasks.splice(0, metrics.completedTasks.length - 100);
        }
        delete metrics.inFlightTasks[slug];
        dirty = true;
      }
    }

    batchEtaState.metrics = metrics;
    if (dirty) {
      await $.fs
        .write(joinPath(mainRoot, BATCH_METRICS_REL_PATH), JSON.stringify(metrics, null, 2) + '\n')
        .catch(() => undefined);
    }

    const snap = computeBatchEta({
      batchKey: crewRuntimeState.activeBatchKey,
      batchTotalTasks: crewRuntimeState.activeBatchTotalTasks,
      batchDoneTasks: crewRuntimeState.activeBatchDoneTasks,
      activeTaskSlug: crewRuntimeState.activeTaskSlug,
      activeTaskDone: crewRuntimeState.activeTaskDone,
      activeTaskTotal: crewRuntimeState.activeTaskTotal,
      metrics,
      nowMs,
    });
    batchEtaState.snapshot = snap;
    crewRuntimeState.etaSummaryLine = snap.line;

    $.ui.invalidate('ui.render');
    return next(e);
  });
}

export const register = registerBatchEtaCost;
