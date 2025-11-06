# extract_ultra_perfect.py
# ULTRA PERFECT with category filtering!

from dataclasses import dataclass
from typing import List, Tuple, Set
import fitz


@dataclass
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


@dataclass
class WidgetBox:
    x0: float
    y0: float
    x1: float
    y1: float


# מילון הקטגוריות - כל המילים בנפרד!
CATEGORY_WORDS = {
    "Electrics", "Inside", "the", "vehicle", "Outside",
    "Under", "Engine", "compartment", "Additional",
    "work", "every", "years", "Test", "drive", "2"
}


def clean_with_category_logic(text: str) -> str:
    """
    מסיר מילים מהתחילה לפי הלוגיקה:
    1. אם לא מתחילה באות גדולה - הסר
    2. אם נמצאת במילון קטגוריות - הסר
    3. חזור על 1-2 עד שהתנאים מתקיימים
    """
    words = text.split()

    while words:
        first_word = words[0]

        # בדיקה 1: האם מתחילה באות גדולה?
        if not first_word or not first_word[0].isupper():
            # לא מתחילה באות גדולה - הסר!
            words = words[1:]
            continue

        # בדיקה 2: האם במילון קטגוריות?
        if first_word in CATEGORY_WORDS:
            # במילון - הסר!
            words = words[1:]
            continue

        # עברנו את כל הבדיקות - זו השורה הנכונה!
        break

    return " ".join(words)


def is_junk_full(text: str) -> bool:
    """בדיקה אם לא רלוונטי"""
    junk = [
        "Name Date", "Licence No", "Vehicle Ident", "Order No",
        "WP0ZZZ", "Mileage", "26/10/2025"
    ]
    return any(j in text for j in junk)


def words_to_lines(words: List[Word], y_tol: float = 1.8) -> List[Tuple[float, str]]:
    """מאחד מילים לשורות"""
    words.sort(key=lambda w: (w.y0, w.x0))
    lines: List[Tuple[float, List[str]]] = []

    for w in words:
        if not lines:
            lines.append(((w.y0 + w.y1) / 2.0, [w.text]))
            continue
        y, toks = lines[-1]
        if abs(((w.y0 + w.y1) / 2.0) - y) <= y_tol:
            toks.append(w.text)
        else:
            lines.append(((w.y0 + w.y1) / 2.0, [w.text]))

    return [(y, " ".join(toks)) for y, toks in lines]


def extract_ultra_perfect(pdf_path: str) -> List[str]:
    """חילוץ מושלם עם סינון קטגוריות"""
    doc = fitz.open(pdf_path)
    all_items = []
    seen: Set[str] = set()

    for page_num in range(len(doc)):
        page = doc[page_num]

        widgets = []
        for w in page.widgets():
            rect = w.rect
            widgets.append(WidgetBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1))

        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            words.append(Word(x0=x0, y0=y0, x1=x1, y1=y1, text=txt))

        lines = words_to_lines(words, y_tol=1.8)

        y_pad = 15.0

        for widget in widgets:
            wy = (widget.y0 + widget.y1) / 2.0

            close_lines = []
            for ly, ltxt in lines:
                if abs(ly - wy) <= y_pad:
                    close_lines.append((ly, ltxt))

            if not close_lines:
                continue

            close_lines.sort(key=lambda x: x[0])
            full_text = " ".join([t for _, t in close_lines])
            full_text = full_text.strip()

            # ניקוי עם לוגיקת קטגוריות!
            cleaned_text = clean_with_category_logic(full_text)

            if not cleaned_text or is_junk_full(cleaned_text) or cleaned_text in seen:
                continue

            all_items.append(cleaned_text)
            seen.add(cleaned_text)

    doc.close()
    return all_items


def main():
    print("=" * 80)
    print("ULTRA PERFECT EXTRACTION WITH CATEGORY FILTERING!")
    print("=" * 80)

    print("\n[1/2] Oil Maintenance.pdf...")
    oil_items = extract_ultra_perfect("../PDF Files/Panamera/Oil Maintenance.pdf")

    with open("PDF Files/oil_ultra.txt", "w", encoding="utf-8") as f:
        for item in oil_items:
            f.write(item + "\n")

    print(f"  ✅ {len(oil_items)} items → oil_ultra.txt")

    print("\n[2/2] Inspection.pdf...")
    insp_items = extract_ultra_perfect("../PDF Files/Panamera/Inspection.pdf")

    with open("PDF Files/inspection_ultra.txt", "w", encoding="utf-8") as f:
        for item in insp_items:
            f.write(item + "\n")

    print(f"  ✅ {len(insp_items)} items → inspection_ultra.txt")

    print("\n" + "=" * 80)
    print("DONE! ✨ THIS SHOULD BE PERFECT!")
    print("=" * 80)


if __name__ == "__main__":
    main()
