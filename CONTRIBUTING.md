# Contributing to IntraNest

## Branching & Releases
- `main` = stable, protected
- `dev` = integration
- Feature branches: `feat/<topic>`, bugfix: `fix/<topic>`

## Commit Style
- Conventional Commits preferred (e.g., `feat:`, `fix:`, `docs:`)

## PRs
- Include description, testing notes, screenshots/logs if relevant
- Ensure CI is green (lint/build/tests)

## Code Style
- Python: ruff/black; run `pytest` for tests
- Node: eslint/tsc build must pass

## Security
- Never commit secrets. Use `.env` files locally and secret managers in CI/CD.
