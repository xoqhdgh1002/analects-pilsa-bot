#!/usr/bin/env python3
"""
논어 필사 PDF 생성기 (Analects Tracing PDF Generator)

한자 원문이 희미하게(Ghost Text) 인쇄된 습자(Tracing)용 PDF 필사 노트를 생성합니다.
"""

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from fpdf import FPDF

from hanja_dictionary import get_hanja_meaning


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """페이지 및 디자인 설정"""
    # Page (A4)
    page_width: float = 210.0
    page_height: float = 297.0

    # Margins
    margin_left: float = 15.0
    margin_right: float = 15.0
    margin_top: float = 20.0
    margin_bottom: float = 15.0

    # Grid defaults
    default_cell_size: float = 30.0
    min_cell_size: float = 20.0
    max_cell_size: float = 30.0
    chars_per_line: int = 6  # fallback when wrapping

    # Grid line
    border_width: float = 0.3
    dash_width: float = 0.15
    dash_length: float = 1.5
    dash_gap: float = 1.5

    # Spacing
    label_height: float = 7.0
    interp_height: float = 8.0
    reading_height: float = 6.0
    meaning_height: float = 5.0
    meaning_box_height: float = 6.0  # Height for manual meaning writing box
    row_gap: float = 4.0
    passage_gap: float = 12.0

    # Interpretation practice lines
    interp_practice_lines: int = 3
    interp_practice_height: float = 12.0

    # Colors (RGB)
    color_original: tuple = (30, 30, 30)
    color_interpretation: tuple = (80, 80, 80)
    color_ghost: tuple = (220, 220, 220)
    color_border: tuple = (180, 180, 180)
    color_cross: tuple = (210, 210, 210)
    color_label: tuple = (60, 60, 60)
    color_meaning_box: tuple = (200, 200, 200)

    # Font size ratio (relative to cell size)
    font_ratio: float = 0.78
    mm_to_pt: float = 1.0 / 0.3528  # mm → pt conversion

    @property
    def usable_width(self) -> float:
        return self.page_width - self.margin_left - self.margin_right

    @property
    def usable_height(self) -> float:
        return self.page_height - self.margin_top - self.margin_bottom


@dataclass
class PassageData:
    """구절 데이터"""
    label: str
    original: str
    interpretation: str
    reading: str = ""


# ---------------------------------------------------------------------------
# PDF Generator
# ---------------------------------------------------------------------------

class AnalectsTracingPDF:
    """논어 필사 PDF 생성 엔진"""

    def __init__(self, config: Config, font_path: str):
        self.cfg = config
        self.font_path = font_path

        self.pdf = FPDF(unit="mm", format="A4")
        self.pdf.set_auto_page_break(auto=False)
        self.pdf.set_margins(
            left=self.cfg.margin_left,
            top=self.cfg.margin_top,
            right=self.cfg.margin_right,
        )

        # Register CJK font
        self.pdf.add_font("CJK", "", self.font_path)
        self.pdf.add_font("CJK", "B", self.font_path)

    # ----- Layout calculation -----

    def calculate_layout(self, n_chars: int) -> tuple[float, int]:
        """
        글자 수에 따라 셀 크기와 줄당 글자 수를 계산합니다.
        """
        cfg = self.cfg
        w = cfg.usable_width

        if n_chars <= 6:
            cell = min(w / n_chars, cfg.max_cell_size)
            return max(cell, cfg.min_cell_size), n_chars

        if n_chars <= 9:
            cell = w / n_chars
            if cell >= cfg.min_cell_size:
                return cell, n_chars

        cell = w / n_chars
        if cell >= cfg.min_cell_size:
            return cell, n_chars

        cell = cfg.min_cell_size
        cpl = int(w // cell)
        return cell, cpl

    def calculate_font_size(self, cell_size: float) -> float:
        """셀 크기에 맞는 폰트 크기(pt)를 계산합니다."""
        return cell_size * self.cfg.font_ratio * self.cfg.mm_to_pt

    # ----- Drawing primitives -----

    def draw_dashed_cross(self, x: float, y: float, size: float):
        """셀 내부에 십자(+) 점선 가이드를 그립니다."""
        cfg = self.cfg
        self.pdf.set_draw_color(*cfg.color_cross)
        self.pdf.set_line_width(cfg.dash_width)
        self.pdf.set_dash_pattern(dash=cfg.dash_length, gap=cfg.dash_gap)

        mid_y = y + size / 2
        self.pdf.line(x, mid_y, x + size, mid_y)
        mid_x = x + size / 2
        self.pdf.line(mid_x, y, mid_x, y + size)
        self.pdf.set_dash_pattern()

    def draw_grid_cell(self, x: float, y: float, size: float):
        """정사각형 격자 셀(테두리 + 십자 점선)을 그립니다."""
        cfg = self.cfg
        self.draw_dashed_cross(x, y, size)
        self.pdf.set_draw_color(*cfg.color_border)
        self.pdf.set_line_width(cfg.border_width)
        self.pdf.rect(x, y, size, size)

    def draw_meaning_box(self, x: float, y: float, width: float, height: float):
        """훈음을 직접 쓸 수 있는 빈 상자를 그립니다."""
        cfg = self.cfg
        self.pdf.set_draw_color(*cfg.color_meaning_box)
        self.pdf.set_line_width(0.2)
        self.pdf.rect(x, y, width, height)

    # ----- Row renderers -----

    def _start_x(self, chars_in_line: int, cell_size: float) -> float:
        """줄의 시작 x 좌표 (왼쪽 정렬)"""
        return self.cfg.margin_left

    def render_original_row(
        self, chars: list[str], interpretation: str,
        cell_size: float, chars_per_line: int, y_start: float,
        reading: str = "",
        sounds: list[str] = None,
    ) -> float:
        """
        Row 1: 진한 원문 글자 + 음독 + 한글 해석 (간격 및 레이아웃 최적화)
        """
        cfg = self.cfg
        font_size = self.calculate_font_size(cell_size)
        y = y_start
        
        row_height = cell_size + cfg.meaning_height
        if not sounds:
            sounds = [None] * len(chars)

        lines_chars = [chars[i:i + chars_per_line] for i in range(0, len(chars), chars_per_line)]
        lines_sounds = [sounds[i:i + chars_per_line] for i in range(0, len(sounds), chars_per_line)]

        for line_chars, line_sounds in zip(lines_chars, lines_sounds):
            x = self._start_x(len(line_chars), cell_size)
            for ch, sound in zip(line_chars, line_sounds):
                # 1. Original Hanja
                self.pdf.set_font("CJK", "", font_size)
                self.pdf.set_text_color(*cfg.color_original)
                self.pdf.text(
                    x + (cell_size - self.pdf.get_string_width(ch)) / 2,
                    y + cell_size * 0.72,
                    ch,
                )
                
                # 2. Meaning below
                meaning = get_hanja_meaning(ch, preferred_sound=sound)
                if meaning:
                    self.pdf.set_font("CJK", "", 7)
                    self.pdf.set_text_color(*cfg.color_interpretation)
                    m_width = self.pdf.get_string_width(meaning)
                    m_x = x + (cell_size - m_width) / 2
                    m_y = y + cell_size + cfg.meaning_height * 0.7
                    if m_width > cell_size + 2: 
                        self.pdf.set_font("CJK", "", 5)
                        m_width = self.pdf.get_string_width(meaning)
                        m_x = x + (cell_size - m_width) / 2
                    self.pdf.text(m_x, m_y, meaning)
                x += cell_size
            y += row_height

        # --- 음독 및 해석 간격 조정 ---
        y += 2
        text_x = cfg.margin_left + 1

        # 3. Reading (음독)
        if reading:
            self.pdf.set_font("CJK", "", 10)
            self.pdf.set_text_color(*cfg.color_original)
            self.pdf.set_xy(text_x, y)
            self.pdf.cell(0, 8, reading, border=0, ln=1)
            y = self.pdf.get_y()

        # 4. Interpretation (해석)
        self.pdf.set_font("CJK", "", 9)
        self.pdf.set_text_color(*cfg.color_interpretation)
        self.pdf.set_xy(text_x, y)
        self.pdf.multi_cell(cfg.usable_width - 2, 5, interpretation, border=0, align='L')
        y = self.pdf.get_y() + 4

        return y

    def render_ghost_row(
        self, chars: list[str], cell_size: float,
        chars_per_line: int, y_start: float,
    ) -> float:
        """
        Row 2: 연한 회색 글자 + 격자 + 훈음 쓰기 빈 칸
        """
        cfg = self.cfg
        font_size = self.calculate_font_size(cell_size)
        y = y_start
        row_height = cell_size + cfg.meaning_box_height
        n_rows = math.ceil(len(chars) / chars_per_line)
        if y + (n_rows * row_height) > cfg.page_height - cfg.margin_bottom:
            self.pdf.add_page()
            y = cfg.margin_top

        lines = [chars[i:i + chars_per_line] for i in range(0, len(chars), chars_per_line)]
        for line_chars in lines:
            x = self._start_x(len(line_chars), cell_size)
            for ch in line_chars:
                self.draw_grid_cell(x, y, cell_size)
                self.pdf.set_font("CJK", "", font_size)
                self.pdf.set_text_color(*cfg.color_ghost)
                self.pdf.text(
                    x + (cell_size - self.pdf.get_string_width(ch)) / 2,
                    y + cell_size * 0.72,
                    ch,
                )
                self.draw_meaning_box(x, y + cell_size, cell_size, cfg.meaning_box_height)
                x += cell_size
            y += row_height
        return y

    def render_practice_row(
        self, n_chars: int, cell_size: float,
        chars_per_line: int, y_start: float,
    ) -> float:
        """
        Row 3: 빈 격자 + 훈음 쓰기 빈 칸
        """
        cfg = self.cfg
        y = y_start
        row_height = cell_size + cfg.meaning_box_height
        n_rows = math.ceil(n_chars / chars_per_line)
        if y + (n_rows * row_height) > cfg.page_height - cfg.margin_bottom:
            self.pdf.add_page()
            y = cfg.margin_top

        remaining = n_chars
        for _ in range(n_rows):
            n_in_line = min(remaining, chars_per_line)
            x = self._start_x(n_in_line, cell_size)
            for _ in range(n_in_line):
                self.draw_grid_cell(x, y, cell_size)
                self.draw_meaning_box(x, y + cell_size, cell_size, cfg.meaning_box_height)
                x += cell_size
            remaining -= n_in_line
            y += row_height
        return y

    def render_interp_practice(self, y_start: float) -> float:
        """해석 필사 라인"""
        cfg = self.cfg
        y = y_start
        needed_h = cfg.interp_practice_lines * cfg.interp_practice_height
        if y + needed_h > cfg.page_height - cfg.margin_bottom:
            self.pdf.add_page()
            y = cfg.margin_top
        self.pdf.set_draw_color(*cfg.color_border)
        self.pdf.set_line_width(0.2)
        self.pdf.set_font("CJK", "", 7)
        self.pdf.set_text_color(*cfg.color_label)
        self.pdf.text(cfg.margin_left, y + 4, "[해석 필사]")
        y += 6
        for _ in range(cfg.interp_practice_lines):
            y += cfg.interp_practice_height
            self.pdf.line(cfg.margin_left, y, cfg.page_width - cfg.margin_right, y)
        return y

    # ----- Passage renderer -----

    def render_passage(self, passage: PassageData):
        """구절 렌더링"""
        cfg = self.cfg
        chars = list(passage.original)
        n = len(chars)
        cell_size, cpl = self.calculate_layout(n)

        sounds = []
        if passage.reading:
            extracted_sounds = list(_extract_hangul(passage.reading))
            if len(extracted_sounds) == n:
                sounds = extracted_sounds
            else:
                sounds = [None] * n
        else:
            sounds = [None] * n

        if self.pdf.page == 0:
            self.pdf.add_page()
        else:
            self.pdf.add_page()
        
        y = cfg.margin_top
        self.pdf.set_font("CJK", "", 9)
        self.pdf.set_text_color(*cfg.color_label)
        self.pdf.text(cfg.margin_left, y + cfg.label_height * 0.65, passage.label)
        y += cfg.label_height

        y = self.render_original_row(chars, passage.interpretation, cell_size, cpl, y, reading=passage.reading, sounds=sounds)
        y += cfg.row_gap
        y = self.render_ghost_row(chars, cell_size, cpl, y)
        y += cfg.row_gap
        y = self.render_practice_row(n, cell_size, cpl, y)
        y += cfg.row_gap
        y = self.render_interp_practice(y)

    def generate(self, passages: list[PassageData], output_path: str):
        for passage in passages:
            self.render_passage(passage)
        self.pdf.output(output_path)


# ---------------------------------------------------------------------------
# Data loading & Utils
# ---------------------------------------------------------------------------

def _is_cjk(ch: str) -> bool:
    return ("\u4e00" <= ch <= "\u9fff" or "\u3400" <= ch <= "\u4dbf" or "\uf900" <= ch <= "\ufaff")

def _contains_cjk(text: str) -> bool:
    return any(_is_cjk(ch) for ch in text)

def _extract_cjk(text: str) -> str:
    return "".join(ch for ch in text if _is_cjk(ch))

def _extract_hangul(text: str) -> str:
    return "".join(ch for ch in text if "\uac00" <= ch <= "\ud7a3")

def parse_text_input(text: str) -> list[PassageData]:
    lines = text.strip().split("\n")
    passages = []
    chapter_num, chapter_name = "", ""
    verse_num, original, reading, interp_lines = "", "", "", []

    def flush():
        nonlocal verse_num, original, reading, interp_lines
        if not original: return
        name = chapter_name.rstrip("편")
        label = f"{name} {chapter_num}-{verse_num}" if chapter_num else verse_num
        passages.append(PassageData(label=label, original=original, interpretation=" ".join(interp_lines).strip(), reading=reading))
        verse_num, original, reading, interp_lines = "", "", "", []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or re.match(r"^\d{6}$", line) or line.startswith("http"): continue
        m = re.match(r"^(\d+)\.\s*(.+)$", line)
        if m and not _contains_cjk(line):
            flush(); chapter_num, chapter_name = m.group(1), m.group(2).strip(); continue
        if m and _contains_cjk(line):
            flush(); verse_num, original = m.group(1), _extract_cjk(m.group(2)); continue
        if line.startswith("(") and line.endswith(")"):
            reading = line[1:-1].strip(); continue
        interp_lines.append(line)
    flush()
    return passages

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", required=True)
    parser.add_argument("--input")
    parser.add_argument("--output", default="analects_tracing.pdf")
    args = parser.parse_args()
    if not Path(args.font).exists(): return
    text = Path(args.input).read_text(encoding="utf-8")
    passages = parse_text_input(text)
    config = Config()
    generator = AnalectsTracingPDF(config, str(args.font))
    generator.generate(passages, args.output)

if __name__ == "__main__":
    main()