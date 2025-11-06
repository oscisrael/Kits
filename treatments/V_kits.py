# -*- coding: utf-8 -*-

# kits_extractor_FIXED_COLUMNS_FROM_PAGE1.py

# 🔥 גרסה תוקנת: חלץ עמודות מעמוד 1 בלבד, השתמש בהן בכל הדפים!

from dataclasses import dataclass
from typing import List, Dict, Tuple
import fitz
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


def find_measures_position(page):
    """מצא את מיקום Measures"""
    for word_info in page.get_text("words"):
        x0, y0, x1, y1, txt, _, _, _ = word_info
        if txt == "Measures":
            return x0, (y0 + y1) / 2.0
    return 0, 0


# ============================================================================
# 🆕 NEW: find_background_boundary_v3
# ============================================================================

def find_background_boundary_v3(img, pixel_x, pixel_y, direction="up"):
    """זהה את הגבול של הרקע"""
    img_height = img.shape[0]
    boundary_pixel = None

    if direction == "up":
        step = -1
        start = pixel_y
        end = max(0, pixel_y - 150)
    else:
        step = 1
        start = pixel_y
        end = min(img_height, pixel_y + 150)

    py = start
    stage = 0

    while (direction == "up" and py >= end) or (direction == "down" and py <= end):
        r, g, b = img[py, pixel_x]
        rgb_avg = (int(r) + int(g) + int(b)) // 3

        if stage == 0:
            if rgb_avg < 240:
                stage = 1
        elif stage == 1:
            if rgb_avg >= 200:
                stage = 2
        elif stage == 2:
            if rgb_avg < 200:
                boundary_pixel = py
                break

        py += step

    return boundary_pixel


# ============================================================================
# 🆕 NEW: Extract service columns from FIRST PAGE ONLY
# ============================================================================

def extract_service_columns_from_page1(doc, pdf_path):
    """
    🎯 חלץ עמודות service מעמוד 1 בלבד!
    חזור עם מיפוי: header_x → {service, text}
    """
    first_page = doc[0]
    page_rect = first_page.rect

    measures_x, measures_y = find_measures_position(first_page)

    print(f"\n{'=' * 130}")
    print(f"📊 EXTRACTING SERVICE COLUMNS FROM PAGE 1 ONLY")
    print(f"{'=' * 130}\n")
    print(f"Measures Y: {measures_y:.1f}\n")

    # חלץ כל טקסט מעל Measures
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

                if y_center >= measures_y - 50:
                    continue

                all_text.append({"text": text, "x": x_center, "y": y_center})

    # סנן רק service headers
    service_headers = []
    for item in all_text:
        if any(kw in item["text"] for kw in ["tkm", "tmls", "years", "Time", "Every"]):
            service_headers.append(item)

    # זהה service לכל header
    column_mapping = {}  # header_x → service_name

    print(f"{'Header X':>15} {'Service':>20} {'Header Text':>80}")
    print("-" * 130)

    for header in sorted(service_headers, key=lambda x: x['x']):
        h_x = header['x']
        h_text = header['text']
        service = identify_service_from_text(h_text)

        if service is None:
            service = "unknown"

        column_mapping[h_x] = {
            'service': service,
            'text': h_text
        }

        text_display = h_text[:80]
        print(f"{h_x:>15.1f} {service:>20} {text_display:>80}")

    print(f"\n✅ Extracted {len(column_mapping)} service columns\n")

    return column_mapping


def identify_service_from_text(text):
    """זהה service מ-text"""
    text_lower = text.lower()

    if "15" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_15000"
    elif "30" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_30000"
    elif "45" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_45000"
    elif "60" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_60000"
    elif "90" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_90000"
    elif "120" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_120000"
    elif "180" in text_lower and ("tkm" in text_lower or "tmls" in text_lower):
        return "service_180000"
    elif "time" in text_lower and "dependent" in text_lower:
        return "service_time_dependent"

    return None


# ============================================================================
# 🆕 NEW: Calculate checkbox Y-ranges from page
# ============================================================================

def calculate_checkbox_y_ranges(page, pdf_path, measures_y):
    """חשב Y-ranges של checkboxes"""

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
                    checkboxes.append({"x": cb_x, "y": cb_y})

    # Dedup
    unique = []
    for cb in checkboxes:
        is_dup = False
        for existing in unique:
            if abs(cb["x"] - existing["x"]) < 1.0 and abs(cb["y"] - existing["y"]) < 1.0:
                is_dup = True
                break
        if not is_dup:
            unique.append(cb)

    checkboxes = sorted(unique, key=lambda c: (c["y"], c["x"]))

    # Convert PDF to image
    page_rect = page.rect
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img_height = pix.height
    img_width = pix.width

    # Calculate Y-ranges
    checkbox_ranges = []

    for i, cb in enumerate(checkboxes):
        pixel_x = int((cb["x"] / page_rect.width) * img_width)
        pixel_y = int((cb["y"] / page_rect.height) * img_height)

        top_pixel = find_background_boundary_v3(img, pixel_x, pixel_y, direction="up")
        bottom_pixel = find_background_boundary_v3(img, pixel_x, pixel_y, direction="down")

        if top_pixel is None:
            top_pixel = pixel_y
        if bottom_pixel is None:
            bottom_pixel = pixel_y

        top_pdf_y = (top_pixel / img_height) * page_rect.height
        bottom_pdf_y = (bottom_pixel / img_height) * page_rect.height

        checkbox_ranges.append({
            'checkbox_id': i,
            'checkbox_y': cb['y'],
            'checkbox_x': cb['x'],
            'y_top': top_pdf_y,
            'y_bottom': bottom_pdf_y
        })

    return checkbox_ranges


def find_checkbox_for_text(text_y, checkbox_ranges):
    """מצא checkbox לטקסט"""
    for cb_range in checkbox_ranges:
        if cb_range['y_top'] <= text_y <= cb_range['y_bottom']:
            return cb_range['checkbox_id']
    return None


def find_closest_column(text_x, column_mapping):
    """מצא עמודת service הקרובה ביותר לטקסט"""
    if not column_mapping:
        return None

    closest_x = min(column_mapping.keys(), key=lambda x: abs(text_x - x))
    return column_mapping[closest_x]['service']


# ============================================================================
# 🆕 MAIN EXTRACTION - FIXED
# ============================================================================

def extract_treatments_all_pages(pdf_path, column_mapping):
    """
    🎯 חלץ טקסט מכל הדפים באמצעות FIXED column_mapping מעמוד 1
    """
    doc = fitz.open(pdf_path)
    all_items = []

    print(f"\n{'=' * 130}")
    print(f"📄 EXTRACTING TREATMENTS FROM ALL PAGES")
    print(f"{'=' * 130}\n")

    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"📄 Page {page_num + 1}/{len(doc)}")

        measures_x, measures_y = find_measures_position(page)

        # Calculate Y-ranges for THIS page
        checkbox_ranges = calculate_checkbox_y_ranges(page, pdf_path, measures_y)

        if not checkbox_ranges:
            print(f"  ⚠️ No checkboxes on page {page_num + 1}, skipping\n")
            continue

        # חלץ מילים
        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            y_center = (y0 + y1) / 2.0

            if x0 < measures_x or y_center < measures_y:
                continue

            words.append({"text": txt, "y": y_center, "x": x0})

        # Assign words to checkboxes
        words_by_checkbox = defaultdict(list)

        for word in words:
            checkbox_id = find_checkbox_for_text(word["y"], checkbox_ranges)
            if checkbox_id is not None:
                words_by_checkbox[checkbox_id].append(word["text"])

        # Extract text for each checkbox
        for checkbox_id, word_list in words_by_checkbox.items():
            if word_list:
                full_text = " ".join(word_list)
                cleaned = clean_with_category_logic(full_text.strip())

                if not cleaned or len(cleaned) < 10:
                    if word_list:
                        cleaned = full_text.strip()

                if cleaned and not is_junk_full(cleaned):
                    cb_range = checkbox_ranges[checkbox_id]

                    all_items.append({
                        "text": cleaned,
                        "y": cb_range['checkbox_y'],
                        "x": cb_range['checkbox_x'],
                        "page": page_num,
                        "checkbox_id": checkbox_id
                    })

        print(f"  ✅ Extracted {len([i for i in all_items if i['page'] == page_num])} items\n")

    doc.close()

    print(f"✅ Total items extracted: {len(all_items)}\n")

    return all_items


def check_gray_bullet_at_intersection(pdf_path, x, y, page_num=0):
    """בדוק gray bullet"""
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

    page_rect = page.rect
    img_height = pix.height
    img_width = pix.width

    pixel_x = int((x / page_rect.width) * img_width)
    pixel_y = int((y / page_rect.height) * img_height)

    x_range = 10
    y_range = 10

    gray_pixel_count = 0

    for py in range(max(0, pixel_y - y_range), min(img_height, pixel_y + y_range + 1)):
        for px in range(max(0, pixel_x - x_range), min(img_width, pixel_x + x_range + 1)):
            try:
                r, g, b = img[py, px]
                if 116 <= r <= 156 and 116 <= g <= 156 and 116 <= b <= 156:
                    if abs(int(r) - int(g)) < 20 and abs(int(g) - int(b)) < 20:
                        gray_pixel_count += 1
            except:
                continue

    doc.close()
    return gray_pixel_count >= 5


# ============================================================================
# 🆕 MAPPING
# ============================================================================

def map_treatments_to_services(pdf_path, treatments, column_mapping):
    """שייך טיפולים לservices לפי column_mapping"""

    print(f"\n{'=' * 130}")
    print(f"🔗 MAPPING TREATMENTS TO SERVICES")
    print(f"{'=' * 130}\n")

    final_mapping = defaultdict(lambda: defaultdict(list))

    # עבור כל treatment, מצא את ה-service הקרוב ביותר לפי X
    for treatment in treatments:
        item_x = treatment["x"]
        item_y = treatment["y"]
        item_page = treatment["page"]

        # מצא service קרוב
        service = find_closest_column(item_x, column_mapping)

        if service:
            # בדוק bullet
            has_bullet = check_gray_bullet_at_intersection(pdf_path, item_x, item_y, page_num=item_page)

            if has_bullet:
                final_mapping[service]["General"].append(treatment["text"])

    return dict(final_mapping)


def find_pdf_files(folder_path):
    """מצא PDFs"""
    all_pdfs = glob.glob(os.path.join(folder_path, "*.pdf"))

    oil_pdf = None
    inspection_pdf = None

    for pdf in all_pdfs:
        basename = os.path.basename(pdf).lower()
        if "oil" in basename:
            oil_pdf = pdf
        elif "inspection" in basename:
            inspection_pdf = pdf

    return oil_pdf, inspection_pdf


def main():
    print("=" * 130)
    print("🔥 KITS EXTRACTOR - FIXED (Columns from Page 1, Applied to All Pages)")
    print("=" * 130)

    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = input("\nEnter folder path: ").strip()

    if not os.path.isdir(folder_path):
        print(f"❌ Error: '{folder_path}' is not a valid directory!")
        sys.exit(1)

    oil_pdf, inspection_pdf = find_pdf_files(folder_path)

    if not oil_pdf and not inspection_pdf:
        print("❌ No PDFs found!")
        sys.exit(1)

    if oil_pdf:
        print(f"✅ Oil: {os.path.basename(oil_pdf)}")
    if inspection_pdf:
        print(f"✅ Inspection: {os.path.basename(inspection_pdf)}")

    output_dir = "../outputs"
    os.makedirs(output_dir, exist_ok=True)

    combined_mapping = {}

    if inspection_pdf:
        print("\n" + "=" * 130)
        print("INSPECTION")
        print("=" * 130)

        doc = fitz.open(inspection_pdf)
        column_mapping = extract_service_columns_from_page1(doc, inspection_pdf)
        doc.close()

        treatments = extract_treatments_all_pages(inspection_pdf, column_mapping)
        insp_mapping = map_treatments_to_services(inspection_pdf, treatments, column_mapping)
        combined_mapping.update(insp_mapping)

    if oil_pdf:
        print("\n" + "=" * 130)
        print("OIL MAINTENANCE")
        print("=" * 130)

        doc = fitz.open(oil_pdf)
        column_mapping = extract_service_columns_from_page1(doc, oil_pdf)
        doc.close()

        treatments = extract_treatments_all_pages(oil_pdf, column_mapping)
        oil_mapping = map_treatments_to_services(oil_pdf, treatments, column_mapping)
        combined_mapping.update(oil_mapping)

    ordered_mapping = {}
    for service in SERVICE_ORDER:
        if service in combined_mapping:
            ordered_mapping[service] = combined_mapping[service]

    output_file = os.path.join(output_dir, "combined_service_mapping.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ordered_mapping, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 130)
    print("✅ SUMMARY")
    print("=" * 130)

    for service in SERVICE_ORDER:
        if service in ordered_mapping:
            count = sum(len(items) for items in ordered_mapping[service].values())
            print(f"  {service}: {count} items")

    print(f"\n✅ Saved: {output_file}\n")


if __name__ == "__main__":
    main()
