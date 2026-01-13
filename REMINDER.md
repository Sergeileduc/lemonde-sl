# REMINDER for me

## TESTS

soit uv :
`uv run pytest`

soit pytest directement :
`pytest`

## NETTOYAGE de uv

```shell
rm -r .venv
rm -r dist
rm -r build
rm -r .pytest_cache
rm -r .ruff_cache
```

puis
`uv sync`

## Installer en dev

`uv sync` (recommandé)

et avec les libs (pytest, black, etc)

`uv sync --dev`

### Nettoyage du cache global uv (rarement nécessaire)

uv garde un cache global dans :
~/.cache/uv/

Pour le vider proprement :
`uv cache prune`

ou pour tout supprimer :
`uv cache clean`

Recommandation :

- prune = safe
- clean = reset total (à utiliser seulement si tu veux vraiment repartir de zéro)

## Installer les dependandies

`uv sync`

## Installer avec les outils de dev (pytest, etc...)

`uv sync --dev`

## Installer les dependances optionnelles

`uv pip install "name-of-package-sl[docs]"`

`uv pip install "name-of-package-sl[full]"`

## Vérifier

`uv pip list`


## exemple de Github action

```yaml
name: CI

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Sync environment (runtime + dev)
        run: uv sync --dev

      - name: Run tests
        run: uv run pytest -q
```
