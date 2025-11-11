import pdfplumber
import json
import re


def extract_with_accurate_columns(pdf_path, output_json_path=None):
    """
    חילוץ מדויק עם גבולות עמודות מדויקים - ללא OCR!
    """

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]

        # חלץ מילים (טקסט ישיר מה-PDF, לא OCR!)
        words = page.extract_words(x_tolerance=3, y_tolerance=3)

        # קבץ לפי Y
        rows = {}
        for word in words:
            y = round(word['top'])
            if y not in rows:
                rows[y] = []
            rows[y].append(word)

        # מיין
        for y in rows:
            rows[y] = sorted(rows[y], key=lambda w: w['x0'])

        sorted_rows = sorted(rows.items(), key=lambda r: r[0])

        # מצא header
        header_idx = None
        for i, (y, row_words) in enumerate(sorted_rows):
            text = " ".join([w['text'] for w in row_words])
            if "Ill-No." in text and "Pos" in text:
                header_idx = i
                break

        print(f"Header נמצא בשורה {header_idx}")

        # עבור על שורות הנתונים
        result_list = []
        current_row = None

        for i in range(header_idx + 1, len(sorted_rows)):
            y, row_words = sorted_rows[i]

            if not row_words:
                continue

            # בדוק אם זו שורה חדשה (מתחילה עם Ill-No. ב-X=23)
            first_word = row_words[0]
            is_new_row = (first_word['x0'] < 30 and
                          re.match(r'^\d{3}-\d{3}$', first_word['text']))

            if is_new_row:
                # שמור שורה קודמת
                if current_row:
                    result_list.append(current_row)

                # פרוק שורה חדשה
                current_row = parse_row_accurate(row_words)
            else:
                # זו continuation
                if current_row:
                    # צרף לפי X
                    for word in row_words:
                        x = word['x0']
                        text = word['text']

                        if x < 85:  # Ill-No. - לא צריך
                            pass
                        elif x < 130:  # Pos - לא צריך
                            pass
                        elif x < 210:  # Part Number - לא צריך
                            pass
                        elif x < 380:  # Description
                            if current_row["Description"]:
                                current_row["Description"] += " " + text
                            else:
                                current_row["Description"] = text
                        elif x < 465:  # Remark
                            if current_row["Remark"]:
                                current_row["Remark"] += " " + text
                            else:
                                current_row["Remark"] = text
                        elif x < 510:  # Qty - לא צריך
                            pass
                        else:  # Model
                            if current_row["Model"]:
                                current_row["Model"] += " " + text
                            else:
                                current_row["Model"] = text

        # שמור שורה אחרונה
        if current_row:
            result_list.append(current_row)

        # שמור
        if output_json_path:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(result_list, f, ensure_ascii=False, indent=2)
            print(f"\n✓ נשמר ל: {output_json_path}")

        print(f"✓ חולצו {len(result_list)} שורות")
        return result_list


def parse_row_accurate(row_words):
    """
    פרוק שורה עם גבולות מדויקים
    """
    row_dict = {
        "Ill-No.": "",
        "Pos": "",
        "Part Number": "",
        "Description": "",
        "Remark": "",
        "Qty": "",
        "Model": ""
    }

    for word in row_words:
        x = word['x0']
        text = word['text']

        # זהה לפי X
        if x < 85:  # Ill-No.
            row_dict["Ill-No."] += text + " "
        elif x < 130:  # Pos
            row_dict["Pos"] += text + " "
        elif x < 210:  # Part Number (6 מילים)
            row_dict["Part Number"] += text + " "
        elif x < 380:  # Description
            row_dict["Description"] += text + " "
        elif x < 465:  # Remark
            row_dict["Remark"] += text + " "
        elif x < 510:  # Qty
            row_dict["Qty"] += text + " "
        else:  # Model
            row_dict["Model"] += text + " "

    # נקה רווחים
    for key in row_dict:
        row_dict[key] = row_dict[key].strip()

    # נקה Pos מסוגריים
    if row_dict["Pos"]:
        row_dict["Pos"] = row_dict["Pos"].replace("(", "").replace(")", "")

    return row_dict


if __name__ == "__main__":
    import os
    import glob

    # בקשת תיקיית קלט מהמשתמש
    input_folder = input("הכנס/י תיקייה עם קבצי PET (לדוגמה: 'PET Files'): ").strip()

    if not os.path.isdir(input_folder):
        print(f"❌ השגיאה: '{input_folder}' אינה תיקייה תקינה.")
        exit()

    # יצירת תיקיית פלט
    output_folder = "PET Outputs"
    os.makedirs(output_folder, exist_ok=True)

    # מציאת כל קבצי ה-PDF בתיקייה
    pdf_files = glob.glob(os.path.join(input_folder, "*.pdf"))

    if not pdf_files:
        print("❌ לא נמצאו קבצי PDF בתיקייה.")
        exit()

    print(f"\n✓ נמצאו {len(pdf_files)} קבצים. מתחיל עיבוד...\n")

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)

        # הוצאת שם ללא הסיומת
        base_name = file_name.replace(".pdf", "")

        # הורדת " - PET File" אם קיים
        clean_name = base_name.replace(" - PET File", "").strip()

        # יצירת שם פלט
        output_name = f"{clean_name} PET lines.json"
        output_path = os.path.join(output_folder, output_name)

        print(f"⏳ מעבד: {file_name}")
        rows = extract_with_accurate_columns(pdf_path, output_path)
        print(f"✅ נשמר: {output_path}\n")

    print("\n🎉 הסתיים! כל הפלטים נמצאים בתיקייה:")
    print(f"➡  {output_folder}")
