"""Renders reMarkable .rm v6 scene files to SVG vector graphics."""

from __future__ import annotations

import io
import logging
from typing import BinaryIO
from xml.sax.saxutils import escape

from rmscene import CrdtId, SceneTree, read_tree
from rmscene import scene_items as si
from rmscene.text import TextDocument

from rmcompanion.render.writing_tools import create_pen

logger = logging.getLogger(__name__)

# Standard reMarkable dimensions
RM2_WIDTH = 1404
RM2_HEIGHT = 1872
RM_PRO_WIDTH = 1620
RM_PRO_HEIGHT = 2160

TEXT_TOP_Y = -88
LINE_HEIGHTS = {
    si.ParagraphStyle.PLAIN: 70,
    si.ParagraphStyle.BULLET: 45,
    si.ParagraphStyle.BULLET2: 45,
    si.ParagraphStyle.BOLD: 70,
    si.ParagraphStyle.HEADING: 140,
    si.ParagraphStyle.CHECKBOX: 45,
    si.ParagraphStyle.CHECKBOX_CHECKED: 45,
}


def build_anchor_map(text_item: si.Text | None, default_height: int) -> dict[CrdtId, float]:
    """Map text anchor CRDT IDs to vertical y coordinates."""
    anchor_map: dict[CrdtId, float] = {}

    if text_item is not None:
        try:
            doc = TextDocument.from_scene_item(text_item)
            ypos = float(text_item.pos_y + TEXT_TOP_Y)
            top_y = ypos
            for p in doc.contents:
                anchor_map[p.start_id] = ypos
                for sub in p.contents:
                    for k in sub.i:
                        anchor_map[k] = ypos
                lh = LINE_HEIGHTS.get(p.style.value, 70)
                ypos += lh
            bottom_y = ypos

            anchor_map[CrdtId(0, 281474976710654)] = top_y
            anchor_map[CrdtId(0, 281474976710655)] = bottom_y
            return anchor_map
        except Exception as e:
            logger.warning("Failed to build text anchors: %s", e)

    anchor_map[CrdtId(0, 281474976710654)] = 0.0
    anchor_map[CrdtId(0, 281474976710655)] = float(default_height)
    return anchor_map


def get_group_anchor(group: si.Group, anchor_map: dict[CrdtId, float]) -> tuple[float, float]:
    ax = 0.0
    ay = 0.0
    if group.anchor_id is not None:
        if group.anchor_origin_x is not None:
            ax = float(group.anchor_origin_x.value)
        if group.anchor_id.value in anchor_map:
            ay = anchor_map[group.anchor_id.value]
    return ax, ay


def render_rm_to_svg(
    rm_data: bytes | BinaryIO,
    dark_mode: bool = False,
    include_background: bool = True,
    target_width: int | None = None,
    target_height: int | None = None,
) -> str:
    """Parse .rm binary data and render complete SVG string."""
    if isinstance(rm_data, bytes):
        stream = io.BytesIO(rm_data)
    else:
        stream = rm_data

    tree: SceneTree = read_tree(stream)

    # Detect paper size (defaults to Paper Pro 1620x2160 or user target)
    width = target_width or RM_PRO_WIDTH
    height = target_height or RM_PRO_HEIGHT

    # Check if scene tree specifies custom paper size
    scene_info = getattr(tree, "info", None)
    if scene_info and getattr(scene_info, "paper_size", None):
        ps = scene_info.paper_size
        if isinstance(ps, (tuple, list)) and len(ps) >= 2 and ps[0] > 0 and ps[1] > 0:
            width, height = ps[0], ps[1]

    half_w = width // 2
    viewbox = f"{-half_w} 0 {width} {height}"

    bg_color = "#18181b" if dark_mode else "#ffffff"
    text_color = "#f4f4f5" if dark_mode else "#18181b"

    out = io.StringIO()
    out.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" width="{width}" height="{height}">\n')

    # SVG styling
    out.write(f"""  <style>
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
    .rm-plain {{ font-size: 26px; fill: {text_color}; }}
    .rm-bold {{ font-size: 28px; font-weight: bold; fill: {text_color}; }}
    .rm-heading {{ font-size: 42px; font-weight: bold; fill: {text_color}; }}
    .rm-bullet {{ font-size: 26px; fill: {text_color}; }}
    .rm-checkbox {{ font-size: 26px; fill: {text_color}; }}
  </style>\n""")

    if include_background:
        out.write(f'  <rect x="{-half_w}" y="0" width="{width}" height="{height}" fill="{bg_color}"/>\n')

    anchor_map = build_anchor_map(tree.root_text, height)

    # 1. Render typed text
    if tree.root_text is not None:
        try:
            doc = TextDocument.from_scene_item(tree.root_text)
            y_offset = float(tree.root_text.pos_y + TEXT_TOP_Y)
            text_x = float(tree.root_text.pos_x)

            out.write('  <g class="rm-typed-text">\n')
            for p in doc.contents:
                y_offset += LINE_HEIGHTS.get(p.style.value, 70)
                raw_str = str(p).strip()
                if not raw_str:
                    continue

                escaped = escape(raw_str)

                if p.style.value == si.ParagraphStyle.HEADING:
                    out.write(f'    <text x="{text_x:.1f}" y="{y_offset:.1f}" class="rm-heading">{escaped}</text>\n')
                elif p.style.value == si.ParagraphStyle.BOLD:
                    out.write(f'    <text x="{text_x:.1f}" y="{y_offset:.1f}" class="rm-bold">{escaped}</text>\n')
                elif p.style.value in (si.ParagraphStyle.BULLET, si.ParagraphStyle.BULLET2):
                    out.write(f'    <circle cx="{text_x - 20:.1f}" cy="{y_offset - 8:.1f}" r="4" fill="{text_color}"/>\n')
                    out.write(f'    <text x="{text_x:.1f}" y="{y_offset:.1f}" class="rm-bullet">{escaped}</text>\n')
                elif p.style.value == si.ParagraphStyle.CHECKBOX:
                    # Unchecked box
                    out.write(f'    <rect x="{text_x - 30:.1f}" y="{y_offset - 20:.1f}" width="18" height="18" rx="3" fill="none" stroke="{text_color}" stroke-width="2"/>\n')
                    out.write(f'    <text x="{text_x:.1f}" y="{y_offset:.1f}" class="rm-checkbox">{escaped}</text>\n')
                elif p.style.value == si.ParagraphStyle.CHECKBOX_CHECKED:
                    # Checked box
                    out.write(f'    <rect x="{text_x - 30:.1f}" y="{y_offset - 20:.1f}" width="18" height="18" rx="3" fill="none" stroke="{text_color}" stroke-width="2"/>\n')
                    out.write(f'    <path d="M {text_x - 27:.1f} {y_offset - 11:.1f} L {text_x - 22:.1f} {y_offset - 6:.1f} L {text_x - 15:.1f} {y_offset - 16:.1f}" fill="none" stroke="{text_color}" stroke-width="2.5" stroke-linecap="round"/>\n')
                    out.write(f'    <text x="{text_x:.1f}" y="{y_offset:.1f}" class="rm-checkbox" text-decoration="line-through">{escaped}</text>\n')
                else:
                    out.write(f'    <text x="{text_x:.1f}" y="{y_offset:.1f}" class="rm-plain">{escaped}</text>\n')
            out.write('  </g>\n')
        except Exception as e:
            logger.warning("Error rendering typed text: %s", e)

    # 2. Render stroke ink
    out.write('  <g class="rm-drawing">\n')

    def draw_group(group: si.Group, cur_ax: float, cur_ay: float) -> None:
        gx, gy = get_group_anchor(group, anchor_map)
        total_ax = cur_ax + gx
        total_ay = cur_ay + gy

        for child_id in group.children:
            child = group.children[child_id]
            if isinstance(child, si.Group):
                draw_group(child, total_ax, total_ay)
            elif isinstance(child, si.Line):
                draw_line(child, total_ax, total_ay)

    def draw_line(line: si.Line, ax: float, ay: float) -> None:
        if not line.points:
            return

        pen = create_pen(
            line.tool.value,
            line.color.value,
            line.thickness_scale,
            explicit_rgba=line.color_rgba,
            dark_mode=dark_mode,
        )

        if pen.base_opacity <= 0.001:
            return

        blend_style = f"mix-blend-mode:{pen.mix_blend_mode};" if pen.mix_blend_mode != "normal" else ""
        points = line.points
        seg_len = pen.segment_length

        # Split into segments according to pen sensitivity
        for i in range(0, len(points), seg_len):
            chunk = points[i : i + seg_len + 1]
            if not chunk:
                continue

            pt = chunk[0]
            w = pen.get_segment_width(pt.speed, pt.direction, pt.width, pt.pressure, pen.base_width)
            col = pen.get_segment_color(pt.speed, pt.direction, pt.width, pt.pressure, pen.base_width)
            op = pen.get_segment_opacity(pt.speed, pt.direction, pt.width, pt.pressure, pen.base_width)

            pts_str = " ".join(f"{(p.x + ax):.1f},{(p.y + ay):.1f}" for p in chunk)
            out.write(
                f'    <polyline fill="none" stroke="{col}" stroke-width="{w:.2f}" opacity="{op:.2f}" '
                f'stroke-linecap="{pen.stroke_linecap}" stroke-linejoin="round" '
                f'style="{blend_style}" points="{pts_str}" />\n'
            )

    draw_group(tree.root, 0.0, 0.0)

    out.write('  </g>\n')
    out.write('</svg>\n')
    return out.getvalue()
