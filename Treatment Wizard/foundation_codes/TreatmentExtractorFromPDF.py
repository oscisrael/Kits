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


# ============================================================================
# 🆕 NEW: find_background_boundary_v3 - יהיה חלק מהקוד!
# ============================================================================

def find_background_boundary_v3(img, pixel_x, pixel_y, direction="up"):
    """
    זהה את הגבול של הרקע (BACKGROUND EDGE):
    1. דלג על WHITE (checkbox עצמו)
    2. דלג על GRAY (מסגרת)
    3. היכנס ל-LIGHT_GRAY (רקע)
    4. עצור כשיוצאים מ-LIGHT_GRAY
    """
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
    # stage 0: WHITE (255)
    # stage 1: GRAY (150-240)
    # stage 2: LIGHT_GRAY (200+) - the background
    # stage 3: exit background ← STOP HERE

    while (direction == "up" and py >= end) or (direction == "down" and py <= end):
        r, g, b = img[py, pixel_x]
        rgb_avg = (int(r) + int(g) + int(b)) // 3

        if stage == 0:  # Looking for WHITE zone
            if rgb_avg < 240:
                stage = 1

        elif stage == 1:  # In GRAY/medium zone
            if rgb_avg >= 200:  # Entered LIGHT zone (background)
                stage = 2

        elif stage == 2:  # In LIGHT_GRAY zone (background)
            if rgb_avg < 200:  # LEFT background! ← This is the boundary!
                boundary_pixel = py
                break

        py += step

    return boundary_pixel


# ============================================================================
# 🆕 NEW: calculate_checkbox_y_ranges
# ============================================================================

def calculate_checkbox_y_ranges(page, pdf_path):
    """
    🎯 חשב את ה-Y-ranges המדויקים לכל checkbox
    באמצעות find_background_boundary_v3
    """
    measures_x, measures_y = find_measures_position(page)

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
                    checkboxes.append({"x": cb_x, "y": cb_y})

    # Convert PDF to image
    page_rect = page.rect
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img_height = pix.height
    img_width = pix.width

    # Calculate Y-ranges for each checkbox
    checkbox_ranges = []

    for i, cb in enumerate(checkboxes):
        # Convert PDF coords to image pixel coords
        pixel_x = int((cb["x"] / page_rect.width) * img_width)
        pixel_y = int((cb["y"] / page_rect.height) * img_height)

        # Find boundaries using three-zone approach
        top_pixel = find_background_boundary_v3(img, pixel_x, pixel_y, direction="up")
        bottom_pixel = find_background_boundary_v3(img, pixel_x, pixel_y, direction="down")

        if top_pixel is None:
            top_pixel = pixel_y
        if bottom_pixel is None:
            bottom_pixel = pixel_y

        # Convert back to PDF coordinates
        top_pdf_y = (top_pixel / img_height) * page_rect.height
        bottom_pdf_y = (bottom_pixel / img_height) * page_rect.height

        checkbox_ranges.append({
            'checkbox_id': i,
            'checkbox_y': cb['y'],
            'checkbox_x': cb['x'],
            'y_top': top_pdf_y,
            'y_bottom': bottom_pdf_y,
            'range_height': bottom_pdf_y - top_pdf_y
        })

    return checkbox_ranges


# ============================================================================
# 🆕 NEW: find_checkbox_for_text
# ============================================================================

def find_checkbox_for_text(text_y, checkbox_ranges):
    """
    מצא איזה checkbox טקסט זה שייך אליו
    בהתאם ל-Y-ranges המדויקים
    """
    for cb_range in checkbox_ranges:
        if cb_range['y_top'] <= text_y <= cb_range['y_bottom']:
            return cb_range['checkbox_id']
    return None


def extract_checkboxes_with_y_ranges(pdf_path):
    """
    🎯 חדש: קיבוץ מילים לפי Y-RANGES גיאומטריים!
    (לא ±30 pixels אלא ranges אמיתיים מ-find_background_boundary_v3)
    """
    doc = fitz.open(pdf_path)
    all_items = []

    print(f"\n📄 Extracting with Y-RANGES GEOMETRIC: {os.path.basename(pdf_path)}")

    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"\n 📄 Page {page_num + 1}")

        measures_x, measures_y = find_measures_position(page)
        print(f" Measures: Y={measures_y:.1f}")

        # 🆕 Calculate Y-ranges using three-zone approach
        checkbox_ranges = calculate_checkbox_y_ranges(page, pdf_path)
        print(f" Calculated {len(checkbox_ranges)} checkbox Y-ranges")

        for i, cb_range in enumerate(checkbox_ranges):
            print(
                f"  CB {i}: Y-range [{cb_range['y_top']:.1f}, {cb_range['y_bottom']:.1f}] (height: {cb_range['range_height']:.1f})")

        # חלץ כל המילים עם מיקום
        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            y_center = (y0 + y1) / 2.0

            if x0 < measures_x or y_center < measures_y:
                continue

            words.append({"text": txt, "y": y_center, "x": x0})

        print(f" Found {len(words)} words")

        # 🆕 Assign words to checkboxes by exact Y-ranges
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

                # If clean deleted everything, take original
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

        print(f" ✅ Extracted {len([i for i in all_items if i['page'] == page_num])} items from page {page_num + 1}")

    doc.close()

    print(f"\n ✅ Total: {len(all_items)} items across all pages")

    # Print statistics
    unique_texts = len(set(item['text'] for item in all_items))
    print(f" 📊 Unique texts: {unique_texts}")

    long_texts = [item for item in all_items if len(item['text']) > 150]
    print(f" 📊 Long texts (>150 chars): {len(set(t['text'] for t in long_texts))}")

    if long_texts:
        print(f"\n 🔍 Sample long texts:")
        shown = set()
        for item in long_texts[:3]:
            if item['text'] not in shown:
                print(f" {item['text'][:100]}...")
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
    """מיפוי מבוסס נקודות חיתוך - סורק את כל הדפים לחיפוש עמודות service"""
    doc = fitz.open(pdf_path)
    print(f"\n📋 Mapping with INTERSECTION-BASED approach (ALL PAGES)...")

    # 🔥 סרוק את כל הדפים לחיפוש checkboxes!
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

    # קבץ לפי X position
    service_x_list = sorted(all_checkboxes_by_x.keys())

    print(f"\n✅ Found {len(service_x_list)} unique service columns across ALL pages:")
    print(f"{'Service X':>15}")
    print("-" * 20)

    for x in service_x_list:
        print(f"{x:>15.1f}")

    # Take first page for text extraction
    first_page = doc[0]
    measures_x, measures_y = find_measures_position(first_page)

    # Extract all text
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

    model_x_positions = find_model_column_x_positions(first_page, measures_y, service_x_list)

    if not model_x_positions:
        print(" ⚠️ No model columns found!")
        doc.close()
        return {}

    model_cols = {}
    for model_x in model_x_positions:
        name = get_model_name_for_x(first_page, model_x, measures_y)
        model_cols[model_x] = name

    print(f"\n 📊 Column identification:")
    print(f" Model columns: {len(model_cols)}")
    for x, name in sorted(model_cols.items()):
        print(f" X={x:.1f} → \"{name}\"")

    print(f" Service columns: {len(service_cols)}")
    for x, name in sorted(service_cols.items()):
        print(f" X={x:.1f} → \"{name[:50]}...\"")

    # Map X to service
    x_to_service = {}
    for x_val, header_text in service_cols.items():
        if "240 tkm" in header_text or "160 tmls" in header_text:
            x_to_service[x_val] = "service_240000"
        elif "180 tkm" in header_text or "120 tmls" in header_text:
            x_to_service[x_val] = "service_180000"
        elif "120 tkm" in header_text or "80 tmls" in header_text:
            x_to_service[x_val] = "service_120000"
        elif "90 tkm" in header_text or "60 tmls" in header_text:
            x_to_service[x_val] = "service_90000"
        elif "60 tkm" in header_text or "40 tmls" in header_text:
            x_to_service[x_val] = "service_60000"
        elif "45 tkm" in header_text or "30 tmls" in header_text:
            x_to_service[x_val] = "service_45000"
        elif "30 tkm" in header_text or "20 tmls" in header_text:  #
            x_to_service[x_val] = "service_30000"
        elif "15 tkm" in header_text or "10 tmls" in header_text:
            x_to_service[x_val] = "service_15000"
        elif "Time-dependent" in header_text or "time-dependent" in header_text.lower():
            x_to_service[x_val] = "service_time_dependent"

    print(f"\n 🗺️ Service mapping:")
    for x_val, service in sorted(x_to_service.items()):
        print(f" X={x_val:.1f} → {service}")

    print(f"\n 🗺️ Service mapping:")
    for x_val, service in sorted(x_to_service.items()):
        print(f" X={x_val:.1f} → {service}")


    final_mapping = defaultdict(lambda: defaultdict(list))

    print(f"\n 🔗 Checking {len(text_data)} treatments across {len(set(item['page'] for item in text_data))} pages...")

    bullets_found = 0

    for item in text_data:
        item_x = item["x"]
        item_y = item["y"]
        item_page = item["page"]

        service = None
        for sx in service_x_list:
            closest_sx = min(service_x_list, key=lambda x: abs(item_x - x))
            min_distance = abs(item_x - closest_sx)
            if min_distance < 20:  # רק אם קרוב מספיק
                service = x_to_service.get(closest_sx)
            else:
                service = None

        if not service:
            continue

        for model_x in model_x_positions:
            has_bullet = check_gray_bullet_at_intersection(pdf_path, model_x, item_y, page_num=item_page)

            if has_bullet:
                bullets_found += 1
                model_name = model_cols[model_x]

                if item["text"] not in final_mapping[service][model_name]:
                    final_mapping[service][model_name].append(item["text"])

    print(f" Found {bullets_found} gray bullets at intersections")

    doc.close()

    result = {}
    # Build result with original headers
    result = {}
    service_to_original_header = {}

    # Create mapping from normalized key to original header
    for x_val in service_cols.keys():
        normalized_key = x_to_service.get(x_val)
        if normalized_key:
            original_header = service_cols[x_val]
            service_to_original_header[normalized_key] = original_header

    # Build result with metadata
    for service, models_dict in final_mapping.items():
        result[service] = {
            "original_header": service_to_original_header.get(service, service),
            "items": dict(models_dict)
        }

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
    print("🔥 PORSCHE PDF EXTRACTOR")
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

    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)

    combined_mapping = {}

    if oil_pdf:
        print("\n" + "=" * 80)
        print("OIL MAINTENANCE")
        print("=" * 80)
        oil_text = extract_checkboxes_with_y_ranges(oil_pdf)
        oil_mapping = map_services_intersection_based(oil_pdf, oil_text, "oil")
        combined_mapping.update(oil_mapping)

    if inspection_pdf:
        print("\n" + "=" * 80)
        print("INSPECTION")
        print("=" * 80)
        insp_text = extract_checkboxes_with_y_ranges(inspection_pdf)
        insp_mapping = map_services_intersection_based(inspection_pdf, insp_text, "inspection")
        combined_mapping.update(insp_mapping)

    ordered_mapping = {}
    for service in SERVICE_ORDER:
        if service in combined_mapping:
            ordered_mapping[service] = combined_mapping[service]

    folder_name = os.path.basename(os.path.normpath(folder_path))
    output_file = os.path.join(output_dir, f"{folder_name}_Service_Mapping.json")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(ordered_mapping, f, indent=2, ensure_ascii=False)
    output_file = os.path.join(output_dir, f"{folder_name}_Service_Mapping.json")

    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    for service in SERVICE_ORDER:
        if service in ordered_mapping:
            print(f"\n🔧 {service}:")
            for model, items in ordered_mapping[service].items():
                print(f" 📋 {model[:60]}: {len(items)} items")

    print(f"\n✅ Saved: {output_file}")

    print("\n" + "=" * 80)
    print("🎉 DONE!")
    print("=" * 80)


if __name__ == "__main__":
    main()