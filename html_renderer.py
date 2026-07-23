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

    back_items = [item for item in doc_data.get('back', []) if item.get('type') != 'footnotes']
    ctx = dict(doc_data)
    ctx['back'] = back_items
    ctx.update({
        'css': Markup(css_content),
        'publisher_logo': Markup(publisher_logo_html),
        'journal_logo': Markup(journal_logo_html),
        'first_page_note': Markup(_render_first_page_note(doc_data)),
        'render_inline': _render_inline,
        'render_inline_list': _render_inline_list,
        'render_body_item': _render_body_item,
        'render_back_item': _render_back_item,
        'get_history': lambda: Markup(_get_history(doc_data)),
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


def _render_first_page_note(doc_data):
    notes = []
    front = doc_data.get('front', {})
    if front.get('copyright'):
        notes.append(_escape(front.get('copyright')).strip())
    if front.get('license'):
        notes.append(str(_render_inline_list(front.get('license'))).strip())
    for item in doc_data.get('back', []):
        if item.get('type') == 'footnotes':
            for fn in item.get('footnotes', []):
                for p in fn.get('content', []):
                    text = str(_render_inline_list(p)).strip()
                    # 清理 XML 中的多余空白字符（换行、tab等）
                    import re
                    text = re.sub(r'\s+', ' ', text)
                    notes.append(text)
    if not notes:
        return ''
    # CC BY license badge for open-access articles
    badge_html = _build_license_badge(doc_data)
    return '<div id="first-footer">' + badge_html + '<br>'.join(notes) + '</div>'


def _build_license_badge(doc_data):
    """Build a Creative Commons license badge image for the first page footer."""
    front = doc_data.get('front', {})
    license_list = front.get('license', [])
    if not license_list:
        return ''
    # Detect license type from the license inline content
    license_text = str(_render_inline_list(license_list))
    import re
    # Map license text to badge URL
    badge_map = {
        'CC BY 4.0': os.path.join(_LOGO_DIR, 'cc_by_4.0.png'),
        'CC BY 3.0': os.path.join(_LOGO_DIR, 'cc_by_3.0.png'),
        'CC BY-NC 4.0': os.path.join(_LOGO_DIR, 'cc_by_nc_4.0.png'),
        'CC BY-NC-ND 4.0': os.path.join(_LOGO_DIR, 'cc_by_nc_nd_4.0.png'),
        'CC BY-NC-SA 4.0': os.path.join(_LOGO_DIR, 'cc_by_nc_sa_4.0.png'),
        'CC0': os.path.join(_LOGO_DIR, 'cc_zero.png'),
    }
    badge_file = ''
    for key, filename in badge_map.items():
        if key in license_text:
            badge_file = filename
            break
    if not badge_file:
        return ''
    import pathlib
    badge_uri = pathlib.Path(badge_file).as_uri()
    return f'<img src="{badge_uri}" alt="{key}" class="first-footer-logo" /> '


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
        ref_type = item.get('ref_type', '')
        rid = item.get('rid', '')
        if ref_type == 'bibr' and rid:
            return Markup(f'<sup class="xref-sup"><a href="#ref-{_escape(rid)}">{_render_inline_list(content)}</a></sup>')
        elif ref_type == 'fig' and rid:
            return Markup(f'<sup class="xref-sup"><a href="#fig-{_escape(rid)}">{_render_inline_list(content)}</a></sup>')
        elif rid:
            # aff / fn / other: content typically already contains <sup>, just wrap in link
            return Markup(f'<a href="#{_escape(rid)}">{_render_inline_list(content)}</a>')
        else:
            return _render_inline_list(content)
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
    elif t == 'table':
        return Markup(_render_table(item))
    elif t == 'display_formula':
        return Markup(_render_formula(item))
    elif t == 'blockquote':
        return Markup(_render_blockquote(item))
    elif t == 'list':
        return Markup(_render_list(item))
    return Markup('')


def _render_section(section):
    parts = []
    level = section.get('level', 1)
    htag = f'h{min(level + 1, 6)}'
    css_class = 'section-title' if level <= 2 else 'subsection-title'
    title = section.get('title', [])
    if title:
        parts.append(f'<{htag} class="{css_class}">{_render_inline_list(title)}</{htag}>')
    for child in section.get('children', []):
        parts.append(str(_render_body_item(child)))
    return Markup('\n'.join(parts))


def _render_figure(fig):
    fig_id = fig.get('id', '')
    id_attr = f' id="fig-{_escape(fig_id)}"' if fig_id else ''
    parts = [f'<div class="figure-wrap"{id_attr}>']
    img_path = fig.get('img_path', '')
    if img_path and os.path.exists(img_path):
        import pathlib
        uri = pathlib.Path(img_path).resolve().as_uri()
        parts.append(f'<img src="{uri}" alt="figure" />')
    elif img_path:
        parts.append(f'<p class="fig-missing">[Image: {_escape(img_path)}]</p>')

    label = fig.get('label', [])
    parts.append(f'<p class="fig-label">{_render_inline_list(label) if isinstance(label, list) else _escape(str(label))}</p>')
    caption = fig.get('caption', '')
    if caption:
        parts.append(f'<div class="fig-caption">{_render_inline_list(caption) if isinstance(caption, list) else _escape(str(caption))}</div>')
    parts.append('</div>')
    return Markup('\n'.join(parts))


def _render_table(tbl):
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
        align = attrs.get('align', '')
        if align:
            attr_str += f' style="text-align:{align}"'
        content = str(_render_inline_list(cell.get('content', [])))
        cells.append(f'<{ctag}{attr_str}>{content}</{ctag}>')
    return '<tr>' + ''.join(cells) + '</tr>'


def _render_formula(formula):
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
        parts.append('<div class="back-columns">')
        for p in item.get('paragraphs', []):
            parts.append(f'<p>{_render_inline_list(p)}</p>')
        parts.append('</div>')
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'references':
        parts.append('<div class="references">')
        ti = item.get('title', 'References')
        parts.append(f'<h2 class="back-title">{_render_inline_list(ti) if isinstance(ti, list) else _escape(str(ti))}</h2>')
        parts.append('<div class="back-columns">')
        parts.append('<ol class="ref-list">')
        for ref in item.get('references', []):
            ref_content = ref.get('content', [])
            ref_id = ref.get('id', '')
            id_attr = f' id="ref-{_escape(ref_id)}"' if ref_id else ''
            parts.append(f'<li{id_attr}>{_render_inline_list(ref_content)}</li>')
        parts.append('</ol>')
        parts.append('</div>')
        parts.append('</div>')
        return Markup('\n'.join(parts))

    elif t == 'footnotes':
        parts.append('<div class="back-footnotes">')
        for fn in item.get('footnotes', []):
            for p in fn.get('content', []):
                parts.append(f'<p>{_render_inline_list(p)}</p>')
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
