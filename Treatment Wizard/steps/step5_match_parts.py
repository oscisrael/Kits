"""
STEP 5: Match PARTS to PET part numbers
Final Version — Fully compatible with STEP 6 Basket Builder

🔥 DO NOT CHANGE OUTPUT STRUCTURE!
Keys must be the original PDF headers, e.g.:
{
  "Every 15 tkm/10 tmls or 1 year": {
      "model": "...",
      "oil_capacity": 8.5,
      "matched_parts": [ ... ]
  },
  "Every 120 tkm/80 tmls or 4 years": { ... },
  "Time-dependent": { ... }
}

Author: ChatGPT
"""

import re
import json
from typing import Dict, List, Optional
from difflib import SequenceMatcher
from collections import OrderedDict

# Import oil capacity function
from foundation_codes.oil_capacity_config import get_oil_capacity


# ------------------------------------------------------------
# Sort services exactly how STEP 6 expects
# ------------------------------------------------------------
def sort_services_by_interval(services: Dict) -> Dict:
    """
    Sort headers such as:
      "Every 15 tkm/10 tmls or 1 year"
      "Every 120 tkm/80 tmls or 4 years"
      "Time-dependent"  ← must always go last
    """

    time_dependent = {}
    km_services = {}

    for key, value in services.items():
        if "time-dependent" in key.lower() or "time dependent" in key.lower():
            time_dependent[key] = value
        else:
            km_services[key] = value

    def extract_km_from_header(header: str) -> int:
        match = re.search(r"(\d+)\s*tkm", header.lower())
        if match:
            return int(match.group(1)) * 1000
        return 999999999

    sorted_km = OrderedDict(
        sorted(km_services.items(), key=lambda x: extract_km_from_header(x[0]))
    )

    for key, value in time_dependent.items():
        sorted_km[key] = value

    return sorted_km


# ------------------------------------------------------------
# Text utilities
# ------------------------------------------------------------
def clean_text(t: str) -> str:
    t = (t or "").lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, clean_text(a), clean_text(b)).ratio()


def extract_x_version(desc: str) -> int:
    m = re.search(r"x(\d+)", desc.lower())
    return int(m.group(1)) if m else -1


# ------------------------------------------------------------
# PET matching logic (improved)
# ------------------------------------------------------------
def best_pet_match(service_line: str, pet_rows: List[Dict], model_name: str,
                   min_score: float = 0.28) -> List[Dict]:

    results = []
    s_low = service_line.lower()

    for row in pet_rows:
        desc = row.get("Description", "")
        remark = row.get("Remark", "")
        part = row.get("Part Number", "")

        score = similarity(service_line, desc)

        # Boost: engine oil (but NOT filter)
        if ("engine oil" in s_low or "fill in" in s_low) and \
           ("engine oil" in desc.lower()) and "filter" not in desc.lower():
            score += 0.35

        if score >= min_score:
            results.append({
                "part_number": part,
                "description": desc,
                "remark": remark,
                "quantity": row.get("Qty", "1"),
                "score": score
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# ------------------------------------------------------------
# Apply Porsche-specific matching rules
# ------------------------------------------------------------
def apply_special_rules(line: str, model: str, matches: List[Dict]) -> List[Dict]:

    l = line.lower()
    model_low = model.lower()

    is_panamera = "panamera" in model_low
    is_cayenne = "cayenne" in model_low

    # Oil filter: add drain plug + washer
    if (is_panamera or is_cayenne) and "change oil filter" in l and matches:
        base = matches[0]
        return [
            base,
            {
                "part_number": "PAF911679",
                "description": "Oil drain plug",
                "remark": "פקק אגן שמן",
                "quantity": "1",
                "score": 1.0,
                "is_addon": True
            },
            {
                "part_number": "PAF013849",
                "description": "Drain washer",
                "remark": "שייבה לאגן שמן",
                "quantity": "1",
                "score": 1.0,
                "is_addon": True
            }
        ]

    # Engine oil match selection priority
    if "fill in" in l and "engine oil" in l and matches:
        oils = []
        for m in matches:
            d = m.get("description", "").lower()
            if "engine" in d and "filter" not in d:
                oils.append(m)
        if not oils:
            return []

        # Choose by X version
        x_candidates = [(extract_x_version(m.get("description","")), m) for m in oils if extract_x_version(m.get("description","")) > 0]
        if x_candidates:
            x_candidates.sort(key=lambda x: x[0], reverse=True)
            return [x_candidates[0][1]]  # top X version
        return [oils[0]]

    return matches[:1] if matches else []


# ------------------------------------------------------------
# MAIN STEP 5 FUNCTION
# ------------------------------------------------------------
def match_parts_to_services(classified_data: Dict, pet_data: List[Dict],
                           model_description: str) -> Optional[Dict]:

    if not classified_data or "services" not in classified_data:
        print("❌ STEP 5 INPUT MISSING `services`")
        return None

    if not pet_data:
        print("❌ PET data missing")
        return None

    oil_capacity = get_oil_capacity(model_description)
    if oil_capacity:
        print(f"⛽ Oil capacity: {oil_capacity}L")
    else:
        oil_capacity = None
        print("⚠️ No oil capacity found")

    services = classified_data["services"]
    output = {}
    total, found, missing = 0, 0, 0

    for svc_key, svc in services.items():
        original_header = svc.get("original_header", svc_key)
        print(f"\n📌 {svc_key} → {original_header}")

        items = svc.get("items", [])
        service_result = {
            "model": model_description,
            "oil_capacity": oil_capacity,
            "matched_parts": []
        }

        for item in items:
            text = item.get("text", "")
            category = item.get("category", "")
            conf = item.get("confidence", 0.5)

            if category != "PARTS":
                continue

            total += 1

            matches = best_pet_match(text, pet_data, model_description)
            matches = apply_special_rules(text, model_description, matches)

            qty = "1"
            if "engine oil" in text.lower() and oil_capacity:
                qty = str(oil_capacity)

            if matches:
                found += 1
                for m in matches:
                    addon = m.get("is_addon", False)
                    svc_line = f"{text} ({m.get('remark','')})" if addon else text
                    service_result["matched_parts"].append({
                        "SERVICE LINE": svc_line,
                        "CATEGORY": category,
                        "CONFIDENCE": conf,
                        "PART NUMBER": m.get("part_number","NOT FOUND"),
                        "DESCRIPTION": m.get("description",""),
                        "REMARK": m.get("remark",""),
                        "QUANTITY": qty if ("oil" in text.lower() and not addon) else m.get("quantity","1"),
                        "MATCH SCORE": round(m.get("score",0),3)
                    })
            else:
                missing += 1
                print(f"   ❌ NOT FOUND: {text}")
                service_result["matched_parts"].append({
                    "SERVICE LINE": text,
                    "CATEGORY": category,
                    "CONFIDENCE": conf,
                    "PART NUMBER": "NOT FOUND",
                    "DESCRIPTION": "",
                    "REMARK": "",
                    "QUANTITY": qty,
                    "MATCH SCORE": 0.0
                })

        output[original_header] = service_result

    print("\n🎯 STEP 5 SUMMARY")
    print(f"   Total parts lines: {total}")
    print(f"   Found matches:     {found}")
    print(f"   Not matched:       {missing}")

    return sort_services_by_interval(output)
