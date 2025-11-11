import json

INPUT_FILE = "Classification Results/Panamera_S_GTS_Turbo_S_EHybrid_S_EHybrid/Panamera_S_GTS_Turbo_S_EHybrid_S_EHybrid_classified.json"   # קובץ המקור
OUTPUT_FILE = "Panamera_only_parts.json"                                  # קובץ חדש שמכיל רק PARTS

def extract_parts_only(input_path, output_path):
    # טען את הקובץ
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    services = data.get("services", {})

    parts_only_services = {}

    # עבר שירות-שירות
    for service_name, service_data in services.items():
        items = service_data.get("items", [])

        # סינון ה-ITEMS שהם PARTS בלבד
        parts_items = [item for item in items if item.get("category") == "PARTS"]

        # להוסיף רק אם יש חלקים
        if parts_items:
            parts_only_services[service_name] = {
                "items": parts_items,
            }

    # בניית מבנה JSON חדש
    output_data = {
        "services": parts_only_services
    }

    # כתיבת הקובץ החדש
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"✅ קובץ חדש נוצר: {output_path}")

# הפעלה:
extract_parts_only(INPUT_FILE, OUTPUT_FILE)
