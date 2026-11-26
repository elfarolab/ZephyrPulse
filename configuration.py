"""Read public defaults and recursively overlay a private configuration."""
from pathlib import Path
import yaml


def merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def read(path):
    value = yaml.safe_load(path.read_text(encoding='utf-8'))
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f'Configuration must be a mapping: {path}')
    return value


def load_config(root, override=None):
    root = Path(root)
    default = root / 'config.yml'
    base = read(default)
    path = Path(override) if override is not None else root / 'config.local.yml'
    if override is None and not path.exists():
        return base
    if path.resolve() == default.resolve():
        return base
    return merge(base, read(path))
