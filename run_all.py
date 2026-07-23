#!/usr/bin/env python3
"""
批量测试脚本 — 对所有5个样例生成 PDF
"""
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_BASE = r'C:\Users\szp12\Desktop\学术期刊创新大赛\样例-最新版(已修复)\样例-最新版'
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'sample_output')

sys.path.insert(0, SCRIPT_DIR)
from generate_pdf import generate_pdf


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    samples = []
    for i in range(1, 6):
        sample_dir = os.path.join(SAMPLE_BASE, f'样例{i}', '第二组')
        xml_path = os.path.join(sample_dir, '初始文件.xml')
        if os.path.exists(xml_path):
            pdf_path = os.path.join(OUTPUT_DIR, f'样例{i}_output.pdf')
            samples.append((i, xml_path, pdf_path))
        else:
            print(f"Warning: Sample {i} not found at {xml_path}")

    results = []
    for num, xml_path, pdf_path in samples:
        print(f"\n{'='*60}")
        print(f"Processing Sample {num}: {os.path.basename(xml_path)}")
        print(f"{'='*60}")
        start = time.time()
        try:
            generate_pdf(xml_path, pdf_path, use_mathjax=True, debug=False)
            elapsed = time.time() - start
            results.append((num, 'OK', elapsed, pdf_path))
        except Exception as e:
            elapsed = time.time() - start
            results.append((num, f'FAILED: {e}', elapsed, pdf_path))
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("Summary:")
    print(f"{'='*60}")
    for num, status, elapsed, path in results:
        status_icon = '✅' if status == 'OK' else '❌'
        print(f"  Sample {num}: {status_icon} {status} ({elapsed:.1f}s) → {path}")


if __name__ == '__main__':
    main()
