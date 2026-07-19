#!/usr/bin/env python3
"""
批量测试脚本 — 自动发现所有 初始文件.xml 并生成 PDF
"""
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'output')

sys.path.insert(0, SCRIPT_DIR)
from generate_pdf import generate_pdf


def _find_samples(base_dir):
    samples = []
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            if f == '初始文件.xml':
                if root == base_dir:
                    continue  # skip root-level XML
                rel = os.path.relpath(root, base_dir)
                label = rel.replace(os.sep, '_').replace(' ', '_')
                pdf_path = os.path.join(OUTPUT_DIR, f'{label}.pdf')
                samples.append((label, os.path.join(root, f), pdf_path))
    return sorted(samples, key=lambda x: x[0])


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    samples = _find_samples(SCRIPT_DIR)
    if not samples:
        print("Error: No XML files found.")
        return

    results = []
    for label, xml_path, pdf_path in samples:
        print(f"\n{'='*60}")
        print(f"Processing: {label}")
        print(f"{'='*60}")
        start = time.time()
        try:
            generate_pdf(xml_path, pdf_path, use_mathjax=True, debug=False)
            elapsed = time.time() - start
            results.append((label, 'OK', elapsed, pdf_path))
        except Exception as e:
            elapsed = time.time() - start
            results.append((label, f'FAILED: {e}', elapsed, pdf_path))
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"{'='*60}")
    for label, status, elapsed, path in results:
        icon = 'OK' if status == 'OK' else 'FAIL'
        print(f"  {label}: {icon} ({elapsed:.1f}s) -> {path}")


if __name__ == '__main__':
    main()
