# match_service_parts_to_pet.py
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

SERVICE_PATH = Path("outputs/Panamera_Service_Mapping.json")
PET_PATH = Path("PET Outputs/Panamera PET lines.json")
OUTPUT_PATH = Path("outputs/Panamera_Service_Parts_Matched.json")

# ---------- Utilities ----------

def clean(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# כללי PARTS: לפי הפרומפט ששיפרנו
PARTS_KEYWORDS = [
    "replace", "change", "fill", "refill", "add", "install", "renew",
    "top up", "replenish", "replace filter", "replace element",
    "replace fluid", "replace spark", "oil change", "fluid change"
]

INSPECTION_ONLY_KEYWORDS = [
    "check", "inspect", "inspection", "visual inspection", "read", "reset",
    "diagnose", "diagnostic", "verify", "measure", "look", "test", "drain",
    "prepare report", "check function", "check condition", "check level",
    "read out memory", "reset maintenance interval"
]

def is_parts_line(line: str) -> bool:
    """
    קובע אם השורה היא PARTS לפי כללים דטרמיניסטיים:
    - אם יש מילת PARTS → True
    - "drain" לבדו (בלי change/fill/add/install/renew/top up) → False
    - אם גם וגם (check AND replace) → True (PARTS מנצח)
    """
    l = clean(line)
    has_parts_kw = any(kw in l for kw in PARTS_KEYWORDS)
    has_inspect_kw = any(kw in l for kw in INSPECTION_ONLY_KEYWORDS)

    # drain לבדו לא נחשב חלק
    drain_alone = ("drain" in l) and not any(kw in l for kw in ["replace","change","fill","add","install","renew","top up","replenish"])

    if drain_alone:
        return False

    if has_parts_kw:
        return True

    # אם אין מילת PARTS — לא חלק
    return False

# מנוע ניקוד התאמה בין SERVICE LINE לבין תיאור חלק ב-PET
KEYWORDS = [
    "oil", "filter", "spark", "plug", "brake", "fluid", "air",
    "pollen", "dust", "belt", "coolant", "grease", "lubricant",
    "paste", "transmission", "differential", "compressor"
]

def keyword_score(a: str, b: str) -> float:
    score = 0.0
    for kw in KEYWORDS:
        if kw in a and kw in b:
            score += 3.0
        elif kw in a or kw in b:
            score += 0.5
    return score

def similarity_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def score_match(service_line: str, pet_desc: str) -> float:
    a, b = clean(service_line), clean(pet_desc)
    # משקל דמיון + משקל מילות מפתח
    return similarity_score(a, b) * 5.0 + keyword_score(a, b)

def best_pet_match(service_line: str, pet_rows: list, min_score: float = 2.0):
    """
    מחזיר את ההתאמה הטובה ביותר או None אם לא עבר סף.
    """
    best = None
    best_sc = -1.0

    for row in pet_rows:
        desc = f"{row.get('Description','')}"
        sc = score_match(service_line, desc)
        if sc > best_sc:
            best_sc = sc
            best = row

    if best_sc >= min_score:
        return {
            "SERVICE LINE": service_line,
            "PART NUMBER": best.get("Part Number", "").strip(),
            "DESCRIPTION": best.get("Description", "").strip(),
            "REMARK": best.get("Remark", "").strip(),
            "QUANTITY": best.get("Qty", "").strip(),
        }
    else:
        # לא נמצאה התאמה טובה מספיק — נחזיר שורה עם שדות חלק ריקים
        return {
            "SERVICE LINE": service_line,
            "PART NUMBER": "",
            "DESCRIPTION": "",
            "REMARK": "",
            "QUANTITY": "",
        }

# ---------- Main ----------

def main():
    if not SERVICE_PATH.exists():
        raise FileNotFoundError(f"Service mapping not found: {SERVICE_PATH}")
    if not PET_PATH.exists():
        raise FileNotFoundError(f"PET lines not found: {PET_PATH}")

    with SERVICE_PATH.open("r", encoding="utf-8") as f:
        service_data = json.load(f)

    with PET_PATH.open("r", encoding="utf-8") as f:
        pet_rows = json.load(f)

    # הפלט לפי טיפול: service_xxxxx → [matches...]
    output = {}

    # service_data במבנה: { service_key: { model_name: [lines...] } }
    for service_key, models_dict in service_data.items():
        collected_lines = []
        # מאחדים את כל הדגמים לאותה רשימה (הפרדה רק לפי טיפול)
        for model_name, lines in models_dict.items():
            collected_lines.extend(lines or [])

        # נשמור רק שורות PARTS
        parts_lines = [ln for ln in collected_lines if is_parts_line(ln)]

        # התאמה מול PET
        matched = [best_pet_match(line, pet_rows) for line in parts_lines]

        output[service_key] = matched

    # שמירה
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Done! Output saved to: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
