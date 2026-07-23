"""
MathML → SVG 渲染模块
通过调用 Node.js + MathJax 将 MathML 转换为 SVG。
支持缓存机制避免重复渲染。
"""

import hashlib
import os
import subprocess
import json
import shutil
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 查找 Node.js 可执行文件
def _find_node():
    """查找 Node.js 可执行文件路径。"""
    # 先尝试 shutil.which
    node = shutil.which('node')
    if node:
        return node

    # 尝试常见路径
    candidates = [
        r'C:\Program Files\nodejs\node.exe',
        r'C:\Program Files (x86)\nodejs\node.exe',
        '/usr/local/bin/node',
        '/usr/bin/node',
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    # 最后尝试 node
    return 'node'

_NODE_PATH = _find_node()

# 缓存目录
CACHE_DIR = os.path.join(_SCRIPT_DIR, '.mathml_cache')
os.makedirs(CACHE_DIR, exist_ok=True)


def render_mathml(mathml_str, display=False):
    """将 MathML 字符串渲染为 SVG。

    Args:
        mathml_str: MathML XML 字符串
        display: True=块级公式, False=内联公式

    Returns:
        SVG 字符串
    """
    if not mathml_str or not mathml_str.strip():
        return ''

    # 检查缓存
    cache_key = hashlib.md5((mathml_str + str(display)).encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f'{cache_key}.svg')
    if os.path.exists(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return f.read()

    # 调用 Node.js 渲染
    js_path = os.path.join(_SCRIPT_DIR, 'mathjax_render.js')
    mode = 'display' if display else 'inline'

    try:
        result = subprocess.run(
            [_NODE_PATH, js_path, mode],
            input=mathml_str,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30,
            cwd=_SCRIPT_DIR,
        )
        svg = result.stdout.strip()

        # 检查是否成功（输出包含 <svg> 标签）
        if '<svg' in svg:
            # 缓存结果
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(svg)
            return svg
        else:
            # 渲染失败，返回降级 HTML 表示
            stderr = result.stderr.strip()
            if stderr:
                print(f"  [WARN] MathJax render failed: {stderr[:100]}")
            return _fallback_html(mathml_str, display)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  [WARN] MathJax subprocess error: {e}")
        return _fallback_html(mathml_str, display)


def render_all_mathml(doc_data):
    """遍历文档数据，渲染所有 MathML 公式。

    Args:
        doc_data: 解析后的文档数据字典

    Returns:
        更新后的 doc_data，公式被替换为 SVG
    """
    formula_count = 0

    def walk_and_render(node, parent_key=None):
        nonlocal formula_count
        if isinstance(node, dict):
            # 处理 MathML
            if 'mathml' in node and node['mathml']:
                display = 'display' in node.get('type', '')
                svg = render_mathml(node['mathml'], display=display)
                node['svg'] = svg
                formula_count += 1

            for key, value in node.items():
                walk_and_render(value, key)

        elif isinstance(node, list):
            for item in node:
                walk_and_render(item)

    walk_and_render(doc_data)
    print(f"  Rendered {formula_count} MathML formulas to SVG")
    return doc_data


def _fallback_html(mathml_str, display=False):
    """当 MathJax 渲染失败时的降级 HTML 渲染。"""
    # 简单的 MathML → HTML 转换，支持带命名空间前缀和无前缀标签。
    import re
    html = mathml_str
    html = re.sub(r'<(?:mml:)?mi[^>]*>([^<]*)</(?:mml:)?mi>', r'<i>\1</i>', html)
    html = re.sub(r'<(?:mml:)?mo[^>]*>([^<]*)</(?:mml:)?mo>', r'\1', html)
    html = re.sub(r'<(?:mml:)?mn[^>]*>([^<]*)</(?:mml:)?mn>', r'\1', html)
    html = re.sub(r'<(?:mml:)?msub[^>]*>.*?</(?:mml:)?msub>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(?:mml:)?msup[^>]*>.*?</(?:mml:)?msup>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(?:mml:)?mfrac[^>]*>.*?</(?:mml:)?mfrac>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(?:mml:)?munder[^>]*>.*?</(?:mml:)?munder>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(?:mml:)?mover[^>]*>.*?</(?:mml:)?mover>', '', html, flags=re.DOTALL)
    html = re.sub(r'<(?:mml:)?munderover[^>]*>.*?</(?:mml:)?munderover>', '', html, flags=re.DOTALL)
    html = re.sub(r'</?(?:mml:)?(?:math|semantics|mrow|mfrac|msub|msup|munder|mover|munderover|mtext|mpadded|mfenced|msqrt|mroot)[^>]*>', '', html)
    html = re.sub(r'</?(?:mml:)?\w+[^>]*>', '', html)

    if display:
        return f'<div class="formula-fallback">{html.strip()}</div>'
    else:
        return f'<span class="formula-fallback">{html.strip()}</span>'


# ─── 批量渲染脚本 ────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    from jats_parser import parse_jats

    xml_path = sys.argv[1] if len(sys.argv) > 1 else '初始文件.xml'
    print(f"Parsing: {xml_path}")
    doc = parse_jats(xml_path)
    print(f"Rendering MathML formulas...")
    doc = render_all_mathml(doc)
    print(f"Done.")
