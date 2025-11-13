"""
step6_create_service_baskets.py

Step 6: Create combined service baskets from Service_lines_with_part_number.json

OUTPUT: Clean JSON with:
- model and oil_capacity ONCE at top level
- No CATEGORY, CONFIDENCE, MATCH SCORE in parts
- Only: SERVICE LINE, PART NUMBER, DESCRIPTION, REMARK, QUANTITY
- Only service_number and mileage_km at service level
- Duplicates removed based on PART NUMBER
"""

import re
import json
from typing import Dict, List, Optional
from collections import OrderedDict

def extract_km_from_key(key: str) -> Optional[int]:
    """Extract km value from service key (e.g., 'Every 15 tkm...' → 15000)"""
    match = re.search(r'(\d+)\s*tkm', key.lower())
    if match:
        return int(match.group(1)) * 1000
    return None

def is_time_dependent(key: str) -> bool:
    """Check if a service key is time-dependent"""
    key_lower = key.lower()
    return "time-dependent" in key_lower or "time dependent" in key_lower

def clean_part(part: Dict) -> Dict:
    """
    Clean part by removing unnecessary fields
    Removes: CATEGORY, CONFIDENCE, MATCH SCORE
    Keeps: SERVICE LINE, PART NUMBER, DESCRIPTION, REMARK, QUANTITY
    """
    return {
        'SERVICE LINE': part.get('SERVICE LINE', ''),
        'PART NUMBER': part.get('PART NUMBER', ''),
        'DESCRIPTION': part.get('DESCRIPTION', ''),
        'REMARK': part.get('REMARK', ''),
        'QUANTITY': part.get('QUANTITY', '1')
    }

def remove_duplicate_parts(parts: List[Dict]) -> List[Dict]:
    """Remove duplicate parts based on PART NUMBER"""
    seen_part_numbers = set()
    unique_parts = []

    for part in parts:
        part_number = part.get('PART NUMBER', '')
        if not part_number:
            unique_parts.append(part)
            continue

        if part_number not in seen_part_numbers:
            seen_part_numbers.add(part_number)
            unique_parts.append(part)

    return unique_parts

def create_service_baskets(service_lines_data: Dict) -> Optional[Dict]:
    """
    Create combined service baskets from individual service lines

    Returns:
    Clean JSON with model/oil_capacity at top level:
    {
      "model": "Panamera GTS",
      "oil_capacity": 9.5,
      "15000": {
        "service_number": 1,
        "mileage_km": 15000,
        "matched_parts": [...]
      }
    }
    """
    if not service_lines_data:
        print("❌ Invalid service lines data")
        return None

    print("🔧 Creating combined service baskets...")

    # Extract all km-based services and time-dependent
    km_services = {}
    time_dependent_data = None

    for key, value in service_lines_data.items():
        km = extract_km_from_key(key)
        if km:
            km_services[km] = {
                'key': key,
                'data': value
            }
        elif is_time_dependent(key):
            time_dependent_data = value

    if not km_services:
        print("❌ No km-based services found")
        return None

    sorted_km_list = sorted(km_services.keys())
    print(f"✅ Found {len(sorted_km_list)} km-based services: {sorted_km_list}")

    if time_dependent_data:
        print(f"✅ Found Time-dependent service")

    # Get model and oil_capacity from first service (ONLY ONCE)
    base_service = km_services[sorted_km_list[0]]['data']
    model = base_service.get('model', 'Unknown')
    oil_capacity = base_service.get('oil_capacity', None)

    # Create combined baskets
    combined_baskets = {}

    for target_km in sorted_km_list:
        service_number = target_km // 15000
        print(f"\n📦 Building basket for {target_km} km (Service #{service_number})...")

        all_parts = []

        # Add all services that divide evenly into target_km
        for km in sorted_km_list:
            if target_km % km == 0:
                service_data = km_services[km]['data']
                parts = service_data.get('matched_parts', [])

                # Clean parts before adding
                cleaned_parts = [clean_part(part) for part in parts]
                all_parts.extend(cleaned_parts)
                print(f"  ✅ Including {km} km ({len(parts)} parts)")

        # Add Time-dependent if service number is even
        if service_number % 2 == 0 and time_dependent_data:
            time_parts = time_dependent_data.get('matched_parts', [])

            # Clean time-dependent parts before adding
            cleaned_time_parts = [clean_part(part) for part in time_parts]
            all_parts.extend(cleaned_time_parts)
            print(f"  ✅ Including Time-dependent ({len(time_parts)} parts)")

        # Remove duplicates
        parts_before = len(all_parts)
        unique_parts = remove_duplicate_parts(all_parts)
        parts_after = len(unique_parts)

        if parts_before != parts_after:
            duplicates_removed = parts_before - parts_after
            print(f"  🔄 Removed {duplicates_removed} duplicate(s)")

        # Create basket with only service_number and mileage_km
        combined_baskets[str(target_km)] = {
            'service_number': service_number,
            'mileage_km': target_km,
            'matched_parts': unique_parts
        }

        print(f"  📊 Final parts in basket: {parts_after} (from {parts_before} total)")

    # Create final output with model/oil_capacity at TOP level
    # Services added directly to root (not under "services" key)
    final_output = {
        'model': model,
        'oil_capacity': oil_capacity
    }

    # Add all services directly to root
    final_output.update(combined_baskets)

    print(f"\n✅ Created {len(combined_baskets)} service baskets")

    return final_output

def _test():
    """Test the step with sample data"""
    from pathlib import Path

    test_file = Path("Service_lines_with_part_number.json")

    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return

    print("="*70)
    print("Testing Step 6: Create Service Baskets (Clean Output)")
    print("="*70)

    with open(test_file, 'r', encoding='utf-8') as f:
        service_lines_data = json.load(f)

    result = create_service_baskets(service_lines_data)

    if result:
        print("\n✅ Basket creation successful!")

        output_path = Path("Combined_Service_Baskets.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Output saved to: {output_path}")
        print(f"\n📋 Clean Output Structure:")
        print(f"  Model: {result.get('model')}")
        print(f"  Oil Capacity: {result.get('oil_capacity')}L")

        # Count services (excluding model and oil_capacity keys)
        service_count = len([k for k in result.keys() if k not in ['model', 'oil_capacity']])
        print(f"  Services: {service_count} baskets")

        print("\n✅ Output is clean:")
        print("  - model/oil_capacity: ONCE at top level")
        print("  - Services directly in root (not under 'services' key)")
        print("  - No CATEGORY in parts")
        print("  - No CONFIDENCE in parts")
        print("  - No MATCH SCORE in parts")
        print("  - Only service_number and mileage_km at service level")
    else:
        print("\n❌ Basket creation failed")

if __name__ == "__main__":
    _test()
