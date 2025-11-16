import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from openai import OpenAI
from datetime import datetime

client = OpenAI(
    api_key="***REMOVED***"
)
CACHE_FILE = Path(__file__).parent / "translation_cache.json"

# טקסטים מיוחדים שמחליפים את התרגום בתוכן הסוגריים
SPECIAL_PATTERNS = [
    re.compile(r"Change oil filter \(([^)]+)\)", re.IGNORECASE),
]

def load_cache() -> Dict[str, str]:
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(cache: Dict[str, str]) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def extract_special_translation(text: str) -> str:
    for pattern in SPECIAL_PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            return match.group(1).strip()
    return None

def translate_text(text: str, cache: Dict[str, str]) -> str:
    # בדיקת cache קודם
    if text in cache:
        return cache[text]

    # בדיקה אם יש תרגום מיוחד
    special = extract_special_translation(text)
    if special is not None:
        cache[text] = special
        return special

    # פנייה ל-API לתרגום
    prompt = f"Translate the following phrase to Hebrew, only the phrase:\n{text}\nHebrew only, without transliteration."

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
        )
        translation = response.choices[0].message.content.strip()
        cache[text] = translation
        return translation
    except Exception as e:
        print(f"⚠️ Translation error for '{text}': {e}")
        return text  # במקרה של שגיאה מחזיר את הטקסט המקורי

def translate_service_data(data: Dict[str, Any]) -> Dict[str, Any]:
    cache = load_cache()

    def recursive_translate(obj: Any) -> Any:
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                # רק עבור מפתח SERVICE LINE מתרגמים ערך (האם הוא מחרוזת)
                if k == "SERVICE LINE" and isinstance(v, str):
                    translated_val = translate_text(v, cache)
                    new_obj["SERVICE LINE ORIGINAL"] = v
                    new_obj[k] = translated_val
                else:
                    new_obj[k] = recursive_translate(v)
            return new_obj
        elif isinstance(obj, list):
            return [recursive_translate(i) for i in obj]
        else:
            return obj
    translated = recursive_translate(data)
    save_cache(cache)
    return translated


if __name__ == "__main__":
    input_path = Path("Combined_Service_Baskets.json")
    output_path = Path("Combined_Service_Baskets_HEB.json")

    if not input_path.exists():
        print(f"❌ קובץ הקלט חסר: {input_path}")
        exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    translated_data = translate_service_data(data)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translated_data, f, ensure_ascii=False, indent=2)

    print(f"✅ תרגום הוצלח ושמור בקובץ: {output_path}")
