import fitz  # PyMuPDF
import json
from collections import defaultdict
import os
import sys
import glob
import numpy as np
import re

CATEGORY_WORDS = {
    "Electrics", "Inside", "the", "vehicle", "Outside",
    "Under", "Engine", "compartment", "Additional",
    "work", "every", "years", "Test", "drive", "2",
    "Measures"
}

SERVICE_ORDER = [
    "service_15000",
    "service_30000",
    "service_45000",
    "service_60000",
    "service_90000",
    "service_120000",
    "service_180000",
    "service_240000",
    "service_time_dependent"
]


def clean_with_category_logic(text: str) -> str:
    """נקה טקסט מקטגוריות מיותרות"""
    words = text.split()
    while words:
        first_word = words[0]
        if not first_word:
            words = words[1:]
            continue
        first_char = first_word[0]
        if not first_char.isupper() and not first_char.isdigit():
            words = words[1:]
            continue
        if first_word in CATEGORY_WORDS:
            words = words[1:]
            continue
        break
    return " ".join(words)


def is_junk_full(text: str) -> bool:
    """בדוק אם הטקסט הוא זבל"""
    junk = ["Name Date", "Licence No", "Vehicle Ident", "Order No", "WP0ZZZ", "Mileage", "Date"]
    return any(j in text for j in junk)


def is_real_date(text: str) -> bool:
    """בדוק אם זה תאריך אמיתי"""
    text = text.strip()
    date_pattern = r'^\d{1,2}/\d{1,2}/\d{2,4}$'
    return bool(re.match(date_pattern, text))


def find_measures_position(page):
    """מצא את מיקום Measures"""
    for word_info in page.get_text("words"):
        x0, y0, x1, y1, txt, _, _, _ = word_info
        if txt == "Measures":
            return x0, (y0 + y1) / 2.0
    category_positions = []
    for word_info in page.get_text("words"):
        x0, y0, x1, y1, txt, _, _, _ = word_info
        if txt in CATEGORY_WORDS:
            category_positions.append((x0, (y0 + y1) / 2.0))
    if category_positions:
        max_pos = max(category_positions, key=lambda p: p[0])
        return max_pos
    return 0, 0


def extract_vertical_sections(page, measures_x_pos):
    """
    מחזיר רשימת כותרות אנכיות (SECTION) שנמצאות מימין ל-measures_x_pos,
    הן טקסטים עם סיבוב 90 מעלות בערך.
    """
    vertical_sections = []
    text_dict = page.get_text("dict")
    for block in text_dict["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                bbox = span["bbox"]  # [x0, y0, x1, y1]
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]

                text = span["text"].strip()
                if not text:
                    continue

                # בדיקת כיוון אנכי - יחס גבוה בין height ל-width (טקסט מאונך)
                if height > width * 3:
                    # בדוק שהטקסט נמצא מימין ל-measures_x_pos עם טווח סף של 20 נקודות
                    if bbox[0] < measures_x_pos + 20:
                        continue

                    vertical_sections.append({
                        "text": text,
                        "x": bbox[0],
                        "y": bbox[1]
                    })

    # מיון לפי y מהנמוך לגבוה
    vertical_sections.sort(key=lambda x: x["y"])
    return vertical_sections


def extract_checkboxes_with_y_ranges(pdf_path: str):
    """
    חילוץ הטקסטים עם טווחי Y מדויקים ותיוג לפי SECTION מאונך.
    """
    doc = fitz.open(pdf_path)
    all_items = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        measures_x, measures_y = find_measures_position(page)
        vertical_sections = extract_vertical_sections(page, measures_x)

        # חילוץ קופסאות סימון (checkboxes)
        checkboxes = []
        for w in page.widgets():
            rect = w.rect
            width = rect.x1 - rect.x0
            height = rect.y1 - rect.y0
            if width > 0 and height > 0:
                ratio = height / width
                if 0.8 < ratio < 1.2 and 10 < width < 20:
                    cb_y = (rect.y0 + rect.y1) / 2.0
                    cb_x = (rect.x0 + rect.x1) / 2.0
                    if cb_y > measures_y:
                        checkboxes.append({
                            "x": cb_x,
                            "y": cb_y
                        })

        # חילוץ מילים מתאימות עם מיקום Y למעלה מ-measures
        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            y_center = (y0 + y1) / 2.0
            if x0 < measures_x or y_center < measures_y:
                continue
            words.append({"text": txt, "y": y_center, "x": x0})

        # מיפוי מילים לקופסאות לפי טווחי Y
        def find_checkbox_for_text(text_y, checkboxes):
            for idx, cb in enumerate(checkboxes):
                # נרשה שוליים של ±10
                if abs(cb["y"] - text_y) < 10:
                    return idx
            return None

        words_by_checkbox = defaultdict(list)
        for word in words:
            cb_idx = find_checkbox_for_text(word["y"], checkboxes)
            if cb_idx is not None:
                words_by_checkbox[cb_idx].append(word["text"])

        for cb_idx, word_list in words_by_checkbox.items():
            if word_list:
                full_text = " ".join(word_list)
                cleaned = clean_with_category_logic(full_text.strip())
                if not cleaned or len(cleaned) < 10:
                    cleaned = full_text.strip()
                if cleaned and not is_junk_full(cleaned):
                    # מציאת ה-SECTION המתאים לפי y של קופסא
                    cb_y = checkboxes[cb_idx]["y"]
                    assigned_section = None
                    for i, section in enumerate(vertical_sections):
                        next_y = vertical_sections[i + 1]["y"] if i + 1 < len(vertical_sections) else None
                        if next_y is None:
                            if cb_y >= section["y"]:
                                assigned_section = section["text"]
                        else:
                            if section["y"] <= cb_y < next_y:
                                assigned_section = section["text"]
                    all_items.append({
                        "text": cleaned,
                        "y": cb_y,
                        "x": checkboxes[cb_idx]["x"],
                        "page": page_num,
                        "section": assigned_section,
                        "checkbox_id": cb_idx
                    })

    doc.close()
    return all_items


def map_services_intersection_based(pdf_path: str, text_data, service_type: str):
    """
    מיפוי מבוסס נקודות חיתוך - סורק את כל הדפים לחיפוש עמודות service
    """
    doc = fitz.open(pdf_path)
    all_checkboxes_by_x = defaultdict(list)

    for page_num in range(len(doc)):
        page = doc[page_num]
        measures_x, measures_y = find_measures_position(page)
        for w in page.widgets():
            rect = w.rect
            width = rect.x1 - rect.x0
            height = rect.y1 - rect.y0
            if width > 0 and height > 0:
                ratio = height / width
                if 0.7 < ratio < 1.3 and 8 < width < 25:
                    cb_y = (rect.y0 + rect.y1) / 2.0
                    cb_x = (rect.x0 + rect.x1) / 2.0
                    if cb_y > measures_y:
                        all_checkboxes_by_x[round(cb_x, 1)].append(cb_x)
    service_x_list = sorted(all_checkboxes_by_x.keys())

    # Extract all text blocks from the first page for headers
    first_page = doc[0]
    measures_x, measures_y = find_measures_position(first_page)
    text_dict = first_page.get_text("dict")
    all_text = []
    for block in text_dict["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"].strip()
                if not text:
                    continue
                bbox = span["bbox"]
                x_center = (bbox[0] + bbox[2]) / 2.0
                y_center = (bbox[1] + bbox[3]) / 2.0
                all_text.append({"text": text, "x": x_center, "y": y_center})

    service_cols = {}
    for sx in service_x_list:
        header_words = []
        for item in all_text:
            if item["y"] < measures_y and abs(item["x"] - sx) < 15:
                header_words.append(item["text"])
        header = " ".join(header_words[:8])
        service_cols[sx] = header

    first_service_x = min(service_x_list) if service_x_list else 0
    model_x_positions = []  # Logic for model x positions can be added here if needed

    final_mapping = defaultdict(lambda: defaultdict(list))

    for item in text_data:
        item_x = item["x"]
        item_y = item["y"]
        item_section = item.get("section")
        service = None
        # Find closest service x position for each item
        if service_x_list:
            closest_sx = min(service_x_list, key=lambda x: abs(item_x - x))
            if abs(item_x - closest_sx) < 20:
                # Map from header text to service keys by heuristic:
                header_text = service_cols.get(closest_sx, "").lower()
                if "240 tkm" in header_text or "160 tmls" in header_text:
                    service = "service_240000"
                elif "180 tkm" in header_text or "120 tmls" in header_text:
                    service = "service_180000"
                elif "120 tkm" in header_text or "80 tmls" in header_text:
                    service = "service_120000"
                elif "90 tkm" in header_text or "60 tmls" in header_text:
                    service = "service_90000"
                elif "60 tkm" in header_text or "40 tmls" in header_text:
                    service = "service_60000"
                elif "45 tkm" in header_text or "30 tmls" in header_text:
                    service = "service_45000"
                elif "30 tkm" in header_text or "20 tmls" in header_text:
                    service = "service_30000"
                elif "15 tkm" in header_text or "10 tmls" in header_text:
                    service = "service_15000"
                elif "time-dependent" in header_text:
                    service = "service_time_dependent"
        if not service:
            continue

        # Use section text as a prefix to organize
        section_key = item_section if item_section else "General"
        final_mapping[service][section_key].append(item["text"])

    doc.close()

    # Convert defaultdict to normal dicts for output
    final_result = {}
    for service, sections in final_mapping.items():
        final_result[service] = {}
        for section, items in sections.items():
            final_result[service][section] = list(sorted(set(items)))  # Unique items

    return final_result
