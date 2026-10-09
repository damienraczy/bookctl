# Note technique — Bibliothèque CLI (Typer / Click)

> **Objet :** choix de la bibliothèque qui implémente la grammaire de `bookctl` (`specs/03-cli.md` § 1).
> **Recommandation :** **Typer** (au-dessus de Click), avec un pré-traitement des options globales.

---

## 1. Besoins issus de la spec

| Besoin | Référence |
|---|---|
| `bookctl [options-globales] <command> [target] [options]` | 03 § 1 |
| Options globales acceptées **avant ou après** la commande | 03 § 1 |
| Sous-commandes groupées (`subject new`, `workspace init`) | 03 § 2 |
| Codes de retour maîtrisés (0 à 5), y compris pour les erreurs d'usage | 03 § 7.2 |
| Sortie `--json` | 03 § 7.1 |
| Confirmation interactive pour les gates H, TTY exigé | 02 § 10 |
| Testabilité de chaque commande | 03 § 10 |

---

## 2. Options

| Critère | **Typer** | Click | argparse |
|---|---|---|---|
| Déclaration | annotations de type Python | décorateurs | impératif |
| Sous-commandes groupées | oui | oui | oui (plus verbeux) |
| Options globales après la commande | non nativement | non nativement | non nativement |
| Tests | `typer.testing.CliRunner` | `click.testing.CliRunner` | à la main |
| Aide générée | oui, riche | oui | oui |
| Dépendances | Click (+ Rich en option) | aucune | stdlib |

Aucune des trois n'accepte nativement une option de groupe placée **après** la
sous-commande. Solution simple et testable : un **pré-traitement d'`argv`** qui
extrait `--subject/-s`, `--message/-m`, `--instructions/-i`, `--json` où qu'ils
soient, avant de passer le reste à Typer.

---

## 3. Points d'implémentation

- **Codes de retour** : Click renvoie `2` sur erreur d'usage, ce qui correspond
  au code `2` de la spec. Les autres codes sont levés explicitement
  (`raise typer.Exit(code=…)`) depuis une exception métier unique par code.
- **Gates H** : `sys.stdin.isatty()` exigé ; sinon refus (code `4`).
  Confirmation par `typer.confirm`. Dans les tests, simuler un TTY plutôt que
  désactiver la vérification.
- **`--json`** : un seul point de sortie qui sérialise le verdict ; aucune
  autre écriture sur stdout dans ce mode (les messages vont sur stderr).
- **Point d'entrée** : `[project.scripts] bookctl = "bookctl.cli:main"` dans
  `pyproject.toml`.

---

## 4. Décision

Typer, pour la concision des signatures typées et `CliRunner`, avec le
pré-traitement d'`argv` décrit ci-dessus. Versions épinglées.

*Note rédigée le 9 octobre 2026.*
