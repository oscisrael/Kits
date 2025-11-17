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
    {"חלקים": "נוזל שמשות",      "מק\"ט": "T.110",       "כמות": "1"},
    {"חלקים": "חומרי עזר",        "מק\"ט": "1111",        "כמות": "1"},
]


# ==========================
# Main Export Function
# ==========================
def export_service_baskets_to_excel(json_path: str, output_dir: str, model_code: str):
    json_path = Path(json_path)
    output_dir = Path(output_dir)

    if not json_path.exists():
        raise FileNotFoundError(f"JSON not found: {json_path}")

    # Create Excel directory if missing
    excel_dir = output_dir / "Excel"
    excel_dir.mkdir(exist_ok=True)

    # Build output file path
    excel_filename = f"{model_code} - Service Baskets.xlsx"
    excel_path = excel_dir / excel_filename

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Model header will use model_code instead of model name
    model_header_text = f"model: {model_code}"

    # Initialize writer
    writer = pd.ExcelWriter(excel_path, engine="xlsxwriter")
    writer.book.use_zip64()  # safer for larger files

    # Create worksheet RTL
    writer.book.add_format()
    df_model = pd.DataFrame([{"model": model_header_text}])
    df_model.to_excel(writer, sheet_name="טיפולים", index=False, startrow=0)

    worksheet = writer.sheets["טיפולים"]
    worksheet.right_to_left()  # <--- RTL ENABLED

    row_position = 3

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
            rows.append({
                "חלקים": part.get("SERVICE LINE", ""),
                "מק\"ט": part.get("PART NUMBER", ""),
                "כמות": part.get("QUANTITY", "")
            })

        # Add constant extra parts
        rows.extend(EXTRA_PARTS)

        # Create DataFrame
        df = pd.DataFrame(rows)

        # Write treatment title
        worksheet.write(row_position, 0, mileage_label)
        row_position += 1

        # Write table
        df.to_excel(writer, sheet_name="טיפולים", index=False, startrow=row_position)
        row_position += len(df) + 3  # spacing before next block

    writer.close()

    print(f"📁 Excel נוצר בהצלחה:\n{excel_path}")
    return str(excel_path)
