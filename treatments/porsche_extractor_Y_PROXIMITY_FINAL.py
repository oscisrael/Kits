# -*- coding: utf-8 -*-
# porsche_extractor_Y_PROXIMITY_FINAL.py
# 🔥 אסטרטגיה חדשה: קיבוץ מילים לפי proximity ל-checkbox - לא לפי קווי טבלה!

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


def find_service_column_x_positions(page, measures_y):
    """מצא X של עמודות service"""
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
                    checkboxes.append(cb_x)

    if not checkboxes:
        return []

    unique_x = []
    for cb_x in checkboxes:
        found = False
        for ux in unique_x:
            if abs(cb_x - ux) < 10:
                found = True
                break
        if not found:
            unique_x.append(cb_x)

    return sorted(unique_x)


def find_model_column_x_positions(page, measures_y, service_x_positions):
    """מצא X של עמודות דגמים"""
    if not service_x_positions:
        return []

    first_service_x = min(service_x_positions)

    # חלץ כל הטקסט
    all_text = []
    text_dict = page.get_text("dict")
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

    candidates = []

    for item in all_text:
        if item["y"] >= measures_y:
            continue

        if item["x"] >= first_service_x:
            continue

        distance = first_service_x - item["x"]
        if distance < 20 or distance > 100:
            continue

        if is_real_date(item["text"]):
            continue

        if item["text"] in ["or", "and", "the", "years", "tkm", "tmls", "->", "Every", "/"]:
            continue

        if len(item["text"]) < 2:
            continue

        candidates.append({"text": item["text"], "x": item["x"], "y": item["y"]})

    if not candidates:
        return []

    x_positions = []
    for item in candidates:
        found = False
        for existing_x in x_positions:
            if abs(item["x"] - existing_x) < 10:
                found = True
                break
        if not found:
            x_positions.append(item["x"])

    x_positions.sort()

    final_x_positions = []
    i = 0
    while i < len(x_positions):
        current_x = x_positions[i]

        if i + 1 < len(x_positions):
            next_x = x_positions[i + 1]
            distance = next_x - current_x

            if 15 <= distance <= 25:
                final_x_positions.append(current_x)
                final_x_positions.append(next_x)
                i += 2
                continue

        final_x_positions.append(current_x)
        i += 1

    return final_x_positions


def get_model_name_for_x(page, model_x, measures_y):
    """מצא שם לעמודת דגם"""
    text_dict = page.get_text("dict")
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

    nearby = []
    for item in all_text:
        if item["y"] >= measures_y:
            continue

        if abs(item["x"] - model_x) < 10:
            if not is_real_date(item["text"]):
                if item["text"] not in ["or", "and", "the", "years", "tkm", "tmls", "->", "Every", "/"]:
                    if len(item["text"]) >= 2:
                        nearby.append(item["text"])

    if nearby:
        unique = []
        seen = set()
        for txt in nearby:
            if txt not in seen:
                unique.append(txt)
                seen.add(txt)
        return " ".join(unique[:5])

    return f"Model Column {model_x:.0f}"


def extract_checkboxes_with_y_proximity(pdf_path):
    """
    🔥 אסטרטגיה חדשה: קיבוץ מילים לפי Y proximity ל-checkbox!
    """
    doc = fitz.open(pdf_path)
    all_items = []

    print(f"\n📄 Extracting with Y-PROXIMITY strategy: {os.path.basename(pdf_path)}")

    for page_num in range(len(doc)):
        page = doc[page_num]

        print(f"\n  📄 Page {page_num + 1}")

        measures_x, measures_y = find_measures_position(page)
        print(f"     Measures: Y={measures_y:.1f}")

        # חלץ checkboxes
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
                        checkboxes.append({"x": cb_x, "y": cb_y, "page": page_num})

        print(f"     Found {len(checkboxes)} checkboxes")

        # חלץ כל המילים עם מיקום
        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            y_center = (y0 + y1) / 2.0

            if x0 < measures_x or y_center < measures_y:
                continue

            words.append({"text": txt, "y": y_center, "x": x0})

        print(f"     Found {len(words)} words")

        # 🔥 קיבוץ מילים לפי proximity ל-checkbox!
        y_range = 30  # פיקסלים למעלה ולמטה

        for i, cb in enumerate(checkboxes):
            if i % 10 == 0:
                print(f"     Processing checkbox {i + 1}/{len(checkboxes)}...")

            # מצא את כל המילים בטווח ±30 פיקסלים מה-Y של הcheckbox
            matching_words = []
            for word in words:
                if abs(word["y"] - cb["y"]) <= y_range:
                    matching_words.append(word["text"])

            if matching_words:
                full_text = " ".join(matching_words)

                cleaned = clean_with_category_logic(full_text.strip())

                # אם clean מחק הכל, קח את הטקסט המקורי
                if not cleaned or len(cleaned) < 10:
                    if matching_words:
                        cleaned = full_text.strip()

                if cleaned and not is_junk_full(cleaned):
                    all_items.append({
                        "text": cleaned,
                        "y": cb["y"],
                        "x": cb["x"],
                        "page": cb["page"]
                    })

        print(f"     ✅ Extracted {len([i for i in all_items if i['page'] == page_num])} items from page {page_num + 1}")

    doc.close()
    print(f"\n  ✅ Total: {len(all_items)} items across all pages")

    # 🔥 הדפס סטטיסטיקות
    unique_texts = len(set(item['text'] for item in all_items))
    print(f"  📊 Unique texts: {unique_texts}")

    # מצא טקסטים ארוכים
    long_texts = [item for item in all_items if len(item['text']) > 150]
    print(f"  📊 Long texts (>150 chars): {len(set(t['text'] for t in long_texts))}")

    if long_texts:
        print(f"\n  🔍 Sample long texts:")
        shown = set()
        for item in long_texts[:3]:
            if item['text'] not in shown:
                print(f"     {item['text'][:100]}...")
                shown.add(item['text'])

    return all_items


def check_gray_bullet_at_intersection(pdf_path, x, y, page_num=0):
    """בדוק אם יש gray bullet בנקודת חיתוך"""
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
                    if abs(int(r) - int(g)) < 20 and abs(int(g) - int(b)) < 20 and abs(int(r) - int(b)) < 20:
                        gray_pixel_count += 1
            except:
                continue

    doc.close()

    return gray_pixel_count >= 5


def map_services_intersection_based(pdf_path, text_data, service_type):
    """מיפוי מבוסס נקודות חיתוך"""
    doc = fitz.open(pdf_path)

    print(f"\n📋 Mapping with INTERSECTION-BASED approach...")

    page = doc[0]
    measures_x, measures_y = find_measures_position(page)

    service_x_list = find_service_column_x_positions(page, measures_y)

    if not service_x_list:
        print("  ❌ No service columns found!")
        doc.close()
        return {}

    # חלץ כל הטקסט
    text_dict = page.get_text("dict")
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

    first_service_x = min(service_x_list)
    model_x_positions = find_model_column_x_positions(page, measures_y, service_x_list)

    if not model_x_positions:
        print("  ⚠️ No model columns found!")
        doc.close()
        return {}

    model_cols = {}
    for model_x in model_x_positions:
        name = get_model_name_for_x(page, model_x, measures_y)
        model_cols[model_x] = name

    print(f"\n  📊 Column identification:")
    print(f"     Model columns: {len(model_cols)}")
    for x, name in sorted(model_cols.items()):
        print(f"       X={x:.1f} → \"{name}\"")

    print(f"     Service columns: {len(service_cols)}")
    for x, name in sorted(service_cols.items()):
        print(f"       X={x:.1f} → \"{name[:50]}...\"")

    # מפה X לservice
    x_to_service = {}
    for x_val, header_text in service_cols.items():
        if "30 tkm" in header_text or "20 tmls" in header_text:
            x_to_service[x_val] = "service_30000"
        elif "45 tkm" in header_text or "30 tmls" in header_text:
            x_to_service[x_val] = "service_45000"
        elif "60 tkm" in header_text or "40 tmls" in header_text:
            x_to_service[x_val] = "service_60000"
        elif "90 tkm" in header_text or "60 tmls" in header_text:
            x_to_service[x_val] = "service_90000"
        elif "120 tkm" in header_text or "80 tmls" in header_text:
            x_to_service[x_val] = "service_120000"
        elif "180 tkm" in header_text or "120 tmls" in header_text:
            x_to_service[x_val] = "service_180000"
        elif "Time-dependent" in header_text:
            x_to_service[x_val] = "service_time_dependent"
        elif "15 tkm" in header_text or "10 tmls" in header_text:
            x_to_service[x_val] = "service_15000"

    print(f"\n  🗺️ Service mapping:")
    for x_val, service in sorted(x_to_service.items()):
        print(f"     X={x_val:.1f} → {service}")

    final_mapping = defaultdict(lambda: defaultdict(list))

    print(f"\n  🔗 Checking {len(text_data)} treatments across {len(set(item['page'] for item in text_data))} pages...")

    bullets_found = 0

    for item in text_data:
        item_x = item["x"]
        item_y = item["y"]
        item_page = item["page"]

        service = None
        for sx in service_x_list:
            if abs(item_x - sx) < 15:
                service = x_to_service.get(sx)
                break

        if not service:
            continue

        for model_x in model_x_positions:
            has_bullet = check_gray_bullet_at_intersection(pdf_path, model_x, item_y, page_num=item_page)

            if has_bullet:
                bullets_found += 1
                model_name = model_cols[model_x]
                if item["text"] not in final_mapping[service][model_name]:
                    final_mapping[service][model_name].append(item["text"])

    print(f"     Found {bullets_found} gray bullets at intersections")

    doc.close()

    result = {}
    for service, models_dict in final_mapping.items():
        result[service] = dict(models_dict)

    return result


def find_pdf_files(folder_path):
    """מצא קבצי PDF בתיקייה"""
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
    print("=" * 80)
    print("🔥 PORSCHE EXTRACTOR - Y-PROXIMITY FINAL!")
    print("=" * 80)

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

    if oil_pdf:
        print("\n" + "=" * 80)
        print("OIL MAINTENANCE")
        print("=" * 80)

        oil_text = extract_checkboxes_with_y_proximity(oil_pdf)
        oil_mapping = map_services_intersection_based(oil_pdf, oil_text, "oil")
        combined_mapping.update(oil_mapping)

    if inspection_pdf:
        print("\n" + "=" * 80)
        print("INSPECTION")
        print("=" * 80)

        insp_text = extract_checkboxes_with_y_proximity(inspection_pdf)
        insp_mapping = map_services_intersection_based(inspection_pdf, insp_text, "inspection")
        combined_mapping.update(insp_mapping)

    ordered_mapping = {}
    for service in SERVICE_ORDER:
        if service in combined_mapping:
            ordered_mapping[service] = combined_mapping[service]

    output_file = os.path.join(output_dir, "combined_service_mapping_with_models.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ordered_mapping, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    for service in SERVICE_ORDER:
        if service in ordered_mapping:
            print(f"\n🔧 {service}:")
            for model, items in ordered_mapping[service].items():
                print(f"  📋 {model[:60]}: {len(items)} items")

    print(f"\n✅ Saved: {output_file}")
    print("\n" + "=" * 80)
    print("🎉 DONE - Y-PROXIMITY CAPTURES ALL MULTILINE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
