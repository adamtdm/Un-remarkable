"""Pen stroke modeling and styling for reMarkable writing tools."""

from __future__ import annotations

import math

from rmscene.scene_items import Pen as PenType

from rmcompanion.render.palette import format_rgba, lookup_color


def clamp(val: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    return max(min_val, min(val, max_val))


class PenTool:
    """Base class for writing tool stroke calculations."""

    name: str = "Pen"
    segment_length: int = 1000
    stroke_linecap: str = "round"
    base_opacity: float = 1.0
    mix_blend_mode: str = "normal"

    def __init__(
        self,
        base_width: float,
        rgba: tuple[int, int, int, int],
        dark_mode: bool = False,
    ) -> None:
        self.base_width = base_width
        self.rgba = rgba
        self.dark_mode = dark_mode

    def get_segment_width(
        self,
        speed: float,
        direction: float,
        width: float,
        pressure: float,
        last_width: float,
    ) -> float:
        return self.base_width

    def get_segment_opacity(
        self,
        speed: float,
        direction: float,
        width: float,
        pressure: float,
        last_width: float,
    ) -> float:
        return self.base_opacity

    def get_segment_color(
        self,
        speed: float,
        direction: float,
        width: float,
        pressure: float,
        last_width: float,
    ) -> str:
        r, g, b, _ = self.rgba
        return format_rgba(r, g, b, 1.0)


class Fineliner(PenTool):
    name = "Fineliner"
    segment_length = 1000
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 1.8, rgba, dark_mode)


class Ballpoint(PenTool):
    name = "Ballpoint"
    segment_length = 5
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 1.5, rgba, dark_mode)

    def get_segment_width(
        self, speed: float, direction: float, width: float, pressure: float, last_width: float
    ) -> float:
        # Pressure ranges ~0-1 (after normalization)
        norm_pressure = clamp(pressure / 255.0 if pressure > 1.0 else pressure)
        w = self.base_width * (0.6 + 0.8 * norm_pressure)
        return max(0.5, w)

    def get_segment_opacity(
        self, speed: float, direction: float, width: float, pressure: float, last_width: float
    ) -> float:
        norm_pressure = clamp(pressure / 255.0 if pressure > 1.0 else pressure)
        return clamp(0.7 + 0.3 * norm_pressure)


class Marker(PenTool):
    name = "Marker"
    segment_length = 1000
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 3.2, rgba, dark_mode)


class Pencil(PenTool):
    name = "Pencil"
    segment_length = 5
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 1.6, rgba, dark_mode)

    def get_segment_opacity(
        self, speed: float, direction: float, width: float, pressure: float, last_width: float
    ) -> float:
        norm_pressure = clamp(pressure / 255.0 if pressure > 1.0 else pressure)
        return clamp(0.4 + 0.5 * norm_pressure)

    def get_segment_width(
        self, speed: float, direction: float, width: float, pressure: float, last_width: float
    ) -> float:
        norm_pressure = clamp(pressure / 255.0 if pressure > 1.0 else pressure)
        return max(0.6, self.base_width * (0.7 + 0.6 * norm_pressure))


class MechanicalPencil(PenTool):
    name = "MechanicalPencil"
    segment_length = 1000
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 1.2, rgba, dark_mode)
        self.base_opacity = 0.85


class Paintbrush(PenTool):
    name = "Paintbrush"
    segment_length = 4
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 4.0, rgba, dark_mode)

    def get_segment_width(
        self, speed: float, direction: float, width: float, pressure: float, last_width: float
    ) -> float:
        norm_pressure = clamp(pressure / 255.0 if pressure > 1.0 else pressure)
        return max(1.0, self.base_width * (0.3 + 1.4 * norm_pressure))


class Calligraphy(PenTool):
    name = "Calligraphy"
    segment_length = 3
    stroke_linecap = "butt"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 3.5, rgba, dark_mode)

    def get_segment_width(
        self, speed: float, direction: float, width: float, pressure: float, last_width: float
    ) -> float:
        # Chisel tip: stroke width varies according to angle (approx. 45-degree angle)
        tilt = direction * (math.pi * 2) / 255.0 if direction > math.pi * 2 else direction
        angle_diff = math.sin(tilt - math.pi / 4.0)
        return max(1.0, self.base_width * (0.3 + 0.7 * abs(angle_diff)))


class Highlighter(PenTool):
    name = "Highlighter"
    segment_length = 1000
    stroke_linecap = "square"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(28.0, rgba, dark_mode)
        if dark_mode:
            self.base_opacity = 0.55
            self.mix_blend_mode = "screen"
        else:
            self.base_opacity = 0.40
            self.mix_blend_mode = "multiply"


class Shader(PenTool):
    name = "Shader"
    segment_length = 5
    stroke_linecap = "round"

    def __init__(self, base_width: float, rgba: tuple[int, int, int, int], dark_mode: bool = False) -> None:
        super().__init__(base_width * 6.0, rgba, dark_mode)
        self.base_opacity = 0.35
        if dark_mode:
            self.mix_blend_mode = "screen"
        else:
            self.mix_blend_mode = "multiply"


class Eraser(PenTool):
    name = "Eraser"
    segment_length = 1000
    base_opacity = 0.0


def create_pen(
    pen_type_val: int,
    color_val: int,
    thickness_scale: float,
    explicit_rgba: tuple[int, ...] | None = None,
    dark_mode: bool = False,
) -> PenTool:
    """Factory creating configured pen tool instance."""
    rgba = lookup_color(color_val, explicit_rgba, dark_mode=dark_mode)

    # Normalize thickness scale (defaults to 1.0 or 2.0 depending on rm version)
    width = max(0.5, thickness_scale)

    if pen_type_val in (PenType.FINELINER_1.value, PenType.FINELINER_2.value):
        return Fineliner(width, rgba, dark_mode)
    elif pen_type_val in (PenType.BALLPOINT_1.value, PenType.BALLPOINT_2.value):
        return Ballpoint(width, rgba, dark_mode)
    elif pen_type_val in (PenType.MARKER_1.value, PenType.MARKER_2.value):
        return Marker(width, rgba, dark_mode)
    elif pen_type_val in (PenType.PENCIL_1.value, PenType.PENCIL_2.value):
        return Pencil(width, rgba, dark_mode)
    elif pen_type_val in (PenType.MECHANICAL_PENCIL_1.value, PenType.MECHANICAL_PENCIL_2.value):
        return MechanicalPencil(width, rgba, dark_mode)
    elif pen_type_val in (PenType.PAINTBRUSH_1.value, PenType.PAINTBRUSH_2.value):
        return Paintbrush(width, rgba, dark_mode)
    elif pen_type_val == PenType.CALIGRAPHY.value:
        return Calligraphy(width, rgba, dark_mode)
    elif pen_type_val in (PenType.HIGHLIGHTER_1.value, PenType.HIGHLIGHTER_2.value):
        return Highlighter(width, rgba, dark_mode)
    elif pen_type_val == getattr(PenType, "SHADER", 23):
        return Shader(width, rgba, dark_mode)
    elif pen_type_val in (PenType.ERASER.value, PenType.ERASER_AREA.value):
        return Eraser(width, rgba, dark_mode)
    else:
        return Ballpoint(width, rgba, dark_mode)
