# 04 — Primitives System 1

> Document de spécification. Définit la couche de jugement calibré : le contrat
> System 1, les fournisseurs, les questions par étape, les règles de routage et
> leur traduction en verdict CLI.
>
> Rédigé le 9 octobre 2026.

---

## 0. Position

System 1 est le **juge gradué** de la chaîne qualité (`01-architecture.md` § 3).
Il s'insère entre Vale (motifs codés, binaire) et le correcteur LLM (génératif,
coûteux). Il ne rédige pas, n'explique pas, ne corrige pas : il **juge et
route**. Documentation technique des fournisseurs : `doc-tools/system-one.md`.

---

## 1. Le contrat System 1

### 1.1 Requête et réponse

Un appel `POST …/v1/systemone` envoie un `state` (le texte à juger), un `model`
et jusqu'à 64 `questions` nommées, évaluées **en isolation** contre le même
`state`, en une passe, **sans génération de texte**.

| Primitive | Critères | Réponse |
|---|---|---|
| **`choice`** | options nommées (avec description) | `choice`, `probabilities`, `confidence` |
| **`score`** | niveaux ordonnés, du plus bas au plus haut | `score` (niveau pondéré), `legend`, `probabilities`, `confidence` |
| **`noul`** | `true` / `false` (optionnels) | `noul` (probabilité que la réponse soit vraie) **seulement** |

**`noul` ne renvoie pas de `confidence`** (documentation TypeSafe et Ollama).
Sa certitude se lit directement dans la probabilité : proche de 0 ou de 1 =
certain, proche de 0,5 = incertain.

**`confidence` ≠ justesse.** Pour `choice` et `score`, elle mesure la
*concentration* de la distribution, pas la probabilité d'avoir raison.

### 1.2 Fournisseurs

| Fournisseur | Usage | Endpoint | Remarques |
|---|---|---|---|
| **Jev** (TypeSafe, cloud) | **cible** (exécution et calibration) | `https://api.typesafe.ai/v1/systemone`, clé `Bearer` | anglais prioritaire ; contexte 32k pour le `state` |
| **Ollama local** (Nimble, Tev1, Clef…) | **poste de développement seulement**, si le matériel le permet | `http://localhost:11434/v1/systemone` | contexte effectif réduit (Tev1 ≈ 2k, Nimble ≈ 8k tokens) |

Ollama Cloud ne sert pas de modèles System 1 à ce jour.

**[S04-01]** Le fournisseur est choisi dans `params.yml` ; le code appelle une
interface unique (`System1Client`) quel que soit le fournisseur.

### 1.3 Limites communes

**[S04-02]** Pour rester portable entre fournisseurs, les questions respectent
l'intersection des limites :

| Limite | Valeur retenue | Origine |
|---|---|---|
| Questions par appel | ≤ 64 | Ollama |
| Options `choice` | 2 à 24 | Tev1 entraîné sur 2–24 (Jev : 255) |
| Niveaux `score` | 2 à 10 | Jev : 10 maximum (Ollama : 26) |
| Taille de requête | ≤ 64 Kio | Ollama |
| Taille du `state` | ≤ `system1.max_state_tokens` du modèle actif | dépend du modèle |

**[S04-03]** Une requête qui dépasse une limite lève une exception avant
l'envoi (pas de troncature silencieuse).

---

## 2. Paramètres (aucun codé en dur)

```yaml
# params.yml (extrait)
system1:
  enabled: false                 # P0/P1 : gate = Vale + humain
  provider: typesafe             # typesafe | ollama
  providers:
    typesafe:
      url: TYPESAFE_URL          # nom de variable d'environnement
      api_key: TYPESAFE_API_KEY
      model: jev-latest
      max_state_tokens: 32000
      timeout: 30
    ollama:                      # poste de développement uniquement
      url: OLLAMA_LOCAL_URL
      model: nimble
      max_state_tokens: 8000
      timeout: 60
  routing:
    noul_true_threshold: 0.8     # noul ≥ seuil → vrai
    noul_false_threshold: 0.2    # noul ≤ seuil → faux ; entre les deux → incertain
    confidence_threshold: 0.6    # choice/score : sous ce seuil → incertain
```

Les seuils sont des **valeurs de départ**, à calibrer par la boucle 1
(`06-boucles-dspy.md`). Les formulations des questions sont chargées
**just-in-time** depuis des fichiers (§ 4.1).

---

## 3. Routage

### 3.1 Bande de certitude par primitive

**[S04-04]** Chaque réponse est classée en **certaine** ou **incertaine** :

| Primitive | Certaine | Incertaine |
|---|---|---|
| `noul` | `noul ≥ noul_true_threshold` (vrai) ou `noul ≤ noul_false_threshold` (faux) | entre les deux seuils |
| `choice`, `score` | `confidence ≥ confidence_threshold` | `confidence < confidence_threshold` |

Pour l'affichage et le journal, la certitude d'un `noul` est rapportée sous la
forme `|2p − 1|` (0 = incertitude totale, 1 = certitude), comme le suggère la
documentation TypeSafe.

### 3.2 Agrégation en verdict de gate

**[S04-05]** Une gate pose plusieurs questions. Le verdict System 1 est
calculé **en code** :

1. au moins une réponse **certaine** et **non conforme** → `fail` ;
2. sinon, au moins une réponse **incertaine** → `escalate` ;
3. sinon → `pass`.

Chaque question déclare dans son fichier ce que « non conforme » veut dire
(ex. `noul` vrai pour « contient un ternaire creux » ; `score` au-dessus d'un
niveau donné pour « densité de tics »).

---

## 4. Les questions, par étape

Chaque question est un « gut-check » scopé (le jugement qu'un expert fait en
quelques secondes). Un jugement multi-facteurs est **décomposé en
sous-questions** combinées en code, jamais dans la question.

### 4.1 Fichiers

Les questions font partie de l'outil : elles vivent dans le dépôt, dans
`prompt/system1/` :

```
bookctl/prompt/system1/
├── ternaire_system.md       # instructions + critères (ce qu'on juge, la grille)
├── ternaire_user.md         # gabarit du state, ex. "{passage}"
├── ternaire.yml             # type, règle de non-conformité, unité de jugement
└── ...
```

`_system.md` porte l'instruction ; `_user.md` le gabarit du `state` ; le `.yml`
les métadonnées (paramètres, pas de prompt). Variables `{variable}` validées
(`PRINCIPES.md`).

### 4.2 Unité de jugement

**[S04-06]** L'unité de jugement est celle du travail en cours : une phrase si
l'étape travaille à la phrase, un paragraphe si elle travaille au paragraphe,
la section ou le document entier si l'étape porte sur eux. Chaque question
déclare son unité dans son `.yml`. Si l'unité dépasse `max_state_tokens` du
modèle actif, la commande échoue (code `5`) : on change de modèle ou d'unité,
on ne tronque pas.

### 4.3 Mapping étape → primitive → question

| Étape | Commande | Primitive | Question (gut-check) | Unité |
|---|---|---|---|---|
| L2 | `outline` | `choice` | « ce chapitre appartient-il à la partie A, B ou C ? » | chapitre (titre + résumé) |
| L3 | `detail` | `score` | « ce point clé est-il au bon niveau d'abstraction ? » | point clé |
| L4 | `draft` | `noul` | « ce passage contient-il un ternaire creux ? » | paragraphe |
| L4 | `draft` | `score` | « densité de tics stylistiques ? » | section |
| L7 | `unify` | `noul` (lot) | « ce concept est-il déjà défini ailleurs ? » | section |
| L8 | `polish` | `score` | « conformité au guide stylistique ? » | section |
| L9 | `lock` | `noul` (lot) | « la révision introduit-elle plus de tics qu'elle n'en retire ? » | section (avant / après) |
| L9 | `lock` | `noul` (lot) | confirmation des constats de l'Auditeur (§ 4.5) | passage + référence |

Les étapes L0, L1, L5, L6, L10 n'appellent pas System 1.

### 4.4 Le parallélisme

Pour L7 et L9, on émet **plusieurs questions en un seul appel** (jusqu'à 64),
chacune jugée en isolation contre le même `state`. Exemple L7 : une `noul` par
concept de `state/concepts.yml`, « déjà défini ? », sur une section.

### 4.5 Confirmation des constats de l'Auditeur (L9)

L'Auditeur (`02-agents.md` § 6.1) propose des constats ; System 1 les confirme
ou les infirme. Chaque **catégorie** de constat a sa question de confirmation,
dans `prompt/system1/audit_<catégorie>_system.md` :

| Catégorie | Question de confirmation (`noul`) | `state` |
|---|---|---|
| `contradiction-these` | « ce passage contredit-il cet énoncé de la constitution ? » | passage + énoncé cité |
| `promesse-non-tenue` | « ce chapitre traite-t-il ce point du plan ? » (non-conforme si faux) | chapitre + point cité |
| `concept-avant-definition` | « ce passage utilise-t-il ce concept sans qu'il ait été défini auparavant ? » | passage + définition et position |
| `redefinition` | « ce passage redéfinit-il ce concept déjà défini ? » | passage + définition existante |
| `progression` | « ce passage suppose-t-il une notion présentée seulement plus loin ? » | passage + notion citée |
| `fait-douteux` | « cet énoncé nécessite-t-il une vérification par un expert ? » | passage |

- **[S04-10]** La liste des catégories est **fermée** : un constat d'une
  catégorie inconnue est rejeté au chargement (exception consignée, constat
  écarté du rapport).
- **[S04-11]** Un constat est **confirmé** si sa réponse est certaine et non
  conforme (§ 3.1), **infirmé** si elle est certaine et conforme, **incertain**
  sinon. Seuls les confirmés et les incertains entrent dans l'agrégation du
  § 3.2 ; les infirmés sont consignés.
- La catégorie `fait-douteux` ne donne jamais `fail` : une confirmation donne
  `escalate`, parce que le fond relève de l'expert (L5), pas de System 1.
- Les questions de confirmation sont calibrées par la boucle 1 comme les autres.

---

## 5. Mapping vers le verdict CLI

| Verdict System 1 (§ 3.2) | Code de retour |
|---|---|
| `pass` | `0` |
| `fail` | `1` |
| `escalate` | `3` |

La gate complète combine Vale, les compteurs et System 1 avec la même règle
qu'au § 3.2 : un défaut certain (`fail`) l'emporte sur une incertitude
(`escalate`), qui l'emporte sur `pass`. Un défaut certain doit être corrigé de
toute façon ; l'escalade n'a de sens que si rien n'est fautif avec certitude. Sur `escalate`, l'utilisateur décide :
`resume` après intervention manuelle, ou passage au Correcteur.

---

## 6. Traçabilité

**[S04-07]** Chaque appel System 1 est journalisé localement
(`03-cli.md` § 9) : fournisseur, modèle et version renvoyée, instructions et
`state` envoyés, seuils, réponse complète, jetons, durée.

---

## 7. Fail-fast

- **[S04-08]** Fournisseur injoignable, 401, 422 → exception explicite (code
  `5`), sans repli vers un autre juge. Les erreurs transitoires (429, 529) sont
  retentées avec backoff exponentiel borné (`params.yml`), puis exception.
- **[S04-09]** Réponse incomplète (question manquante, `probabilities` absentes
  pour `choice`/`score`, valeur hors [0, 1]) → exception, pas d'interprétation
  par défaut.
- **Miscalibration détectée** (écart mesuré entre réponses et étiquettes
  humaines au-dessus d'un seuil) → alarme explicite.

---

## 8. Valeurs à mesurer

Ce ne sont pas des choix de conception, mais des valeurs fixées par la mesure
(spikes, boucle 1, premiers chapitres).

- **Seuils de routage** : à calibrer par la boucle 1.
- **Modèle System 1 retenu** : `jev-latest` par défaut ; le choix définitif est
  un résultat de la boucle 1.
- **Nombre de niveaux de chaque `score`** : à fixer avec le dataset.
