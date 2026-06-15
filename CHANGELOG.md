# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

---

## [0.2.0] - 2026-06-15

### Added

- Character management with multi-character ESI sync (planets, extractors, factories, skills)
- Extractors overview with expiry time, cycle time, output rate and urgency indicators
- Planets overview with project assignment and storage content
- Projects — define production targets, auto-expand P1→P4 factory chains, assign planets
- Corp PI — share characters with corp managers, corp-wide project planning
- Optimizer — suggest planet assignments for a production plan, create projects from results
- Profit calculator — fully integrated chain profit per schematic (Jita buy prices via Fuzzwork)
- Build-out view — factory and extractor slot requirements per project planet
- Maintenance log — cross-character transfer and export tracking per project
- Market price sync via Fuzzwork Marketstat API (Celery Beat task)
- ESI client via `django-esi` `ESIClientProvider` — ETag/304 caching, error-limit handling, autoretry
- German translation (de)
- Plan→Planet auto-linking on ESI sync

### Fixed

- Corp mode optimizer accidentally using personal characters when no corp pool existed
- Share button on Characters page not saving (AA `auth-framework.js` collision with `fetchPost`)
- CSRF cookie not guaranteed on Characters page

[Unreleased]: https://github.com/GurkeTonic/aa-pi-tracker/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/GurkeTonic/aa-pi-tracker/compare/v0.1.0...v0.2.0
