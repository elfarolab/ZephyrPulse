"""Publish compact discovery metadata and immutable, on-demand board evidence."""
import hashlib
import json
import logging
import re
from collections import defaultdict


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def write_changed(path, content):
    if path.exists() and path.read_bytes() == content:
        return False
    path.write_bytes(content)
    return True


def publish_catalog(docs, comparison, payload):
    """Keep every feature state in the catalog; move full DTS nodes off the hot path.

    A file is shared by all targets/baselines of a board. Its digest is part of
    its URL, so a browser cannot accidentally use an older evidence snapshot.
    Only files in this dedicated generated directory are cleaned up.
    """
    directory = docs / 'data' / 'board-evidence'
    directory.mkdir(parents=True, exist_ok=True)
    by_board = defaultdict(list)
    for t in comparison['targets']:
        by_board[t['board_id']].append(t)
    previous = set()
    old_catalog = docs / 'intelligence.json'
    if old_catalog.exists():
        try:
            previous = {t.get('evidence_url','').rsplit('/',1)[-1] for t in json.loads(old_catalog.read_bytes()).get('comparison',{}).get('targets',[])}
        except (ValueError, TypeError, AttributeError):
            logging.warning('Previous browser catalog unreadable; skipping previous evidence retention')
    wanted = set()
    changed = total = 0
    for board_id, targets in sorted(by_board.items()):
        evidence = {}
        for t in targets:
            record = {}
            for baseline, meta in [('main', t['metadata']), *((r['tag'], r) for r in t['releases'] if r['found'])]:
                if meta is None:
                    continue
                ev = meta.get('dts_evidence') or {}
                record[baseline] = ev
                # The comparator's state/coverage and discovery need only these.
                meta['dts_evidence'] = {'present_features': ev.get('present_features', [])}
            evidence[t['id']] = record
        raw = encoded({'board_id': board_id, 'targets': evidence})
        name = hashlib.sha256(raw).hexdigest() + '.json'
        wanted.add(name)
        changed += write_changed(directory / name, raw)
        total += len(raw)
        for t in targets:
            t['evidence_url'] = 'data/board-evidence/' + name
    for p in directory.glob('*.json'):
        if re.fullmatch(r'[0-9a-f]{64}\.json', p.name) and p.name not in wanted and p.name not in previous:
            p.unlink()
    # Keep lightweight views for pages that do not need the whole hardware catalog.
    associated = {key for e in payload.get('events', []) for key in e.get('boards', [])}
    common = {k: payload[k] for k in ('updated', 'watchlist', 'preferences') if k in payload}
    news = {**common, 'boards': [b for b in payload.get('boards', []) if b['id'] in associated], 'events': payload.get('events', [])}
    prefs = {**{k:v for k,v in common.items() if k != 'updated'}, 'comparison': {'snapshots': comparison.get('snapshots', [])}}
    news_bytes = encoded(news); prefs_bytes = encoded(prefs)
    write_changed(docs / 'data' / 'news-view.json', news_bytes)
    write_changed(docs / 'data' / 'preferences.json', prefs_bytes)
    logging.info('Browser news view: %.2f MiB; settings view: %.2f KiB', len(news_bytes)/1048576, len(prefs_bytes)/1024)
    payload = {**payload, 'schema_version': 2, 'comparison': comparison}
    raw = encoded(payload)
    write_changed(docs / 'intelligence.json', raw)
    logging.info('Browser catalog: %.2f MiB; current board evidence: %d files, %d changed/new, %.2f MiB total', len(raw)/1048576, len(wanted), changed, total/1048576)
