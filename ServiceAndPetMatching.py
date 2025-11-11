# ServiceAndPetMatching_Enhanced.py

"""
מערכת התאמה אוטומטית בין Service Lines ל-PET Parts
כולל:
- התאמה מבוססת ניקוד
- כללים מיוחדים לפי דגם (Panamera, Cayenne)
- בחירת גירסת שמן X מתקדמת
- חישוב כמות שמן דינמי לפי דגם
- תמיכה ב-VIN או הזנה ידנית של דגם
"""

import json
import re
import argparse
from difflib import SequenceMatcher
from pathlib import Path
from oil_capacity_config import get_oil_capacity
from SmartVinDecoder import SmartVinDecoder

# נתיבי קבצים
CLASSIFIED_SERVICE_PATH = Path("Classification Results/Panamera_S_GTS_Turbo_S_EHybrid_S_EHybrid/Panamera_S_GTS_Turbo_S_EHybrid_S_EHybrid_classified.json")
PET_PATH = Path("PET Outputs/Macan PET lines.json")  # שנה לנתיב הנכון של PET
OUTPUT_PATH = Path("outputs/Service_Parts_Matched.json")


# ---------- Utilities ----------

def clean(text: str) -> str:
    """ניקוי טקסט להשוואה"""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_x_version(description: str) -> int:
    """
    מחלץ את מספר הגירסה של X (למשל X3, X4, X10)
    מחזיר -1 אם לא נמצא X
    """
    match = re.search(r'\bX(\d+)\b', description)
    if match:
        return int(match.group(1))
    return -1


def get_model_from_user(args) -> str:
    """
    מקבל את סוג הדגם מהמשתמש בשלוש דרכים אפשריות:
    1. דרך command line argument (--model)
    2. דרך VIN (--vin)
    3. דרך interactive mode (--interactive)
    """

    # אפשרות 1: דרך --model
    if args.model:
        print(f"✅ דגם נבחר: {args.model}")
        return args.model

    # אפשרות 2: דרך --vin
    if args.vin:
        try:
            decoder = SmartVinDecoder()
            decoder.load_model("smart_vin_decoder.pkl")
            result = decoder.decode_vin(args.vin)

            if result and result.get('model_description'):
                model = result['model_description']
                confidence = result.get('confidence', 0)
                print(f"✅ דגם זוהה מ-VIN: {model} (Confidence: {confidence}%)")
                return model
            else:
                print(f"⚠️ לא הצלחתי לזהות דגם מ-VIN: {args.vin}")
        except Exception as e:
            print(f"❌ שגיאה בזיהוי VIN: {e}")

    # אפשרות 3: Interactive mode
    if args.interactive:
        print("\n=== מצב אינטראקטיבי ===")
        print("דוגמאות: Panamera GTS, Panamera 4S, Cayenne Turbo, Macan")
        model = input("הכנס את סוג הדגם: ").strip()
        if model:
            print(f"✅ דגם נבחר: {model}")
            return model
        else:
            print("⚠️ לא הוכנס דגם")

    # ברירת מחדל: קריאה מה-metadata של הקובץ
    print("⚠️ לא הוכנס דגם, נסה לקרוא מ-metadata...")
    return None


# מנוע ניקוד התאמה
KEYWORDS = [
    "oil", "filter", "spark", "plug", "brake", "fluid", "air",
    "pollen", "dust", "belt", "coolant", "grease", "lubricant",
    "paste", "transmission", "differential", "compressor", "allergen",
    "odour", "particle", "cleaner", "element"
]


def keyword_score(a: str, b: str) -> float:
    """ניקוד לפי מילות מפתח משותפות"""
    score = 0.0
    for kw in KEYWORDS:
        if kw in a and kw in b:
            score += 3.0
        elif kw in a or kw in b:
            score += 0.5
    return score


def similarity_score(a: str, b: str) -> float:
    """ניקוד דמיון בין מחרוזות"""
    return SequenceMatcher(None, a, b).ratio()


def score_match(service_line: str, pet_desc: str) -> float:
    """ציון כולל להתאמה"""
    a, b = clean(service_line), clean(pet_desc)
    return similarity_score(a, b) * 5.0 + keyword_score(a, b)


# ---------- כללי התאמה מיוחדים ----------

def apply_special_matching_rules(service_line: str, pet_rows: list, model_name: str):
    """
    מיישם כללי התאמה מיוחדים לפי דגם ותיאור השורה
    מחזיר רשימה של התאמות או None
    """
    service_clean = clean(service_line)
    model_upper = model_name.upper()

    # זיהוי אם מדובר ב-PANAMERA או CAYENNE
    is_panamera = "PANAMERA" in model_upper
    is_cayenne = "CAYENNE" in model_upper

    # כלל מיוחד: Fill in engine oil - בחירת הגירסה הגבוהה ביותר של X
    if "fill in engine oil" in service_clean or "fill engine oil" in service_clean:
        engine_oil_candidates = []
        for row in pet_rows:
            desc = row.get('Description', '')
            desc_clean = clean(desc)
            if "engine oil" in desc_clean:
                x_version = extract_x_version(desc)
                engine_oil_candidates.append({
                    "row": row,
                    "x_version": x_version
                })

        # בחירת השורה עם ה-X הגבוה ביותר
        if engine_oil_candidates:
            best_candidate = max(engine_oil_candidates, key=lambda x: x["x_version"])
            best_row = best_candidate["row"]

            # קבלת הכמות המתאימה לדגם
            oil_capacity = get_oil_capacity(model_name)
            quantity_str = f"{oil_capacity} L" if oil_capacity else best_row.get("Qty", "").strip()

            return [{
                "SERVICE LINE": service_line,
                "PART NUMBER": best_row.get("Part Number", "").strip(),
                "DESCRIPTION": best_row.get("Description", "").strip(),
                "REMARK": best_row.get("Remark", "").strip(),
                "QUANTITY": quantity_str,
                "CALCULATED_CAPACITY": oil_capacity  # שדה נוסף למעקב
            }]

    # כלל 1: עבור PANAMERA ו-CAYENNE - Change oil filter
    if (is_panamera or is_cayenne) and "change oil filter" in service_clean:
        # חיפוש "oil filter, with seal"
        matched_parts = []
        for row in pet_rows:
            desc_clean = clean(row.get('Description', ''))
            if "oil filter" in desc_clean and "with seal" in desc_clean:
                matched_parts.append({
                    "SERVICE LINE": service_line,
                    "PART NUMBER": row.get("Part Number", "").strip(),
                    "DESCRIPTION": row.get("Description", "").strip(),
                    "REMARK": row.get("Remark", "").strip(),
                    "QUANTITY": row.get("Qty", "").strip(),
                })

                # הוספת המק"טים הנוספים
                matched_parts.append({
                    "SERVICE LINE": service_line + " (פקק לאגן שמן)",
                    "PART NUMBER": "PAF911679",
                    "DESCRIPTION": "Oil drain plug",
                    "REMARK": "פקק לאגן שמן",
                    "QUANTITY": "1",
                })

                matched_parts.append({
                    "SERVICE LINE": service_line + " (שייבה לאגן שמן)",
                    "PART NUMBER": "PAF013849",
                    "DESCRIPTION": "Oil drain washer",
                    "REMARK": "שייבה לאגן שמן",
                    "QUANTITY": "1",
                })

                return matched_parts

    # כלל 2: עבור כל הדגמים - Air cleaner: replace filter element
    if "air cleaner" in service_clean and "replace filter element" in service_clean:
        for row in pet_rows:
            desc_clean = clean(row.get('Description', ''))
            if "air filter element" in desc_clean:
                return [{
                    "SERVICE LINE": service_line,
                    "PART NUMBER": row.get("Part Number", "").strip(),
                    "DESCRIPTION": row.get("Description", "").strip(),
                    "REMARK": row.get("Remark", "").strip(),
                    "QUANTITY": row.get("Qty", "").strip(),
                }]

    # כלל 3: עבור כל הדגמים - Particle filter: replace filter element
    if "particle filter" in service_clean and "replace filter element" in service_clean:
        for row in pet_rows:
            desc_clean = clean(row.get('Description', ''))
            if ("odour" in desc_clean and "allergen" in desc_clean and "filter" in desc_clean) or \
                    ("odour and allergen filter" in desc_clean):
                return [{
                    "SERVICE LINE": service_line,
                    "PART NUMBER": row.get("Part Number", "").strip(),
                    "DESCRIPTION": row.get("Description", "").strip(),
                    "REMARK": row.get("Remark", "").strip(),
                    "QUANTITY": row.get("Qty", "").strip(),
                }]

    return None


def best_pet_match(service_line: str, pet_rows: list, model_name: str = "", min_score: float = 2.0):
    """
    מחזיר את ההתאמה הטובה ביותר עם תמיכה בכללים מיוחדים
    """
    # בדיקה אם יש כלל מיוחד
    special_match = apply_special_matching_rules(service_line, pet_rows, model_name)
    if special_match:
        return special_match

    # התאמה רגילה לפי ניקוד
    best = None
    best_sc = -1.0

    for row in pet_rows:
        desc = row.get('Description', '')
        sc = score_match(service_line, desc)

        if sc > best_sc:
            best_sc = sc
            best = row

    if best_sc >= min_score and best:
        return [{
            "SERVICE LINE": service_line,
            "PART NUMBER": best.get("Part Number", "").strip(),
            "DESCRIPTION": best.get("Description", "").strip(),
            "REMARK": best.get("Remark", "").strip(),
            "QUANTITY": best.get("Qty", "").strip(),
        }]
    else:
        # אם לא נמצאה התאמה טובה
        return [{
            "SERVICE LINE": service_line,
            "PART NUMBER": "NOT FOUND",
            "DESCRIPTION": "לא נמצאה התאמה ב-PET",
            "REMARK": "",
            "QUANTITY": "",
        }]


# ---------- Main ----------

def main():
    # הגדרת command line arguments
    parser = argparse.ArgumentParser(
        description='התאמה אוטומטית בין Service Mapping ל-PET Lines',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
דוגמאות שימוש:
  python ServiceAndPetMatching_Enhanced.py --model "Panamera GTS"
  python ServiceAndPetMatching_Enhanced.py --vin WP0AA2A7XJLA12345
  python ServiceAndPetMatching_Enhanced.py --interactive
        """
    )
    parser.add_argument('--model', type=str, help='סוג הדגם (למשל: "Panamera GTS")')
    parser.add_argument('--vin', type=str, help='מספר VIN של הרכב')
    parser.add_argument('--interactive', action='store_true', help='מצב אינטראקטיבי')
    parser.add_argument('--service-file', type=str, help='נתיב לקובץ Service Classified')
    parser.add_argument('--pet-file', type=str, help='נתיב לקובץ PET Lines')
    parser.add_argument('--output', type=str, help='נתיב לקובץ פלט')

    args = parser.parse_args()

    # עדכון נתיבים אם הוזנו
    service_path = Path(args.service_file) if args.service_file else CLASSIFIED_SERVICE_PATH
    pet_path = Path(args.pet_file) if args.pet_file else PET_PATH
    output_path = Path(args.output) if args.output else OUTPUT_PATH

    # בדיקת קיום קבצים
    if not service_path.exists():
        raise FileNotFoundError(f"Classified service file not found: {service_path}")
    if not pet_path.exists():
        raise FileNotFoundError(f"PET lines not found: {pet_path}")

    # טעינת הקובץ המסווג
    with service_path.open("r", encoding="utf-8") as f:
        classified_data = json.load(f)

    # טעינת PET
    with pet_path.open("r", encoding="utf-8") as f:
        pet_rows = json.load(f)

    # קבלת שם הדגם מהמשתמש
    model_name = get_model_from_user(args)

    # אם לא הוכנס דגם, ננסה לקרוא מה-metadata
    if not model_name:
        model_name = classified_data.get("metadata", {}).get("model_variant", "Unknown")
        print(f"📋 נקרא דגם מ-metadata: {model_name}")

    # בדיקה אם יש כמות שמן מוגדרת לדגם
    oil_capacity = get_oil_capacity(model_name)
    if oil_capacity:
        print(f"🛢️  Oil capacity for {model_name}: {oil_capacity} L")
    else:
        print(f"⚠️  No oil capacity defined for {model_name}")

    output = {}

    # עבור כל service (15000, 30000 וכו')
    for service_key, service_data in classified_data.get("services", {}).items():
        matched_parts = []

        # עבור כל item ב-service
        for item in service_data.get("items", []):
            # רק אם הקטגוריה היא PARTS
            if item.get("category") == "PARTS":
                service_line = item.get("text", "")

                # התאמה מול PET
                matches = best_pet_match(service_line, pet_rows, model_name)
                matched_parts.extend(matches)

        output[service_key] = {
            "model": model_name,
            "oil_capacity": oil_capacity,
            "parts_count": len(matched_parts),
            "matched_parts": matched_parts
        }

    # שמירה
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Done! Output saved to: {output_path}")
    print(f"📊 Model: {model_name}")
    print(f"📦 Total services processed: {len(output)}")

    # סיכום
    total_parts = sum(s["parts_count"] for s in output.values())
    print(f"🔧 Total parts matched: {total_parts}")


if __name__ == "__main__":
    main()
