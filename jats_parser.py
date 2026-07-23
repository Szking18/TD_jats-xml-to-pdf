"""
JATS XML 完整解析器
将 JATS 1.3 格式的学术论文 XML 解析为结构化数据字典，
供后续 HTML 模板渲染使用。

支持命名空间: JATS, MathML (mml), XLink
"""

import re
import os
from lxml import etree

# 命名空间常量
NS = {
    'jats': None,  # 自动检测默认命名空间
    'mml': 'http://www.w3.org/1998/Math/MathML',
    'xlink': 'http://www.w3.org/1999/xlink',
}


def parse_jats(xml_path: str) -> dict:
    """解析 JATS XML 文件，返回结构化数据字典。"""
    tree = etree.parse(xml_path)
    root = tree.getroot()

    # 检测 JATS 默认命名空间
    ns_uri = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    if ns_uri:
        NS['jats'] = ns_uri

    doc = {
        'xml_dir': os.path.dirname(os.path.abspath(xml_path)),
        'xml_filename': os.path.basename(xml_path),
        'article_type': root.get('article-type', ''),
        'title': '',
        'front': {},
        'body': [],
        'back': [],
        '_id_map': {},  # 存储 id -> label 的映射，用于交叉引用
        '_figure_count': 0,
        '_table_count': 0,
        '_formula_count': 0,
        '_ref_count': 0,
    }

    # 解析 front
    front = _find(root, 'front')
    if front is not None:
        doc['front'] = _parse_front(front)
        doc['title'] = doc['front'].get('title', '')

    # 解析 body
    body = _find(root, 'body')
    if body is not None:
        doc['body'] = _parse_body(body, doc)

    # 解析 back
    back = _find(root, 'back')
    if back is not None:
        doc['back'] = _parse_back(back, doc)

    return doc


# ─── helpers ────────────────────────────────────────────────────

def _find(elem, tag):
    """在元素中查找直接或嵌套子元素（处理命名空间）。"""
    for ns_prefix in ['jats', None]:
        ns_uri = NS.get(ns_prefix, '')
        full_tag = f'{{{ns_uri}}}{tag}' if ns_uri else tag
        found = elem.find(f'.//{full_tag}')
        if found is not None:
            return found
    return elem.find(f'.//{tag}') if not NS.get('jats') else elem.find(f'.//{{}}{tag}')


def _find_direct(elem, tag):
    """查找直接子元素。"""
    ns = NS.get('jats', '')
    full_tag = f'{{{ns}}}{tag}' if ns else tag
    return elem.find(full_tag)


def _findall(elem, tag):
    """查找所有子元素（递归）。"""
    ns = NS.get('jats', '')
    full_tag = f'.//{{{ns}}}{tag}' if ns else f'.//{tag}'
    return elem.findall(full_tag)


def _findall_direct(elem, tag):
    """查找所有直接子元素。"""
    ns = NS.get('jats', '')
    full_tag = f'{{{ns}}}{tag}' if ns else tag
    return elem.findall(full_tag)


def _tag(elem):
    """获取元素的本地标签名（去掉命名空间前缀）。"""
    return elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag


def _get_text(elem):
    """获取元素的纯文本内容。"""
    return ''.join(elem.itertext()).strip() if elem is not None else ''


def _attr(elem, name, ns=None):
    """获取属性值。"""
    if ns:
        ns_uri = NS.get(ns, '')
        if ns_uri:
            full_attr = f'{{{ns_uri}}}{name}'
            return elem.get(full_attr, '')
    return elem.get(name, '')


# ─── front 解析 ─────────────────────────────────────────────────

def _parse_front(front):
    journal_meta = _find(front, 'journal-meta')
    article_meta = _find(front, 'article-meta')

    result = {}

    if journal_meta is not None:
        result['journal'] = _parse_journal_meta(journal_meta)
    if article_meta is not None:
        result.update(_parse_article_meta(article_meta))

    return result


def _parse_journal_meta(jm):
    info = {}

    jid = _find(jm, 'journal-id')
    if jid is not None:
        info['publisher_id'] = _get_text(jid)

    jtg = _find(jm, 'journal-title-group')
    if jtg is not None:
        jt = _find(jtg, 'journal-title')
        if jt is not None:
            info['title'] = _get_text(jt)
        for abrelem in _findall(jtg, 'abbrev-journal-title'):
            atype = _attr(abrelem, 'abbrev-type')
            text = _get_text(abrelem)
            if atype == 'publisher':
                info['abbrev'] = text
            elif atype == 'pubmed':
                info['abbrev_pubmed'] = text

    issns = []
    for issn in _findall(jm, 'issn'):
        issns.append({
            'type': _attr(issn, 'pub-type'),
            'value': _get_text(issn),
        })
    info['issn'] = issns

    publisher = _find(jm, 'publisher')
    if publisher is not None:
        pname = _find(publisher, 'publisher-name')
        if pname is not None:
            info['publisher'] = _get_text(pname)

    return info


def _parse_article_meta(am):
    info = {}

    # DOI
    doi = _find_article_id(am, 'doi')
    if doi:
        info['doi'] = doi

    # 文章类型
    sc = _find(am, 'article-categories')
    if sc is not None:
        subjects = []
        for sg in _findall(sc, 'subj-group'):
            st = _find(sg, 'subject')
            if st is not None:
                subjects.append(_get_text(st))
        info['subjects'] = subjects
        if subjects:
            info['article_type_label'] = subjects[0]

    # 标题
    tg = _find(am, 'title-group')
    if tg is not None:
        at = _find(tg, 'article-title')
        if at is not None:
            info['title'] = _render_inline_to_dict(at)
            info['title_text'] = _get_text(at)

    # 作者
    info['authors'] = []
    info['editors'] = []
    for cg in _findall(am, 'contrib-group'):
        for contrib in _findall_direct(cg, 'contrib'):
            ctype = _attr(contrib, 'contrib-type')
            author_data = _parse_contrib(contrib)
            if ctype == 'editor':
                info['editors'].append(author_data)
            else:
                info['authors'].append(author_data)

    # 机构
    info['affiliations'] = []
    for aff in _findall(am, 'aff'):
        info['affiliations'].append(_parse_affiliation(aff))

    # 作者注释（通讯作者等）
    an = _find(am, 'author-notes')
    if an is not None:
        info['correspondence'] = []
        info['author_footnotes'] = []
        for child in an:
            ctag = _tag(child)
            if ctag == 'corresp':
                corr_info = {'label': _render_inline_to_dict(_find(child, 'sup')),
                             'text': _parse_mixed_content(child)}
                # Extract emails
                emails = _findall(child, 'email')
                corr_info['emails'] = [_get_text(e) for e in emails]
                info['correspondence'].append(corr_info)
            elif ctag == 'fn':
                info['author_footnotes'].append(_parse_mixed_content(child))

    # 日期
    for ptype in ['epub', 'ppub', 'collection']:
        pd = _find_with_attr(am, 'pub-date', 'pub-type', ptype)
        if pd is not None:
            info[f'pub_date_{ptype}'] = _parse_date(pd)

    # 卷/期/文章位置
    for tag in ['volume', 'issue', 'elocation-id']:
        elem = _find(am, tag)
        if elem is not None and _get_text(elem):
            info[tag.replace('-', '_')] = _get_text(elem)

    # 历史记录
    history = _find(am, 'history')
    if history is not None:
        info['history'] = []
        for date in _findall_direct(history, 'date'):
            d = _parse_date(date)
            d['type'] = _attr(date, 'date-type')
            info['history'].append(d)

    # 权限/版权
    perm = _find(am, 'permissions')
    if perm is not None:
        cs = _find(perm, 'copyright-statement')
        if cs is not None:
            info['copyright'] = _get_text(cs)
        cy = _find(perm, 'copyright-year')
        if cy is not None:
            info['copyright_year'] = _get_text(cy)
        lic = _find(perm, 'license')
        if lic is not None:
            lp = _find(lic, 'license-p')
            if lp is not None:
                info['license'] = _parse_mixed_content(lp)

    # 摘要
    abstract = _find(am, 'abstract')
    if abstract is not None:
        info['abstract'] = _parse_abstract(abstract)

    # 关键词
    kwd_group = _find(am, 'kwd-group')
    if kwd_group is not None:
        info['keywords'] = [_get_text(k) for k in _findall(kwd_group, 'kwd')]

    # 资助
    funding = _find(am, 'funding-group')
    if funding is not None:
        info['funding'] = []
        for ag in _findall(funding, 'award-group'):
            fs = _find(ag, 'funding-source')
            aid = _find(ag, 'award-id')
            info['funding'].append({
                'source': _get_text(fs) if fs is not None else '',
                'id': _get_text(aid) if aid is not None else '',
            })
        fstmt = _find(funding, 'funding-statement')
        if fstmt is not None:
            info['funding_statement'] = _get_text(fstmt)

    return info


def _find_article_id(am, id_type):
    for aid in _findall(am, 'article-id'):
        if _attr(aid, 'pub-id-type') == id_type:
            return _get_text(aid)
    return None


def _find_with_attr(elem, tag, attr_name, attr_value):
    for child in _findall(elem, tag):
        if _attr(child, attr_name) == attr_value:
            return child
    return None


_MONTH_NAMES = {
    '1': 'January', '2': 'February', '3': 'March', '4': 'April',
    '5': 'May', '6': 'June', '7': 'July', '8': 'August',
    '9': 'September', '10': 'October', '11': 'November', '12': 'December',
}


def _parse_date(elem):
    parts = {}
    for sub in ['day', 'month', 'year']:
        s = _find(elem, sub)
        parts[sub] = _get_text(s) if s is not None else ''
    # 格式化日期字符串 (ISO)
    if parts.get('year'):
        y = parts.get('year', '')
        m = parts.get('month', '')
        d = parts.get('day', '')
        if m and d:
            date_str = f'{y}-{int(m):02d}-{int(d):02d}'
        elif m:
            date_str = f'{y}-{int(m):02d}'
        else:
            date_str = y
    else:
        date_str = ''
    parts['formatted'] = date_str
    # 自然语言格式: "DD Month YYYY"
    if parts.get('day') and parts.get('month') and parts.get('year'):
        month_name = _MONTH_NAMES.get(str(int(parts['month'])), parts['month'])
        parts['display'] = f'{int(parts["day"])} {month_name} {parts["year"]}'
    elif parts.get('month') and parts.get('year'):
        month_name = _MONTH_NAMES.get(str(int(parts['month'])), parts['month'])
        parts['display'] = f'{month_name} {parts["year"]}'
    elif parts.get('year'):
        parts['display'] = parts['year']
    else:
        parts['display'] = ''
    return parts


def _parse_contrib(contrib):
    data = {
        'type': _attr(contrib, 'contrib-type', ''),
        'name': '',
        'surname': '',
        'given_names': '',
        'xrefs': [],
        'emails': [],
        'orcid': '',
        'role': '',
    }

    for ci in _findall(contrib, 'contrib-id'):
        if _attr(ci, 'contrib-id-type') == 'orcid':
            data['orcid'] = _get_text(ci)

    name = _find(contrib, 'name')
    if name is not None:
        sn = _find(name, 'surname')
        gn = _find(name, 'given-names')
        data['surname'] = _get_text(sn) if sn is not None else ''
        data['given_names'] = _get_text(gn) if gn is not None else ''
        data['name'] = f"{data['given_names']} {data['surname']}".strip()

    for xref in _findall(contrib, 'xref'):
        data['xrefs'].append({
            'ref_type': _attr(xref, 'ref-type', ''),
            'rid': _attr(xref, 'rid', ''),
            'text': _render_inline_to_dict(xref),
        })

    for email in _findall(contrib, 'email'):
        data['emails'].append(_get_text(email))

    role = _find(contrib, 'role')
    if role is not None:
        data['role'] = _get_text(role)

    return data


def _parse_affiliation(aff):
    aff_id = _attr(aff, 'id', '')
    sup = _find(aff, 'sup')
    label = _get_text(sup) if sup is not None else ''
    # 获取除 sup 外的所有文本
    parts = []
    if sup is not None:
        parts.append(_get_text(sup))
        parts.append(' ')
    for child in aff:
        if _tag(child) != 'sup':
            parts.append(_get_text(child) if child.text else '')
            parts.append(child.tail or '')
    text = ''.join(parts).strip()
    # 更简洁的方式：直接用 itertext
    text = ' '.join(aff.itertext()).strip()
    return {'id': aff_id, 'label': label, 'text': text}


def _parse_abstract(abstract):
    sections = []
    # 检查是否有 <sec> 子元素（结构化摘要）
    secs = _findall_direct(abstract, 'sec')
    if secs:
        for sec in secs:
            title = _find(sec, 'title')
            paragraphs = []
            for p in _findall_direct(sec, 'p'):
                paragraphs.append(_parse_mixed_content(p))
            sections.append({
                'title': _get_text(title) if title is not None else '',
                'paragraphs': paragraphs,
            })
    else:
        # 非结构化摘要（只有 <p>）
        paragraphs = []
        for p in _findall_direct(abstract, 'p'):
            paragraphs.append(_parse_mixed_content(p))
        sections.append({
            'title': '',
            'paragraphs': paragraphs,
        })
    return sections


# ─── body 解析 ──────────────────────────────────────────────────

def _parse_body(body, doc):
    sections = []
    for child in body:
        tag = _tag(child)
        if tag == 'sec':
            sections.append(_parse_section(child, doc))
        elif tag == 'p':
            sections.append({'type': 'paragraph', 'content': _parse_mixed_content(child)})
        elif tag == 'fig':
            sections.append(_parse_figure(child, doc))
        elif tag == 'table-wrap':
            sections.append(_parse_table(child, doc))
        elif tag == 'disp-formula':
            sections.append(_parse_disp_formula(child, doc))
        elif tag == 'disp-quote':
            sections.append(_parse_blockquote(child))
        elif tag == 'list':
            sections.append(_parse_list(child))
    return sections


def _parse_section(sec, doc, level=1):
    section = {
        'type': 'section',
        'level': level,
        'id': _attr(sec, 'id', ''),
        'title': '',
        'children': [],
    }
    sec_title = _find_direct(sec, 'title')
    if sec_title is not None:
        section['title'] = _render_inline_to_dict(sec_title)

    for child in sec:
        tag = _tag(child)
        if tag == 'title':
            continue
        elif tag == 'sec':
            section['children'].append(_parse_section(child, doc, level + 1))
        elif tag == 'p':
            section['children'].append({'type': 'paragraph', 'content': _parse_mixed_content(child)})
        elif tag == 'fig':
            section['children'].append(_parse_figure(child, doc))
        elif tag == 'table-wrap':
            section['children'].append(_parse_table(child, doc))
        elif tag == 'disp-formula':
            section['children'].append(_parse_disp_formula(child, doc))
        elif tag == 'disp-quote':
            section['children'].append(_parse_blockquote(child))
        elif tag == 'list':
            section['children'].append(_parse_list(child))

    return section


def _parse_figure(fig, doc):
    doc['_figure_count'] += 1
    fig_num = doc['_figure_count']
    fig_id = _attr(fig, 'id', '')

    label = _find(fig, 'label')
    caption = _find(fig, 'caption')
    graphic = _find(fig, 'graphic')

    # 尝试确定图片路径
    img_path = ''
    if graphic is not None:
        href = _attr(graphic, 'href', ns='xlink')
        img_path = href if href else ''

    if fig_id:
        doc['_id_map'][fig_id] = f'Fig. {fig_num}'

    return {
        'type': 'figure',
        'id': fig_id,
        'number': fig_num,
        'label': _parse_mixed_content(label) if label is not None else f'Fig. {fig_num}.',
        'caption': _parse_mixed_content(caption) if caption is not None else '',
        'img_path': img_path,
    }


def _parse_table(table_wrap, doc):
    doc['_table_count'] += 1
    tbl_num = doc['_table_count']
    tbl_id = _attr(table_wrap, 'id', '')

    label = _find(table_wrap, 'label')
    caption = _find(table_wrap, 'caption')
    table = _find(table_wrap, 'table')
    foot = _find(table_wrap, 'table-wrap-foot')

    if tbl_id:
        doc['_id_map'][tbl_id] = f'Table {tbl_num}'

    result = {
        'type': 'table',
        'id': tbl_id,
        'number': tbl_num,
        'label': _parse_mixed_content(label) if label is not None else f'Table {tbl_num}.',
        'caption': _parse_mixed_content(caption) if caption is not None else [],
        'colgroups': [],
        'headers': [],
        'rows': [],
        'footnotes': [],
    }

    # 解析 colgroup
    if table is not None:
        for colgroup in _findall_direct(table, 'colgroup'):
            cg = []
            for col in _findall_direct(colgroup, 'col'):
                cg.append({
                    'width': _attr(col, 'width', ''),
                })
            result['colgroups'].append(cg)

        # 解析 thead
        thead = _find_direct(table, 'thead')
        if thead is not None:
            for tr in _findall_direct(thead, 'tr'):
                result['headers'].append(_parse_row(tr))

        # 解析 tbody
        tbody = _find_direct(table, 'tbody')
        if tbody is not None:
            for tr in _findall_direct(tbody, 'tr'):
                result['rows'].append(_parse_row(tr))

    # 脚注
    if foot is not None:
        for fn in _findall_direct(foot, 'fn'):
            fn_id = _attr(fn, 'id', '')
            paragraphs = []
            for p in _findall_direct(fn, 'p'):
                paragraphs.append(_parse_mixed_content(p))
            result['footnotes'].append({'id': fn_id, 'content': paragraphs})

    return result


def _parse_row(tr):
    cells = []
    for cell in tr:
        ctag = _tag(cell)
        if ctag in ('th', 'td'):
            attrs = {
                'colspan': _attr(cell, 'colspan', '') or '1',
                'rowspan': _attr(cell, 'rowspan', '') or '1',
                'align': _attr(cell, 'align', '') or 'left',
                'style': _attr(cell, 'style', ''),
            }
            cells.append({
                'tag': ctag,
                'attrs': attrs,
                'content': _parse_mixed_content(cell),
            })
    return cells


def _parse_disp_formula(formula, doc):
    doc['_formula_count'] += 1
    fnum = doc['_formula_count']
    fid = _attr(formula, 'id', '')

    label = _find(formula, 'label')
    math = _find(formula, '{http://www.w3.org/1998/Math/MathML}math')
    if math is None:
        math = _find(formula, 'math')

    if fid:
        doc['_id_map'][fid] = f'({fnum})'

    return {
        'type': 'display_formula',
        'id': fid,
        'number': fnum,
        'label': _get_text(label) if label is not None else f'({fnum})',
        'mathml': etree.tostring(math, encoding='unicode') if math is not None else '',
    }


def _parse_blockquote(elem):
    paragraphs = []
    for p in _findall_direct(elem, 'p'):
        paragraphs.append(_parse_mixed_content(p))
    attrib = _find(elem, 'attrib')
    attribution = _parse_mixed_content(attrib) if attrib is not None else ''
    return {
        'type': 'blockquote',
        'paragraphs': paragraphs,
        'attribution': attribution,
    }


def _parse_list(list_elem):
    list_type = _attr(list_elem, 'list-type', '') or 'bullet'
    items = []
    for item in _findall_direct(list_elem, 'list-item'):
        p = _find(item, 'p')
        if p is not None:
            items.append(_parse_mixed_content(p))
        else:
            items.append(_get_text(item))
    return {
        'type': 'list',
        'list_type': list_type,
        'items': items,
    }


# ─── back 解析 ──────────────────────────────────────────────────

def _parse_back(back, doc):
    sections = []
    for child in back:
        tag = _tag(child)
        if tag == 'sec':
            sections.append(_parse_section(child, doc))
        elif tag == 'ack':
            sections.append(_parse_ack(child))
        elif tag == 'ref-list':
            sections.append(_parse_ref_list(child, doc))
        elif tag == 'fn-group':
            sections.append(_parse_fn_group(child))
        elif tag == 'app-group':
            for app in _findall_direct(child, 'app'):
                sections.append(_parse_section(app, doc))
        elif tag == 'bio':
            sections.append(_parse_bio(child))
        elif tag == 'notes':
            sections.append({'type': 'notes', 'content': _parse_mixed_content(child)})
    return sections


def _parse_ack(ack):
    title = _find(ack, 'title')
    paragraphs = []
    for p in _findall_direct(ack, 'p'):
        paragraphs.append(_parse_mixed_content(p))
    return {
        'type': 'acknowledgment',
        'title': _parse_mixed_content(title) if title is not None else 'Acknowledgments',
        'paragraphs': paragraphs,
    }


def _parse_ref_list(ref_list, doc):
    title = _find(ref_list, 'title')
    refs = []
    for ref in _findall_direct(ref_list, 'ref'):
        refs.append(_parse_reference(ref))
    doc['_ref_count'] = len(refs)
    return {
        'type': 'references',
        'title': _parse_mixed_content(title) if title is not None else 'References',
        'references': refs,
    }


def _parse_reference(ref):
    ref_id = _attr(ref, 'id', '')
    citation = _find(ref, 'element-citation')
    if citation is None:
        citation = _find(ref, 'mixed-citation')
    if citation is not None:
        return {
            'id': ref_id,
            'type': _attr(citation, 'publication-type', '') if citation is not None else '',
            'content': _parse_mixed_content(citation),
            'text': _get_text(citation) if citation is not None else '',
        }
    return {'id': ref_id, 'content': _parse_mixed_content(ref), 'text': _get_text(ref)}


def _parse_fn_group(fn_group):
    fns = []
    for fn in _findall_direct(fn_group, 'fn'):
        fn_id = _attr(fn, 'id', '')
        paragraphs = []
        for p in _findall_direct(fn, 'p'):
            paragraphs.append(_parse_mixed_content(p))
        fns.append({'id': fn_id, 'content': paragraphs})
    return {'type': 'footnotes', 'footnotes': fns}


def _parse_bio(bio):
    title = _find(bio, 'title')
    paragraphs = []
    for p in _findall_direct(bio, 'p'):
        paragraphs.append(_parse_mixed_content(p))
    return {
        'type': 'bio',
        'title': _parse_mixed_content(title) if title is not None else '',
        'paragraphs': paragraphs,
    }


# ─── 混合内容解析（内联元素）──────────────────────────────────────

def _parse_mixed_content(elem):
    """解析混合内容（文本 + 内联元素），返回列表。"""
    if elem is None:
        return []
    result = []
    _parse_mixed_recursive(elem, result)
    return result


def _parse_mixed_recursive(elem, result):
    """递归解析混合内容元素。"""
    if elem is None:
        return

    # 元素前的文本
    if elem.text:
        result.append({'type': 'text', 'value': elem.text})

    for child in elem:
        tag = _tag(child)
        if tag == 'italic' or tag == 'i':
            result.append({'type': 'italic', 'content': _parse_mixed_content(child)})
        elif tag == 'bold' or tag == 'b':
            result.append({'type': 'bold', 'content': _parse_mixed_content(child)})
        elif tag == 'sup':
            result.append({'type': 'superscript', 'content': _parse_mixed_content(child)})
        elif tag == 'sub':
            result.append({'type': 'subscript', 'content': _parse_mixed_content(child)})
        elif tag == 'sc':
            result.append({'type': 'smallcaps', 'content': _parse_mixed_content(child)})
        elif tag == 'monospace':
            result.append({'type': 'monospace', 'content': _parse_mixed_content(child)})
        elif tag == 'underline':
            result.append({'type': 'underline', 'content': _parse_mixed_content(child)})
        elif tag == 'xref':
            result.append({
                'type': 'xref',
                'ref_type': _attr(child, 'ref-type', ''),
                'rid': _attr(child, 'rid', ''),
                'content': _parse_mixed_content(child),
            })
        elif tag == 'ext-link':
            result.append({
                'type': 'link',
                'href': _attr(child, 'href', ns='xlink') or _attr(child, 'href', ''),
                'ext_type': _attr(child, 'ext-link-type', ''),
                'content': _parse_mixed_content(child),
            })
        elif tag == 'inline-formula':
            math = _find(child, '{http://www.w3.org/1998/Math/MathML}math')
            if math is None:
                math = _find(child, 'math')
            result.append({
                'type': 'inline_formula',
                'mathml': etree.tostring(math, encoding='unicode') if math is not None else '',
            })
        elif tag == 'email':
            result.append({'type': 'email', 'value': _get_text(child)})
        elif tag == 'named-content':
            result.append({'type': 'named_content', 'content': _parse_mixed_content(child)})
        elif tag == 'break':
            result.append({'type': 'linebreak'})
        elif tag == 'disp-formula':
            math = _find(child, '{http://www.w3.org/1998/Math/MathML}math')
            if math is None:
                math = _find(child, 'math')
            result.append({
                'type': 'display_formula_inline',
                'mathml': etree.tostring(math, encoding='unicode') if math is not None else '',
            })
        elif tag == 'fn':
            result.append({'type': 'footnote_ref', 'id': _attr(child, 'id', ''),
                           'content': _parse_mixed_content(child)})
        elif tag == 'p':
            result.append({'type': 'paragraph_inline', 'content': _parse_mixed_content(child)})
        elif tag == 'graphic':
            href = _attr(child, 'href', ns='xlink') or _attr(child, 'href', '')
            result.append({'type': 'inline_graphic', 'href': href})
        else:
            # 递归处理未知元素
            _parse_mixed_recursive(child, result)

        # 处理子元素后的 tail 文本
        if child.tail:
            result.append({'type': 'text', 'value': child.tail})


def _render_inline_to_dict(elem):
    """将内联元素渲染为结构化的 mixed content 列表。"""
    return _parse_mixed_content(elem)


# ─── 工具函数：从解析后的数据获取便捷信息 ────────────────────────

def get_citation_info(doc):
    """生成前端显示的引用信息行。"""
    front = doc.get('front', {})
    journal = front.get('journal', {})
    parts = []

    abbrev = journal.get('abbrev', '')
    if abbrev:
        parts.append(abbrev)

    epub = front.get('pub_date_epub', {})
    if epub.get('year'):
        parts.append(epub['year'])

    vol = front.get('volume', '')
    issue = front.get('issue', '')
    eloc = front.get('elocation_id', '')
    vi = ''
    if vol:
        vi = vol
    if issue:
        vi += f'({issue})'
    if eloc and vol:
        vi += f': {eloc}'
    if vi:
        parts.append(vi)

    return '; '.join(parts) if parts else ''


def get_history_text(doc):
    """格式化 history 文本，返回单行字符串。"""
    front = doc.get('front', {})
    history = front.get('history', [])
    parts = []
    for entry in history:
        dtype = entry.get('type', '')
        disp = entry.get('display', '')
        if dtype == 'received':
            parts.append(f'Submitted: {disp}')
        elif dtype == 'rev-recd':
            parts.append(f'Revised: {disp}')
        elif dtype == 'accepted':
            parts.append(f'Accepted: {disp}')
    # 添加 Published 日期（从 epub 出版日期获取）
    epub = front.get('pub_date_epub', {})
    pub_display = epub.get('display', '')
    if pub_display:
        parts.append(f'Published: {pub_display}')
    return '&nbsp;&nbsp;&nbsp;'.join(parts) if parts else ''


if __name__ == '__main__':
    import json
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else '初始文件.xml'
    doc = parse_jats(path)
    # 只打印结构概要
    def print_structure(d, indent=0):
        if isinstance(d, dict):
            for k, v in d.items():
                if k.startswith('_'):
                    continue
                if isinstance(v, (list, dict)):
                    print('  ' * indent + f'{k}: ({type(v).__name__}) len={len(v) if isinstance(v, list) else "N/A"}')
                else:
                    val = str(v)[:80]
                    print('  ' * indent + f'{k}: {val}')
        elif isinstance(d, list):
            print('  ' * indent + f'[list] len={len(d)}')
    print_structure(doc)
    print(f"\nFigures: {doc['_figure_count']}, Tables: {doc['_table_count']}, Formulas: {doc['_formula_count']}")
    print(f"Body sections/children: {len(doc['body'])}")
    print(f"Back sections: {len(doc['back'])}")
