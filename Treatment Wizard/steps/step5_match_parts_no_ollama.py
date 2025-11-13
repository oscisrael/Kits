"""
step5_match_parts.py
Step 5: Match classified treatment lines (PARTS) to PET part numbers

INPUT:
- classified_data (from step 3)
- pet_data (from step 4)
- model_description (for oil capacity lookup)

OUTPUT: Final matched data with part numbers for each service

Features:
- Smart fuzzy matching between service lines and PET parts
- Special rules for specific models (Panamera/Cayenne oil filter add-ons)
- Oil capacity calculation from model
- Original PDF headers as keys
- Sorted by interval with time-dependent last
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
import json
import re
from difflib import SequenceMatcher
from collections import OrderedDict

# Add foundation_codes to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))

from oil_capacity_config import get_oil_capacity


def sort_services_by_interval(services: Dict) -> Dict:
    """
    Sort services by interval (km), with time_dependent always last
    Now works with original headers like "Every 15 tkm/10 tmls or 1 year"

    Args:
        services: Dict of services (unsorted)

    Returns:
        OrderedDict with sorted services
    """
    # Separate time_dependent from km-based services
    time_dependent = {}
    km_services = {}

    for key, value in services.items():
        if "time-dependent" in key.lower() or "time dependent" in key.lower():
            time_dependent[key] = value
        else:
            km_services[key] = value

    # Sort km-based services by extracting the km number
    def extract_km_from_header(header):
        """Extract km value from header (e.g., 'Every 15 tkm...' → 15000)"""
        match = re.search(r'(\d+)\s*tkm', header.lower())
        if match:
            return int(match.group(1)) * 1000
        return 999999

    sorted_km_services = OrderedDict(
        sorted(km_services.items(), key=lambda x: extract_km_from_header(x[0]))
    )

    # Add time_dependent at the end
    for key, value in time_dependent.items():
        sorted_km_services[key] = value

    return sorted_km_services


def clean_text(text: str) -> str:
    """
    Clean text for matching

    Args:
        text: Original text

    Returns:
        Cleaned lowercase text
    """
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_x_version(description: str) -> int:
    """
    Extract X version number from description (e.g., X3, X4, X10)

    Args:
        description: Part description

    Returns:
        X version number or -1 if not found
    """
    match = re.search(r'x(\d+)', description.lower())
    if match:
        return int(match.group(1))
    return -1


def similarity_score(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0.0 to 1.0)
    """
    return SequenceMatcher(None, clean_text(text1), clean_text(text2)).ratio()


def best_pet_match(service_line: str, pet_rows: List[Dict],
                   model_name: str, min_score: float = 0.25) -> List[Dict]:
    """
    Find best matching PET parts for a service line

    Args:
        service_line: Service line text (e.g., "Fill in engine oil")
        pet_rows: List of PET parts
        model_name: Model name for filtering
        min_score: Minimum similarity score (default 0.25 for broader matches)

    Returns:
        List of matched parts (sorted by score)
    """
    matches = []

    service_clean = clean_text(service_line)
    service_lower = service_line.lower()

    for pet_row in pet_rows:
        desc = pet_row.get('Description', '')
        remark = pet_row.get('Remark', '')
        part_num = pet_row.get('Part Number', '')

        # Special case: if service contains "engine oil" or "fill in", boost score if PET has "engine oil"
        desc_lower = desc.lower()
        boost_score = 0.0
        if ('engine oil' in service_lower or 'fill in' in service_lower):
            if 'engine oil' in desc_lower and 'filter' not in desc_lower:
                boost_score = 0.3  # Boost engine oil matches

        # Calculate scores
        desc_score = similarity_score(service_line, desc) + boost_score
        remark_score = similarity_score(service_line, remark) * 0.5  # Lower weight

        total_score = max(desc_score, remark_score)

        if total_score >= min_score:
            matches.append({
                'part_number': part_num,
                'description': desc,
                'remark': remark,
                'quantity': pet_row.get('Qty', '1'),
                'score': total_score
            })

    # Sort by score (descending)
    matches.sort(key=lambda x: x['score'], reverse=True)

    return matches


def apply_special_rules(service_line: str, model_name: str,
                        matches: List[Dict]) -> List[Dict]:
    """
    Apply special matching rules based on model and service type

    Args:
        service_line: Service line text
        model_name: Model name
        matches: Initial matches

    Returns:
        List of matched parts (with additions for oil filter case)
    """
    service_lower = service_line.lower()
    model_lower = model_name.lower()

    # Check if Panamera or Cayenne
    is_panamera = 'panamera' in model_lower
    is_cayenne = 'cayenne' in model_lower
    # Rule 1: Change oil filter - add drain plug and washer (Panamera/Cayenne only)
    if (is_panamera or is_cayenne) and "change oil filter" in service_lower:
        if matches:
            # Find "with seal" match specifically
            seal_match = None
            for match in matches:
                desc_lower = match.get('description', '').lower()
                if 'with seal' in desc_lower or 'seal' in desc_lower:
                    seal_match = match
                    break

            # If no "with seal" found, take first match
            if not seal_match:
                seal_match = matches[0]

            # Build result with oil filter + drain plug + washer
            result = [seal_match]

            # Add drain plug
            result.append({
                'part_number': 'PAF911679',
                'description': 'Oil drain plug',
                'remark': 'פקק לאגן שמן',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True
            })

            # Add drain washer
            result.append({
                'part_number': 'PAF013849',
                'description': 'Oil drain washer',
                'remark': 'שייבה לאגן שמן',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True
            })

            print(f"   🔧 Added oil drain plug + washer for Panamera/Cayenne")
            return result
        else:
            return matches

    # Rule 2: Fill in engine oil - ONLY match ENGINE oil (not oil filter!)
    if 'fill in' in service_lower and 'engine oil' in service_lower:
        if matches:
            # Filter matches: MUST contain "engine" or "motor" in description
            # AND must NOT contain "filter" (to exclude oil filter)
            engine_oil_matches = []
            for match in matches:
                desc_lower = match.get('description', '').lower()
                remark_lower = match.get('remark', '').lower()

                # Must have "engine" or "motor" in description/remark
                has_engine = ('engine' in desc_lower or 'motor' in desc_lower or
                              'engine' in remark_lower or 'motor' in remark_lower)

                # Must NOT have "filter" (excludes oil filter)
                has_no_filter = 'filter' not in desc_lower

                # Must NOT be cleaning/grease/brake
                is_not_noise = ('window' not in desc_lower and
                                'grease' not in desc_lower and
                                'brake' not in desc_lower and
                                'cleaning' not in desc_lower)

                if has_engine and has_no_filter and is_not_noise:
                    engine_oil_matches.append(match)

            if not engine_oil_matches:
                print(f"   ⚠️  No ENGINE OIL match found (filtered out filter/noise)")
                return []

            # Extract X versions from filtered matches
            x_versions = []
            for match in engine_oil_matches:
                desc = match.get('description', '')
                x_ver = extract_x_version(desc)
                if x_ver > 0:
                    x_versions.append((x_ver, match))

            if x_versions:
                # Sort by X version (descending)
                x_versions.sort(key=lambda x: x[0], reverse=True)

                # Prefer highest X version for performance models
                if 'gts' in model_lower or 'turbo' in model_lower:
                    return [x_versions[0][1]]  # Highest X
                else:
                    return [x_versions[-1][1]]  # Lowest X
            else:
                # No X version found, return best engine oil match
                return [engine_oil_matches[0]]

    # Rule 3: Oil filter - take first match
    if 'oil filter' in service_lower:
        if matches:
            return [matches[0]]

    # Rule 4: Brake pads - usually no part number (inspection)
    if 'brake' in service_lower and 'check' in service_lower:
        return []

    # Default: return ONLY top match (not top 3!)
    return matches[:1] if matches else []




def match_parts_to_services(classified_data: Dict, pet_data: List[Dict],
                           model_description: str) -> Optional[Dict]:
    """
    Match PARTS lines from classified treatments to PET part numbers

    Args:
        classified_data: Classified treatment data from step 3
        pet_data: PET part data from step 4
        model_description: Model description for oil capacity lookup

    Returns:
        Matched data with original headers:
        {
            "Every 15 tkm/10 tmls or 1 year": {
                "model": "Panamera GTS",
                "oil_capacity": 8.5,
                "matched_parts": [
                    {
                        "SERVICE LINE": "Fill in engine oil",
                        "CATEGORY": "PARTS",
                        "CONFIDENCE": 0.95,
                        "PART NUMBER": "000-043-206-71",
                        "DESCRIPTION": "Engine oil 0W-30 X4",
                        "REMARK": "Porsche Classic Motoroil",
                        "QUANTITY": "8.5",
                        "MATCH SCORE": 0.85
                    },
                    {
                        "SERVICE LINE": "Change oil filter (פקק לאגן שמן)",
                        "CATEGORY": "PARTS",
                        "CONFIDENCE": 0.98,
                        "PART NUMBER": "PAF911679",
                        "DESCRIPTION": "Oil drain plug",
                        "REMARK": "פקק לאגן שמן",
                        "QUANTITY": "1",
                        "MATCH SCORE": 1.0
                    },
                    ...
                ]
            },
            ...
        }

        Returns None if matching fails
    """
    if not classified_data or "services" not in classified_data:
        print("❌ Invalid classified data format")
        return None

    if not pet_data:
        print("❌ No PET data provided")
        return None

    print(f"Matching parts for model: {model_description}")

    # Get oil capacity for this model
    oil_capacity = get_oil_capacity(model_description)
    if oil_capacity:
        print(f"✅ Oil capacity: {oil_capacity}L")
    else:
        print("⚠️  No oil capacity defined for this model")
        oil_capacity = None

    # Prepare output
    matched_data = {}

    services = classified_data["services"]
    total_parts = 0
    matched_parts = 0
    not_found = 0

    # Process each service
    for service_key, service_data in services.items():
        # Extract original header
        original_header = service_data.get("original_header", service_key)

        print(f"\n📋 Processing {service_key} ({original_header})...")

        items = service_data.get("items", [])

        if not items:
            print(f"   ⚠️  No items found for {service_key}")
            continue

        # Use model_description from VIN (not from PDF header)
        model_name = model_description

        # Initialize service output
        service_output = {
            "model": model_name,
            "oil_capacity": oil_capacity,
            "matched_parts": []
        }

        # Process each item
        for item in items:
            text = item.get("text", "")
            category = item.get("category", "")
            confidence = item.get("confidence", 0.5)

            # Only match PARTS category
            if category != "PARTS":
                continue

            total_parts += 1

            # Find matches in PET
            matches = best_pet_match(text, pet_data, model_name, min_score=0.3)

            # Apply special rules
            matches = apply_special_rules(text, model_name, matches)

            # Handle oil quantity
            quantity = "1"
            if "engine oil" in text.lower() or "fill in" in text.lower():
                if oil_capacity:
                    quantity = str(oil_capacity)

            # Build output
            if matches:
                # Process all matches (including add-ons)
                for match in matches:
                    is_addon = match.get('is_addon', False)

                    # For add-ons, modify SERVICE LINE
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
                print(f"   ✅ {text[:40]}... → {len(matches)} part(s)")
            else:
                # No match found
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
                print(f"   ⚠️  {text[:40]}... → NOT FOUND")

        # ✅ Use original_header as key instead of service_key
        matched_data[original_header] = service_output

    print(f"\n✅ Matching completed:")
    print(f"   Total PARTS lines: {total_parts}")
    print(f"   Successfully matched: {matched_parts}")
    print(f"   Not found: {not_found}")

    if not_found > 0:
        print(f"\n⚠️  Warning: {not_found} parts could not be matched")
        print("   These will have 'NOT FOUND' as part number")

    # Sort services by interval (ascending), with time_dependent last
    sorted_matched_data = sort_services_by_interval(matched_data)

    return sorted_matched_data


# Test function (for standalone testing)
def _test():
    """Test the step with sample data"""
    from pathlib import Path

    # Sample classified data (from step 3)
    sample_classified = {
        "metadata": {},
        "services": {
            "service_15000": {
                "original_header": "Every 15 tkm/10 tmls or 1 year",
                "items": [
                    {
                        "text": "Fill in engine oil",
                        "category": "PARTS",
                        "confidence": 0.95,
                        "model_name": "Panamera GTS"
                    },
                    {
                        "text": "Change oil filter",
                        "category": "PARTS",
                        "confidence": 0.98,
                        "model_name": "Panamera GTS"
                    },
                    {
                        "text": "Check brake pads",
                        "category": "INSPECTION",
                        "confidence": 0.92,
                        "model_name": "Panamera GTS"
                    }
                ]
            }
        }
    }

    # Sample PET data (from step 4)
    sample_pet = [
        {
            "Part Number": "000-043-206-71",
            "Description": "Engine oil 0W-30 X4",
            "Remark": "Porsche Classic Motoroil SAE 20W-50",
            "Qty": "1",
            "Model": "Panamera"
        },
        {
            "Part Number": "000-043-206-88",
            "Description": "Oil filter element",
            "Remark": "",
            "Qty": "1",
            "Model": "Panamera"
        }
    ]

    print("="*70)
    print("Testing Step 5: Parts Matching")
    print("="*70)

    result = match_parts_to_services(sample_classified, sample_pet, "Panamera GTS")

    if result:
        print("\n✅ Matching successful!")

        # Save to test output
        output_path = Path("test_step5_output.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Test output saved to: {output_path}")

        # Show sample
        if result:
            first_service = list(result.keys())[0]
            first_data = result[first_service]
            print(f"\n📋 Sample output ({first_service}):")
            print(json.dumps(first_data, ensure_ascii=False, indent=2))
    else:
        print("\n❌ Matching failed")


if __name__ == "__main__":
    _test()
