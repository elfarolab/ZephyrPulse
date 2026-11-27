"""Portable, server-rendered news tables; all evidence remains accessible without JS."""
from html import escape
from urllib.parse import quote

COLUMNS = ('UTC date / time', 'Category', 'Subject / target', 'Headline', 'Confidence', 'Release', 'Commit')


def news_columns(category=None, grouped=False):
    """Stable logical column IDs, independent of the visible column positions."""
    labels = dict(enumerate(COLUMNS))
    if not grouped:
        if category:
            labels.update({2:'Board / target', 3:'Commit description'})
            labels.pop(1)
        return list(labels.items())
    labels.update({3:'Commit description', 4:'Files'})
    if category in {'driver','sensor'}:
        labels.update({1:'Subsystem', 2:'Driver'})
        if category == 'sensor': labels.pop(1)
    else:
        if category not in {'all','release_news'}: labels.pop(1)
        if category == 'soc': labels[2] = 'SoC / family'
        elif category in {'board','board_change','board_candidate','board_feature'}: labels[2] = 'Board / target'
        else: labels.pop(2)
    return list(labels.items())


def render_news_table(items, statuses=None, boards=None, idx=None, related=None, category=None):
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
    columns = news_columns(category)
    layout = ' pulse-compact-news' if category else ''
    fixed = f' data-fixed-category="{escape(category,quote=True)}"' if category else ''
    out = [f'<div class="pulse-news-table{layout}" data-pulse-news="100"{fixed}>',
           f'<div class="pulse-news-scroll"><table class="pulse-news-list"><colgroup><col class="pulse-news-expand-col"><col span="{len(columns)}"></colgroup><thead><tr>',
           '<th scope="col" class="pulse-news-expand"><span class="pulse-sr-only">Details</span></th>']
    out.extend(f'<th scope="col" data-news-column="{i}">{escape(c)}</th>' for i,c in columns)
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
        for i, _ in columns:
            val = vals[i]
            if category and i == 5 and release == 'Not in tracked releases': val='Not in tags'
            if category and i in (3,6): val=f'<button type="button" class="pulse-commit-expand" aria-expanded="true">{val}</button>'
            out.append(f'<td class="pulse-news-col-{i}" title="{escape([stamp,CATEGORIES[kind],subject,headline,confidence,release,sha][i],quote=True)}">{val}</td>')
        out.append('</tr>')
        links = [action('Commit '+sha, url, 'commit', 'View commit on GitHub')]
        if path:
            links.append(action('Source file', source, 'github', 'View source file on GitHub'))
        board_links = ' '.join(action(b['name'], profile_url(b), 'board', 'Open board profile: '+b['name']) for b in linked)
        board_header = f'<p class="pulse-detail-boards">{board_links}</p>' if board_links else ''
        out.append(f'<tr class="pulse-news-detail"><td colspan="{len(columns)+1}"><article class="pulse-news-detail-panel">{board_header}<strong>{escape(subject)}</strong><p>{escape(headline)}</p><p>{escape(r["detail"])}</p><p>Change type: {escape(typ)}</p><p>{escape(stamp)} UTC · {escape(CATEGORIES[kind])} · {escape(confidence)} · {escape(release)} (exact commit inclusion)</p>')
        peers = [k for k in CATEGORIES if k != kind and k in related.get(subject.casefold(), set())]
        if peers:
            out.append('<p>Same subject in other categories: '+ ' · '.join(action(CATEGORIES[k], f'{k}.html?subject={quote(subject,safe="")}', CATEGORY_ICONS[k]) for k in peers) + '</p>')
        if key is not None:
            out.append(f'<p>{icon("filter")} Subject filter: {filter_link}</p>')
        if vendors: out.append(f'<p>Vendor association: {escape(vendors)}</p>')
        if path: out.append(f'<p>Source: <code>{escape(path)}</code>{" (before removal)" if revision != sha else ""}</p>')
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


def render_grouped_news(items, category, statuses=None, boards=None, idx=None, commit_files=None, board_context=False):
    import json
    from news_groups import group_events, manifest_files, DRIVERS, SCOPED, group_unit
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
    columns = news_columns(category, True)
    mixed = category in {'all','release_news'}
    unit = group_unit(category)
    evidence_label = 'board evidence records' if board_context else 'classified events'
    fixed = '' if mixed else category
    out = [f'<div class="pulse-news-table pulse-grouped-news pulse-compact-news" data-pulse-news="100" data-group-unit="{unit}" data-group-category="{category}" data-fixed-category="{fixed}" data-evidence-label="{evidence_label}">',
           f'<p class="pulse-group-summary">{len(groups)} {unit} · {len(items)} {evidence_label}. File counts are for the complete commit when available; + means partial evidence.</p><div class="pulse-news-scroll"><table class="pulse-news-list"><colgroup><col class="pulse-news-expand-col"><col span="{len(columns)}"></colgroup><thead><tr>',
           '<th scope="col" class="pulse-news-expand"><span class="pulse-sr-only">Details</span></th>']
    out.extend(f'<th scope="col" data-news-column="{i}">{escape(h)}</th>' for i,h in columns)
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
        kinds = list(dict.fromkeys(e['kind'] for e in rows))
        category_text = ', '.join(CATEGORIES[k] for k in kinds) if mixed else CATEGORIES[category]
        if board_context and all(e.get('manifest_only') for e in rows): category_text = 'Board maintenance · Direct board-folder change'
        data = {'kind':r['kind'] if mixed else category,'kinds':json.dumps(kinds),'time':r['committed'],'change-type':', '.join(g['types']),'change-types':json.dumps(g['types']),'subjects':json.dumps(list(dict.fromkeys([*g['subjects'],g['subject']]))),'scope':g['subject'] if category in SCOPED else '','subsystem':g['subsystem'],'driver':g['driver'],'vendor':vendors,'event-count':len(rows)}
        attrs = ' '.join(f'data-{k}="{attr(v)}"' for k,v in data.items())
        out.append(f'<tr class="pulse-news-row pulse-cat-{r["kind"] if mixed else category}" {attrs}>')
        out.append(f'<td class="pulse-news-expand"><button type="button" class="pulse-news-toggle" aria-expanded="true" aria-label="Details for {attr(headline)}"><span aria-hidden="true">▾</span></button></td>')
        vals = [stamp,g['subsystem'] if driver else category_text,g['driver'] if driver else g['subject'],headline,str(file_count) if manifest is not None else f'{file_count}+',release,sha[:10]]
        for i,_ in columns:
            v=vals[i]
            cell = expand_button(v) if i in (3,6) else escape('Not in tags' if i==5 and v=='Not in tracked releases' else v)
            if i==1 and mixed: cell = escape(category_text) if board_context and all(e.get('manifest_only') for e in rows) else ' · '.join(icon(CATEGORY_ICONS[k])+' '+escape(CATEGORIES[k]) for k in kinds)
            if i==2 and category in {'board','board_candidate','board_change','board_feature'} and g['subjects']==[v]:
                key=resolver.resolve(r, ids)
                if key is not None: cell=f'<a class="pulse-board-profile-link" href="{profile_url(boards[key])}">{escape(v)}</a>'
            if i==2 and category=='board_feature':
                cell+=f'<span class="pulse-signal-preview">{escape(r["detail"])} · {escape(r["confidence"])}</span>'
            sort_value = f' data-sort-value="{file_count}"' if i==4 else f' data-sort-value="{attr(v)}"' if i==2 and category=='board_feature' else ''
            out.append(f'<td class="pulse-news-col-{i}" title="{attr(v)}"{sort_value}>{cell}</td>')
        out.append('</tr>')
        board_links = ' '.join(action(b['name'],profile_url(b),'board') for b in linked) if not board_context else ''
        board_header = f'<p class="pulse-detail-boards">{board_links}</p>' if board_links else ''
        out.append(f'<tr class="pulse-news-detail"><td colspan="{len(columns)+1}"><article class="pulse-news-detail-panel">{board_header}<strong>{escape(headline)}</strong><p>{escape(stamp)} UTC · {escape(category_text)} · {escape(release)} (exact commit inclusion)</p>')
        if rel.get('latest_release') or rel.get('lts_tags'):
            out.append(f'<p>Latest tracked containing tag: {escape(rel.get("latest_release") or "Unknown")} · LTS tags: {escape(", ".join(rel.get("lts_tags",[])) or "None")}</p>')
        if driver: out.append(f'<p>Subsystem: {escape(g["subsystem"])} · Driver: {escape(g["driver"])}</p>')
        if not driver and category in SCOPED: out.append(f'<p>Hardware scope: {escape(g["subject"])}</p>')
        if vendors: out.append(f'<p>Vendor association: {escape(vendors)}</p>')
        heading = f'Affected files ({file_count}) — complete commit' if manifest is not None else f'Known evidence files ({file_count}) — complete diff unavailable'
        out.append(f'<p><strong>{heading}</strong> · {len(rows)} {evidence_label} in this group</p><ul class="pulse-affected-files">')
        for path,revision,status,old_path,evidence in files+extra:
            url = f'{UPSTREAM}/blob/{quote(revision,safe="")}/{quote(path,safe="/")}'
            note = {'A':'Added','M':'Modified','D':'Deleted','R':'Renamed','C':'Copied','T':'Type changed'}.get(status,'Additional evidence' if manifest is not None else '')
            if old_path: note += ' from '+old_path
            out.append('<li>'+action(path,url,'github')+(' · '+escape(note) if note else '')+(' (before removal)' if revision!=sha else ''))
            if evidence: out.append('<ul>')
            for e in evidence:
                out.append(f'<li>{escape(CATEGORIES[e["kind"]])+" · " if mixed else ""}{escape(e["subject"])} · {escape(e.get("change_type") or "Unknown")} · {escape(e.get("confidence") or "unknown")}: {escape(e["detail"])}</li>')
            if evidence: out.append('</ul>')
            out.append('</li>')
        for e in rows:
            if not e.get('path'): out.append(f'<li>{escape(CATEGORIES[e["kind"]])+" · " if mixed else ""}{escape(e["subject"])} · {escape(e.get("change_type") or "Unknown")} · {escape(e.get("confidence") or "unknown")}: {escape(e["detail"])}</li>')
        links = [action('View upstream commit',f'{UPSTREAM}/commit/{quote(sha,safe="")}','commit')]
        out.append('</ul><p class="pulse-news-links">'+' '.join(links)+'</p></article></td></tr>')
    out.append('</tbody></table></div></div>')
    return '\n'.join(out)


def render_board_timeline(timeline, statuses, release_text):
    """Group retained board milestones by commit without inventing historical titles or complete diffs."""
    from pulse import UPSTREAM, icon
    from collections import defaultdict
    if not timeline:
        return '_No retained milestone._'
    groups = defaultdict(list)
    for row in timeline: groups[row['sha']].append(row)
    def esc(value): return escape(str(value), quote=True)
    out = ['<div class="pulse-matrix pulse-board-timeline"><table><thead><tr><th>UTC date / time</th><th>Detected signals</th><th>Evidence</th><th>Release inclusion</th><th>Commit</th></tr></thead><tbody>']
    for sha, rows in groups.items():
        stamp=rows[0]['committed'][:16].replace('T',' ')
        labels=list(dict.fromkeys(r['label'] for r in rows))
        signals=' · '.join(labels[:2])+ (f' · +{len(labels)-2} more' if len(labels)>2 else '')
        out.append(f'<tr><td>{esc(stamp)}</td><td title="{esc(" · ".join(labels))}">{esc(signals)}</td><td data-sort-value="{len(rows)}"><details><summary>{len(rows)} milestone{"s" if len(rows)!=1 else ""}</summary><ul>')
        for r in rows:
            path=r['path']; href=f'{UPSTREAM}/blob/{quote(sha,safe="")}/{quote(path,safe="/")}'
            link=f' · <a href="{esc(href)}">{icon("github")} {esc(path)}</a>' if path else ''
            out.append(f'<li>{esc(r["label"])} ({esc(r["confidence"])}){link}</li>')
        out.append(f'</ul></details></td><td>{esc(release_text(statuses.get(sha,{})))}</td><td><a href="{UPSTREAM}/commit/{quote(sha,safe="")}">{icon("commit")} {esc(sha[:10])}</a></td></tr>')
    out.append('</tbody></table></div>')
    return '\n'.join(out)
