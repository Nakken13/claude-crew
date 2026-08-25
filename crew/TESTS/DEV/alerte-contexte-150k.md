# alerte-contexte-150k

Validation du seuil de contexte 150k (`CLAUDE.md` § Reset de session) en
usage réel — items non outillables par l'IA seule.

## 🖱️ Manuel (DEV)

- [ ] 🖱️ Session réelle qui dépasse 150k tokens de contexte estimé :
      confirmer que le hook Stop émet effectivement l'avertissement
      `[contexte]` (visible côté outillage/logs du hook, pas dans la
      réponse assistant) au bon moment, sans faux positif avant le seuil
      ni faux négatif après. Jugement humain requis sur la justesse de
      l'estimation (proxy `usage.input_tokens` + cache), pas seulement sa
      présence.
- [ ] 🖱️ Vérifier qu'un subagent (`Agent` tool) dont le contexte dépasse
      ~150k applique réellement la consigne textuelle de `CLAUDE.md`
      (auto-arrêt, recap bullet points, relance d'un nouvel agent) plutôt
      que de continuer à grossir son propre contexte — non automatisable :
      aucun mécanisme technique ne force ce comportement (cf. limitation
      documentée dans `CLAUDE.md` § Reset de session), seule l'observation
      d'un cas réel permet de juger si la consigne est suivie et si le
      format du recap est utilisable pour la relance.
- [ ] 🖱️ Revue qualitative : le format de recap attendu (bullet points —
      travail fait, état courant, fichiers touchés, découvertes clés
      bloquantes) est-il suffisant en pratique pour qu'un nouvel agent
      reprenne sans perte d'information notable ? Ajuster la formulation
      dans `CLAUDE.md` si un cas réel montre un recap insuffisant.
