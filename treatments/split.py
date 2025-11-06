import json
import os
from pathlib import Path


def split_classified_files(input_folder, output_folder=None):
    """
    מקבל תיקייה עם קבצי JSON מסווגים ומפריד כל קובץ לשני קבצים:
    1. קובץ עם כל הפריטים מסוג "חלק"
    2. קובץ עם כל הפריטים מסוג "פעולה"

    Parameters:
    -----------
    input_folder : str
        נתיב לתיקייה שבה נמצאים קבצי ה-JSON המסווגים
    output_folder : str, optional
        נתיב לתיקיית הפלט. אם לא מסופק, נשתמש באותה תיקייה
    """

    # אם לא סופק תיקיית פלט, נשתמש בתיקיית הקלט
    if output_folder is None:
        output_folder = input_folder

    # יצירת תיקיית הפלט אם היא לא קיימת
    os.makedirs(output_folder, exist_ok=True)

    # מציאת כל קבצי ה-JSON בתיקייה
    input_path = Path(input_folder)
    json_files = list(input_path.glob("*_classified.json"))

    if not json_files:
        print(f"לא נמצאו קבצי JSON מסווגים בתיקייה: {input_folder}")
        return

    # עיבוד כל קובץ
    for json_file in json_files:
        print(f"\nמעבד קובץ: {json_file.name}")

        # קריאת הקובץ
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # יצירת שני מבנים חדשים - אחד לחלקים ואחד לפעולות
        parts_data = {}
        actions_data = {}

        # מעבר על כל רמות השירות
        for service_level, models_dict in data.items():
            parts_data[service_level] = {}
            actions_data[service_level] = {}

            # מעבר על כל דגם
            for model_name, items_list in models_dict.items():
                parts_items = []
                actions_items = []

                # סינון הפריטים לפי סוג
                for item in items_list:
                    if item['type'] == 'חלק':
                        parts_items.append(item)
                    elif item['type'] == 'פעולה':
                        actions_items.append(item)

                # הוספה למבנה רק אם יש פריטים
                if parts_items:
                    parts_data[service_level][model_name] = parts_items
                if actions_items:
                    actions_data[service_level][model_name] = actions_items

            # הסרת רמת שירות ריקה
            if not parts_data[service_level]:
                del parts_data[service_level]
            if not actions_data[service_level]:
                del actions_data[service_level]

        # שמירת הקבצים החדשים
        base_name = json_file.stem.replace('_classified', '')

        # קובץ חלקים
        parts_file = Path(output_folder) / f"{base_name}_parts.json"
        with open(parts_file, 'w', encoding='utf-8') as f:
            json.dump(parts_data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ נוצר קובץ חלקים: {parts_file.name}")

        # קובץ פעולות
        actions_file = Path(output_folder) / f"{base_name}_actions.json"
        with open(actions_file, 'w', encoding='utf-8') as f:
            json.dump(actions_data, f, ensure_ascii=False, indent=2)
        print(f"  ✓ נוצר קובץ פעולות: {actions_file.name}")

        # הדפסת סטטיסטיקות
        total_parts = sum(len(items) for models in parts_data.values() for items in models.values())
        total_actions = sum(len(items) for models in actions_data.values() for items in models.values())
        print(f"  סה\"כ חלקים: {total_parts}")
        print(f"  סה\"כ פעולות: {total_actions}")

    print(f"\n✅ הושלם! נוצרו {len(json_files) * 2} קבצים חדשים")


# דוגמה לשימוש:
if __name__ == "__main__":
    # הגדר כאן את נתיב התיקייה שלך
    folder_path = r"/Claude_classification"

    # הפרד את הקבצים
    split_classified_files(folder_path)

    # או אם אתה רוצה לשמור בתיקייה אחרת:
    # split_classified_files(folder_path, output_folder=r"C:\path\to\output")
