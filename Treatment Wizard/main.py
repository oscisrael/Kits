"""
main.py
Treatment Wizard - Main Pipeline

Input: VIN number
Output: Service_lines_with_part_number.json

Usage:
    python main.py <VIN>                    # Skip existing files
    python main.py <VIN> --force            # Regenerate all files
    python main.py WP0ZZZ976PL135008
"""

import sys
import argparse
from pathlib import Path
import json

# Add codes directory to path
sys.path.insert(0, str(Path(__file__).parent / 'codes'))

from SmartVinDecoder import SmartVinDecoder
from step2_extract_pdf import extract_treatments_from_pdfs
from step3_classify import classify_treatment_lines
from step4_extract_pet import extract_pet_lines
from step5_match_parts import match_parts_to_services


class TreatmentWizard:
    """Main pipeline orchestrator"""

    def __init__(self, base_path: str = "Kits - PDF DB"):
        self.base_path = Path(base_path)
        self.decoder = None

    def initialize(self):
        """Initialize the VIN decoder"""
        print("Initializing VIN Decoder...")
        self.decoder = SmartVinDecoder()
        self.decoder.load_model("smart_vin_decoder.pkl")
        print("✅ VIN Decoder ready\n")

    def run_pipeline(self, vin: str, force: bool = False):
        """
        Run the complete pipeline for a given VIN

        Args:
            vin: Vehicle VIN number
            force: If True, regenerate all files even if they exist
        """
        print("=" * 70)
        print("🚗 Treatment Wizard - VIN Processing Pipeline")
        print("=" * 70)
        print(f"VIN: {vin}")
        print(f"Force mode: {'ON' if force else 'OFF'}")
        print("=" * 70)

        # ====== STEP 1: Decode VIN ======
        print("\n" + "=" * 70)
        print("STEP 1: VIN Decoding")
        print("-" * 70)

        result = self.decoder.decode_vin(vin)

        if result['confidence'] == 0:
            print(f"❌ Failed to decode VIN: {vin}")
            return None

        model_code = result['model_code']
        model_family = result['model_family']
        model_desc = result['model_description']
        year = result['year']

        print(f"✅ Model detected:")
        print(f"   Code: {model_code}")
        print(f"   Family: {model_family}")
        print(f"   Description: {model_desc}")
        print(f"   Year: {year}")
        print(f"   Confidence: {result['confidence']}%")

        # Build directory path
        model_dir = self.base_path / model_family / model_code

        if not model_dir.exists():
            print(f"❌ Model directory not found: {model_dir}")
            return None

        print(f"✅ Model directory found: {model_dir}")

        # ====== STEP 2: Extract PDFs ======
        print("\n" + "=" * 70)
        print("STEP 2: PDF Treatment Extraction")
        print("-" * 70)

        pdf_output = model_dir / "PDF Extracted" / "Treatments_lines.json"

        if pdf_output.exists() and not force:
            print(f"✅ Output already exists: {pdf_output}")
            print("⏭️  Skipping to next step...")
            with open(pdf_output, 'r', encoding='utf-8') as f:
                treatments_data = json.load(f)
        else:
            if force and pdf_output.exists():
                print(f"⚠️  Force mode: Regenerating {pdf_output}")

            print("▶️  Running PDF extraction...")
            treatments_data = extract_treatments_from_pdfs(model_dir)

            if treatments_data:
                pdf_output.parent.mkdir(parents=True, exist_ok=True)
                with open(pdf_output, 'w', encoding='utf-8') as f:
                    json.dump(treatments_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Extraction completed: {pdf_output}")
            else:
                print("❌ PDF extraction failed")
                return None

        # ====== STEP 3: Classify Treatment Lines ======
        print("\n" + "=" * 70)
        print("STEP 3: Treatment Line Classification")
        print("-" * 70)

        classified_output = model_dir / "Classified" / "Classified_Treatments_lines.json"

        if classified_output.exists() and not force:
            print(f"✅ Output already exists: {classified_output}")
            print("⏭️  Skipping to next step...")
            with open(classified_output, 'r', encoding='utf-8') as f:
                classified_data = json.load(f)
        else:
            if force and classified_output.exists():
                print(f"⚠️  Force mode: Regenerating {classified_output}")

            print("▶️  Running classification...")
            classified_data = classify_treatment_lines(treatments_data, model_desc)

            if classified_data:
                classified_output.parent.mkdir(parents=True, exist_ok=True)
                with open(classified_output, 'w', encoding='utf-8') as f:
                    json.dump(classified_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Classification completed: {classified_output}")
            else:
                print("❌ Classification failed")
                return None

        # ====== STEP 4: Extract PET Lines ======
        print("\n" + "=" * 70)
        print("STEP 4: PET File Extraction")
        print("-" * 70)

        pet_output = model_dir / "PET Files" / "PET_Extracted.json"

        if pet_output.exists() and not force:
            print(f"✅ Output already exists: {pet_output}")
            print("⏭️  Skipping to next step...")
            with open(pet_output, 'r', encoding='utf-8') as f:
                pet_data = json.load(f)
        else:
            if force and pet_output.exists():
                print(f"⚠️  Force mode: Regenerating {pet_output}")

            print("▶️  Running PET extraction...")
            pet_data = extract_pet_lines(model_dir)

            if pet_data:
                with open(pet_output, 'w', encoding='utf-8') as f:
                    json.dump(pet_data, f, ensure_ascii=False, indent=2)
                print(f"✅ PET extraction completed: {pet_output}")
            else:
                print("❌ PET extraction failed")
                return None

        # ====== STEP 5: Match Parts to Services ======
        print("\n" + "=" * 70)
        print("STEP 5: Parts Matching")
        print("-" * 70)

        final_output = model_dir / "Service_lines_with_part_number.json"

        if final_output.exists() and not force:
            print(f"✅ Output already exists: {final_output}")
            print("⏭️  Final output ready!")
            with open(final_output, 'r', encoding='utf-8') as f:
                final_data = json.load(f)
        else:
            if force and final_output.exists():
                print(f"⚠️  Force mode: Regenerating {final_output}")

            print("▶️  Running parts matching...")
            final_data = match_parts_to_services(classified_data, pet_data, model_desc)

            if final_data:
                with open(final_output, 'w', encoding='utf-8') as f:
                    json.dump(final_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Parts matching completed: {final_output}")
            else:
                print("❌ Parts matching failed")
                return None

        # ====== SUMMARY ======
        print("\n" + "=" * 70)
        print("✅ PIPELINE COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print(f"Final output: {final_output}")
        print(f"Model: {model_desc} ({model_code})")
        print(f"Year: {year}")

        return final_output


def main():
    parser = argparse.ArgumentParser(
        description='Treatment Wizard - VIN Processing Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py WP0ZZZ976PL135008              # Normal mode (skip existing)
  python main.py WP0ZZZ976PL135008 --force      # Force mode (regenerate all)
        """
    )
    parser.add_argument('vin', type=str, help='Vehicle VIN number (17 characters)')
    parser.add_argument('--force', action='store_true', help='Force regeneration of all files')
    parser.add_argument('--base-path', type=str, default='Kits - PDF DB',
                        help='Base path to PDF database (default: "Kits - PDF DB")')

    args = parser.parse_args()

    # Validate VIN
    if len(args.vin) != 17:
        print(f"❌ Error: VIN must be exactly 17 characters (got {len(args.vin)})")
        sys.exit(1)

    # Run pipeline
    wizard = TreatmentWizard(args.base_path)
    wizard.initialize()

    try:
        result = wizard.run_pipeline(args.vin, force=args.force)
        if result:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Pipeline failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
