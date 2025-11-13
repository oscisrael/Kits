"""
step2_extract_pdf.py
Step 2: Extract treatment lines from Oil Maintenance and Inspection PDFs

INPUT: model_dir (Path to model directory)
OUTPUT: Dict with treatments grouped by service intervals

Uses functions from TreatmentExtractorFromPDF.py
"""

import sys
from pathlib import Path
from typing import Dict, Optional
import json

# Add foundation_codes to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))

from TreatmentExtractorFromPDF import (
    extract_checkboxes_with_y_ranges,
    map_services_intersection_based,
    SERVICE_ORDER
)


def find_pdf_by_keyword(directory: Path, keyword: str) -> Optional[Path]:
    """
    Find a PDF file in directory that contains the keyword (case-insensitive)

    Args:
        directory: Directory to search in
        keyword: Keyword to search for in filename

    Returns:
        Path to PDF file or None if not found
    """
    if not directory.exists():
        return None

    # Search for PDF files containing the keyword (case-insensitive)
    for pdf_file in directory.glob("*.pdf"):
        if keyword.lower() in pdf_file.name.lower():
            return pdf_file

    return None


def extract_from_single_pdf(pdf_path: Path, service_type: str) -> Optional[Dict]:
    """
    Extract treatments from a single PDF file

    Args:
        pdf_path: Path to PDF file
        service_type: Type of service ('oil_maintenance' or 'inspection')

    Returns:
        Dict with services or None if extraction fails
    """
    try:
        print(f"   Extracting from: {pdf_path.name}")

        # Step 1: Extract checkboxes with Y ranges
        text_data = extract_checkboxes_with_y_ranges(str(pdf_path))

        if not text_data:
            print(f"   ⚠️  No data extracted from {pdf_path.name}")
            return None

        # Step 2: Map to services
        services = map_services_intersection_based(str(pdf_path), text_data, service_type)

        if not services:
            print(f"   ⚠️  No services mapped from {pdf_path.name}")
            return None

        # Count items
        total_items = sum(len(items) for items in services.values())
        print(f"   ✅ Extracted {total_items} items from {len(services)} services")

        return services

    except Exception as e:
        print(f"   ❌ Error extracting from {pdf_path.name}: {e}")
        import traceback
        traceback.print_exc()
        return None


def merge_services(inspection_data: Dict, maintenance_data: Dict) -> Dict:
    """
    Merge inspection and maintenance services data
    Handles both old format (dict of lists) and new format (dict with original_header and items)

    Args:
        inspection_data: Services from inspection PDF
        maintenance_data: Services from maintenance PDF

    Returns:
        Merged services data with combined items
    """
    merged = {}

    all_service_keys = set(inspection_data.keys()) | set(maintenance_data.keys())

    for service_key in all_service_keys:
        insp_service = inspection_data.get(service_key, {})
        maint_service = maintenance_data.get(service_key, {})

        # Determine if new format (with original_header) or old format
        insp_is_new_format = isinstance(insp_service, dict) and "items" in insp_service
        maint_is_new_format = isinstance(maint_service, dict) and "items" in maint_service

        # Extract original_header (prefer inspection, fallback to maintenance, fallback to service_key)
        original_header = service_key
        if insp_is_new_format:
            original_header = insp_service.get("original_header", service_key)
        elif maint_is_new_format:
            original_header = maint_service.get("original_header", service_key)

        # Extract items dict from both formats
        if insp_is_new_format:
            insp_items = insp_service.get("items", {})
        else:
            insp_items = insp_service if isinstance(insp_service, dict) else {}

        if maint_is_new_format:
            maint_items = maint_service.get("items", {})
        else:
            maint_items = maint_service if isinstance(maint_service, dict) else {}

        # Merge items by model
        merged_items = {}
        all_models = set(insp_items.keys()) | set(maint_items.keys())

        for model in all_models:
            list1 = insp_items.get(model, [])
            list2 = maint_items.get(model, [])

            # Ensure both are lists
            if not isinstance(list1, list):
                list1 = []
            if not isinstance(list2, list):
                list2 = []

            # Merge and deduplicate
            merged_items[model] = list(set(list1 + list2))

        # Store in new format with original_header
        merged[service_key] = {
            "original_header": original_header,
            "items": merged_items
        }

    return merged


def extract_treatments_from_pdfs(model_dir: Path) -> Optional[Dict]:
    """
    Extract treatment lines from Oil Maintenance and Inspection PDFs

    Args:
        model_dir: Path to model directory (e.g., Cars/Panamera/97ADS1/)

    Returns:
        Combined treatment data from both PDFs:
        {
            "metadata": {
                "model_dir": str,
                "oil_maintenance_pdf": str or None,
                "inspection_pdf": str or None
            },
            "services": {
                "service_15000": {
                    "model_name": ["item1", "item2", ...]
                },
                ...
            }
        }

        Returns None if extraction fails

    Example output structure:
        {
            "metadata": {
                "model_dir": "Cars/Panamera/97ADS1",
                "oil_maintenance_pdf": "Oil maintenance.pdf",
                "inspection_pdf": "Inspection.pdf"
            },
            "services": {
                "service_15000": {
                    "Panamera GTS": [
                        "Fill in engine oil",
                        "Change oil filter",
                        ...
                    ]
                },
                "service_30000": {...}
            }
        }
    """
    pdfs_dir = model_dir / "PDFs"

    if not pdfs_dir.exists():
        print(f"❌ PDFs directory not found: {pdfs_dir}")
        return None

    print(f"Searching for PDFs in: {pdfs_dir}")

    # Find Oil Maintenance PDF
    oil_pdf = find_pdf_by_keyword(pdfs_dir, "oil maintenance")
    oil_services = None

    if not oil_pdf:
        print(f"⚠️  Oil maintenance PDF not found in {pdfs_dir}")
    else:
        print(f"✅ Found: {oil_pdf.name}")
        oil_services = extract_from_single_pdf(oil_pdf, "oil_maintenance")

    # Find Inspection PDF
    inspection_pdf = find_pdf_by_keyword(pdfs_dir, "inspection")
    inspection_services = None

    if not inspection_pdf:
        print(f"⚠️  Inspection PDF not found in {pdfs_dir}")
    else:
        print(f"✅ Found: {inspection_pdf.name}")
        inspection_services = extract_from_single_pdf(inspection_pdf, "inspection")

    # Check if at least one PDF was extracted
    if not oil_services and not inspection_services:
        print("❌ No PDFs were successfully extracted")
        return None

    # Merge services
    merged_services = {}

    if oil_services:
        merged_services = oil_services

    if inspection_services:
        if merged_services:
            merged_services = merge_services(merged_services, inspection_services)
        else:
            merged_services = inspection_services

    # Build output
    output_data = {
        "metadata": {
            "model_dir": str(model_dir),
            "oil_maintenance_pdf": oil_pdf.name if oil_pdf else None,
            "inspection_pdf": inspection_pdf.name if inspection_pdf else None,
        },
        "services": merged_services
    }

    # Count totals
    total_services = len(merged_services)
    total_items = sum(
        len(items)
        for service_data in merged_services.values()
        for items in service_data.values()
    )

    print(f"✅ Extraction complete:")
    print(f"   Services: {total_services}")
    print(f"   Total items: {total_items}")

    return output_data


# Test function (for standalone testing)
def _test():
    """Test the step with a sample model directory"""
    from pathlib import Path

    # Example: test with Panamera GTS
    test_dir = Path(r"C:\Users\MayPery\PycharmProjects\Kits\Cars\Panamera\97AAA1")

    if not test_dir.exists():
        print(f"❌ Test directory not found: {test_dir}")
        print("   Please update the path in _test() function")
        return

    print("=" * 70)
    print("Testing Step 2: PDF Extraction")
    print("=" * 70)
    print(f"Model directory: {test_dir}\n")

    result = extract_treatments_from_pdfs(test_dir)

    if result:
        print("\n✅ Extraction successful!")
        print(f"\nServices found: {list(result['services'].keys())}")

        # Save to test output
        output_path = Path("test_step2_output.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Test output saved to: {output_path}")
    else:
        print("\n❌ Extraction failed")


if __name__ == "__main__":
    _test()
