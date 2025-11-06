# step2_map_services_to_items_DEBUG.py
# עם הדפסות DEBUG

import fitz
import json
from collections import defaultdict
from typing import Dict, List

SERVICE_ORDER = [
    "service_time_dependent",
    "service_180000",
    "service_120000",
    "service_90000",
    "service_60000",
    "service_45000",
    "service_30000"
]


def detect_columns_and_grid(pdf_path: str) -> Dict:
    """זיהוי אוטומטי של עמודות וGrid - עם DEBUG"""
    doc = fitz.open(pdf_path)
    page = doc[0]

    # חילוץ כל הwidgets
    all_widgets = []
    for w in page.widgets():
        rect = w.rect
        all_widgets.append({
            "x": round((rect.x0 + rect.x1) / 2.0, 2),
            "y": round((rect.y0 + rect.y1) / 2.0, 2)
        })

    print(f"\n  🔍 DEBUG: Total widgets found: {len(all_widgets)}")

    # מיון לפי X
    all_widgets.sort(key=lambda w: w["x"])

    # DEBUG: הדפסת כל ה-X values
    all_x_values = sorted(set(w["x"] for w in all_widgets))
    print(f"  🔍 DEBUG: Unique X values: {all_x_values}")

    # זיהוי עמודות - **שיטה משופרת**
    # קיבוץ X-values דומים
    columns_x = []
    current_group = [all_x_values[0]]

    for x in all_x_values[1:]:
        if abs(x - current_group[-1]) < 5:  # סף קטן יותר
            current_group.append(x)
        else:
            # חשב ממוצע של הקבוצה
            avg_x = sum(current_group) / len(current_group)
            columns_x.append(round(avg_x, 2))
            current_group = [x]

    # אל תשכח את האחרונה
    if current_group:
        avg_x = sum(current_group) / len(current_group)
        columns_x.append(round(avg_x, 2))

    print(f"  🔍 DEBUG: Detected column X values: {columns_x}")
    print(f"  🔍 DEBUG: Number of columns: {len(columns_x)}")

    # מיון מימין לשמאל
    columns_x.sort(reverse=True)

    # התאמה לשמות טיפולים
    service_columns = {}

    # נדלג על העמודה הראשונה (הכי שמאלית) - זה הדגמים
    service_columns_x = columns_x[:-1]  # כל החוץ מהאחרונה

    for i, service_name in enumerate(SERVICE_ORDER):
        if i < len(service_columns_x):
            service_columns[service_name] = service_columns_x[i]

    print(f"  🔍 DEBUG: Service mapping: {service_columns}")

    # בניית Grid
    grid = defaultdict(set)

    for widget in all_widgets:
        # מצא את העמודה הקרובה ביותר
        closest_service = None
        min_distance = float('inf')

        for service_name, x_val in service_columns.items():
            distance = abs(widget["x"] - x_val)
            if distance < min_distance and distance < 15:  # סף גדול יותר!
                min_distance = distance
                closest_service = service_name

        if closest_service:
            grid[closest_service].add(widget["y"])

    # DEBUG: הדפסת סטטיסטיקות
    for service, y_vals in grid.items():
        print(f"  🔍 {service}: {len(y_vals)} checkboxes")

    doc.close()

    return {
        "columns": service_columns,
        "grid": {k: list(v) for k, v in grid.items()}
    }


def match_items_to_services(items_file: str, grid_info: Dict) -> Dict:
    """התאמת שורות לטיפולים"""
    with open(items_file, "r", encoding="utf-8") as f:
        items = json.load(f)

    result = {service: [] for service in SERVICE_ORDER}

    y_tolerance = 5.0

    for service, y_values in grid_info["grid"].items():
        for item in items:
            item_y = item["y"]

            for grid_y in y_values:
                if abs(item_y - grid_y) <= y_tolerance:
                    result[service].append(item["text"])
                    break

    return result


def main():
    print("=" * 80)
    print("STEP 2: MAP SERVICES TO ITEMS (DEBUG MODE)")
    print("=" * 80)

    print("\n[1/2] Processing INSPECTION...")
    grid_info = detect_columns_and_grid("../PDF Files/Panamera/Inspection.pdf")

    print(f"\n  ✅ Detected {len(grid_info['columns'])} service columns")

    inspection_mapping = match_items_to_services(
        "../PDF Files/inspection_with_location.json",
        grid_info
    )

    with open("PDF Files/inspection_services_mapped.json", "w", encoding="utf-8") as f:
        json.dump(inspection_mapping, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Saved → inspection_services_mapped.json")

    print("\n[2/2] Processing Oil Maintenance...")
    with open("../PDF Files/oil_with_location.json", "r", encoding="utf-8") as f:
        oil_items = json.load(f)

    oil_mapping = {
        "service_15000": [item["text"] for item in oil_items]
    }

    with open("PDF Files/oil_services_mapped.json", "w", encoding="utf-8") as f:
        json.dump(oil_mapping, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Saved → oil_services_mapped.json")

    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    for service, items in inspection_mapping.items():
        print(f"  {service}: {len(items)} items")
    print(f"  service_15000 (Oil): {len(oil_mapping['service_15000'])} items")

    print("\n" + "=" * 80)
    print("DONE! ✨")
    print("=" * 80)


if __name__ == "__main__":
    main()
