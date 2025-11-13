"""
oil_capacity_config.py
Smart oil capacity matching with fuzzy model name recognition

Source: Official Porsche maintenance documentation
"""

from typing import Optional
import re


# Official oil capacity table (source of truth)
OIL_CAPACITY_TABLE = {
    "Panamera": {
        "Panamera GTS": 9.5,
        "Panamera Turbo": 9.5,
        "Panamera Turbo S": 9.5,
        "Panamera Turbo S Hybrid": 9.0,
        "Panamera 4S": 7.2,
        "Panamera": 7.2,
        "Panamera 4": 7.2,
        "Panamera 4 Hybrid": 6.8,
        "Panamera 4S Hybrid": 6.8,
    },
    "Macan": {
        "Macan GTS": 8.0,
        "Macan Turbo": 8.0,
        "Macan S": 7.5,
        "Macan": 7.5,
    },
    "Cayenne": {
        "Cayenne Turbo": 9.0,
        "Cayenne GTS": 8.5,
        "Cayenne S": 8.0,
        "Cayenne": 8.0,
    },
    # Add more families as needed
}


# Words to ignore in model descriptions (design variants, generations, etc.)
IGNORE_WORDS = {
    # Generations
    "g1", "g2", "g3", "g4",

    # Design variants
    "st", "sport", "turismo", "executive", "platinum", "edition",

    # Prefixes
    "e-", "e",

    # Other common additions
    "new", "plus", "exclusive", "design"
}


# Word equivalences (normalize before matching)
WORD_EQUIVALENCES = {
    "e-hybrid": "hybrid",
    "ehybrid": "hybrid",
    "e hybrid": "hybrid",
}


def normalize_model_name(model_name: str) -> str:
    """
    Normalize model name for matching

    Steps:
    1. Convert to lowercase
    2. Apply word equivalences (E-Hybrid → Hybrid)
    3. Remove ignored words (G3, ST, etc.)
    4. Remove duplicate words
    5. Clean up spacing

    Args:
        model_name: Raw model name (e.g., "G3 Panamera 4 E-Hybrid Platinum")

    Returns:
        Normalized name (e.g., "panamera 4 hybrid")

    Examples:
        >>> normalize_model_name("G3 Panamera")
        'panamera'

        >>> normalize_model_name("Panamera GTS Sport Turismo")
        'panamera gts'

        >>> normalize_model_name("Panamera 4 E-Hybrid Platinum")
        'panamera 4 hybrid'
    """
    # Convert to lowercase
    name = model_name.lower().strip()

    # Apply word equivalences
    for old_word, new_word in WORD_EQUIVALENCES.items():
        name = name.replace(old_word, new_word)

    # Split into words
    words = re.split(r'[\s\-/]+', name)

    # Remove ignored words and clean
    filtered_words = []
    for word in words:
        word_clean = word.strip()
        if word_clean and word_clean not in IGNORE_WORDS:
            filtered_words.append(word_clean)

    # Remove duplicates while preserving order
    seen = set()
    unique_words = []
    for word in filtered_words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)

    return ' '.join(unique_words)


def find_best_match(normalized_input: str, table_entries: dict) -> Optional[str]:
    """
    Find the longest matching entry from the table

    Args:
        normalized_input: Normalized input model name (e.g., "panamera turbo s")
        table_entries: Dict of {model_name: capacity} from table

    Returns:
        Best matching model name from table, or None

    Algorithm:
        For each table entry, check if all its words exist in the input (in order).
        Return the entry with the most matching words.

    Examples:
        Input: "panamera turbo s executive"
        Table: ["Panamera", "Panamera Turbo", "Panamera Turbo S"]

        Matches:
        - "Panamera" → 1 word match ✓
        - "Panamera Turbo" → 2 words match ✓
        - "Panamera Turbo S" → 3 words match ✓✓✓ (longest!)

        Result: "Panamera Turbo S"
    """
    input_words = normalized_input.split()

    best_match = None
    best_match_length = 0

    for table_model in table_entries.keys():
        table_normalized = normalize_model_name(table_model)
        table_words = table_normalized.split()

        # Check if all table words exist in input (in order)
        match_found = True
        input_idx = 0

        for table_word in table_words:
            # Find table_word in remaining input words
            found = False
            while input_idx < len(input_words):
                if input_words[input_idx] == table_word:
                    found = True
                    input_idx += 1
                    break
                input_idx += 1

            if not found:
                match_found = False
                break

        # If match found and it's longer than previous best, update
        if match_found and len(table_words) > best_match_length:
            best_match = table_model
            best_match_length = len(table_words)

    return best_match


def get_oil_capacity(model_description: str) -> Optional[float]:
    """
    Get oil capacity for a given model using smart fuzzy matching

    Args:
        model_description: Full model description (e.g., "G3 Panamera 4 E-Hybrid Platinum")

    Returns:
        Oil capacity in liters, or None if no match found

    Examples:
        >>> get_oil_capacity("G3 Panamera")
        7.2

        >>> get_oil_capacity("Panamera GTS Sport Turismo")
        9.5

        >>> get_oil_capacity("Panamera 4 E-Hybrid Platinum")
        6.8

        >>> get_oil_capacity("Panamera Turbo S Executive")
        9.5
    """
    if not model_description:
        return None

    # Normalize input
    normalized_input = normalize_model_name(model_description)

    # Determine model family (first word usually)
    words = normalized_input.split()
    if not words:
        return None

    family = words[0].capitalize()  # "panamera" → "Panamera"

    # Get table for this family
    if family not in OIL_CAPACITY_TABLE:
        print(f"⚠️  Unknown model family: {family}")
        return None

    table_entries = OIL_CAPACITY_TABLE[family]

    # Find best match
    best_match = find_best_match(normalized_input, table_entries)

    if best_match:
        capacity = table_entries[best_match]
        print(f"✅ Matched '{model_description}' → '{best_match}' → {capacity}L")
        return capacity
    else:
        print(f"⚠️  No oil capacity match found for: {model_description}")
        return None


# Test function
def _test():
    """Test the smart matching"""
    test_cases = [
        ("G3 Panamera", 7.2),
        ("Panamera GTS Sport Turismo", 9.5),
        ("Panamera ST Turbo", 9.5),
        ("Panamera 4 E-Hybrid Platinum", 6.8),
        ("Panamera Turbo S", 9.5),
        ("Panamera Turbo S Hybrid Executive", 9.0),
        ("Panamera 4S", 7.2),
        ("Macan GTS", 8.0),
        ("Cayenne Turbo", 9.0),
    ]

    print("="*70)
    print("Testing Smart Oil Capacity Matching")
    print("="*70)

    passed = 0
    failed = 0

    for model_desc, expected_capacity in test_cases:
        result = get_oil_capacity(model_desc)

        if result == expected_capacity:
            print(f"✅ PASS: {model_desc} → {result}L")
            passed += 1
        else:
            print(f"❌ FAIL: {model_desc} → Expected {expected_capacity}L, got {result}L")
            failed += 1

    print("\n" + "="*70)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*70)


if __name__ == "__main__":
    _test()
