# -*- coding: utf-8 -*-
"""
video2gif.py — 基于 MoviePy + Pillow 的视频转 GIF 命令行工具。

支持：常见视频格式、时间截取、尺寸缩放、帧率、颜色数量优化、批量转换、进度条（tqdm）。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# MoviePy 2.x：请使用 from moviepy import ...，不再提供 moviepy.editor 模块
from moviepy import VideoFileClip
from PIL import Image
from tqdm import tqdm


def parse_time_seconds(s: Optional[str]) -> Optional[float]:
    """将「秒」或「时:分:秒」字符串解析为秒数；None 或空串返回 None。"""
    if s is None or str(s).strip() == "":
        return None
    s = str(s).strip()
    if ":" in s:
        parts = s.split(":")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            raise argparse.ArgumentTypeError(f"无法解析时间: {s}")
        if len(nums) == 3:
            h, m, sec = nums
            return h * 3600 + m * 60 + sec
        if len(nums) == 2:
            m, sec = nums
            return m * 60 + sec
        raise argparse.ArgumentTypeError(f"时间格式应为 SS、MM:SS 或 HH:MM:SS: {s}")
    try:
        return float(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"无法解析时间: {s}")


def apply_subclip(
    clip: VideoFileClip,
    start: Optional[float],
    end: Optional[float],
    duration: Optional[float],
) -> VideoFileClip:
    """按开始/结束时间或持续时间截取片段。"""
    dur = float(clip.duration)
    t0 = start if start is not None else 0.0
    if t0 < 0:
        t0 = 0.0
    if t0 > dur:
        t0 = dur

    if duration is not None:
        if duration <= 0:
            raise ValueError("持续时间必须大于 0")
        t1 = min(t0 + duration, dur)
    elif end is not None:
        if end <= t0:
            raise ValueError("结束时间必须大于开始时间")
        t1 = min(end, dur)
    else:
        t1 = dur

    if t1 <= t0:
        raise ValueError("截取结果长度为 0，请检查开始/结束/持续时间")
    return clip.subclipped(t0, t1)


def apply_resize(
    clip: VideoFileClip,
    scale: Optional[float],
    width: Optional[int],
    height: Optional[int],
) -> VideoFileClip:
    """按比例或指定宽高缩放（仅宽或仅高时保持宽高比）；MoviePy 2 使用 resized()。"""
    if scale is not None:
        if scale <= 0:
            raise ValueError("缩放比例必须大于 0")
        return clip.resized(new_size=scale)
    if width is not None and height is not None:
        if width < 1 or height < 1:
            raise ValueError("宽高必须为正整数")
        return clip.resized(new_size=(width, height))
    if width is not None:
        if width < 1:
            raise ValueError("宽度必须为正整数")
        return clip.resized(width=width)
    if height is not None:
        if height < 1:
            raise ValueError("高度必须为正整数")
        return clip.resized(height=height)
    return clip


def apply_fps(clip: VideoFileClip, fps: Optional[float]) -> VideoFileClip:
    """设置输出帧率；None 表示沿用截取后片段的原始 fps（若无法取得则用 10）。"""
    if fps is None:
        return clip
    if fps <= 0:
        raise ValueError("帧率必须大于 0")
    return clip.with_fps(fps)


def get_effective_fps(clip: VideoFileClip, fps: Optional[float]) -> float:
    """用于写 GIF 的实际帧率。"""
    if fps is not None:
        return float(fps)
    try:
        f = float(clip.fps)
        if f > 0:
            return f
    except Exception:
        pass
    return 10.0


def write_gif_pillow(
    clip: VideoFileClip,
    outfile: str,
    fps: float,
    colors: int,
    show_progress: bool,
) -> None:
    """
    将视频片段逐帧写出为 GIF；使用 Pillow 量化以控制颜色数、减小体积。
    首帧生成调色板，后续帧复用同一调色板，利于动画 GIF 压缩。
    """
    colors = max(2, min(256, int(colors)))
    duration_ms = max(1, int(round(1000.0 / fps)))
    # 预估帧数（iter_frames 按 fps 采样，最后一帧可能略少）
    est = max(1, int(float(clip.duration) * fps + 0.5))
    gen = clip.iter_frames(fps=fps, dtype="uint8")
    it: Iterable = tqdm(gen, total=est, desc="写入 GIF", unit="帧") if show_progress else gen

    pil_frames: List[Image.Image] = []
    palette_ref: Optional[Image.Image] = None

    for frame in it:
        im = Image.fromarray(frame).convert("RGB")
        if palette_ref is None:
            palette_ref = im.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
            pil_frames.append(palette_ref)
        else:
            pil_frames.append(im.quantize(palette=palette_ref))

    if not pil_frames:
        raise RuntimeError("未生成任何帧，请检查视频与参数")

    out_path = Path(outfile)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if len(pil_frames) == 1:
        pil_frames[0].save(str(out_path), loop=0, optimize=True)
    else:
        pil_frames[0].save(
            str(out_path),
            save_all=True,
            append_images=pil_frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True,
        )


def convert_one(
    input_path: str,
    output_path: str,
    start: Optional[float],
    end: Optional[float],
    duration: Optional[float],
    scale: Optional[float],
    width: Optional[int],
    height: Optional[int],
    fps: Optional[float],
    colors: int,
    show_progress: bool,
) -> None:
    """转换单个视频文件为 GIF。"""
    clip = VideoFileClip(input_path)
    try:
        clip = apply_subclip(clip, start, end, duration)
        clip = apply_resize(clip, scale, width, height)
        clip = apply_fps(clip, fps)
        eff_fps = get_effective_fps(clip, fps)
        write_gif_pillow(clip, output_path, eff_fps, colors, show_progress)
    finally:
        clip.close()


def default_output_path(input_file: str, output: Optional[str], batch: bool) -> str:
    """根据输入与 -o 推导输出路径。"""
    stem = Path(input_file).stem
    if output is None:
        return str(Path(input_file).with_suffix(".gif"))
    p = Path(output)
    if batch or p.is_dir() or str(output).endswith(os.sep) or str(output).endswith("/"):
        p = Path(output) if not str(output).endswith(os.sep) else Path(output[:-1])
        p.mkdir(parents=True, exist_ok=True)
        return str(p / f"{stem}.gif")
    if len(Path(output).suffix) == 0 and not Path(output).exists():
        # 用户可能想表示目录
        p.mkdir(parents=True, exist_ok=True)
        return str(p / f"{stem}.gif")
    return output


def collect_inputs(paths: List[str]) -> List[str]:
    """展开输入路径列表（文件直接加入，目录内常见视频后缀）。"""
    exts = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".flv", ".m4v"}
    result: List[str] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            result.append(str(path.resolve()))
        elif path.is_dir():
            for f in sorted(path.iterdir()):
                if f.suffix.lower() in exts:
                    result.append(str(f.resolve()))
        else:
            raise FileNotFoundError(f"找不到输入: {p}")
    return result


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="将视频（MP4/AVI/MOV 等）转为 GIF，支持截取、缩放、帧率、颜色数与批量处理。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令行使用示例（Windows PowerShell / cmd 均可）：

  1) 基本转换（输出与视频同目录、同名 .gif）
     python video2gif.py  demo.mp4

  2) 指定输出文件
     python video2gif.py  demo.mp4  -o  out.gif

  3) 从第 5 秒截取到第 12 秒
     python video2gif.py  demo.mp4  -o clip.gif  --start 5  --end 12

  4) 从 1 分 10 秒起持续 8 秒（时间支持 时:分:秒）
     python video2gif.py  demo.mp4  --start 1:10  --duration 8  -o part.gif

  5) 缩放为宽度 320（高度按比例）
     python video2gif.py  demo.mp4  --width 320  -o small.gif

  6) 整体缩放为 50%%，输出帧率 12，颜色 128 以减小文件
     python video2gif.py  demo.mp4  --scale 0.5  --fps 12  --colors 128  -o lite.gif

  7) 批量：多个文件输出到同一目录（自动生成 文件名.gif）
     python video2gif.py  a.mp4  b.mov  -o  ./gifs/

  8) 批量：整个目录下所有支持的视频
     python video2gif.py  ./videos/  -o  ./gifs/

  9) 安静模式（不显示 tqdm 进度条）
     python video2gif.py  demo.mp4  -o out.gif  --no-progress
""",
    )
    p.add_argument(
        "inputs",
        nargs="+",
        help="输入视频文件，或多个文件/目录（目录内按扩展名筛选常见视频）",
    )
    p.add_argument("-o", "--output", default=None, help="输出 GIF 路径，或批量时的输出目录")
    p.add_argument("--start", type=parse_time_seconds, default=None, help="开始时间（秒或 MM:SS / HH:MM:SS）")
    p.add_argument("--end", type=parse_time_seconds, default=None, help="结束时间（与 --duration 二选一）")
    p.add_argument("--duration", type=parse_time_seconds, default=None, help="持续时间（秒），与 --end 二选一")
    p.add_argument("--scale", type=float, default=None, help="整体缩放比例，如 0.5 表示一半尺寸")
    p.add_argument("--width", type=int, default=None, help="目标宽度（像素），与 --height 可只给其一以保持比例")
    p.add_argument("--height", type=int, default=None, help="目标高度（像素）")
    p.add_argument("--fps", type=float, default=None, help="输出 GIF 帧率；默认与源视频一致（无法读取则用 10）")
    p.add_argument(
        "--colors",
        type=int,
        default=256,
        help="GIF 调色板颜色数量（2–256），越小通常文件越小，默认 256",
    )
    p.add_argument("--no-progress", action="store_true", help="关闭 tqdm 进度条")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)
    try:
        input_list = collect_inputs(args.inputs)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 1
    if not input_list:
        print("未找到任何可转换的视频文件。", file=sys.stderr)
        return 1

    batch = len(input_list) > 1
    if batch and args.output and Path(args.output).suffix.lower() == ".gif":
        print("批量转换时 -o 请指定目录，而不是单个 .gif 文件。", file=sys.stderr)
        return 1

    show_progress = not args.no_progress
    errors = 0
    for inp in input_list:
        out = default_output_path(inp, args.output, batch or Path(inp).is_dir())
        try:
            convert_one(
                inp,
                out,
                args.start,
                args.end,
                args.duration,
                args.scale,
                args.width,
                args.height,
                args.fps,
                args.colors,
                show_progress,
            )
            print(f"完成: {inp} -> {out}")
        except Exception as e:
            errors += 1
            print(f"失败 [{inp}]: {e}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
