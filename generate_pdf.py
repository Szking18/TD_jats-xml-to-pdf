#!/usr/bin/env python3
"""
JATS XML → PDF 智能排版引擎 — 主入口
用法: python generate_pdf.py <input.xml> [output.pdf] [options]

选项:
  --no-mathjax    跳过 MathML 渲染（快速预览模式）
  --debug         保留中间 HTML 文件
"""

import os
import sys
import argparse
import tempfile
import zipfile
import shutil
from weasyprint import HTML

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)

from jats_parser import parse_jats
from html_renderer import render_html

# 临时目录，用于存放解压的图片
_EXTRACT_DIRS = []


def _default_input_path():
    """返回默认的输入 XML 文件路径。"""
    candidates = [
        os.path.join(_SCRIPT_DIR, '初始文件.xml'),
        os.path.join(_SCRIPT_DIR, 'input.xml'),
        os.path.join(_SCRIPT_DIR, 'sample.xml'),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]


def _extract_zip_images(xml_dir):
    """解压 XML 目录下的所有 ZIP 文件中的图片到临时目录（保留目录结构）。"""
    import re
    extract_paths = []

    for fname in os.listdir(xml_dir):
        if fname.lower().endswith('.zip'):
            zip_path = os.path.join(xml_dir, fname)
            try:
                tmpdir = tempfile.mkdtemp(prefix='jats_imgs_')
                _EXTRACT_DIRS.append(tmpdir)

                with zipfile.ZipFile(zip_path, 'r') as zf:
                    img_exts = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.svg', '.webp'}
                    for member in zf.namelist():
                        ext = os.path.splitext(member)[1].lower()
                        if ext in img_exts:
                            # 保留 ZIP 内的目录结构
                            target_path = os.path.join(tmpdir, member)
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            # 避免覆盖
                            if os.path.exists(target_path):
                                base, e = os.path.splitext(target_path)
                                counter = 1
                                while os.path.exists(f"{base}_{counter}{e}"):
                                    counter += 1
                                target_path = f"{base}_{counter}{e}"
                            with zf.open(member) as src:
                                with open(target_path, 'wb') as dst:
                                    shutil.copyfileobj(src, dst)
                extract_paths.append(tmpdir)
                print(f"       Extracted images from: {fname}")
            except Exception as e:
                print(f"       [WARN] Could not extract {fname}: {e}")

    return extract_paths


def _cleanup():
    """清理临时目录。"""
    for d in _EXTRACT_DIRS:
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


def _resolve_image(href, xml_dir, extract_dirs):
    """智能解析图片路径，支持多种命名约定。"""
    import re
    if not href:
        return ''

    basename = os.path.basename(href)

    # === 策略1: 精确路径匹配 ===
    candidates = [
        os.path.join(xml_dir, href),       # XML目录下的相对路径
        os.path.join(xml_dir, basename),   # XML目录下的文件名
    ]
    for ed in extract_dirs:
        candidates.append(os.path.join(ed, href))       # 解压目录下的相对路径
        candidates.append(os.path.join(ed, basename))   # 解压目录下的文件名

    for c in candidates:
        if os.path.exists(c):
            return c

    # === 策略2: 递归搜索 basename ===
    for search_dir in [xml_dir] + extract_dirs:
        for root, dirs, files in os.walk(search_dir):
            if basename in files:
                return os.path.join(root, basename)

    # === 策略3: 模糊匹配数字格式（fig-01.jpg ↔ fig1.jpg, figure1.jpg ↔ fig1.jpg 等）===
    basename_noext, ext = os.path.splitext(basename)
    num_match = re.search(r'(\d+)$', basename_noext)
    if num_match:
        num_str = num_match.group(1)
        num = int(num_str)
        prefix = basename_noext[:num_match.start()].rstrip('-_ .')
        # 生成同前缀不同数字格式的变体
        alt_names = []
        for fmt in [f'{num}', f'{num:02d}', f'{num:03d}', f'{num:04d}']:
            for sep in ['', '-', '_', ' ']:
                alt_names.append(f'{prefix}{sep}{fmt}{ext}')
        # 也尝试常见 figure 前缀变化
        if prefix.lower() in ('fig', 'figure'):
            for fig_prefix in ['fig', 'Fig', 'figure', 'Figure']:
                if fig_prefix != prefix:
                    for fmt in [f'{num}', f'{num:02d}', f'{num:03d}', f'{num:04d}']:
                        for sep in ['', '-', '_', ' ']:
                            alt_names.append(f'{fig_prefix}{sep}{fmt}{ext}')

        for search_dir in [xml_dir] + extract_dirs:
            for root, dirs, files in os.walk(search_dir):
                for f in files:
                    if f.lower() in [a.lower() for a in alt_names]:
                        return os.path.join(root, f)

    return href


def _fix_image_paths(doc, xml_dir, extract_dirs):
    """修复文档中所有图片路径（在 HTML 渲染前调用）。"""

    def walk_and_fix(node):
        if isinstance(node, dict):
            # 图片/figure
            if node.get('type') in ('figure', 'inline_graphic') and node.get('img_path'):
                node['img_path'] = _resolve_image(node['img_path'], xml_dir, extract_dirs)
            # inline_graphic with href
            if node.get('type') == 'inline_graphic' and node.get('href'):
                node['img_path'] = _resolve_image(node['href'], xml_dir, extract_dirs)
            for key, value in node.items():
                walk_and_fix(value)
        elif isinstance(node, list):
            for item in node:
                walk_and_fix(item)

    walk_and_fix(doc)


def generate_pdf(xml_path, pdf_path, use_mathjax=True, debug=False):
    """主流程：JATS XML → PDF"""
    xml_path = os.path.abspath(xml_path)
    xml_dir = os.path.dirname(xml_path)

    # 解压 ZIP 中的图片
    print(f"[0/3] Extracting images from ZIP archives...")
    extract_dirs = _extract_zip_images(xml_dir)

    print(f"[1/3] Parsing JATS XML: {os.path.basename(xml_path)}")
    doc = parse_jats(xml_path)
    print(f"       Title: {doc.get('front', {}).get('title_text', 'N/A')[:80]}")
    print(f"       Authors: {len(doc.get('front', {}).get('authors', []))}")
    print(f"       Body sections: {len(doc.get('body', []))}")
    print(f"       References: {doc.get('_ref_count', 0)}")

    # 修复图片路径
    _fix_image_paths(doc, xml_dir, extract_dirs)

    # MathML 渲染
    if use_mathjax:
        print("[2/3] Rendering MathML formulas...")
        from mathml_renderer import render_all_mathml
        doc = render_all_mathml(doc)
    else:
        print("[2/3] Skipping MathML rendering (--no-mathjax)")

    # HTML 生成
    print("[3/3] Generating HTML and PDF...")
    html_content = render_html(doc)

    if debug:
        html_path = os.path.join(os.path.dirname(pdf_path),
                                 os.path.basename(xml_path).replace('.xml', '_debug.html'))
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"       Debug HTML: {html_path} ({len(html_content):,} chars)")

    # PDF 生成（base_url 设为 XML 目录以便相对路径引用）
    HTML(string=html_content, base_url=xml_dir).write_pdf(pdf_path)
    size_kb = os.path.getsize(pdf_path) / 1024
    print(f"       PDF generated: {pdf_path} ({size_kb:.1f} KB)")
    print("Done!")

    # 清理临时文件
    _cleanup()


def main():
    parser = argparse.ArgumentParser(
        description='JATS XML → PDF 智能排版引擎',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python generate_pdf.py 初始文件.xml
  python generate_pdf.py input.xml output.pdf
  python generate_pdf.py input.xml --no-mathjax --debug
        """
    )
    parser.add_argument('input', nargs='?', default=None,
                        help='输入的 JATS XML 文件路径 (可选，默认查找初始文件.xml / input.xml / sample.xml)')
    parser.add_argument('output', nargs='?', default=None,
                        help='输出 PDF 文件路径 (默认: 与输入同名的 .pdf)')
    parser.add_argument('--no-mathjax', action='store_true',
                        help='跳过 MathML → SVG 渲染')
    parser.add_argument('--debug', action='store_true',
                        help='保留中间 HTML 文件')
    args = parser.parse_args()

    input_path = args.input or _default_input_path()
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        sys.exit(1)

    if args.output is None:
        base = os.path.splitext(input_path)[0]
        args.output = base + '.pdf'

    out_dir = os.path.dirname(os.path.abspath(args.output)) or '.'
    os.makedirs(out_dir, exist_ok=True)

    generate_pdf(
        input_path,
        args.output,
        use_mathjax=not args.no_mathjax,
        debug=args.debug,
    )


if __name__ == '__main__':
    main()
