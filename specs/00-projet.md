# 00 — Le projet `bookctl`

> Document d'entrée des spécifications. Explique ce qu'est le projet, à qui il
> s'adresse, ce qu'il fait et ne fait pas, et comment lire les autres specs.
> Il ne porte pas d'exigence testable : celles-ci sont dans les documents 01 à
> 06 et dans `PRINCIPES.md`.
>
> Auteur : Damien Raczy.

---

## 1. En une phrase

`bookctl` est un outil en ligne de commande qui aide un auteur à rédiger des documents longs en français (manuels techniques, essais, guides méthodologiques, et autres documents longs structurés) à l’aide de modèles de langage. Il structure l’écriture étape par étape, maintient l’auteur aux commandes du processus et mesure la qualité du texte produit à chaque étape.

---

## 2. Le problème

Écrire un document long et structuré avec un LLM pose trois difficultés.

1. **Générer d'un bloc dégrade le texte.** Demandé en une fois, un chapitre
   accumule des défauts typiques : répétitions, concepts définis plusieurs fois,
   terminologie qui dérive, niveaux d'abstraction qui varient d'une page à
   l'autre. Le modèle doit tenir trop de choses en tête à la fois. Améliorer le
   prompt ne suffit pas : c'est l'**ordre de travail** qui limite la qualité.
2. **Le français est mal outillé.** Les outils qui repèrent les tics d'écriture
   des LLM (« il convient de », ternaires creux, formules éculées) existent
   surtout pour l'anglais. Les chaînes complètes de production de livres
   existent, mais pour la fiction, et pas en français.
3. **Juger un texte avec un LLM est fragile.** Un LLM qui évalue un texte
   produit par un LLM tend à le trouver bon, et ne rend pas deux fois le même
   verdict. Sans mesure fiable, on ne sait pas si le texte s'améliore.

---

## 3. La réponse

Trois axes, par ordre de priorité.

### 3.1 Axe 1 — L'ordre de travail

L'ouvrage est produit **par étapes successives**, chacune reposant sur la
précédente : cadrage, plan, plan détaillé de chaque chapitre, premier jet
section par section, transitions, harmonisation, correction stylistique,
contrôle final, assemblage. À chaque étape, le modèle ne reçoit qu'un **extrait**
de l'étape supérieure, jamais l'ouvrage entier. Chaque étape produit un fichier
que l'auteur peut relire, corriger et faire refaire, sans régénérer ce qui
précède.

### 3.2 Axe 2 — Une chaîne qualité à trois étages

| Étage | Outil | Ce qu'il fait |
|---|---|---|
| 1 | **Vale** | repère de façon déterministe les formes figées interdites (règles écrites à la main) |
| 2 | **System 1** | juge les motifs en contexte, variantes comprises, avec une probabilité ; dit quand il est sûr et quand il ne l'est pas |
| 3 | **Correcteur** (LLM) | réécrit ce qui a été signalé |

System 1 est une famille de modèles qui **ne génèrent pas de texte** : ils
répondent à des questions typées (« ce passage contient-il un ternaire
creux ? ») par des probabilités. Ils ne sont donc pas complaisants, et leurs
réponses sont stables.

### 3.3 Axe 3 — Optimiser par la mesure

Avec **DSPy** et son optimiseur **GEPA** : d'abord rendre le juge System 1
fiable en français (le **calibrer** sur des exemples étiquetés par l'auteur),
puis seulement l'utiliser pour optimiser les instructions du rédacteur.

---

## 4. Pour qui

| Profil | Rôle dans `bookctl` |
|---|---|
| **Auteur** d'un document long et structuré, premièrement en français | conduit chaque étape, valide les points de contrôle, décide de tout |
| **Expert métier** (SME), facultatif | relit le fond d'un chapitre et l'annote |
| **Développeur** de l'outil | fait évoluer le code, les prompts, les règles et la calibration |

`bookctl` est un **outil d'auteur**, pas un générateur d'ouvrages en un clic.

---

## 5. Périmètre

### 5.1 Ce que fait `bookctl`

- organiser le travail en **sujets** (un ouvrage = un sujet) dans un **espace de
  travail** local ;
- exécuter chaque étape de rédaction sur commande, sur une cible précise
  (chapitre, section, sous-section) ;
- contrôler chaque production (Vale, System 1, compteurs) et rendre un
  **verdict** lisible par l'humain et par un script ;
- garder l'**historique** de chaque artefact et savoir ce qui doit être refait
  quand un artefact amont change ;
- **journaliser** chaque appel de modèle (traçabilité) ;
- assembler l'ouvrage en EPUB, DOCX et PDF.

### 5.2 Ce que `bookctl` ne fait pas

- **Écrire l'ouvrage seul.** Aucune commande n'enchaîne les étapes de
  elle-même ; aucun agent ne décide à la place de l'auteur.
- **Valider le fond.** L'exactitude conceptuelle et technique relève de l'auteur et de
  l'expert métier.
- **Faire de la fiction.** Le cadre (plan, contrats de chapitre, terminologie
  contrôlée, renvois) est celui de documents longs non-fiction.
- **Faire tourner des LLM en local.** Les LLM sont appelés dans le cloud.
- **Publier.** Il produit des fichiers d'export ; la diffusion est hors
  périmètre.

---

## 6. Parcours type

L'auteur se place une fois dans son espace de travail, puis tout se fait par
commandes.

1. **Créer le sujet** : `bookctl subject new manuel-ia`, puis
   `bookctl subject use manuel-ia`.
2. **Cadrer** : `bookctl init --instructions brief.md` produit la constitution
   de l'ouvrage (thèse, audience, périmètre, voix). L'auteur la relit, la corrige
   au besoin et l'**accepte** : c'est un point de contrôle obligatoire.
3. **Structurer** : `bookctl outline` produit la table des matières, acceptée
   à son tour.
4. **Détailler** : `bookctl detail 3` produit le contrat et le plan détaillé du
   chapitre 3, acceptés avant toute rédaction.
5. **Rédiger** : `bookctl draft 3.1`, `bookctl draft 3.2`… Chaque section
   revient avec son verdict. L'auteur accepte, fait refaire avec une consigne
   (`bookctl retry 3.2 --message "…"`), ou corrige à la main puis reprend.
6. **Faire relire** (facultatif) : `bookctl review 3` prépare la fiche
   d'annotations de l'expert métier.
7. **Lier, harmoniser, polir** : `link`, `unify`, `polish`, chapitre par
   chapitre.
8. **Contrôler** : `bookctl lock` vérifie que la correction n'a pas dégradé le
   texte et fait chercher par un Auditeur les problèmes d'ensemble ; seuls les
   constats confirmés par System 1 comptent. L'auteur valide l'ouvrage complet.
9. **Assembler** : `bookctl build` produit EPUB, DOCX et PDF.

À tout moment, `bookctl redo` refait une étape amont (par exemple le plan d'un
chapitre) ; ce qui en dépend est signalé comme à refaire.

---

## 7. Principes structurants

| Principe | Conséquence |
|---|---|
| **L'auteur conduit** | une commande = une étape sur une cible ; six points de contrôle humains obligatoires |
| **Le fichier est le message** | les agents ne se parlent pas ; ils lisent et écrivent des fichiers texte |
| **Extrait, jamais le tout** | chaque agent reçoit une tranche définie de l'ouvrage |
| **Aucun modèle ne juge son propre texte** | rédacteur, correcteur, auditeur, juge et optimiseur sont des modèles distincts |
| **Mesurer plutôt que croire** | chaque production a un verdict ; la qualité se suit par des indicateurs |
| **Échouer explicitement** | aucune valeur par défaut silencieuse, aucun repli caché |
| **Les textes de l'auteur restent chez l'auteur** | le dépôt public ne contient que l'outil |

Le socle de développement (TDD, paramètres, secrets, documentation) est dans
`PRINCIPES.md`.

---

## 8. Technologies

| Rôle | Technologie | Note |
|---|---|---|
| Interface | CLI Python (Typer) | `doc-tools/cli-typer.md` |
| Agents LLM | modules **DSPy**, modèles **Ollama Cloud** déclarés dans `params.yml` | `doc-tools/dspy.md`, `doc-tools/llm-cloud.md` |
| Juge | **System 1** : Jev (TypeSafe, cloud) ; Ollama local sur le poste de développement | `doc-tools/system-one.md` |
| Relecture déterministe | **Vale** + règles françaises | `doc-tools/vale.md` |
| Optimisation | **GEPA** (via DSPy et en mode autonome) | `doc-tools/gepa.md` |
| Assemblage | **Pandoc** | `doc-tools/pandoc.md` |
| Versionnement du code | git, dépôt public en liste blanche | `doc-tools/git.md` |

---

## 9. Données et confidentialité

- Les manuscrits, consignes, rapports, journaux et datasets construits à partir
  des textes de l'auteur sont des **données personnelles**. Ils restent dans
  l'espace de travail local et **n'entrent jamais dans git**.
- `bookctl` versionne lui-même ces travaux (historique de révisions).
- Les textes sont envoyés aux fournisseurs de modèles cloud configurés
  (Ollama Cloud, TypeSafe) le temps du traitement : le choix des fournisseurs
  dans `params.yml` est aussi un choix de confidentialité.
- Les clés d'API restent dans `~/.env`.

---

## 10. Hypothèse, risques et critères de succès

**Hypothèse centrale** : produire par étapes donne un meilleur texte que
générer d'un bloc. Elle est **vérifiée en premier**, sur deux chapitres d'un
ouvrage pilote, avant d'écrire le code qui en dépend.

**Risques principaux** :

- la calibration de System 1 en français n'est pas démontrée (les modèles sont
  entraînés surtout en anglais) ;
- l'écosystème System 1 et les API de DSPy et GEPA évoluent vite ;
- le pipeline complet est ambitieux pour une petite équipe.

D'où un ordre de réalisation qui livre un ouvrage **sans dépendre** des parties
risquées : System 1 et les boucles DSPy améliorent le résultat, ils ne le
conditionnent pas.

**Critère de succès principal** : le **taux de réécriture humaine**, la part
du texte que l'auteur modifie entre le premier jet et la version acceptée, doit
être nettement plus bas qu'avec une génération d'un bloc. Les autres
indicateurs sont dans `01-architecture.md` § 8.

---

## 11. Statut

Spécifications v1.0, sans code. La feuille de route (spikes, version minimale,
pipeline complet, calibration, boucles d'optimisation) est dans
`01-architecture.md` § 7.

---

## 12. Lexique

| Terme | Définition |
|---|---|
| **Espace de travail** | répertoire local où l'auteur se place ; contient `params.yml`, `config.yml` et les sujets |
| **Ouvrage** | document long et structuré, non-fiction : manuel technique, documentation, essai, guide méthodologique… |
| **Sujet** | un ouvrage, désigné par son nom |
| **Étape** (L0 à L10) | une primitive de rédaction, invoquée par une commande (`init`, `draft`…) |
| **Cible** | ce sur quoi porte une commande : chapitre `3`, section `3.2`, sous-section `3.2.1`, ou plage `3..5` |
| **Artefact** | fichier produit par une étape (constitution, plan, section…) |
| **Gate** | contrôle passé par un artefact après sa production (Vale, compteurs, System 1) |
| **Verdict** | résultat de la gate : `pass`, `fail` ou `escalate` |
| **Décision** | choix de l'auteur après un verdict : `accept`, `retry`, `resume`, `redo` |
| **Gate humaine** (H0 à H5) | point de contrôle où l'acceptation explicite de l'auteur est obligatoire |
| **Constitution** | thèse, audience, périmètre et voix de l'ouvrage (étape L0) |
| **Contrat de chapitre** | rôle, apport, prérequis et limites d'un chapitre, en tête de son plan détaillé |
| **System 1** | modèle de décision qui répond à des questions typées par des probabilités, sans générer de texte |
| **Calibration** | accord entre les probabilités annoncées par le juge et la réalité observée |
| **Escalade** | verdict rendu quand le juge n'est pas assez sûr : l'auteur tranche |
| **Auditeur** | agent LLM du contrôle final qui propose des constats ; System 1 les confirme ou non |
| **Périmé** (`stale`) | artefact dont une entrée a changé depuis sa production, à refaire ou reprendre |
| **Sujet pilote** | ouvrage réel sur lequel le projet est conduit et évalué |

---

## 13. Lire les spécifications

| Document | Contenu | À lire si… |
|---|---|---|
| `00-projet.md` | ce document | on découvre le projet |
| `PRINCIPES.md` | socle de développement : TDD, paramètres, secrets, git, documents | on écrit du code ou de la documentation |
| `01-architecture.md` | les trois axes, feuille de route, indicateurs | on veut comprendre les choix |
| `02-agents.md` | étapes, agents, gates humaines, tranches de contexte | on travaille sur un agent ou une étape |
| `03-cli.md` | espace de travail, commandes, cibles, verdicts, versionnement | on implémente ou utilise le CLI |
| `04-primitives-system1.md` | contrat System 1, questions, routage | on travaille sur le juge |
| `05-dataset-calibration.md` | dataset français, mesure de calibration | on construit le dataset |
| `06-boucles-dspy.md` | les deux boucles d'optimisation | on travaille sur DSPy et GEPA |

Les notes techniques sur les outils sont dans `doc-tools/`.

---

## 14. Licence

Code sous PolyForm Noncommercial 1.0.0, documentation sous CC BY-NC 4.0 :
distribution et modification non commerciales autorisées en conservant le nom
de l'auteur ; tout usage commercial requiert l'accord écrit de Damien Raczy
(`NOTICE`).
