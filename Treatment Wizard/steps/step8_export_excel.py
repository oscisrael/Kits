import json
import os
import pandas as pd
from pathlib import Path


# ==========================
# Helper: Format KM with comma
# ==========================
def format_km(num: int) -> str:
    return f"{num:,}".replace(",", ",")


# ==========================
# Constant parts to add to every service
# ==========================
EXTRA_PARTS = [
    {"חלקים": "תוסף דלק פורשה", "מק\"ט": "00004320902", "כמות": "1"},
    {"חלקים": "נוזל שמשות", "מק\"ט": "T.110", "כמות": "1"},
    {"חלקים": "חומרי עזר", "מק\"ט": "1111", "כמות": "1"},
    {"חלקים": "עבודה", "מק\"ט": "", "כמות": ""},
]


# ==========================
# Load SAP Parts Database
# ==========================
def load_sap_parts_database(sap_file_path: str) -> dict:
    """
    טוען את קובץ SAP ומחזיר מילון: מק"ט (ללא רווחים) -> שם חלק
    """
    sap_path = Path(sap_file_path)
    if not sap_path.exists():
        print(f"⚠️ קובץ SAP לא נמצא: {sap_file_path}")
        return {}

    try:
        # קריאת קובץ SAP
        df_sap = pd.read_excel(sap_path, header=0)

        # בדיקה שהעמודות הנדרשות קיימות
        if df_sap.shape[1] < 2:
            print(f"⚠️ קובץ SAP לא מכיל מספיק עמודות")
            return {}

        # עמודה A (אינדקס 0) = קוד פריט, עמודה B (אינדקס 1) = שם חלק
        # מתחילים מהשורה השנייה (אינדקס 1) כי יש HEADER
        sap_dict = {}
        for idx, row in df_sap.iterrows():
            part_code = str(row.iloc[0]).strip().replace(" ", "")  # עמודה A ללא רווחים
            part_name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""  # עמודה B

            if part_code and part_code != "nan":
                sap_dict[part_code] = part_name

        print(f"✅ נטענו {len(sap_dict)} מק\"טים מקובץ SAP")
        return sap_dict

    except Exception as e:
        print(f"⚠️ שגיאה בטעינת קובץ SAP: {e}")
        return {}


# ==========================
# Main Export Function
# ==========================
def export_service_baskets_to_excel(json_path: str, output_dir: str, model_vin: str, model_code: str,
                                    model_desc: str = None):
    """
    Export service baskets to Excel with DEBUG prints
    """
    json_path = Path(json_path)
    output_dir = Path(output_dir)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON not found: {json_path}")

    # Create Excel directory if missing
    excel_dir = output_dir / "Excel"
    excel_dir.mkdir(exist_ok=True)

    # Build output file path
    excel_filename = f"{model_code} - קיט טיפולים.xlsx"
    excel_path = excel_dir / excel_filename

    print("\n" + "=" * 70)
    print("🐛 DEBUG MODE: export_service_baskets_to_excel")
    print("=" * 70)
    print(f"📄 JSON path: {json_path}")
    print(f"📂 Output dir: {output_dir}")
    print(f"🔑 Model VIN: {model_vin}")
    print(f"🔑 Model code: {model_code}")
    print(f"🔑 Model desc: {model_desc}")
    print("=" * 70 + "\n")

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # טעינת מאגר מק"טים מ-SAP
    sap_file_path = r"C:\Users\MayPery\PycharmProjects\Kits\Treatment Wizard\ExcelDB\פרטי מחסן סאפ - מקטים.xlsx"
    sap_parts_db = load_sap_parts_database(sap_file_path)

    print(f"📊 Loaded {len(sap_parts_db)} parts from SAP database\n")

    # Initialize writer
    writer = pd.ExcelWriter(excel_path, engine="xlsxwriter")
    writer.book.use_zip64()

    # Create worksheet RTL
    writer.book.add_format()

    # Build header based on whether model_desc is provided
    if model_desc:
        cleaned_model_code = model_code.split('_')[0]
        df_model = pd.DataFrame([
            {"Header": model_vin},
            {"Header": ""},
            {"Header": cleaned_model_code},
            {"Header": ""},
            {"Header": model_desc}
        ])
        print(f"✅ Header created WITH model_desc (5 rows)")
    else:
        cleaned_model_code = model_code.split('_')[0]
        df_model = pd.DataFrame([
            {"Header": model_vin},
            {"Header": ""},
            {"Header": cleaned_model_code}
        ])
        print(f"✅ Header created WITHOUT model_desc (3 rows)")

    df_model.to_excel(writer, sheet_name="טיפולים", index=False, startrow=0, header=False)

    worksheet = writer.sheets["טיפולים"]
    worksheet.right_to_left()

    # ✅ Calculate row_position based on actual DataFrame length
    row_position = len(df_model)
    print(f"✅ Starting row position: {row_position}\n")

    # Iterate over treatment blocks
    for key, block in data.items():
        if not key.isdigit():  # skip "model" and other metadata
            continue

        mileage = int(key)
        mileage_label = f"טיפול {format_km(mileage)} ק\"מ"
        matched_parts = block.get("matched_parts", [])

        if not matched_parts:
            continue

        print("\n" + "-" * 70)
        print(f"🔧 Processing: {mileage_label} ({len(matched_parts)} parts)")
        print("-" * 70)

        # Convert parts to rows
        rows = []
        for idx, part in enumerate(matched_parts, 1):
            # קבלת הערכים המקוריים
            original_service_line = part.get("SERVICE LINE", "")
            part_number = part.get("PART NUMBER", "")
            quantity = part.get("QUANTITY", "")

            print(f"\n  Part #{idx}:")
            print(f"    📦 SERVICE LINE: {original_service_line}")
            print(f"    🔑 PART NUMBER (from JSON): '{part_number}'")
            print(f"    📊 QUANTITY: {quantity}")

            # הסרת רווחים מהמק"ט לצורך חיפוש
            part_number_no_spaces = str(part_number).strip().replace(" ", "")
            print(f"    🔍 Searching in SAP with: '{part_number_no_spaces}'")

            # חיפוש בקובץ SAP
            if part_number_no_spaces in sap_parts_db:
                # נמצאה התאמה - החלפת שם החלק
                updated_service_line = sap_parts_db[part_number_no_spaces]
                print(f"    ✅ FOUND IN SAP!")
                print(f"    🔄 Replacing description:")
                print(f"       OLD: '{original_service_line}'")
                print(f"       NEW: '{updated_service_line}'")
                print(f"    ⚠️  Part number STAYS: '{part_number}'")
            else:
                # לא נמצאה התאמה - שומרים את הערך המקורי
                updated_service_line = original_service_line
                print(f"    ⚠️  NOT FOUND in SAP - keeping original description")

            rows.append({
                "חלקים": updated_service_line,
                "מק\"ט": part_number,  # ← Part number should NOT change!
                "כמות": quantity
            })

        # Add constant extra parts with SAP lookup
        print(f"\n  Adding {len(EXTRA_PARTS)} EXTRA parts...")
        for extra_idx, extra_part in enumerate(EXTRA_PARTS, 1):
            extra_service_line = extra_part["חלקים"]
            extra_part_number = extra_part["מק\"ט"]
            extra_quantity = extra_part["כמות"]

            print(f"\n  Extra Part #{extra_idx}:")
            print(f"    📦 SERVICE LINE: {extra_service_line}")
            print(f"    🔑 PART NUMBER: '{extra_part_number}'")

            # הסרת רווחים מהמק"ט לצורך חיפוש
            extra_part_number_no_spaces = str(extra_part_number).strip().replace(" ", "")
            print(f"    🔍 Searching in SAP with: '{extra_part_number_no_spaces}'")

            # חיפוש בקובץ SAP
            if extra_part_number_no_spaces in sap_parts_db:
                updated_extra_service_line = sap_parts_db[extra_part_number_no_spaces]
                print(f"    ✅ FOUND IN SAP!")
                print(f"    🔄 Replacing description:")
                print(f"       OLD: '{extra_service_line}'")
                print(f"       NEW: '{updated_extra_service_line}'")
            else:
                updated_extra_service_line = extra_service_line
                print(f"    ⚠️  NOT FOUND in SAP - keeping original")

            rows.append({
                "חלקים": updated_extra_service_line,
                "מק\"ט": extra_part_number,
                "כמות": extra_quantity
            })

        # Create DataFrame
        df = pd.DataFrame(rows)
        df['מק"ט'] = df['מק"ט'].str.replace(' ', '', regex=False)

        print(f"\n  ✅ Created DataFrame with {len(df)} rows")
        print(f"  📍 Writing to Excel starting at row {row_position}")

        # Write treatment title
        worksheet.write(row_position, 0, mileage_label)
        row_position += 1

        # Write table
        df.to_excel(writer, sheet_name="טיפולים", index=False, startrow=row_position)
        row_position += len(df) + 3  # spacing before next block

    writer.close()
    print("\n" + "=" * 70)
    print(f"✅ Excel created successfully:")
    print(f"📁 {excel_path}")
    print("=" * 70 + "\n")
    return str(excel_path)
