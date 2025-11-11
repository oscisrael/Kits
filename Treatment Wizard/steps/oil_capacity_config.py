"""
oil_capacity_config.py

מילוני כמויות שמן עבור דגמי פורשה שונים
"""

# מילון עבור Panamera
PANAMERA_OIL_CAPACITY = {
    "Panamera GTS": 9.5,
    "Panamera Turbo": 9.5,
    "Panamera Turbo S Hybrid": 9.0,
    "Panamera Turbo S E-Hybrid": 9.0,  # ← הוספה!
    "Panamera 4S": 7.2,
    "Panamera": 7.2,
    "Panamera 4": 7.2,
    "Panamera 4 Hybrid": 6.8,
    "Panamera 4 E-Hybrid": 6.8,  # ← הוספה!
    "Panamera S Diesel": 9.0
}

# מילון עבור Cayenne (לדוגמה - להוסיף בעתיד)
CAYENNE_OIL_CAPACITY = {
    "Cayenne": 8.0,
    "Cayenne S": 8.5,
    "Cayenne Turbo": 9.0,
    # להוסיף דגמים נוספים...
}

# מילון עבור Macan (לדוגמה - להוסיף בעתיד)
MACAN_OIL_CAPACITY = {
    "Macan": 6.0,
    "Macan S": 6.5,
    "Macan Turbo": 7.0,
    # להוסיף דגמים נוספים...
}

# מילון מרכזי שמפנה לפי משפחת דגם
OIL_CAPACITY_REGISTRY = {
    "PANAMERA": PANAMERA_OIL_CAPACITY,
    "CAYENNE": CAYENNE_OIL_CAPACITY,
    "MACAN": MACAN_OIL_CAPACITY,
}


def get_oil_capacity(model_variant: str) -> float:
    """
    מחזיר את כמות השמן המתאימה לדגם

    Args:
        model_variant: שם הדגם (למשל "Panamera / S / GTS / Turbo")

    Returns:
        כמות השמן בליטרים, או None אם לא נמצא
    """
    model_upper = model_variant.upper()

    # זיהוי משפחת הדגם
    model_family = None
    for family_name in OIL_CAPACITY_REGISTRY.keys():
        if family_name in model_upper:
            model_family = family_name
            break

    if not model_family:
        return None

    # קבלת המילון המתאים
    capacity_dict = OIL_CAPACITY_REGISTRY[model_family]

    # רשימת עדיפויות - מהספציפי לכללי
    # חשוב! הסדר צריך להיות מהספציפי ביותר לכללי ביותר
    priority_order = [
        "TURBO S E-HYBRID",  # ← זה צריך להיות לפני "TURBO S HYBRID"!
        "TURBO S HYBRID",
        "GTS",
        "TURBO",
        "4S",
        "S DIESEL",
        "4 E-HYBRID",  # ← זה צריך להיות לפני "4 HYBRID"!
        "4 HYBRID",
        "E-HYBRID",
        "HYBRID",
        "4",
        "S",
    ]

    # חיפוש לפי סדר עדיפויות
    for priority_key in priority_order:
        if priority_key in model_upper:
            # מצא את המפתח המתאים במילון
            for dict_key, capacity in capacity_dict.items():
                dict_key_upper = dict_key.upper()
                if priority_key in dict_key_upper:
                    return capacity

    # אם לא נמצא התאמה ספציפית, נסה את הדגם הבסיסי
    for dict_key, capacity in capacity_dict.items():
        dict_key_upper = dict_key.upper()
        # בדיקה אם זה הדגם הבסיסי (בלי תוספות)
        if dict_key_upper == model_family and model_family in model_upper:
            return capacity

    return None


def add_oil_capacity(model_family: str, model_variant: str, capacity: float):
    """
    מוסיף או מעדכן כמות שמן עבור דגם

    Args:
        model_family: משפחת הדגם (למשל "PANAMERA")
        model_variant: שם הדגם הספציפי (למשל "Panamera GTS")
        capacity: כמות השמן בליטרים
    """
    model_family_upper = model_family.upper()

    if model_family_upper not in OIL_CAPACITY_REGISTRY:
        OIL_CAPACITY_REGISTRY[model_family_upper] = {}

    OIL_CAPACITY_REGISTRY[model_family_upper][model_variant] = capacity
    print(f"✅ נוסף/עודכן: {model_variant} → {capacity} ליטר במשפחת {model_family_upper}")
