"""
סקריפט להמרת קבצי קיט טיפולים לפורמט אקסיומה
הסקריפט מבקש מהמשתמש להזין את נתיב הקובץ
"""

import pandas as pd
import os
from pathlib import Path


def convert_kit_to_axioma_format(input_file_path):
    """
    ממיר קובץ קיט טיפולים לפורמט אקסיומה

    Parameters:
    input_file_path (str): נתיב לקובץ המקור

    Returns:
    str: נתיב לקובץ הפלט
    """

    try:
        # בדיקה שהקובץ קיים
        if not os.path.exists(input_file_path):
            raise FileNotFoundError(f"הקובץ לא נמצא: {input_file_path}")

        print(f"\nמעבד את הקובץ: {input_file_path}")

        # קריאת הקובץ המקורי
        df = pd.read_excel(input_file_path, header=None)

        # קבלת קוד הדגם מתא A3 (שורה 2, עמודה 0 ב-pandas)
        model_code = df.iloc[2, 0]
        print(f"קוד דגם: {model_code}")

        # רשימה לאחסון התוצאות
        results = []

        # מעבר על כל השורות בקובץ
        current_treatment = None
        i = 0

        while i < len(df):
            row = df.iloc[i]
            first_cell = str(row[0]).strip()

            # בדיקה אם זה שורת טיפול (מתחיל ב"טיפול")
            if first_cell.startswith("טיפול") and not pd.isna(row[0]):
                current_treatment = first_cell
                print(f"מעבד טיפול: {current_treatment}")
                i += 1
                continue

            # בדיקה אם זו שורת כותרת (חלקים/מק"ט/כמות)
            if first_cell == "חלקים":
                i += 1
                continue

            # בדיקה אם זו שורת פריט (יש מק"ט וכמות)
            if current_treatment and not pd.isna(row[1]) and row[1] != "מק\"ט":
                item_name = row[0]
                item_code = str(row[1]).strip()
                quantity = row[2]

                # התעלמות משורות "עבודה"
                if item_name != "עבודה" and not pd.isna(quantity):
                    results.append({
                        'קוד דגם': model_code,
                        'קוד קיט': None,  # עמודה ריקה
                        'שם קיט': current_treatment,
                        'קוד פריט': item_code,
                        'כמות': quantity
                    })

            i += 1

        if not results:
            raise ValueError("לא נמצאו טיפולים בקובץ")

        # יצירת DataFrame מהתוצאות
        output_df = pd.DataFrame(results)

        # יצירת שם הקובץ החדש
        input_path = Path(input_file_path)
        output_filename = f"{input_path.stem} - פורמט אקסיומה{input_path.suffix}"
        output_path = input_path.parent / output_filename

        # שמירת הקובץ
        output_df.to_excel(output_path, index=False)

        print(f"\n{'='*60}")
        print(f"✓ ההמרה הושלמה בהצלחה!")
        print(f"✓ הקובץ החדש נשמר ב: {output_path}")
        print(f"✓ סה\"כ שורות בקובץ החדש: {len(output_df)}")
        print(f"{'='*60}")

        return str(output_path)

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"✗ שגיאה בעיבוד הקובץ: {str(e)}")
        print(f"{'='*60}")
        raise


def main():
    """
    פונקציה ראשית - מבקשת מהמשתמש להזין נתיב קובץ
    """
    print("="*60)
    print("המרת קיט טיפולים לפורמט אקסיומה")
    print("="*60)

    while True:
        print("\nהכנס את הנתיב המלא לקובץ האקסל:")
        print("(או הקלד 'exit' ליציאה)")
        print("\nדוגמה: C:\\Users\\YourName\\Documents\\קיט טיפולים.xlsx")

        input_file = input("\nנתיב הקובץ: ").strip()

        # בדיקה אם המשתמש רוצה לצאת
        if input_file.lower() == 'exit':
            print("\nיציאה מהתוכנית. להתראות!")
            break

        # הסרת גרשיים אם המשתמש הדביק נתיב עם גרשיים
        input_file = input_file.strip('"').strip("'")

        # בדיקה שהקובץ קיים
        if not input_file:
            print("\n✗ לא הוזן נתיב. נסה שוב.")
            continue

        if not os.path.exists(input_file):
            print(f"\n✗ הקובץ לא נמצא: {input_file}")
            print("אנא בדוק את הנתיב ונסה שוב.")
            continue

        # ביצוע ההמרה
        try:
            output_file = convert_kit_to_axioma_format(input_file)

            # שאלה אם רוצים להמיר קובץ נוסף
            print("\nרוצה להמיר קובץ נוסף? (y/n)")
            answer = input().strip().lower()

            if answer not in ['y', 'yes', 'כן', 'ע']:
                print("\nתודה! להתראות!")
                break

        except Exception as e:
            print("\nרוצה לנסות שוב? (y/n)")
            answer = input().strip().lower()

            if answer not in ['y', 'yes', 'כן', 'ע']:
                print("\nתודה! להתראות!")
                break


if __name__ == "__main__":
    main()
