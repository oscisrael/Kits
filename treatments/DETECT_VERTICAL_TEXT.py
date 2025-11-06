# DETECT_VERTICAL_TEXT.py
# Detect vertical column headers with rotation!

import fitz
from PIL import Image, ImageDraw
import os


def extract_vertical_text_with_rotation(pdf_path):
    """חילוץ טקסט אנכי עם rotation"""
    doc = fitz.open(pdf_path)
    page = doc[0]

    # חילוץ טקסט עם metadata
    text_instances = page.get_text("dict")

    vertical_texts = []

    print("\n" + "=" * 80)
    print("🔍 SEARCHING FOR VERTICAL TEXT")
    print("=" * 80)

    for block in text_instances["blocks"]:
        if block.get("type") != 0:  # לא טקסט
            continue

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                # בדיקה אם הטקסט מסובב
                # dir[0] ו-dir[1] מציינים את כיוון הטקסט
                text = span.get("text", "").strip()
                bbox = span.get("bbox")  # (x0, y0, x1, y1)

                if not text or len(text) < 3:
                    continue

                # חישוב גובה ורוחב
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]

                # טקסט אנכי: גובה >> רוחב
                if height > width * 1.5:
                    vertical_texts.append({
                        "text": text,
                        "bbox": bbox,
                        "x": (bbox[0] + bbox[2]) / 2,
                        "y": (bbox[1] + bbox[3]) / 2,
                        "width": width,
                        "height": height
                    })
                    print(f"  ✅ Found: '{text}' at X={bbox[0]:.1f}")

    doc.close()
    return vertical_texts


def visualize_vertical_columns(pdf_path, vertical_texts, output_path):
    """ויזואליזציה של העמודות האנכיות"""
    doc = fitz.open(pdf_path)
    page = doc[0]

    # המרה לתמונה
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(img)

    print("\n" + "=" * 80)
    print("🎨 CREATING VISUALIZATION")
    print("=" * 80)

    # ציור כל טקסט אנכי
    colors = ["red", "blue", "green", "purple", "orange", "pink", "cyan", "brown"]

    for i, vtext in enumerate(vertical_texts):
        bbox = vtext["bbox"]
        color = colors[i % len(colors)]

        # ציור ריבוע סביב הטקסט
        draw.rectangle(
            [bbox[0] * 2, bbox[1] * 2, bbox[2] * 2, bbox[3] * 2],
            outline=color,
            width=4
        )

        # קו אנכי במרכז
        center_x = vtext["x"] * 2
        draw.line(
            [(center_x, 0), (center_x, img.height)],
            fill=color,
            width=3
        )

        # טקסט עם המספר
        draw.text(
            (bbox[0] * 2 + 5, bbox[1] * 2 + 5),
            f"{i + 1}",
            fill=color
        )

    # שמירה
    img.save(output_path)
    print(f"  ✅ Saved: {output_path}")

    doc.close()


def cluster_columns(vertical_texts, threshold=50):
    """קיבוץ טקסטים לעמודות"""
    if not vertical_texts:
        return []

    # מיון לפי X
    sorted_texts = sorted(vertical_texts, key=lambda t: t["x"])

    columns = []
    current_column = [sorted_texts[0]]

    for text in sorted_texts[1:]:
        # אם קרוב לעמודה הנוכחית
        if abs(text["x"] - current_column[0]["x"]) < threshold:
            current_column.append(text)
        else:
            # עמודה חדשה
            columns.append(current_column)
            current_column = [text]

    columns.append(current_column)  # האחרונה

    return columns


def main():
    print("=" * 80)
    print("🔄 VERTICAL TEXT DETECTION WITH ROTATION")
    print("=" * 80)

    os.makedirs("../PDF Files/vertical_detection", exist_ok=True)

    print("\nProcessing Inspection.pdf...")
    vertical_texts = extract_vertical_text_with_rotation("../PDF Files/Panamera/Inspection.pdf")

    print(f"\n📊 Total vertical text instances: {len(vertical_texts)}")

    if vertical_texts:
        print("\n" + "=" * 80)
        print("DETECTED VERTICAL TEXTS:")
        print("=" * 80)
        for i, vt in enumerate(vertical_texts, 1):
            print(f"  [{i}] X={vt['x']:6.1f}  Text: '{vt['text']}'")

        # קיבוץ לעמודות
        columns = cluster_columns(vertical_texts, threshold=50)

        print(f"\n📊 Grouped into {len(columns)} columns:")
        for i, col in enumerate(columns, 1):
            avg_x = sum(t["x"] for t in col) / len(col)
            texts = [t["text"] for t in col]
            print(f"  Column {i}: X={avg_x:.1f}  Texts: {texts}")

        # ויזואליזציה
        visualize_vertical_columns(
            "../PDF Files/Panamera/Inspection.pdf",
            vertical_texts,
            "PDF Files/vertical_detection/vertical_columns_viz.png"
        )
    else:
        print("\n⚠️  No vertical text detected!")
        print("    This might mean:")
        print("    1. Text is rotated differently")
        print("    2. Text is embedded as images")
        print("    3. Need different detection method")

    print("\n" + "=" * 80)
    print("DONE! ✨")
    print("=" * 80)


if __name__ == "__main__":
    main()
