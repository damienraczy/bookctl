# 01 — Architecture du pipeline de génération de manuel

> Document de référence. Fige les choix d'architecture. Remplace toute décision
> antérieure qui le contredirait.
>
> Rédigé le 9 octobre 2026.

---

## 0. Position du problème

Deux constats fondent le projet :

1. **Aucun outil existant ne fait le travail** clé en main. Les briques existent
   (génération, optimisation de prompts, linter), mais leur assemblage pour de la
   non-fiction technique **en français** n'est livré nulle part.
2. **Le maillon manquant est l'ordre de travail**, plus que le prompt ou les
   contraintes. Générer un chapitre d'un bloc (one-shot) oblige le modèle à
   maintenir trop d'états en interne et produit les défauts classiques :
   répétitions, concepts définis plusieurs fois, terminologie qui dérive,
   niveaux d'abstraction variables. La qualité atteignable par les prompts est
   *plafonnée* par la façon dont on séquence la production.

> Le constat 2 est une **hypothèse de travail**. Elle est à vérifier par une
> comparaison mesurée avec le one-shot avant d'investir dans les axes 2 et 3.

Ce document pose trois axes, par ordre de priorité :

- **Axe 1 — Ordre incrémental** (le mécanisme, prioritaire) ;
- **Axe 2 — Chaîne de qualité à trois étages** (Vale → System 1 → correcteur LLM) ;
- **Axe 3 — Deux boucles DSPy** (calibrer le juge, puis optimiser le rédacteur).

---

## 1. Principes directeurs

### 1.1 Le pilier est l'état versionné, pas un modèle

Le pilier est **l'ordre incrémental + l'état versionné en fichiers texte**. Le
versionnement des artefacts est assuré par `bookctl` (historique de révisions et
manifeste, `03-cli.md` § 8), **pas par git** : les travaux de rédaction sont des
données personnelles et n'entrent pas dans le dépôt (`PRINCIPES.md` § 2).
System 1, DSPy et Vale sont des composants branchés sur cet état. Aucun
composant ne détient seul la cohérence du livre.

### 1.2 Le contexte descendu est toujours un extrait dérivé

À chaque étape, le modèle reçoit une **tranche** de l'étage supérieur, jamais
« le livre entier ». Le contexte transmis à la rédaction d'une section est
l'extrait du plan détaillé qui la concerne, pas le manuscrit en cours.

### 1.3 Chaque étage est un point de reprise corrigible

L'humain peut corriger un artefact à n'importe quel étage L(n), puis relancer
l'aval L(n+1)… **sans régénérer l'amont L(0)…L(n-1)**. Les dépendances forment
un graphe explicite (manifeste, `03-cli.md` § 8), pas une chaîne qu'on refait
en entier.

### 1.4 Aucun jugement ne repose sur le modèle qui a rédigé

Le rédacteur, le juge (System 1) et le correcteur (LLM) sont des modèles
distincts. Le feedback de qualité n'est jamais produit par le modèle dont on
évalue la sortie.

### 1.5 Modèles dans le cloud

Les LLM génératifs sont appelés dans le cloud (Ollama Cloud en priorité), via
DSPy (`02-agents.md` § 13). System 1 est servi par une API cloud (Jev) ou, sur
le poste de développement seulement, par Ollama local (`04-primitives-system1.md`
§ 1).

---

## 2. Axe 1 — Ordre incrémental (L0 → L10)

### 2.1 Les étapes

Chaque étape est une **primitive de rédaction**, nommée par un verbe d'action.
C'est l'unité d'exécution et d'invocation. Le conducteur est **l'utilisateur**,
qui déclenche chaque étape par une commande explicite.

La table des étapes (action, commande, composant, artefact, gate humaine,
primitive System 1) a une **source de vérité unique** : `02-agents.md` § 4.

La granularité de contexte de chaque étape est l'extrait dérivé de l'étape
supérieure, jamais « le livre entier ».

### 2.2 Format d'état entre étapes

Chaque artefact est un fichier texte versionné par `bookctl`. La disposition
d'un espace de travail et d'un sujet est définie dans `03-cli.md` § 2 (**source
de vérité**).

Le format de travail est **Markdown**. PDF, EPUB et DOCX sont des cibles
d'export (Pandoc, L10), jamais le format de rédaction.

Les artefacts **transverses à l'outil** se répartissent ainsi :

- dans le **dépôt** (code public) : prompts, règles Vale, liste des motifs ;
- dans l'**espace de travail** (hors dépôt) : dataset de calibration, rapports
  de calibration, parce qu'ils sont construits à partir des textes de
  l'utilisateur (`05-dataset-calibration.md` § 1.2).

### 2.3 Le conducteur et les exécuteurs

L'ordre incrémental est **conduit par l'utilisateur** via le CLI `bookctl`
(`03-cli.md`) : une commande = une primitive appliquée à une cible explicite,
jamais d'enchaînement spontané d'étapes. L'agent (LLM) sous chaque commande est
un **exécuteur** : il lit les artefacts amont, produit l'artefact de l'étape, la
gate rend son verdict, l'exécution s'arrête.

Un hôte agentique conversationnel est **optionnel** : il peut appeler le CLI,
mais il n'orchestre rien.

---

## 3. Axe 2 — Chaîne de qualité à trois étages

Le linter (binaire) et le correcteur LLM (génératif, coûteux) laissent un trou :
le **jugement gradué**. System 1 le comble :

```
Vale (binaire)  →  System 1 (probabilités, routé)  →  Correcteur LLM
   motifs codés        jugement contextuel               réécrit
```

### 3.1 Les rôles, strictement délimités

| Couche | Outil | Nature | Rôle | Ne fait pas |
|---|---|---|---|---|
| Relecture déterministe | **Vale** + règles FR | binaire, regex | signale les motifs codés, zéro biais LLM | juger le contexte, graduer |
| Jugement calibré | **System 1** | probabiliste, typé | juger en contexte, router avec un signal de certitude | expliquer, réécrire |
| Correction | **Correcteur** (LLM) | génératif, coûteux | corriger, réécrire, expliquer | être la barrière unique |

Vale et System 1 sont **complémentaires**, pas redondants : Vale ne détecte que
les chaînes exactes qu'on a programmées (fragile aux variantes, maintenance
lourde) ; System 1 juge le motif en contexte, y compris ses variantes.

### 3.2 Primitives System 1

Trois primitives (`choice`, `score`, `noul`), sans génération de texte. Contrat,
limites par fournisseur et signal de certitude : `04-primitives-system1.md`
(**source de vérité**). Point clé : `choice` et `score` renvoient une
`confidence` ; `noul` ne renvoie qu'une probabilité, dont la certitude se lit
par bandes de seuils.

### 3.3 Routage par certitude

- **Certitude forte** → verdict automatique de la gate (`pass` ou `fail`).
- **Certitude faible** → verdict `escalate` (vers l'humain ou le correcteur).

La gate produit un **verdict**, jamais une action : la décision suivante
appartient toujours à l'utilisateur (`02-agents.md` § 1). Le correcteur LLM
n'est donc plus appelé systématiquement, mais quand l'utilisateur le décide,
notamment sur `escalate`.

### 3.4 Risque structurant

**La calibration en français n'est pas démontrée.** Les modèles System 1 sont
entraînés surtout en anglais ; l'éditeur de Jev indique lui-même que l'anglais
est la langue où la précision est la meilleure. Comprendre le français ≠ être
calibré sur des jugements éditoriaux français. Tant que la calibration n'est pas
mesurée, System 1 est un **levier potentiel**, pas une couche acquise.

---

## 4. Axe 3 — Deux boucles DSPy

DSPy n'orchestre rien et ne persiste rien. C'est le moteur de module unitaire
(signatures typées, modules, optimisation GEPA contre une métrique). Son rôle
est double, **dans cet ordre** (détail : `06-boucles-dspy.md`) :

### 4.1 Boucle 1 — Calibrer le juge (System 1)

- **Dataset** : textes français étiquetés humainement sur les motifs
  (`05-dataset-calibration.md`).
- **Métrique** : erreur de calibration (Brier par exemple, ECE en rapport), pas
  la justesse brute.
- **Ce que GEPA optimise** : la formulation des `instructions`/`criteria` des
  questions System 1.
- **Choix du modèle System 1** : boucle externe (chaque modèle candidat reçoit
  son instruction optimisée, on compare les calibrations). GEPA optimise du
  texte, il ne choisit pas de modèle.
- **Coût** : les appels System 1 sont peu coûteux ; le `reflection_lm` de GEPA
  (LLM fort) est le poste de coût principal.

### 4.2 Boucle 2 — Optimiser le rédacteur

Une fois la boucle 1 stabilisée, le jugement System 1 calibré entre dans la
métrique de la boucle 2 : System 1 + violations Vale + fidélité terminologique +
couverture du plan. Le feedback textuel vient d'un `reflection_lm` **distinct**
du rédacteur.

### 4.3 Le paradoxe résolu

Le cercle « GEPA a besoin d'une métrique fiable → la métrique serait System 1 →
mais System 1 n'est pas calibré » est brisé en **inversant l'ordre** : on
utilise DSPy pour rendre System 1 fiable, puis il devient une métrique.

---

## 5. Vue d'ensemble

```
                 [ORDRE INCRÉMENTAL — le pilier, conduit par l'utilisateur]
  L0 cadrage → L1 documentation → L2 plan directeur → L3 plan détaillé
       → L4 premier jet → L5 validation technique → L6 transitions → L7 harmonisation
       → L8 style → L9 contrôle final → L10 assemblage
             [état versionné par bookctl + allers-retours, l'utilisateur décide]

                         [AXE QUALITÉ — trois étages]
  Vale (motifs codés)  →  System 1 (jugement contextuel, routé)  →  Correcteur LLM

                         [AXE DSPy — deux boucles]
  Boucle 1 : GEPA calibre les questions System 1 contre le dataset FR
  Boucle 2 : GEPA optimise le rédacteur contre System 1 + Vale + terminologie + couverture
```

---

## 6. Ce qui est « complément, pas pilier »

- **System 1** : juge gradué et routeur. Jamais rédacteur, jamais seul.
- **DSPy** : moteur des agents LLM, puis optimiseur des questions System 1 et du
  rédacteur. Jamais orchestrateur, jamais persistance.
- **Vale** : première barrière déterministe. System 1 ne la remplace pas.
- **L'Auditeur** (LLM, contrôle final) : propose des constats globaux ; seuls
  ceux que System 1 confirme comptent. Il ne décide jamais (`02-agents.md` § 6.1).
- **L'agent** : exécute une commande à la fois, lit et écrit l'état. Il
  **n'orchestre pas** : l'utilisateur conduit la séquence L0→L10.

---

## 7. Préalable bloquant et ordre de mise en œuvre

La boucle 1 exige un **dataset français étiqueté**. C'est le livrable qui
déverrouille les deux boucles. Il sert deux fois : calibration de System 1 et
source des règles Vale.

| Phase | Contenu | Prérequis |
|---|---|---|
| **P0** | CLI `bookctl` + Vale + règles FR + agents LLM (DSPy, prompts manuels) + ordre incrémental | — |
| **P1** | Protocole de mesure de calibration System 1 sur le dataset FR | dataset FR construit |
| **P2** | Boucle 1 (GEPA calibre les questions System 1) | calibration mesurable |
| **P3** | Boucle 2 (GEPA optimise le rédacteur) | jugement System 1 fiable |

### Documents de spécification

- `specs/PRINCIPES.md` — socle de développement.
- `specs/02-agents.md` — agents, coordination, table des étapes.
- `specs/03-cli.md` — `bookctl` : espace de travail, commandes, cibles, sorties, versionnement.
- `specs/04-primitives-system1.md` — contrat System 1, questions par étape, routage.
- `specs/05-dataset-calibration.md` — dataset FR et mesure de calibration.
- `specs/06-boucles-dspy.md` — les deux boucles DSPy.
