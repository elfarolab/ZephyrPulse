"""Zensical implementation; the rest of the application has no Zensical dependency."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib
import shutil
import logging
import hashlib
from importlib.metadata import version, PackageNotFoundError

class Zensical:
    def __init__(self, config):
        self.strict = config.get('strict', True)
        self.native_search = config.get('native_search', False)
        self.incremental = config.get('incremental', False)
        if not all(isinstance(x,bool) for x in (self.strict,self.native_search,self.incremental)):
            raise ValueError('generator.strict and native_search must be booleans')

    def render(self, project: Path, workspace: Path, site_url: str):
        template=(project/'zensical.toml').read_text(encoding='utf-8')
        # Runtime overrides only in staging; keep the version-controlled theme file unchanged.
        text=template.replace('site_url = "http://localhost:8000/"', 'site_url = '+json.dumps(site_url,ensure_ascii=False),1)
        text=text.replace('enabled = false # native full-text search', f'enabled = {str(self.native_search).lower()} # native full-text search',1)
        data=tomllib.loads(text)['project']
        if data['site_url']!=site_url or data['plugins']['search']['enabled']!=self.native_search:
            raise ValueError('Zensical template runtime override mismatch')
        if data.get('site_dir')!='site' or data.get('docs_dir')!='docs' or data.get('use_directory_urls') is not False:
            raise ValueError('Generator must preserve docs -> site and flat .html URLs')
        if self.incremental:
            try:
                self._cached(project,workspace,text)
                return
            except Exception:
                logging.exception('Incremental rendering failed; retrying a clean staged build')
                cache=project/'.pulse-render-cache'
                if cache.is_dir() and not cache.is_symlink(): shutil.rmtree(cache)
                if (workspace/'site').exists(): shutil.rmtree(workspace/'site')
        self._run(workspace,text,clean=True)
        self._validate_search(workspace/'site')

    def _validate_search(self, output):
        """Zensical 0.1.3 emits an empty index even when search is disabled."""
        if self.native_search:
            return
        index = output / 'search.json'
        if not index.exists():
            return
        try:
            data = json.loads(index.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError('Disabled native search produced an invalid index') from exc
        if not isinstance(data, dict) or data.get('items') != []:
            raise RuntimeError('Disabled native search produced a nonempty or unrecognized index')
        logging.info('Zensical native search disabled: empty index (%d bytes) accepted', index.stat().st_size)

    def _run(self,workspace,text,clean):
        config=workspace/'zensical.toml'
        if not config.exists() or config.read_text(encoding='utf-8')!=text:
            config.write_text(text,encoding='utf-8')
        command=[sys.executable,'-m','zensical','build','--config-file','zensical.toml']
        if clean: command.append('--clean')
        if self.strict: command.append('--strict')
        subprocess.run(command,cwd=workspace,check=True)

    def _cached(self,project,workspace,text):
        from .base import validate_site
        cache=project/'.pulse-render-cache'
        if cache.is_symlink() or (cache.exists() and not cache.is_dir()):
            raise ValueError('Unsafe incremental cache path')
        try: renderer_version=version('zensical')
        except PackageNotFoundError: renderer_version='unknown'
        signature=hashlib.sha256((renderer_version+'\n'+str(self.strict)+'\n'+text).encode()).hexdigest()
        marker=cache/'signature'
        clean=not marker.is_file() or marker.read_text()!=signature
        if clean and cache.exists(): shutil.rmtree(cache)
        cache.mkdir(exist_ok=True)
        docs=cache/'docs'; docs.mkdir(exist_ok=True)
        inputs={p.relative_to(workspace/'docs'):p for p in (workspace/'docs').rglob('*') if p.is_file()}
        old={p.relative_to(docs):p for p in docs.rglob('*') if p.is_file()}
        removed=old.keys()-inputs.keys()
        # Removing Markdown can affect navigation and search. Rebuild clean in that case.
        clean=clean or any(p.suffix=='.md' for p in removed)
        for rel in removed:
            old[rel].unlink()
            output=cache/'site'/(rel.with_suffix('.html') if rel.suffix=='.md' else rel)
            output.unlink(missing_ok=True)
        changed=0
        for rel,source in inputs.items():
            target=docs/rel
            if not target.is_file() or target.read_bytes()!=source.read_bytes():
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target);changed+=1
        if clean and (cache/'site').exists(): shutil.rmtree(cache/'site')
        logging.info('Zensical cache: %s; %d updated inputs, %d removed', 'clean build' if clean else 'incremental build',changed,len(removed))
        # A failed run must not be used as the next successful baseline.
        marker.unlink(missing_ok=True)
        self._run(cache,text,clean=clean)
        validate_site(docs,cache/'site')
        self._validate_search(cache/'site')
        shutil.copytree(cache/'site',workspace/'site')
        marker.write_text(signature)

