# DEEP_DEBUG.py
# Let's see EXACTLY what's happening!

import fitz
import json


def analyze_inspection_grid():
    """ניתוח מלא של הGrid"""
    doc = fitz.open("../PDF Files/Panamera/Inspection.pdf")
    page = doc[0]

    # חילוץ כל הwidgets
    all_widgets = []
    for w in page.widgets():
        rect = w.rect
        all_widgets.append({
            "x": round((rect.x0 + rect.x1) / 2.0, 2),
            "y": round((rect.y0 + rect.y1) / 2.0, 2),
            "x0": round(rect.x0, 2),
            "x1": round(rect.x1, 2),
            "y0": round(rect.y0, 2),
            "y1": round(rect.y1, 2)
        })

    print("=" * 100)
    print("🔍 DEEP DEBUG - INSPECTION.PDF")
    print("=" * 100)

    print(f"\n📊 TOTAL CHECKBOXES: {len(all_widgets)}\n")

    # הדפסת כל הwidgets
    print("=" * 100)
    print("ALL CHECKBOXES (sorted by Y, then X):")
    print("=" * 100)
    all_widgets.sort(key=lambda w: (w["y"], w["x"]))

    for i, w in enumerate(all_widgets, 1):
        print(
            f"  [{i:2d}] X={w['x']:6.2f}  Y={w['y']:6.2f}  (Box: {w['x0']:.2f}-{w['x1']:.2f}, {w['y0']:.2f}-{w['y1']:.2f})")

    # ניתוח X values
    print("\n" + "=" * 100)
    print("X-AXIS ANALYSIS (Columns):")
    print("=" * 100)

    all_x = sorted(set(w["x"] for w in all_widgets), reverse=True)
    print(f"\nUnique X values ({len(all_x)}):")
    for i, x in enumerate(all_x, 1):
        count = sum(1 for w in all_widgets if w["x"] == x)
        print(f"  Column {i}: X={x:6.2f}  ({count} checkboxes)")

    # ניתוח Y values
    print("\n" + "=" * 100)
    print("Y-AXIS ANALYSIS (Rows):")
    print("=" * 100)

    all_y = sorted(set(w["y"] for w in all_widgets))
    print(f"\nUnique Y values ({len(all_y)}):")
    for i, y in enumerate(all_y, 1):
        count = sum(1 for w in all_widgets if w["y"] == y)
        x_vals = [w["x"] for w in all_widgets if w["y"] == y]
        print(f"  Row {i:2d}: Y={y:6.2f}  ({count} checkboxes at X={x_vals})")

    # Grid visualization
    print("\n" + "=" * 100)
    print("GRID MATRIX:")
    print("=" * 100)

    # יצירת matrix
    print("\n     ", end="")
    for x in all_x:
        print(f"X={x:5.1f} ", end="")
    print()

    for y in all_y:
        print(f"Y={y:5.1f}: ", end="")
        for x in all_x:
            has_checkbox = any(w["x"] == x and w["y"] == y for w in all_widgets)
            print("   ✓     " if has_checkbox else "   ✗     ", end="")
        print()

    # שמירת הנתונים לקובץ
    debug_data = {
        "total_widgets": len(all_widgets),
        "unique_x": all_x,
        "unique_y": all_y,
        "all_widgets": all_widgets,
        "grid_matrix": {}
    }

    for y in all_y:
        debug_data["grid_matrix"][f"Y_{y}"] = {}
        for x in all_x:
            has_checkbox = any(w["x"] == x and w["y"] == y for w in all_widgets)
            debug_data["grid_matrix"][f"Y_{y}"][f"X_{x}"] = has_checkbox

    with open("../PDF Files/DEBUG_grid_analysis.json", "w", encoding="utf-8") as f:
        json.dump(debug_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 100)
    print("✅ DEBUG data saved to: DEBUG_grid_analysis.json")
    print("=" * 100)

    doc.close()

    return debug_data


def compare_with_text_items():
    """השוואה עם הטקסט שחילצנו"""
    print("\n" + "=" * 100)
    print("📝 TEXT ITEMS COMPARISON:")
    print("=" * 100)

    try:
        with open("../PDF Files/inspection_with_location.json", "r", encoding="utf-8") as f:
            text_items = json.load(f)

        print(f"\nTotal text items: {len(text_items)}\n")

        for i, item in enumerate(text_items, 1):
            print(f"  [{i:2d}] Y={item['y']:6.2f}  Text: {item['text'][:60]}...")
    except Exception as e:
        print(f"  ⚠️  Could not load text items: {e}")


if __name__ == "__main__":
    # ניתוח Grid
    debug_data = analyze_inspection_grid()

    # השוואה עם טקסט
    compare_with_text_items()

    print("\n" + "=" * 100)
    print("🎯 ANALYSIS COMPLETE!")
    print("=" * 100)
    print("\nNext steps:")
    print("  1. Check the grid matrix above")
    print("  2. Compare Y values of checkboxes vs text items")
    print("  3. See if X clustering is correct (should be 7-8 columns)")
    print("  4. Review DEBUG_grid_analysis.json for full details")
    print("=" * 100)
