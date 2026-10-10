# PRINCIPES — Socle de développement

> Règles qui s'imposent à tout le code de `bookctl`. Les autres specs y renvoient.
> Mis à jour le 9 octobre 2026.

---

## 0. Règle d'or

Le projet repose sur un socle de développement guidé par les tests et l'intégrité systémique :

* **Développement dirigé par les tests : TDD strict et couverture (pytest)**
  * Cycle obligatoire : **Red → Green → Refactor**.
  * Couverture ≥ 90 %.
  * Obligatoire : cas nominaux, cas limites, entrées invalides et levées d'exceptions (`pytest.raises`).
* **Exigences non fonctionnelles = critères d'acceptation :** isolation, minimisation des données et contrôle d'accès sont des invariants exécutables, testés comme le reste.
* **Traçabilité (bonne pratique) :** chaque appel à un modèle (LLM ou System 1) est journalisé localement : modèle et version, instructions envoyées, paramètres, réponse, durée, coût. Ce journal sert à auditer et expliquer un résultat. Il reste sur le poste de l'utilisateur, dans le sujet, et **n'entre jamais dans git** (§2).
* **Incréments sémantiques :** chaque commit est atomique, typé, rattaché à son exigence et à sa phase TDD (format en §1).
* **Séparation stricte des langages et contenus :** un type de contenu par fichier : `.py` pour Python, `.md` pour les prompts, `.yml` pour les paramètres, etc. Les exceptions doivent avoir une raison et une justification.
* **Échec explicite (*fail-fast*) :** toute erreur ou anomalie significative (clé API manquante, configuration invalide, échec réseau persistant, fichier introuvable) lève immédiatement une exception explicite. Aucun mécanisme de secours silencieux cachant une erreur ou anomalie significative .
* **Zéro paramètre codé en dur :** tous les réglages d'exécution sont centralisés dans `params.yml`, à la racine de l'espace de travail.
* **Chargement au dernier moment (*just-in-time*) :** paramètres, variables d'environnement et prompts sont chargés à l'exécution, jamais en amont.
* **Séparation des prompts *system* / *user* :**
  * Convention : `{libelle_clair}_system.md` et `{libelle_clair}_user.md`.
  * Variables injectées sous la forme `{nom_variable}`, avec validation automatique entre variables requises et fournies (variable manquante ou en trop → exception).
* **Documentation du code :** chaque fonction, méthode ou classe créée ou modifiée est documentée, avec un typage explicite.
  - rôle exact ;
  - chaque paramètre, son type et ses contraintes ;
  - la valeur de retour (type et sémantique) ;
  - les exceptions levées ;
  - standards : Python = Google Docstrings + typage PEP 484/526 ; JavaScript/TypeScript = JSDoc/TSDoc.
* **Secrets :** les clés d'API vivent dans `~/.env`, jamais dans le dépôt, jamais dans `params.yml` (qui ne contient que le **nom** de la variable d'environnement). Lecture : `load_dotenv(os.path.expanduser('~/.env'), override=True)`.
* **Modèles dans le cloud :** les LLM sont appelés dans le cloud (fournisseur principal : Ollama Cloud). Aucun LLM génératif local. Seul System 1 peut tourner localement, **sur le poste de développement uniquement**, si le matériel le permet (`doc-tools/system-one.md`).
* **Documents de travail :** chaque document doit être auto-suffisant et décrire exclusivement l'état actuel du système (« ce qui est »). Ne pas inclure des sections de journal des modifications (changelog), des diffs ou des explications comparatives vis-à-vis d'anciennes versions (« ce qui était »), sauf raison impérative. Tout élément devenu invalide ou déprécié est purement retiré, sans mention de son abandon, sauf si cela n'apporte aucune valeur opérationnelle directe.
* **Versionnage des documents de travail :** chaque modification des documents de travail (spécification, documentation), donne lieu à un fichier nommé {nom_fichier}.ar{n}.{extension} (ex. architecture_systeme.ar1.md, architecture_systeme.ar2.md), où :ar désigne l'archive ou l'itération de révision (n est un entier incrémental  >= 1).  Les versions archivées sont en lecture seule, pour histoique seulement.
* **Anciens documents :** Les documents situés dans des répertoires `old` sont à ignorer.

---

## 1. Format des commits

```
type(scope): [ID] [RED|GREEN|REFACTOR] sujet
```

- `type` : `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.
- `scope` : module concerné (`cli`, `gate`, `system1`, `dspy`, `vale`, `state`…).
- `ID` : identifiant de l'exigence (§3), ou `DOC` pour une modification de spec sans exigence.
- La phase TDD est obligatoire pour `feat`, `fix`, `test`, `refactor`.

Lexique ; 
- `feat` : ajout d’une nouvelle fonctionnalité.
- `fix` : correction d’une anomalie ou d’un bogue.
- `test` : ajout ou mise à jour de tests automatisés, sans impact sur le code de production.
- `refactor` : restructuration du code sans altération de son comportement fonctionnel.
- `docs` : création ou modification de la documentation uniquement.
- `chore` : maintenance courante (dépendances, configuration, outillage), sans impact sur le code métier.

Exemple : `feat(cli): [S03-05] [GREEN] résolution du sujet par --subject`.

---

## 2. Dépôt git : le code seulement

**git versionne le code de l'outil, jamais les travaux de rédaction.** Les manuscrits, instructions, rapports, journaux d'audit et datasets construits à partir des textes de l'utilisateur sont des **données personnelles**. Ils vivent dans l'espace de travail, hors dépôt.

- Le dépôt est **public**. Il ne contient ni secret, ni donnée personnelle, ni travail de rédaction.
- Les versions archivées des documents (`*.arN.*`), les anciennes versions et le contenu des dossiers `old` restent en local : ils n'entrent pas dans git.
- Le `.gitignore` fonctionne **par liste blanche** : tout est ignoré (`/*`), puis seuls les chemins de l'outil sont réautorisés explicitement. Un nouveau dossier n'entre dans git que par une ligne ajoutée volontairement au `.gitignore`.
- Un test vérifie que les dossiers d'un sujet (`book/`, `state/`, `reports/`, `history/`) et `params.yml` sont ignorés.
- Le versionnement des artefacts d'un sujet est assuré par `bookctl` lui-même (`03-cli.md` § 8), pas par git.
- les documents archivés, les anciennes versions et les documents des dossier `old` ne sont pas archivés
---

## 3. Identifiants d'exigences

Chaque exigence testable porte un identifiant `SNN-MM` : `NN` = numéro de la spec (`01`…`06` ; `00` pour le présent document, `00-projet.md` ne portant pas d'exigence testable), `MM` = numéro d'ordre dans la spec. Il apparaît entre crochets en tête de l'exigence : **[S03-07]**. Les tests citent l'identifiant dans leur nom ou leur docstring. Un identifiant n'est jamais réutilisé.

| ID | Exigence |
|---|---|
| **[S00-01]** | Couverture de tests ≥ 90 %. |
| **[S00-02]** | Aucun paramètre d'exécution codé en dur : tout vient de `params.yml`. |
| **[S00-03]** | Variables de prompt : requises = fournies, sinon exception. |
| **[S00-04]** | Clé API absente ou variable d'environnement non définie → exception explicite. |
| **[S00-05]** | Chaque appel modèle produit une entrée de journal d'audit local. |
| **[S00-06]** | Le `.gitignore` est en liste blanche ; les données de sujet et `params.yml` sont ignorés (testé). |
| **[S00-07]** | Un hook pre-commit refuse tout commit contenant un motif de clé d'API ou de secret. |
