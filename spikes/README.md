# Spikes

Essais courts et **jetables** qui répondent à une question précise avant
d'écrire le code de `bookctl` qui en dépend (`specs/01-architecture.md` § 7,
phase S).

## Règles

- **Un dossier par spike**, nommé `<id>_<sujet>` (ex. `b5_ollama_dspy`).
- Chaque spike a un `README.md` qui fixe, **avant** de lancer l'essai : la
  question, le protocole, le critère de décision.
- Le code d'un spike suit `specs/PRINCIPES.md` : paramètres dans son
  `params.yml`, prompts en `.md` (`*_system.md` / `*_user.md`), secrets dans
  `~/.env`, docstrings. Il n'est **pas** importé par `bookctl`.
- **Résultats** : dans `out/` du spike, **jamais versionné** (ils peuvent
  contenir des textes de l'auteur et des réponses de modèles).
- La **décision** issue d'un spike est reportée dans les specs ou la doc
  concernées, le jour même.
- Chaque spike a son propre environnement Python (`uv`), indépendant de celui
  de `bookctl`.

## Spikes

| Id | Dossier | Question |
|---|---|---|
| B5 | `b5_ollama_dspy/` | Comment appeler les modèles Ollama Cloud depuis DSPy (noms, voie d'accès, `think`) ? |
