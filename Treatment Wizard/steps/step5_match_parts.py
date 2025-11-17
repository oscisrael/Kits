import json
import os
import difflib

# --- הגדרות זיהוי פילטרים לפי DESCRIPTION בקובץ ה-PET ---
ENGINE_AIR_KEYWORDS = [
    "air filter element", "engine air filter", "air cleaner element", "air cleaner"
]

CABIN_FILTER_KEYWORDS = [
    "dust and pollen filter", "pollen filter", "odour and allergen filter",
    "combination filter", "particle filter"
]

def is_engine_air_filter(desc: str) -> bool:
    d = desc.lower()
    return any(k in d for k in ENGINE_AIR_KEYWORDS)

def is_cabin_filter(desc: str) -> bool:
    d = desc.lower()
    return any(k in d for k in CABIN_FILTER_KEYWORDS)

# --- פונקציית התאמת חלקים ---
def find_best_pet_match(description, pet_parts):
    desc = description.lower()

    # 1️⃣ ניסיון התאמה לפילטר מנוע
    if is_engine_air_filter(desc):
        for p in pet_parts:
            if is_engine_air_filter(str(p.get("Description", "")).lower()):
                return p

    # 2️⃣ ניסיון התאמה לפילטר מזגן
    if is_cabin_filter(desc):
        for p in pet_parts:
            if is_cabin_filter(str(p.get("Description", "")).lower()):
                return p

    # 3️⃣ Fallback למידת דמיון
    best_match = None
    best_ratio = 0.0
    for p in pet_parts:
        ratio = difflib.SequenceMatcher(None, desc, str(p.get("Description", "")).lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = p

    if best_ratio > 0.60:
        return best_match

    return None


# --- עיבוד קובץ ה-Service Lines ---
def match_parts_to_services(service_file, pet_file, output_file, model_name):
    with open(service_file, encoding="utf-8") as f:
        service_lines = json.load(f)

    with open(pet_file, encoding="utf-8") as f:
        pet_parts = json.load(f)

    results = []

    for item in service_lines:

        # Normalize string-only items
        if isinstance(item, str):
            item = {
                "SERVICE LINE ORIGINAL": item,
                "SERVICE LINE": item,
                "DESCRIPTION": item
            }

        original = item.get("SERVICE LINE ORIGINAL", "")
        description = item.get("DESCRIPTION", "")

        matched = find_best_pet_match(description, pet_parts)
        part_number = matched.get("Part Number") if matched else ""
        remark = matched.get("Remark") if matched else ""
        qty = matched.get("Qty") if matched else ""

        # 🟢 טיפול מיוחד: Panamera / Cayenne → Change Oil Filter מוסיף פקק + שייבה
        if (
            "oil filter" in description.lower()
            and model_name
            and model_name.lower() in ["panamera", "cayenne"]
        ):
            results.append({
                "SERVICE LINE ORIGINAL": original,
                "SERVICE LINE": "פקק לאגן שמן",
                "PART NUMBER": "00004321044",
                "DESCRIPTION": "Oil drain plug",
                "REMARK": "",
                "QUANTITY": "1"
            })
            results.append({
                "SERVICE LINE ORIGINAL": original,
                "SERVICE LINE": "שייבה לאגן שמן",
                "PART NUMBER": "90012310630",
                "DESCRIPTION": "Oil washer",
                "REMARK": "",
                "QUANTITY": "1"
            })

        # שורת הבסיס (תמיד תתווסף)
        results.append({
            "SERVICE LINE ORIGINAL": original,
            "SERVICE LINE": item.get("SERVICE LINE", ""),
            "PART NUMBER": part_number,
            "DESCRIPTION": description,
            "REMARK": remark,
            "QUANTITY": qty
        })

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return output_file


if __name__ == "__main__":
    base = os.path.dirname(__file__)
    service_file = os.path.join(base, "..", "Service_lines.json")
    pet_file = os.path.join(base, "..", "PET.json")
    output = os.path.join(base, "..", "Service_lines_with_part_number.json")
    match_parts_to_services(service_file, pet_file, output, model_name="Panamera")
    print("✔ STEP 5 completed")
