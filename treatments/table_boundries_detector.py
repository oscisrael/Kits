# -*- coding: utf-8 -*-
"""
🎯 THREE-ZONE APPROACH v2
WHITE → GRAY → LIGHT_GRAY → EXIT LIGHT_GRAY (stop!)
"""

import fitz
import numpy as np
from PIL import Image, ImageDraw
import os
import sys


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


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else input("PDF path: ").strip()

    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)
    page = doc[0]
    page_rect = page.rect

    # Find Measures
    measures_y = 0
    for word_info in page.get_text("words"):
        x0, y0, x1, y1, txt, _, _, _ = word_info
        if txt == "Measures":
            measures_y = (y0 + y1) / 2.0
            break

    # Get checkboxes
    checkboxes = []
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

    # Get image
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    img_height = pix.height
    img_width = pix.width

    print(f"\n{'=' * 130}")
    print(f"🎯 THREE-ZONE APPROACH v2: Find BACKGROUND EXIT")
    print(f"{'=' * 130}")
    print(f"\nFound {len(checkboxes)} unique checkboxes\n")

    print(f"{'Idx':>3} {'Y PDF':>8} {'X PDF':>8} {'Top Bound':>10} {'Bottom Bound':>12} {'Row Height':>12}")
    print(f"{'-' * 85}")

    # Create visualization
    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    draw = ImageDraw.Draw(pil_img)

    for i, cb in enumerate(checkboxes):
        pixel_x = int((cb["x"] / page_rect.width) * img_width)
        pixel_y = int((cb["y"] / page_rect.height) * img_height)

        top_pixel = find_background_boundary_v3(img, pixel_x, pixel_y, direction="up")
        bottom_pixel = find_background_boundary_v3(img, pixel_x, pixel_y, direction="down")

        if top_pixel is None:
            top_pixel = pixel_y
        if bottom_pixel is None:
            bottom_pixel = pixel_y

        top_y = (top_pixel / img_height) * page_rect.height
        bottom_y = (bottom_pixel / img_height) * page_rect.height
        row_height = bottom_y - top_y

        print(f"{i:>3} {cb['y']:>8.1f} {cb['x']:>8.1f} {top_pixel:>10} {bottom_pixel:>12} {row_height:>12.1f}")

        # Draw
        if top_pixel > 0:
            draw.line([(0, top_pixel), (img_width, top_pixel)], fill=(255, 0, 0), width=3)
        if bottom_pixel > 0:
            draw.line([(0, bottom_pixel), (img_width, bottom_pixel)], fill=(0, 255, 0), width=3)

        draw.ellipse([pixel_x - 8, pixel_y - 8, pixel_x + 8, pixel_y + 8],
                     fill=(255, 165, 0), outline=(0, 0, 0), width=2)

    output_file = f"THREE_ZONE_v2_911inspection.jpg"
    pil_img.save(output_file, "JPEG", quality=95)
    print(f"\n✅ Saved: {output_file}")

    print(f"\n{'=' * 130}")
    print(f"✅ THREE-ZONE APPROACH v2 - DONE!")
    print(f"{'=' * 130}\n")

    doc.close()


if __name__ == "__main__":
    main()
