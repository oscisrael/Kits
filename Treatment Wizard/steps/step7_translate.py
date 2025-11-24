"""
STEP 7: Hebrew Translation of SERVICE LINE (part names only, without verbs)

Logic:
1. For each SERVICE LINE:
   - First, try to infer the Hebrew name from the PET DESCRIPTION
     (e.g. distinguish engine air filter vs. cabin/pollen filter).
   - If no DESCRIPTION-based rule → try predefined text rules.
   - Else → call GPT to translate to Hebrew, but ask it to return ONLY
     the part name (no verbs, no instructions).

Input:  Combined_Service_Baskets.json
Output: Combined_Service_Baskets_HEB.json

Requires:
- OPENAI_API_KEY in environment
- pip install openai
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Dict
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

# -------------------------------
# Config
# -------------------------------
MODEL_GPT = "gpt-4.1-mini"
INPUT_PATH = Path("Combined_Service_Baskets.json")
OUTPUT_PATH = Path("Combined_Service_Baskets_HEB.json")
api_key = os.getenv("OPENAI_API_KEY")

client = OpenAI(
   api_key=api_key
)
# -------------------------------
# Translation override rules (by English SERVICE LINE)
# -------------------------------
# סדר חשוב – הרגולר אקספרשנים נבדקים לפי הסדר
TRANSLATION_RULES = [
    # כללים כלליים לפי הטקסט האנגלי
    (re.compile(r"replace spark plugs", re.IGNORECASE), "מצתים"),
    (re.compile(r"pdk.*change oil", re.IGNORECASE), "שמן גיר PDK"),
    (re.compile(r"all-wheel final drive.*change oil", re.IGNORECASE), "שמן דיפרנציאלי"),
    (re.compile(r"rear final drive.*change oil", re.IGNORECASE), "שמן סרן"),
    (re.compile(r"change oil filter", re.IGNORECASE), "מסנן שמן"),  # אחרי החוקים הספציפיים
    (re.compile(r"fill in engine oil", re.IGNORECASE), "שמן מנוע"),
    (re.compile(r"particle filter.*replace filter element", re.IGNORECASE), "מסנן חלקיקים למזגן"),
    (re.compile(r"change brake fluid", re.IGNORECASE), "נוזל בלמים"),
]

# Cache to avoid repeated GPT calls for same string
TRANSLATION_CACHE: Dict[str, str] = {}


# -------------------------------
# Rule-based translation (by English SERVICE LINE)
# -------------------------------
def apply_translation_rules(english_text: str) -> str | None:
    """Return Hebrew translation if a rule matches, else None."""
    for pattern, hebrew in TRANSLATION_RULES:
        if pattern.search(english_text):
            return hebrew
    return None


# -------------------------------
# Hebrew post-processing
# -------------------------------
def clean_hebrew_name(name: str) -> str:
    """
    Remove leading verbs / instructions from Hebrew, keep only the noun phrase.
    חשוב: נוגעים רק בתחילת המשפט – לא נוגעים באמצע (כמו PDK).
    """

    if not isinstance(name, str):
        return ""

    s = name.strip()

    # להסיר גרשיים מיותרים מסביב
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()

    # להסיר פעלים נפוצים בתחילת המשפט
    verb_patterns = [
        r"^(החלפת|החלפה|החלף|שינוי|שנה|בדיקת|בדיקה|בדוק|מילוי|מלא|מילאו|הוספת|הוסף|שימון|ניקוי|נקה)\s+",
        r"^(השתמש(?:ו)?\s+רק\s+ב|השתמש(?:ו)?\s+ב)\s+",
        r"^שמן\s+את\s+",
    ]

    for pat in verb_patterns:
        s = re.sub(pat, "", s).strip()

    # לרכך רווחים כפולים
    s = re.sub(r"\s+", " ", s).strip()

    return s


# -------------------------------
# GPT-based translation
# -------------------------------
def translate_with_gpt(english_text: str) -> str:
    """
    Use GPT to translate the service line to Hebrew.
    GPT is instructed to return ONLY the part name (noun phrase), no verbs.
    """
    prompt = f"""
You are an expert translator for automotive service operations.

Task:
Given an English service line describing an operation (e.g. "Change oil filter"),
return ONLY the name of the part/component in Hebrew, without any verb or instruction.

Rules:
- Output MUST be in Hebrew.
- NO verbs like "החלף", "שנה", "בדוק", "הוסף", "מלא", "השתמש", etc.
- Return only a short noun phrase (1–4 words), e.g.:
  - "Change oil filter" → "מסנן שמן"
  - "Fill in engine oil" → "שמן מנוע"
  - "Change brake fluid (use only original Porsche brake fluid)" → "נוזל בלמים"
  - "PDK transmission: change oil" → "שמן גיר PDK"

Input:
"{english_text}"

Return JSON ONLY in the following format:
{{"he": "<hebrew part name only>"}}
"""

    resp = client.chat.completions.create(
        model=MODEL_GPT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=60,
    )

    raw = resp.choices[0].message.content.strip()

    # ניסיון לפרש כ-JSON
    he = ""
    try:
        data = json.loads(raw)
        he = data.get("he", "").strip()
    except Exception:
        # אם המודל לא החזיר JSON, ניקח את הטקסט כמו שהוא
        he = raw.strip()

    he = clean_hebrew_name(he)
    return he or english_text  # fallback אחרון – לא להשאיר ריק


# -------------------------------
# DESCRIPTION-based overrides (מה-PET)
# -------------------------------
def hebrew_from_description(description: str) -> str | None:
    """
    אם אפשר להסיק את שם החלק מה-PET DESCRIPTION – נעשה את זה כאן.
    לדוגמה:
    - "Air filter element"          → מסנן אוויר מנוע
    - "Odour and allergen filter"   → מסנן חלקיקים למזגן
    - "Dust and pollen filter"      → מסנן חלקיקים למזגן
    """
    if not isinstance(description, str):
        return None

    desc = description.lower()

    # Engine air filter
    # Engine air filter
    if ("air filter element" in desc) or ("engine air filter" in desc) or ("air cleaner" in desc):
        return "מסנן אוויר למנוע"

    # Cabin / pollen / dust filter
    if "odour and allergen" in desc or "odor and allergen" in desc or "dust and pollen" in desc:
        return "מסנן חלקיקים למזגן"

    return None


# -------------------------------
# Main translation logic per line
# -------------------------------
def translate_value(service_line_original: str, description: str = "", part_number: str = "") -> str:
    """
    Decide how to translate a given line:
    0. Try DESCRIPTION-based rule (from PET).
    1. Check specific cases by DESCRIPTION or PART NUMBER.
    2. Then try predefined rules by English SERVICE LINE.
    3. If no rule → GPT translation + cleanup.
    """
    if not isinstance(service_line_original, str):
        return ""

    original = service_line_original.strip()

    # 0) ניסיון קודם כל לפי DESCRIPTION מה-PET
    #desc_based = hebrew_from_description(description or "")
    #if desc_based:
    #    return desc_based

    # 1) זיהוי ספציפי לפי DESCRIPTION - זה החלק החשוב!
    desc_lower = (description or "").lower()

    # אם זה "Change oil filter" - צריך לבדוק מה זה בדיוק לפי DESCRIPTION
    if "change oil filter" in original.lower():
        if "drain plug" in desc_lower or "oil drain plug" in desc_lower:
            return "פקק לאגן שמן"
        elif "drain washer" in desc_lower or "washer" in desc_lower or "sealing ring" in desc_lower:
            return "שייבה לאגן שמן"
        elif "oil filter" in desc_lower:
            return "מסנן שמן"

    if "פקק ריקון" in desc_lower:
        return "פקק ריקון"


    if "Particle filter: replace filter element" in original:
        return "מסנן חלקיקים למזגן"

    if "Air cleaner: replace filter element" in original:
        return "מסנן אוויר למנוע"



    # 2) rules (by English service line)
    rule_match = apply_translation_rules(original)
    if rule_match:
        return rule_match

    # 3) cache
    if original in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[original]

    # 4) GPT
    heb = translate_with_gpt(original)
    TRANSLATION_CACHE[original] = heb
    return heb


# -------------------------------
# Recursive traversal
# -------------------------------
def translate_service_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Traverse the combined service baskets structure and translate all SERVICE LINE fields.
    For each object with SERVICE LINE:
      - Take SERVICE LINE ORIGINAL if exists, else SERVICE LINE as source English.
      - Use DESCRIPTION (if exists) כדי להכריע בין מסנן אוויר מנוע / מסנן חלקיקים למזגן וכו'.
      - Write new SERVICE LINE ORIGINAL (English).
      - Write SERVICE LINE (Hebrew part name only).
    """

    def recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                if k == "SERVICE LINE" and isinstance(v, str):
                    original = obj.get("SERVICE LINE ORIGINAL", v)
                    description = obj.get("DESCRIPTION", "")
                    part_number = obj.get("PART NUMBER", "")  # הוסף שורה זו
                    hebrew = translate_value(original, description, part_number)  # עדכן את הקריאה
                    new_obj["SERVICE LINE ORIGINAL"] = original
                    new_obj["SERVICE LINE"] = hebrew
                    # לשמר גם את שאר השדות (PART NUMBER, QUANTITY וכו')
                    for kk, vv in obj.items():
                        if kk not in ("SERVICE LINE", "SERVICE LINE ORIGINAL"):
                            new_obj[kk] = recursive(vv)

                else:
                    new_obj[k] = recursive(v)
            return new_obj

        elif isinstance(obj, list):
            return [recursive(item) for item in obj]

        return obj

    return recursive(data)


# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    if not INPUT_PATH.exists():
        print(f"❌ קובץ הקלט לא נמצא: {INPUT_PATH}")
        raise SystemExit(1)

    print(f"📥 טוען קובץ: {INPUT_PATH}")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("🔁 מבצע תרגום על כל שורות SERVICE LINE...")
    translated = translate_service_data(data)

    print(f"💾 שומר פלט לקובץ: {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(translated, f, ensure_ascii=False, indent=2)

    print("✅ STEP 7 הושלם בהצלחה.")
