# Politique de tests

Fichier appartenant au projet : `/crew-update` ne le modifie jamais. Source
unique des règles de tests, lue par `/crew-close-task` et `/crew-status`.
Éditer librement.

Niveau : light

Zones risquées : (aucune renseignée)

## Niveaux

- `none` : jamais de checklist ni de ligne « Tests : », aucune vérification
  visuelle/émulateur, sauf demande explicite.
- `light` (défaut) : la grille ci-dessous décide tâche par tâche.
- `full` : une checklist à chaque clôture et vérification visuelle
  systématique (comportement historique).

Le niveau ne pilote que les checklists et la vérification visuelle/émulateur.

## Zones risquées

Ce qui coûterait cher si ça cassait sans qu'on le voie (paiement,
comptes/2FA, temps réel, permissions, migrations de données…).
`/crew-init` ou `/crew-update` remplacent la ligne `Zones risquées :` par la
liste déduite du projet, dans ses mots. Toucher une zone = « grave ».

## Grille (niveau `light`)

À la clôture, trois questions :

1. Si ça casse, le verrait-on tout de suite en utilisant normalement le produit ?
2. Sinon, est-ce grave ou irréversible (argent, données, sécurité, perte
   d'utilisateur, zone risquée) ?
3. Est-ce déjà couvert par un test automatisé dans le code ?

- Invisible **ET** grave **ET** non couvert → checklist `TESTS/IA` ou
  `TESTS/DEV`, **5 cases maximum**, seulement ce que l'IA ne peut pas
  exécuter elle-même.
- Sinon → aucun fichier ; une ligne dans `HISTORIQUE.md` :
  `Tests : aucun — <raison>, couvert par <test>`.

## Hésitation (niveau `light`)

Seulement si le défaut serait invisible **et** que la gravité ou la couverture
est réellement incertaine : poser **une** question courte, avant d'écrire
l'`HISTORIQUE` ou la checklist — « Je vérifie, tu vérifies, ou on passe ? ».

- « Je vérifie » → l'IA exécute (émulateur compris si nécessaire) et note le
  résultat dans `HISTORIQUE`.
- « Tu vérifies » → checklist ≤ 5 cases, ou rien d'écrit si c'est à l'œil.
- « On passe » → ligne `HISTORIQUE`, rien d'autre.

Sans interlocuteur (subagent, clôture enchaînée par `/crew-start`) :
checklist ≤ 5 cases, jamais de question bloquante. L'émulateur ou toute
vérification visuelle lourde ne se lance qu'en `full`, sur demande, ou après
« je vérifie ».
