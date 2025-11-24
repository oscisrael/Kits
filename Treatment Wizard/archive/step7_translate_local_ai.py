"""
step7_translate.py – Clean Hebrew Translation with Ollama (Aya-Expanse)

Fixes included:
- Removes transliteration (Latin phonetic text)
- Ensures ONLY Hebrew output
- Removes any Latin characters if model inserts them
- Safe Windows encoding behavior (no utf-8 issues)
- Stronger translation prompt
- Preserves placeholders correctly
"""

import json
import re
from pathlib import Path
from typing import Dict, Any
import subprocess
import time


# =========================
# Key Translations
# =========================

KEY_TRANSLATIONS = {
    'model': 'דגם',
    'oil_capacity': 'קיבולת שמן מנוע',
    'service_number': 'טיפול מספר',
    'mileage_km': 'קילומטראז',
    'matched_parts': 'רכיבים',
    'SERVICE LINE': 'שורת טיפול',
    'PART NUMBER': 'מק"ט',
    'DESCRIPTION': 'תיאור החלק',
    'REMARK': 'הערה',
    'QUANTITY': 'כמות'
}

# Patterns to preserve exactly
PRESERVE_PATTERNS = [
    r'Porsche',
    r'Exxon Mobil',
    r'Mobil 1',
    r'Standard C40',
    r'ESC X4',
    r'PDK',
    r'\d+W[-\s]?\d+',
    r'FFL-\d+',
    r'\d+\.\d+\s*Ltr\.?',
    r'Page:\s*\d+',
]


# =========================
# Helper Functions
# =========================

def run_ollama_safe(args, prompt, timeout=120):
    """
    Runs Ollama safely on Windows by reading raw bytes and decoding manually.
    """
    proc = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False
    )

    try:
        out, err = proc.communicate(prompt.encode('utf-8'), timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return None, "TIMEOUT"

    # Decode manually to UTF-8, ignore bad bytes
    out_decoded = out.decode("utf-8", errors="ignore")
    err_decoded = err.decode("utf-8", errors="ignore")

    return out_decoded, err_decoded


def clean_latin(text: str) -> str:
    """
    Remove any English letters or mixed Latin added by the model.
    Ensures output is pure Hebrew + numbers + placeholders.
    """
    # Allow placeholders like __PRESERVE_0_1__
    placeholder_pattern = r'__PRESERVE_\d+_\d+__'

    # Temporarily protect placeholders
    preserved = re.findall(placeholder_pattern, text)
    for i, ph in enumerate(preserved):
        text = text.replace(ph, f"__TEMP_PH_{i}__")

    # Remove Latin characters a-zA-Z inside parentheses or outside
    text = re.sub(r'\([^)]*[A-Za-z][^)]*\)', '', text)
    text = re.sub(r'[A-Za-z]', '', text)

    # Clean leftover empty parentheses
    text = re.sub(r'\(\s*\)', '', text)

    # Restore placeholders
    for i, ph in enumerate(preserved):
        text = text.replace(f"__TEMP_PH_{i}__", ph)

    return text.strip()


def check_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=15)
        return result.returncode == 0
    except:
        return False


def check_model_exists(model: str) -> bool:
    """Check if model is installed."""
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        return model in result.stdout
    except:
        return False


# =========================
# Translation Core
# =========================

def translate_with_ollama(text: str, model: str = "aya-expanse") -> str:
    if not text or text.strip() == "":
        return text

    if any('\u0590' <= c <= '\u05FF' for c in text):
        return text

    if text.strip().upper() == "NOT FOUND":
        return "לא נמצא"

    preserved = {}
    temp = text
    for i, pattern in enumerate(PRESERVE_PATTERNS):
        for match in re.finditer(pattern, temp, re.IGNORECASE):
            ph = f"__PRESERVE_{i}_{len(preserved)}__"
            preserved[ph] = match.group()
            temp = temp.replace(match.group(), ph, 1)

    prompt = f"""
Translate to Hebrew:

Rules:
- Only pure Hebrew words.
- No transliteration.
- No English.
- No parentheses unless in source.
- Keep placeholders unchanged.

Text:
{temp}

Hebrew only:
""".strip()

    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            capture_output=True,
            timeout=90,
            text=True,                   # decode automatically
            encoding="utf-8",            # force utf-8
            errors="ignore"              # ignore bad bytes
        )

        if result.returncode != 0:
            print("⚠️ Ollama returned error:", result.stderr)
            return text

        output = result.stdout.strip()

        # Restore preserved items
        for ph, original in preserved.items():
            output = output.replace(ph, original)

        # Remove any English
        output = clean_latin(output)

        return output

    except subprocess.TimeoutExpired:
        print("⚠️ Timeout translating:", text[:40])
        return text


# =========================
# Recursive translation
# =========================

def translate_value(value: Any, key: str, model="aya-expanse") -> Any:
    if isinstance(value, str):
        if key == "PART NUMBER":
            return value
        return translate_with_ollama(value, model)

    if isinstance(value, list):
        return [translate_value(v, key, model) for v in value]

    if isinstance(value, dict):
        return translate_dict(value, model)

    return value


def translate_dict(data: Dict, model="aya-expanse") -> Dict:
    result = {}
    for key, value in data.items():

        # Translate keys
        heb_key = KEY_TRANSLATIONS.get(key, key)

        # Special case for parts list
        if key == "matched_parts" and isinstance(value, list):
            result[heb_key] = [translate_dict(p, model) for p in value]
        else:
            result[heb_key] = translate_value(value, key, model)

    return result


# =========================
# Main
# =========================

def translate_service_baskets(input_file: Path, output_file: Path, model="aya-expanse"):
    print("="*70)
    print("Step 7: Translate Service Baskets to Hebrew")
    print("="*70)

    if not check_ollama_running():
        print("❌ Ollama is not running!")
        return False

    if not check_model_exists(model):
        print(f"⚠️ Model {model} not found. Pulling...")
        subprocess.run(['ollama', 'pull', model])

    if not input_file.exists():
        print(f"❌ Missing file: {input_file}")
        return False

    print(f"📄 Loading {input_file} ...")
    data = json.load(open(input_file, encoding="utf-8"))
    print(f"🔍 Found {len(data)} top-level keys")

    print("🔄 Translating...")
    start = time.time()
    translated = translate_dict(data, model)
    print(f"⏳ Finished in {time.time() - start:.1f}s")

    print(f"💾 Saving → {output_file}")
    json.dump(translated, open(output_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("✅ Done!")
    return True


if __name__ == "__main__":
    translate_service_baskets(
        Path("Combined_Service_Baskets.json"),
        Path("Combined_Service_Baskets_Hebrew.json"),
        model="aya-expanse"
    )
