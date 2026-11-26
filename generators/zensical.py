"""Zensical implementation; the rest of the application has no Zensical dependency."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

class Zensical:
    def __init__(self, config):
        self.strict = config.get('strict', True)
        self.native_search = config.get('native_search', True)
        if not isinstance(self.strict,bool) or not isinstance(self.native_search,bool):
            raise ValueError('generator.strict and native_search must be booleans')

    def render(self, project: Path, workspace: Path, site_url: str):
        template=(project/'zensical.toml').read_text(encoding='utf-8')
        # Runtime overrides only in staging; keep the version-controlled theme file unchanged.
        text=template.replace('site_url = "http://localhost:8000/"', 'site_url = '+json.dumps(site_url,ensure_ascii=False),1)
        text=text.replace('enabled = true # native full-text search', f'enabled = {str(self.native_search).lower()} # native full-text search',1)
        data=tomllib.loads(text)['project']
        if data['site_url']!=site_url or data['plugins']['search']['enabled']!=self.native_search:
            raise ValueError('Zensical template runtime override mismatch')
        if data.get('site_dir')!='site' or data.get('docs_dir')!='docs' or data.get('use_directory_urls') is not False:
            raise ValueError('Generator must preserve docs -> site and flat .html URLs')
        (workspace/'zensical.toml').write_text(text,encoding='utf-8')
        command=[sys.executable,'-m','zensical','build','--clean','--config-file','zensical.toml']
        if self.strict: command.append('--strict')
        subprocess.run(command,cwd=workspace,check=True)
