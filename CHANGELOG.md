# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## \[Unreleased]

### Added

* Async HTTP transport via `httpx.AsyncClient` with connection pooling
* WebSocket transport with event dispatch (push notifications)
* Pydantic models with discriminated unions for download status variants
* Full aria2 RPC method coverage (42 methods)
* CLI entry point for binary discovery and daemon management
* Build hook for bundling aria2c static binary into wheel
* 100% type-annotated with `ty` (120+ rules, strict mode)
* Ruff linting with Google-style docstring conventions
* `CODE-REVIEW-RULES.md` with 13 quality gates
* 25 project skills covering tools, patterns, and workflows
* Pre-commit hooks (ruff, ty, pytest)
* Direnv integration for development environment

### Internal

* Project scaffolding with `uv` and `hatchling` build backend
* CI/CD workflow for binary builds (`build-aria2.yml`)
* SDD (Software Design Document) artifacts in `openspec/`

