# extract_perfect_capital_logic.py
# Using CAPITAL LETTER logic to find line start!

from dataclasses import dataclass
from typing import List, Tuple, Set
import fitz
import re


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


def find_first_capital_start(text: str) -> str:
    """
    מוצא את המילה הראשונה שמתחילה באות גדולה ואין לפניה תו אחר.
    זו תחילת השורה האמיתית!
    """
    # חיפוש: תחילת מחרוזת או רווח, ואז אות גדולה
    words = text.split()

    for i, word in enumerate(words):
        # האם המילה מתחילה באות גדולה?
        if word and word[0].isupper():
            # האם זו המילה הראשונה? (אין לפניה כלום)
            if i == 0:
                # זו ההתחלה האמיתית!
                return " ".join(words[i:])

    # אם לא מצאנו - נחזיר את כל הטקסט
    return text


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


def extract_with_capital_logic(pdf_path: str) -> List[str]:
    """חילוץ מושלם עם לוגיקת אות גדולה"""
    doc = fitz.open(pdf_path)
    all_items = []
    seen: Set[str] = set()

    for page_num in range(len(doc)):
        page = doc[page_num]

        # חילוץ widgets (הריבועים הכחולים)
        widgets = []
        for w in page.widgets():
            rect = w.rect
            widgets.append(WidgetBox(x0=rect.x0, y0=rect.y0, x1=rect.x1, y1=rect.y1))

        # חילוץ מילים
        words = []
        for word_info in page.get_text("words"):
            x0, y0, x1, y1, txt, _, _, _ = word_info
            words.append(Word(x0=x0, y0=y0, x1=x1, y1=y1, text=txt))

        # יצירת שורות
        lines = words_to_lines(words, y_tol=1.8)

        # y_pad גדול! כדי לתפוס שורות ארוכות
        y_pad = 15.0  # גדול מאוד!

        for widget in widgets:
            wy = (widget.y0 + widget.y1) / 2.0

            # מצא שורות בטווח רחב
            close_lines = []
            for ly, ltxt in lines:
                # לוקח גם מלמעלה וגם מלמטה
                if abs(ly - wy) <= y_pad:
                    close_lines.append((ly, ltxt))

            if not close_lines:
                continue

            # מיון לפי Y
            close_lines.sort(key=lambda x: x[0])

            # חיבור כל השורות
            full_text = " ".join([t for _, t in close_lines])
            full_text = full_text.strip()

            # ניקוי לפי אות גדולה!
            cleaned_text = find_first_capital_start(full_text)

            # סינון
            if not cleaned_text or is_junk_full(cleaned_text) or cleaned_text in seen:
                continue

            all_items.append(cleaned_text)
            seen.add(cleaned_text)

    doc.close()
    return all_items


def main():
    print("=" * 80)
    print("PERFECT EXTRACTION WITH CAPITAL LETTER LOGIC!")
    print("=" * 80)

    print("\n[1/2] Oil Maintenance.pdf...")
    oil_items = extract_with_capital_logic("../PDF Files/Panamera/Oil Maintenance.pdf")

    with open("PDF Files/oil_capital.txt", "w", encoding="utf-8") as f:
        for item in oil_items:
            f.write(item + "\n")

    print(f"  ✅ {len(oil_items)} items → oil_capital.txt")

    print("\n[2/2] Inspection.pdf...")
    insp_items = extract_with_capital_logic("../PDF Files/Panamera/Inspection.pdf")

    with open("PDF Files/inspection_capital.txt", "w", encoding="utf-8") as f:
        for item in insp_items:
            f.write(item + "\n")

    print(f"  ✅ {len(insp_items)} items → inspection_capital.txt")

    print("\n" + "=" * 80)
    print("DONE! ✨")
    print("=" * 80)


if __name__ == "__main__":
    main()
