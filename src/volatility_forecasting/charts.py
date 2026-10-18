"""Dependency-free SVG and PNG line charts for reproducible study figures."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path
from typing import Sequence


WIDTH, HEIGHT = 1100, 620
LEFT, RIGHT, TOP, BOTTOM = 86, 34, 68, 72
COLORS = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#d97706", "#0891b2"]
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    " ": ("00000",) * 7,
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
}


def _limits(series: Sequence[tuple[str, Sequence[float | None]]]) -> tuple[float, float]:
    values = [v for _, points in series for v in points if v is not None and math.isfinite(v)]
    if not values:
        return 0.0, 1.0
    low, high = min(values), max(values)
    padding = (high - low) * 0.08 or max(abs(low) * 0.08, 0.01)
    return low - padding, high + padding


def _xy(index: int, value: float, count: int, low: float, high: float) -> tuple[float, float]:
    x = LEFT + index * (WIDTH - LEFT - RIGHT) / max(count - 1, 1)
    y = TOP + (high - value) * (HEIGHT - TOP - BOTTOM) / (high - low)
    return x, y


def _png(path: Path, title: str, series: Sequence[tuple[str, Sequence[float | None]]],
         x_label: str, low: float, high: float, subtitle: str) -> None:
    pixels = bytearray([255, 255, 255] * WIDTH * HEIGHT)

    def dot(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            offset = (y * WIDTH + x) * 3
            pixels[offset : offset + 3] = bytes(color)

    def line(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            dot(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * error
            if twice >= dy:
                error += dy
                x0 += sx
            if twice <= dx:
                error += dx
                y0 += sy

    def text(x: int, y: int, value: str, scale: int = 1) -> None:
        cursor = x
        for character in value.upper():
            glyph = FONT.get(character, FONT[" "])
            for row, pattern in enumerate(glyph):
                for column, bit in enumerate(pattern):
                    if bit == "1":
                        for dy in range(scale):
                            for dx in range(scale):
                                dot(cursor + column * scale + dx, y + row * scale + dy, (51, 65, 85))
            cursor += 6 * scale

    grid = (226, 232, 240)
    for step in range(6):
        y = int(TOP + step * (HEIGHT - TOP - BOTTOM) / 5)
        line(LEFT, y, WIDTH - RIGHT, y, grid)
        label = f"{high - step * (high - low) / 5:.3g}"
        text(LEFT - 8 - len(label) * 6, y - 3, label)
    line(LEFT, TOP, LEFT, HEIGHT - BOTTOM, (71, 85, 105))
    line(LEFT, HEIGHT - BOTTOM, WIDTH - RIGHT, HEIGHT - BOTTOM, (71, 85, 105))
    rgb = [(37, 99, 235), (220, 38, 38), (22, 163, 74), (147, 51, 234), (217, 119, 6), (8, 145, 178)]
    for series_index, (_, values) in enumerate(series):
        prior: tuple[int, int] | None = None
        color = rgb[series_index % len(rgb)]
        for i, value in enumerate(values):
            if value is None or not math.isfinite(value):
                prior = None
                continue
            x, y = _xy(i, value, len(values), low, high)
            point = (round(x), round(y))
            if prior is not None:
                line(*prior, *point, color)
            prior = point
    text(LEFT, 7, title, 2)
    text(LEFT, 32, subtitle)
    columns = min(3, max(len(series), 1))
    for index, (label, _) in enumerate(series):
        column, row = index % columns, index // columns
        legend_x = LEFT + column * ((WIDTH - LEFT - RIGHT) // columns)
        legend_y = HEIGHT - BOTTOM + 14 + row * 18
        line(legend_x, legend_y + 5, legend_x + 22, legend_y + 5, rgb[index % len(rgb)])
        text(legend_x + 28, legend_y, label)
    text((WIDTH - len(x_label) * 6) // 2, HEIGHT - 16, x_label)
    raw = b"".join(b"\0" + bytes(pixels[row * WIDTH * 3 : (row + 1) * WIDTH * 3]) for row in range(HEIGHT))

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">2I5B", WIDTH, HEIGHT, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def write_chart(
    directory: Path,
    stem: str,
    title: str,
    series: Sequence[tuple[str, Sequence[float | None]]],
    x_label: str,
    y_label: str,
    subtitle: str = "",
) -> None:
    """Write the same white-background chart to SVG and RGB PNG."""
    directory.mkdir(parents=True, exist_ok=True)
    low, high = _limits(series)
    count = max((len(points) for _, points in series), default=0)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{LEFT}" y="25" font-family="Arial,sans-serif" font-size="20" font-weight="bold" fill="#0f172a">{title}</text>',
        f'<text x="{LEFT}" y="50" font-family="Arial,sans-serif" font-size="12" fill="#475569">{subtitle}</text>',
    ]
    for step in range(6):
        y = TOP + step * (HEIGHT - TOP - BOTTOM) / 5
        value = high - step * (high - low) / 5
        svg.append(f'<line x1="{LEFT}" y1="{y:.1f}" x2="{WIDTH-RIGHT}" y2="{y:.1f}" stroke="#e2e8f0"/>')
        svg.append(f'<text x="{LEFT-10}" y="{y+4:.1f}" text-anchor="end" font-family="Arial" font-size="12" fill="#475569">{value:.3g}</text>')
    svg.extend([
        f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" y2="{HEIGHT-BOTTOM}" stroke="#475569"/>',
        f'<line x1="{LEFT}" y1="{HEIGHT-BOTTOM}" x2="{WIDTH-RIGHT}" y2="{HEIGHT-BOTTOM}" stroke="#475569"/>',
        f'<text x="{(LEFT+WIDTH-RIGHT)/2}" y="{HEIGHT-15}" text-anchor="middle" font-family="Arial" font-size="13" fill="#334155">{x_label}</text>',
        f'<text x="18" y="{HEIGHT/2}" transform="rotate(-90 18 {HEIGHT/2})" text-anchor="middle" font-family="Arial" font-size="13" fill="#334155">{y_label}</text>',
    ])
    for series_index, (label, values) in enumerate(series):
        color = COLORS[series_index % len(COLORS)]
        segment: list[str] = []
        for i, value in enumerate(values):
            if value is None or not math.isfinite(value):
                if segment:
                    svg.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')
                    segment = []
                continue
            x, y = _xy(i, value, len(values), low, high)
            segment.append(f"{x:.1f},{y:.1f}")
        if segment:
            svg.append(f'<polyline points="{" ".join(segment)}" fill="none" stroke="{color}" stroke-width="2"/>')
        columns = min(3, max(len(series), 1))
        column, row = series_index % columns, series_index // columns
        lx = LEFT + column * ((WIDTH - LEFT - RIGHT) // columns)
        ly = HEIGHT - BOTTOM + 14 + row * 18
        svg.extend([
            f'<line x1="{lx}" y1="{ly}" x2="{lx+25}" y2="{ly}" stroke="{color}" stroke-width="3"/>',
            f'<text x="{lx+31}" y="{ly+4}" font-family="Arial" font-size="12" fill="#334155">{label}</text>',
        ])
    svg.append("</svg>")
    (directory / f"{stem}.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    _png(directory / f"{stem}.png", title, series, x_label, low, high, subtitle)
