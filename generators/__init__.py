"""Replaceable renderer boundary; collectors never import a theme or plugin."""
from .base import build_site

def get_generator(config):
    engine = config.get('engine', 'zensical')
    if engine == 'zensical':
        from .zensical import Zensical
        return Zensical(config)
    raise ValueError(f'Unsupported generator: {engine}')
