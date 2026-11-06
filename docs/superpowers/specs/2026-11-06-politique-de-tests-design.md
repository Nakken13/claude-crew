# Politique de tests adaptative — design

Date : 2026-11-06 · Statut : en attente de validation

## Intention et pourquoi

Aujourd'hui `/crew-close-task` (étape 5) crée à **chaque** clôture une
checklist `crew/TESTS/IA/` et/ou `crew/TESTS/DEV/`, sans seuil, sans réglage,
sans moyen de dire « pas de tests ici ». À cela s'ajoutent `requesting-code-review`
+ `simplify` imposés sur toute tâche « même perçue comme petite » (étape 3),
alors que le routage de `CLAUDE.md` les limite aux diffs > ~50 lignes ou aux
fichiers moteur/auth/hook : incohérence entre le skill et la règle.

Mesure sur un vrai projet (app mobile `app-voyageo`, usage intensif) :

| | Fichiers | Lignes | Cases cochées | Cases vides |
|---|---|---|---|---|
| Checklists DEV | 202 | 5 034 | 48 | 1 167 |
| Checklists IA | 53 | 1 045 | 38 | 227 |

Moins de 4 % des cases DEV jamais cochées : le coût principal est l'écriture
de checklists que personne ne relit, plus l'exécution inutile (émulateurs).
Le skill doit apporter de la productivité, pas surcharger contexte et tokens.

Le skill est utilisé par d'autres personnes, sur des projets inconnus : la
solution doit s'intégrer sans configuration lourde et reposer sur du
**jugement**, pas sur une table stack → niveau (une API peut être un
prototype jetable).

## Objectifs

- Réduire drastiquement les tokens dépensés en checklists/tests/revues sans
  valeur, sur n'importe quel type de projet.
- Garder (voire améliorer) la qualité : les vérifications qui comptent
  restent faites, et le sont par un vrai test dans le code quand c'est possible.
- Zéro question supplémentaire à l'utilisateur à l'init (hors cas hésitation,
  cf. §4).
- Jugement visible et corrigeable en une ligne.

## Non-objectifs

- Pas de table stack → niveau.
- Pas de parsing complexe : un seul petit fichier markdown non moteur
  (`TESTS_POLICY.md`), lu directement par les skills.
- Pas de suppression automatique des checklists existantes des projets
  (nettoyage éventuel = demande séparée).
- Ne change pas le modèle de dossiers `crew/` ni le batching.

## Anti-objectifs (échec même si « ça marche »)

- Un changement de comportement imposé en silence à un projet existant.
- Des questions posées après chaque tâche (la friction remplacerait le coût
  en tokens).
- Une grille qui laisse passer un défaut invisible et grave (auth, argent,
  données) sans aucune vérification.

## Design

### 1. Réglage : fichier dédié `crew/CLAUDE_CONTEXT/TESTS_POLICY.md`

**Décision validée par l'utilisateur** (suite au contrôle builder) : le réglage
vit dans un petit fichier **non moteur**, car `CLAUDE.md` est dans
`ENGINE_FILES_COMMON` (`crew/crew_update.py`) : un `CLAUDE.md` édité serait
classé `conflict` ou écrasé par `/crew-update`. `TESTS_POLICY.md` n'est pas
dans la liste moteur, donc `/crew-update` ne le modifie jamais ; il est créé
une fois (init ou update) et appartient ensuite à l'utilisateur. `CLAUDE.md`
(template et racine) contient seulement un pointeur d'une ligne vers ce
fichier dans le routage / la section TESTS ; les skills le lisent (≈10 lignes).

Contenu du fichier (quelques lignes) :

- `Niveau : none | light | full`
- `Zones risquées :` liste libre, dans les mots du projet.

Sens des niveaux (ils ne déplacent que le **seuil**) :

- `none` : jamais de checklist sauf demande explicite de l'utilisateur.
- `light` (**défaut universel**) : la grille de jugement (§3) décide tâche par tâche.
- `full` : comportement actuel (checklist à chaque clôture). Jamais déduit ni
  proposé par défaut ; s'active en éditant la ligne `Niveau` de
  `TESTS_POLICY.md`.

**Fichier absent = comportement historique (`full`)** (retour de revue) : les
skills étant livrés par le plugin, un projet existant sans `TESTS_POLICY.md`
ne doit pas changer de comportement en silence. Les skills le rappellent à la
clôture (« `/crew-update` pour l'activer ») ; `/crew-status` applique alors son
garde-fou.

### 2. Détermination à l'init et à l'update, sans question

`/crew-init` détecte déjà la stack (étape 2) et recueille la description du
projet (étape 3). L'IA **déduit** de cette description + du code :

- la posture : `light` par défaut ; `none` seulement si le projet est
  manifestement sans enjeu (ex. site vitrine, prototype) ;
- la liste des zones risquées (ce qui coûterait cher si ça cassait sans qu'on
  le voie : paiement, comptes/2FA, temps réel, permissions, migrations de
  données…), dans les mots du projet.

Seuls des **faits** sont détectés automatiquement : présence d'une suite de
tests, d'une CI, commande de test.

Le résultat est **affiché dans le rapport final** (« Tests : `light`. Zones
risquées : …. Pour changer, éditer la section Politique de tests de
`CLAUDE.md` »). Description trop vague → `light` sans zones, la grille décide.

`/crew-update` sur un projet existant : ajoute la section **sans rien écraser**,
déduite du `CLAUDE.md` et de l'historique, l'annonce explicitement et ne
l'applique jamais en silence ; `CHANGELOG` documente le changement.

### 3. Grille de jugement à la clôture (posture `light`)

L'IA se pose trois questions :

1. Si ça casse, le verrais-je tout de suite en utilisant normalement le produit ?
2. Si ça casse sans être vu, est-ce grave ou irréversible (argent, données,
   sécurité, perte d'utilisateur) ?
3. Est-ce déjà couvert par un test automatisé dans le code ?

Issues :

- Défaut invisible **et** grave **et** non couvert → checklist, **5 cases
  maximum**, uniquement pour ce que l'IA ne peut pas exécuter elle-même.
- Sinon → **aucune checklist**, une ligne dans `HISTORIQUE.md` :
  « Tests : aucun — <raison>, couvert par <test> » (jugement auditable).
- La vérification de la tâche est un vrai test dans le code (TDD, déjà prévu
  au routage), pas une checklist markdown à dérouler plus tard.
- Une tâche touchant une zone risquée déclarée est traitée comme « grave ».
- Hésitation réelle → §4.

### 4. Cas d'hésitation : demander à la fin de la tâche

Quand la grille ne tranche pas, l'IA pose **une** question courte à la fin de
la tâche : *« Tu veux que je vérifie, que tu vérifies, ou qu'on passe ? »*

- « Je vérifie » → l'IA exécute la vérification elle-même (émulateur compris
  si nécessaire) et note le résultat dans `HISTORIQUE`.
- « Je vérifie » (utilisateur) → checklist ≤ 5 cases, ou rien d'écrit si
  l'utilisateur dit qu'il le fait à l'œil.
- « On passe » → ligne `HISTORIQUE`, rien d'autre.

Garde-fou anti-friction : la question n'est posée que lorsque la grille est
réellement indécise, jamais par réflexe. Toute réponse peut être mémorisée
comme zone (ajout/retrait dans « Zones risquées ») pour ne pas reposer la
même question — à la discrétion du builder sur la forme exacte.

### 5. Revue de code et `simplify` alignés sur le routage

`/crew-close-task` étape 3 : `requesting-code-review` et `simplify` seulement
si le diff dépasse ~50 lignes ou touche un fichier moteur/auth/hook (règle
déjà écrite dans le routage de `CLAUDE.md`) ; sinon `verification-before-completion`
suffit. Supprimer la formulation « même perçue comme petite ».

### 6. Émulateur / exécution lourde

L'émulateur (ou toute vérif visuelle lourde) n'est lancé qu'en `full`, ou si
l'utilisateur le demande, ou s'il répond « je vérifie » au §4. La règle
actuelle du `CLAUDE.md` « frontend … validé visuellement avant de déclarer
fini » est reformulée en cohérence : applicable selon la posture, pas
systématiquement.

### 7. Garde-fou d'auto-correction dans `/crew-status`

`/crew-status` signale l'accumulation de cases jamais cochées (seuil à
définir par le builder, ex. > N cases vides ou ratio cochées/vides très bas) :
« 1 167 cases DEV jamais cochées : passer en `light` ? ». Lecture seule,
suggestion uniquement.

## Fichiers concernés (indicatif)

`skills/crew-close-task/SKILL.md`, `skills/crew-init/SKILL.md`,
`skills/crew-update/SKILL.md`, `skills/crew-status/SKILL.md`,
`template/CLAUDE.md` (section Politique de tests + routage/§ TESTS cohérents),
`CLAUDE.md` racine (miroir du template), `CHANGELOG.md`, éventuellement
`crew/crew_hook.py` si le calcul du garde-fou §7 s'y prête, et les tests
existants du hook.

## Laissé au builder

- Rédaction exacte de la section « Politique de tests » et de la grille.
- Seuil précis du garde-fou §7 et son calcul.
- Forme de la mémorisation des réponses du §4.
- Numéro de version / entrée de `CHANGELOG`.
- Tests automatisés de ce qui est testable (hook/status), sans en faire trop.

## Décisions prises par moi (à confirmer)

- Défaut `light` universel, `full` jamais proposé par défaut.
- `/crew-update` annonce la section plutôt que de l'appliquer en silence.
- Plafond de 5 cases par checklist.

### Précisions issues du contrôle builder (mes choix)

- **Hésitation (§4)** : la grille « ne tranche pas » uniquement quand le défaut
  serait invisible **et** que la gravité ou la couverture par un test est
  réellement incertaine. Elle ne s'applique pas dès qu'une réponse est « non ».
- **Moment de la question (§4)** : posée *avant* l'écriture de la ligne
  `HISTORIQUE` et de la checklist (étape 5 de `/crew-close-task`), pour ne
  jamais réécrire une ligne déjà posée.
- **Sans interlocuteur** (subagent, clôture lancée par `/crew-start`) :
  hésitation → checklist de 5 cases maximum (option prudente et peu coûteuse),
  jamais de question bloquante.
- **Revue de code et `simplify` (§5)** : indépendants du niveau. Seuil de
  ~50 lignes / fichier moteur-auth-hook pour `none`, `light` et `full`. Les
  niveaux ne pilotent que les checklists et la vérification visuelle/émulateur.
- **Vérification visuelle (§6)** : `none` = aucune sauf demande ; `light` =
  jugée par la grille ; `full` = toujours. En `none`, pas de ligne
  « Tests : » dans `HISTORIQUE` (zéro bookkeeping).
- **Garde-fou `/crew-status` (§7)** : texte du skill, pas de nouveau code.
  Compte les `- [ ]` vs `- [x]` dans `TESTS/IA` et `TESTS/DEV` (hors
  `TESTS_DONE`). Ne se déclenche que si le niveau est `full` ou absent
  (projet legacy), jamais en `light`/`none`, pour ne pas répéter la
  suggestion indéfiniment.
- **Inférence sans description (§2)** : lit seulement `CLAUDE.md`, `README` et
  les manifestes, et fait des `grep` ciblés dans `HISTORIQUE` (jamais une
  lecture entière, règle des 100 lignes). Sinon `light` sans zones.
