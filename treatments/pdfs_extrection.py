# extract_simple_final.py
# Back to basics - no X filter, just clean up after!

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


def clean_text(text: str) -> str:
    """ניקוי טקסט - הסרת מילים מיותרות בתחילת המשפט"""
    # הסרת מילים בודדות בתחילה
    remove_prefix = ["the ", "Measures ", "Electrics ", "vehicle ", "compartment "]
    for prefix in remove_prefix:
        if text.startswith(prefix):
            text = text[len(prefix):]
            # אות ראשונה גדולה
            if text:
                text = text[0].upper() + text[1:]

    return text.strip()


def is_junk_full(text: str) -> bool:
    """בדיקה מלאה אם השורה לא רלוונטית"""
    junk = [
        "Name Date", "Licence No", "Vehicle Ident", "Order No",
        "WP0ZZZ", "Mileage", "26/10/2025"
    ]
    # שורות קצרות מדי
    if len(text) < 15:
        return True
    return any(j in text for j in junk)


def words_to_lines(words: List[Word], y_tol: float = 1.8) -> List[Tuple[float, str]]:
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


def extract_final(pdf_path: str) -> List[str]:
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

        y_pad = 2.2

        for widget in widgets:
            wy = (widget.y0 + widget.y1) / 2.0

            close_lines = []
            for ly, ltxt in lines:
                if abs(ly - wy) <= y_pad:
                    close_lines.append((ly, ltxt))

            if not close_lines:
                continue

            close_lines.sort(key=lambda x: x[0])
            text = " ".join([t for _, t in close_lines])
            text = text.strip()

            # ניקוי
            text = clean_text(text)

            if not text or is_junk_full(text) or text in seen:
                continue

            all_items.append(text)
            seen.add(text)

    doc.close()
    return all_items


def main():
    print("=" * 80)
    print("SIMPLE EXTRACTION - FINAL")
    print("=" * 80)

    print("\n[1/2] Oil Maintenance.pdf...")
    oil_items = extract_final("../PDF Files/Panamera/Oil Maintenance.pdf")

    with open("PDF Files/oil_clean.txt", "w", encoding="utf-8") as f:
        for item in oil_items:
            f.write(item + "\n")

    print(f"  ✅ {len(oil_items)} items → oil_clean.txt")

    print("\n[2/2] Inspection.pdf...")
    insp_items = extract_final("../PDF Files/Panamera/Inspection.pdf")

    with open("PDF Files/inspection_clean.txt", "w", encoding="utf-8") as f:
        for item in insp_items:
            f.write(item + "\n")

    print(f"  ✅ {len(insp_items)} items → inspection_clean.txt")

    print("\n" + "=" * 80)
    print("DONE! ✨")
    print("=" * 80)


if __name__ == "__main__":
    main()
