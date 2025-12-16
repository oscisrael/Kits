"""
engine_oil_part_number_config.py
Maps model codes to engine oil part numbers

This configuration replaces PET-based matching for engine oil.
The part number (T.108, T.107, T.133) determines which oil to use.
Oil quantity is still calculated separately using oil_capacity_config.py

Usage:
    from engine_oil_part_number_config import get_oil_part_number

    oil_part = get_oil_part_number("97ABE1")  # Returns "T.108"
"""

from typing import Optional

# Model Code -> Oil Part Number mapping
# Source: Official maintenance documentation
ENGINE_OIL_PART_NUMBER_TABLE = {
    "97ABE1": "T.108",
    "97ANX1": "T.108",
    "YAABE1": "T.108",
    "97AHE1": "T.108",
    "97ADB1": "T.108",
    "97ABX1": "T.108",
    "9YAAE1": "T.107",
    "9YBAI1": "T.107",
    "9YBAA1": "T.107",
    "9YAAA1": "T.107",
    "9YBDA1": "T.107",
    "9YBAE1": "T.107",
    "9YBBG1": "T.133",
    "9YBAV1": "T.107",
    "9YADA1": "T.107",
    "9YBBJ1": "T.133",
    "95BBV1": "T.108",
    "95BAM1": "T.108",
    "95BAU1": "T.107",
    "95BBH1": "T.107",
    "95BBW1": "T.108",
    "95BAS1": "T.108",
}


def get_oil_part_number(model_code: str) -> Optional[str]:
    """
    Get the correct engine oil part number for a given model code.

    Args:
        model_code: Model code from VIN decoding (e.g., "97ABE1", "9YBBG1")

    Returns:
        Oil part number (e.g., "T.108", "T.107", "T.133") or None if not found

    Examples:
        >>> get_oil_part_number("97ABE1")
        "T.108"
        >>> get_oil_part_number("9YBBG1")
        "T.133"
        >>> get_oil_part_number("UNKNOWN")
        None
    """
    if not model_code:
        return None

    # Direct lookup - exact match required
    part_number = ENGINE_OIL_PART_NUMBER_TABLE.get(model_code.upper())

    if part_number:
        print(f"✓ Oil part number for {model_code}: {part_number}")
    else:
        print(f"✗ No oil part number mapping found for model code: {model_code}")

    return part_number


def add_oil_mapping(model_code: str, part_number: str) -> None:
    """
    Add a new model code -> oil part number mapping.

    This is a runtime addition - to make it permanent, update ENGINE_OIL_PART_NUMBER_TABLE.

    Args:
        model_code: Model code (e.g., "97XXX1")
        part_number: Oil part number (e.g., "T.108")
    """
    ENGINE_OIL_PART_NUMBER_TABLE[model_code.upper()] = part_number
    print(f"➕ Added mapping: {model_code} -> {part_number}")


def test():
    """Test the oil part number mapping"""
    print("=" * 70)
    print("Testing Engine Oil Part Number Mapping")
    print("=" * 70)

    test_cases = [
        ("97ABE1", "T.108"),
        ("9YBBG1", "T.133"),
        ("9YAAE1", "T.107"),
        ("UNKNOWN", None),
    ]

    passed = 0
    failed = 0

    for model_code, expected_part in test_cases:
        result = get_oil_part_number(model_code)
        if result == expected_part:
            print(f"✓ PASS: {model_code} -> {result}")
            passed += 1
        else:
            print(f"✗ FAIL: {model_code} -> Expected: {expected_part}, Got: {result}")
            failed += 1

    print("=" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)


if __name__ == "__main__":
    test()
