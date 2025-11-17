"""
STEP 7: Hebrew Translation (Part name only, no action verbs)
Fully revised according to new translation rules.

This script reads Combined_Service_Baskets.json and creates
Combined_Service_Baskets_HEB.json with:
  SERVICE LINE ORIGINAL
  SERVICE LINE (Hebrew short part name only)

Author: ChatGPT
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, Any


# Translation overrides (exact text or partial match rules)
TRANSLATION_RULES = [
    (re.compile(r"replace spark plugs", re.IGNORECASE), "מצתים"),
    (re.compile(r"pdk.*change oil", re.IGNORECASE), "שמן גיר PDK"),
    (re.compile(r"all-wheel final drive.*change oil", re.IGNORECASE), "שמן דיפרנציאלי"),
    (re.compile(r"rear final drive.*change oil", re.IGNORECASE), "שמן סרן"),
    (re.compile(r"change oil filter", re.IGNORECASE), "מסנן שמן"),
    (re.compile(r"fill in engine oil", re.IGNORECASE), "שמן מנוע"),
    (re.compile(r"particle filter.*replace filter element", re.IGNORECASE), "מסנן חלקיקים למזגן"),
    (re.compile(r"change brake fluid", re.IGNORECASE), "נוזל בלמים"),
]


def apply_translation_rules(text: str) -> str:
    """ Return translated part name according to rules """
    for pattern, hebrew in TRANSLATION_RULES:
        if pattern.search(text):
            return hebrew

    return None  # fallback later


def fallback_trim_translation(text: str) -> str:
    """
    If no rule matched, extract component name without action verb.
    Example:
      'Lubricate door arrester and fastening bolts' → 'door arrester and fastening bolts'
    """
    # Remove common English action verbs
    cleaned = re.sub(
        r"\b(change|replace|fill in|lubricate|use|inspect|check|tighten|install|remove)\b",
        "",
        text,
        flags=re.IGNORECASE
    )
    cleaned = cleaned.replace(":", " ").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def translate_value(original: str) -> str:
    """ Main translation logic """

    # 1) Try direct rule match
    rule_match = apply_translation_rules(original)
    if rule_match:
        return rule_match

    # 2) Fallback to generic component extraction
    return fallback_trim_translation(original)


def translate_service_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """ Traverse recursively and translate only SERVICE LINE values """

    def recursive(obj: Any) -> Any:
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                if k == "SERVICE LINE" and isinstance(v, str):
                    new_obj["SERVICE LINE ORIGINAL"] = v
                    new_obj[k] = translate_value(v)
                else:
                    new_obj[k] = recursive(v)
            return new_obj

        elif isinstance(obj, list):
            return [recursive(item) for item in obj]

        return obj

    return recursive(data)


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

    print(f"✅ תרגום בוצע בהצלחה → {output_path}")
