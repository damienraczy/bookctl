# 02 — Agents, communication et coordination

> Document de spécification. Définit la couche qui porte l'ordre incrémental
> (axe 1 de `01-architecture.md`) : les étapes, les agents, leur communication,
> leur coordination, et le contrôle par l'utilisateur.
>
> Rédigé le 9 octobre 2026.

---

## 0. Position

`01-architecture.md` a établi que le pilier est l'**ordre incrémental + l'état
versionné**. Ce document spécifie *comment* : qui sont les agents, comment ils
communiquent, comment ils se coordonnent, et **comment l'utilisateur garde le
contrôle**.

---

## 1. Le conducteur est l'utilisateur

### 1.1 Principe

Le conducteur du pipeline **n'est pas un agent**. C'est l'utilisateur. Le
système n'est **jamais** exécuté en boîte noire par un agent qui décide seul.

Trois règles structurelles :

1. **[S02-01] Une commande = une primitive, appliquée à une cible explicite.**
   Jamais de « génère le manuel ». `draft 4.2` rédige la section 4.2. Une cible
   chapitre ou plage (`draft 4`, `draft 1..3`) exécute la **même** primitive
   sur chaque section visée, une par une, avec un verdict par section
   (`03-cli.md` § 5.5). Une commande n'enchaîne jamais deux étapes différentes.
2. **[S02-02] Pas d'initiative propre.** Une étape terminée s'arrête et rend
   son verdict. Elle ne lance **jamais** l'étape suivante. **Exception** : `redo
   --stop` exécute en lot l'étape refaite et son aval, parce que ce lot est
   *ordonné nommément* par l'utilisateur ; il s'arrête à la première gate
   humaine rencontrée (§ 11).
3. **[S02-03] L'artefact est le contrat de contrôle.** À chaque étape,
   l'utilisateur voit l'artefact produit **et** le verdict (violations Vale +
   jugement System 1), puis décide.

### 1.2 Le modèle de contrôle

```
UTILISATEUR ──(commande : "draft 5.1")──▶ Rédacteur ──▶ artefact + verdict
      ▲                                                       │
      │                                                       ▼
      └──(décision : accept / retry / resume / redo)──────────┘
```

> L'agent optimise une opération ; l'utilisateur possède le chemin.

---

## 2. La surface de contrôle : le CLI

Le contrôle est exposé par le CLI `bookctl`, choisi pour sa **testabilité** :
chaque commande est un pas isolé, rejouable, scriptable, comparable. L'agent est
le *moteur* sous chaque commande, jamais le pilote. La grammaire, les commandes,
les cibles et les options sont spécifiées dans `03-cli.md` (**source de vérité
du CLI**).

---

## 3. Décision structurante : le fichier est le message

### 3.1 Le défaut à éviter

Si les agents échangent essentiellement des prompts et du texte, on obtient une
chaîne de LLM sophistiquée mais fragile.

### 3.2 La règle

**[S02-04] Les agents ne se parlent pas entre eux.** Ils ne s'envoient ni
prompts ni texte. Ils **lisent et écrivent l'état** du sujet (`book/`,
`state/`). Le « message » est l'**artefact produit + son verdict**, déposé dans
le système de fichiers.

### 3.3 Pourquoi

| Propriété | Effet |
|---|---|
| Reproductibilité | chaque artefact est traçable à ses entrées (manifeste) |
| Reprise après interruption | on relit l'état, on ne « se rappelle » pas |
| Cohérence | aucun agent ne mémorise, tous lisent la même source de vérité |
| Auditabilité | chaque transition est une révision consultable (historique `bookctl`) |
| Agilité | corriger un artefact = relancer l'aval, sans toucher l'amont |

---

## 4. Les étapes (L0 → L11) — table de référence

**Cette table est la source de vérité des étapes.** Les autres specs y
renvoient et ne la recopient pas.

| # | Étape | Action | Commande | Composant | Artefact | Gate H | System 1 (`04` § 4) | Statut |
|---|---|---|---|---|---|---|---|---|
| L0 | Cadrage | délimiter | `init` | Planificateur | `book/constitution.md` | — | — | |
| L1 | Documentation | collecter | `collect` | Recherche | `book/research/` | — | — | *optionnel* |
| L2 | Plan directeur | structurer | `outline` | Planificateur | `book/outline.md` | **H1** | `choice` | |
| L3 | Intentions | assigner | `assign` | Planificateur | `book/contracts/NN.md` | — | — | |
| L4 | Plan détaillé | décomposer | `detail` | Planificateur | `book/plans/NN.md` | **H2** | `score` | |
| L5 | Premier jet | rédiger | `draft` | Rédacteur | `book/chapters/NN/<cible>.md` | — | `noul`, `score` | |
| L6 | Validation technique | valider | `review` | **SME (humain)** | `book/reviews/NN.md` | **H3** | — | *optionnel* |
| L7 | Transitions | lier | `link` | Intégrateur | raccords dans `book/chapters/` | — | — | |
| L8 | Harmonisation | unifier | `unify` | Intégrateur | `book/chapters/` + `state/` (termes, crossrefs) | — | `noul` (lot) | |
| L9 | Correction stylistique | polir | `polish` | Correcteur + Vale | `book/chapters/NN/<cible>.md` | **H4** | `score` | |
| L10 | Contrôle final | verrouiller | `lock` | **System 1 + Vale + compteurs** | `reports/lock.md` | **H5** | `noul` (lot) | |
| L11 | Assemblage | générer | `build` | **Outil (Pandoc)** | `exports/` : PDF / EPUB / DOCX | — | — | *optionnel* |

Remarques :

- **L6** est une revue factuelle par un expert métier (SME) : un *checkpoint
  humain*. La commande `review` prépare le gabarit d'annotations
  (`03-cli.md` § 3.1) ; System 1 peut pré-filtrer, pas valider le fond.
- **L10** n'a pas d'agent LLM : la non-régression est jugée par System 1, Vale
  et des compteurs déterministes, contre la référence enregistrée à
  l'acceptation de L5 (`03-cli.md` § 3.2).
- **L11** est une compilation déterministe : un *outil*, pas un agent.
- **L8** modifie les chapitres (alignement des termes, renvois) **et** l'état
  éditorial (`state/concepts.yml`, `state/crossrefs.yml`). Il dépend de *tous*
  les chapitres concernés.
- Les gates humaines sur L0 et L3 sont en discussion (§ 14).

---

## 5. Natures de composant (tout n'est pas un agent)

| Nature | Exemples | Modèle | Rôle |
|---|---|---|---|
| **Agent LLM** | Planificateur, Recherche, Rédacteur, Intégrateur, Correcteur | génératif (cloud, via DSPy) | produire / réécrire du texte |
| **Juge System 1** | jugement de style, de cohérence, de non-régression | décisionnel | juger / router avec un signal de certitude |
| **Outil déterministe** | Vale, compteurs, Pandoc | aucun | barrière, mesure, export |
| **Checkpoint humain** | SME, gates H | humain | décisions de fond non déléguables |
| **DSPy hors-ligne** | boucles GEPA | hors-ligne | compiler des instructions, calibrer le juge |

Seuls les agents LLM sont des *agents* au sens fort (ils génèrent). Les autres
sont des *composants* branchés entre eux.

---

## 6. Roster minimal d'agents LLM

**Le moins d'agents possible** : chaque agent LLM est un risque de cohérence
supplémentaire. Un agent = une responsabilité, pas une étape fine.

| Agent | Étapes | Responsabilité | Rôle de modèle (`params.yml`) |
|---|---|---|---|
| **Planificateur** | L0, L2, L3, L4 | cadrer, structurer, assigner, décomposer | `plan` |
| **Recherche** *(optionnel)* | L1 | collecter la matière | `plan` |
| **Rédacteur** | L5 | rédiger le premier jet | `write` |
| **Intégrateur** | L7, L8 | lier les transitions, unifier la cohérence | `integrate` |
| **Correcteur** | L9 (et sur `escalate`) | polir selon les règles FR | `rewrite` |

Séparations clés :

- **Rédacteur ≠ Correcteur** : le rédacteur produit, le correcteur révise ce
  que la gate a signalé (non-auto-évaluation).
- **Planificateur ≠ Rédacteur** : l'un décide la structure, l'autre exécute une
  tranche.

---

## 7. Contrat d'agent — l'unité de coordination

Chaque agent est défini par un **contrat** à trois champs :

```
Agent X
├── entrées        : fichiers à lire + tranche exacte (jamais le livre entier)
├── sorties        : artefact écrit + rapport (ce qui a été fait, ce qui reste)
└── critère d'acceptation : la gate (Vale / System 1 / humain)
```

Exemple — **Rédacteur** (L5), cible `5.1` :

```yaml
entrées:
  - book/plans/05.md              # tranche du plan détaillé : section 5.1 seulement
  - book/terminology.yml          # lexique contrôlé
  - book/style_system.md          # instruction du rédacteur (manuelle en P0, compilée en P3)
  - state/concepts.yml            # concepts déjà introduits (pour ne pas redéfinir)
sorties:
  - book/chapters/05/5.1.md       # la section rédigée
  - reports/draft/5.1.md          # rapport : choix faits, ambiguïtés signalées
critère_d_acceptation:
  - Vale (aucune violation de niveau error)
  - System 1 (questions de L5, 04 § 4.2)
```

**[S02-05]** Le contrat rend chaque agent **remplaçable et testable
isolément** : on peut faire tourner le Rédacteur seul sur une tranche.

---

## 8. Exécution d'une étape : la micro-boucle

**[S02-06]** Chaque étape L(n) s'exécute comme une micro-boucle à trois temps,
**toujours sur commande explicite** :

```
L(n):  [action] ──▶ artefact ──▶ gate ──▶ verdict { pass | fail | escalate }
        (agent)      (fichier)            puis décision de l'utilisateur
```

La gate rend un **verdict** (`pass` / `fail` / `escalate`). L'utilisateur prend
ensuite une **décision** (`accept` / `retry` / `resume` / `redo`, § 9). Les deux
vocabulaires sont disjoints.

---

## 9. Les quatre décisions de l'utilisateur

| Décision | Commande | Sémantique | Correspondance agile |
|---|---|---|---|
| **accepter** | `accept` | marquer l'artefact accepté ; ne lance rien | validation |
| **répéter** | `retry` | réexécuter la primitive (même étape, même cible), avec instructions éventuelles | itération |
| **reprendre** | `resume` | repasser la gate après modification manuelle de l'artefact | reprise manuelle |
| **refaire** | `redo` | refaire une étape amont, avec re-propagation bornée | revue de plan |

**[S02-07] Limite de répétition.** Une même cible ne peut pas être répétée plus
de `gates.max_retries` fois sur la même étape (`params.yml`). Au-delà, la
commande refuse (code `4`) et invite à `resume` après correction manuelle ou à
`redo` d'une étape amont.

### 9.1 Les deux niveaux d'allers-retours

**Niveau 1 — dans une étape (`retry`, `resume`).** On corrige une section sans
toucher au plan ni aux autres sections.

**Niveau 2 — entre étapes (`redo`).** On refait une étape amont ; l'aval devient
périmé (manifeste) et peut être re-propagé **sans régénérer l'amont antérieur** :

```
redo detail 4 --stop polish  →  re-propage draft → link → unify → polish (chapitre 4)
                              →  s'arrête à la gate H2 de detail si elle n'est pas acceptée
                              →  NE re-propage PAS init, outline, assign
```

---

## 10. Checkpoints humains (gates H)

L'utilisateur accepte chaque artefact à son rythme. En complément, cinq **gates
humaines obligatoires** verrouillent les points où valider à la main est
structurel.

**[S02-08]** À ces étapes, le CLI **refuse** qu'un artefact non accepté serve
d'entrée à l'aval (code `4`).

**[S02-09]** L'`accept` d'une gate H exige une confirmation interactive sur un
terminal (TTY) et consigne l'auteur dans le journal d'audit. C'est une barrière
de **traçabilité**, pas de sécurité : elle empêche un script de franchir la gate
par inadvertance.

| Gate | Étape | Ce que l'utilisateur valide |
|---|---|---|
| H1 | L2 | la table des matières (avant tout le reste) |
| H2 | L4 | le plan détaillé d'un chapitre (avant la rédaction) |
| H3 | L6 | la validation technique (SME, si applicable) |
| H4 | L9 | le chapitre poli (avant le contrôle final) |
| H5 | L10 | le livre complet |

Les autres étapes peuvent être enchaînées par script (chaque commande rend son
verdict et son code de retour).

---

## 11. Séparation des modèles

| Rôle | Modèle | Raison |
|---|---|---|
| Rédacteur | LLM `write` | produit le texte |
| Juge | System 1 | évalue sans générer, pas de complaisance |
| Correcteur | LLM `rewrite` (≠ `write`) | réécrit ce que la gate a signalé |
| Reflection (DSPy) | LLM `reflect` (≠ `write`, ≠ `rewrite`) | produit le feedback textuel de GEPA |

**[S02-10]** Au chargement de `params.yml`, `bookctl` vérifie que `write`,
`rewrite` et `reflect` désignent des modèles distincts ; sinon exception.

---

## 12. Connexion à DSPy

**[S02-11]** Les agents LLM sont des **modules DSPy** (signature + `Predict` ou
`ChainOfThought`). Leurs modèles sont déclarés dans `params.yml` (stock de
modèles + profils, `03-cli.md` § 2.4) et instanciés par `dspy.LM`
(`doc-tools/llm-cloud.md`).

| Agent / composant | Artefact DSPy qu'il consomme |
|---|---|
| Rédacteur | `book/style_system.md` = instruction optimisée par la boucle 2 |
| Juge (System 1) | formulations des questions (`prompt/system1/`) + modèle retenu, issus de la boucle 1 |

**Transition P0 → P2/P3** : tant que les boucles ne sont pas compilées, le
Rédacteur consomme une instruction écrite à la main dans `prompt/`
(`*_system.md`/`*_user.md`), et System 1 n'est **pas branché** (gate = Vale +
humain). Les artefacts compilés remplacent ces instructions en P2/P3.

Le `reflection_lm` n'est **pas** un agent du roster : il tourne hors-ligne
pendant la compilation GEPA.

---

## 13. Intégration dans un hôte

Le CLI est le socle. Un hôte agentique conversationnel peut appeler `bookctl`,
mais il n'orchestre rien : l'utilisateur reste le conducteur. Le critère de
choix d'un hôte éventuel est sa capacité à exécuter une gate déterministe entre
deux étapes ; ce choix ne conditionne pas le CLI.

---

## 14. Points ouverts

- Seuils de routage System 1 : à calibrer par la boucle 1 (`06-boucles-dspy.md`).
- Granularité exacte des tranches de contexte par étape.
- Gates humaines sur L0 (cadrage) et L3 (intentions).
