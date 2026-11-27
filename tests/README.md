# Testing Zephyr Pulse

Automatic GitHub Actions (`Test`) runs on branch pushes and pull requests, not
on tag pushes. It runs Python and JavaScript unit tests and one real synthetic
Zensical build. It does not install or launch Chromium.

The `Extended browser and renderer tests` workflow is manual: Actions →
Extended browser and renderer tests → Run workflow. It builds the same
fixture, checks byte stability after an unrelated commit and two cached
renderer builds, and runs all nine Chromium smoke tests. Failures remain
failures; the manual workflow is not part of automatic CI.

## Local testing

From the project directory with Python dependencies installed and Node.js
available (use `.venv/bin/python`, `env/bin/python`, or your activated Python):

```sh
python -m unittest discover -s tests -v
node --test tests/test*.cjs
python tests/ci_fixture.py
```

For extended testing install Playwright in the same environment, then install
Chromium once (system Chromium is also supported by the browser tests):

```sh
python -m pip install playwright
python -m playwright install chromium
python tests/ci_fixture.py --extended
```

On Linux, if browser system dependencies are missing, use
`python -m playwright install --with-deps chromium` instead.

The fixture runner uses a temporary project and synthetic local Git repository.
It does not copy private configuration, credentials, generated docs, production
site, renderer cache or SQLite state. The temporary directory is cleaned on exit.
It does not publish to Cloudflare. Do not run `rendered_smoke.py` directly against
production output: that test expects the synthetic `kit/chip` board.

The grouped-news browser test can also be run directly with
`python tests/grouped_news_browser_smoke.py`; it exercises commit aggregation,
complete file lists, numeric file-count sorting across pages, filters, keyboard
expansion, and responsive layout without accessing the production site.

The category-layout smoke test is available as `python tests/category_layout_browser_smoke.py`.
It covers category-specific columns, header sorting, scope filters, lazy file
lists, mixed categories, capability signals and grouped board timelines.

The board-profile smoke test is available as `python tests/board_profile_browser_smoke.py`.
It generates a synthetic board from Git and checks the recent-commit table,
collapsed exact targets, home navigation, external-link policy and mobile layout.

The table-controls browser smoke test also covers vendor-grouped Board Explorer:
collapsed defaults, expand/collapse, exact contextual filters, vendor counts,
child table sorting and mobile access. News detail regressions verify that
board shortcuts precede commit titles and redundant related-search links are absent.

The freshness regression test (`python tests/freshness_browser_smoke.py`) uses a
controlled browser clock to verify the four-, twelve- and twenty-four-hour
thresholds, light/dark colors, mobile badge geometry, dynamic table updates,
filtering, sorting, expansion and automatic expiry.

## Scoped analysis cache maintenance

`performance.py` fingerprints three cache domains from their producer functions and statically discoverable local source dependencies. The inventory includes per-target DTS evidence; release snapshots share the DTS and YAML parsers but have their own producer. Recent Git file manifests depend on the diff reader only. The existing exact-release-inclusion cache and Zensical cache remain separate.

When adding indirect dependencies (object methods, dynamic imports, runtime dispatch, non-Python inputs) register the relevant producer roots or bump `CACHE_FORMAT` for a storage/validation change. Direct local function and constant dependencies are followed automatically. Progress reporting is deliberately excluded. These fingerprints are not a general Python runtime dependency tracker. Keep the v0.3.30 promotion constants fixed; a changed producer must not accept legacy cache entries. Run `python -m unittest discover -s tests -p test_cache_fingerprints.py -v` to check invalidation isolation and migration.

### Compact rows (v0.3.32)

`python tests/compact_tables_browser_smoke.py` checks one-line geometry at desktop and mobile widths, inline evidence/freshness badges, title sorting independent of the badges, complete hidden evidence search, and collapsed comparator source links. It is included in the manual extended workflow. Long news strings are visually clipped but preserved in titles and expanded details. Narrow tables scroll horizontally.

### Smart publishing (v0.3.35)

When `generator.incremental: true` and `generator.native_search: false`, the renderer can reuse the last validated persistent output if only application JSON, RSS, or board-image files changed. Markdown, CSS/JS, unknown assets, renderer configuration and native search still follow the normal renderer path. Failure triggers the existing clean staged fallback. The extended synthetic CI run verifies that a repeated unchanged build reports `Zensical fast path: renderer skipped` and that the browser reads the shared collection timestamp.

`data/status.json` contains the exact latest collection timestamp, head, window, historical coverage/cutoff and last successful PR refresh. The `updated` fields in the other JSON snapshots identify when their content last changed; the activity snapshot retains its previous cutoff within a UTC day if no substantive data changed. Use status for the current exact cutoff. The header uses JavaScript to display the status and shows a dash if it is unavailable. PR snapshots default to a 60-minute refresh interval; set `pull_requests.refresh_minutes: 0` to fetch every run. Failed refreshes are marked stale and are retried; a different branch or page limit forces a new fetch.

Run `python -m unittest discover -s tests -p test_smart_publish.py -v` and `python tests/status_browser_smoke.py` for isolated tests. Full real-renderer verification is provided by `python tests/ci_fixture.py --extended` (temporary synthetic project, no production publishing).
