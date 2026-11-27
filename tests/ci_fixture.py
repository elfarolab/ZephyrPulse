"""Build and test a synthetic site in an isolated temporary project.

Never use the production config, state, renderer cache, or generated website.
The default runs one real render; --extended adds stability/cache/browser checks.
"""
import argparse
import base64
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jP1sAAAAASUVORK5CYII='
BROWSER_TESTS = ('news_browser_smoke.py', 'table_browser_smoke.py', 'browser_smoke.py',
                 'link_icons_browser_smoke.py', 'rendered_smoke.py')
REQUIRED = ('index.html', 'boards.html', 'watchlist.xml', 'intelligence.json',
            'compare.html', 'settings.html', 'hardware-search.html')


def run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True)


def stage_project(root, project):
    project.mkdir()
    for path in root.glob('*.py'):
        shutil.copy2(path, project / path.name)
    for name in ('VERSION', 'config.yml', 'zensical.toml'):
        shutil.copy2(root / name, project / name)
    for name in ('generators', 'docs/assets', 'tests'):
        shutil.copytree(root / name, project / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))


def create_upstream(repo):
    repo.mkdir()
    run(repo, 'git', 'init', '-b', 'main')
    run(repo, 'git', 'config', 'user.email', 'test@example.invalid')
    run(repo, 'git', 'config', 'user.name', 'Fixture')
    run(repo, 'git', 'config', 'commit.gpgsign', 'false')
    run(repo, 'git', 'config', 'tag.gpgsign', 'false')
    run(repo, 'git', 'config', 'core.hooksPath', '/dev/null')
    board = repo / 'boards/test/kit'
    (board / 'doc').mkdir(parents=True)
    (board / 'board.yml').write_text('board:\n  name: kit\n  socs:\n    - name: chip\n')
    (board / 'kit.yaml').write_text('identifier: kit/chip\nsupported: [gpio, can]\n')
    # Public synthetic 1x1 PNG fixture; not a credential.
    (board / 'doc/kit.png').write_bytes(base64.b64decode(PNG))
    run(repo, 'git', 'add', '.')
    run(repo, 'git', 'commit', '-m', 'new board')
    run(repo, 'git', 'tag', 'v4.0.0')


def board_hashes(site):
    hashes = {p.relative_to(site).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (site / 'boards').glob('*.html')}
    if not hashes:
        raise RuntimeError('No rendered board pages')
    return hashes


def validate_search(project):
    run(project, sys.executable, '-c',
        "from pathlib import Path; from generators import get_generator; "
        "get_generator({'native_search': False})._validate_search(Path('site'))")


def exercise(work, extended):
    project, repo = work / 'project', work / 'upstream'
    stage_project(ROOT, project)
    create_upstream(repo)
    config = work / 'fixture.yml'
    settings = {'upstream': str(repo), 'branch': 'main', 'state_dir': 'state/ci',
                'site_url': 'http://localhost:8000/', 'publish': False,
                'board_images': True, 'pull_requests': {'enabled': False},
                'generator': {'engine': 'zensical', 'strict': True,
                              'incremental': False, 'native_search': False}}
    config.write_text(yaml.safe_dump(settings))
    def build():
        run(project, sys.executable, 'pulse.py', '--config', str(config), '--no-publish')
    build()
    site = project / 'site'
    for name in REQUIRED:
        if not (site / name).is_file():
            raise RuntimeError(f'Missing fixture output: {name}')
    baseline = board_hashes(site)
    validate_search(project)
    if not extended:
        print('Sample website build passed.')
        return
    def check_stability():
        if board_hashes(site) != baseline:
            raise RuntimeError('Board HTML changed after unrelated input or renderer mode change')
    (repo / 'doc').mkdir()
    (repo / 'doc/unrelated.rst').write_text('Unrelated documentation\n')
    run(repo, 'git', 'add', '.')
    run(repo, 'git', 'commit', '-m', 'unrelated documentation')
    build()
    check_stability()
    settings['generator']['incremental'] = True
    config.write_text(yaml.safe_dump(settings))
    for _ in range(2):
        build()
        check_stability()
        if not (project / '.pulse-render-cache/signature').is_file():
            raise RuntimeError('Expected persistent renderer cache signature')
        validate_search(project)
    for test in BROWSER_TESTS:
        run(project, sys.executable, str(project / 'tests' / test))
    print('Extended renderer and browser checks passed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extended', action='store_true', help='also run stability and browser tests')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='zephyr-pulse-ci-') as tmp:
        exercise(Path(tmp), args.extended)


if __name__ == '__main__':
    main()
