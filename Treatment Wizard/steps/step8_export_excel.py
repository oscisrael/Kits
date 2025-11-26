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

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # טעינת מאגר מק"טים מ-SAP
    sap_file_path = r"C:\Users\MayPery\PycharmProjects\Kits\Treatment Wizard\ExcelDB\פרטי מחסן סאפ - מקטים.xlsx"
    sap_parts_db = load_sap_parts_database(sap_file_path)

    # Initialize writer
    writer = pd.ExcelWriter(excel_path, engine="xlsxwriter")
    writer.book.use_zip64()  # safer for larger files

    # Create worksheet RTL
    writer.book.add_format()

    # Build header based on whether model_desc is provided
    if model_desc:
        # ניקוי model_code מחלק אחרי מקף תחתון אם קיים
        cleaned_model_code = model_code.split('_')[0]  # לוקח רק את החלק שלפני _
        df_model = pd.DataFrame([
            {"Header": model_vin},
            {"Header": ""},
            {"Header": cleaned_model_code}
        ])
    else:
        cleaned_model_code = model_code.split('_')[0]
        df_model = pd.DataFrame([
            {"Header": model_vin},
            {"Header": ""},
            {"Header": cleaned_model_code}
        ])

    df_model.to_excel(writer, sheet_name="טיפולים", index=False, startrow=0, header=False)

    worksheet = writer.sheets["טיפולים"]
    worksheet.right_to_left()  # <--- RTL ENABLED

    row_position = 3 if not model_desc else 4  # Extra row if model_desc present

    # Iterate over treatment blocks
    for key, block in data.items():
        if not key.isdigit():  # skip "model" and other metadata
            continue

        mileage = int(key)
        mileage_label = f"טיפול {format_km(mileage)} ק\"מ"
        matched_parts = block.get("matched_parts", [])

        if not matched_parts:
            continue

        # Convert parts to rows
        rows = []
        for part in matched_parts:
            # קבלת הערכים המקוריים
            original_service_line = part.get("SERVICE LINE", "")
            part_number = part.get("PART NUMBER", "")
            quantity = part.get("QUANTITY", "")

            # הסרת רווחים מהמק"ט לצורך חיפוש
            part_number_no_spaces = str(part_number).strip().replace(" ", "")

            # חיפוש בקובץ SAP
            if part_number_no_spaces in sap_parts_db:
                # נמצאה התאמה - החלפת שם החלק
                updated_service_line = sap_parts_db[part_number_no_spaces]
                print(f"🔄 הוחלף: '{original_service_line}' ← '{updated_service_line}' (מק\"ט: {part_number})")
            else:
                # לא נמצאה התאמה - שומרים את הערך המקורי
                updated_service_line = original_service_line

            rows.append({
                "חלקים": updated_service_line,
                "מק\"ט": part_number,
                "כמות": quantity
            })

        # Add constant extra parts with SAP lookup
        for extra_part in EXTRA_PARTS:
            extra_service_line = extra_part["חלקים"]
            extra_part_number = extra_part["מק\"ט"]
            extra_quantity = extra_part["כמות"]

            # הסרת רווחים מהמק"ט לצורך חיפוש
            extra_part_number_no_spaces = str(extra_part_number).strip().replace(" ", "")

            # חיפוש בקובץ SAP
            if extra_part_number_no_spaces in sap_parts_db:
                updated_extra_service_line = sap_parts_db[extra_part_number_no_spaces]
                print(
                    f"🔄 הוחלף (EXTRA): '{extra_service_line}' ← '{updated_extra_service_line}' (מק\"ט: {extra_part_number})")
            else:
                updated_extra_service_line = extra_service_line

            rows.append({
                "חלקים": updated_extra_service_line,
                "מק\"ט": extra_part_number,
                "כמות": extra_quantity
            })

        # Create DataFrame
        df = pd.DataFrame(rows)
        df['מק"ט'] = df['מק"ט'].str.replace(' ', '', regex=False)

        # Write treatment title
        worksheet.write(row_position, 0, mileage_label)
        row_position += 1

        # Write table
        df.to_excel(writer, sheet_name="טיפולים", index=False, startrow=row_position)
        row_position += len(df) + 3  # spacing before next block

    writer.close()
    print(f"📁 Excel נוצר בהצלחה:\n{excel_path}")
    return str(excel_path)
