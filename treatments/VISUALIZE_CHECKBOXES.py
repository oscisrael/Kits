# VISUALIZE_CHECKBOXES.py
# Draw rectangles on PDF to see what we detect!

import fitz
from PIL import Image, ImageDraw, ImageFont
import os


def visualize_checkboxes(pdf_path, output_path):
    """ציור ויזואלי של הcheckboxes"""
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]

        # המרת הדף לתמונה
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # x2 resolution
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        draw = ImageDraw.Draw(img)

        # חילוץ widgets
        widgets = []
        for w in page.widgets():
            rect = w.rect
            widgets.append({
                "x0": rect.x0 * 2,  # Scale x2
                "y0": rect.y0 * 2,
                "x1": rect.x1 * 2,
                "y1": rect.y1 * 2,
                "center_x": (rect.x0 + rect.x1) / 2.0,
                "center_y": (rect.y0 + rect.y1) / 2.0
            })

        print(f"\nPage {page_num + 1}: Found {len(widgets)} widgets")

        # ציור כל הwidgets
        for i, w in enumerate(widgets):
            # ציור מלבן אדום
            draw.rectangle(
                [w["x0"], w["y0"], w["x1"], w["y1"]],
                outline="red",
                width=3
            )

            # טקסט עם המיקום
            text = f"{i + 1}"
            draw.text((w["x0"] + 5, w["y0"] + 5), text, fill="blue")

        # שמירת התמונה
        output_file = output_path.replace(".png", f"_page{page_num + 1}.png")
        img.save(output_file)
        print(f"  ✅ Saved: {output_file}")

    doc.close()


def main():
    print("=" * 80)
    print("🎨 VISUALIZING CHECKBOXES")
    print("=" * 80)

    # יצירת תיקייה לתמונות
    os.makedirs("../PDF Files/visualizations", exist_ok=True)

    print("\n[1/2] Visualizing Inspection.pdf...")
    visualize_checkboxes(
        "../PDF Files/Panamera/Inspection.pdf",
        "PDF Files/visualizations/inspection_visualization.png"
    )

    print("\n[2/2] Visualizing Oil Maintenance.pdf...")
    visualize_checkboxes(
        "../PDF Files/Panamera/Oil Maintenance.pdf",
        "PDF Files/visualizations/oil_visualization.png"
    )

    print("\n" + "=" * 80)
    print("✅ DONE! Check the 'visualizations' folder")
    print("=" * 80)


if __name__ == "__main__":
    main()
