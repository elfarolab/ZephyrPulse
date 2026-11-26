# Zephyr Pulse v0.3.2

An unofficial, MIT-licensed hardware-focused rolling news site for upstream Zephyr RTOS. Follow new boards, SoCs, sensors, drivers, devicetree changes, documentation and possible newly usable peripherals instead of reading raw `git pull` output.

## Quick start

Linux, Git >= 2.37, Python >= 3.11, and Python's venv module are required. The initial fetch uses a full single-branch bare Git clone (allow sufficient disk space and network time). No Zephyr SDK, `west`, GitHub API token, or AI API is required. The optional open-PR snapshot uses the public GitHub REST API, with an optional token for rate limits.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python pulse.py --no-publish
.venv/bin/python -m http.server 8000 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8000/. Generated Markdown, JSON and RSS are in `docs/`; HTML is in `site/`; local bare Git repository and SQLite database are in `state/`. `--no-build` runs collection and Markdown generation without a renderer or publishing. `--no-publish` builds locally without uploading even if publishing is enabled.

## Configuration

Edit `config.yml`: `upstream`, `branch` (default main), `window_hours` (72), `state_dir`, `site_url` (public RSS channel link), and `publish` (false until deployment is configured). The Zensical adapter automatically passes `site_url` to the staged build for canonical URLs/sitemap. Serve at the root of a domain. Changing the upstream repository or branch requires a fresh `state_dir`; links are intentionally fixed to official upstream Zephyr. The collector uses the branch's **first-parent history**, comparing each mainline commit with its first parent; a merge contributes its net diff once, rather than duplicating side commits. Dates are Git committer timestamps converted to UTC (not GitHub merge timestamps or author dates). New commits are processed oldest first; the checkpoint is committed with events in a single SQLite transaction. If a tracked head is no longer on the first-parent chain, the rolling window is rebuilt. The first run backfills 72 hours of detailed news; all older detailed commits/events expire on subsequent runs. A separate bounded historical summary is retained for 90 days. The checkpoint remains. The raw Git clone keeps history independently of the 72-hour SQLite limit.

## New in v0.3.2: console progress and diagnostics

No configuration or database migration required. Default INFO logging includes startup, elapsed times, Git clone/fetch progress, recent and historical commit counters, inventory, release checks, PR fetches, page generation, renderer validation and publishing. Active stages report a heartbeat every 15 seconds (including nested stages); this confirms the Python process is alive, not that its subprocess is making progress. `--verbose` / `-v` adds per-item and low-level Git operation diagnostics. Output is flushed by Python logging to stderr, while network Git progress is streamed directly. Neither `--no-publish` nor `--no-build` skips upstream collection or history processing.

```bash
python pulse.py --no-publish
python pulse.py --no-publish --verbose
# Capture both stdout and stderr, preserving failures in bash:
set -o pipefail
python pulse.py --no-publish 2>&1 | tee pulse-run.log
# Scheduled service logs:
journalctl -u zephyr-pulse.service -f
```

First clone downloads the full configured branch history and tags, not only 72 hours. Do not start a second collector while one is running. Stop the previous process/timer before upgrading; preserve `state/`, `config.yml`, credentials and the website origin. No new dependencies. If a heartbeat repeats without item progress, inspect the active child processes (`ps -eo pid,ppid,etime,%cpu,stat,args --forest`). This release adds visibility, not performance optimizations or new timeouts. Review logs before sharing, especially Git error messages from authenticated remotes.

## New in v0.3.1: Zensical and portable search

Zensical 0.1.3 is pinned in `requirements.txt`; the native `zensical.toml` uses the classic theme to minimize changes to URLs and existing frontend styles. No MkDocs or Material packages are needed. Python 3.11+ is required. Install `requirements-core.txt` instead if you only collect data with `--no-build`.

The collector writes Markdown, JSON, RSS and static assets under `docs/`. `generators/` contains the renderer interface, validation and Zensical adapter. It copies content to a fresh temporary workspace, builds there with `--clean` (and `--strict` by default), checks every expected HTML page, unchanged data/assets and required mounts, and replaces `site/` only after successful validation. The publisher runs only after a successful build; immutable R2 releases preserve the previous published site if a build/upload fails. Fresh staging avoids carrying obsolete board pages into the next published release. The flat `.html` URL convention is part of the adapter contract. Future adapters can implement `render(project, workspace, site_url)` without changing Git or SQLite code. `theme-zensical.js` bridges the optional palette preference; other application JavaScript does not use theme APIs. CSS includes fallback colors. An alternative generator would still need to load the same assets and maintain the URL/mount contract.

**Search:** Zensical has native client-side full-text search, enabled by default. No MkDocs search plugin or third-party search service is used. Set `generator.native_search: false` in administrator configuration to omit it from the build. **Hardware search** remains available regardless: it uses the public `intelligence.json` dataset and vanilla JavaScript, and does not rely on native search indexes. It searches exact board targets, recent events, upcoming PRs, vendor activity and release tags; it supports case-insensitive substring/glob search (comma-separated OR), category, attributed vendor, date range and optional watchlist filter. Capability filters require every specified exact capability (wildcards are also supported) on current target metadata; they never infer CAN FD from CAN or support from PRs. Use the comparator to compare release baselines. Undated targets/tags are excluded when a date filter is used. News without a known board/vendor association is not included in vendor-filtered results. PRs may be stale or unmerged, and are explicitly marked. Search filter preferences persist in the existing browser store, are editable in Settings, and participate in JSON import/export. Global news remains unfiltered. For the complete list of historical limits see below. Search is a client-side scan of the existing dataset, not a second index; performance on the entire live catalog is not yet benchmarked.

**Upgrade from v0.3.0:** stop the timer and service, back up `state/` and `config.yml`, deploy the new application files, preserve your administrator settings and credentials, remove the old `mkdocs.yml`, install `requirements.txt` in a Python 3.11+ virtual environment, and run `python pulse.py --no-publish`. Serve `site/` with `python -m http.server 8000 --bind 127.0.0.1 --directory site`. Once validated, restart the timer and enable normal publishing. No SQLite migration or browser preference reset is required; the storage key remains unchanged. Keep the same website origin. For rollback, retain the v0.3.0 source and its old virtual environment and the previous R2 release pointer.

## New in v0.3: hardware selection and browser preferences

Open **Compare hardware** and **Settings** from the navigation. The comparison catalog covers all current discovered board targets, not only watched hardware. Select up to eight exact target identifiers, enter required capability names (or choose from the known identifiers), and search by board, SoC, vendor or target with case-insensitive substring/glob matching. The discovery table ranks by requirements with source evidence, not by product readiness. Optionally require evidence for every requirement. YAML declarations are counted separately from DTS hints. Compare all relevant rows, only required rows, or differences plus required rows. Selected targets remain saved even when hidden by discovery filters; missing targets are explicitly labeled and can be removed.

The comparator distinguishes **Declared (YAML)**, **DTS source hint**, **Present in DTS; no okay hint**, **No evidence found**, and **No exact metadata**. These are source observations, not hardware verification. No target features are inherited from other CPU targets. CAN is not CAN FD, USB host is not inferred from USB/device, and Bluetooth LE is not inferred from generic Bluetooth. Known feature identifiers come from the data; custom requirements not explicitly declared are not assumed. RAM/flash (normally KiB), architecture and SoC lists are main-branch metadata; SoC lists are board-level, not a CPU-to-SoC inference. Milestones and vendor counts are also board/vendor context, not per-target verification.

**Release baseline:** choose main, the latest stable tag at collection time, or the latest patch tag of each configured LTS series. At each tag the collector looks for the same current metadata path and exact target identifier, then reads declared features from that tag. Older hardware-model layouts, renamed files or target identifiers can yield no exact metadata; that is unknown, not unsupported. A selected tag is pinned by name; if a newer snapshot replaces it, the old selection is shown as unavailable until you choose another. Release lifecycle remains a dated administrator policy. No release builds or hardware tests are executed.

### Personal settings (no YAML editing needed)

The browser settings panel edits board/SoC, vendor and peripheral watchlists; required capabilities; comparison baseline and rows; discovery search/filter; board explorer search/filter; vendor chart default; homepage and watchlist list limits; and theme. Selected comparison targets are managed directly in the comparator and can also be cleared in Settings. Comparator controls save immediately; Settings uses **Save preferences**. Preferences are stored in `localStorage` under `zephyr-pulse-preferences-v3`. Existing v0.2 watchlists migrate automatically on first use. Precedence is per field: browser override > published YAML default > built-in default. Explicit empty lists and false values override YAML. Unedited fields follow new published defaults. Changes in another tab are picked up when the page is reloaded.

**Export JSON** saves the effective preferences (including selected target IDs); keep separate files for different product designs. **Import JSON** replaces current browser overrides after confirmation. **Restore published defaults** clears overrides. Browser settings are per origin/browser profile; no account or cross-device sync is provided. If browser storage is blocked, changes apply only to the current page; export is still possible while that page is open. The theme preference `default` leaves the theme's own palette control in charge.

Server administrators can optionally seed defaults under `watchlist` and `preferences` in `config.yml`; visitors do not need to modify either. Private server settings (upstream, branch, scheduler, retention, release lifecycle, PR collection, deployment credentials/destination) remain server-side. The global news and RSS are always unfiltered, and the public watchlist RSS remains server-configured. The `intelligence.json` dataset now includes the `preferences` and `comparison` objects. No personal settings are sent to the server.

### Upgrade from v0.2

Back up SQLite and keep `state/`, deployment credentials, systemd setup and any existing administrator configuration. Stop the timer/service while replacing the application files, retain your server config (the new preference defaults are optional), then run `python pulse.py --no-publish` in the virtual environment before enabling normal publication. No new SQLite schema is required; release target snapshots are regenerated from Git tags. Existing localStorage watchlists are migrated on visiting the new site on the same origin. The latest stable and LTS target scans add Git reads and increase the JSON size; full upstream runtime has not been benchmarked.

## New in v0.2

| Page / feed | Purpose |
| --- | --- |
| Overview | Unfiltered priority news and all-category previews, plus an independent watchlist section |
| Board explorer | All current board.yml definitions, SoCs and targets; optional search / watchlist-only toggle |
| Board profile | Per-target declared support matrix, raw board-folder DTS evidence, source links and 90-day milestones |
| Vendor activity | Unique attributed hardware commits, new-board and capability signals, driver/sensor introductions, driver changes, fix/test-source signals, distinct Git authors, and daily trend chart |
| Watchlist | Server default patterns, browser-local personal patterns, server watchlist RSS |
| Releases / LTS | Stable release tags, exact commit reachability, configured support lifecycle and EOL information |
| Upcoming PRs | Recently updated hardware-related open and draft PRs, separate from merged news |
| `feed.xml`, `events.json` | Global news feeds; JSON includes board IDs, release metadata and configured watchlist matches |
| `watchlist.xml`, `intelligence.json` | Configured watchlist feed and public dashboard dataset |

### Watchlists: additive, never exclusive

```yaml
watchlist:
  boards:
    - '*mcxn*'
    - ra8P1
    - '*nrf54*'
  vendors:
    - nxp
    - renesas
  peripherals:
    - ethernet
    - can
```

All patterns are case-insensitive. Plain terms are substring matches (`ra8P1` matches `RA8P1` and `renesas/ra8p1`); globs support `*`, `?`, and character classes (`mcxn94[57]`). Quote globs in YAML. Board matching checks names, full names, source folders, SoCs, variants/targets, and event text. Vendor and peripheral matching also uses event text, so false positives are possible. Any category match qualifies (OR), not all categories at once. The server config affects the additional watchlist page and RSS only. The public homepage, all-category pages and global feed never filter out nonmatching boards. Visitors can create their own watchlist in browser localStorage without accounts or backend, and restore server defaults. The personal watchlist does not change public RSS. The optional board-catalog filter is local to that page and defaults to all boards.

### History and migration

The existing v0.1 SQLite schema is migrated automatically with `CREATE TABLE IF NOT EXISTS`. Back up `state/pulse.sqlite3` before upgrading (stop the service or use SQLite backup). Keep the existing `state/` and R2 configuration. Replace the application files, merge new config keys, and run normally.

`window_hours: 72` governs detailed `commits` and `events`. `history_days: 90` governs the separate compact tables `history_seen`, `milestones`, `vendor_activity` and cached tag results. Old milestone summaries preserve dates, board IDs, brief labels and source commit references, not full raw news. The full bare Git clone remains on disk. Rewritten main history removes orphaned summary records. Historical board associations are based on the current catalog and source folder; removed/renamed boards, shared folders, and old layout changes may be incomplete or ambiguous. No fabricated zero-activity conclusions should be drawn from incomplete backfills.

Default `history_batch: 250` processes up to 250 older commits on each run in addition to all recent news. The pages display processed/total coverage. To complete the historical backfill in one run (potentially expensive on full upstream history):

```sh
.venv/bin/python pulse.py --history-backfill --no-publish
```

Do not run the backfill simultaneously with the timer; the file lock prevents overlap. The initial full clone plus tag fetch can require substantial disk and bandwidth. Exact release-tag containment is cached per commit and invalidated whenever fetched tags or configured LTS classification change. Support policy dates are intentionally separate from Git tags: the config contains a dated policy snapshot, not an automatically scraped lifecycle promise. Consult [official release policy](https://docs.zephyrproject.org/latest/releases/index.html) and update `release_policy` and `lts_series` as new releases arrive. Historical LTS tags (e.g. 2.7) do not imply active support. Cherry-picked backports and later reversions may not be detected by exact-commit reachability. “First stable tag” means lowest containing stable semantic version, not necessarily publication chronology.

### Upcoming PRs and vendor metrics

`pull_requests.enabled: true` reads up to `pages: 2` pages of 100 recently updated open PRs targeting main from the [GitHub REST API](https://docs.github.com/en/rest/pulls/pulls). Title/label heuristics select hardware-related proposals. This is not a comprehensive PR tracker; open items are not available support. On API error/rate limit the last successful snapshot is retained with a stale marker. Set `GITHUB_TOKEN` in the protected service environment if necessary, never in the published files. The clone and merged-news processing do not depend on the API. Disable it for completely Git-only operation.

Vendor activity is attributed to the hardware namespace inferred from paths/board metadata, not employer identity. One commit can affect multiple vendors and signal categories. Distinct Git authors are estimated from hashed commit author emails; no hashes/emails are published in feeds. Test-source signals are not test coverage or test results, and fix signals use commit-title heuristics. The per-board capability matrix combines exact-target YAML with revision-pinned DTS source hints, not compiled configuration; an absent feature means no evidence was collected, never “unsupported.” Raw DTS evidence is file-local, potentially shared by multiple targets. These conservative distinctions help screen candidates for a future design without making unsupported product-readiness claims.

## Detection rules

| Event | Evidence |
| --- | --- |
| New board | Added board name in `boards/<vendor>/<folder>/board.yml` |
| Board capability | New board variant/SoC, new `supported:` metadata item, or explicit same-source DTS `disabled` → `okay` |
| Possible board support | New board configuration, changed node compatible, explicit `okay` added, new driver compatible matched to board source or shared include |
| Sensor | New `DT_DRV_COMPAT` under `drivers/sensor/`, new implementation source, or sensor binding |
| Driver | New driver-compatible declaration or implementation file under `drivers/` |
| SoC | New SoC name or changed/new `soc.yml` |
| Devicetree | New/modified DTS/DTSI/overlay source, new/changed binding compatible |
| Documentation | Added `.rst`/`.md` files in `doc/` or board `doc/` directories |
| Other changes | A mainline commit for which none of the rules matched |

Events can belong to multiple categories. The homepage highlights observed priority events and links to category pages, including possible board support. Counts are events, not unique boards, devices, drivers, or commits. Each item includes date/time, a source link, a commit link, and evidence. There is also a first-parent commit list, RSS feed, and machine-readable JSON.

### Why possible support is separate

`DT_DRV_COMPAT acme_temp123` is matched to existing binding-compatible strings (e.g. `acme,temp123`) and then to quoted DTS references. Shared DTS includes are traversed in reverse by filename (up to 5 levels and 150 visited files). This allows a driver-only commit to surface an existing board. The include search is approximate (same basenames, conditional includes, and indirect includes may yield false positives/negatives). A driver declaration may be moved/refactored or already exist elsewhere; a new binding is not proof of a new implementation. The lexical DTS scanner does not preprocess C macros, compile DTS, resolve overlays, `/delete-node/`, default status, build targets, Kconfig dependencies, or actual devices. `observed` means only an observed source/metadata difference, not successful compilation or hardware validation. `candidate` means investigate. The site reports exact Git release-tag inclusion, not verified feature availability, vendor endorsement, commercial production readiness, or confirmed hardware operation. Deletions, regressions, downstream modules and backports are not exhaustively tracked by v0.3.

## Deploy to Cloudflare R2

1. Create a **private** R2 bucket, e.g. `zephyr-pulse`, and create R2 S3 API credentials scoped to read/write objects in that bucket. Install AWS CLI v2 on the Linux server and ensure `aws` is on PATH. The Worker does not need these credentials.
2. Copy `deploy/env.example` to `/etc/zephyr-pulse.env`, populate real values and restrict permissions to root (`chmod 600`). Never commit credentials. For interactive testing, use shell environment variables instead.
3. Set `publish: true` and public `site_url` in `config.yml`. Run the collector with the environment loaded to upload the first release. `deploy/publish.sh` uploads `site/` to a new `releases/<id>/` prefix and only then updates `current.json`; no live files are deleted. This prevents a failed sync from switching the live release. Old releases are retained; periodically prune them **after** confirming the active pointer, or implement a retention job that preserves the active release and recent rollbacks. Do not apply a blanket age-based lifecycle to active content. Because each HTTP request reads the pointer independently, a deployment between page and asset requests can still cause version mismatch. For this simple site, stable theme assets and no-store caching are used; content-addressed asset routing is a possible future improvement.
4. Install Node.js/npm and configure the Worker:

```sh
cd deploy
cp wrangler.example.toml wrangler.toml
# edit bucket_name to match your R2 bucket
npx wrangler login
npx wrangler deploy
```

5. In Cloudflare Workers & Pages, attach a custom domain to the Worker. It serves root `/` as `index.html`, reads the active release pointer, and maps requests to R2 objects. `use_directory_urls: false` avoids directory-index routing issues for page links. The bucket remains private. The Worker sets `no-store` to avoid stale content; review request costs and implement CDN caching for immutable assets if traffic grows.

References: [R2 S3 API](https://developers.cloudflare.com/r2/api/s3/), [R2 Worker bindings](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/), [Zephyr board porting guide](https://docs.zephyrproject.org/latest/hardware/porting/board_porting.html).

## Run every four hours via systemd

Copy the repository to `/opt/zephyr-pulse` and create an unprivileged user with write access to this directory (generated docs, site, state) and read access to code. On a typical Debian/Ubuntu server:

```sh
sudo useradd --system --home-dir /opt/zephyr-pulse --shell /usr/sbin/nologin zephyr-pulse
sudo chown -R zephyr-pulse:zephyr-pulse /opt/zephyr-pulse
cd /opt/zephyr-pulse
sudo -u zephyr-pulse python3 -m venv .venv
sudo -u zephyr-pulse .venv/bin/pip install -r requirements.txt
sudo install -m 0644 deploy/zephyr-pulse.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now zephyr-pulse.timer
sudo systemctl start zephyr-pulse.service
sudo journalctl -u zephyr-pulse.service -n 100
systemctl list-timers zephyr-pulse.timer
```

Use the root-readable environment file from the deployment steps (systemd loads it before switching service user). The timer runs at 00:00, 04:00, 08:00, 12:00, 16:00 and 20:00 UTC. Persistent timers catch up after downtime. The collector also holds an OS file lock. A build or upload failure leaves the last published release active; the next run renders the entire current window again from SQLite. The systemd unit has a two-hour timeout; adjust if initial clone or backfill is slower.

## Tests and roadmap

```sh
python -m unittest discover -s tests -v
```

The local fixture suite uses actual temporary Git repositories and SQLite to test board/driver detection, inherited candidate matching, expiry, repeat collection, merge handling, rewritten history, lexical parsing, wildcard matching, unfiltered global news, historical retention, bounded backfill, stable/LTS tag inclusion, cache invalidation and stale PR snapshots. CI installs the pinned Zensical version, validates a synthetic site build and exercises the rendered application in Chromium. Run `node --test tests/test*.cjs` for preference, comparator and search logic. Optional real-browser test: install Playwright, run `python -m playwright install chromium`, then `python tests/browser_smoke.py`. Run the current fixture suites to verify this release (including staged-build success/failure using a fake renderer). The pinned Zensical package could not be installed in the local execution environment, so actual Zensical rendering and native search are not locally verified. CI is configured to test actual rendered output and browser behavior; native search UI behavior still requires manual checking. Live upstream ingestion, end-to-end Cloudflare deployment, and actual board builds require testing outside the fixture environment.

Next steps:
- Index effective devicetree and Kconfig for selected boards using pinned Zephyr revisions, `west build`, and `edt.pickle`/`zephyr.dts`. Compare previous/new compiled capabilities rather than source-only heuristics. Sandbox all upstream code execution; no publishing credentials in build environments.
- Build representative samples (CAN, USB, Ethernet, sensor, ADC) for watchlisted boards. Keep build verification separate from hardware testing.
- Improve reverse dependency indexing and add board rename tracking, persistent milestones beyond 90 days and richer release/backport detection.
- Group related commits and enrich merged commit links with PR metadata. Track regressions and reverted features explicitly.
- Track selected west modules and HALs separately, with commit attribution.
- Publish per-category feeds, and a weekly health summary.

## License

MIT for this project. Upstream Zephyr, third-party packages, and theme assets retain their own licenses. The collector publishes derived event descriptions, short commit subjects, and links rather than mirroring upstream source code. Zephyr Pulse is an unofficial independent project, not affiliated with the Zephyr Project. Verify name availability and trademark requirements before public launch.

## Git history compatibility (v0.3.4)

Older Git versions may exit 129 when encountering `--since-as-filter` in v0.3.3. Both recent news and historical analysis now use a single local first-parent metadata walk per date window, filtering UTC committer timestamps in Python. Unlike plain `--since`, this does not skip newer ancestors behind a commit with an older timestamp. The script logs `git --version` at startup. No new dependencies are required for this fix; this is not a guarantee of compatibility with every older Git version.

To upgrade, stop the collector and any timer, extract the v0.3.4 compatibility update into the existing project, and run `python pulse.py --no-publish`. Preserve `state/zephyr.git`, `state/pulse.sqlite3`, and `config.yml`; no reclone is necessary. For diagnosis, run `python pulse.py --no-build --no-publish` to exercise data collection separately from the static renderer.

## Git transfer recovery (v0.3.3)

Git now initializes a persistent bare repository, fetches the configured branch and then fetches tags separately. Each transfer defaults to three attempts with 15/30 second backoff and HTTP/1.1. Git aborts HTTP transfers below 1 byte/s for 120 seconds (not an overall deadline). Successful packs/refs are retained; interrupted packs are not guaranteed resumable. No SQLite update or publication occurs if synchronization fails.

If you already have a complete local Zephyr checkout, seed the first sync with `python pulse.py --no-publish --git-seed /path/to/zephyr`. This uses the local origin branch if present, otherwise the local branch, then fetches from the configured upstream. The checkout is not modified. The seed option is ignored when the collector already has the branch.

Optional server settings (no changes required to existing YAML):

```yaml
git_transport:
  attempts: 3
  retry_delay_seconds: 15
  low_speed_seconds: 120
  http_version: HTTP/1.1  # or HTTP/2 or auto
```

A nonempty invalid repository is never deleted automatically. With the collector stopped, rename `state/zephyr.git` to a backup name and retry; keep `state/pulse.sqlite3`. Full history is retained for exact release reachability. A shallow or partial clone is intentionally rejected.

## v0.3.5: navigation, dashboard and source evidence

- Zensical sticky tabs and six navigation groups; suppress event-heavy right-hand tables of contents. Home shows at most three recent observed items per priority category and three candidate items. Full category pages retain all events, with 12 cards per browser page and no-JavaScript fallback.
- Exact-target YAML remains separate from DTS evidence. The collector reads tracked blobs at the selected revision, follows literal DTS includes, associates compatible and status properties, maps known binding families and specific compatibles, and locates matching `DT_DRV_COMPAT` driver declarations. All links point to the source revision or its file history. Official board docs are linked where a matching source page is found, but never scraped as the authority for main or release snapshots.
- Source hints are heuristic: no C preprocessor, Zephyr effective devicetree, parent enablement, overlays, Kconfig, build or hardware test is evaluated. Last scanned status is not a guaranteed effective status. Omitted status is a default-okay hint only. The comparator counts YAML and positive DTS hints separately; disabled-only or unknown evidence is not counted. A driver-token match is not proof of usable driver configuration. Missing target YAML, unresolved includes, complex DTS syntax and older layouts can still cause incomplete coverage.
- Preserve the existing repository, SQLite, configuration and same-origin localStorage. Stop the timer/collector, extract the v0.3.5 update over v0.3.4, and run `python pulse.py --no-publish`. No new dependencies or database migrations. New data is computed each run, including release snapshots, so some additional processing and larger JSON are expected.

## v0.3.6: dashboard iconography

The application uses original local SVG masks under `docs/assets/icons/` and portable HTML/CSS for dashboard cards and shortcuts. Zensical-specific tab decoration lives in `theme-zensical.js`; the header CPU icon uses the built-in Zensical icon set. Icons are decorative and text labels remain accessible. No CDN or extra dependencies. To upgrade from v0.3.5, stop the collector, extract the icon update at the project root and run `python pulse.py --no-publish`. Preserve `state/`, configuration and browser storage.


## v0.3.7: personal settings (historical branding note; superseded in v0.3.8)

Settings use two columns on wide screens and a single column on smaller screens. Save preferences explicitly; export includes saved values. The collector copies `doc/_static/images/logo.svg` from the exact collected Git revision to `docs/assets/zephyr-upstream.svg`. The renderer uses it when present; otherwise the CPU icon remains. No network download or extra dependencies are needed. The Zephyr logo is not licensed by this project's MIT license; consult [Zephyr branding guidance](https://zephyrproject.org/branding/) and obtain permission where required before public deployment. Zephyr Pulse is unofficial and not endorsed by the Zephyr Project.

## v0.3.8: compact news tables

Overview and category pages show one line per event on desktop, with inline expandable evidence. The entire window is available on Overview, not only priority previews. Choose 25, 50, 100 (default), 200 or All rows per page; filter by text/category or sort by time, category, subject, associated vendor or confidence. Controls are per page and do not change saved preferences. On small screens the rows stack. Without JavaScript, the static details remain visible. The header uses only the Zephyr Pulse title; the old upstream logo is removed during generation.

Upgrade from 0.3.7: extract the update in the application directory, run `python pulse.py --no-publish`, then refresh the browser. Preserve `state/`, `config.yml` and browser storage.
