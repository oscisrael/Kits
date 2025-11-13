"""
step1_detect_model.py
Step 1: Detect model information from VIN using SmartVinDecoder

INPUT: VIN (string, 17 characters)
OUTPUT: Dict with model_code, model_description, model_family, year, confidence
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# Add foundation_codes to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))

from SmartVinDecoder import SmartVinDecoder

# Global decoder instance (loaded once)
_decoder = None


def _get_decoder() -> SmartVinDecoder:
    """
    Get or initialize the SmartVinDecoder instance (singleton pattern)

    Returns:
        SmartVinDecoder instance
    """
    global _decoder

    if _decoder is None:
        print("Initializing SmartVinDecoder...")
        _decoder = SmartVinDecoder()

        # Try to load pre-trained model
        model_path = Path(__file__).parent.parent / 'smart_vin_decoder.pkl'
        if model_path.exists():
            _decoder.load_model(str(model_path))
            print(f"✅ Loaded model from: {model_path}")
        else:
            print(f"⚠️  Pre-trained model not found at: {model_path}")
            print("   The decoder will work with limited functionality")

    return _decoder


def detect_model_from_vin(vin: str) -> Optional[Dict]:
    """
    Detect model information from VIN

    Args:
        vin: Vehicle VIN number (17 characters)

    Returns:
        Dict with keys:
            - vin: Original VIN
            - model_code: Model code (e.g., '97ADS1')
            - model_description: Full description (e.g., 'Panamera GTS')
            - model_family: Model family (e.g., 'Panamera')
            - year: Manufacturing year (e.g., 2023)
            - confidence: Confidence score (0-100)
            - source: Detection source ('exact_match', 'pattern_matching', 'ml_prediction', 'failed')

        Returns None if detection fails

    Example:
        >>> result = detect_model_from_vin("WP0ZZZ976PL135008")
        >>> print(result)
        {
            'vin': 'WP0ZZZ976PL135008',
            'model_code': '97ADS1',
            'model_description': 'Panamera GTS',
            'model_family': 'Panamera',
            'year': 2023,
            'confidence': 100,
            'source': 'exact_match'
        }
    """
    # Validate VIN
    if not vin or len(vin) != 17:
        print(f"❌ Invalid VIN length: {len(vin) if vin else 0} (expected 17)")
        return None

    print(f"▶️  Decoding VIN: {vin}")

    # Get decoder instance
    decoder = _get_decoder()

    # Decode VIN
    try:
        result = decoder.decode_vin(vin)

        if not result:
            print(f"❌ Decoder returned empty result for VIN: {vin}")
            return None

        # Validate result
        if result.get('confidence', 0) == 0:
            print(f"❌ Failed to decode VIN: {vin}")
            print(f"   Source: {result.get('source', 'unknown')}")
            return None

        # Print detection details
        print(f"✅ VIN decoded successfully:")
        print(f"   Model Code: {result.get('model_code')}")
        print(f"   Description: {result.get('model_description')}")
        print(f"   Family: {result.get('model_family')}")
        print(f"   Year: {result.get('year')}")
        print(f"   Confidence: {result.get('confidence')}%")
        print(f"   Source: {result.get('source')}")

        return result

    except Exception as e:
        print(f"❌ Error during VIN decoding: {e}")
        import traceback
        traceback.print_exc()
        return None


# Test function (for standalone testing)
def _test():
    """Test the step with sample VINs"""
    test_vins = [
        "WP0ZZZ976PL135008",  # Panamera GTS
        "WP1ZZZXA6SL078845",  # Macan
        "WP0ZZZYA3SL047443",  # Panamera 4 E-Hybrid
    ]

    print("=" * 70)
    print("Testing Step 1: Model Detection")
    print("=" * 70)

    for vin in test_vins:
        print(f"\n{'=' * 70}")
        result = detect_model_from_vin(vin)

        if result:
            print(f"\n✅ Success: {result['model_description']}")
        else:
            print(f"\n❌ Failed to decode: {vin}")


if __name__ == "__main__":
    _test()
