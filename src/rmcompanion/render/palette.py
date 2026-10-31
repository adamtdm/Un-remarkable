"""Color palettes, perceptual dark mode mappings, and highlighter blend modes."""

from __future__ import annotations

from rmscene.scene_items import PenColor

# Standard reMarkable 3.x+ RGB palette (light background)
RM_PALETTE_LIGHT: dict[int, tuple[int, int, int]] = {
    PenColor.BLACK.value: (24, 24, 27),          # Near black #18181b
    PenColor.GRAY.value: (140, 140, 145),        # Medium gray #8c8c91
    PenColor.WHITE.value: (255, 255, 255),       # White
    PenColor.YELLOW.value: (234, 179, 8),        # Amber/Yellow #eab308
    PenColor.GREEN.value: (34, 197, 94),         # Emerald green #22c55e
    PenColor.PINK.value: (244, 114, 182),        # Pink #f472b6
    PenColor.BLUE.value: (37, 99, 235),          # Cobalt blue #2563eb
    PenColor.RED.value: (220, 38, 38),           # Crimson red #dc2626
    PenColor.GRAY_OVERLAP.value: (115, 115, 120),
    PenColor.GREEN_2.value: (132, 204, 22),      # Lime green #84cc16
    PenColor.CYAN.value: (6, 182, 212),          # Cyan #06b6d4
    PenColor.MAGENTA.value: (168, 85, 247),      # Purple/Magenta #a855f7
    PenColor.YELLOW_2.value: (250, 204, 21),     # Bright yellow #facc15
}

# Perceptually tuned palette for dark mode (#18181b canvas)
# Inverts lightness while preserving hue vibrancy and high contrast
RM_PALETTE_DARK: dict[int, tuple[int, int, int]] = {
    PenColor.BLACK.value: (244, 244, 245),       # Light zinc #f4f4f5 (near white ink)
    PenColor.GRAY.value: (161, 161, 170),        # Zinc 400 #a1a1aa
    PenColor.WHITE.value: (39, 39, 42),          # Zinc 800 (dark ink)
    PenColor.YELLOW.value: (253, 224, 71),       # Yellow 300 #fde047
    PenColor.GREEN.value: (74, 222, 128),        # Green 400 #4ade80
    PenColor.PINK.value: (244, 114, 182),        # Pink 400 #f472b6
    PenColor.BLUE.value: (96, 165, 250),         # Blue 400 #60a5fa
    PenColor.RED.value: (248, 113, 113),         # Red 400 #f87171
    PenColor.GRAY_OVERLAP.value: (161, 161, 170),
    PenColor.GREEN_2.value: (163, 230, 53),      # Lime 400 #a3e635
    PenColor.CYAN.value: (56, 189, 248),         # Sky 400 #38bdf8
    PenColor.MAGENTA.value: (192, 132, 252),     # Purple 400 #c084fc
    PenColor.YELLOW_2.value: (254, 240, 138),    # Yellow 200 #fef08a
}


def lookup_color(
    color_val: int,
    explicit_rgba: tuple[int, ...] | None = None,
    dark_mode: bool = False,
) -> tuple[int, int, int, int]:
    """Return (R, G, B, A) for a given pen color value and theme."""
    palette = RM_PALETTE_DARK if dark_mode else RM_PALETTE_LIGHT

    if explicit_rgba is not None:
        r, g, b = explicit_rgba[0], explicit_rgba[1], explicit_rgba[2]
        a = explicit_rgba[3] if len(explicit_rgba) > 3 else 255
        if dark_mode:
            # Smart invert explicit RGB (if nearly black, map to white)
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if luminance < 50:
                r, g, b = 244, 244, 245
            elif luminance > 200:
                r, g, b = 39, 39, 42
        return r, g, b, a

    rgb = palette.get(color_val, palette[PenColor.BLACK.value])
    return rgb[0], rgb[1], rgb[2], 255


def format_rgba(r: int, g: int, b: int, a: float = 1.0) -> str:
    """Format CSS rgba string."""
    return f"rgba({r}, {g}, {b}, {a:.3f})"
