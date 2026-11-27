# v0.3.31 — Scoped analysis caches and blue-teal freshness

- Separate inventory/target evidence, release metadata snapshots and recent Git file-manifest fingerprints. Follow producer source and direct local dependencies rather than entire mixed-purpose modules. Shared DTS/parser changes still invalidate the affected hardware caches together; presentation and classification changes no longer invalidate unrelated data. Cache format and indirect dependencies have explicit maintenance rules.
- Promote existing cache entries only when they match the exact v0.3.30 global source fingerprint and the unchanged scoped producer baseline. Other stale versions are recomputed safely. No database schema change or classifier migration.
- Replace warm freshness row backgrounds with cool blue-teal shades in light and dark themes, retaining the yellow `last` badge, all time thresholds and auto-expiration. Adjust highlighted link color for contrast. CSS fingerprint changes may cause a one-time larger HTML upload; renderer configuration is unchanged.

# v0.3.30 — Unified board capability news and kernel / architecture

- Merge declared board capability and possible board support evidence into the Board capability changes page. Group by commit and named board/target scope, attaching folder-level evidence only when there is one matching named scope for the commit/folder. Keep ambiguous shared-folder evidence separate. Original signals, confidence, paths and complete commit manifests remain available, with an evidence-type filter. Preserve the raw classifier kinds and legacy page URL (redirect with a fallback link).
- Replace the redundant dashboard card with Kernel & architecture. Classify kernel/, arch/, include/zephyr/kernel/, include/zephyr/arch/ and include/zephyr/kernel.h paths, with conservative title-prefix fallback. Keep fifteen cards and add navigation, search and icon support. Exclude general kernel changes from hardware-specific release inclusion unless a commit also has hardware events.
- Classifier version 3 refreshes recent events and schedules bounded historical refresh. No database schema change. Shared assets and navigation change; expect a one-time clean render and larger upload.

# v0.3.29 — Rolling commit freshness

- Mark commits from the last four hours with a small yellow `last` sticker in the left expansion column. Apply progressively subtler row tints for ages 0–4, 4–12 and 12–24 hours in both themes.
- Share freshness handling across static and dynamic news, watchlists, board recent activity, release inclusion and historical timelines, plus commit-based hardware and universal search results. Use exact commit timestamps, not publication time or PR update time. Recalculate in the browser every 30 seconds and on tab visibility changes; no timestamp-driven HTML churn.
- Preserve header sorting, pagination, row expansion and filter semantics. No classifier, database or hardware inventory cache changes. Board capability and candidate categories remain separate pending review.

# v0.3.28 — Board shortcuts and vendor-grouped explorer

- Move direct board profile links to the top of expanded commit and event details; remove redundant Related hardware / news actions throughout the shared news tables.
- Group Board Explorer by exact vendor identity. Collapse groups by default, show matched board counts and latest retained milestones, and automatically open matches when filtering. Keep sortable vendor and board headers, contextual links, watchlist filters and a flat no-JavaScript fallback.
- No database or classifier migration.

# v0.3.27 — Persistent home branding and fifteen news categories

- Keep the Zephyr Pulse home title visible even when the theme switches to its scrolled page-title state. Preserve external-link policy and internal navigation.
- Add DT bindings, Subsystems, Samples, Tests and West manifest news pages, dashboard cards, sidebar links, search types and icons. Dedicated tables reuse commit grouping, sortable columns and complete changed-file manifests. Desktop dashboard now has three rows of five cards.
- Classify explicit source paths before generic suffixes and title hints. Binding-compatible evidence moves to DT bindings while sensor introduction signals are retained; samples/tests/subsystems are not evidence of hardware support. Manifest changes identify manifest files, not necessarily a module revision bump. General software categories are excluded from hardware-specific release inclusion unless the commit also has hardware events.
- Classifier version 2 refreshes recent events atomically and schedules bounded historical refresh; no schema reset. Navigation configuration and assets change, requiring a one-time clean renderer cache build and larger upload.

# v0.3.26 — Activity-first board profiles and external navigation

- Make the text-only header brand a home link, including nested board pages. Open external HTTP(S) links in a new tab with noopener/noreferrer; preserve internal navigation and handle dynamically inserted links.
- Move recent board-associated commits directly below the overview. Reuse sortable expandable commit rows and complete cached Git manifests; include direct board-folder diffs even without classified events. Shared folders are explicitly folder-level evidence, not inferred driver/SoC impact. Retain the historical support timeline separately.
- Remove the visible photo attribution caption (preserve upstream image provenance in a data attribute) and misleading related-search link. Collapse each exact target capability section by default with a native accessible disclosure, keeping source evidence and table sorting.
- No database or classifier migration. Existing source-based disposable cache fingerprints and browser assets change, so expect a one-time cache refresh and larger upload.

# v0.3.25 — Category-aware tables and consistent commit navigation

- Use category-specific sortable columns across all ten news pages. Remove constant category columns and filters, retain meaningful hardware identifiers, and give the complete upstream commit title more space. Sensors omit the redundant subsystem column; SoCs show a genuine SoC/family scope; documentation, Devicetree and other news omit generic filenames from the collapsed row.
- Group new-board and candidate evidence by commit and conservative board/target scope. Group capability events only when their board/target, signal, confidence and commit agree; keep distinct capabilities visible. Add exact scope dropdowns, maintain board-profile links and preserve complete changed-file manifests and original evidence.
- Convert All commits and recent hardware release inclusion to sortable, expandable commit-level tables. Mixed categories remain visible and filterable. Preserve no-JavaScript summaries, exact release metadata and raw feeds. Collect manifests for every retained commit.
- Group board support timelines by historical commit, with expandable original milestones and evidence links. Do not claim complete historical manifests or invent missing commit titles. Keep board explorer, comparator, vendor metrics, release tags, PRs and personal watched-event semantics intact.
- Build browser-generated grouped detail panels only on expansion, while searching all changed paths and classified evidence before expansion. Preserve full-dataset header sorting, mobile sort controls, accessible expansion and pagination. Add unit and isolated Chromium regression tests; automatic CI remains lightweight.
- No database or classifier migration. Existing source-based disposable hardware cache fingerprints change; expect one cold run and a larger initial site upload.

# v0.3.24 — Commit-oriented hardware news

- Drivers and Sensors display one row per commit, with subsystem/driver identifiers, full original commit descriptions, affected-file counts, exact release inclusion and short SHA. The description, SHA and expansion triangle toggle the same detail panel; driver names are not filename-filter links.
- Group Documentation, Other changes and Devicetree by commit, and SoCs/Board maintenance by commit and conservative hardware scope. Keep New boards, Possible board support and Board capability changes event-oriented. Dashboard cards and category counters identify their units; watchlists and raw feeds retain individual evidence events.
- Publish cached first-parent Git changed-file manifests in the news dataset. Expanded groups list all changed paths, including additions, removals and renames, with revision-pinned source links and original classified evidence; extra evidence paths and incomplete manifests are explicitly identified. No schema or classifier migration. Existing disposable analysis cache fingerprints change because collector source changes; expect one cold cache run.
- Preserve full-dataset header sorting, pagination, keyboard expansion, filtering and mobile layout. Add subsystem/driver dropdowns, numeric file-count sorting and source-path search within groups.
- Add isolated Git and Chromium regression tests and extend the synthetic site fixture. Capture intentionally logged renderer fallback errors in unit tests. Automatic CI remains lightweight; browser checks remain manual.

# v0.3.23 — Lightweight CI and optional integration testing

- Automatic CI runs Python and JavaScript unit tests plus one synthetic Zensical site build on branch pushes and pull requests. Tags do not trigger duplicate runs; superseded runs are cancelled and execution is bounded by a timeout.
- Move repeated renderer stability/cache checks and all Chromium tests to a manually triggered extended workflow. Keep every existing test; no failure is silently ignored.
- Use a shared temporary fixture runner for GitHub and local testing, isolated from the production website, configuration and SQLite state.
- Fix both ambiguous board-profile heading selectors in the rendered browser test.
- No production code, CSS, JavaScript, database or configuration changes.

# v0.3.22 — Search smoke test synchronization

- Wait for the debounced exact-target search to settle before asserting a unique board card, and scope the universal search test to the Board targets group rather than matching news with the same title. Assert persisted query and result type after reload.
- Include the root `env/` virtual environment in `.gitignore`, alongside `.venv/`.
- No production code, CSS, JavaScript, database or configuration changes.

# v0.3.21 — Shared link icons and browser asset freshness

- Decorate ordinary static and dynamically created application links with semantic local SVG icons; retain existing icons, link text, destinations and filtering. Image-only links, heading anchors and theme controls are not decorated.
- Fingerprint local application CSS/JS references in staged HTML after rendering, including nested board pages. Unchanged assets retain their fingerprints; a changed shared asset updates referencing HTML once. Cloudflare must include query strings in its cache key.
- Recover board photographs with recognized raster signatures but incorrect extensions, preserving bytes, original upstream paths and blob verification; reject unknown/LFS files. No classifier migration or hardware analysis cache fingerprint change.

# v0.3.20 — Browser geometry regression fix

- Correct the rendered-site settings assertion: CSS fieldset grid tracks can serialize as repeat()/minmax() expressions, not whitespace-separated columns. Check real child positions, expected row counts and overlap instead. Reuse the same check for dashboard layouts.
- Exercise the actual settings builder at desktop and mobile widths in the direct browser smoke test. Keep CI enabled and allow the rendered smoke test to use an installed Chromium locally. No production code, configuration or database changes.

# v0.3.19 — Expanded news action icons

- Use local icons for Git commits, GitHub source files, board profiles, related categories, hardware search and exact subject filters in static and dynamic news details. Preserve links, filtering and keyboard behavior; let the compact action row wrap on small screens.
- Improve skipped board-image warnings with the detected raster format or Git LFS pointer indicator; keep the existing validation and publication policy.
- No database, classifier, configuration or renderer-template changes. The hardware analysis cache fingerprint is unchanged.

# v0.3.18 — Compact overview and board navigation

- Replace the redundant homepage category preview table with ten linked dashboard cards, including Other changes. Five columns on desktop, two on small screens, and one on very narrow screens; keep personal watchlist highlights and global feed links.
- Resolve exact board names, qualified targets and unique board-folder references to existing board profiles. Preserve non-board subject filters; offer a separate subject-filter action in board news details and a separate target filter in comparator discovery. Ambiguous board associations retain explicit related profile links rather than guessing.
- Use profile links in release inclusion, watchlist fallback, search results and board-scoped PR references; preserve upstream commit and proposal links.
- Fix ambiguous Playwright watchlist selector with a dedicated test ID, use a loopback fixture server instead of intercepted routes, and test dashboard geometry and both news rendering paths. Document the public synthetic PNG in the CI workflow.
- No database or configuration changes. Source changes may invalidate the disposable analysis cache on the first run; no new classifier migration.

# v0.3.17 — Board overview images

- Add compact, responsive board overview cards and lazy image thumbnails in exact-target hardware search. Read matching raster documentation assets from local Git, reuse immutable blob filenames and retain source attribution. No new dependencies or remote requests. Missing or ambiguous photos use a placeholder. Set `board_images: false` to disable publication.
- Retain the version-gated SQLite/classifier migration so direct upgrades remain safe; do not change classifier version.

# v0.3.16 — Source-aware news classification

- Preserve semantic hardware-support detection, then classify remaining changed files by subsystem path. Recognized commit prefixes are a candidate-only fallback; unmatched commits stay in Other changes with a representative source link when available.
- Recognize Devicetree API headers, existing bindings, source and tooling, driver/sensor and SoC maintenance, documentation updates, and separate Board maintenance from new support. Narrow Doxygen-only API documentation detection does not infer a hardware capability.
- Add change-type metadata, filter and sort choices to compact news tables, including dynamic and static rendering. Deleted-source links point to the parent revision. Hardware search indexes the new metadata.
- Automatically reclassify the rolling news window once per classifier revision using an atomic SQLite transaction. Refresh existing historical summaries in bounded batches, preserving previously processed history until each commit is replaced; keep introduction metrics separate from generic maintenance.
- Existing Git repository, configuration and private publisher remain unchanged. The first run may take longer and invalidate hardware analysis and renderer caches. Historical classification refresh progress is reported separately from history coverage.

# v0.3.15 — Compact expandable news tables

- Preserve the first header cell in the table layout; hide only its accessible label. Reserve a narrow 2rem desktop column and a 1.7rem mobile grid track for expand controls.
- Enlarge and center the category-colored triangle, retain keyboard focus and expansion state, and apply the same markup to static and JavaScript-rendered news tables.
- Add browser geometry regression coverage for desktop and mobile. No configuration or database changes.

# v0.3.14 — Contextual table navigation and column sorting

- Filter vendor activity rows and chart together on incoming vendor links; exact case-insensitive vendor and SoC filters, clearable URL state, and search links retain context.
- Add accessible ascending/descending header controls to data tables, sorting complete news and comparator discovery datasets before pagination; preserve expanded news details. Action-only headers remain non-sortable.
- No database or configuration changes.

# v0.3.13 — Disabled search index validation

- Accept Zensical 0.1.3's normal empty `search.json` in both clean and incremental builds. Reject nonempty or malformed indexes when native search is disabled; retain existing clean fallback and publishing protection. Preserve the small empty index rather than deleting a renderer-owned artifact.
- Correct CI checks to validate index contents and confirm a successful incremental cache baseline. No configuration or database changes.

# v0.3.12 — Focus release tracking on current hardware

- Track only the latest final release by default in inclusion checks, comparison snapshots, search and release pages; `release_tracking: latest_and_lts` optionally adds the latest final tag from explicitly configured `lts_series`.
- Exclude Zephyr `.99` development tags as well as release candidates, use numeric ordering, and label negative inclusion results as not in tracked releases rather than main only.
- Keep existing Git tags and full main history; obsolete snapshot cache entries are pruned by the existing snapshot cleanup. No migration of user data required.

# v0.3.11 — Compact layout, universal search and resource optimization

- Center the desktop layout at 70% viewport width on wide screens; retain responsive mobile layout and reduce settings form padding, typography and field heights.
- Add a lazy, generator-independent search dialog (Ctrl/Cmd+K) using structured hardware and news records. Native Zensical search defaults to disabled in fresh installations; an explicit existing configuration value is respected. Optional native search still indexes full static pages.
- Browser schema 3 separates stable `intelligence.json` from `data/activity.json`; the browser merges them. Category pages load one shared news view when native search is disabled, with raw JSON and all-commit links as no-JavaScript fallback. Board evidence and preference keys remain unchanged.
- Merge public YAML defaults with optional `config.local.yml` or an explicit `--config` override recursively; lists and scalar values replace defaults. Invalid YAML fails rather than silently reverting.
- Batch reject release commits unreachable from any stable tag, then check exact tag inclusion for remaining candidates. Report changed/new rendered bytes.
- Optional persistent Zensical workspace (`generator.incremental: true`), validated before publication, with clean fallback on failure and clean rebuild after Markdown deletion or renderer configuration changes. Default remains clean until tested on the deployment server.
- Optional private cron script supports `--dry-run`, keeps checksum verification, and reads merged configuration. No new dependencies, no Worker required. Full integration and live R2 testing remain deployment tasks.

# v0.3.10 — Category navigation and lighter browser data

- Overview lists every category with its complete 72-hour event count and newest timestamp. Expand for three recent events; clicking the category opens its full existing table. All category pages retain pagination, filtering, sorting and evidence expansion.
- Click subject links to toggle exact, case-insensitive filters across all pages of the current news table. Category links navigate to the corresponding tab. Preview subjects open the complete category already filtered; expanded details include same-subject category links (when present) and related hardware search. Links to the board explorer, vendor trends and comparator carry board/SoC/vendor context. Temporary linked filters do not replace saved watchlists.
- Compact `intelligence.json` schema version 2 retains feature states, exact targets, main/release metadata and references to separate immutable board-evidence JSON files. Full evidence loads only for selected comparator boards; board HTML retains its original source links. `data/news-view.json` supplies the homepage/watchlist and `data/preferences.json` supplies preferences and release choices. Unchanged evidence is not rewritten; the preceding catalog's evidence is retained for one additional build to assist cached clients.
- Validate new views and digest-addressed evidence before replacing the local site. Keep the existing clean Zensical build, caches, R2 sync, cron and browser storage schema. No new runtime dependencies. Generated `docs/data/` is ignored; keep your private `config.local.yml`, cron wrapper and credentials unchanged.
- First upgrade build may invalidate the previous analysis cache, refresh board HTML and upload the new evidence objects. Subsequent builds should transfer only changed content. Live dataset size and rendered browser behavior require deployment verification.

# v0.3.9 — Incremental hardware analysis and low-transfer publishing

- Persist hardware inventory and exact-target dependency caches in SQLite. Skip the full inventory when the relevant Git trees are unchanged; otherwise reuse target evidence when its include graph, compatible bindings and matching driver inputs are unchanged. Recheck unresolved includes and invalidate on analysis code changes or upstream history rewrites.
- Cache stable/LTS metadata and DTS evidence by Git tag object ID and target metadata path, including missing paths. Recompute release lifecycle labels on every run; discard cache entries for unselected tags.
- Keep board-specific evidence revision anchors stable while relevant inputs are unchanged. Preserve exact immutable source links, and update board-specific timelines when milestones change or expire. Remove global timestamps and global backfill progress from board profiles; retain them on global pages.
- Keep identical board Markdown files untouched, remove obsolete board pages, and report actual new/changed/unchanged/removed file counts for each validated HTML build. Keep the clean staged Zensical build and native search indexing for correctness; checksum-based publishing skips identical rendered files.
- Direct R2 cron publisher can use rclone `--fast-list --checksum` with full transfer summaries; no changes to credentials, cron schedule or the public URLs. No new Python dependencies. Cache table is created automatically.
- Added regression tests for unrelated commits, selective driver/binding/include invalidation, history rewrites, release retags, stable page output and removal of obsolete board pages. Real Zensical byte stability is checked in CI; live R2 transfer savings still require deployment measurement.

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
