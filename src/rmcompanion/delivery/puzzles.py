"""Generator and fetcher for daily crosswords and puzzles."""

from __future__ import annotations

import datetime
import io
import logging
import random
from typing import Any

import httpx
import pymupdf

logger = logging.getLogger(__name__)


def crop_pdf_to_content(pdf_bytes: bytes, margin: float = 18.0) -> bytes:
    """Trim excess whitespace margins from crossword PDFs so they fill the tablet screen."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        drawings = page.get_drawings()
        rects = [d["rect"] for d in drawings]
        for b in page.get_text("blocks"):
            rects.append(pymupdf.Rect(b[:4]))
        if rects:
            bbox = rects[0]
            for r in rects[1:]:
                bbox |= r
            crop_rect = pymupdf.Rect(
                max(0.0, bbox.x0 - margin),
                max(0.0, bbox.y0 - margin),
                min(page.rect.width, bbox.x1 + margin),
                min(page.rect.height, bbox.y1 + margin),
            )
            page.set_cropbox(crop_rect)
    return doc.tobytes()


class DailyPuzzlesGenerator:
    """Fetches Guardian crosswords and generates daily puzzles."""

    GUARDIAN_BASE_URL = "https://crosswords-static.guim.co.uk"

    @classmethod
    async def fetch_guardian_crossword(
        cls,
        crossword_type: str = "quick",  # 'quick' or 'cryptic'
        target_date: datetime.date | None = None,
    ) -> tuple[bytes, str]:
        """Fetch and optimize a Guardian crossword PDF.

        Falls back up to 4 days if the crossword wasn't published today (e.g. Sundays).
        Returns (pdf_bytes, filename).
        """
        date = target_date or datetime.date.today()
        headers = {
            "User-Agent": "Un-remarkable/0.1.0 (reMarkable Cloud Companion)",
        }

        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            for days_back in range(5):
                check_date = date - datetime.timedelta(days=days_back)
                date_str = check_date.strftime("%Y%m%d")
                url = f"{cls.GUARDIAN_BASE_URL}/gdn.{crossword_type}.{date_str}.pdf"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        logger.info("Found Guardian %s crossword for %s", crossword_type, date_str)
                        optimized_pdf = crop_pdf_to_content(resp.content, margin=16.0)
                        title_type = "Quick" if crossword_type == "quick" else "Cryptic"
                        filename = f"Guardian_{title_type}_Crossword_{check_date.strftime('%Y-%m-%d')}.pdf"
                        return optimized_pdf, filename
                except Exception as e:
                    logger.warning("Failed checking crossword at %s: %s", url, e)

        raise FileNotFoundError(f"Could not find recent Guardian {crossword_type} crossword")

    @classmethod
    def generate_sudoku_pdf(
        cls,
        difficulty: str = "medium",  # 'easy', 'medium', 'hard'
        target_date: datetime.date | None = None,
        width: int = 1620,
        height: int = 2160,
    ) -> tuple[bytes, str]:
        """Generate a daily Sudoku PDF with puzzle on page 1 and solution on page 2."""
        date = target_date or datetime.date.today()
        seed_num = int(date.strftime("%Y%m%d"))
        clues_count = {"easy": 40, "medium": 32, "hard": 26}.get(difficulty.lower(), 32)

        puzzle_grid, solution_grid = cls._generate_sudoku_data(seed=seed_num, clues=clues_count)

        doc = pymupdf.open()

        # Page 1: Puzzle
        page1 = doc.new_page(width=width, height=height)
        cls._render_sudoku_page(
            page=page1,
            grid=puzzle_grid,
            title="DAILY SUDOKU",
            subtitle=f"{date.strftime('%A, %B %d, %Y')}   |   Difficulty: {difficulty.capitalize()}   |   {clues_count} Clues",
            width=width,
            height=height,
            is_solution=False,
        )

        # Page 2: Solution
        page2 = doc.new_page(width=width, height=height)
        cls._render_sudoku_page(
            page=page2,
            grid=solution_grid,
            title="DAILY SUDOKU - SOLUTION",
            subtitle=f"{date.strftime('%A, %B %d, %Y')}   |   Difficulty: {difficulty.capitalize()} Solution",
            width=width,
            height=height,
            is_solution=True,
        )

        filename = f"Daily_Sudoku_{date.strftime('%Y-%m-%d')}.pdf"
        return doc.tobytes(), filename

    @classmethod
    def _render_sudoku_page(
        cls,
        page: pymupdf.Page,
        grid: list[list[int]],
        title: str,
        subtitle: str,
        width: int,
        height: int,
        is_solution: bool = False,
    ) -> None:
        """Render a single Sudoku puzzle or solution page with authentic e-ink borders."""
        # Top Header Banner
        page.draw_line((90, 90), (width - 90, 90), width=3, color=(0, 0, 0))
        page.insert_text((90, 160), title, fontsize=42, fontname="helv")
        page.draw_line((90, 185), (width - 90, 185), width=1, color=(0, 0, 0))
        page.insert_text((90, 225), subtitle, fontsize=20, fontname="helv")
        page.draw_line((90, 250), (width - 90, 250), width=1, color=(0, 0, 0))

        # Dimensions for 9x9 grid
        cell_size = 135
        grid_width = cell_size * 9
        grid_x0 = (width - grid_width) / 2
        grid_y0 = 340

        # Draw grid lines
        for i in range(10):
            lw = 4.5 if i % 3 == 0 else 1.5
            y = grid_y0 + i * cell_size
            x = grid_x0 + i * cell_size
            # Horizontal line
            page.draw_line((grid_x0, y), (grid_x0 + grid_width, y), width=lw, color=(0, 0, 0))
            # Vertical line
            page.draw_line((x, grid_y0), (x, grid_y0 + grid_width), width=lw, color=(0, 0, 0))

        # Insert numbers
        for r in range(9):
            for c in range(9):
                val = grid[r][c]
                if val != 0:
                    x = grid_x0 + c * cell_size + cell_size * 0.33
                    y = grid_y0 + r * cell_size + cell_size * 0.72
                    font = "times-bold" if not is_solution else "helv"
                    color = (0, 0, 0)
                    page.insert_text((x, y), str(val), fontsize=56, fontname=font, color=color)

        # Bottom Notes Area for pencil marks & stylus scratchpad
        if not is_solution:
            notes_y = grid_y0 + grid_width + 80
            page.draw_line((90, notes_y), (width - 90, notes_y), width=1, color=(0.4, 0.4, 0.4))
            page.insert_text(
                (90, notes_y + 35),
                "SCRATCHPAD & PENCIL MARKS",
                fontsize=16,
                fontname="helv",
                color=(0.3, 0.3, 0.3),
            )
            for line_y in range(int(notes_y + 70), height - 120, 60):
                page.draw_line((90, line_y), (width - 90, line_y), width=0.5, color=(0.7, 0.7, 0.7))

        # Footer
        page.insert_text(
            (90, height - 60),
            "reMarkable Companion Puzzles Edition   •   Solution on next page" if not is_solution else "reMarkable Companion Puzzles Edition",
            fontsize=15,
            fontname="helv",
            color=(0.4, 0.4, 0.4),
        )

    @classmethod
    def _generate_sudoku_data(cls, seed: int, clues: int = 32) -> tuple[list[list[int]], list[list[int]]]:
        """Generate a valid 9x9 Sudoku puzzle and solution."""
        rng = random.Random(seed)
        grid = [[0] * 9 for _ in range(9)]

        def is_valid(g: list[list[int]], r: int, c: int, n: int) -> bool:
            for i in range(9):
                if g[r][i] == n or g[i][c] == n:
                    return False
            br, bc = 3 * (r // 3), 3 * (c // 3)
            for i in range(3):
                for j in range(3):
                    if g[br + i][bc + j] == n:
                        return False
            return True

        def solve(g: list[list[int]]) -> bool:
            for r in range(9):
                for c in range(9):
                    if g[r][c] == 0:
                        nums = list(range(1, 10))
                        rng.shuffle(nums)
                        for n in nums:
                            if is_valid(g, r, c, n):
                                g[r][c] = n
                                if solve(g):
                                    return True
                                g[r][c] = 0
                        return False
            return True

        solve(grid)
        solution = [row[:] for row in grid]

        cells = [(r, c) for r in range(9) for c in range(9)]
        rng.shuffle(cells)
        to_remove = max(0, min(81 - clues, 81 - 17))
        for r, c in cells[:to_remove]:
            grid[r][c] = 0

        return grid, solution
