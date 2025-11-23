"""
step5_match_parts.py

Step 5: Match classified treatment lines (PARTS) to PET part numbers
Uses Porsche PET structure knowledge (Ill-No., Part Number patterns)

Updated rules:
1. Engine oil: Always prefer HIGHEST X version (X4 > X3 > X2)
2. Panamera/Cayenne oil filter: Must be "with seal" (NOT "complete")
3. Air cleaner filter: Engine air filter
4. Particle filter: Cabin/pollen/dust filter
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
import json
import re
from collections import OrderedDict

sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))
from oil_capacity_config import get_oil_capacity

ILL_NO_CATEGORIES = {
    '103': 'Spark plugs',
    '104': 'Engine oil system',
    '105': 'Coolant system',
    '106': 'Air intake/filters',
    '305': 'Differential/axle oils',
    '320': 'PDK/Transmission',
    '604': 'Brake system',
}

def sort_services_by_interval(services: Dict) -> Dict:
    time_dependent = {}
    km_services = {}
    for key, value in services.items():
        if "time-dependent" in key.lower() or "time dependent" in key.lower():
            time_dependent[key] = value
        else:
            km_services[key] = value
    def extract_km_from_header(header):
        match = re.search(r'(\d+)\s*tkm', header.lower())
        if match:
            return int(match.group(1)) * 1000
        return 999999
    sorted_km_services = OrderedDict(
        sorted(km_services.items(), key=lambda x: extract_km_from_header(x[0]))
    )
    for key, value in time_dependent.items():
        sorted_km_services[key] = value
    return sorted_km_services

def extract_x_version(description: str) -> int:
    """Extract X version (X3, X4, X10, etc.)"""
    match = re.search(r'x(\d+)', description.lower())
    if match:
        return int(match.group(1))
    return -1

def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'75\s*w\s*-?\s*90', '75w90', text)
    text = re.sub(r'ffl\s*-?\s*(\d+)', r'ffl\1', text)
    text = re.sub(r'dot\s*-?\s*(\d+)', r'dot\1', text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def get_ill_no_base(ill_no: str) -> str:
    if not ill_no:
        return ''
    match = re.match(r'(\d{3})', str(ill_no))
    if match:
        return match.group(1)
    return ''

def get_service_keywords(service_line: str) -> List[str]:
    service_lower = service_line.lower()
    keywords = []
    if "engine oil" in service_lower or "fill in" in service_lower:
        keywords.extend(["engine", "oil", "mobil", "v04"])
    if "oil filter" in service_lower:
        keywords.extend(["oil", "filter", "cartridge"])
    if "brake" in service_lower and "fluid" in service_lower:
        keywords.extend(["brake", "fluid", "dot"])
    if "air filter" in service_lower or "air cleaner" in service_lower:
        keywords.extend(["air", "filter", "engine", "intake"])
    if "cabin" in service_lower or "pollen" in service_lower or "particle filter" in service_lower:
        keywords.extend(["cabin", "pollen", "filter", "dust", "microfilter"])
    if "spark" in service_lower and "plug" in service_lower:
        keywords.extend(["spark", "plug"])
    if "coolant" in service_lower:
        keywords.extend(["coolant", "additive"])
    if "pdk" in service_lower:
        keywords.extend(["pdk", "transmission", "ffl"])
    if "rear" in service_lower and ("differential" in service_lower or "final drive" in service_lower):
        keywords.extend(["rear", "differential", "final", "drive", "75w90"])
    if "front" in service_lower and ("differential" in service_lower or "axle" in service_lower):
        keywords.extend(["front", "differential", "axle"])
    return keywords

def calculate_match_score_porsche(service_line: str, pet_part: Dict) -> float:
    service_norm = normalize_text(service_line)
    part_number = pet_part.get('Part Number', '')
    description = pet_part.get('Description', '')
    remark = pet_part.get('Remark', '')
    ill_no = pet_part.get('Ill-No.', '')
    pet_norm = normalize_text(f"{description} {remark}")
    ill_base = get_ill_no_base(ill_no)
    keywords = get_service_keywords(service_line)
    keyword_score = 0
    if keywords:
        for keyword in keywords:
            if keyword in pet_norm:
                keyword_score += 1
        keyword_score = keyword_score / len(keywords)
    boost = 0
    penalty = 0

    # CRITICAL RULE: Oil filter for Panamera/Cayenne MUST be "with seal"
    if "oil filter" in service_norm and "change" in service_norm:
        if "with seal" in pet_norm or "insert" in pet_norm:
            boost += 0.7  # Strong preference
        if "complete" in pet_norm or "discontinued" in pet_norm:
            penalty += 0.9  # Strong penalty

    # CRITICAL RULE: Air cleaner = Engine air filter
    if "air cleaner" in service_norm or ("air filter" in service_norm and "cabin" not in service_norm):
        if "engine" in pet_norm or "intake" in pet_norm or "air filter" in pet_norm:
            boost += 0.6
        if "cabin" in pet_norm or "pollen" in pet_norm:
            penalty += 0.9  # Wrong filter type

    # CRITICAL RULE: Particle filter = Cabin/pollen/dust filter
    if "particle filter" in service_norm or "cabin" in service_norm or "pollen" in service_norm:
        if "cabin" in pet_norm or "pollen" in pet_norm or "dust" in pet_norm or "microfilter" in pet_norm:
            boost += 0.6
        if "engine" in pet_norm and "air" in pet_norm and "cabin" not in pet_norm:
            penalty += 0.9  # Wrong filter type

    if "pdk" in service_norm:
        if ("ffl8" in pet_norm or "ffl4" in pet_norm):
            boost += 0.6
        else:
            penalty += 0.9
        if ill_base == '320':
            boost += 0.2
    if "rear" in service_norm and ("differential" in service_norm or "final" in service_norm):
        if "75w90" in pet_norm:
            boost += 0.6
        elif "ffl" in pet_norm:
            penalty += 0.9
        if ill_base == '305':
            boost += 0.2
    if "front" in service_norm and "differential" in service_norm:
        if "75w90" in pet_norm and "front" in pet_norm:
            boost += 0.6
        elif "ffl" in pet_norm:
            penalty += 0.9
        if ill_base == '305':
            boost += 0.2
    if ("engine oil" in service_norm or "fill in" in service_norm) and "filter" not in service_norm:
        if ill_base == '104':
            boost += 0.3
        if "filter" in pet_norm:
            penalty += 0.5
        # Penalty for discontinued parts
        if "discontinued" in pet_norm:
            penalty += 0.3
    if "brake" in service_norm and "fluid" in service_norm:
        if "dot" in pet_norm or ill_base == '604':
            boost += 0.4
    if "spark" in service_norm and "plug" in service_norm:
        if ill_base == '103':
            boost += 0.4
    if "coolant" in service_norm:
        if ill_base == '105':
            boost += 0.3
    final_score = keyword_score + boost - penalty
    return max(0, min(1, final_score))

def best_pet_match_porsche(service_line: str, pet_rows: List[Dict], model_name: str) -> List[Dict]:
    if not pet_rows:
        return []
    scored_parts = []
    for pet_row in pet_rows:
        part_num = pet_row.get('Part Number', '')
        description = pet_row.get('Description', '')
        remark = pet_row.get('Remark', '')
        ill_no = pet_row.get('Ill-No.', '')
        score = calculate_match_score_porsche(service_line, pet_row)
        if score > 0.3:
            scored_parts.append({
                'part_number': part_num,
                'description': description,
                'remark': remark,
                'ill_no': ill_no,
                'quantity': pet_row.get('Qty', '1'),
                'score': score
            })
    scored_parts.sort(key=lambda x: x['score'], reverse=True)
    if scored_parts:
        best_match = scored_parts[0]
        print(f"  ✅ Matched: {best_match['part_number']} (Ill-No: {best_match['ill_no']}, score: {best_match['score']:.2f})")
        return [best_match]
    else:
        print(f"  ⚠️ No match found")
        return []

def apply_special_rules(service_line: str, model_name: str, matches: List[Dict]) -> List[Dict]:
    service_lower = service_line.lower()
    model_lower = model_name.lower()
    is_panamera = 'panamera' in model_lower
    is_cayenne = 'cayenne' in model_lower

    # Rule 1: Oil filter for Panamera/Cayenne - add drain plug and washer
    if "change oil filter" in service_lower: #if (is_panamera or is_cayenne) and "change oil filter" in service_lower:
        if matches:
            result = [matches[0]]
            result.append({
                'part_number': 'PAF911679',
                'description': 'Oil drain plug',
                'remark': 'פקק לאגן שמן',
                'ill_no': '',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True
            })
            result.append({
                'part_number': 'PAF013849',
                'description': 'Oil drain washer',
                'remark': 'שייבה לאגן שמן',
                'ill_no': '',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True
            })
            print(f"  🔧 Added oil drain plug + washer")
            return result
        else:
            return matches

        # Rule 1: Oil filter for Panamera/Cayenne - add drain plug and washer
        if "change oil filter" in service_lower:  # if (is_panamera or is_cayenne) and "change oil filter" in service_lower:
            if matches:
                result = [matches[0]]
                result.append({
                    'part_number': 'PAF911679',
                    'description': 'Oil drain plug',
                    'remark': 'פקק לאגן שמן',
                    'ill_no': '',
                    'quantity': '1',
                    'score': 1.0,
                    'is_addon': True
                })
                result.append({
                    'part_number': 'PAF013849',
                    'description': 'Oil drain washer',
                    'remark': 'שייבה לאגן שמן',
                    'ill_no': '',
                    'quantity': '1',
                    'score': 1.0,
                    'is_addon': True
                })
                print(f"  🔧 Added oil drain plug + washer")
                return result
            else:
                return matches

    # Rule 2: Engine oil - ALWAYS prefer HIGHEST X version
    if ('fill in' in service_lower and 'engine oil' in service_lower) or 'engine oil' in service_lower:
        if matches:
            # Extract ALL X versions from candidates
            all_candidates = []
            for match in matches:
                desc = match.get('description', '')
                x_ver = extract_x_version(desc)
                all_candidates.append((x_ver, match))

            # Filter only those with X version
            x_versions = [(x, m) for x, m in all_candidates if x > 0]

            if x_versions:
                # Sort by X version (highest first)
                x_versions.sort(key=lambda x: x[0], reverse=True)
                highest_x = x_versions[0][1]
                print(f"  🔝 Selected HIGHEST X version: X{x_versions[0][0]}")
                return [highest_x]

    return matches[:1] if matches else []

def match_parts_to_services(classified_data: Dict, pet_data: List[Dict], model_description: str) -> Optional[Dict]:
    if not classified_data or "services" not in classified_data:
        print("❌ Invalid classified data")
        return None
    if not pet_data:
        print("❌ No PET data")
        return None
    print(f"🔧 Matching parts with Porsche PET Knowledge")
    print(f"Model: {model_description}")
    print(f"PET parts: {len(pet_data)}")
    oil_capacity = get_oil_capacity(model_description)
    if oil_capacity:
        print(f"✅ Oil capacity: {oil_capacity}L")
    else:
        print("⚠️ No oil capacity defined")
        oil_capacity = None
    matched_data = {}
    services = classified_data["services"]
    total_parts = 0
    matched_parts = 0
    not_found = 0
    for service_key, service_data in services.items():
        original_header = service_data.get("original_header", service_key)
        print(f"\n📋 Processing {service_key} ({original_header})...")
        items = service_data.get("items", [])
        if not items:
            print(f"  ⚠️ No items found")
            continue
        model_name = model_description
        service_output = {
            "model": model_name,
            "oil_capacity": oil_capacity,
            "matched_parts": []
        }
        for item in items:
            text = item.get("text", "")
            category = item.get("category", "")
            confidence = item.get("confidence", 0.5)
            if category != "PARTS":
                continue
            total_parts += 1
            matches = best_pet_match_porsche(text, pet_data, model_name)
            matches = apply_special_rules(text, model_name, matches)
            quantity = "1"
            if "engine oil" in text.lower() or "fill in" in text.lower():
                if oil_capacity:
                    quantity = str(oil_capacity)
            if matches:
                for match in matches:
                    is_addon = match.get('is_addon', False)
                    if is_addon:
                        service_line_text = f"{text} ({match.get('remark', '')})"
                    else:
                        service_line_text = text
                    service_output["matched_parts"].append({
                        "SERVICE LINE": service_line_text,
                        "CATEGORY": category,
                        "CONFIDENCE": confidence,
                        "PART NUMBER": match.get('part_number', 'NOT FOUND'),
                        "DESCRIPTION": match.get('description', ''),
                        "REMARK": match.get('remark', ''),
                        "QUANTITY": quantity if "oil" in text.lower() and not is_addon else match.get('quantity', '1'),
                        "MATCH SCORE": round(match.get('score', 0), 3)
                    })
                matched_parts += len(matches)
                print(f"  ✅ {text[:40]}... → {len(matches)} part(s)")
            else:
                service_output["matched_parts"].append({
                    "SERVICE LINE": text,
                    "CATEGORY": category,
                    "CONFIDENCE": confidence,
                    "PART NUMBER": "NOT FOUND",
                    "DESCRIPTION": "",
                    "REMARK": "",
                    "QUANTITY": quantity,
                    "MATCH SCORE": 0.0
                })
                not_found += 1
                print(f"  ⚠️ {text[:40]}... → NOT FOUND")
        matched_data[original_header] = service_output
    print(f"\n✅ Matching completed:")
    print(f"  Total PARTS lines: {total_parts}")
    print(f"  Successfully matched: {matched_parts}")
    print(f"  Not found: {not_found}")
    if not_found > 0:
        print(f"\n⚠️ Warning: {not_found} parts not matched")
    sorted_matched_data = sort_services_by_interval(matched_data)
    return sorted_matched_data

def _test():
    print("="*70)
    print("Testing Step 5: Porsche PET Knowledge Matching")
    print("="*70)
    print("\n✅ Ready!")
    print("Updated rules:")
    print("  1. Engine oil: HIGHEST X version preferred")
    print("  2. Panamera/Cayenne oil filter: Must be 'with seal'")
    print("  3. Air cleaner: Engine air filter")
    print("  4. Particle filter: Cabin/pollen/dust filter")

if __name__ == "__main__":
    _test()
