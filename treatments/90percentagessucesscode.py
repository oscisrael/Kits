# porsche_service_parser.py
# דורש: pip install pymupdf
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple

import fitz  # PyMuPDF
import numpy as np


SERVICE_NAMES_INSPECTION = [
    "service_30000",
    "service_45000",
    "service_60000",
    "service_90000",
    "service_120000",
    "service_180000",
    "service_time_dependent",
]


@dataclass
class Word:
    x0: float; y0: float; x1: float; y1: float; text: str


@dataclass
class WidgetBox:
    x0: float; y0: float; x1: float; y1: float
    page_index: int


def words_to_lines(words: List[Word], y_tol: float = 1.8) -> List[Tuple[float, str]]:
    """מאחד מילים לפי קירבת Y לשורה אחת; מחזיר [(y_center, text)]"""
    words = sorted(words, key=lambda w: (w.y0, w.x0))
    lines: List[Tuple[float, List[str]]] = []
    for w in words:
        if not lines:
            lines.append(((w.y0 + w.y1) / 2.0, [w.text]))
            continue
        y, toks = lines[-1]
        if abs(((w.y0 + w.y1) / 2.0) - y) <= y_tol:
            toks.append(w.text)
        else:
            lines[-1] = (y, toks)
            lines.append(((w.y0 + w.y1) / 2.0, [w.text]))
    return [(y, " ".join(toks).strip()) for y, toks in lines]


def extract_task_lines(page: fitz.Page) -> List[Tuple[float, str]]:
    """מחלץ את שורות ה'Measures' בלבד, ומסנן כותרות/קטגוריות."""
    words_raw = page.get_text("words")
    words = [Word(*w[:4], w[4]) for w in words_raw]

    # מצא את y של המילה 'Measures' לעוגן
    anchor_y = None
    for w in words:
        if w.text.strip().lower() == "measures":
            anchor_y = (w.y0 + w.y1) / 2.0
            break
    # אם לא מצאנו, נסתמך על כל הטקסט – נסנן בהמשך ע"פ שדות הטופס
    all_lines = words_to_lines(words)

    # סינון כותרות ברורות
    drop_prefixes = ("Electrics", "Inside", "Outside", "Under the vehicle",
                     "Engine compartment", "Test drive", "Additional work")
    task_lines = []
    for y, txt in all_lines:
        if anchor_y is not None and y < anchor_y:
            continue
        if any(txt.startswith(p) for p in drop_prefixes):
            continue
        if not txt or len(txt) < 3:
            continue
        task_lines.append((y, txt))
    return task_lines


def extract_widget_boxes(page: fitz.Page, page_index: int) -> List[WidgetBox]:
    """אוסף מיקומי תיבות הסימון מתוך שדות הטופס (widgets)."""
    boxes: List[WidgetBox] = []
    for w in (page.widgets() or []):
        r: fitz.Rect = w.rect
        boxes.append(WidgetBox(r.x0, r.y0, r.x1, r.y1, page_index))
    return boxes


def cluster_columns(xs: List[float], min_gap: float = 8.0) -> List[float]:
    """ממיין את מרכזי ה-X ומאחד עמודות קרובות ל-x אחד (מרחק>min_gap)."""
    xs = sorted(xs)
    if not xs:
        return []
    cols = [xs[0]]
    for x in xs[1:]:
        if abs(x - cols[-1]) >= min_gap:
            cols.append(x)
    return cols


def assign_tasks_to_columns(task_lines: List[Tuple[float, str]],
                            widgets: List[WidgetBox],
                            y_pad: float = 2.2) -> Dict[float, List[str]]:
    """
    משייך משימות לעמודות לפי קרבת Y לכל תיבת סימון,
    ואז מרכז את כל ה-X-ים לעמודות ממוינות.
    """
    # קודם: אסוף מרכזי X/Y של כל תיבות הסימון שנמצאות מימין לטקסט
    xs = []
    row_hits = []  # (x_center, y_center, text)
    for (y, text) in task_lines:
        # מצא כל widget שנופל ברצועת Y של השורה
        hits = []
        for wb in widgets:
            wy = (wb.y0 + wb.y1) / 2.0
            if y - y_pad <= wy <= y + y_pad:
                hits.append(wb)
        if not hits:
            continue
        for wb in hits:
            wx = (wb.x0 + wb.x1) / 2.0
            xs.append(wx)
            row_hits.append((wx, (wb.y0 + wb.y1) / 2.0, text))

    col_centers = cluster_columns(xs, min_gap=8.0)
    # מיפוי x→טעינה של עמודה הקרובה
    def nearest_col(x):
        return min(col_centers, key=lambda c: abs(c - x)) if col_centers else None

    col_map: Dict[float, List[str]] = defaultdict(list)
    for wx, wy, text in row_hits:
        c = nearest_col(wx)
        if c is None:
            continue
        if not col_map[c] or col_map[c][-1] != text:
            col_map[c].append(text)
    return dict(sorted(col_map.items(), key=lambda kv: kv[0]))


def parse_oil(oil_pdf: str) -> List[str]:
    doc = fitz.open(oil_pdf)
    col_to_tasks: Dict[float, List[str]] = defaultdict(list)
    for i, page in enumerate(doc):
        task_lines = extract_task_lines(page)
        widgets = extract_widget_boxes(page, i)
        page_map = assign_tasks_to_columns(task_lines, widgets)
        # OIL: יש עמודת טיפול אחת – ניקח את הימנית ביותר
        if page_map:
            rightmost = max(page_map.keys())
            col_to_tasks[rightmost].extend(page_map[rightmost])
    # דה-דופ
    seen, out = set(), []
    for t in sum(col_to_tasks.values(), []):
        if t not in seen:
            out.append(t)
            seen.add(t)
    return out


def parse_inspection(insp_pdf: str) -> Dict[str, List[str]]:
    doc = fitz.open(insp_pdf)
    # אוספים מכל העמודים, ואז ממפים משמאל לימין ל-7 השירותים
    all_cols: Dict[float, List[str]] = defaultdict(list)
    for i, page in enumerate(doc):
        task_lines = extract_task_lines(page)
        widgets = extract_widget_boxes(page, i)
        page_map = assign_tasks_to_columns(task_lines, widgets)
        for x, lst in page_map.items():
            all_cols[x].extend(lst)

    # מיין משמאל לימין, מיפוי לשמות
    sorted_cols = sorted(all_cols.items(), key=lambda kv: kv[0])
    result = {k: [] for k in SERVICE_NAMES_INSPECTION}
    for idx, (_, tasks) in enumerate(sorted_cols[:len(SERVICE_NAMES_INSPECTION)]):
        seen, uniq = set(), []
        for t in tasks:
            if t not in seen:
                uniq.append(t); seen.add(t)
        result[SERVICE_NAMES_INSPECTION[idx]] = uniq
    return result


def build_services_json(oil_pdf: str, insp_pdf: str) -> Dict[str, List[str]]:
    data = {
        "service_15000": [],
        "service_30000": [],
        "service_45000": [],
        "service_60000": [],
        "service_90000": [],
        "service_120000": [],
        "service_180000": [],
        "service_time_dependent": [],
    }
    data["service_15000"] = parse_oil(oil_pdf)
    insp = parse_inspection(insp_pdf)
    data.update(insp)
    return data


if __name__ == "__main__":
    oil = "PDF Files/Oil Maintenance.pdf"
    insp = "PDF Files/Inspection.pdf"
    out = build_services_json(oil, insp)
    with open("porsche_services.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("✅ wrote porsche_services.json")
