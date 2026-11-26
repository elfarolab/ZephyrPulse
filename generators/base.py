"""Static generator contract: render a content snapshot into a fresh output tree."""
from pathlib import Path
from typing import Protocol
import hashlib
import json
import shutil
import tempfile
from progress import stage

class Generator(Protocol):
    def render(self, project: Path, workspace: Path, site_url: str) -> None:
        """Render workspace/docs into workspace/site; raise on failure."""


def validate_site(docs: Path, output: Path):
    """The public URL contract is flat .html pages and unchanged static data/assets."""
    required = {'index.html','compare.html','settings.html','hardware-search.html',
                'boards.html','events.json','intelligence.json','feed.xml','watchlist.xml'}
    for path in docs.rglob('*'):
        if not path.is_file(): continue
        rel = path.relative_to(docs)
        target = output / (rel.with_suffix('.html') if path.suffix == '.md' else rel)
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError(f'Missing/empty output: {target.relative_to(output)}')
        if path.suffix != '.md' and hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise RuntimeError(f'Changed static asset: {rel}')
    for name in sorted(required):
        if not (output/name).is_file() or not (output/name).stat().st_size:
            raise RuntimeError(f'Missing/empty required output: {name}')
    for name in ('events.json','intelligence.json'):
        with (output/name).open(encoding='utf-8') as f: json.load(f)
    for name, mount in [('compare.html','pulse-comparator'),('settings.html','pulse-settings'),('hardware-search.html','pulse-hardware-search')]:
        if not any(f'id={q}{mount}{q}' in (output/name).read_text(encoding='utf-8') for q in ('"', "'")):
            raise RuntimeError(f'Missing interactive mount: {name} / {mount}')


def build_site(project: Path, generator: Generator, site_url: str) -> Path:
    """Clean staged build, validate, then replace local site; failure never publishes."""
    project = project.resolve(); dest = project/'site'
    if dest.is_symlink() or (dest.exists() and not dest.is_dir()):
        raise ValueError('site must be a real directory')
    with tempfile.TemporaryDirectory(prefix='.pulse-build-',dir=project) as tmp:
        work = Path(tmp)
        with stage('Stage portable content'):
            shutil.copytree(project/'docs', work/'docs')
        with stage('Run static renderer'):
            generator.render(project, work, site_url)
        new = work/'site'
        with stage('Validate generated files and assets'):
            validate_site(work/'docs',new)
        backup = work/'previous'
        if dest.exists(): dest.rename(backup)
        try: new.rename(dest)
        except BaseException:
            if backup.exists(): backup.rename(dest)
            raise
    return dest
