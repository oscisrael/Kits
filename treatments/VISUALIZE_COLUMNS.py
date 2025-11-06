# VISUALIZE_COLUMNS.py
# Show how we detect columns + draw them!

import fitz
from PIL import Image, ImageDraw, ImageFont
import os

SERVICE_ORDER = [
    "service_time_dependent",
    "service_180000",
    "service_120000",
    "service_90000",
    "service_60000",
    "service_45000",
    "service_30000"
]

COLORS = [
    "red", "blue", "green", "purple", "orange", "pink", "cyan"
]


def cluster_x_values(x_values, threshold=10.0):
    """קיבוץ ערכי X קרובים"""
    x_values = sorted(x_values)
    clusters = []
    current = [x_values[0]]

    for x in x_values[1:]:
        if x - current[-1] <= threshold:
            current.append(x)
        else:
            clusters.append(sum(current) / len(current))
            current = [x]

    if current:
        clusters.append(sum(current) / len(current))

    return [round(c, 2) for c in clusters]


def detect_and_visualize_columns(pdf_path, output_path):
    """זיהוי עמודות + ויזואליזציה"""
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]

        # חילוץ widgets
        all_widgets = []
        for w in page.widgets():
            rect = w.rect
            all_widgets.append({
                "x": round((rect.x0 + rect.x1) / 2.0, 2),
                "y": round((rect.y0 + rect.y1) / 2.0, 2),
                "rect": rect
            })

        print(f"\n" + "=" * 80)
        print(f"PAGE {page_num + 1}: Analyzing {len(all_widgets)} checkboxes")
        print("=" * 80)

        # זיהוי עמודות
        all_x = [w["x"] for w in all_widgets]
        unique_x = sorted(set(all_x), reverse=True)

        print(f"\n📊 RAW unique X values: {unique_x}")

        # Clustering
        clustered_x = cluster_x_values(unique_x, threshold=10.0)
        clustered_x.sort(reverse=True)

        print(f"📊 After clustering ({len(clustered_x)} columns): {clustered_x}")

        # הסרת עמודת דגמים (הכי שמאלית)
        if len(clustered_x) > 1:
            models_column_x = clustered_x[-1]
            service_columns_x = clustered_x[:-1]
            print(f"\n🚫 Models column (removed): X={models_column_x}")
            print(f"✅ Service columns: {service_columns_x}")
        else:
            service_columns_x = clustered_x
            models_column_x = None

        # מיפוי לשמות טיפולים
        service_map = {}
        for i, service in enumerate(SERVICE_ORDER):
            if i < len(service_columns_x):
                service_map[service] = service_columns_x[i]

        print(f"\n🗺️  SERVICE MAPPING:")
        for service, x_val in service_map.items():
            count = sum(1 for w in all_widgets if abs(w["x"] - x_val) < 15)
            print(f"    {service}: X={x_val} ({count} checkboxes)")

        # יצירת תמונה
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        draw = ImageDraw.Draw(img)

        # ציור קווים אנכיים לכל עמודה
        for i, (service, x_val) in enumerate(service_map.items()):
            color = COLORS[i % len(COLORS)]
            x_pixel = x_val * 2  # Scale x2

            # קו אנכי
            draw.line([(x_pixel, 0), (x_pixel, img.height)], fill=color, width=3)

            # טקסט בראש העמוד
            draw.text((x_pixel - 30, 50), service.split("_")[1], fill=color)

        # ציור עמודת דגמים
        if models_column_x:
            x_pixel = models_column_x * 2
            draw.line([(x_pixel, 0), (x_pixel, img.height)], fill="gray", width=5)
            draw.text((x_pixel - 50, 50), "MODELS", fill="gray")

        # ציור checkboxes
        for w in all_widgets:
            rect = w["rect"]
            # מצא איזו עמודה
            closest_service = None
            min_dist = float('inf')

            for service, x_val in service_map.items():
                dist = abs(w["x"] - x_val)
                if dist < min_dist:
                    min_dist = dist
                    closest_service = service

            # בחירת צבע
            if closest_service and min_dist < 15:
                color_idx = list(service_map.keys()).index(closest_service)
                color = COLORS[color_idx % len(COLORS)]
            else:
                color = "gray"

            # ציור ריבוע
            draw.rectangle(
                [rect.x0 * 2, rect.y0 * 2, rect.x1 * 2, rect.y1 * 2],
                outline=color,
                width=2
            )

        # שמירה
        output_file = output_path.replace(".png", f"_page{page_num + 1}.png")
        img.save(output_file)
        print(f"\n✅ Saved visualization: {output_file}")

    doc.close()


def main():
    print("=" * 80)
    print("🎨 COLUMN DETECTION VISUALIZATION")
    print("=" * 80)

    os.makedirs("../PDF Files/column_viz", exist_ok=True)

    print("\nProcessing Inspection.pdf...")
    detect_and_visualize_columns(
        "../PDF Files/Panamera/Inspection.pdf",
        "PDF Files/column_viz/inspection_columns.png"
    )

    print("\n" + "=" * 80)
    print("✅ DONE! Check 'column_viz' folder")
    print("=" * 80)
    print("\nLegend:")
    print("  - Vertical colored lines = Service columns")
    print("  - Gray line = Models column (excluded)")
    print("  - Colored boxes = Checkboxes assigned to each service")
    print("=" * 80)


if __name__ == "__main__":
    main()
