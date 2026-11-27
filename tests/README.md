# Testing Zephyr Pulse

Automatic GitHub Actions (`Test`) runs on branch pushes and pull requests, not
on tag pushes. It runs Python and JavaScript unit tests and one real synthetic
Zensical build. It does not install or launch Chromium.

The `Extended browser and renderer tests` workflow is manual: Actions →
Extended browser and renderer tests → Run workflow. It builds the same
fixture, checks byte stability after an unrelated commit and two cached
renderer builds, and runs all eight Chromium smoke tests. Failures remain
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
