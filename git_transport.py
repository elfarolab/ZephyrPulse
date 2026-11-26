"""Resilient Git synchronization. No shallow/partial history for release analysis."""
from __future__ import annotations

import logging
import os
from pathlib import Path
import subprocess
import time

from progress import stage


def synchronize(repo, url, branch, options=None, seed=None):
    options = options or {}
    attempts = int(options.get('attempts', 3))
    delay = float(options.get('retry_delay_seconds', 15))
    low_speed_time = int(options.get('low_speed_seconds', 120))
    http_version = options.get('http_version', 'HTTP/1.1')
    if attempts < 1 or delay < 0 or low_speed_time < 1 or http_version not in ('HTTP/1.1', 'HTTP/2', 'auto'):
        raise ValueError('Invalid git_transport settings')
    subprocess.run(['git', 'check-ref-format', f'refs/heads/{branch}'], check=True)
    path = repo.path
    if not path.exists() or (path.is_dir() and not any(path.iterdir())):
        path.parent.mkdir(parents=True, exist_ok=True)
        with stage('Initialize persistent bare Git repository'):
            subprocess.run(['git', 'init', '--bare', '--initial-branch', branch, str(path)], check=True)
    # Never delete an existing repository, even if a failed clone left it invalid.
    try:
        bare = repo.git('rev-parse', '--is-bare-repository').strip()
    except RuntimeError as exc:
        raise RuntimeError(f'Invalid Git repository at {path}. Move it aside manually and retry; SQLite need not be removed.') from exc
    if bare != 'true':
        raise RuntimeError(f'Expected a bare Git repository at {path}; refusing to modify it')
    if repo.git('rev-parse', '--is-shallow-repository').strip() == 'true' or repo.git('config', '--get-regexp', r'^(extensions\.partialclone|remote\..*\.promisor)$', allow=(0,1)).strip():
        raise RuntimeError('Shallow/partial repository detected; complete history is required for release inclusion. Use a full seed or fresh repository.')
    remotes = repo.git('remote').splitlines()
    if 'origin' not in remotes:
        repo.git('remote', 'add', 'origin', url)
    elif repo.git('remote', 'get-url', 'origin').strip() != url:
        raise RuntimeError('Existing origin does not match configured upstream; verify and update it explicitly before retrying')
    repo.git('symbolic-ref', 'HEAD', f'refs/heads/{branch}')
    ref = f'refs/heads/{branch}'
    has_branch = bool(repo.git('rev-parse', '--verify', '--quiet', ref, allow=(0,1)).strip())
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    cmd = ['git', '-C', str(path)]
    if http_version != 'auto':
        cmd += ['-c', f'http.version={http_version}']
    cmd += ['-c', 'http.lowSpeedLimit=1', '-c', f'http.lowSpeedTime={low_speed_time}']

    def fetch(label, *args):
        for attempt in range(1, attempts+1):
            try:
                with stage(f'{label} (attempt {attempt}/{attempts})'):
                    subprocess.run(cmd + ['fetch', '--progress', '--no-tags', *args], env=env, check=True)
                return
            except subprocess.CalledProcessError as exc:
                if attempt == attempts:
                    logging.error('%s exhausted %d attempts; successful earlier fetches are retained', label, attempts)
                    raise
                wait = min(delay * 2**(attempt-1), 300)
                logging.warning('%s failed (exit %d); retry in %.0fs', label, exc.returncode, wait)
                time.sleep(wait)

    if seed and not has_branch:
        seed = Path(seed).expanduser().resolve(strict=True)
        if seed == path.resolve():
            raise ValueError('Git seed must be a different local repository')
        def seedgit(*args):
            return subprocess.check_output(['git', '-C', str(seed), *args], text=True).strip()
        if seedgit('rev-parse','--is-shallow-repository') == 'true':
            raise ValueError('Local seed is shallow; provide a complete repository')
        # Check for partial clone without requiring it to have any matching config keys.
        partial = subprocess.run(['git','-C',str(seed),'config','--get-regexp',r'^(extensions\.partialclone|remote\..*\.promisor)$'], capture_output=True, text=True)
        if partial.returncode != 1:
            raise ValueError('Local seed is partial or its Git configuration could not be read')
        refs = seedgit('for-each-ref','--format=%(refname)',ref,f'refs/remotes/origin/{branch}').splitlines()
        source = next((r for r in (f'refs/remotes/origin/{branch}',ref) if r in refs),None)
        if not source:
            raise ValueError(f'Local seed has neither {ref} nor origin/{branch}')
        fetch('Import existing local Git history', str(seed), f'+{source}:{ref}')
        # Tags are only trusted as upstream release refs after upstream fetch succeeds.
    logging.info('Git transport: %s; %d attempts; HTTP low-speed threshold %ds', http_version, attempts, low_speed_time)
    fetch('Git fetch main branch' if branch == 'main' else f'Git fetch branch {branch}', 'origin', f'+{ref}:{ref}')
    # Separate transfers: a failed tag download never forces another full main download.
    fetch('Git fetch release tags', 'origin', 'refs/tags/*:refs/tags/*')
    return repo.git('rev-parse', ref).strip()
