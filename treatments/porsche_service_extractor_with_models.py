# porsche_extractor_COMPLETE.py
# גרסה סופית שעובדת על הכל!

from dataclasses import dataclass
from typing import List, Dict, Tuple
import fitz
import json
from collections import defaultdict
import os
import sys
import glob
import cv2
import numpy as np
import re


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


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

KNOWN_SERVICE_PATTERNS = [
    "Every 15 tkm",
    "Every 30 tkm",
    "Every 45 tkm",
    "Every 60 tkm",
    "Every 90 tkm",
    "Every 120 tkm",
    "Every 180 tkm",
    "Time-dependent"
]


def clean_with_category_logic(text: str) -> str:
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
    junk = ["Name Date", "Licence No", "Vehicle Ident", "Order No", "WP0ZZZ", "Mileage", "Date"]
    return any(j in text for j in junk)


def is_date(text: str) -> bool:
    """בדיקה אם הטקסט הוא תאריך"""
    if "/" in text or "-" in text:
        if any(c.isdigit() for c in text):
            return True
    return False


def find_measures_position(page):
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


def is_service_column_text(header_text):
    for pattern in KNOWN_SERVICE_PATTERNS:
        if pattern in header_text:
            return True
    return False


def extract_all_text_with_rotation(page):
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
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]

                all_text.append({
                    "text": text,
                    "x": x_center,
                    "y": y_center,
                    "width": width,
                    "height": height,
                    "bbox": bbox
                })

    return all_text


def find_vertical_model_columns(page, measures_y, first_service_x):
    """
    🔴 זיהוי 1-2 עמודות דגמים - טווח רחב יותר!
    """
    all_text = extract_all_text_with_rotation(page)

    print(f"\n  🔍 Searching for model column(s)...")
    print(f"     Measures Y: {measures_y:.1f}")
    print(f"     First service X: {first_service_x:.1f}")

    model_candidates = []

    for item in all_text:
        # תנאי 1: למעלה מ-Measures
        if item["y"] >= measures_y:
            continue

        # 🔴 תנאי 2: משמאל לעמודת service הראשונה (רק מ-X קטן יותר!)
        if item["x"] >= first_service_x:
            continue

        # תנאי 3: קרוב מספיק (עד 80 פיקסלים משמאל)
        distance_from_first_service = first_service_x - item["x"]
        if distance_from_first_service > 80:
            continue

        # 🔴 תנאי 4: לא תאריך!
        if is_date(item["text"]):
            continue

        # תנאי 5: לא מילים נפוצות
        if item["text"] in ["or", "and", "the", "/", "years", "tkm", "tmls", "->", "Every"]:
            continue

        if len(item["text"]) < 2:
            continue

        model_candidates.append({
            "text": item["text"],
            "x": item["x"],
            "y": item["y"],
            "distance_from_service": distance_from_first_service
        })

    if not model_candidates:
        print("     ⚠️ No model column text found!")
        return {}

    print(f"     Found {len(model_candidates)} candidate texts")
    for c in model_candidates[:10]:
        print(f"       \"{c['text']}\" (X={c['x']:.1f}, Y={c['y']:.1f}, dist={c['distance_from_service']:.1f})")

    # 🔴 קבץ לפי X - אם הפרש > 15 פיקסלים = עמודה נפרדת!
    grouped_by_x = {}

    for item in model_candidates:
        found_group = False
        for group_x in list(grouped_by_x.keys()):
            if abs(item["x"] - group_x) < 15:  # אותה עמודה
                grouped_by_x[group_x].append(item)
                found_group = True
                break

        if not found_group:
            grouped_by_x[item["x"]] = [item]

    print(f"     Grouped into {len(grouped_by_x)} column(s)")

    # בנה שם לכל עמודה
    model_columns = {}

    for group_x, items in grouped_by_x.items():
        # חשב X ממוצע
        avg_x = sum(i["x"] for i in items) / len(items)

        # בנה שם
        words = []
        seen = set()
        for item in items:
            txt = item["text"]
            if txt not in seen:
                words.append(txt)
                seen.add(txt)

        name = " ".join(words) if words else "Unknown Model"
        model_columns[avg_x] = name
        print(f"       Column {len(model_columns)}: X={avg_x:.1f} → \"{name}\"")

    return model_columns


def detect_dots_in_pdf(pdf_path, page_num=0):
    doc = fitz.open(pdf_path)
    page = doc[page_num]

    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    dots_in_pixels = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 50 < area < 500:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                dots_in_pixels.append((cx, cy))

    page_rect = page.rect
    img_width = pix.width
    img_height = pix.height

    dots_in_pdf = []
    for px, py in dots_in_pixels:
        pdf_x = (px / img_width) * page_rect.width
        pdf_y = (py / img_height) * page_rect.height
        dots_in_pdf.append((pdf_x, pdf_y))

    doc.close()

    return dots_in_pdf


def extract_checkboxes_and_text(pdf_path):
    doc = fitz.open(pdf_path)
    all_items = []
    seen = set()

    print(f"\n📄 Extracting checkboxes and text from: {os.path.basename(pdf_path)}")

    for page_num in range(len(doc)):
        page = doc[page_num]

        print(f"  Page {page_num + 1}...", end="")

        measures_x, measures_y = find_measures_position(page)

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
                            "y": cb_y,
                            "page": page_num + 1
                        })

        checkboxes.sort(key=lambda c: c["y"])

        unique_y = sorted(set(cb["y"] for cb in checkboxes))

        for i, cb_y in enumerate(unique_y):
            if i == 0:
                y_top = measures_y
            else:
                y_top = (unique_y[i - 1] + cb_y) / 2.0

            if i == len(unique_y) - 1:
                y_bottom = 999999
            else:
                y_bottom = (cb_y + unique_y[i + 1]) / 2.0

            for cb in checkboxes:
                if abs(cb["y"] - cb_y) < 0.5:
                    cb["y_top"] = y_top
                    cb["y_bottom"] = y_bottom

        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            y_center = (y0 + y1) / 2.0

            if x0 < measures_x or y_center < measures_y:
                continue

            words.append(Word(x0=x0, y0=y0, x1=x1, y1=y1, text=txt))

        words.sort(key=lambda w: (w.y0, w.x0))
        lines = []

        for w in words:
            if not lines:
                lines.append(((w.y0 + w.y1) / 2.0, [w.text]))
                continue
            y, toks = lines[-1]
            if abs(((w.y0 + w.y1) / 2.0) - y) <= 2:
                toks.append(w.text)
            else:
                lines.append(((w.y0 + w.y1) / 2.0, [w.text]))

        for cb in checkboxes:
            if "y_top" not in cb:
                continue

            matching_lines = []
            for ly, ltxt in lines:
                if cb["y_top"] <= ly <= cb["y_bottom"]:
                    line_text = " ".join(ltxt)
                    matching_lines.append(line_text)

            if matching_lines:
                full_text = " ".join(matching_lines)
                cleaned = clean_with_category_logic(full_text.strip())

                if cleaned and not is_junk_full(cleaned):
                    item_key = (cleaned, round(cb["y"], 2), round(cb["x"], 1), cb["page"])

                    if item_key not in seen:
                        all_items.append({
                            "text": cleaned,
                            "y": cb["y"],
                            "x": cb["x"],
                            "page": cb["page"]
                        })
                        seen.add(item_key)

        print(f" {len([i for i in all_items if i['page'] == page_num + 1])} items")

    doc.close()
    print(f"  ✅ Total: {len(all_items)} items")
    return all_items


def map_services_with_models_CV_V2(pdf_path, text_data, dots_data, service_type):
    doc = fitz.open(pdf_path)

    print(f"\n📋 Mapping with multi-column model detection + CV...")

    page = doc[0]
    measures_x, measures_y = find_measures_position(page)

    all_x = sorted(set(item["x"] for item in text_data))
    grouped_x = []

    if all_x:
        current = [all_x[0]]
        for x in all_x[1:]:
            if x - current[-1] < 5:
                current.append(x)
            else:
                grouped_x.append(sum(current) / len(current))
                current = [x]
        grouped_x.append(sum(current) / len(current))

    service_cols = {}
    first_service_x = None

    for x in grouped_x:
        all_text = extract_all_text_with_rotation(page)
        header_words = []

        for item in all_text:
            if item["y"] < measures_y and abs(item["x"] - x) < 15:
                header_words.append(item["text"])

        header = " ".join(header_words[:8])

        if is_service_column_text(header):
            service_cols[x] = header
            if first_service_x is None or x < first_service_x:
                first_service_x = x

    if not first_service_x:
        print("  ❌ No service columns found!")
        doc.close()
        return {}

    model_cols = find_vertical_model_columns(page, measures_y, first_service_x)

    print(f"\n  📊 Column identification:")
    print(f"     Model columns: {len(model_cols)}")
    for x, name in sorted(model_cols.items()):
        print(f"       X={x:.1f} → \"{name}\"")

    print(f"     Service columns: {len(service_cols)}")
    for x, name in sorted(service_cols.items()):
        print(f"       X={x:.1f} → \"{name[:50]}...\"")

    service_cols_list = sorted(service_cols.keys(), reverse=True)

    if service_type == "oil":
        x_to_service = {service_cols_list[0]: "service_15000"} if service_cols_list else {}
    else:
        x_to_service = {}
        for i, x_val in enumerate(service_cols_list):
            reverse_index = len(SERVICE_ORDER) - 1 - i
            if 1 <= reverse_index < len(SERVICE_ORDER):
                x_to_service[x_val] = SERVICE_ORDER[reverse_index]

    final_mapping = defaultdict(lambda: defaultdict(list))

    print(f"\n  🔗 Cross-referencing {len(dots_data)} CV dots with {len(model_cols)} model column(s)...")

    item_x_to_group_x = {}
    for item in text_data:
        closest = min(grouped_x, key=lambda gx: abs(gx - item["x"]))
        item_x_to_group_x[item["x"]] = closest

    for item in text_data:
        group_x = item_x_to_group_x[item["x"]]
        item_y = item["y"]

        if group_x in service_cols:
            service = x_to_service.get(group_x)
            if not service:
                continue

            # 🔴 מצא דגמים - לכל עמודת דגם בנפרד!
            applicable_models = []

            for dot_x, dot_y in dots_data:
                if abs(dot_y - item_y) < 15:
                    for model_x, model_name in model_cols.items():
                        if abs(dot_x - model_x) < 40:
                            if model_name not in applicable_models:
                                applicable_models.append(model_name)

            # 🔴 אם לא נמצאו נקודות - לא להוסיף בכלל (ולא "All")
            if not applicable_models:
                continue

            for model in applicable_models:
                if item["text"] not in final_mapping[service][model]:
                    final_mapping[service][model].append(item["text"])

    doc.close()

    result = {}
    for service, models_dict in final_mapping.items():
        result[service] = dict(models_dict)

    return result


def find_pdf_files(folder_path):
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
    print("🚗 PORSCHE EXTRACTOR - COMPLETE VERSION!")
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

        oil_text = extract_checkboxes_and_text(oil_pdf)
        oil_dots = detect_dots_in_pdf(oil_pdf)
        print(f"  🔍 CV detected {len(oil_dots)} dots")
        oil_mapping = map_services_with_models_CV_V2(oil_pdf, oil_text, oil_dots, "oil")
        combined_mapping.update(oil_mapping)

    if inspection_pdf:
        print("\n" + "=" * 80)
        print("INSPECTION")
        print("=" * 80)

        insp_text = extract_checkboxes_and_text(inspection_pdf)
        insp_dots = detect_dots_in_pdf(inspection_pdf)
        print(f"  🔍 CV detected {len(insp_dots)} dots")
        insp_mapping = map_services_with_models_CV_V2(inspection_pdf, insp_text, insp_dots, "inspection")
        combined_mapping.update(insp_mapping)

    ordered_mapping = {}
    for service in SERVICE_ORDER:
        if service in combined_mapping:
            ordered_mapping[service] = combined_mapping[service]

    output_file = os.path.join(output_dir, "911.json")
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
    print("🎉 DONE!")
    print("=" * 80)


if __name__ == "__main__":
    main()
