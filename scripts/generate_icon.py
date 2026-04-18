from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
PNG_PATH = ASSETS_DIR / "palworld-trainer-icon.png"
ICO_PATH = ASSETS_DIR / "palworld-trainer.ico"


def clamp01(value: float) -> float:
    if value <= 0.0:
        return 0.0
    if value >= 1.0:
        return 1.0
    return value


def smooth_step(edge0: float, edge1: float, value: float) -> float:
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0
    t = clamp01((value - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b, strict=True))


def over(dst: tuple[int, int, int, int], src: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    sr, sg, sb, sa = src
    if sa <= 0:
        return dst
    dr, dg, db, da = dst
    src_a = sa / 255.0
    dst_a = da / 255.0
    out_a = src_a + dst_a * (1.0 - src_a)
    if out_a <= 0.0:
        return (0, 0, 0, 0)
    out_r = (sr * src_a + dr * dst_a * (1.0 - src_a)) / out_a
    out_g = (sg * src_a + dg * dst_a * (1.0 - src_a)) / out_a
    out_b = (sb * src_a + db * dst_a * (1.0 - src_a)) / out_a
    return (
        int(round(out_r)),
        int(round(out_g)),
        int(round(out_b)),
        int(round(out_a * 255.0)),
    )


def ellipse_alpha(px: float, py: float, cx: float, cy: float, rx: float, ry: float, blur: float) -> float:
    dx = (px - cx) / rx
    dy = (py - cy) / ry
    dist = math.sqrt(dx * dx + dy * dy)
    return 1.0 - smooth_step(1.0 - blur, 1.0 + blur, dist)


def circle_alpha(px: float, py: float, cx: float, cy: float, radius: float, blur: float) -> float:
    dist = math.hypot(px - cx, py - cy) / radius
    return 1.0 - smooth_step(1.0 - blur, 1.0 + blur, dist)


def ring_alpha(px: float, py: float, cx: float, cy: float, inner: float, outer: float, blur: float) -> float:
    dist = math.hypot(px - cx, py - cy)
    outer_mask = 1.0 - smooth_step(outer - blur, outer + blur, dist)
    inner_mask = smooth_step(inner - blur, inner + blur, dist)
    return outer_mask * inner_mask


def diamond_alpha(px: float, py: float, cx: float, cy: float, radius: float, blur: float) -> float:
    dist = (abs(px - cx) + abs(py - cy)) / radius
    return 1.0 - smooth_step(1.0 - blur, 1.0 + blur, dist)


def render_icon(size: int) -> bytes:
    outer_bg_top = (49, 183, 195)
    outer_bg_bottom = (13, 92, 124)
    inner_bg_top = (86, 221, 213)
    inner_bg_bottom = (17, 108, 142)
    paw_white = (244, 252, 255)
    paw_shadow = (12, 46, 70)
    ring_light = (227, 252, 255)
    ring_gold = (255, 210, 102)
    spark = (255, 236, 151)

    pixels: list[tuple[int, int, int, int]] = [(0, 0, 0, 0)] * (size * size)
    center = (size - 1) / 2.0
    outer_radius = size * 0.47
    inner_radius = size * 0.40
    blur = size * 0.01

    for y in range(size):
        py = y + 0.5
        vertical_t = y / max(size - 1, 1)
        for x in range(size):
            px = x + 0.5
            idx = y * size + x
            dist = math.hypot(px - center, py - center)

            outer_mask = 1.0 - smooth_step(outer_radius - blur, outer_radius + blur, dist)
            if outer_mask <= 0.0:
                continue

            ring_t = clamp01((py - (center - outer_radius)) / (outer_radius * 2.0))
            base_rgb = mix_rgb(outer_bg_top, outer_bg_bottom, ring_t)
            highlight = math.exp(
                -(((px - size * 0.30) ** 2 + (py - size * 0.24) ** 2) / (2.0 * (size * 0.12) ** 2))
            )
            base_rgb = mix_rgb(base_rgb, ring_light, highlight * 0.35)
            pixels[idx] = (*base_rgb, int(round(outer_mask * 255.0)))

            border = ring_alpha(px, py, center, center, size * 0.405, size * 0.438, blur)
            if border > 0.0:
                pixels[idx] = over(
                    pixels[idx],
                    (*ring_gold, int(round(border * 255.0 * 0.95))),
                )

            inner_mask = 1.0 - smooth_step(inner_radius - blur, inner_radius + blur, dist)
            if inner_mask > 0.0:
                inner_rgb = mix_rgb(inner_bg_top, inner_bg_bottom, vertical_t)
                inner_highlight = math.exp(
                    -(((px - size * 0.34) ** 2 + (py - size * 0.28) ** 2) / (2.0 * (size * 0.10) ** 2))
                )
                inner_rgb = mix_rgb(inner_rgb, ring_light, inner_highlight * 0.25)
                pixels[idx] = over(
                    pixels[idx],
                    (*inner_rgb, int(round(inner_mask * 255.0))),
                )

            rim = ring_alpha(px, py, center, center, size * 0.36, size * 0.39, blur)
            if rim > 0.0:
                pixels[idx] = over(
                    pixels[idx],
                    (*ring_light, int(round(rim * 255.0 * 0.75))),
                )

    def paint_shape(index: int, alpha: float, color: tuple[int, int, int], strength: float = 1.0) -> None:
        if alpha <= 0.0:
            return
        src = (*color, int(round(clamp01(alpha * strength) * 255.0)))
        pixels[index] = over(pixels[index], src)

    for y in range(size):
        py = y + 0.5
        for x in range(size):
            px = x + 0.5
            idx = y * size + x

            shadow = ellipse_alpha(px, py, size * 0.516, size * 0.63, size * 0.18, size * 0.14, 0.08)
            for toe_x, toe_y, toe_r in (
                (0.36, 0.40, 0.072),
                (0.47, 0.31, 0.070),
                (0.58, 0.31, 0.070),
                (0.69, 0.40, 0.072),
            ):
                shadow = max(
                    shadow,
                    circle_alpha(px, py, size * (toe_x + 0.016), size * (toe_y + 0.02), size * toe_r, 0.08),
                )
            paint_shape(idx, shadow, paw_shadow, 0.34)

            paw = ellipse_alpha(px, py, size * 0.50, size * 0.61, size * 0.18, size * 0.14, 0.08)
            paw = max(paw, circle_alpha(px, py, size * 0.36, size * 0.40, size * 0.072, 0.08))
            paw = max(paw, circle_alpha(px, py, size * 0.47, size * 0.31, size * 0.070, 0.08))
            paw = max(paw, circle_alpha(px, py, size * 0.58, size * 0.31, size * 0.070, 0.08))
            paw = max(paw, circle_alpha(px, py, size * 0.69, size * 0.40, size * 0.072, 0.08))
            paint_shape(idx, paw, paw_white, 1.0)

            sparkle = diamond_alpha(px, py, size * 0.74, size * 0.29, size * 0.060, 0.12)
            paint_shape(idx, sparkle, spark, 0.95)

            sparkle_small = diamond_alpha(px, py, size * 0.80, size * 0.21, size * 0.030, 0.16)
            paint_shape(idx, sparkle_small, ring_light, 0.95)

    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            r, g, b, a = pixels[y * size + x]
            row.extend((r, g, b, a))
        rows.append(bytes(row))

    raw = b"".join(rows)
    compressed = zlib.compress(raw, level=9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def write_ico(images: list[tuple[int, bytes]], path: Path) -> None:
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = []
    payload = bytearray()
    offset = 6 + len(images) * 16
    for size, data in images:
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        entries.append(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        payload.extend(data)
        offset += len(data)
    path.write_bytes(header + b"".join(entries) + payload)


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    sizes = [256, 128, 64, 48, 32, 16]
    rendered = [(size, render_icon(size)) for size in sizes]
    PNG_PATH.write_bytes(rendered[0][1])
    write_ico(rendered, ICO_PATH)
    print(f"Generated {PNG_PATH}")
    print(f"Generated {ICO_PATH}")


if __name__ == "__main__":
    main()
