# 03 — Spécification du CLI `bookctl`

> Document de spécification. Définit la surface de contrôle utilisateur :
> espace de travail, sujets, grammaire, commandes, cibles, options, sorties,
> versionnement des artefacts et contrat de test.
>
> Rédigé le 9 octobre 2026.

---

## 0. Position

Le CLI est la surface de contrôle **première** (`02-agents.md` § 2). Il est
choisi pour sa **testabilité** : chaque commande est un pas isolé, rejouable,
scriptable, comparable. L'utilisateur est le conducteur ; le CLI traduit chaque
commande en une seule primitive, jamais en séquence autonome d'étapes.

---

## 1. Grammaire

Syntaxe de type **POSIX** :

```
bookctl [options-globales] <command> [target] [options]
```

- **`command`** : un verbe (action, décision ou gestion), obligatoire, en anglais.
- **`target`** : la cible (chapitre / section / sous-section / plage), optionnelle.
  Omission → cible courante (§ 6).
- **`options`** : options de la commande. Les options globales sont acceptées
  avant ou après la commande.

### Options globales

| Option | Effet |
|---|---|
| `--subject <nom>` / `-s <nom>` | cibler un sujet par son nom pour cette commande |
| `--message <texte>` / `-m <texte>` | instruction complémentaire inline (§ 4.3) |
| `--instructions <fichier>` / `-i <fichier>` | instruction complémentaire depuis un fichier (§ 4.3) |
| `--json` | verdict en JSON (lisible par une machine) |
| `--help` / `-h` | aide |
| `--version` / `-V` | version |

---

## 2. Espace de travail et sujets

### 2.1 L'espace de travail

L'**espace de travail** est le répertoire dans lequel l'utilisateur se place
(`cd`) pour travailler. Il contient les paramètres, l'état de travail et les
sujets. Une fois dedans, **aucun autre `cd` n'est nécessaire** : on change de
sujet par commande, pas en changeant de répertoire.

- **[S03-01]** `bookctl` s'exécute depuis la racine de l'espace de travail. Si
  `params.yml` ou `config.yml` sont absents du répertoire courant, la commande
  échoue (code `4`) avec un message qui l'indique. `bookctl` ne remonte pas
  l'arborescence et ne cherche pas ailleurs.
- **[S03-02]** `bookctl workspace init` crée `config.yml` et un `params.yml` à
  partir du modèle `params.sample.yml` du dépôt, dans le répertoire courant, et
  refuse d'écraser un fichier existant.

L'espace de travail est un répertoire **hors dépôt git** : il contient des
données personnelles (`PRINCIPES.md` § 2).

### 2.2 Disposition (source de vérité)

```
<espace de travail>/
├── params.yml              # paramètres d'exécution (§ 2.4) — unique
├── config.yml              # état de travail : sujet courant, cibles courantes
├── dataset/                # dataset de calibration (05-dataset-calibration.md)
├── reports/                # rapports transverses (calibration, boucles DSPy)
└── <nom du sujet>/
    ├── book/
    │   ├── constitution.md       # L0 cadrage
    │   ├── research/             # L1 documentation (optionnel)
    │   ├── outline.md            # L2 plan directeur
    │   ├── plans/NN.md           # L3 contrat + plan détaillé de chapitre
    │   ├── chapters/NN/<cible>.md  # L4, puis L6/L7/L8 : un fichier par cible (§ 5.2)
    │   ├── reviews/NN.md         # L5 annotations SME
    │   ├── style_system.md       # instruction du rédacteur (compilée par DSPy en P3)
    │   └── terminology.yml       # lexique contrôlé
    ├── state/
    │   ├── manifest.yml          # dépendances, empreintes, statuts (§ 8)
    │   ├── concepts.yml          # concepts définis, ordre d'introduction
    │   ├── crossrefs.yml         # renvois internes
    │   ├── baseline/             # mesures de référence pour L9 (§ 3.2)
    │   └── audit/                # journal des appels modèles (§ 9)
    ├── history/                  # révisions des artefacts (§ 8)
    ├── reports/                  # rapports d'étape (draft/, lock.md…)
    └── exports/                  # sorties de L10
```

`NN` = numéro de chapitre sur deux chiffres (`03`). Les cibles (`3.2`) ne sont
jamais complétées par des zéros.

**Rien n'est caché** : tout est en fichiers texte lisibles et éditables, à la
racine, en clair. Aucun fichier ni dossier caché.

Rôles des deux fichiers racine :

- **`config.yml`** : l'état de travail (sujet courant, cible courante **par
  sujet**, dernière action par sujet). Modifié par `bookctl`.
- **`params.yml`** : les paramètres d'exécution. Seule source des réglages
  (`PRINCIPES.md`). Il ne contient aucun secret.

### 2.3 Gestion des sujets

Un **sujet** est une œuvre distincte (`manuel-ia`, `cuisine`), désignée **par
son nom**. Aucun état n'est partagé entre sujets.

| Commande | Effet |
|---|---|
| `bookctl subject new <nom>` | créer le sujet `<nom>` et son arborescence dans l'espace de travail |
| `bookctl subject list` | lister les sujets **par nom** |
| `bookctl subject show` | afficher le sujet courant **par nom** et sa cible courante |
| `bookctl subject use <nom>` | définir le sujet courant (écrit dans `config.yml`) |

**[S03-03]** Un nom de sujet est un identifiant simple (`[a-z0-9][a-z0-9-]*`) ;
il ne peut pas être un nom réservé de l'espace (`dataset`, `reports`).

### 2.4 `params.yml`

Un seul fichier, à la racine de l'espace de travail. Structure (exemple complet
dans `params.sample.yml` du dépôt) :

```yaml
# Stock de modèles : nom logique → fournisseur, identifiant, variables d'environnement
models:
  glm-flash:
    provider: ollama                # Ollama Cloud
    name: glm-5.3-flash:cloud
    url: OLLAMA_CLOUD_URL           # NOM de la variable d'environnement, pas la valeur
    api_key: OLLAMA_API_KEY
    timeout: 120

# Profils : rôles → modèles du stock
.profils:
  standard: &standard
    llm:
      plan: deepseek-pro
      write: glm-flash
      integrate: deepseek-pro
      rewrite: mistral-large
      audit: deepseek-pro
      reflect: deepseek-pro

llm_config: *standard               # profil actif

system1: { ... }                    # 04-primitives-system1.md § 2
gates: { max_retries: 3, ... }      # 02-agents.md § 9
vale: { ... }
dspy: { ... }                       # 06-boucles-dspy.md
```

**[S03-04]** Au chargement : rôle sans modèle, modèle absent du stock, variable
d'environnement non définie → exception (code `5`).

### 2.5 Résolution du sujet

Le sujet est **toujours** déterminé par l'utilisateur, jamais par le répertoire :

| Priorité | Signal |
|---|---|
| 1 | `--subject <nom>` (pour cette commande seulement) |
| 2 | sujet courant de `config.yml` (défini par `subject use`) |

**[S03-05]** Aucun des deux → erreur d'état (code `4`). Sujet inconnu → erreur
d'usage (code `2`).

```bash
cd ~/ecriture                      # l'espace de travail
bookctl subject new manuel-ia
bookctl subject new cuisine
bookctl subject use manuel-ia
bookctl draft 2.1                  # → manuel-ia
bookctl --subject cuisine draft 2.1  # → cuisine, sans changer le sujet courant
```

---

## 3. Commandes d'action

**Une commande canonique par étape, sans alias.** La correspondance étape →
commande → composant → artefact est la table de `02-agents.md` § 4. La commande
canonique est l'identifiant de l'étape partout, y compris dans `redo`.

Commandes : `init`, `collect`, `outline`, `detail`, `draft`,
`review`, `link`, `unify`, `polish`, `lock`, `build`.

### 3.1 `review` (L5, humain)

`review <chapitre>` crée `book/reviews/NN.md`, un gabarit d'annotations listant
les sections du chapitre. Le SME le remplit ; `accept` clôt la revue (gate H3).
Les annotations deviennent une entrée de `link` et `polish`.

### 3.2 `lock` (L9) : l'Auditeur propose, System 1 dispose

**[S03-06]** À l'`accept` d'un artefact de L4, `bookctl` enregistre ses mesures
dans `state/baseline/` (violations Vale par catégorie, jugements System 1,
nombre de mots). C'est la référence de la non-régression.

`lock <chapitre>` déroule quatre temps, pour chaque chapitre visé :

1. **Mesure** — Vale, compteurs (mots, termes hors lexique, redéfinitions
   relevées dans `state/concepts.yml`) et questions System 1 de non-régression,
   comparés à la référence.
2. **Constats** — l'Auditeur (rôle `audit`) lit le chapitre et ses références
   (`02-agents.md` § 6.1) et propose des constats typés et localisés.
3. **Confirmation** — chaque constat devient une question System 1
   (`04-primitives-system1.md` § 4.5) : confirmé, infirmé ou incertain.
4. **Verdict et rapport** — agrégation du § 3.2 de `04` sur les mesures et les
   constats confirmés ou incertains ; rapport écrit dans
   `reports/lock/NN.md`.

**[S03-21]** `lock` rend `fail` si la révision introduit plus de défauts
qu'elle n'en retire par rapport à la référence, ou si un constat est confirmé.

**[S03-22]** Sans cible, `lock` traite tous les chapitres puis écrit la
synthèse `reports/lock.md`, qui est l'artefact de la gate H5 (le livre
complet).

Le rapport d'un chapitre a toujours la même structure :

```markdown
# Contrôle final — chapitre NN
## Verdict            pass | fail | escalate, et pourquoi
## Non-régression     tableau référence L4 → état L8, par mesure
## Constats confirmés catégorie, cible, passage, référence, explication
## Constats à vérifier (incertains, ou non confirmés si System 1 est débranché)
## Constats infirmés  rappel bref, pour mémoire
```

### 3.3 `build` (L10)

Assemble les fichiers de cibles dans l'ordre de `outline.md` et appelle Pandoc
(`doc-tools/pandoc.md`). Sortie dans `exports/`.

---

## 4. Commandes de décision

| Décision | Commande | Sémantique |
|---|---|---|
| accepter | `accept` | marquer l'artefact accepté ; ne lance rien |
| répéter | `retry` | réexécuter la même primitive sur la même cible |
| reprendre | `resume` | repasser la gate après modification manuelle |
| refaire | `redo` | refaire une étape amont, re-propagation bornée |

### 4.1 Syntaxe de `redo`

`redo` désigne les étapes **uniquement** par leur commande canonique :

```
bookctl redo                                       # refaire la dernière action (étape + cible)
bookctl redo <command>                             # refaire la dernière action de type <command>
bookctl redo <command> <target>                    # refaire <command> sur <target>
bookctl redo <command> <target> --stop <command>   # puis re-propager jusqu'à <command> inclus
```

- **[S03-07]** Sans `--stop`, `redo` refait **la seule étape** visée ; l'aval
  qui en dépend passe au statut `stale` (§ 8), sans être régénéré.
- **[S03-08]** Avec `--stop`, l'aval dépendant est ré-exécuté dans l'ordre des
  étapes, jusqu'à `<command>` inclus. La re-propagation **s'arrête à la première
  gate humaine** dont l'artefact n'est pas accepté, et le signale (code `4`).
- **[S03-09]** Une étape amont n'est jamais régénérée par la re-propagation.

### 4.2 Instructions sur `retry` / `redo`

```
bookctl retry 3.2 --message "préciser la distinction agent/agentif en §3.2.1"
bookctl redo draft 3.2 --instructions ~/notes/directives.md
```

Sans instruction, la primitive est réexécutée **sans instruction
complémentaire**. Aucune instruction antérieure n'est réutilisée implicitement.

### 4.3 Instructions complémentaires (toutes commandes)

Deux modes, mutuellement exclusifs, valables pour **toute** commande d'action ou
de décision :

```
bookctl polish 3.2 --message "alléger le ton, réduire les phrases > 40 mots"
bookctl draft 3 --instructions consignes-chapitre3.md
```

- Une instruction est **complémentaire** : elle s'ajoute au contrat de l'étape,
  elle ne le remplace pas.
- Le fichier est lu **au moment de l'exécution** (just-in-time).
- **[S03-10]** Le chemin de `--instructions` est **toujours** celui donné par
  l'utilisateur, résolu depuis le répertoire courant (ou absolu). Aucun dossier
  par défaut, aucun repli : fichier introuvable → code `2`.
- **[S03-11]** `--message` et `--instructions` ensemble → code `2`.
- L'instruction utilisée est consignée dans le journal d'audit.

### 4.4 Emplacement des prompts

Les prompts (`system`/`user`) font partie de l'outil : ils vivent dans le dépôt,
dans `prompt/`, à côté du code :

```
bookctl/
├── src/bookctl/     # code Python (dont le point d'entrée CLI)
├── prompt/          # prompts system/user, chargés just-in-time
├── vale/            # règles Vale FR
├── tests/
└── params.sample.yml
```

---

## 5. Cibles et numérotation

### 5.1 Adressage

Les cibles sont adressées par un **chemin décimal pointé**, et uniquement par
cela :

| Cible | Type |
|---|---|
| `3` | chapitre 3 |
| `3.2` | section 2 du chapitre 3 |
| `3.2.1` | sous-section 1 de la section 3.2 |

### 5.2 Un fichier par cible

**[S03-12]** Chaque section et sous-section rédigée est un fichier dont le nom
est son adresse : `book/chapters/03/3.2.md`, `book/chapters/03/3.2.1.md`. Si une
section a des sous-sections, son fichier ne contient que son texte propre
(introduction de la section). `build` assemble les fichiers dans l'ordre du
plan.

### 5.3 Les parties

Une **partie** n'est pas un type de cible : c'est un regroupement de chapitres
défini dans l'outline. On agit sur une partie par la **plage** de chapitres
qu'elle couvre.

### 5.4 Plages

```
<N>..<M>      de N à M (bornes inclusives)
<N>..         de N à la fin
```

Reconnaissance : `^(\d+(\.\d+){0,2})(\.\.(\d+(\.\d+){0,2})?)?$`

**[S03-13]** Les deux bornes d'une plage sont de même niveau, appartiennent au
même parent (pour les sections) et sont ordonnées. Sinon : code `2`.

```
bookctl draft 3..5       # chapitres 3 à 5
bookctl draft 3.1..3.4   # sections 3.1 à 3.4
bookctl polish 3..       # du chapitre 3 à la fin
```

### 5.5 Exécution sur plusieurs cibles

**[S03-14]** Une cible chapitre ou plage exécute la primitive sur chaque cible
élémentaire concernée, **séquentiellement**, dans l'ordre du plan, avec un
verdict par cible. L'exécution s'arrête à la première cible qui ne rend pas
`pass`, sauf avec `--keep-going`. Le code de retour est le plus grave des codes
obtenus (§ 7.2).

---

## 6. Comportements par défaut

| Commande sans cible | Comportement |
|---|---|
| `draft` | la **cible courante** si elle est rédigeable ; sinon la **prochaine** section non rédigée selon le plan |
| `polish`, `review`, `link` | la cible courante |
| `lock` | tous les chapitres, puis la synthèse (§ 3.2) |
| `build` | le sujet entier |
| `accept` / `retry` / `resume` | la **dernière action** du sujet |
| `redo` | la **dernière action** (même étape, même cible) |

### 6.1 La cible courante

**[S03-15]** La cible courante (dernière adressée) est enregistrée **par sujet**
dans `config.yml`, et nulle part ailleurs.

```
bookctl draft 3.2
bookctl polish        # → polit 3.2
bookctl accept        # → accepte la dernière action
```

### 6.2 Gates humaines

Les gates H0–H5 (`02-agents.md` § 10) s'appliquent : un artefact non accepté ne
sert pas d'entrée à l'aval (code `4`), et leur `accept` exige une confirmation
interactive.

---

## 7. Sorties et codes de retour

### 7.1 Contenu du verdict

**[S03-23]** Le verdict a un schéma versionné. Avec `--json`, `bookctl` écrit
sur stdout un objet par commande (un tableau `results` pour plusieurs cibles) ;
les messages humains vont sur stderr.

```json
{
  "schema_version": "1.0",
  "command": "draft",
  "subject": "manuel-ia",
  "exit_code": 1,
  "results": [
    {
      "target": "3.2",
      "verdict": "fail",
      "artefact": "manuel-ia/book/chapters/03/3.2.md",
      "revision": 4,
      "status": "draft",
      "gate": {
        "vale": {
          "verdict": "fail",
          "violations": [
            {"line": 12, "column": 5, "rule": "fr.Chevilles", "level": "error",
             "match": "il convient de", "message": "Cheville : « il convient de »"}
          ]
        },
        "counters": {"words": 1180, "terms_outside_lexicon": 0, "redefinitions": 0},
        "system1": {
          "enabled": true,
          "provider": "typesafe",
          "model": "jev-1.13.0",
          "verdict": "pass",
          "questions": {
            "ternaire": {"type": "noul", "value": 0.07, "certainty": 0.86, "band": "certain", "conforming": true}
          }
        },
        "audit": null
      },
      "human_gate": "not_required",
      "prerequisites": []
    }
  ]
}
```

- `status` : `draft`, `accepted` ou `stale` (§ 8.2).
- `system1` vaut `{"enabled": false}` quand le juge est débranché.
- `audit` n'est rempli que par `lock` : `{"findings": [{"category", "target",
  "passage", "reference", "explanation", "confirmation": "confirmed" |
  "rejected" | "uncertain" | "unconfirmed"}]}`.
- Les erreurs (codes `2`, `4`, `5`) renvoient `{"schema_version", "command",
  "exit_code", "error": {"type", "message"}}`.

### 7.2 Codes de retour

| Code | Signification |
|---|---|
| `0` | `pass` — gate passée |
| `1` | `fail` — défauts constatés (liste fournie) |
| `2` | erreur d'usage (commande, cible, option, fichier d'instructions) |
| `3` | `escalate` — certitude insuffisante, intervention humaine requise |
| `4` | erreur d'état (sujet non défini, prérequis non accepté, limite de `retry`) |
| `5` | erreur d'exécution (configuration, clé API, fournisseur injoignable) |

**[S03-16]** Gravité, pour le code agrégé d'une exécution multi-cibles :
`5` > `4` > `2` > `1` > `3` > `0` (un `fail` l'emporte sur un
`escalate`, comme dans `04-primitives-system1.md` § 3.2).

---

## 8. Versionnement des artefacts et manifeste

Les artefacts d'un sujet ne sont pas dans git. `bookctl` les versionne lui-même.

### 8.1 Historique

**[S03-17]** Chaque commande qui écrit un artefact crée une **révision** :
copie horodatée dans `history/<chemin de l'artefact>/<n>.md`, avec la commande,
l'instruction, le verdict et les modèles utilisés. Les révisions ne sont jamais
modifiées.

**[S03-24]** Les révisions sont toutes conservées ; aucune purge automatique.

Commandes de consultation (lecture seule) :

| Commande | Effet |
|---|---|
| `bookctl log [cible]` | révisions d'une cible (ou du sujet) avec commande, verdict, statut |
| `bookctl diff <cible> [rev1] [rev2]` | différence entre deux révisions (défaut : les deux dernières) |

### 8.2 Manifeste et péremption

**[S03-18]** `state/manifest.yml` enregistre pour chaque artefact : étape,
cible, révision courante, statut (`draft`, `accepted`, `stale`), et la liste des
**entrées lues** avec leur empreinte (hash) au moment de la production.

**[S03-19]** Quand une entrée change (nouvelle révision, modification manuelle
détectée par empreinte), tout artefact qui l'a lue passe à `stale`. Un artefact
`stale` ne peut pas servir d'entrée à l'aval (code `4`) tant qu'il n'est pas
refait ou repris (`resume`).

---

## 9. Journal d'audit

**[S03-20]** Chaque appel modèle (LLM ou System 1) ajoute une ligne JSON dans
`state/audit/<date>.jsonl` : horodatage, commande, cible, rôle, fournisseur,
modèle et version, prompts envoyés (ou leur référence de révision), paramètres,
réponse, jetons, coût estimé, durée. Le journal reste local, dans le sujet.

---

## 10. Contrat de test

Chaque commande est **testable isolément** :

1. **Entrées figées** : les fichiers lus sont identifiés par leur empreinte ;
   rejouée sur le même état, une commande lit les mêmes entrées.
2. **Artefact versionné** : chaque écriture crée une révision (§ 8).
3. **Gate reproductible** : Vale est déterministe ; les réponses System 1 et LLM
   sont simulées (doublures) dans les tests unitaires.
4. **Isolation** : une commande peut tourner seule sur une tranche, sans le
   reste du pipeline.

---

## 11. Exemple de session

```bash
cd ~/ecriture
bookctl workspace init
bookctl subject new manuel-ia
bookctl subject use manuel-ia

bookctl init --instructions ~/notes/brief-these.md   # L0 cadrage, gate H0
bookctl accept                                       # confirmation interactive
bookctl outline                                      # L2, gate H1
bookctl accept                                       # confirmation interactive
bookctl detail 3                                     # L3, gate H2
bookctl accept
bookctl draft 3.1                                    # L4
bookctl retry 3.1 --message "préciser la distinction agent/agentif"
bookctl accept
bookctl polish 3.1                                   # L8

bookctl log 3.1
bookctl redo detail 3 --stop draft                   # refaire le plan du chapitre 3, re-rédiger
```

---

## 12. Options locales

**[S03-25]** En v1, les seules options locales sont `--stop <command>` (`redo`)
et `--keep-going` (cibles multiples). Toute autre consigne passe par
`--message` ou `--instructions`. Une nouvelle option locale (ex. `--words`)
s'ajoute par révision de cette spec.
