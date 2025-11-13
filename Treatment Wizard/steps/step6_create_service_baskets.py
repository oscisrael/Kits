"""
step6_create_service_baskets.py

Step 6: Create combined service baskets from Service_lines_with_part_number.json

INPUT:
- service_lines_data (from step 5): Service_lines_with_part_number.json

OUTPUT: Combined_Service_Baskets.json
- Combined service baskets where each service includes all relevant sub-services

Logic:
1. Extract all km-based services (15000, 30000, 45000, etc.)
2. For each target service, include all services that divide evenly into it
3. Add Time-dependent for even service numbers (2, 4, 6, 8, ...)

Example:
- Service 90000 (service #6) includes:
  * 15000 (90000 % 15000 = 0)
  * 30000 (90000 % 30000 = 0)
  * 45000 (90000 % 45000 = 0)
  * 90000 itself
  * Time-dependent (6 % 2 = 0)
"""

import re
from typing import Dict, List, Optional
from collections import OrderedDict


def extract_km_from_key(key: str) -> Optional[int]:
    """
    Extract km value from service key (e.g., 'Every 15 tkm...' → 15000)

    Args:
        key: Service key from JSON

    Returns:
        Km value (int) or None if not found
    """
    match = re.search(r'(\d+)\s*tkm', key.lower())
    if match:
        return int(match.group(1)) * 1000
    return None


def is_time_dependent(key: str) -> bool:
    """
    Check if a service key is time-dependent

    Args:
        key: Service key from JSON

    Returns:
        True if time-dependent, False otherwise
    """
    key_lower = key.lower()
    return "time-dependent" in key_lower or "time dependent" in key_lower


def create_service_baskets(service_lines_data: Dict) -> Optional[Dict]:
    """
    Create combined service baskets from individual service lines

    Args:
        service_lines_data: Service_lines_with_part_number.json data (from step 5)

    Returns:
        Combined service baskets as dict:
        {
            "15000": {
                "service_number": 1,
                "mileage_km": 15000,
                "model": "Panamera GTS",
                "oil_capacity": 9.5,
                "matched_parts": [...]
            },
            ...
        }
    """
    if not service_lines_data:
        print("❌ Invalid service lines data")
        return None

    print("🔧 Creating combined service baskets...")

    # Step 1: Extract all km-based services and time-dependent
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

    # Get sorted list of km values
    sorted_km_list = sorted(km_services.keys())
    print(f"✅ Found {len(sorted_km_list)} km-based services: {sorted_km_list}")

    if time_dependent_data:
        print(f"✅ Found Time-dependent service")

    # Step 2: Create combined baskets
    combined_baskets = {}

    for target_km in sorted_km_list:
        service_number = target_km // 15000

        print(f"\n📦 Building basket for {target_km} km (Service #{service_number})...")

        # Collect all parts for this service
        all_parts = []
        included_services = []

        # Add all services that divide evenly into target_km
        for km in sorted_km_list:
            if target_km % km == 0:
                service_data = km_services[km]['data']
                parts = service_data.get('matched_parts', [])
                all_parts.extend(parts)
                included_services.append(km)
                print(f"  ✅ Including {km} km ({len(parts)} parts)")

        # Add Time-dependent if service number is even
        if service_number % 2 == 0 and time_dependent_data:
            time_parts = time_dependent_data.get('matched_parts', [])
            all_parts.extend(time_parts)
            included_services.append("time-dependent")
            print(f"  ✅ Including Time-dependent ({len(time_parts)} parts)")

        # Get model and oil_capacity from first service (15000)
        base_service = km_services[sorted_km_list[0]]['data']
        model = base_service.get('model', 'Unknown')
        oil_capacity = base_service.get('oil_capacity', None)

        # Create basket
        combined_baskets[str(target_km)] = {
            'service_number': service_number,
            'mileage_km': target_km,
            'model': model,
            'oil_capacity': oil_capacity,
            'included_services': included_services,
            'matched_parts': all_parts
        }

        print(f"  📊 Total parts in basket: {len(all_parts)}")

    print(f"\n✅ Created {len(combined_baskets)} service baskets")

    return combined_baskets


def _test():
    """Test the step with sample data"""
    import json
    from pathlib import Path

    # Load test data
    test_file = Path("Service_lines_with_part_number.json")

    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return

    print("=" * 70)
    print("Testing Step 6: Create Service Baskets")
    print("=" * 70)

    with open(test_file, 'r', encoding='utf-8') as f:
        service_lines_data = json.load(f)

    result = create_service_baskets(service_lines_data)

    if result:
        print("\n✅ Basket creation successful!")

        # Save to test output
        output_path = Path("Combined_Service_Baskets.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"\n📄 Output saved to: {output_path}")

        # Show summary
        print(f"\n📋 Service Baskets Summary:")
        print("-" * 70)
        for km, basket in result.items():
            parts_count = len(basket['matched_parts'])
            service_num = basket['service_number']
            print(f"  Service {km} km (#{service_num}): {parts_count} parts")
    else:
        print("\n❌ Basket creation failed")


if __name__ == "__main__":
    _test()
