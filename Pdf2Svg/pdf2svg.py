# -*- coding: utf-8 -*-
"""
PDF 转 SVG 命令行工具（基于 PyMuPDF / fitz）

================================================================================
命令行使用示例
================================================================================

1) 将单个 PDF 全部页转为 SVG，输出到 ./out（目录不存在会自动创建）::

    python pdf2svg.py document.pdf -o ./out

2) 指定 DPI（默认 72；数值越大，矢量缩放/细节通常越清晰）::

    python pdf2svg.py document.pdf -o ./out --dpi 150

3) 只转换第 1、3、5 页（页码从 1 开始）::

    python pdf2svg.py document.pdf -o ./out --pages 1,3,5

4) 转换连续页码范围（含首尾）::

    python pdf2svg.py document.pdf -o ./out --pages 1-5

5) 混用范围与单页::

    python pdf2svg.py document.pdf -o ./out --pages 1-3,7,10-12

6) 批量处理多个 PDF::

    python pdf2svg.py a.pdf b.pdf c.pdf -o ./out

7) 文本保留为 <text>（文件更小；依赖查看器字体）::

    python pdf2svg.py doc.pdf -o ./out --no-text-as-path

8) 查看帮助::

    python pdf2svg.py -h

================================================================================
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
from tqdm import tqdm


def _dpi_to_matrix(dpi: float) -> fitz.Matrix:
    """将 DPI 转为缩放矩阵。PDF 用户空间默认 72 DPI，故 zoom = dpi / 72。"""
    if dpi <= 0:
        raise ValueError("DPI 必须为正数")
    zoom = dpi / 72.0
    return fitz.Matrix(zoom, zoom)


def parse_pages_arg(spec: str, page_count: int) -> list[int]:
    """
    解析 --pages 参数，返回 0-based 页索引列表（升序、去重）。

    支持:
    - all / * / 空: 全部页
    - 1,3,5: 指定页（1 起算）
    - 1-5: 闭区间范围
    - 混用: 1-3,5,7-9
    """
    s = (spec or "").strip()
    if not s or s.lower() in ("all", "*"):
        return list(range(page_count))

    indices: set[int] = set()
    for part in re.split(r"\s*,\s*", s):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start_p, end_p = int(a.strip()), int(b.strip())
            if start_p < 1 or end_p < start_p:
                raise ValueError(f"无效页范围: {part}")
            for p in range(start_p, end_p + 1):
                idx = p - 1
                if 0 <= idx < page_count:
                    indices.add(idx)
        else:
            p = int(part)
            if p < 1:
                raise ValueError(f"页码须 >= 1: {p}")
            idx = p - 1
            if idx < page_count:
                indices.add(idx)

    if not indices:
        raise ValueError("未解析到任何有效页码（可能全部超出文档页数）")
    return sorted(indices)


def ensure_dir(path: Path) -> None:
    """若输出目录不存在则递归创建。"""
    path.mkdir(parents=True, exist_ok=True)


def safe_stem(pdf_path: Path) -> str:
    """用于文件名的 PDF 基名（避免路径分隔符等问题）。"""
    stem = pdf_path.stem
    return re.sub(r'[<>:"/\\|?*]', "_", stem) or "output"


def convert_pdf_pages(
    pdf_path: Path,
    out_dir: Path,
    page_indices: Iterable[int],
    dpi: float,
    text_as_path: bool,
    pbar: tqdm | None,
) -> tuple[int, int]:
    """
    将指定页转为 SVG。

    返回 (成功页数, 失败页数)。
    """
    ok = 0
    fail = 0
    mat = _dpi_to_matrix(dpi)
    stem = safe_stem(pdf_path)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[错误] 无法打开 PDF: {pdf_path} — {e}", file=sys.stderr)
        return 0, 0

    try:
        for idx in page_indices:
            if idx < 0 or idx >= doc.page_count:
                print(
                    f"[跳过] {pdf_path.name} 页 {idx + 1} 超出范围 (共 {doc.page_count} 页)",
                    file=sys.stderr,
                )
                fail += 1
                if pbar:
                    pbar.update(1)
                continue
            page = doc.load_page(idx)
            out_name = f"{stem}_p{idx + 1:04d}.svg"
            out_path = out_dir / out_name
            try:
                svg_bytes = page.get_svg_image(
                    matrix=mat,
                    text_as_path=text_as_path,
                )
                if isinstance(svg_bytes, str):
                    data = svg_bytes.encode("utf-8")
                else:
                    data = svg_bytes
                out_path.write_bytes(data)
                ok += 1
            except Exception as e:
                print(
                    f"[错误] {pdf_path.name} 第 {idx + 1} 页: {e}",
                    file=sys.stderr,
                )
                fail += 1
            finally:
                if pbar:
                    pbar.update(1)
    finally:
        doc.close()

    return ok, fail


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="使用 PyMuPDF 将 PDF 转为 SVG（矢量优先），支持多文件、页码范围与 DPI。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "pdfs",
        nargs="+",
        metavar="PDF",
        type=str,
        help="一个或多个 PDF 文件路径",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        type=str,
        help="输出目录（不存在会自动创建）",
    )
    p.add_argument(
        "--pages",
        type=str,
        default="all",
        help='要转换的页: all 或 1,3,5 或 1-5 或 1-3,7 (默认: all)',
    )
    p.add_argument(
        "--dpi",
        type=float,
        default=72.0,
        help="输出缩放对应的 DPI（相对 PDF 默认 72；越大通常越清晰，默认 72）",
    )
    p.add_argument(
        "--no-text-as-path",
        action="store_true",
        help="不把文字转为路径，保留 SVG 文本（文件更小，需查看器有对应字体）",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    out_dir = Path(args.output).resolve()
    ensure_dir(out_dir)

    dpi = float(args.dpi)
    text_as_path = not args.no_text_as_path

    # 统计总任务数（用于进度条）
    jobs: list[tuple[Path, list[int]]] = []
    total_steps = 0
    for raw in args.pdfs:
        pdf_path = Path(raw).expanduser()
        if not pdf_path.is_file():
            print(f"[错误] 不是有效文件: {pdf_path}", file=sys.stderr)
            continue
        try:
            doc = fitz.open(pdf_path)
            n = doc.page_count
            doc.close()
        except Exception as e:
            print(f"[错误] 无法读取 PDF: {pdf_path} — {e}", file=sys.stderr)
            continue
        try:
            pages = parse_pages_arg(args.pages, n)
        except ValueError as e:
            print(f"[错误] {pdf_path.name} 页码参数: {e}", file=sys.stderr)
            continue
        jobs.append((pdf_path, pages))
        total_steps += len(pages)

    if not jobs:
        print("没有可处理的 PDF。", file=sys.stderr)
        return 1

    pbar = tqdm(
        total=total_steps,
        unit="页",
        desc="转换",
        ncols=80,
        disable=(total_steps == 0 or not sys.stdout.isatty()),
    )

    total_ok = total_fail = 0
    for pdf_path, pages in jobs:
        o, f = convert_pdf_pages(
            pdf_path,
            out_dir,
            pages,
            dpi=dpi,
            text_as_path=text_as_path,
            pbar=pbar,
        )
        total_ok += o
        total_fail += f

    if pbar:
        pbar.close()

    print(f"完成: 成功 {total_ok} 页, 失败 {total_fail} 页。输出目录: {out_dir}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
