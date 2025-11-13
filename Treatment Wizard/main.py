"""
Treatment Wizard - Main Pipeline

Input: VIN number
Output: Combined_Service_Baskets.json  (STEP 7 disabled)

Usage:
    python main.py WP0ZZZ976PL135008
    python main.py WP0ZZZ976PL135008 --force
    python main.py WP0ZZZ976PL135008 --base-path "C:\\custom"
"""

import sys
import argparse
from pathlib import Path
import json

# Add steps and foundation_codes to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / 'steps'))
sys.path.insert(0, str(SCRIPT_DIR / 'foundation_codes'))

from step1_detect_model import detect_model_from_vin
from step2_extract_pdf import extract_treatments_from_pdfs
from step3_classify import classify_treatment_lines
from step4_extract_pet import extract_pet_lines
from step5_match_parts import match_parts_to_services
from step6_create_service_baskets import create_service_baskets
# STEP 7 intentionally disabled
# from step7_translate import translate_service_baskets


class TreatmentWizard:
    """Main pipeline orchestrator"""

    def __init__(self, base_path: str = r"C:\Users\MayPery\PycharmProjects\Kits\Cars"):
        self.base_path = Path(base_path)

    def run_pipeline(self, vin: str, force: bool = False):
        """
        Run the complete pipeline for a given VIN.
        STEP 7 disabled → Pipeline ends after STEP 6.
        """

        print("="*70)
        print("🚗 Treatment Wizard - VIN Processing Pipeline")
        print("="*70)
        print(f"VIN: {vin}")
        print(f"Force mode: {'ON' if force else 'OFF'}")
        print(f"Base path: {self.base_path}")
        print("="*70)

        # ====== STEP 1: Decode VIN ======
        print("\n" + "="*70)
        print("STEP 1: VIN Decoding")
        print("-"*70)

        model_info = detect_model_from_vin(vin)
        if not model_info or model_info['confidence'] == 0:
            print(f"❌ Failed to decode VIN: {vin}")
            return None

        model_code = model_info['model_code']
        model_family = model_info['model_family']
        model_desc  = model_info['model_description']
        year        = model_info['year']

        print(f"✅ Model detected:")
        print(f"   Code: {model_code}")
        print(f"   Family: {model_family}")
        print(f"   Description: {model_desc}")
        print(f"   Year: {year}")
        print(f"   Confidence: {model_info['confidence']}%")

        model_dir = self.base_path / model_family / model_code

        if not model_dir.exists():
            print(f"❌ Model directory not found: {model_dir}")
            return None

        print(f"✅ Model directory found: {model_dir}")

        # ====== STEP 2: Extract PDFs ======
        print("\n" + "="*70)
        print("STEP 2: PDF Treatment Extraction")
        print("-"*70)

        pdf_output = model_dir / "PDF Extracted" / "Treatments_lines.json"

        if pdf_output.exists() and not force:
            print(f"✅ Output already exists: {pdf_output}")
            print("⏭️  Skipping to next step...")
            treatments_data = json.load(open(pdf_output, 'r', encoding='utf-8'))
        else:
            print("▶️  Running PDF extraction...")
            treatments_data = extract_treatments_from_pdfs(model_dir)

            if not treatments_data:
                print("❌ PDF extraction failed")
                return None

            pdf_output.parent.mkdir(parents=True, exist_ok=True)
            json.dump(treatments_data, open(pdf_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print(f"✅ Extraction completed: {pdf_output}")

        # ====== STEP 3: Classify Treatment Lines ======
        print("\n" + "="*70)
        print("STEP 3: Treatment Line Classification")
        print("-"*70)

        classified_output = model_dir / "Classified" / "Classified_Treatments_lines.json"

        if classified_output.exists() and not force:
            print(f"✅ Output already exists: {classified_output}")
            print("⏭️  Skipping...")
            classified_data = json.load(open(classified_output, 'r', encoding='utf-8'))
        else:
            print("▶️  Running classification...")
            classified_data = classify_treatment_lines(treatments_data, model_desc)

            if not classified_data:
                print("❌ Classification failed")
                return None

            classified_output.parent.mkdir(parents=True, exist_ok=True)
            json.dump(classified_data, open(classified_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print(f"✅ Classification completed: {classified_output}")

        # ====== STEP 4: Extract PET Lines ======
        print("\n" + "="*70)
        print("STEP 4: PET File Extraction")
        print("-"*70)

        pet_output = model_dir / "PET Files" / "PET_Extracted.json"

        if pet_output.exists() and not force:
            print(f"✅ Output already exists: {pet_output}")
            print("⏭️  Skipping...")
            pet_data = json.load(open(pet_output, 'r', encoding='utf-8'))
        else:
            print("▶️  Running PET extraction...")
            pet_data = extract_pet_lines(model_dir)

            if not pet_data:
                print("❌ PET extraction failed")
                return None

            pet_output.parent.mkdir(parents=True, exist_ok=True)
            json.dump(pet_data, open(pet_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print(f"✅ PET extraction completed: {pet_output}")

        # ====== STEP 5: Match Parts to Services ======
        print("\n" + "="*70)
        print("STEP 5: Parts Matching")
        print("-"*70)

        service_lines_output = model_dir / "Service_lines_with_part_number.json"

        if service_lines_output.exists() and not force:
            print(f"✅ Output exists: {service_lines_output}")
            print("⏭️  Skipping...")
            service_lines_data = json.load(open(service_lines_output, 'r', encoding='utf-8'))
        else:
            print("▶️  Running parts matching...")
            service_lines_data = match_parts_to_services(classified_data, pet_data, model_desc)

            if not service_lines_data:
                print("❌ Parts matching failed")
                return None

            json.dump(service_lines_data,
                      open(service_lines_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print(f"✅ Parts matching completed: {service_lines_output}")

        # ====== STEP 6: Create Service Baskets ======
        print("\n" + "="*70)
        print("STEP 6: Service Baskets Creation")
        print("-"*70)

        baskets_output = model_dir / "Combined_Service_Baskets.json"

        if baskets_output.exists() and not force:
            print(f"✅ Output already exists: {baskets_output}")
            print("⏭️  Skipping...")
            baskets_data = json.load(open(baskets_output, 'r', encoding='utf-8'))
        else:
            print("▶️  Creating service baskets...")
            baskets_data = create_service_baskets(service_lines_data)

            if not baskets_data:
                print("❌ Service basket creation failed")
                return None

            json.dump(baskets_data,
                      open(baskets_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)
            print(f"✅ Service baskets created: {baskets_output}")

        # ---------------------------------------------------------
        # OPTIONAL: STEP 7 - Hebrew Translation (DISABLED by default)
        # ---------------------------------------------------------
        #
        # אם תרצי להפעיל תרגום לעברית בעתיד:
        # 1. הסירי את הסימנים # מראש כל שורה בבלוק הבא
        # 2. ודאי שקובץ step7_translate.py קיים בתיקייה steps
        # 3. ודאי ש־Ollama מותקן ועובד עם המודל aya-expanse
        #
        # print("\n" + "="*70)
        # print("STEP 7: Hebrew Translation")
        # print("-"*70)
        #
        # hebrew_output = model_dir / "Combined_Service_Baskets_HEB.json"
        #
        # print("▶️  Running translation to Hebrew...")
        # translated_data = translate_service_baskets(baskets_data)
        #
        # if not translated_data:
        #     print("❌ Hebrew translation failed — returning English only")
        # else:
        #     json.dump(translated_data,
        #               open(hebrew_output, 'w', encoding='utf-8'),
        #               ensure_ascii=False, indent=2)
        #     print(f"✅ Hebrew translation saved to: {hebrew_output}")
        #
        # החזרה של קובץ עברי:
        # return hebrew_output

        # ---------------------------------------------------------
        # STEP 7 disabled → return STEP 6 output
        # ---------------------------------------------------------

        print("\n" + "=" * 70)
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY (STEP 7 disabled)")
        print("=" * 70)
        print(f"English output: {baskets_output}")
        print("=" * 70)

        return baskets_output  # THIS MAKES PIPELINE SUCCEED


def main():
    parser = argparse.ArgumentParser(
        description='Treatment Wizard - VIN Processing Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('vin', type=str)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--base-path', type=str,
                       default=r'C:\Users\MayPery\PycharmProjects\Kits\Cars')

    args = parser.parse_args()

    if len(args.vin) != 17:
        print(f"❌ VIN must be exactly 17 characters (got {len(args.vin)})")
        sys.exit(1)

    base_path = Path(args.base_path)
    if not base_path.exists():
        print(f"❌ Base path does not exist: {base_path}")
        sys.exit(1)

    wizard = TreatmentWizard(args.base_path)
    try:
        result = wizard.run_pipeline(args.vin, force=args.force)

        if result:
            print("\n🎉 Pipeline completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Pipeline failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        raise


if __name__ == "__main__":
    main()
