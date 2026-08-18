# -*- coding: utf-8 -*-
"""生成程序图标 assets/icon.ico（文件夹 + 下载箭头主题，多尺寸）。

用法：
    python tools/make_icon.py

生成多尺寸 ICO（16/24/32/48/64/128/256），供：
  * exe 图标（PyInstaller --icon）
  * 系统托盘图标（tray.py 加载）
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"

SIZES = (16, 24, 32, 48, 64, 128, 256)


def draw_icon(size: int) -> Image.Image:
    """绘制单个尺寸的图标：蓝色圆角底 + 黄色文件夹 + 白色下载箭头。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256.0  # 缩放因子，基于 256 设计稿

    def R(x0, y0, x1, y1, r, fill):
        d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=r * s, fill=fill)

    # 蓝色圆角背景
    R(8, 8, 248, 248, 56, (52, 120, 246, 255))

    # 文件夹（黄色）
    R(44, 84, 212, 176, 14, (255, 200, 60, 255))          # 文件夹主体
    R(44, 84, 120, 104, 8, (255, 216, 90, 255))           # 文件夹标签

    # 白色下载箭头（在文件夹上）
    d.rectangle([118 * s, 88 * s, 138 * s, 136 * s], fill=(255, 255, 255, 255))  # 竖杆
    d.polygon([
        (100 * s, 132 * s), (156 * s, 132 * s),
        (128 * s, 162 * s),
    ], fill=(255, 255, 255, 255))                          # 箭头
    d.rectangle([96 * s, 140 * s, 160 * s, 152 * s], fill=(255, 255, 255, 255))  # 箭头底

    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 以 256 大图 + sizes 参数生成多尺寸 ICO（Pillow 自动缩放各尺寸）
    img = draw_icon(256)
    img.save(
        OUT, format="ICO", sizes=[(s, s) for s in SIZES],
    )
    print(f"已生成 {OUT} ({len(SIZES)} 个尺寸)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
