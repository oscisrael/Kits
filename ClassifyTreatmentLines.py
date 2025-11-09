import requests
import json
import os
import glob
from datetime import datetime
from collections import defaultdict
from tqdm import tqdm


def normalize_model_name(model_name):
    """
    נרמל את שם הדגם - הסר / / כפולים
    """
    # החלף / / ב-/
    normalized = model_name.replace(' / / ', ' / ')
    return normalized


def sanitize_variant_name(variant_name):
    """
    נקה את שם הוריאנט כדי ליצור שם קובץ תקני
    הסר slashes, spaces, underscores כפולים
    """
    # החלף את כל הslashes ו-spaces בunderscore
    safe_name = variant_name.replace(' / ', '_').replace('/', '_').replace(' ', '_')

    # הסר תווים שאינם alphanumeric או underscore (כולל hyphen)
    safe_name = "".join(c for c in safe_name if c.isalnum() or c == '_')

    # הסר underscores כפולים/משולשים וכו'
    while '__' in safe_name:
        safe_name = safe_name.replace('__', '_')

    # הסר underscores בהתחלה או בסוף
    safe_name = safe_name.strip('_')

    # אם השם ריק, תן שם ברירת מחדל
    if not safe_name:
        safe_name = "model_variant"

    return safe_name


def classify_with_ollama(item, num_runs=1):
    """
    Classify item using Ollama with consistency-based confidence
    """
#     prompt = f"""Task: Classify this car service item.
#
# Service item: "{item}"
#
# Does this require ADDING or REPLACING a physical part (oil, filter, fluid, spark plug, etc.)?
#
# - Answer YES if it involves adding/replacing/changing parts
# - Answer NO if it's only inspection/checking/reading/resetting
#
# Important:
# - "Drain" without replacement = NO
# - "Fill" or "Change" or "Replace" = YES
# - "Check" or "Inspect" = NO
#
# Answer with ONLY one word: YES or NO"""

#     prompt = f"""Task: Classify the following car-service line into one of two categories:
# 1. PARTS — The line requires adding, replacing, installing, or changing a physical part or fluid.
# 2. INSPECTION — The line describes checking, inspecting, reading, resetting, cleaning, verifying, or any diagnostic or administrative action.
#
# Service item: "{item}"
#
# Strict classification rules:
# - Words meaning PARTS (always classify as PARTS):
#   "replace", "change", "fill", "refill", "install", "add", "top up", "renew".
# - Words meaning INSPECTION (always classify as INSPECTION):
#   "check", "inspect", "visual inspection", "read", "reset", "diagnose",
#   "diagnostic", "look", "verify", "test", "measure", "prepare report".
# - Special rules:
#   - "Drain" alone (without any replace/fill/change) = INSPECTION.
#   - "Replace filter element" or any filter replacement = PARTS.
#   - Changing/adding/refilling ANY oil/fluid = PARTS.
#   - Any cleaning system check = INSPECTION.
#   - Administrative tasks (prepare report, read memory) = INSPECTION.
# - If both categories appear (e.g., "check and replace") → classify as PARTS.
# - When in doubt → choose INSPECTION.
#
# Output format:
# Respond with a single word only: "YES" for PARTS or "NO" for INSPECTION.
# No explanation. No additional text. Only YES or NO.
# """

    prompt = f"""Task: Classify the following car-service line into one of two categories:
- PARTS → The line requires adding, replacing, filling, changing, renewing, installing, or topping up any physical part or fluid.
- INSPECTION → The line describes checking, inspecting, reading, resetting, measuring, diagnosing, cleaning, verifying, visually inspecting, or any administrative or functional check.

Service item: "{item}"

Classification Rules (strict and deterministic):

PARTS category keywords (always classify as PARTS if any appear):
"replace", "change", "fill", "refill", "add", "install", "renew", 
"top up", "replenish", "replace filter", "replace element", "replace fluid",
"replace spark", "oil change", "fluid change".

INSPECTION category keywords (always classify as INSPECTION if ONLY these appear):
"check", "inspect", "inspection", "visual inspection",
"read", "reset", "diagnose", "diagnostic", "verify",
"measure", "look", "test", "drain", "prepare report",
"check function", "check condition", "check level",
"read out memory", "reset maintenance interval".

Special rules:
- "Drain" WITHOUT "replace/change/fill/add" = INSPECTION.
- ANY mention of a filter replacement = PARTS.
- ANY addition/refill/change of a liquid/oil/fluid = PARTS.
- ANY combination of both (e.g. “check and replace”) = PARTS always wins.
- Administrative actions (prepare report, reset, read memory) = INSPECTION.
- When the meaning is ambiguous → classify as INSPECTION.

Output format:
Respond with ONE WORD ONLY:
- "YES" → if the line is PARTS
- "NO" → if the line is INSPECTION
Do NOT add explanations, reasoning, or extra text.
"""
    results = []

    for run in range(num_runs):
        try:
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    "model": "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.3}
                },
                timeout=120
            )

            if response.status_code == 200:
                answer = response.json()['response'].strip().upper()
                if 'YES' in answer:
                    results.append('YES')
                elif 'NO' in answer:
                    results.append('NO')
                else:
                    results.append('UNCLEAR')
        except Exception as e:
            print(f"Error on run {run + 1}: {e}")
            results.append('ERROR')

    # Calculate confidence
    yes_count = results.count('YES')
    no_count = results.count('NO')
    total_valid = yes_count + no_count

    if total_valid == 0:
        return 'ERROR', 0

    if yes_count > no_count:
        confidence = int((yes_count / total_valid) * 100)
        return 'PARTS', confidence
    else:
        confidence = int((no_count / total_valid) * 100)
        return 'INSPECTION', confidence


def deduplicate_items(all_json_data):
    """
    אסוף את כל הפריטים מכל ה-JSONs,
    הסר כפילויות והחזר רשימה של פריטים ייחודיים
    """
    unique_items = set()

    for json_file_data in all_json_data:
        for service_key, models_dict in json_file_data.items():
            if isinstance(models_dict, dict):
                for model_name, items_list in models_dict.items():
                    if isinstance(items_list, list):
                        for item in items_list:
                            unique_items.add(item)

    return list(unique_items)


def classify_unique_items(unique_items):
    """
    סווג את כל הפריטים הייחודיים (פעם אחת כל פריט)
    החזר dictionary: {item_text: {category, confidence}}
    """
    classifications = {}

    print(f"\n{'=' * 80}")
    print(f"CLASSIFYING {len(unique_items)} UNIQUE ITEMS")
    print(f"{'=' * 80}\n")

    for item in tqdm(unique_items, desc="Classifying items", unit="item"):
        category, confidence = classify_with_ollama(item, num_runs=3)
        classifications[item] = {
            'category': 'PARTS' if category == 'PARTS' else 'INSPECTION',
            'confidence': confidence
        }

    return classifications


def load_json_files(folder_path):
    """
    טען את כל קבצי ה-JSON מהתיקייה
    """
    json_files = glob.glob(os.path.join(folder_path, "*.json"))

    if not json_files:
        print(f"❌ No JSON files found in {folder_path}")
        return []

    all_data = []
    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_data.append({
                    'filename': os.path.basename(json_file),
                    'data': data
                })
                print(f"✅ Loaded: {os.path.basename(json_file)}")
        except Exception as e:
            print(f"❌ Error loading {json_file}: {e}")

    return all_data


def extract_model_variants(json_file_data):
    """
    חלץ את כל וריאנטי הדגמים מ-JSON
    נרמל שמות דגמים לפני קיבוץ (הסר / / כפולים)

    החזר: {model_variant_name: {service_key: [items]}}
    """
    model_variants = defaultdict(lambda: defaultdict(list))

    for service_key, models_dict in json_file_data.items():
        if isinstance(models_dict, dict):
            for model_name, items_list in models_dict.items():
                # נרמל את שם הדגם
                normalized_model_name = normalize_model_name(model_name)

                if isinstance(items_list, list):
                    for item in items_list:
                        model_variants[normalized_model_name][service_key].append(item)

    return dict(model_variants)


def process_json_file(json_file_info, classifications, output_base_path):
    """
    עבדו קובץ JSON בודד - עם DEBUG
    1. חלץ וריאנטי דגמים
    2. לכל וריאנט, צור קובץ output בנפרד
    """
    json_filename = json_file_info['filename']
    json_data = json_file_info['data']

    # חלץ וריאנטי דגמים (עם נורמליזציה)
    model_variants = extract_model_variants(json_data)

    print(f"\n{'=' * 80}")
    print(f"📄 Processing: {json_filename}")
    print(f"{'=' * 80}")
    print(f"Found {len(model_variants)} model variant(s)")

    # עבור כל וריאנט דגם, צור קובץ output
    for variant_idx, (variant_name, services_dict) in enumerate(model_variants.items(), 1):
        print(f"\n[{variant_idx}/{len(model_variants)}] Processing variant: {variant_name}")

        # DEBUG: הראה את כל השירותים
        print(f"  Services in this variant: {list(services_dict.keys())}")

        # המרת שם הוריאנט לשם קובץ - עם ניקוי כפול
        safe_variant_name = sanitize_variant_name(variant_name)

        # יצירת תיקייה לדגם זה
        model_folder = os.path.join(output_base_path, safe_variant_name)
        os.makedirs(model_folder, exist_ok=True)

        # Progress bar לעיבוד השירותים
        pbar = tqdm(total=len(services_dict), desc=f"  Processing services", unit="service")

        # בנה את ה-output structure
        classified_output = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'source_file': json_filename,
                'model_variant': variant_name,
                'classifier': 'ollama-llama3.2'
            },
            'services': {}
        }

        parts_items = []
        inspection_items = []
        missing_items_count = 0

        for service_key, items_list in services_dict.items():
            print(f"    Processing {service_key}: {len(items_list)} items")

            classified_output['services'][service_key] = {
                'items': [],
                'summary': {
                    'total': 0,
                    'parts': 0,
                    'inspection': 0
                }
            }

            for item in items_list:
                if item in classifications:
                    classification = classifications[item]
                    category = classification['category']
                    confidence = classification['confidence']

                    item_entry = {
                        'text': item,
                        'category': category,
                        'confidence': confidence
                    }

                    classified_output['services'][service_key]['items'].append(item_entry)
                    classified_output['services'][service_key]['summary']['total'] += 1

                    if category == 'PARTS':
                        classified_output['services'][service_key]['summary']['parts'] += 1
                        parts_items.append(item_entry)
                    else:
                        classified_output['services'][service_key]['summary']['inspection'] += 1
                        inspection_items.append(item_entry)
                else:
                    # DEBUG: פריט לא נמצא בסיווגים
                    print(f"      ⚠️  Item not in classifications: {item[:50]}...")
                    missing_items_count += 1

            pbar.update(1)

        pbar.close()

        if missing_items_count > 0:
            print(f"  ⚠️  Total missing items: {missing_items_count}")

        # מיון לפי confidence
        parts_items.sort(key=lambda x: x['confidence'], reverse=True)
        inspection_items.sort(key=lambda x: x['confidence'], reverse=True)

        classified_output['metadata']['total_items'] = sum(
            s['summary']['total'] for s in classified_output['services'].values()
        )
        classified_output['metadata']['parts_count'] = len(parts_items)
        classified_output['metadata']['inspection_count'] = len(inspection_items)

        # שמור קבצים

        # 1. קובץ ראשי (הכל)
        main_output_file = os.path.join(
            model_folder,
            f"{safe_variant_name}_classified.json"
        )
        # with open(main_output_file, 'w', encoding='utf-8') as f:
        #     json.dump(classified_output, f, ensure_ascii=False, indent=2)
        # print(f"  ✅ Saved: {os.path.basename(main_output_file)}")
        #
        # # 2. קובץ parts בלבד
        # parts_output_file = os.path.join(
        #     model_folder,
        #     f"{safe_variant_name}_parts_only.json"
        # )
        # with open(parts_output_file, 'w', encoding='utf-8') as f:
        #     json.dump(parts_items, f, ensure_ascii=False, indent=2)
        # print(f"  ✅ Saved: {os.path.basename(parts_output_file)}")
        #
        # # 3. קובץ inspection בלבד
        # inspection_output_file = os.path.join(
        #     model_folder,
        #     f"{safe_variant_name}_inspection_only.json"
        # )
        # with open(inspection_output_file, 'w', encoding='utf-8') as f:
        #     json.dump(inspection_items, f, ensure_ascii=False, indent=2)
        # print(f"  ✅ Saved: {os.path.basename(inspection_output_file)}")

        # סיכום
        print(f"\n  📊 Summary for {variant_name}:")
        print(f"     Total items: {classified_output['metadata']['total_items']}")
        print(f"     Parts: {len(parts_items)}")
        print(f"     Inspection: {len(inspection_items)}")


def main():
    print("=" * 80)
    print("🔥 PORSCHE SERVICE ITEMS CLASSIFIER - JSON MODE (WITH DEBUG)")
    print("=" * 80)

    # Check Ollama
    try:
        response = requests.get('http://localhost:11434/api/version', timeout=5)
        if response.status_code != 200:
            print("❌ ERROR: Ollama is not running!")
            print("   Start it with: ollama serve")
            return
    except:
        print("❌ ERROR: Cannot connect to Ollama!")
        print("   Make sure Ollama is installed and running")
        return

    # Get folder path
    print("\n📁 Enter the folder path containing JSON files:")
    folder_path = input("Path: ").strip()

    if not os.path.isdir(folder_path):
        print(f"❌ ERROR: '{folder_path}' is not a valid directory!")
        return

    # Load JSON files
    print(f"\n📂 Loading JSON files from: {folder_path}")
    all_json_files = load_json_files(folder_path)

    if not all_json_files:
        print("❌ No JSON files loaded!")
        return

    print(f"\n✅ Loaded {len(all_json_files)} JSON file(s)")

    # Deduplicate items across all JSONs
    print("\n🔍 Deduplicating items across all JSON files...")
    all_json_data = [item['data'] for item in all_json_files]
    unique_items = deduplicate_items(all_json_data)

    print(f"✅ Found {len(unique_items)} unique items to classify")

    # Classify unique items
    classifications = classify_unique_items(unique_items)

    # DEBUG: הראה כמה פריטים סווגו
    print(f"\n🔍 DEBUG - Classifications summary:")
    print(f"   Total classifications: {len(classifications)}")
    parts_count = sum(1 for c in classifications.values() if c['category'] == 'PARTS')
    inspection_count = sum(1 for c in classifications.values() if c['category'] == 'INSPECTION')
    print(f"   Parts: {parts_count}")
    print(f"   Inspection: {inspection_count}")

    # Create output directory structure
    output_base_path = "Classification Results"
    os.makedirs(output_base_path, exist_ok=True)

    # Process each JSON file
    print(f"\n{'=' * 80}")
    print("📋 PROCESSING JSON FILES")
    print(f"{'=' * 80}")

    for json_file_info in all_json_files:
        process_json_file(json_file_info, classifications, output_base_path)

    # Summary
    print(f"\n{'=' * 80}")
    print("✅ CLASSIFICATION COMPLETE!")
    print(f"{'=' * 80}")
    print(f"📂 Output folder: {output_base_path}")
    print(f"🔧 Total unique items classified: {len(unique_items)}")
    print(f"📊 Classification files created in subfolders by model variant")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
