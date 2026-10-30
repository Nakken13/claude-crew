# token-weather : `computeTokenWeather(NaN)` affiche `NaN/200k (NaN%)`

Statut : ✅ résolu (garde `Number.isFinite`, test étendu NaN/Infinity)

## Contexte

Trouvé en vérifiant `verif-mod-token-weather`. `computeTokenWeather` fait
`Math.max(0, contextTokens)` : `Math.max(0, NaN)` vaut `NaN`, donc ratio,
pourcentage et ligne deviennent `NaN` (`☀️ Clear [░░░░░░░░] NaN/200k (NaN%)`).

## Gravité

Faible : le chemin événementiel est protégé (`extractTurnUsage` ne laisse
passer que des nombres finis, et `contextTokens > 0` est testé avant
d'écrire l'état). Seul un appel direct avec NaN est touché (régression
future, autre appelant).

## Piste

Garde `Number.isFinite(contextTokens) ? Math.max(0, contextTokens) : 0` dans
`hooks/mods/token-weather.ts`. Le test `météo : seuils … jamais de NaN`
(`hooks/mods.test.ts`) couvre le cas une fois corrigé.
