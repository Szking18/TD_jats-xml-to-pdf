"""
Jinja2 HTML 渲染器
将解析后的 JATS 数据字典渲染为完整的 HTML 文档。
使用 jinja2.Markup 防止自动转义。
"""
import os
import pathlib
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(_SCRIPT_DIR, 'templates')
_LOGO_DIR = os.path.join(_SCRIPT_DIR, 'logos')

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(['html', 'xml']),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(doc_data: dict) -> str:
    template = _env.get_template('article.html')
    css_path = os.path.join(_SCRIPT_DIR, 'style.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    journal = doc_data.get('front', {}).get('journal', {})
    publisher_logo_html = _build_publisher_logo(journal.get('publisher', ''))
    journal_logo_html = _build_journal_logo(journal.get('publisher_id', ''))

    ctx = dict(doc_data)
    ctx.update({
        'css': Markup(css_content),
        'publisher_logo': Markup(publisher_logo_html),
        'journal_logo': Markup(journal_logo_html),
        'body_blocks': _render_body_blocks(doc_data.get('body', [])),
        'render_inline': _render_inline,
        'render_inline_list': _render_inline_list,
        'render_back_item': _render_back_item,
        'get_history': lambda: _get_history(doc_data),
        'citation_line': _get_citation_line(doc_data),
        'striptags': _strip_tags,
    })
    return template.render(**ctx)


# ─── Logo helpers ──────────────────────────────────────────────────

def _logo_path(name):
    if not name:
        return None
    name = name.strip().lower().replace(' ', '_').replace('/', '_')
    name = ''.join(c for c in name if c.isalnum() or c == '_')
    path = os.path.join(_LOGO_DIR, f'{name}.png')
    return path if os.path.exists(path) else None


def _build_publisher_logo(publisher_name):
    path = _logo_path(publisher_name)
    if not path:
        return ''
    uri = pathlib.Path(path).as_uri()
    return f'<div id="publisher-logo"><img src="{uri}" alt="{publisher_name}" /></div>'


def _build_journal_logo(journal_id):
    if not journal_id:
        return ''
    path = _logo_path(f'journal_{journal_id}')
    if not path:
        return ''
    uri = pathlib.Path(path).as_uri()
    return f'<div id="journal-logo"><img src="{uri}" alt="{journal_id}" /></div>'


# ─── Inline rendering (all return Markup) ─────────────────────────

def _render_inline(item):
    if item is None:
        return Markup('')
    t = item.get('type', '')
    val = item.get('value', '')
    content = item.get('content', [])

    if t == 'text':
        return Markup(_escape(val))
    elif t == 'italic':
        return Markup(f'<i>{_render_inline_list(content)}</i>')
    elif t == 'bold':
        return Markup(f'<b>{_render_inline_list(content)}</b>')
    elif t == 'superscript':
        return Markup(f'<sup>{_render_inline_list(content)}</sup>')
    elif t == 'subscript':
        return Markup(f'<sub>{_render_inline_list(content)}</sub>')
    elif t == 'smallcaps':
        return Markup(f'<span class="sc">{_render_inline_list(content)}</span>')
    elif t == 'monospace':
        return Markup(f'<code>{_render_inline_list(content)}</code>')
    elif t == 'underline':
        return Markup(f'<u>{_render_inline_list(content)}</u>')
    elif t == 'xref':
        rid = item.get('rid', '')
        content_html = _render_inline_list(content)
        if rid:
            return Markup(f'<a href="#{rid}" class="xref-link"><sup>{content_html}</sup></a>')
        return Markup(f'<sup>{content_html}</sup>')
    elif t == 'link':
        href = item.get('href', '')
        return Markup(f'<a href="{_escape(href)}">{_render_inline_list(content)}</a>')
    elif t == 'inline_formula':
        svg = item.get('svg', '')
        if svg and '<svg' in svg:
            return Markup(f'<span class="inline-formula">{svg}</span>')
        return Markup(f'<span class="inline-formula-fallback">{_escape(item.get("mathml", ""))}</span>')
    elif t == 'email':
        return Markup(f'<a href="mailto:{_escape(val)}">{_escape(val)}</a>')
    elif t == 'named_content':
        return Markup(_render_inline_list(content))
    elif t == 'linebreak':
        return Markup('<br/>')
    elif t == 'footnote_ref':
        return Markup(f'<sup class="fn-ref">{_render_inline_list(content)}</sup>')
    elif t == 'display_formula_inline':
        svg = item.get('svg', '')
        if svg and '<svg' in svg:
            return Markup(f'<span class="formula-inline-svg">{svg}</span>')
        return Markup('')
    elif t == 'paragraph_inline':
        return Markup(f'<p>{_render_inline_list(content)}</p>')
    elif t == 'inline_graphic':
        href = item.get('href', '')
        img_path = item.get('img_path', href)
        if img_path and os.path.exists(img_path):
            import pathlib
            uri = pathlib.Path(img_path).as_uri()
            return Markup(f'<img src="{uri}" class="inline-graphic" />')
        elif href:
            return Markup(f'[Image: {_escape(href)}]')
        return Markup('')
    else:
        return Markup(_escape(val))


def _render_inline_list(items):
    if not items:
        return Markup('')
    parts = []
    for i in items:
        parts.append(str(_render_inline(i)))
    return Markup(''.join(parts))


# ─── Body rendering ───────────────────────────────────────────────

def _render_body_item(item):
    t = item.get('type', '')
    if t == 'section':
        return Markup(_render_section(item))
    elif t == 'paragraph':
        return Markup(f'<p>{_render_inline_list(item.get("content", []))}</p>')
    elif t == 'figure':
        return Markup(_render_figure(item))
    elif t == 'display_formula':
        return Markup(_render_formula(item))
    elif t == 'blockquote':
        return Markup(_render_blockquote(item))
    elif t == 'list':
        return Markup(_render_list(item))
    return Markup('')


def _render_body_blocks(body):
    """Render body items, separating table (full-width) from multicol content."""
    multicol = []
    blocks = []

    def flush():
        if multicol:
            blocks.append('<div class="article-body">')
            blocks.append('\n'.join(multicol))
            blocks.append('</div>')
            multicol.clear()

    for item in body:
        _walk_body_item(item, multicol, blocks, flush)

    flush()
    return Markup('\n'.join(blocks))


def _walk_body_item(item, multicol, blocks, flush):
    t = item.get('type', '')
    if t == 'section':
        sec_id = item.get('id', '')
        title = item.get('title', [])
        level = item.get('level', 1)
        htag = f'h{min(level + 1, 6)}'
        css_class = 'section-title' if level <= 2 else 'subsection-title'
        if title:
            id_attr = f' id="{sec_id}"' if sec_id else ''
            multicol.append(f'<{htag} class="{css_class}"{id_attr}>{_render_inline_list(title)}</{htag}>')
        for child in item.get('children', []):
            _walk_body_item(child, multicol, blocks, flush)
    elif t == 'table':
        flush()
        blocks.append(str(_render_table(item)))
    else:
        multicol.append(str(_render_body_item(item)))


def _render_section(section):
    parts = []
    sec_id = section.get('id', '')
    level = section.get('level', 1)
    htag = f'h{min(level + 1, 6)}'
    css_class = 'section-title' if level <= 2 else 'subsection-title'
    title = section.get('title', [])
    if title:
        id_attr = f' id="{sec_id}"' if sec_id else ''
        parts.append(f'<{htag} class="{css_class}"{id_attr}>{_render_inline_list(title)}</{htag}>')
    for child in section.get('children', []):
        parts.append(str(_render_body_item(child)))
    return Markup('\n'.join(parts))


def _render_figure(fig):
    fig_id = fig.get('id', '')
    if fig_id:
        parts = [f'<div class="figure-wrap" id="{fig_id}">']
    else:
        parts = ['<div class="figure-wrap">']
    label = fig.get('label', [])
    parts.append(f'<p class="fig-label">{_render_inline_list(label) if isinstance(label, list) else _escape(str(label))}</p>')
    caption = fig.get('caption', '')
    if caption:
        parts.append(f'<p class="fig-caption">{_render_inline_list(caption) if isinstance(caption, list) else _escape(str(caption))}</p>')
    img_path = fig.get('img_path', '')
    if img_path and os.path.exists(img_path):
        import pathlib
        uri = pathlib.Path(img_path).as_uri()
        parts.append(f'<img src="{uri}" alt="figure" />')
    elif img_path:
        parts.append(f'<p class="fig-missing">[Image: {_escape(img_path)}]</p>')
    parts.append('</div>')
    return Markup('\n'.join(parts))


def _render_table(tbl):
    tbl_id = tbl.get('id', '')
    if tbl_id:
        parts = [f'<div class="table-wrap" id="{tbl_id}">']
    else:
        parts = ['<div class="table-wrap">']
    label = tbl.get('label', [])
    parts.append(f'<p class="table-label">{_render_inline_list(label) if isinstance(label, list) else _escape(str(label))}</p>')
    caption = tbl.get('caption', [])
    if caption:
        parts.append(f'<p class="table-caption">{_render_inline_list(caption) if isinstance(caption, list) else _escape(str(caption))}</p>')
    parts.append('<table>')
    headers = tbl.get('headers', [])
    if headers:
        parts.append('<thead>')
        for row in headers:
            parts.append(_render_table_row(row, 'th'))
        parts.append('</thead>')
    rows = tbl.get('rows', [])
    if rows:
        parts.append('<tbody>')
        for row in rows:
            parts.append(_render_table_row(row, 'td'))
        parts.append('</tbody>')
    parts.append('</table>')
    for fn in tbl.get('footnotes', []):
        for p in fn.get('content', []):
            parts.append(f'<p class="table-fn">{_render_inline_list(p)}</p>')
    parts.append('</div>')
    return Markup('\n'.join(parts))


def _render_table_row(row, default_tag):
    cells = []
    for cell in row:
        ctag = cell.get('tag', default_tag)
        attrs = cell.get('attrs', {})
        attr_str = ''
        cs = attrs.get('colspan', '1')
        rs = attrs.get('rowspan', '1')
        if cs and cs != '1':
            attr_str += f' colspan="{cs}"'
        if rs and rs != '1':
            attr_str += f' rowspan="{rs}"'
        cell_style = attrs.get('style', '')
        align = attrs.get('align', '')
        style_parts = []
        if align:
            style_parts.append(f'text-align:{align}')
        if cell_style:
            existing = [s.strip() for s in cell_style.split(';') if s.strip() and not s.strip().startswith('text-align')]
            style_parts.extend(existing)
        if style_parts:
            attr_str += f' style="{"; ".join(style_parts)}"'
        content = str(_render_inline_list(cell.get('content', [])))
        cells.append(f'<{ctag}{attr_str}>{content}</{ctag}>')
    return '<tr>' + ''.join(cells) + '</tr>'


def _render_formula(formula):
    fid = formula.get('id', '')
    if fid:
        parts = [f'<div class="display-formula" id="{fid}">']
    else:
        parts = ['<div class="display-formula">']
    svg = formula.get('svg', '')
    if svg and '<svg' in svg:
        parts.append(svg)
    else:
        parts.append(f'<span class="formula-fallback">{_escape(formula.get("mathml", ""))}</span>')
    label = formula.get('label', '')
    if label:
        parts.append(f'<span class="formula-label">{_escape(label)}</span>')
    parts.append('</div>')
    return Markup('\n'.join(parts))


def _render_blockquote(bq):
    parts = ['<blockquote>']
    for p in bq.get('paragraphs', []):
        parts.append(f'<p>{_render_inline_list(p)}</p>')
    attr = bq.get('attribution', '')
    if attr:
        parts.append(f'<cite>— {_render_inline_list(attr) if isinstance(attr, list) else _escape(attr)}</cite>')
    parts.append('</blockquote>')
    return Markup('\n'.join(parts))


def _render_list(lst):
    tag = 'ol' if lst.get('list_type') in ('order', 'alpha-lower', 'alpha-upper', 'roman-lower', 'roman-upper') else 'ul'
    parts = [f'<{tag}>']
    for item in lst.get('items', []):
        parts.append(f'<li>{_render_inline_list(item) if isinstance(item, list) else _escape(str(item))}</li>')
    parts.append(f'</{tag}>')
    return Markup('\n'.join(parts))


# ─── Back matter ──────────────────────────────────────────────────

def _render_back_item(item):
    t = item.get('type', '')
    parts = []

    if t == 'section':
        parts.append('<div class="back-section">')
        title = item.get('title', [])
        if title:
            parts.append(f'<h2 class="back-title">{_render_inline_list(title)}</h2>')
        for child in item.get('children', []):
            parts.append(str(_render_body_item(child)))
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'acknowledgment':
        parts.append('<div class="acknowledgment">')
        ti = item.get('title', 'Acknowledgments')
        parts.append(f'<h2 class="back-title">{_render_inline_list(ti) if isinstance(ti, list) else _escape(str(ti))}</h2>')
        for p in item.get('paragraphs', []):
            parts.append(f'<p>{_render_inline_list(p)}</p>')
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'references':
        parts.append('<div class="references">')
        ti = item.get('title', 'References')
        parts.append(f'<h2 class="back-title">{_render_inline_list(ti) if isinstance(ti, list) else _escape(str(ti))}</h2>')
        parts.append('<ol class="ref-list">')
        for ref in item.get('references', []):
            ref_id = ref.get('id', '')
            ref_content = ref.get('content', [])
            if ref_id:
                parts.append(f'<li id="{ref_id}">{_render_inline_list(ref_content)}</li>')
            else:
                parts.append(f'<li>{_render_inline_list(ref_content)}</li>')
        parts.append('</ol>')
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'footnotes':
        parts.append('<div class="footnotes">')
        for fn in item.get('footnotes', []):
            for p in fn.get('content', []):
                parts.append(f'<p class="fn-p">{_render_inline_list(p)}</p>')
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'bio':
        parts.append('<div class="bio">')
        ti = item.get('title', '')
        if ti:
            parts.append(f'<h3>{_render_inline_list(ti) if isinstance(ti, list) else _escape(str(ti))}</h3>')
        for p in item.get('paragraphs', []):
            parts.append(f'<p>{_render_inline_list(p)}</p>')
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'notes':
        return Markup(f'<div class="notes">{_render_inline_list(item.get("content", []))}</div>')

    return Markup('')


# ─── Helpers ──────────────────────────────────────────────────────

def _escape(text):
    if not text:
        return ''
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _strip_tags(html_str):
    import re
    return re.sub(r'<[^>]*>', '', html_str or '')


def _get_citation_line(doc_data):
    from jats_parser import get_citation_info
    return get_citation_info(doc_data)


def _get_history(doc_data):
    from jats_parser import get_history_text
    return get_history_text(doc_data)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, _SCRIPT_DIR)
    from jats_parser import parse_jats
    from mathml_renderer import render_all_mathml
    xml_path = sys.argv[1] if len(sys.argv) > 1 else '初始文件.xml'
    doc = parse_jats(xml_path)
    doc = render_all_mathml(doc)
    html = render_html(doc)
    out = xml_path.replace('.xml', '_out.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML → {out} ({len(html):,} chars)")
