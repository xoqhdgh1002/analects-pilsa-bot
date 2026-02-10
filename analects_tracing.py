#!/usr/bin/env python3
"""
논어 필사 PDF 생성기 (Analects Tracing PDF Generator)

한자 원문이 희미하게(Ghost Text) 인쇄된 습자(Tracing)용 PDF 필사 노트를 생성합니다.

사용법:
    python analects_tracing.py --font /path/to/cjk_font.ttf --output output.pdf

폰트 안내:
    CJK(한중일) 문자를 지원하는 TTF 폰트가 필요합니다.
    추천 폰트:
    - Noto Sans CJK (https://fonts.google.com/noto)
    - Noto Serif CJK
    - 나눔명조 / 나눔고딕
    - 본명조 / 본고딕
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

        Returns:
            (cell_size_mm, chars_per_line)
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

        # 10자 이상 또는 한 줄에 안 맞는 경우: 한 줄에 최대한 맞추되 셀 크기 축소
        cell = w / n_chars
        if cell >= cfg.min_cell_size:
            return cell, n_chars

        # 그래도 안 맞으면 줄바꿈 (min_cell_size 사용, 줄당 최대 글자 수)
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

        # Horizontal center line
        mid_y = y + size / 2
        self.pdf.line(x, mid_y, x + size, mid_y)

        # Vertical center line
        mid_x = x + size / 2
        self.pdf.line(mid_x, y, mid_x, y + size)

        # Reset dash
        self.pdf.set_dash_pattern()

    def draw_grid_cell(self, x: float, y: float, size: float):
        """정사각형 격자 셀(테두리 + 십자 점선)을 그립니다."""
        cfg = self.cfg

        # Draw cross guides first (behind border)
        self.draw_dashed_cross(x, y, size)

        # Border
        self.pdf.set_draw_color(*cfg.color_border)
        self.pdf.set_line_width(cfg.border_width)
        self.pdf.rect(x, y, size, size)

    # ----- Row renderers -----

    def _start_x(self, chars_in_line: int, cell_size: float) -> float:
        """줄의 시작 x 좌표 (왼쪽 정렬)"""
        return self.cfg.margin_left

    def render_original_row(
        self, chars: list[str], interpretation: str,
        cell_size: float, chars_per_line: int, y_start: float,
        reading: str = "",
    ) -> float:
        """
        Row 1: 진한 원문 글자 + 음독 + 한글 해석 (자동 줄바꿈 지원)
        """
        cfg = self.cfg
        font_size = self.calculate_font_size(cell_size)
        y = y_start

        lines = [chars[i:i + chars_per_line] for i in range(0, len(chars), chars_per_line)]

        for line_chars in lines:
            x = self._start_x(len(line_chars), cell_size)
            self.pdf.set_font("CJK", "", font_size)
            self.pdf.set_text_color(*cfg.color_original)
            for ch in line_chars:
                self.pdf.text(
                    x + (cell_size - self.pdf.get_string_width(ch)) / 2,
                    y + cell_size * 0.72,
                    ch,
                )
                x += cell_size
            y += cell_size

        text_x = cfg.margin_left + 1

        # Reading text (음독)
        if reading:
            self.pdf.set_font("CJK", "", 8)
            self.pdf.set_text_color(*cfg.color_interpretation)
            self.pdf.text(text_x, y + cfg.reading_height * 0.65, reading)
            y += cfg.reading_height

        # Interpretation text (해석) - multi_cell 사용하여 자동 줄바꿈
        self.pdf.set_font("CJK", "", 9)
        self.pdf.set_text_color(*cfg.color_interpretation)
        self.pdf.set_xy(text_x, y)
        # 너비는 가용 너비에서 마진을 뺀 값으로 설정
        self.pdf.multi_cell(cfg.usable_width - 2, 5, interpretation, border=0, align='L')
        y = self.pdf.get_y() + 2  # multi_cell 이후 y 좌표 업데이트 및 여백 추가

        return y

    def render_ghost_row(
        self, chars: list[str], cell_size: float,
        chars_per_line: int, y_start: float,
    ) -> float:
        """
        Row 2: 연한 회색 글자 + 격자 + 십자 점선 (따라쓰기) + 훈음
        """
        cfg = self.cfg
        font_size = self.calculate_font_size(cell_size)
        y = y_start
        
        # 행 높이: 셀 크기 + 훈음 높이
        row_height = cell_size + cfg.meaning_height

        # 페이지 하단 체크: 따라쓰기 행이 잘릴 것 같으면 새 페이지
        n_rows = math.ceil(len(chars) / chars_per_line)
        if y + (n_rows * row_height) > cfg.page_height - cfg.margin_bottom:
            self.pdf.add_page()
            y = cfg.margin_top

        lines = [chars[i:i + chars_per_line] for i in range(0, len(chars), chars_per_line)]

        for line_chars in lines:
            x = self._start_x(len(line_chars), cell_size)
            for ch in line_chars:
                # 1. Grid & Ghost char
                self.draw_grid_cell(x, y, cell_size)
                self.pdf.set_font("CJK", "", font_size)
                self.pdf.set_text_color(*cfg.color_ghost)
                self.pdf.text(
                    x + (cell_size - self.pdf.get_string_width(ch)) / 2,
                    y + cell_size * 0.72,
                    ch,
                )
                
                # 2. Meaning (Hanja Hun-Eum)
                meaning = get_hanja_meaning(ch)
                if meaning:
                    # 훈음 폰트 설정 (작게)
                    self.pdf.set_font("CJK", "", 7)
                    self.pdf.set_text_color(*cfg.color_interpretation)
                    
                    # 텍스트 너비 계산하여 중앙 정렬
                    m_width = self.pdf.get_string_width(meaning)
                    m_x = x + (cell_size - m_width) / 2
                    m_y = y + cell_size + cfg.meaning_height * 0.7
                    
                    # 셀 영역 밖으로 너무 나가면 글자 크기 더 줄이기
                    if m_width > cell_size + 2: 
                        self.pdf.set_font("CJK", "", 5)
                        m_width = self.pdf.get_string_width(meaning)
                        m_x = x + (cell_size - m_width) / 2
                    
                    self.pdf.text(m_x, m_y, meaning)

                x += cell_size
            y += row_height

        return y

    def render_practice_row(
        self, n_chars: int, cell_size: float,
        chars_per_line: int, y_start: float,
    ) -> float:
        """
        Row 3: 빈 격자 + 십자 점선 (자유 필사)
        """
        cfg = self.cfg
        y = y_start
        
        # 페이지 하단 체크: 빈 격자 행이 잘릴 것 같으면 새 페이지
        n_rows = math.ceil(n_chars / chars_per_line)
        if y + (n_rows * cell_size) > cfg.page_height - cfg.margin_bottom:
            self.pdf.add_page()
            y = cfg.margin_top

        remaining = n_chars
        for _ in range(n_rows):
            n_in_line = min(remaining, chars_per_line)
            x = self._start_x(n_in_line, cell_size)
            for _ in range(n_in_line):
                self.draw_grid_cell(x, y, cell_size)
                x += cell_size
            remaining -= n_in_line
            y += cell_size

        return y

    def render_interp_practice(self, y_start: float) -> float:
        """한글 해석을 직접 쓸 수 있도록 가로줄(노트 라인)을 그립니다."""
        cfg = self.cfg
        y = y_start
        
        # 페이지 하단 체크
        needed_h = cfg.interp_practice_lines * cfg.interp_practice_height
        if y + needed_h > cfg.page_height - cfg.margin_bottom:
            self.pdf.add_page()
            y = cfg.margin_top

        self.pdf.set_draw_color(*cfg.color_border)
        self.pdf.set_line_width(0.2)
        
        # '해석 필사' 라벨 (작게)
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
        """구절 하나를 렌더링합니다. 각 구절은 항상 새 페이지에서 시작합니다."""
        cfg = self.cfg
        chars = list(passage.original)
        n = len(chars)
        cell_size, cpl = self.calculate_layout(n)

        # 항상 새 페이지 추가 (단, 첫 페이지가 비어있는 경우는 제외)
        if self.pdf.page == 0:
            self.pdf.add_page()
        else:
            self.pdf.add_page()
        
        self.cursor_y = cfg.margin_top
        y = self.cursor_y

        # Label
        self.pdf.set_font("CJK", "", 9)
        self.pdf.set_text_color(*cfg.color_label)
        self.pdf.text(cfg.margin_left, y + cfg.label_height * 0.65, passage.label)
        y += cfg.label_height

        # Row 1: Original text + reading + interpretation
        y = self.render_original_row(
            chars, passage.interpretation, cell_size, cpl, y,
            reading=passage.reading,
        )
        y += cfg.row_gap

        # Row 2: Ghost text for tracing (내부에서 페이지 체크 수행)
        y = self.render_ghost_row(chars, cell_size, cpl, y)
        y += cfg.row_gap

        # Row 3: Empty practice grid (내부에서 페이지 체크 수행)
        y = self.render_practice_row(n, cell_size, cpl, y)
        y += cfg.row_gap

        # Row 4: Interpretation practice lines (가로줄 추가)
        y = self.render_interp_practice(y)
        y += cfg.passage_gap

        self.cursor_y = y

    # ----- Main generation -----

    def generate(self, passages: list[PassageData], output_path: str):
        """전체 PDF를 생성합니다."""
        self.cursor_y = self.cfg.margin_top

        for passage in passages:
            self.render_passage(passage)

        self.pdf.output(output_path)
        print(f"PDF 생성 완료: {output_path}")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _is_cjk(ch: str) -> bool:
    """한자(CJK) 문자인지 판별합니다."""
    return (
        "\u4e00" <= ch <= "\u9fff"          # CJK Unified Ideographs
        or "\u3400" <= ch <= "\u4dbf"       # CJK Unified Ideographs Extension A
        or "\uf900" <= ch <= "\ufaff"       # CJK Compatibility Ideographs
        or "\U00020000" <= ch <= "\U0002a6df"  # CJK Unified Ideographs Extension B
    )


def _contains_cjk(text: str) -> bool:
    """텍스트에 한자(CJK)가 포함되어 있는지 확인합니다."""
    return any(_is_cjk(ch) for ch in text)


def _extract_cjk(text: str) -> str:
    """텍스트에서 한자(CJK) 문자만 추출합니다."""
    return "".join(ch for ch in text if _is_cjk(ch))


def parse_text_input(text: str) -> list[PassageData]:
    """
    자유 형식 텍스트를 파싱하여 PassageData 리스트로 변환합니다.

    입력 형식 예시:
        9.자한편
        29.子曰: "歲寒, 然後知松栢之後彫也."
        (자왈: "세한, 연후지송백지후조야.")

        공자께서 말씀하셨다. "날씨가 추워진 뒤에야..."
    """
    lines = text.strip().split("\n")
    passages: list[PassageData] = []

    chapter_num = ""
    chapter_name = ""

    # 현재 파싱 중인 구절
    verse_num = ""
    original = ""
    reading = ""
    interp_lines: list[str] = []

    def flush():
        nonlocal verse_num, original, reading, interp_lines
        if not original:
            return
        name = chapter_name.rstrip("편")
        label = f"{name} {chapter_num}-{verse_num}" if chapter_num else verse_num
        passages.append(PassageData(
            label=label,
            original=original,
            interpretation=" ".join(interp_lines).strip(),
            reading=reading,
        ))
        verse_num = ""
        original = ""
        reading = ""
        interp_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            continue

        # 날짜 무시 (예: 260209)
        if re.match(r"^\d{6}$", line):
            continue

        # URL 무시 (예: https://naver.me/...)
        if line.startswith("http"):
            continue

        # 편 정보: "9.자한편" — 숫자 + 점 + 한글(한자 없음)
        m = re.match(r"^(\d+)\.\s*(.+)$", line)
        if m and not _contains_cjk(line):
            flush()
            chapter_num = m.group(1)
            chapter_name = m.group(2).strip()
            continue

        # 구절 원문: "29.子曰: ..." — 숫자 + 점 + 한자 포함
        if m and _contains_cjk(line):
            flush()
            verse_num = m.group(1)
            original = _extract_cjk(m.group(2))
            continue

        # 음독: "(자왈: ...)"
        if line.startswith("(") and line.endswith(")"):
            reading = line[1:-1].strip()
            continue

        # 나머지는 해석
        interp_lines.append(line)

    flush()
    return passages


def load_passages(json_path: str) -> list[PassageData]:
    """JSON 파일에서 구절 데이터를 로드합니다."""
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return [
        PassageData(
            label=p["label"],
            original=p["original"],
            interpretation=p["interpretation"],
            reading=p.get("reading", ""),
        )
        for p in data["passages"]
    ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="논어 필사 PDF 생성기 - 습자(Tracing)용 필사 노트를 생성합니다.",
    )
    parser.add_argument(
        "--font",
        required=True,
        help="CJK 지원 TTF/OTF 폰트 파일 경로",
    )

    # 입력 소스 (둘 중 하나)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--input",
        help="자유 형식 텍스트 파일 경로 (편명/원문/음독/해석 자동 파싱)",
    )
    input_group.add_argument(
        "--data",
        help="구절 데이터 JSON 파일 경로",
    )

    parser.add_argument(
        "--output",
        default="analects_tracing.pdf",
        help="출력 PDF 파일 경로 (기본: analects_tracing.pdf)",
    )

    args = parser.parse_args()

    # Validate font file
    font_path = Path(args.font)
    if not font_path.exists():
        print(f"오류: 폰트 파일을 찾을 수 없습니다: {font_path}")
        print("CJK 지원 TTF/OTF 폰트 파일 경로를 확인해주세요.")
        return

    # Load passages
    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"오류: 입력 파일을 찾을 수 없습니다: {input_path}")
            return
        text = input_path.read_text(encoding="utf-8")
        passages = parse_text_input(text)
    elif args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"오류: 데이터 파일을 찾을 수 없습니다: {data_path}")
            return
        passages = load_passages(str(data_path))
    else:
        print("오류: --input (텍스트 파일) 또는 --data (JSON 파일) 옵션 중 하나를 반드시 지정해야 합니다.")
        return

    if not passages:
        print("오류: 파싱된 구절이 없습니다. 입력 형식을 확인해주세요.")
        return

    print(f"총 {len(passages)}개 구절을 로드했습니다.")
    for p in passages:
        print(f"  [{p.label}] {p.original} ({len(p.original)}자)")

    # Generate PDF
    config = Config()
    generator = AnalectsTracingPDF(config, str(font_path))
    generator.generate(passages, args.output)


if __name__ == "__main__":
    main()
