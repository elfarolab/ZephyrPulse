"""Portable, server-rendered news tables; all evidence remains accessible without JS."""
from html import escape
from urllib.parse import quote

COLUMNS = ('UTC date / time', 'Category', 'Subject / target', 'Headline', 'Confidence', 'Release', 'Commit')


def render_news_table(items, statuses=None, boards=None, idx=None, related=None):
    from pulse import UPSTREAM, CATEGORIES, CATEGORY_ICONS, icon
    from intelligence import board_ids, folder_index
    from board_links import BoardLinks, profile_url
    def action(label, href, glyph, title=None):
        hint = f' title="{escape(title, quote=True)}"' if title else ''
        return f'<a href="{escape(href, quote=True)}" class="pulse-detail-link"{hint}>{icon(glyph)} <span>{escape(label)}</span></a>'
    statuses = statuses or {}; boards = boards or {}; idx = idx if idx is not None else folder_index(boards)
    resolver=BoardLinks(boards)
    related = related if related is not None else subject_categories(items)
    if not items:
        return '_No matching events in this window._\n'
    out = ['<div class="pulse-news-table" data-pulse-news="100">',
           '<div class="pulse-news-scroll"><table class="pulse-news-list"><colgroup><col class="pulse-news-expand-col"><col span="7"></colgroup><thead><tr>',
           '<th scope="col" class="pulse-news-expand"><span class="pulse-sr-only">Details</span></th>']
    out.extend(f'<th scope="col">{escape(c)}</th>' for c in COLUMNS)
    out.append('</tr></thead><tbody>')
    for item in items:
        r = dict(item); sha = r['sha']; kind = r['kind']; subject = r['subject']; headline = r.get('commit_subject') or subject
        stamp = r['committed'][:16].replace('T', ' '); confidence = r['confidence'].capitalize()
        rel = statuses.get(sha, r.get('release', {})); release = rel.get('first_release') or ('Not in tracked releases' if rel.get('status') == 'main_only' else 'Unknown')
        ids = r.get('boards') if 'boards' in r else board_ids(r, boards, idx)
        key=resolver.resolve(r,ids)
        if key is not None and key not in ids: ids=[*ids,key]
        linked = [boards[k] for k in ids if k in boards]
        filter_link=f'<a class="pulse-subject-filter" href="{kind}.html?subject={quote(subject,safe="")}" data-subject="{escape(subject,quote=True)}">{escape(subject)}</a>'
        subject_link=(f'<a class="pulse-board-profile-link" href="{profile_url(boards[key])}" title="Open board profile">{escape(subject)}</a>' if key is not None else filter_link)
        vendors = ' '.join(str(b.get('vendor',''))+' '+str(b.get('vendor_name','')) for b in linked)
        url = f'{UPSTREAM}/commit/{quote(sha,safe="")}'
        path = r.get('path') or ''; revision = r.get('source_revision') or sha; source = f'{UPSTREAM}/blob/{quote(revision,safe="")}/{quote(path,safe="/")}'
        typ = r.get('change_type') or 'Unknown'
        out.append(f'<tr class="pulse-news-row pulse-cat-{kind}" data-change-type="{escape(typ,quote=True)}" data-kind="{escape(kind,quote=True)}" data-time="{escape(r["committed"],quote=True)}" data-vendor="{escape(vendors,quote=True)}" data-confidence="{escape(confidence,quote=True)}">')
        out.append(f'<td class="pulse-news-expand"><button type="button" class="pulse-news-toggle" aria-expanded="true" aria-label="Details for {escape(subject,quote=True)}"><span aria-hidden="true">▾</span></button></td>')
        vals = [escape(stamp), f'<a class="pulse-category-link" href="{kind}.html">{icon(CATEGORY_ICONS[kind])} {escape(CATEGORIES[kind])}</a>', subject_link, escape(headline), escape(confidence), escape(release), escape(sha[:10])]
        for i, val in enumerate(vals):
            out.append(f'<td class="pulse-news-col-{i}" title="{escape([stamp,CATEGORIES[kind],subject,headline,confidence,release,sha][i],quote=True)}">{val}</td>')
        out.append('</tr>')
        links = [action('Commit '+sha, url, 'commit', 'View commit on GitHub')]
        if path:
            links.append(action('Source file', source, 'github', 'View source file on GitHub'))
        links.extend(action(b['name'], profile_url(b), 'board', 'Open board profile: '+b['name']) for b in linked)
        out.append(f'<tr class="pulse-news-detail"><td colspan="8"><article class="pulse-news-detail-panel"><strong>{escape(subject)}</strong><p>{escape(headline)}</p><p>{escape(r["detail"])}</p><p>Change type: {escape(typ)}</p><p>{escape(stamp)} UTC · {escape(CATEGORIES[kind])} · {escape(confidence)} · {escape(release)} (exact commit inclusion)</p>')
        peers = [k for k in CATEGORIES if k != kind and k in related.get(subject.casefold(), set())]
        if peers:
            out.append('<p>Same subject in other categories: '+ ' · '.join(action(CATEGORIES[k], f'{k}.html?subject={quote(subject,safe="")}', CATEGORY_ICONS[k]) for k in peers) + '</p>')
        if key is not None:
            out.append(f'<p>{icon("filter")} Subject filter: {filter_link}</p>')
        if vendors: out.append(f'<p>Vendor association: {escape(vendors)}</p>')
        if path: out.append(f'<p>Source: <code>{escape(path)}</code>{" (before removal)" if revision != sha else ""}</p>')
        links.append(action('Related hardware / news', f'hardware-search.html?subject={quote(subject,safe="")}', 'search'))
        out.append('<p class="pulse-news-links">'+' '.join(links)+'</p></article></td></tr>')
    out.append('</tbody></table></div></div>')
    # One raw HTML block (no blank lines) for Markdown engines.
    return '\n'.join(out)


def subject_categories(items):
    result = {}
    for r in items:
        result.setdefault(r['subject'].casefold(), set()).add(r['kind'])
    return result


def render_category_summary(items, statuses, boards, idx, preview=3):
    """Bound the homepage DOM while retaining direct access to every event."""
    from pulse import CATEGORIES, CATEGORY_ICONS, icon
    groups = {k: [] for k in CATEGORIES}
    for r in items:
        groups[r['kind']].append(r)
    related = subject_categories(items)
    out = ['<div class="pulse-category-summary">']
    for k, label in CATEGORIES.items():
        rows = groups[k]
        latest = rows[0]['committed'][:16].replace('T', ' ')+' UTC' if rows else 'No recent events'
        out.append(f'<details class="pulse-category-group pulse-cat-{k}"><summary><span class="pulse-category-name"><a class="pulse-category-link" href="{k}.html">{icon(CATEGORY_ICONS[k])} {escape(label)}</a></span><strong>{len(rows)}</strong><span class="pulse-category-latest">{escape(latest)}</span></summary>')
        if rows:
            out.append(render_news_table(rows[:preview], statuses, boards, idx, related).replace('data-pulse-news="100"', 'data-pulse-news="100" data-pulse-preview="true"', 1))
        out.append(f'<p class="pulse-category-more"><a href="{k}.html">View all {len(rows)} {escape(label.lower())} →</a></p></details>')
    out.append('</div>')
    return '\n'.join(out)


def render_grouped_news(items, category, statuses=None, boards=None, idx=None, commit_files=None):
    import json
    from news_groups import group_events, manifest_files, DRIVERS
    from pulse import UPSTREAM, CATEGORIES, CATEGORY_ICONS, icon
    from intelligence import board_ids, folder_index
    from board_links import BoardLinks, profile_url
    if not items:
        return '_No matching events in this window._\n'
    statuses, boards = statuses or {}, boards or {}
    idx = idx if idx is not None else folder_index(boards)
    resolver = BoardLinks(boards)
    groups = group_events(items, category)
    def attr(value): return escape(str(value), quote=True)
    def action(label, href, glyph):
        return f'<a class="pulse-detail-link" href="{attr(href)}">{icon(glyph)} <span>{escape(label)}</span></a>'
    def expand_button(text):
        return f'<button type="button" class="pulse-commit-expand" aria-expanded="true">{escape(text)}</button>'
    driver = category in DRIVERS
    headers = ('UTC date / time', 'Subsystem' if driver else 'Category', 'Driver' if driver else 'Subject / target', 'Commit description', 'Files', 'Release', 'Commit')
    unit = 'commit groups' if category in {'soc','board_change'} else 'commits'
    out = [f'<div class="pulse-news-table pulse-grouped-news" data-pulse-news="100" data-group-unit="{unit}" data-group-category="{category}">',
           f'<p class="pulse-group-summary">{len(groups)} {unit} · {len(items)} classified events. File counts are for the complete commit when available; + means partial evidence.</p><div class="pulse-news-scroll"><table class="pulse-news-list"><colgroup><col class="pulse-news-expand-col"><col span="7"></colgroup><thead><tr>',
           '<th scope="col" class="pulse-news-expand"><span class="pulse-sr-only">Details</span></th>']
    out.extend(f'<th scope="col">{escape(h)}</th>' for h in headers)
    out.append('</tr></thead><tbody>')
    for g in groups:
        rows, sha = g['rows'], g['sha']; r = rows[0]
        manifest = (commit_files or {}).get(sha)
        files, extra = manifest_files(g, manifest)
        file_count = len({p for p, *_ in files})
        headline = r.get('commit_subject') or r['subject']; stamp = r['committed'][:16].replace('T',' ')
        rel = statuses.get(sha, r.get('release',{})); release = rel.get('first_release') or ('Not in tracked releases' if rel.get('status')=='main_only' else 'Unknown')
        ids = set()
        for e in rows:
            associated = e.get('boards') if 'boards' in e else board_ids(e, boards, idx)
            ids.update(associated); key = resolver.resolve(e, associated)
            if key is not None: ids.add(key)
        linked = [boards[k] for k in sorted(ids) if k in boards]
        vendors = ' '.join(str(b.get('vendor',''))+' '+str(b.get('vendor_name','')) for b in linked)
        data = {'kind':category,'time':r['committed'],'change-type':', '.join(g['types']),'change-types':json.dumps(g['types']),'subjects':json.dumps(g['subjects']),'subsystem':g['subsystem'],'driver':g['driver'],'vendor':vendors,'event-count':len(rows)}
        attrs = ' '.join(f'data-{k}="{attr(v)}"' for k,v in data.items())
        out.append(f'<tr class="pulse-news-row pulse-cat-{category}" {attrs}>')
        out.append(f'<td class="pulse-news-expand"><button type="button" class="pulse-news-toggle" aria-expanded="true" aria-label="Details for {attr(headline)}"><span aria-hidden="true">▾</span></button></td>')
        vals = [stamp,g['subsystem'] if driver else CATEGORIES[category],g['driver'] if driver else g['subject'],headline,str(file_count) if manifest is not None else f'{file_count}+',release,sha[:10]]
        for i,v in enumerate(vals):
            cell = expand_button(v) if i in (3,6) else escape(v)
            if i==1 and not driver: cell = icon(CATEGORY_ICONS[category])+' '+cell
            if i==2 and not driver and g['subjects']==[v]:
                key=resolver.resolve(r, ids)
                if key is not None: cell=f'<a class="pulse-board-profile-link" href="{profile_url(boards[key])}">{escape(v)}</a>'
                else: cell=f'<a class="pulse-subject-filter" href="{category}.html?subject={quote(v,safe="")}" data-subject="{attr(v)}">{escape(v)}</a>'
            sort_value = f' data-sort-value="{file_count}"' if i==4 else ''
            out.append(f'<td class="pulse-news-col-{i}" title="{attr(v)}"{sort_value}>{cell}</td>')
        out.append('</tr>')
        out.append(f'<tr class="pulse-news-detail"><td colspan="8"><article class="pulse-news-detail-panel"><strong>{escape(headline)}</strong><p>{escape(stamp)} UTC · {escape(CATEGORIES[category])} · {escape(release)} (exact commit inclusion)</p>')
        if driver: out.append(f'<p>Subsystem: {escape(g["subsystem"])} · Driver: {escape(g["driver"])}</p>')
        if vendors: out.append(f'<p>Vendor association: {escape(vendors)}</p>')
        heading = f'Affected files ({file_count}) — complete commit' if manifest is not None else f'Known evidence files ({file_count}) — complete diff unavailable'
        out.append(f'<p><strong>{heading}</strong> · {len(rows)} classified events in this category/group</p><ul class="pulse-affected-files">')
        for path,revision,status,old_path,evidence in files+extra:
            url = f'{UPSTREAM}/blob/{quote(revision,safe="")}/{quote(path,safe="/")}'
            note = {'A':'Added','M':'Modified','D':'Deleted','R':'Renamed','C':'Copied','T':'Type changed'}.get(status,'Additional evidence' if manifest is not None else '')
            if old_path: note += ' from '+old_path
            out.append('<li>'+action(path,url,'github')+(' · '+escape(note) if note else '')+(' (before removal)' if revision!=sha else ''))
            if evidence: out.append('<ul>')
            for e in evidence:
                out.append(f'<li>{escape(e["subject"])} · {escape(e.get("change_type") or "Unknown")} · {escape(e.get("confidence") or "unknown")}: {escape(e["detail"])}</li>')
            if evidence: out.append('</ul>')
            out.append('</li>')
        for e in rows:
            if not e.get('path'): out.append(f'<li>{escape(e["subject"])} · {escape(e.get("change_type") or "Unknown")} · {escape(e.get("confidence") or "unknown")}: {escape(e["detail"])}</li>')
        out.append('</ul><p class="pulse-news-links">'+action('View upstream commit',f'{UPSTREAM}/commit/{quote(sha,safe="")}','commit')+' '+ ' '.join(action(b['name'],profile_url(b),'board') for b in linked)+' '+action('Related hardware / news','hardware-search.html?subject='+quote(sha,safe=''),'search')+'</p></article></td></tr>')
    out.append('</tbody></table></div></div>')
    return '\n'.join(out)
