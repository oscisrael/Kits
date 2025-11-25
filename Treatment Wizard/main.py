"""
Treatment Wizard - Main Pipeline

Input: VIN number
Output: Combined_Service_Baskets.json  (STEP 7 disabled)

Usage:
    python main.py WP0ZZZ976PL135008
    python main.py WP0ZZZ976PL135008 --force
    python main.py WP0ZZZ976PL135008 --base-path "Cayenne:\\custom"
"""

import sys
import argparse
from pathlib import Path
import json
import string
import re

# Add steps and foundation_codes to path
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR / 'steps'))
sys.path.insert(0, str(SCRIPT_DIR / 'foundation_codes'))

from steps.step1_detect_model import detect_model_from_vin
from steps.step2_extract_pdf import extract_treatments_from_pdfs
from steps.step3_classify import classify_treatment_lines
from steps.step4_extract_pet import extract_pet_lines
from steps.step5_match_parts import match_parts_to_services
from steps.step6_create_service_baskets import create_service_baskets
from steps.step7_translate import translate_service_data
from steps.step8_export_excel import export_service_baskets_to_excel

def normalize_model_name(name: str) -> str:
    # מחליפה רצף של '/' עם רווחים סביבם ל'/'
    name = re.sub(r'\s*/\s*', '/', name)
    # מחליפה כמה '/' רצופים ל '/'
    name = re.sub(r'/+', '/', name)
    # מסירה רווחים בתחילת וסוף המחרוזת
    name = name.strip()
    return name

def find_model_desc(data):
    if isinstance(data, dict):
        if "model" in data:
            return data["model"]
        for v in data.values():
            found = find_model_desc(v)
            if found:
                return found
    elif isinstance(data, list):
        for item in data:
            found = find_model_desc(item)
            if found:
                return found
    return None

class TreatmentWizard:
    """Main pipeline orchestrator"""

    def __init__(self, base_path: str = r"Cayenne:\Users\MayPery\PycharmProjects\Kits\Cars"):
        self.base_path = Path(base_path)

    def run_pipeline(self, vin: str, force: bool = False):
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
            with open(pdf_output, 'w', encoding='utf-8') as f:
                json.dump(treatments_data, f, ensure_ascii=False, indent=2)
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
            with open(classified_output, 'w', encoding='utf-8') as f:
                json.dump(classified_data, f, ensure_ascii=False, indent=2)
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
            with open(pet_output, 'w', encoding='utf-8') as f:
                json.dump(pet_data, f, ensure_ascii=False, indent=2)
            print(f"✅ PET extraction completed: {pet_output}")

        # ====== STEP 5: Match Parts to Services with proper model_name normalization and filtering ======
        print("\n" + "=" * 70)
        print("STEP 5: Parts Matching")
        print("-" * 70)

        def map_model_names_to_ids(model_names):
            letters = string.ascii_uppercase
            return {model: letters[i] for i, model in enumerate(sorted(model_names))}

        # Extract all normalized model_names found in items list
        model_names = set()
        for service_key, service_data in classified_data.get("services", {}).items():
            items = service_data.get("items", [])
            if isinstance(items, list):
                for item in items:
                    mn = item.get("model_name")
                    if mn:
                        model_names.add(normalize_model_name(mn))

        service_lines_data = {}
        model_id_map = {}

        if len(model_names) < 2:
            # Only one model_name - process as usual
            service_lines_output = model_dir / "Service_lines_with_part_number.json"

            if service_lines_output.exists() and not force:
                print(f"✅ Output exists: {service_lines_output}")
                print("⏭️  Skipping...")
                service_lines_data = json.load(open(service_lines_output, 'r', encoding='utf-8'))
            else:
                print("▶️  Running parts matching on single model...")

                result = match_parts_to_services(
                    classified_data,
                    pet_data,
                    model_desc
                )

                if not result:
                    print("❌ Parts matching failed")
                    return None

                with open(service_lines_output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                service_lines_data['A'] = result
                model_id_map[model_desc] = 'A'

            print(f"✅ Parts matching completed for single model.")
        else:
            print(f"▶️ Multiple model_names detected: {model_names}")
            model_id_map = map_model_names_to_ids(model_names)

            for model_name, model_id in model_id_map.items():
                print(f"▶️ Running parts matching for model '{model_name}' (ID {model_id})...")

                split_classified_data = {"services": {}}

                for service_key, service_data in classified_data.get("services", {}).items():
                    items = service_data.get("items", [])
                    if isinstance(items, list):
                        filtered_items = [
                            item for item in items if normalize_model_name(item.get("model_name", "")) == model_name
                        ]
                        if filtered_items:
                            split_classified_data["services"][service_key] = {
                                "original_header": service_data.get("original_header", ""),
                                "items": filtered_items
                            }

                result = match_parts_to_services(split_classified_data, pet_data, model_name)

                if not result:
                    print(f"❌ Parts matching failed for model {model_name}")
                    continue

                output_file = model_dir / "Outputs" / "Service Lines" / f"Service_lines_with_part_number_{model_id}.json"
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)

                service_lines_data[model_id] = result
                print(f"✅ Parts matching completed for {model_name} saved to {output_file}")

        # ====== STEP 6: Create Service Baskets for each model_id ======
        print("\n" + "="*70)
        print("STEP 6: Service Baskets Creation")
        print("-"*70)

        baskets_data_map = {}
        for model_id, data in service_lines_data.items():
            baskets_output = model_dir / "Outputs" / "Service Baskets" / f"Combined_Service_Baskets_{model_id}.json"
            baskets_output.parent.mkdir(parents=True, exist_ok=True)

            if baskets_output.exists() and not force:
                print(f"✅ Output already exists: {baskets_output}")
                print("⏭️  Skipping...")
                baskets_data = json.load(open(baskets_output, 'r', encoding='utf-8'))
            else:
                print(f"▶️  Creating service baskets for model ID {model_id} ...")
                baskets_data = create_service_baskets(data)

                if not baskets_data:
                    print("❌ Service basket creation failed")
                    return None

                with open(baskets_output, 'w', encoding='utf-8') as f:
                    json.dump(baskets_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Service baskets created: {baskets_output}")

            baskets_data_map[model_id] = baskets_data

        # ====== STEP 7: Hebrew Translation for each model_id ======
        print("\n" + "="*70)
        print("STEP 7: Hebrew Translation")
        print("-"*70)

        hebrew_outputs = {}
        for model_id, baskets_data in baskets_data_map.items():
            hebrew_output = model_dir / "Outputs" / "Hebrew" / f"Combined_Service_Baskets_HEB_{model_id}.json"
            hebrew_output.parent.mkdir(parents=True, exist_ok=True)

            if hebrew_output.exists() and not force:
                print(f"✅ Output already exists: {hebrew_output}")
                print("⏭️ Skipping Step 7...")
            else:
                print(f"▶️ Running translation to Hebrew for model ID {model_id} ...")
                translated_data = translate_service_data(baskets_data)

                if not translated_data:
                    print("❌ Hebrew translation failed — returning English only")
                    translated_data = baskets_data

                with open(hebrew_output, "w", encoding="utf-8") as f:
                    json.dump(translated_data, f, ensure_ascii=False, indent=2)
                print(f"✅ Hebrew translation saved to: {hebrew_output}")

            hebrew_outputs[model_id] = hebrew_output

        # ====== STEP 8: Export Excel for each model_id ======
        print("\n" + "=" * 70)
        print("STEP 8: Export Excel")
        print("-" * 70)

        excel_paths = {}
        for model_id, hebrew_output in hebrew_outputs.items():
            try:
                baskets_data = baskets_data_map.get(model_id, {})
                extracted_model_desc = find_model_desc(baskets_data)

                print(f"  Model ID {model_id}: extracted_model_desc = {extracted_model_desc}")
                print(f"  Multiple models? len(model_names) = {len(model_names)}")

                model_desc_param = extracted_model_desc if len(model_names) > 1 else None

                if len(model_names) > 1:
                    model_code_param = f"{model_code}_{model_id}"
                else:
                    model_code_param = model_code

                excel_path = export_service_baskets_to_excel(
                    json_path=str(hebrew_output),
                    output_dir=str(model_dir),
                    model_vin= vin,
                    model_code=model_code_param,  # <--- שונה
                    model_desc=model_desc_param
                )
                excel_paths[model_id] = excel_path
                print(f"📊 Excel exported for model ID {model_id}: {excel_path}")

            except Exception as e:
                print(f"⚠️ Excel export failed for model ID {model_id}: {e}")
                import traceback
                traceback.print_exc()
                excel_paths[model_id] = None

        print("\n" + "="*70)
        print("🎉 PIPELINE COMPLETED SUCCESSFULLY")
        print("="*70)
        print("JSON Hebrew outputs:")
        for k, v in hebrew_outputs.items():
            print(f"  [{k}] {v}")
        print("Excel outputs:")
        for k, v in excel_paths.items():
            print(f"  [{k}] {v if v else 'FAILED'}")
        print("="*70)

        return {
            "json": hebrew_outputs,
            "excel": excel_paths
        }


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
