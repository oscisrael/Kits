"""
SmartVinDecoder.py
מערכת חכמה לזיהוי קוד דגם מ-VIN באמצעות ML + מיפוי ישיר
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import pickle
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

class SmartVinDecoder:
    """
    מערכת היברידית לזיהוי קוד דגם:
    1. Exact Match - בדיקה ישירה במסד נתונים
    2. ML Prediction - ניבוי באמצעות Random Forest
    3. Pattern Matching - חיפוש דגמים דומים
    """

    def __init__(self, excel_path: str = "VINS-and-Model-Descriptions-including-Model-Code-all-data.xlsx"):
        self.excel_path = excel_path
        self.model = None
        self.vin_database = {}
        self.df = None
        self.code_to_desc = {}  # ← חדש! מיפוי קוד דגם -> תיאור

        # טעינה אוטומטית
        if os.path.exists(excel_path):
            self.load_data()

    def load_data(self):
        """טוען את הדאטה מה-Excel"""
        print("📊 טוען דאטה...")
        self.df = pd.read_excel(self.excel_path)
        self.df['קוד דגם'] = self.df['קוד דגם'].astype(str)

        # בניית מסד נתונים ישיר
        for _, row in self.df.iterrows():
            self.vin_database[row['מספר שלדה']] = {
                'code': row['קוד דגם'],
                'desc': row['תיאור דגם']
            }

            # מיפוי קוד דגם -> תיאור (לקחת את הראשון שנמצא)
            if row['קוד דגם'] not in self.code_to_desc:
                self.code_to_desc[row['קוד דגם']] = row['תיאור דגם']

        print(f"   ✓ נטענו {len(self.vin_database)} שלדות")
        print(f"   ✓ {len(self.code_to_desc)} קודי דגם ייחודיים")

    def train_model(self):
        """אימון מודל ML"""
        if self.df is None:
            raise ValueError("יש לטעון דאטה תחילה")

        print("\n🧠 אימון מודל ML...")

        # חילוץ features
        X = np.array([self._extract_features(vin) for vin in self.df['מספר שלדה']])
        y = self.df['קוד דגם'].values

        # אימון
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=30,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.model.fit(X, y)

        print("   ✓ מודל אומן בהצלחה!")

    def _extract_features(self, vin: str) -> list:
        """מחלץ 17 features מ-VIN"""
        if pd.isna(vin) or len(str(vin)) < 17:
            return [0] * 17

        vin_str = str(vin)[:17]
        features = []

        for char in vin_str:
            if char.isdigit():
                features.append(int(char))
            elif char.isalpha():
                features.append(ord(char.upper()) - ord('A') + 10)
            else:
                features.append(0)

        return features

    def decode_vin(self, vin: str) -> Dict:
        """
        מזהה קוד דגם ותיאור מ-VIN
        מחזיר: dict עם code, description, confidence, source
        """
        # שלב 1: Exact Match
        if vin in self.vin_database:
            return {
                'vin': vin,
                'model_code': self.vin_database[vin]['code'],
                'model_description': self.vin_database[vin]['desc'],
                'confidence': 100,
                'source': 'exact_match'
            }

        # שלב 2: Pattern Matching (VINs דומים)
        similar = self._find_similar_vins(vin)
        if similar:
            return {
                'vin': vin,
                'model_code': similar['code'],
                'model_description': similar['desc'],
                'confidence': similar['confidence'],
                'source': 'pattern_matching'
            }

        # שלב 3: ML Prediction
        if self.model:
            features = np.array([self._extract_features(vin)])
            predicted_code = self.model.predict(features)[0]
            predicted_proba = self.model.predict_proba(features)[0]
            confidence = max(predicted_proba) * 100

            # חיפוש תיאור לפי הקוד המנובא - עם fallback!
            description = self.code_to_desc.get(predicted_code, "Unknown Model")

            return {
                'vin': vin,
                'model_code': predicted_code,
                'model_description': description,
                'confidence': round(confidence, 1),
                'source': 'ml_prediction'
            }

        # שלב 4: Fallback
        return {
            'vin': vin,
            'model_code': 'UNKNOWN',
            'model_description': 'Unknown Model',
            'confidence': 0,
            'source': 'failed'
        }

    def _find_similar_vins(self, vin: str, threshold: int = 14) -> Optional[Dict]:
        """
        מחפש VINs דומים (לפחות threshold תווים זהים באותם מיקומים)
        """
        if len(vin) < 17:
            return None

        best_match = None
        best_similarity = 0

        for known_vin, data in self.vin_database.items():
            if len(known_vin) < 17:
                continue

            # חישוב דמיון
            similarity = sum(1 for i in range(17) if i < len(vin) and i < len(known_vin) and vin[i] == known_vin[i])

            if similarity >= threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = data

        if best_match:
            confidence = (best_similarity / 17) * 100
            return {
                'code': best_match['code'],
                'desc': best_match['desc'],
                'confidence': round(confidence, 1)
            }

        return None

    def save_model(self, path: str = "smart_vin_decoder.pkl"):
        """שמירת המודל"""
        data = {
            'model': self.model,
            'database': self.vin_database,
            'code_to_desc': self.code_to_desc  # ← חדש! שומר גם את המיפוי
        }
        with open(path, 'wb') as f:
            pickle.dump(data, f)
        print(f"✅ נשמר: {path}")

    def load_model(self, path: str = "smart_vin_decoder.pkl"):
        """טעינת מודל שמור"""
        if os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
            self.model = data['model']
            self.vin_database = data['database']
            self.code_to_desc = data.get('code_to_desc', {})  # ← חדש! טוען את המיפוי
            print(f"✅ נטען: {path}")
        else:
            print(f"⚠️ קובץ לא נמצא: {path}")


# דוגמה לשימוש
if __name__ == "__main__":
    # יצירת המערכת
    decoder = SmartVinDecoder("VINS-and-Model-Descriptions-including-Model-Code-all-data.xlsx")

    # אימון המודל (פעם אחת)
    decoder.train_model()

    # שמירה
    decoder.save_model()

    # בדיקה
    test_vins = [
        "WP1ZZZXA6SL078845",  # VIN חדש
        "WP1ZZZXAXSL078833",  # VIN קיים
    ]

    print("\n" + "="*70)
    print("🔍 בדיקת VINs")
    print("="*70)

    for vin in test_vins:
        result = decoder.decode_vin(vin)
        print(f"\nVIN: {result['vin']}")
        print(f"   קוד דגם: {result['model_code']}")
        print(f"   תיאור: {result['model_description']}")
        print(f"   Confidence: {result['confidence']}%")
        print(f"   Source: {result['source']}")
