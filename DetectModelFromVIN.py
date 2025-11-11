"""
detect_vin.py
סקריפט פשוט להזנת VIN וקבלת תוצאה
"""

from SmartVinDecoder import SmartVinDecoder


def main():
    print("=" * 70)
    print("🚗 מערכת זיהוי VIN - Porsche")
    print("=" * 70)

    # טעינת המודל המאומן
    print("\n📊 טוען מודל...")
    decoder = SmartVinDecoder()
    decoder.load_model("smart_vin_decoder.pkl")
    print("✅ מודל נטען בהצלחה!\n")

    # לולאה אינסופית לקבלת VINs
    while True:
        print("-" * 70)
        vin = input("הכנס VIN (או 'exit' ליציאה): ").strip()

        if vin.lower() in ['exit', 'quit', 'q']:
            print("\n👋 להתראות!")
            break

        if not vin:
            print("⚠️ נא להזין VIN")
            continue

        if len(vin) != 17:
            print(f"⚠️ VIN צריך להיות בדיוק 17 תווים (הזנת {len(vin)} תווים)")
            continue

        # זיהוי
        print(f"\n🔍 מזהה VIN: {vin}")
        result = decoder.decode_vin(vin)

        # הצגת תוצאות
        print("\n📋 תוצאות:")
        print(f"   קוד דגם:        {result['model_code']}")
        print(f"   תיאור דגם:      {result['model_description']}")
        print(f"   רמת ביטחון:     {result['confidence']}%")
        print(f"   מקור זיהוי:     {result['source']}")

        # הסבר למקור
        source_explanation = {
            'exact_match': '✅ VIN נמצא במסד הנתונים',
            'pattern_matching': '🔍 נמצא VIN דומה במסד הנתונים',
            'ml_prediction': '🤖 ניבוי באמצעות Machine Learning',
            'failed': '❌ לא הצלחתי לזהות'
        }
        print(f"   הסבר:           {source_explanation.get(result['source'], 'לא ידוע')}")
        print()


if __name__ == "__main__":
    main()
