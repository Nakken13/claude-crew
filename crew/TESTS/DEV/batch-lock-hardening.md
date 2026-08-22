# batch-lock-hardening

Validation des 3 quick wins de durcissement du verrouillage batch multi-session
(voir `crew/CLAUDE_CONTEXT/HISTORIQUE.md`). Le pendant automatisable est dans
`../IA/batch-lock-hardening.md`.

## 🖱️ Manuel / multi-session réelle (DEV)

- [ ] 🖱️ Créer deux tâches dans un même batch `CLAUDE_BATCH.md` (`Zone :`
      définie), lancer deux vraies sessions Claude Code, démarrer la tâche A
      dans la session 1, puis quasi immédiatement (décalage de quelques
      secondes) tenter de démarrer la tâche voisine B dans la session 2 —
      vérifier que la session 2 se fait bloquer soit au `PreToolUse` (avant
      le `git mv`, message `[batch] ... collision detectee`), soit au pire
      au `Stop` suivant, mais pas silencieusement.
- [ ] 🖱️ Même scénario avec deux batchs différents dont les `Zone :` se
      chevauchent (au lieu de deux tâches du même batch) : vérifier que la
      session 2 est bloquée une fois les deux batchs verrouillés par des
      sessions différentes (`check_zone_overlaps` cross-session).
- [ ] 🖱️ Vérifier que `crew/CLAUDE_CONTEXT/BATCH_LOCKS.md` reflète bien en
      temps réel les verrous 🔒/🔓 pendant que les deux sessions tournent.
