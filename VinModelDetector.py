"""
PorscheVINDecoder.py
מערכת לזיהוי וניתוח VIN של רכבי פורשה
"""

import pandas as pd
import re
from typing import Dict, Optional, List
from datetime import datetime


class PorscheVINDecoder:
    """
    מחלקה לזיהוי וניתוח VIN של רכבי פורשה
    תומכת בזיהוי תבניות ולמידה מקובץ Excel
    """

    # מיפוי שנות ייצור לפי תו 10 ב-VIN
    YEAR_CODE = {
        'A': 1980, 'B': 1981, 'C': 1982, 'D': 1983, 'E': 1984,
        'F': 1985, 'G': 1986, 'H': 1987, 'J': 1988, 'K': 1989,
        'L': 1990, 'M': 1991, 'N': 1992, 'P': 1993, 'R': 1994,
        'S': 1995, 'T': 1996, 'V': 1997, 'W': 1998, 'X': 1999,
        'Y': 2000, '1': 2001, '2': 2002, '3': 2003, '4': 2004,
        '5': 2005, '6': 2006, '7': 2007, '8': 2008, '9': 2009,
    }

    # מיפוי קודי דגמים ידועים
    MODEL_CODES = {
        '964': '911 (964)',
        '993': '911 (993)',
        '996': '911 (996)',
        '997': '911 (997)',
        '991': '911 (991)',
        '992': '911 (992)',
        '986': 'Boxster (986)',
        '987': 'Boxster/Cayman (987)',
        '981': 'Boxster/Cayman (981)',
        '982': 'Boxster/Cayman (982)',
        '955': 'Cayenne (955)',
        '957': 'Cayenne (957)',
        '958': 'Cayenne (958)',
        '9PA': 'Cayenne (92A)',
        '970': 'Panamera (970)',
        '971': 'Panamera (971)',
        '9Y0': 'Panamera (G2)',
        '95B': 'Macan',
        '929': 'Cayenne (PO536)',
        '9A2': 'Taycan',
    }

    def __init__(self, excel_path: Optional[str] = None, mode: str = 'hybrid'):
        """
        אתחול המחלקה

        Args:
            excel_path: נתיב לקובץ Excel עם VINs ידועים
            mode: 'local' (חיפוש בטבלה בלבד), 'pattern' (זיהוי תבניות בלבד),
                  'hybrid' (קודם טבלה, אחר כך תבניות)
        """
        self.mode = mode
        self.vins_db = None
        self.learned_patterns = {}

        if excel_path:
            self.load_excel_database(excel_path)

    def load_excel_database(self, excel_path: str):
        """טעינת מסד נתוני VINs מקובץ Excel"""
        try:
            self.vins_db = pd.read_excel(excel_path)
            print(f"✓ נטענו {len(self.vins_db)} VINs מהמסד נתונים")
            self._learn_patterns_from_database()
        except Exception as e:
            print(f"⚠ שגיאה בטעינת קובץ Excel: {e}")
            self.vins_db = None

    def _learn_patterns_from_database(self):
        """למידת תבניות מהמסד נתונים"""
        if self.vins_db is None:
            return

        # בניית מילון של קודי דגמים ותיאורים
        for _, row in self.vins_db.iterrows():
            vin = str(row['מספר שלדה'])
            model_desc = str(row['תיאור דגם'])
            model_code = str(row['קוד דגם'])

            # חילוץ קוד דגם מה-VIN
            if len(vin) >= 12:
                extracted_code = vin[6] + vin[7] + vin[11]

                if extracted_code not in self.learned_patterns:
                    self.learned_patterns[extracted_code] = {
                        'descriptions': set(),
                        'model_codes': set()
                    }

                self.learned_patterns[extracted_code]['descriptions'].add(model_desc)
                self.learned_patterns[extracted_code]['model_codes'].add(model_code)

        print(f"✓ נלמדו {len(self.learned_patterns)} תבניות דגמים")

    def validate_vin(self, vin: str) -> bool:
        """בדיקת תקינות VIN"""
        if not vin or not isinstance(vin, str):
            return False

        # הסרת רווחים
        vin = vin.strip().upper()

        # בדיקת אורך
        if len(vin) != 17:
            return False

        # בדיקה שמתחיל ב-WP (פורשה)
        if not vin.startswith('WP'):
            return False

        # בדיקה שמכיל רק תווים חוקיים (אין I, O, Q)
        if not re.match(r'^[A-HJ-NPR-Z0-9]{17}$', vin):
            return False

        return True

    def extract_year(self, vin: str) -> Optional[int]:
        """חילוץ שנת ייצור מה-VIN (גרסה מתוקנת)"""
        if len(vin) < 10:
            return None

        year_char = vin[9]  # תו 10 (אינדקס 9)

        # בדיקה במיפוי הבסיסי
        if year_char in self.YEAR_CODE:
            base_year = self.YEAR_CODE[year_char]
            current_year = datetime.now().year

            # אם השנה הבסיסית ישנה מדי (יותר מ-15 שנה אחורה), נוסיף 30 שנה
            # זה מטפל במחזוריות של קוד השנה
            while base_year < current_year - 15:
                base_year += 30

            # אם קיבלנו שנה עתידית מדי (יותר מ-2 שנים קדימה), נחזיר למחזור הקודם
            if base_year > current_year + 2:
                base_year -= 30

            return base_year

        return None

    def extract_model_code(self, vin: str) -> str:
        """חילוץ קוד דגם מה-VIN (תווים 7+8+12)"""
        if len(vin) < 12:
            return ""

        return vin[6] + vin[7] + vin[11]

    def get_model_name(self, model_code: str) -> str:
        """קבלת שם דגם לפי קוד"""
        # חיפוש במילון הידוע
        if model_code in self.MODEL_CODES:
            return self.MODEL_CODES[model_code]

        # חיפוש בתבניות שנלמדו
        if model_code in self.learned_patterns:
            descriptions = self.learned_patterns[model_code]['descriptions']
            if descriptions:
                # החזרת התיאור הנפוץ ביותר
                return list(descriptions)[0]

        return "Unknown Model"

    def search_in_database(self, vin: str) -> Optional[Dict]:
        """חיפוש VIN במסד הנתונים המקומי"""
        if self.vins_db is None:
            return None

        # חיפוש התאמה מדויקת
        match = self.vins_db[self.vins_db['מספר שלדה'] == vin]

        if not match.empty:
            row = match.iloc[0]
            year = self.extract_year(vin)

            return {
                'vin': vin,
                'model': str(row['תיאור דגם']),
                'year': year,
                'sub_model': str(row['תיאור דגם']),
                'model_code': str(row['קוד דגם']),
                'source': 'database',
                'confidence': 'exact_match'
            }

        return None

    def decode_by_pattern(self, vin: str) -> Dict:
        """זיהוי VIN לפי תבניות"""
        model_code = self.extract_model_code(vin)
        year = self.extract_year(vin)
        model_name = self.get_model_name(model_code)

        # ניסיון לחלץ פרטים נוספים
        sub_model = model_name

        # אם יש תבנית נלמדת, נשתמש בה
        if model_code in self.learned_patterns:
            descriptions = self.learned_patterns[model_code]['descriptions']
            if descriptions:
                sub_model = list(descriptions)[0]
                confidence = 'high'
            else:
                confidence = 'medium'
        else:
            confidence = 'low' if model_name == "Unknown Model" else 'medium'

        return {
            'vin': vin,
            'model': model_name,
            'year': year,
            'sub_model': sub_model,
            'model_code': model_code,
            'source': 'pattern_recognition',
            'confidence': confidence
        }

    def find_similar_vins(self, vin: str, max_results: int = 5) -> List[str]:
        """חיפוש VINs דומים במסד הנתונים"""
        if self.vins_db is None:
            return []

        model_code = self.extract_model_code(vin)
        similar = []

        for _, row in self.vins_db.iterrows():
            db_vin = str(row['מספר שלדה'])
            db_model_code = self.extract_model_code(db_vin)

            if db_model_code == model_code:
                similar.append(db_vin)
                if len(similar) >= max_results:
                    break

        return similar

    def decode(self, vin: str) -> Dict:
        """
        פענוח VIN ראשי

        Args:
            vin: מספר שלדה

        Returns:
            מילון עם פרטי הרכב או הודעת שגיאה
        """
        # ניקוי והמרה לאותיות גדולות
        vin = vin.strip().upper()

        # בדיקת תקינות
        if not self.validate_vin(vin):
            return {
                'vin': vin,
                'error': 'VIN לא תקין. VIN חייב להיות בן 17 תווים ולהתחיל ב-WP',
                'success': False
            }

        result = None

        # מצב LOCAL - חיפוש רק במסד נתונים
        if self.mode == 'local':
            result = self.search_in_database(vin)
            if result is None:
                similar = self.find_similar_vins(vin)
                return {
                    'vin': vin,
                    'error': 'VIN לא נמצא במסד הנתונים',
                    'suggestion': f'נמצאו VINs דומים: {similar[:3]}' if similar else 'אין הצעות',
                    'success': False
                }

        # מצב PATTERN - זיהוי רק לפי תבניות
        elif self.mode == 'pattern':
            result = self.decode_by_pattern(vin)

        # מצב HYBRID - קודם מסד נתונים, אחר כך תבניות
        else:  # hybrid
            result = self.search_in_database(vin)
            if result is None:
                result = self.decode_by_pattern(vin)
                # הוספת הצעות VINs דומים
                similar = self.find_similar_vins(vin)
                if similar:
                    result['similar_vins'] = similar[:3]

        result['success'] = True
        return result

    def decode_batch(self, vins: List[str]) -> List[Dict]:
        """פענוח מספר VINs בבת אחת"""
        return [self.decode(vin) for vin in vins]

    def get_statistics(self) -> Dict:
        """קבלת סטטיסטיקות על המסד נתונים"""
        if self.vins_db is None:
            return {'error': 'אין מסד נתונים טעון'}

        stats = {
            'total_vins': len(self.vins_db),
            'unique_models': self.vins_db['קוד דגם'].nunique(),
            'learned_patterns': len(self.learned_patterns),
            'model_distribution': self.vins_db['קוד דגם'].value_counts().to_dict()
        }

        return stats


# ============================================
# דוגמאות שימוש
# ============================================

if __name__ == "__main__":
    # יצירת מופע של ה-decoder
    decoder = PorscheVINDecoder(
        excel_path='ExcelDB/VINS and Model Descriptions - including Model Code (all data).xlsx',
        mode='hybrid'
    )

    input_vin = input("Inset VIN: ")
    result = decoder.decode(input_vin)

    if result['success']:
        print(f"   ✓ model: {result['model']}")
        print(f"   ✓ year: {result['year']}")
        print(f"   ✓ sub-model: {result['sub_model']}")
        print(f"   ✓ model-code: {result['model_code']}")
        print(f"   ✓ source: {result['source']}")
        print(f"   ✓confidence: {result['confidence']}")
    else:
        print(f"   ✗ error: {result['error']}")
        if 'suggestion' in result:
            print(f"   💡 {result['suggestion']}")

    # # דוגמאות VINs
    # test_vins = [
    #     'WP0ZZZ99ZTS392124',  # 911 Carrera S
    #     'WP0AA2999SS621435',  # 911
    #     'WP0CA2986SS621123',  # Boxster
    #     'WP1ZZZ9PZLA012345',  # Cayenne
    #     'INVALID12345',  # VIN לא תקין
    # ]
    #
    # print("\n" + "=" * 60)
    # print("בדיקת VIN Decoder")
    # print("=" * 60)
    #
    # for vin in test_vins:
    #     print(f"\n🔍 בודק VIN: {vin}")
    #     result = decoder.decode(vin)
    #
    #     if result['success']:
    #         print(f"   ✓ דגם: {result['model']}")
    #         print(f"   ✓ שנה: {result['year']}")
    #         print(f"   ✓ תת-דגם: {result['sub_model']}")
    #         print(f"   ✓ קוד דגם: {result['model_code']}")
    #         print(f"   ✓ מקור: {result['source']}")
    #         print(f"   ✓ רמת ביטחון: {result['confidence']}")
    #     else:
    #         print(f"   ✗ שגיאה: {result['error']}")
    #         if 'suggestion' in result:
    #             print(f"   💡 {result['suggestion']}")
    #
    # # הצגת סטטיסטיקות
    # print("\n" + "=" * 60)
    # print("סטטיסטיקות מסד נתונים")
    # print("=" * 60)
    # stats = decoder.get_statistics()
    # for key, value in stats.items():
    #     if key != 'model_distribution':
    #         print(f"{key}: {value}")
