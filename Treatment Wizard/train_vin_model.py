"""
train_vin_model.py
סקריפט לאימון המערכת החכמה פעם אחת
"""

from foundation_codes.SmartVinDecoder import SmartVinDecoder

def main():
    print("="*70)
    print("🚀 אימון מערכת זיהוי VIN חכמה")
    print("="*70)

    # יצירת המערכת - תני נתיב מלא לקובץ!
    excel_path = r"ExcelDB/VINS and Model Descriptions - including Model Code (all data).xlsx"

    decoder = SmartVinDecoder(excel_path)

    # אימון
    decoder.train_model()

    # שמירה
    decoder.save_model("smart_vin_decoder.pkl")

    # בדיקות
    print("\n" + "="*70)
    print("✅ בדיקות")
    print("="*70)

    test_cases = [
        "WP1ZZZXA6SL078845",  # Macan - VIN חדש
        "WP1ZZZXAXSL078833",  # Macan - VIN קיים
        "WP0ZZZYA3SL047443",  # Panamera
        "WP1ZZZ9Y2SDA28919",  # Cayenne
    ]

    for vin in test_cases:
        result = decoder.decode_vin(vin)
        print(f"\n{vin}")
        print(f"  → {result['model_code']} | {result['model_description']}")
        print(f"  → {result['confidence']}% ({result['source']})")

    print("\n" + "="*70)
    print("✅ המערכת מוכנה לשימוש!")
    print("="*70)

if __name__ == "__main__":
    main()
