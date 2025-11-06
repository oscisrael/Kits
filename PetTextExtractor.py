import pdfplumber
import json


def extract_pdf_to_dicts(pdf_path, output_json_path=None):
    """
    המרת טבלה מ-PDF לרשימת מילונים.
    Part Number = המזהה (לא ריק = שורה חדשה)
    כל Part Number עם או בלי Remark, Qty, Model
    """

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()

            if table is None or len(table) < 2:
                continue

            data_row = table[1]

            # פרוק את הנתונים לפי \n
            ill_no_items = data_row[0].split('\n')
            pos_items = data_row[1].split('\n')
            part_number_items = data_row[2].split('\n')
            description_items = data_row[3].split('\n')
            remark_items = data_row[4].split('\n')
            qty_items = data_row[5].split('\n')
            model_items = data_row[6].split('\n')

            result_list = []

            # מונה לכל עמודה
            ill_no_idx = 0
            pos_idx = 0
            description_idx = 0
            remark_idx = 0
            qty_idx = 0
            model_idx = 0

            # עבור על כל Part Number (המזהה הראשי)
            for pn_idx, part_number in enumerate(part_number_items):
                part_number = part_number.strip()

                # אם Part Number ריק - זו continuation, דלג
                if not part_number:
                    # עדיין צרוך Description ו-Remark אם יש
                    if description_idx < len(description_items):
                        desc = description_items[description_idx].strip()
                        if desc:
                            description_idx += 1

                    if remark_idx < len(remark_items):
                        rem = remark_items[remark_idx].strip()
                        if rem:
                            remark_idx += 1
                    continue

                # זו שורה חדשה - קח ערכים
                ill_no = ""
                pos = ""
                qty = ""
                model = ""

                # קח את הערכים הבאים מכל עמודה
                if ill_no_idx < len(ill_no_items):
                    ill_no = ill_no_items[ill_no_idx].strip()
                    ill_no_idx += 1

                if pos_idx < len(pos_items):
                    pos = pos_items[pos_idx].strip()
                    pos_idx += 1

                if qty_idx < len(qty_items):
                    qty = qty_items[qty_idx].strip()
                    qty_idx += 1

                if model_idx < len(model_items):
                    model = model_items[model_idx].strip()
                    model_idx += 1

                # צבור Description ו-Remark עד שנגיע ל-Part Number הבא
                description_parts = []
                remark_parts = []

                # קח את ה-Description ו-Remark הנוכחיים
                if description_idx < len(description_items):
                    desc = description_items[description_idx].strip()
                    if desc:
                        description_parts.append(desc)
                    description_idx += 1

                if remark_idx < len(remark_items):
                    rem = remark_items[remark_idx].strip()
                    if rem:
                        remark_parts.append(rem)
                    remark_idx += 1

                # בדוק את ה-Part Numbers הבאים - אם הם ריקים, צרוך עוד Description ו-Remark
                next_pn_idx = pn_idx + 1
                while next_pn_idx < len(part_number_items):
                    next_pn = part_number_items[next_pn_idx].strip()

                    if next_pn:  # Part Number חדש - עצור
                        break

                    # Part Number ריק - צרוך עוד Description ו-Remark
                    if description_idx < len(description_items):
                        desc = description_items[description_idx].strip()
                        if desc:
                            description_parts.append(desc)
                        description_idx += 1

                    if remark_idx < len(remark_items):
                        rem = remark_items[remark_idx].strip()
                        if rem:
                            remark_parts.append(rem)
                        remark_idx += 1

                    next_pn_idx += 1

                # בנה את המילון
                row_dict = {
                    "Ill-No.": ill_no,
                    "Pos": parse_pos(pos),
                    "Part Number": part_number,
                    "Description": " ".join(description_parts),
                    "Remark": " ".join(remark_parts),
                    "Qty": parse_qty(qty),
                    "Model": model
                }
                result_list.append(row_dict)

            # הדפסה לקונסול
            print("[")
            for idx, row in enumerate(result_list):
                print(f"  {json.dumps(row, ensure_ascii=False)}" + ("," if idx < len(result_list) - 1 else ""))
            print("]")

            # שמירה לקובץ JSON
            if output_json_path:
                with open(output_json_path, 'w', encoding='utf-8') as f:
                    json.dump(result_list, f, ensure_ascii=False, indent=2)
                print(f"\n✓ הקובץ נשמר בהצלחה ל: {output_json_path}")

            print(f"\n✓ סך הכל {len(result_list)} שורות חולצו בהצלחה!")
            return result_list


def parse_pos(pos_str):
    """המרת Pos למספר"""
    if not pos_str:
        return None
    pos_str = pos_str.replace("(", "").replace(")", "").strip()
    try:
        return int(pos_str)
    except ValueError:
        return None


def parse_qty(qty_str):
    """המרת Qty למספר"""
    if not qty_str:
        return None
    qty_str = qty_str.strip()
    try:
        return int(qty_str)
    except ValueError:
        return qty_str


# שימוש:
if __name__ == "__main__":
    pdf_path = "PET Files/Panamera - PET File.pdf"
    output_json_path = "output.json"

    rows = extract_pdf_to_dicts(pdf_path, output_json_path)
