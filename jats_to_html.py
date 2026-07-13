import os
import pathlib
import xml.etree.ElementTree as ET

XLINK_NS = '{http://www.w3.org/1999/xlink}'


def jats_to_html(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    xml_dir = os.path.dirname(os.path.abspath(xml_path))

    parts = []
    parts.append("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Document</title>
</head>
<body>
""")
    parts.append(_build_front(root))
    parts.append(_build_body(root, xml_dir))
    parts.append(_build_back(root))
    parts.append("</body>\n</html>")
    return '\n'.join(parts)


def _render_inline(elem):
    if elem is None:
        return ''
    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    result = _escape(elem.text or '')

    if tag == 'msub':
        children = list(elem)
        if len(children) >= 2:
            base = _render_inline(children[0])
            sub = _render_inline(children[1])
            return base + f'<sub>{sub}</sub>'
    elif tag == 'msup':
        children = list(elem)
        if len(children) >= 2:
            base = _render_inline(children[0])
            sup = _render_inline(children[1])
            return base + f'<sup>{sup}</sup>'
    elif tag == 'mfrac':
        children = list(elem)
        if len(children) >= 2:
            num = _render_inline(children[0])
            den = _render_inline(children[1])
            return f'({num})/({den})'

    for child in elem:
        ctag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        inner = _render_inline(child)
        if ctag == 'italic':
            result += f'<i>{inner}</i>'
        elif ctag == 'bold':
            result += f'<b>{inner}</b>'
        elif ctag == 'sup':
            result += f'<sup>{inner}</sup>'
        elif ctag == 'sub':
            result += f'<sub>{inner}</sub>'
        elif ctag == 'xref':
            result += f'<sup>{inner}</sup>'
        elif ctag == 'inline-formula':
            result += f'<span class="inline-formula">{inner}</span>'
        elif ctag == 'math':
            result += inner
        elif ctag == 'mi':
            result += f'<i>{inner}</i>'
        elif ctag == 'mo':
            result += inner
        elif ctag == 'mn':
            result += inner
        elif ctag in ('mrow', 'mphantom'):
            result += inner
        elif ctag == 'mtext':
            result += f'<span class="mtext">{inner}</span>'
        else:
            result += inner
        result += _escape(child.tail or '')
    return result


def _get_text(elem):
    return ''.join(elem.itertext()) if elem is not None else ''


def _escape(text):
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('\u2061', '')
    text = text.replace('\u2062', '')
    text = text.replace('\u2063', '')
    text = text.replace('\u2064', '')
    return text


def _build_front(root):
    lines = []
    lines.append('<div class="front">')

    lines.append('<div class="journal-header">')

    abbrev_journal = root.find('.//abbrev-journal-title[@abbrev-type="publisher"]')
    pub_year = root.find('.//pub-date[@pub-type="epub"]//year')
    volume = root.find('.//volume')
    issue = root.find('.//issue')
    eloc = root.find('.//elocation-id')
    doi_elem = root.find('.//article-id[@pub-id-type="doi"]')
    subject = root.find('.//subj-group[@subj-group-type="heading"]//subject')

    journal_line_parts = []
    if abbrev_journal is not None:
        journal_line_parts.append(_get_text(abbrev_journal))
    if pub_year is not None:
        journal_line_parts.append(_get_text(pub_year))
    vol_issue = ''
    if volume is not None:
        vol_issue = _get_text(volume)
    if issue is not None:
        vol_issue += f'({_get_text(issue)})'
    if eloc is not None:
        vol_issue += f': {_get_text(eloc)}'
    if vol_issue:
        journal_line_parts.append(vol_issue)

    if journal_line_parts:
        lines.append(f'<p class="journal-line">{"; ".join(journal_line_parts)}</p>')

    if doi_elem is not None:
        doi_text = _get_text(doi_elem)
        lines.append(f'<p class="journal-doi">https://doi.org/{doi_text}</p>')

    if subject is not None:
        lines.append(f'<p class="article-type">{_get_text(subject)}</p>')

    lines.append('</div>')

    title_elem = root.find('.//article-title')
    title = _render_inline(title_elem)
    lines.append(f'<h1 class="article-title">{title}</h1>')

    lines.append('<div class="authors">')
    for author in root.findall('.//contrib'):
        surname = author.find('.//surname')
        given = author.find('.//given-names')
        if surname is not None and given is not None:
            lines.append(f'<span class="author">{_get_text(given)} {_get_text(surname)}</span>')
    lines.append('</div>')

    abstract = root.find('.//abstract')
    if abstract is not None:
        lines.append('<div class="abstract">')
        lines.append('<h2>Abstract</h2>')
        for p in abstract.findall('.//p'):
            lines.append(f'<p>{_render_inline(p)}</p>')
        lines.append('</div>')

    kwd_group = root.find('.//kwd-group')
    if kwd_group is not None:
        lines.append('<div class="keywords">')
        lines.append('<h2>Keywords</h2>')
        keywords = [f'<span class="keyword">{_get_text(kwd)}</span>' for kwd in kwd_group.findall('kwd')]
        lines.append(', '.join(keywords))
        lines.append('</div>')

    lines.append('</div>')
    return '\n'.join(lines)


def _build_body(root, xml_dir):
    lines = []
    body = root.find('.//body')
    if body is None:
        return ''

    lines.append('<div class="body">')
    for child in body:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'sec':
            _render_sec(child, lines, xml_dir, level=1)
        elif tag == 'p':
            lines.append(f'<p>{_render_inline(child)}</p>')
        elif tag == 'fig':
            _handle_fig(child, lines, xml_dir)
        elif tag == 'table-wrap':
            _handle_table(child, lines)
    lines.append('</div>')
    return '\n'.join(lines)


def _render_sec(sec_elem, lines, xml_dir, level):
    sec_title = sec_elem.find('title')
    if sec_title is not None:
        h_tag = f'h{min(level + 1, 6)}'
        cls = 'sec-title' if level == 1 else 'subsec-title'
        lines.append(f'<{h_tag} class="{cls}">{_render_inline(sec_title)}</{h_tag}>')

    for child in sec_elem:
        if child.tag == 'title':
            continue
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'p':
            lines.append(f'<p>{_render_inline(child)}</p>')
        elif tag == 'fig':
            _handle_fig(child, lines, xml_dir)
        elif tag == 'sec':
            _render_sec(child, lines, xml_dir, level + 1)
        elif tag == 'table-wrap':
            _handle_table(child, lines)


def _handle_fig(fig_elem, lines, xml_dir):
    label = fig_elem.find('label')
    graphic = fig_elem.find('graphic')

    lines.append('<div class="figure">')
    if label is not None:
        lines.append(f'<p class="fig-label">{_render_inline(label)}</p>')

    caption_ps = fig_elem.findall('.//caption//p')
    if not caption_ps:
        caption_title = fig_elem.find('.//caption/title')
        if caption_title is not None:
            lines.append(f'<p class="fig-caption">{_render_inline(caption_title)}</p>')
    else:
        caption_text = ' '.join(_render_inline(p) for p in caption_ps)
        lines.append(f'<p class="fig-caption">{caption_text}</p>')

    if graphic is not None:
        href = graphic.get(XLINK_NS + 'href', '')
        if href:
            img_path = os.path.join(xml_dir, href) if not os.path.isabs(href) else href
            if not os.path.exists(img_path):
                basename = os.path.basename(href)
                fallback = os.path.join(xml_dir, basename)
                if os.path.exists(fallback):
                    img_path = fallback
            img_src = pathlib.Path(img_path).as_uri()
            lines.append(f'<img src="{img_src}" alt="figure" />')
    lines.append('</div>')


def _handle_table(table_elem, lines):
    lines.append('<div class="table-wrap">')

    label = table_elem.find('label')
    if label is not None:
        lines.append(f'<p class="table-label">{_render_inline(label)}</p>')

    caption = table_elem.find('caption')
    if caption is not None:
        for p in caption.findall('.//p'):
            lines.append(f'<p class="table-caption">{_render_inline(p)}</p>')

    table = table_elem.find('table')
    if table is not None:
        lines.append('<table>')
        for section in table:
            stag = section.tag.split('}')[-1] if '}' in section.tag else section.tag
            if stag in ('thead', 'tbody', 'tfoot'):
                lines.append(f'<{stag}>')
                for tr in section.findall('tr'):
                    lines.append('<tr>')
                    for cell in tr:
                        ctag = cell.tag.split('}')[-1] if '}' in cell.tag else cell.tag
                        if ctag in ('th', 'td'):
                            attrs = ''
                            colspan = cell.get('colspan')
                            rowspan = cell.get('rowspan')
                            if colspan:
                                attrs += f' colspan="{colspan}"'
                            if rowspan:
                                attrs += f' rowspan="{rowspan}"'
                            lines.append(f'<{ctag}{attrs}>{_render_inline(cell)}</{ctag}>')
                    lines.append('</tr>')
                lines.append(f'</{stag}>')
        lines.append('</table>')

    foot = table_elem.find('table-wrap-foot')
    if foot is not None:
        lines.append('<div class="table-footnotes">')
        for fn in foot.findall('fn'):
            for p in fn.findall('p'):
                lines.append(f'<p class="table-fn">{_render_inline(p)}</p>')
        lines.append('</div>')

    lines.append('</div>')


def _build_back(root):
    lines = []
    back = root.find('.//back')
    if back is None:
        return ''

    lines.append('<div class="back">')
    for child in back:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'sec':
            _render_sec(child, lines, None, level=1)
        elif tag == 'ack':
            _handle_ack(child, lines)
        elif tag == 'ref-list':
            _handle_ref_list(child, lines)
        elif tag == 'fn-group':
            _handle_fn_group(child, lines)
        elif tag == 'app-group':
            for app in child.findall('app'):
                _render_sec(app, lines, None, level=1)
    lines.append('</div>')
    return '\n'.join(lines)


def _handle_ack(ack_elem, lines):
    title = ack_elem.find('title')
    if title is not None:
        lines.append(f'<h2 class="sec-title">{_render_inline(title)}</h2>')
    for p in ack_elem.findall('p'):
        lines.append(f'<p>{_render_inline(p)}</p>')


def _handle_ref_list(ref_list_elem, lines):
    title = ref_list_elem.find('title')
    if title is not None:
        lines.append(f'<h2 class="sec-title">{_render_inline(title)}</h2>')

    lines.append('<ol class="ref-list">')
    for ref in ref_list_elem.findall('ref'):
        lines.append(f'<li>{_render_ref(ref)}</li>')
    lines.append('</ol>')


def _render_ref(ref_elem):
    citation = ref_elem.find('element-citation')
    if citation is None:
        citation = ref_elem.find('mixed-citation')
        if citation is not None:
            return _render_inline(citation)

    parts = []

    person_group = citation.find('person-group') if citation is not None else None
    if person_group is not None:
        names = []
        for name in person_group.findall('name'):
            surname = name.find('surname')
            given = name.find('given-names')
            if surname is not None and given is not None:
                names.append(f'{_get_text(surname)} {_get_text(given)}')
        has_etal = person_group.find('etal') is not None
        if names:
            if has_etal:
                parts.append(', '.join(names) + ', et al.')
            else:
                parts.append(', '.join(names))

    if citation is None:
        return _escape(_get_text(ref_elem))

    article_title = citation.find('article-title')
    if article_title is not None:
        parts.append(f'<i>{_render_inline(article_title)}</i>')

    source = citation.find('source')
    if source is not None:
        parts.append(f'<span class="ref-source">{_render_inline(source)}</span>')

    edition = citation.find('edition')
    publisher_name = citation.find('publisher-name')
    publisher_loc = citation.find('publisher-loc')
    if publisher_name is not None or publisher_loc is not None:
        loc = _get_text(publisher_loc) if publisher_loc is not None else ''
        pub = _get_text(publisher_name) if publisher_name is not None else ''
        if edition is not None:
            parts.append(f'({_get_text(edition)})')
        if loc and pub:
            parts.append(f'{loc}: {pub}')
        elif pub:
            parts.append(pub)

    year = citation.find('year')
    volume = citation.find('volume')
    fpage = citation.find('fpage')
    lpage = citation.find('lpage')

    year_text = _get_text(year) if year is not None else ''
    volume_text = _get_text(volume) if volume is not None else ''
    pages = ''
    if fpage is not None:
        pages = _get_text(fpage)
        if lpage is not None:
            pages += '--' + _get_text(lpage)

    if citation.get('publication-type') == 'book':
        if year_text:
            parts.append(year_text)
    else:
        loc_parts = []
        if year_text:
            loc_parts.append(year_text)
        if volume_text:
            loc_parts.append(f'<b>{volume_text}</b>')
        if pages:
            loc_parts.append(f':{pages}')
        if loc_parts:
            parts.append(', '.join(loc_parts))

    ext_link = citation.find('ext-link')
    if ext_link is not None:
        href = ext_link.get(XLINK_NS + 'href', '')
        if href:
            parts.append(f'<a href="{href}">{href}</a>')

    comment = citation.find('comment')
    date_in_citation = citation.find('date-in-citation')
    if comment is not None:
        text = _get_text(comment)
        if text:
            parts.append(text)
    if date_in_citation is not None:
        text = _get_text(date_in_citation)
        if text:
            parts.append(f'({text})')

    return '. '.join(parts) + '.' if parts else ''


def _handle_fn_group(fn_group_elem, lines):
    for fn in fn_group_elem.findall('fn'):
        for p in fn.findall('p'):
            lines.append(f'<p>{_render_inline(p)}</p>')
