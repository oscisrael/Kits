"""
step4_extract_pet.py
Step 4: Extract part numbers and details from PET file

INPUT: model_dir (Path to model directory)
OUTPUT: List of dicts with Part Number, Description, Remark, Qty, Model

Uses extract_with_accurate_columns from PetTextExtractor.py
"""

import sys
from pathlib import Path
from typing import List, Dict, Optional
import json

# Add foundation_codes to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))

from PetTextExtractor import extract_with_accurate_columns


def find_pet_file(pet_dir: Path) -> Optional[Path]:
    """
    Find PET file in directory (contains "PET FILE" in name, case-insensitive)

    Args:
        pet_dir: PET Files directory

    Returns:
        Path to PET file or None
    """
    if not pet_dir.exists():
        return None

    # Search for PDF containing "PET FILE" (case-insensitive)
    for pdf_file in pet_dir.glob("*.pdf"):
        if "pet file" in pdf_file.name.lower():
            return pdf_file

    # If not found, try without space
    for pdf_file in pet_dir.glob("*.pdf"):
        if "petfile" in pdf_file.name.lower():
            return pdf_file

    return None


def extract_pet_lines(model_dir: Path) -> Optional[List[Dict]]:
    """
    Extract part numbers and details from PET file

    Args:
        model_dir: Path to model directory (e.g., Cars/Panamera/97AAA1/)

    Returns:
        List of part data dicts:
        [
            {
                "Part Number": "000-043-206-71",
                "Description": "Oil filter",
                "Remark": "Standard",
                "Qty": "1",
                "Model": "Panamera"
            },
            ...
        ]

        Returns None if extraction fails

    Example output:
        [
            {
                "Part Number": "000-043-206-71",
                "Description": "Engine oil 0W-30",
                "Remark": "Porsche Classic Motoroil SAE 20W-50",
                "Qty": "8.5",
                "Model": "Panamera GTS"
            }
        ]
    """
    pet_dir = model_dir / "PET Files"

    if not pet_dir.exists():
        print(f"❌ PET Files directory not found: {pet_dir}")
        return None

    print(f"Searching for PET file in: {pet_dir}")

    # Find PET file
    pet_file = find_pet_file(pet_dir)

    if not pet_file:
        print(f"❌ PET file not found in {pet_dir}")
        print("   (Expected filename to contain 'PET FILE')")

        # List available files for debugging
        pdf_files = list(pet_dir.glob("*.pdf"))
        if pdf_files:
            print(f"   Available PDF files:")
            for f in pdf_files:
                print(f"     - {f.name}")

        return None

    print(f"✅ Found PET file: {pet_file.name}")
    print("   Extracting part numbers...")

    try:
        # Extract data using PetTextExtractor
        pet_data = extract_with_accurate_columns(str(pet_file))

        if not pet_data or not isinstance(pet_data, list):
            print("❌ PET extraction returned invalid data")
            return None

        # Validate data structure
        if pet_data and not isinstance(pet_data[0], dict):
            print("❌ PET extraction returned invalid format (expected list of dicts)")
            return None

        print(f"✅ Extracted {len(pet_data)} part entries")

        # Print sample for verification
        if pet_data:
            print("\n📋 Sample entries:")
            for i, entry in enumerate(pet_data[:3], 1):
                part_num = entry.get('Part Number', 'N/A')
                desc = entry.get('Description', 'N/A')
                print(f"   {i}. {part_num} - {desc[:50]}...")

        return pet_data

    except Exception as e:
        print(f"❌ PET extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# Test function (for standalone testing)
def _test():
    """Test the step with a sample model directory"""
    from pathlib import Path

    # Use same path format as step 2
    test_dir = Path(r"C:\Users\MayPery\PycharmProjects\Kits\Cars\Panamera\97ADS1")

    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        print("   Please update the path in _test() function")
        return

    print("=" * 70)
    print("Testing Step 4: PET Extraction")
    print("=" * 70)
    print(f"Model directory: {test_dir}\n")

    result = extract_pet_lines(test_dir)

    if result:
        print("\n✅ Extraction successful!")
        print(f"\nTotal parts extracted: {len(result)}")

        # Show breakdown by category if available
        if result:
            # Count unique part numbers
            unique_parts = set(entry.get('Part Number', '') for entry in result)
            print(f"Unique part numbers: {len(unique_parts)}")

        # Save to test output
        output_path = Path("test_step4_output.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Test output saved to: {output_path}")

        # Show detailed sample
        if len(result) > 0:
            print(f"\n📋 First entry (full details):")
            print(json.dumps(result[0], ensure_ascii=False, indent=2))
    else:
        print("\n❌ Extraction failed")


if __name__ == "__main__":
    _test()
