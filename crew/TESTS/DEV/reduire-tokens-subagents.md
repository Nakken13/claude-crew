# reduire-tokens-subagents

Validation des changements visant à réduire la consommation de tokens des
dispatches de personas/subagents crew.

## 🖱️ Manuel (dev)

- [ ] 🖱️ Relire les 4 personas (`.claude/agents/architect.md`, `ceo.md`,
      `manager.md`, `comms.md`) et confirmer que la nouvelle ligne
      « grep ciblé d'abord » reste cohérente en ton/format avec le reste du
      fichier — jugement subjectif de style, pas outillable.
- [ ] 🖱️ Sur quelques sessions crew réelles à venir, observer si le seuil de
      contexte différencié (~100k agents d'implémentation / ~150k personas
      read-only, `CLAUDE.md` § Efficience de contexte) réduit effectivement
      les coupures/relances par rapport à l'ancien seuil unique ~150k, ou si
      le seuil resserré déclenche trop de cycles recap/relaunch (tradeoff
      documenté mais non mesurable a priori).
