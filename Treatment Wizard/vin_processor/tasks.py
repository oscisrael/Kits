from celery import shared_task
from .models import VINProcessing
import sys
from pathlib import Path
import json

# Import the existing pipeline
SCRIPT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPT_DIR / 'steps'))
sys.path.insert(0, str(SCRIPT_DIR / 'foundation_codes'))

from step1_detect_model import detect_model_from_vin
from step2_extract_pdf import extract_treatments_from_pdfs
from step3_classify import classify_treatment_lines
from step4_extract_pet import extract_pet_lines
from step5_match_parts import match_parts_to_services
from step6_create_service_baskets import create_service_baskets


@shared_task(bind=True)
def process_vin_task(self, vin_id):
    """
    עיבוד VIN ברקע עם עדכון progress
    """
    try:
        vin_obj = VINProcessing.objects.get(id=vin_id)
        vin = vin_obj.vin
        base_path = Path(r"C:\Users\MayPery\PycharmProjects\Kits\Cars")

        # Step 1: VIN Decoding (0-16%)
        vin_obj.status = 'PROCESSING'
        vin_obj.current_step = 'זיהוי דגם מ-VIN'
        vin_obj.progress = 0
        vin_obj.save()

        model_info = detect_model_from_vin(vin)
        if not model_info or model_info['confidence'] == 0:
            raise Exception(f"Failed to decode VIN: {vin}")

        model_code = model_info['model_code']
        model_family = model_info['model_family']
        model_desc = model_info['model_description']

        model_dir = base_path / model_family / model_code
        if not model_dir.exists():
            raise Exception(f"Model directory not found: {model_dir}")

        vin_obj.progress = 16
        vin_obj.save()

        # Step 2: PDF Extraction (16-33%)
        vin_obj.current_step = 'חילוץ טיפולים מ-PDF'
        vin_obj.save()

        pdf_output = model_dir / "PDF Extracted" / "Treatments_lines.json"
        if pdf_output.exists():
            treatments_data = json.load(open(pdf_output, 'r', encoding='utf-8'))
        else:
            treatments_data = extract_treatments_from_pdfs(model_dir)
            pdf_output.parent.mkdir(parents=True, exist_ok=True)
            json.dump(treatments_data, open(pdf_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)

        vin_obj.progress = 33
        vin_obj.save()

        # Step 3: Classification (33-50%)
        vin_obj.current_step = 'סיווג שורות טיפול'
        vin_obj.save()

        classified_output = model_dir / "Classified" / "Classified_Treatments_lines.json"
        if classified_output.exists():
            classified_data = json.load(open(classified_output, 'r', encoding='utf-8'))
        else:
            classified_data = classify_treatment_lines(treatments_data, model_desc)
            classified_output.parent.mkdir(parents=True, exist_ok=True)
            json.dump(classified_data, open(classified_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)

        vin_obj.progress = 50
        vin_obj.save()

        # Step 4: PET Extraction (50-66%)
        vin_obj.current_step = 'חילוץ חלקים מ-PET'
        vin_obj.save()

        pet_output = model_dir / "PET Files" / "PET_Extracted.json"
        if pet_output.exists():
            pet_data = json.load(open(pet_output, 'r', encoding='utf-8'))
        else:
            pet_data = extract_pet_lines(model_dir)
            pet_output.parent.mkdir(parents=True, exist_ok=True)
            json.dump(pet_data, open(pet_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)

        vin_obj.progress = 66
        vin_obj.save()

        # Step 5: Parts Matching (66-83%)
        vin_obj.current_step = 'התאמת חלקים לשירותים'
        vin_obj.save()

        service_lines_output = model_dir / "Service_lines_with_part_number.json"
        if service_lines_output.exists():
            service_lines_data = json.load(open(service_lines_output, 'r', encoding='utf-8'))
        else:
            service_lines_data = match_parts_to_services(classified_data, pet_data, model_desc)
            json.dump(service_lines_data, open(service_lines_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)

        vin_obj.progress = 83
        vin_obj.save()

        # Step 6: Service Baskets (83-100%)
        vin_obj.current_step = 'יצירת סלי שירות'
        vin_obj.save()

        baskets_output = model_dir / "Combined_Service_Baskets.json"
        if baskets_output.exists():
            baskets_data = json.load(open(baskets_output, 'r', encoding='utf-8'))
        else:
            baskets_data = create_service_baskets(service_lines_data)
            json.dump(baskets_data, open(baskets_output, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=2)

        # Save result
        vin_obj.result_json = json.dumps(baskets_data, ensure_ascii=False)
        vin_obj.status = 'COMPLETED'
        vin_obj.progress = 100
        vin_obj.current_step = 'הושלם'
        vin_obj.save()

        return baskets_data

    except Exception as e:
        vin_obj.status = 'FAILED'
        vin_obj.error_message = str(e)
        vin_obj.save()
        raise
