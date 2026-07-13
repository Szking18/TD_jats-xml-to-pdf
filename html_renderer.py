"""
Jinja2 HTML 渲染器
将解析后的 JATS 数据字典渲染为完整的 HTML 文档。
"""

import os
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATE_DIR = os.path.join(_SCRIPT_DIR, 'templates')

# 初始化 Jinja2 环境
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(['html', 'xml']),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_html(doc_data: dict) -> str:
    """将解析后的文档数据渲染为 HTML 字符串。

    Args:
        doc_data: jats_parser.parse_jats() 返回的数据字典

    Returns:
        完整的 HTML 字符串
    """
    template = _env.get_template('article.html')

    # 读取 CSS
    css_path = os.path.join(_SCRIPT_DIR, 'style.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    # 注入自定义函数到模板上下文
    ctx = dict(doc_data)
    ctx.update({
        'css': css_content,
        'render_inline': _render_inline,
        'render_inline_list': _render_inline_list,
        'render_body_item': _render_body_item,
        'render_back_item': _render_back_item,
        'get_history': lambda: _get_history(doc_data),
        'citation_line': _get_citation_line(doc_data),
        'striptags': _strip_tags,
    })

    return template.render(**ctx)


# ─── 内联元素渲染 ─────────────────────────────────────────────────

def _render_inline(item):
    """渲染单个内联元素为 HTML 字符串。"""
    if item is None:
        return ''
    t = item.get('type', '')
    val = item.get('value', '')
    content = item.get('content', [])

    if t == 'text':
        return _escape(val)
    elif t == 'italic':
        return f'<i>{_render_inline_list(content)}</i>'
    elif t == 'bold':
        return f'<b>{_render_inline_list(content)}</b>'
    elif t == 'superscript':
        return f'<sup>{_render_inline_list(content)}</sup>'
    elif t == 'subscript':
        return f'<sub>{_render_inline_list(content)}</sub>'
    elif t == 'smallcaps':
        return f'<span class="sc">{_render_inline_list(content)}</span>'
    elif t == 'monospace':
        return f'<code>{_render_inline_list(content)}</code>'
    elif t == 'underline':
        return f'<u>{_render_inline_list(content)}</u>'
    elif t == 'xref':
        rid = item.get('rid', '')
        return f'<sup>{_render_inline_list(content)}</sup>'
    elif t == 'link':
        href = item.get('href', '')
        return f'<a href="{_escape(href)}">{_render_inline_list(content)}</a>'
    elif t == 'inline_formula':
        svg = item.get('svg', '') or item.get('mathml', '')
        if svg.startswith('<svg'):
            return f'<span class="inline-formula">{svg}</span>'
        else:
            return f'<span class="inline-formula-fallback">{_escape(svg)}</span>'
    elif t == 'email':
        return f'<a href="mailto:{_escape(val)}">{_escape(val)}</a>'
    elif t == 'named_content':
        return _render_inline_list(content)
    elif t == 'linebreak':
        return '<br/>'
    elif t == 'footnote_ref':
        return f'<sup class="fn-ref">{_render_inline_list(content)}</sup>'
    elif t == 'display_formula_inline':
        svg = item.get('svg', '')
        if svg.startswith('<svg'):
            return f'<div class="formula-inline-svg">{svg}</div>'
        return ''
    elif t == 'paragraph_inline':
        return f'<p>{_render_inline_list(content)}</p>'
    else:
        return _escape(val)


def _render_inline_list(items):
    """渲染内联元素列表为 HTML 字符串。"""
    if not items:
        return ''
    return ''.join(_render_inline(i) for i in items)


# ─── Body 元素渲染 ────────────────────────────────────────────────

def _render_body_item(item):
    """渲染 body 中的单个元素。"""
    t = item.get('type', '')

    if t == 'section':
        return _render_section(item)
    elif t == 'paragraph':
        return f'<p>{_render_inline_list(item.get("content", []))}</p>'
    elif t == 'figure':
        return _render_figure(item)
    elif t == 'table':
        return _render_table(item)
    elif t == 'display_formula':
        return _render_formula(item)
    elif t == 'blockquote':
        return _render_blockquote(item)
    elif t == 'list':
        return _render_list(item)
    else:
        return ''


def _render_section(section):
    """渲染章节。"""
    parts = []
    level = section.get('level', 1)
    htag = f'h{min(level + 1, 6)}'
    css_class = 'section-title' if level <= 2 else 'subsection-title'

    title = section.get('title', [])
    if title:
        parts.append(f'<{htag} class="{css_class}">{_render_inline_list(title)}</{htag}>')

    for child in section.get('children', []):
        parts.append(_render_body_item(child))

    return '\n'.join(parts)


def _render_figure(fig):
    """渲染图片。"""
    parts = ['<div class="figure-wrap">']
    parts.append(f'<p class="fig-label">{_render_inline_list(fig.get("label", []))}</p>')

    caption = fig.get('caption', '')
    if caption:
        parts.append(f'<p class="fig-caption">{_render_inline_list(caption) if isinstance(caption, list) else _escape(caption)}</p>')

    img_path = fig.get('img_path', '')
    if img_path and os.path.exists(img_path):
        # 转换为 file:// URI
        import pathlib
        uri = pathlib.Path(img_path).as_uri()
        parts.append(f'<img src="{uri}" alt="figure" />')
    elif img_path:
        parts.append(f'<p class="fig-missing">[Image: {_escape(img_path)}]</p>')

    parts.append('</div>')
    return '\n'.join(parts)


def _render_table(tbl):
    """渲染表格。"""
    parts = ['<div class="table-wrap">']

    # Label + caption
    parts.append(f'<p class="table-label">{_render_inline_list(tbl.get("label", []))}</p>')

    caption = tbl.get('caption', [])
    if caption:
        parts.append(f'<p class="table-caption">{_render_inline_list(caption)}</p>')

    # 表格主体
    parts.append('<table>')

    # Headers
    headers = tbl.get('headers', [])
    if headers:
        parts.append('<thead>')
        for row in headers:
            parts.append(_render_table_row(row, 'th'))
        parts.append('</thead>')

    # Body rows
    rows = tbl.get('rows', [])
    if rows:
        parts.append('<tbody>')
        for row in rows:
            parts.append(_render_table_row(row, 'td'))
        parts.append('</tbody>')

    parts.append('</table>')

    # Footnotes
    footnotes = tbl.get('footnotes', [])
    for fn in footnotes:
        for p in fn.get('content', []):
            parts.append(f'<p class="table-fn">{_render_inline_list(p)}</p>')

    parts.append('</div>')
    return '\n'.join(parts)


def _render_table_row(row, default_tag):
    """渲染表格行。"""
    cells = []
    for cell in row:
        ctag = cell.get('tag', default_tag)
        attrs = cell.get('attrs', {})
        attr_str = ''
        if attrs.get('colspan') and attrs['colspan'] != '1':
            attr_str += f' colspan="{attrs["colspan"]}"'
        if attrs.get('rowspan') and attrs['rowspan'] != '1':
            attr_str += f' rowspan="{attrs["rowspan"]}"'
        if attrs.get('align'):
            attr_str += f' style="text-align:{attrs["align"]};"'
        content = _render_inline_list(cell.get('content', []))
        cells.append(f'<{ctag}{attr_str}>{content}</{ctag}>')
    return f'<tr>{"".join(cells)}</tr>'


def _render_formula(formula):
    """渲染显示公式。"""
    parts = ['<div class="display-formula">']
    svg = formula.get('svg', '')
    if svg.startswith('<svg'):
        parts.append(svg)
    else:
        parts.append(f'<div class="formula-fallback">{_escape(formula.get("mathml", ""))}</div>')
    label = formula.get('label', '')
    if label:
        parts.append(f'<span class="formula-label">{_escape(label)}</span>')
    parts.append('</div>')
    return '\n'.join(parts)


def _render_blockquote(bq):
    """渲染引用块。"""
    parts = ['<blockquote>']
    for p in bq.get('paragraphs', []):
        parts.append(f'<p>{_render_inline_list(p)}</p>')
    attr = bq.get('attribution', '')
    if attr:
        parts.append(f'<cite>— {_render_inline_list(attr) if isinstance(attr, list) else _escape(attr)}</cite>')
    parts.append('</blockquote>')
    return '\n'.join(parts)


def _render_list(lst):
    """渲染列表。"""
    tag = 'ol' if lst.get('list_type') in ('order', 'alpha-lower', 'alpha-upper', 'roman-lower', 'roman-upper') else 'ul'
    parts = [f'<{tag}>']
    for item in lst.get('items', []):
        parts.append(f'<li>{_render_inline_list(item) if isinstance(item, list) else _escape(item)}</li>')
    parts.append(f'</{tag}>')
    return '\n'.join(parts)


# ─── Back 元素渲染 ────────────────────────────────────────────────

def _render_back_item(item):
    """渲染 back 元素。"""
    t = item.get('type', '')

    if t == 'section':
        parts = ['<div class="back-section">']
        title = item.get('title', [])
        if title:
            parts.append(f'<h2 class="back-title">{_render_inline_list(title)}</h2>')
        for child in item.get('children', []):
            parts.append(_render_body_item(child))
        parts.append('</div>')
        return '\n'.join(parts)

    elif t == 'acknowledgment':
        parts = ['<div class="acknowledgment">']
        title = item.get('title', 'Acknowledgments')
        parts.append(f'<h2 class="back-title">{_render_inline_list(title) if isinstance(title, list) else _escape(title)}</h2>')
        for p in item.get('paragraphs', []):
            parts.append(f'<p>{_render_inline_list(p)}</p>')
        parts.append('</div>')
        return '\n'.join(parts)

    elif t == 'references':
        parts = ['<div class="references">']
        title = item.get('title', 'References')
        parts.append(f'<h2 class="back-title">{_render_inline_list(title) if isinstance(title, list) else _escape(title)}</h2>')
        parts.append('<ol class="ref-list">')
        for ref in item.get('references', []):
            ref_content = ref.get('content', [])
            parts.append(f'<li>{_render_inline_list(ref_content)}</li>')
        parts.append('</ol>')
        parts.append('</div>')
        return '\n'.join(parts)

    elif t == 'footnotes':
        parts = ['<div class="footnotes">']
        for fn in item.get('footnotes', []):
            for p in fn.get('content', []):
                parts.append(f'<p class="fn-p">{_render_inline_list(p)}</p>')
        parts.append('</div>')
        return '\n'.join(parts)

    elif t == 'bio':
        parts = ['<div class="bio">']
        title = item.get('title', '')
        if title:
            parts.append(f'<h3>{_render_inline_list(title) if isinstance(title, list) else _escape(title)}</h3>')
        for p in item.get('paragraphs', []):
            parts.append(f'<p>{_render_inline_list(p)}</p>')
        parts.append('</div>')
        return '\n'.join(parts)

    elif t == 'notes':
        parts = ['<div class="notes">']
        parts.append(f'{_render_inline_list(item.get("content", []))}')
        parts.append('</div>')
        return '\n'.join(parts)

    else:
        return ''


# ─── 辅助函数 ─────────────────────────────────────────────────────

def _escape(text):
    """HTML 转义。"""
    if not text:
        return ''
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def _strip_tags(html_str):
    """移除 HTML 标签。"""
    import re
    return re.sub(r'<[^>]*>', '', html_str)


def _get_citation_line(doc_data):
    """生成期刊引用行。"""
    from jats_parser import get_citation_info
    return get_citation_info(doc_data)


def _get_history(doc_data):
    """获取格式化历史信息。"""
    from jats_parser import get_history_text
    return get_history_text(doc_data)


# ─── 独立测试入口 ─────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    sys.path.insert(0, _SCRIPT_DIR)
    from jats_parser import parse_jats
    from mathml_renderer import render_all_mathml

    xml_path = sys.argv[1] if len(sys.argv) > 1 else '初始文件.xml'
    print(f"Parsing: {xml_path}")
    doc = parse_jats(xml_path)

    print("Rendering MathML...")
    doc = render_all_mathml(doc)

    print("Rendering HTML...")
    html = render_html(doc)

    output_html = xml_path.replace('.xml', '_out.html')
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML written to: {output_html}")
    print(f"HTML size: {len(html):,} chars")
