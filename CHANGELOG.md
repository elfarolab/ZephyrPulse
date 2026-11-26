# v0.3.8 — Dense expandable news and text-only header

- Overview displays the full rolling news window in a single filterable table; category counts and shortcuts remain cards.
- Hardware categories, documentation and other event pages use the same compact table. 100 rows per page by default; 25, 50, 100, 200 or all. Filter, sort, expand details inline, or expand/collapse the current page. Narrow screens use stacked rows.
- Watchlist highlights use the same expandable table when browser data is available. All source links remain available without JavaScript.
- Stop copying the upstream logo, remove the old generated SVG on collection and hide the theme header/drawer logo; retain the text title and upstream repository link.
- No database or preference schema change.

# v0.3.7 — Settings and upstream branding

- Copy the official documentation SVG from the collected upstream Git revision when available; retain the built-in CPU icon as a fallback. Keep independent project disclosure. The Zephyr mark is subject to its own trademark rules.
- Redesign settings as responsive two-column cards with aligned fields, clear action groups and save feedback. Preserve the browser storage key, preferences, configuration and data.

# v0.3.6 — Dashboard iconography

- Add locally hosted, original outline SVG icons with semantic category accents in both color schemes.
- Iconify summary cards, engineering shortcuts, news links and navigation tabs; use a native Zensical CPU logo.
- Hide redundant homepage navigation sidebar; preserve category pagination, search, watchlists and all data.
- No dependency, data schema or collector changes.

# v0.3.5 — source evidence and dashboard

- Fix missing sticky tabs; group navigation and hide right-side TOCs on generated pages.
- Bound home news previews; preserve all events on paginated category pages, feeds and search.
- Add revision-pinned exact-target DTS/include/binding and driver-token evidence for main and selected release snapshots; keep YAML declarations and unresolved source hints distinct.
- Add source and file-history links; link official board docs when discovered.
- Preserve existing state, preferences, configuration, and publication workflow. No compiled DT or hardware verification.

# Changelog

## 0.3.4

- Replace both uses of Git `--since-as-filter` with a portable first-parent metadata walk and exact UTC committer-time filtering in Python. Preserve out-of-order commit dates and first-parent merge semantics.
- Log the installed Git version on startup. Add regression tests for old-Git option rejection, timestamp skew and cutoff boundaries. Existing Git repository, SQLite schema, configuration and browser preferences remain unchanged.

## 0.3.3

- Persistent bare initialization and separate branch/tag fetches, bounded retries with exponential backoff and HTTP/1.1 by default.
- HTTP low-speed abort, disable interactive credential prompts, preserve successful transfers and reject invalid/shallow/partial repositories without deleting state.
- Optional `--git-seed` reuses full local history; upstream sync remains authoritative. No DB or preference changes.

## 0.3.2

- Default stage logging, elapsed time and 15-second heartbeats during long operations.
- Stream initial Git clone/fetch progress without changing captured Git data commands.
- Throttled counters for recent commits, history, inventory, release checks/snapshots and board pages; report PR pages and build/publish stages.
- Add `--verbose` / `-v` diagnostics; preserve nonzero exit codes on failures and interrupts.
- No database, preference schema, dependency or feature changes.

## 0.3.1

- Replace MkDocs/Material with pinned Zensical 0.1.3 and native TOML classic theme configuration.
- Introduce renderer contract, staged clean builds, output validation and preservation of previous output on renderer/validation errors. Keep flat URLs and R2 release publishing unchanged.
- Native Zensical full-text search plus independently implemented structured hardware search over existing JSON; no MkDocs plugins or remote search APIs.
- Hardware search filters persist in the existing browser settings schema; global news remains unfiltered. Extract optional theme bridge and add CSS fallback colors.
- Add core-only dependency file, generator fixture tests, search logic tests and rendered-site CI smoke test. No DB migration; advanced verification deferred.
- Actual Zensical build and native search UI not locally validated (dependency unavailable).

## 0.3.0

- Exact-target hardware comparator and requirement-ranked discovery across the entire board catalog; up to eight selected targets.
- Conservative capability aliases; distinct CAN/CAN FD, USB/device/host and missing-metadata states.
- Main and latest stable/configured LTS target metadata snapshots, with source evidence and explicit old-layout limitations.
- Central browser-local settings panel, per-field overrides of YAML defaults, migration from v0.2, JSON export/import and reset.
- Persistent comparison, watchlists, explorer filters, vendor chart selection and display preferences; global news and public RSS remain unfiltered.
- Existing collector, SQLite retention, four-hour schedule, MkDocs and R2 deployment retained. No compiled DTS/Kconfig analysis or hardware verification.
- Python and Node fixture tests; optional Playwright smoke test and CI build checks.

## 0.2.0

- Unfiltered global dashboard with additive configured and browser-local watchlists.
- Case-insensitive substring and glob matching for boards, SoCs, vendors and peripheral terms.
- Full current board catalog, per-target declared capability matrices and source-based historical milestones.
- 90-day compact history, bounded backfill, coverage reporting, vendor activity analytics and trends.
- Stable/LTS tag inclusion, dated support policy, and bounded optional public open-PR snapshot.
- Global RSS/JSON plus configured watchlist RSS and intelligence dataset.
- Preserves v0.1 collector, SQLite expiry, MkDocs, R2 publishing, systemd schedule and MIT license.
- Advanced compiled DTS/Kconfig analysis and build/hardware validation intentionally deferred.
