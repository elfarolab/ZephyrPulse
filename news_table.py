"""Portable, server-rendered news tables; all evidence remains accessible without JS."""
from html import escape
from urllib.parse import quote

COLUMNS = ('UTC date / time', 'Category', 'Subject / target', 'Headline', 'Confidence', 'Release', 'Commit')


def render_news_table(items, statuses=None, boards=None, idx=None, related=None):
    from pulse import UPSTREAM, CATEGORIES, CATEGORY_ICONS, icon
    from intelligence import board_ids, folder_index
    statuses = statuses or {}; boards = boards or {}; idx = idx if idx is not None else folder_index(boards)
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
        linked = [boards[k] for k in ids if k in boards]
        vendors = ' '.join(str(b.get('vendor',''))+' '+str(b.get('vendor_name','')) for b in linked)
        url = f'{UPSTREAM}/commit/{quote(sha,safe="")}'
        path = r.get('path') or ''; source = f'{UPSTREAM}/blob/{quote(sha,safe="")}/{quote(path,safe="/")}'
        out.append(f'<tr class="pulse-news-row pulse-cat-{kind}" data-kind="{escape(kind,quote=True)}" data-time="{escape(r["committed"],quote=True)}" data-vendor="{escape(vendors,quote=True)}" data-confidence="{escape(confidence,quote=True)}">')
        out.append(f'<td class="pulse-news-expand"><button type="button" class="pulse-news-toggle" aria-expanded="true" aria-label="Details for {escape(subject,quote=True)}"><span aria-hidden="true">▾</span></button></td>')
        vals = [escape(stamp), f'<a class="pulse-category-link" href="{kind}.html">{icon(CATEGORY_ICONS[kind])} {escape(CATEGORIES[kind])}</a>', f'<a class="pulse-subject-filter" href="{kind}.html?subject={quote(subject,safe="")}" data-subject="{escape(subject,quote=True)}">{escape(subject)}</a>', escape(headline), escape(confidence), escape(release), escape(sha[:10])]
        for i, val in enumerate(vals):
            out.append(f'<td class="pulse-news-col-{i}" title="{escape([stamp,CATEGORIES[kind],subject,headline,confidence,release,sha][i],quote=True)}">{val}</td>')
        out.append('</tr>')
        links = ' · '.join(f'<a href="boards/{quote(b["slug"],safe="")}.html">{escape(b["name"])}</a>' for b in linked)
        out.append(f'<tr class="pulse-news-detail"><td colspan="8"><article class="pulse-news-detail-panel"><strong>{escape(subject)}</strong><p>{escape(headline)}</p><p>{escape(r["detail"])}</p><p>{escape(stamp)} UTC · {escape(CATEGORIES[kind])} · {escape(confidence)} · {escape(release)} (exact commit inclusion)</p>')
        peers = [k for k in CATEGORIES if k != kind and k in related.get(subject.casefold(), set())]
        if peers:
            out.append('<p>Same subject in other categories: '+ ' · '.join(f'<a href="{k}.html?subject={quote(subject,safe="")}">{escape(CATEGORIES[k])}</a>' for k in peers) + '</p>')
        if vendors: out.append(f'<p>Vendor association: {escape(vendors)}</p>')
        if path: out.append(f'<p>Source: <code>{escape(path)}</code></p>')
        out.append(f'<p class="pulse-news-links"><a href="{url}">{icon("commit")} Commit {escape(sha)}</a>'+ (f' · <a href="{source}">{icon("source")} Source file</a>' if path else '') + (' · Board profiles: '+links if links else '')+f' · <a href="hardware-search.html?subject={quote(subject,safe="")}">Related hardware / news</a></p></article></td></tr>')
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
