"""
step3_classify.py

Step 3: Classify treatment lines into PARTS vs INSPECTION/OPERATIONS

INPUT: treatments_data (Dict from step 2 with services)
OUTPUT: classified_data with each item marked as PARTS or INSPECTION

Features:
- Uses OpenAI ChatGPT API for classification
- Global classification cache to avoid re-classifying same items
- Validates OpenAI API key before starting
- Only classifies unique items per service
- Supports original PDF headers
- Force certain items to INSPECTION (e.g., "drain engine oil")
"""

import sys
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import json
from collections import defaultdict
from datetime import datetime
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# Add foundation_codes to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))

# Cache file location
CACHE_FILE = Path(__file__).parent.parent / 'foundation_codes' / 'classification_cache.json'

api_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(
    api_key=api_key
)

def check_openai_configured() -> bool:
    """
    Check if OpenAI API key is configured

    Returns:
        True if API key is configured, False otherwise
    """
    api_key = "***REMOVED***"

    if not api_key:
        print("❌ OpenAI API key is not configured!")
        print("   Please set OPENAI_API_KEY environment variable")
        print("   Example (Windows): set OPENAI_API_KEY=your-key-here")
        print("   Example (Linux/Mac): export OPENAI_API_KEY=your-key-here")
        return False

    print("✅ OpenAI API is configured")
    return True

def load_cache() -> Dict:
    """
    Load classification cache from file

    Returns:
        Dict with cached classifications
    """
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            print(f"✅ Loaded cache with {len(cache)} entries from: {CACHE_FILE}")
            return cache
        except Exception as e:
            print(f"⚠️ Failed to load cache: {e}")
            return {}
    else:
        print(f"ℹ️ No cache file found, starting fresh")
        return {}

def save_cache(cache: Dict):
    """
    Save classification cache to file

    Args:
        cache: Dict with classifications to save
    """
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        print(f"✅ Saved cache with {len(cache)} entries to: {CACHE_FILE}")
    except Exception as e:
        print(f"⚠️ Failed to save cache: {e}")

def normalize_text(text: str) -> str:
    """
    Normalize text for cache key

    Args:
        text: Original text

    Returns:
        Normalized lowercase text
    """
    return text.lower().strip()

def should_force_inspection(text: str) -> bool:
    """
    Check if a line should always be classified as INSPECTION

    Args:
        text: Service line text

    Returns:
        True if should be forced to INSPECTION
    """
    text_lower = text.lower()

    # List of keywords that should always be INSPECTION
    force_inspection_keywords = [
        "drain engine oil",
        "drain oil",
        "lubricate",
        "grease",
        "stickers",
        "Warning sticker",
        "replace missing stickers",
        "All-wheel final drive: change oil",
        "All-wheel",

    ]

    for keyword in force_inspection_keywords:
        if keyword in text_lower:
            return True

    return False

def classify_with_chatgpt(item: str, num_runs: int = 3) -> Tuple[str, float]:
    """
    Classify a single item using ChatGPT with consistency-based confidence

    Args:
        item: Text to classify
        num_runs: Number of times to run classification for consistency

    Returns:
        Tuple of (category, confidence)
        - category: "PARTS" or "INSPECTION"
        - confidence: 0.0 to 1.0
    """
    prompt = f"""Task: Classify the following car-service line into one of two categories:
- PARTS: The line requires adding, replacing, filling, changing, renewing, installing, or topping up any physical part or fluid.
- INSPECTION: The line describes checking, inspecting, testing, measuring, or examining something without necessarily replacing or adding anything.

Examples:
- "Fill in engine oil" → PARTS
- "Change oil filter" → PARTS
- "Check brake pads" → INSPECTION
- "Test battery voltage" → INSPECTION

Service line: "{item}"

Respond with ONLY one word: either PARTS or INSPECTION."""

    results = []

    for _ in range(num_runs):
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",  # או "gpt-4" למודל מתקדם יותר
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # נמוך יותר לעקביות
                max_tokens=10
            )

            answer = response.choices[0].message.content.strip().upper()

            # Extract PARTS or INSPECTION from response
            if "PARTS" in answer:
                results.append("PARTS")
            elif "INSPECTION" in answer:
                results.append("INSPECTION")

        except Exception as e:
            print(f"   ⚠️ ChatGPT request failed: {e}")
            continue

    # If all attempts failed, default to INSPECTION
    if not results:
        print(f"   ⚠️ All classification attempts failed for: {item}")
        return ("INSPECTION", 0.5)

    # Calculate confidence based on consistency
    parts_count = results.count("PARTS")
    inspection_count = results.count("INSPECTION")

    if parts_count > inspection_count:
        category = "PARTS"
        confidence = parts_count / len(results)
    else:
        category = "INSPECTION"
        confidence = inspection_count / len(results)

    return (category, confidence)

def classify_unique_items(items: List[str], cache: Dict) -> Dict[str, Tuple[str, float]]:
    """
    Classify unique items, using cache when available

    Args:
        items: List of items to classify
        cache: Classification cache

    Returns:
        Dict mapping each unique item to (category, confidence)
    """
    unique_items = list(set(items))
    results = {}

    cache_hits = 0
    api_calls = 0
    forced_rules = 0

    for item in unique_items:
        normalized = normalize_text(item)

        # Check for forced INSPECTION rules
        if should_force_inspection(item):
            results[item] = ("INSPECTION", 1.0)
            # Update cache with forced rule
            cache[normalized] = {
                'category': 'INSPECTION',
                'confidence': 1.0,
                'classified_at': datetime.now().isoformat(),
                'forced_rule': True
            }
            forced_rules += 1
            print(f"   [FORCED] {item[:50]}... → INSPECTION (forced rule)")
            continue

        # Check cache first
        if normalized in cache:
            category = cache[normalized].get('category', 'INSPECTION')
            confidence = cache[normalized].get('confidence', 0.5)
            results[item] = (category, confidence)
            cache_hits += 1
        else:
            # Classify with ChatGPT
            category, confidence = classify_with_chatgpt(item, num_runs=3)
            results[item] = (category, confidence)

            # Update cache
            cache[normalized] = {
                'category': category,
                'confidence': confidence,
                'classified_at': datetime.now().isoformat()
            }

            api_calls += 1
            print(f"   [{api_calls}/{len(unique_items) - cache_hits - forced_rules}] {item[:50]}... → {category} ({confidence:.2f})")

    print(f"   ✅ Cache hits: {cache_hits}/{len(unique_items)}")
    print(f"   🤖 ChatGPT classifications: {api_calls}/{len(unique_items)}")
    if forced_rules > 0:
        print(f"   🔒 Forced rules: {forced_rules}/{len(unique_items)}")

    return results

def classify_treatment_lines(treatments_data: Dict, model_description: str) -> Optional[Dict]:
    """
    Classify each treatment line as PARTS or INSPECTION

    Args:
        treatments_data: Data from step 2 (treatments extraction)
        model_description: Model description for context

    Returns:
        Classified data with original headers:
        {
            "metadata": {...},
            "services": {
                "service_15000": {
                    "original_header": "Every 15 tkm/10 tmls or 1 year",
                    "items": [
                        {
                            "text": "Fill in engine oil",
                            "category": "PARTS",
                            "confidence": 0.95,
                            "model_name": "Panamera GTS"
                        },
                        ...
                    ]
                },
                ...
            }
        }

        Returns None if classification fails
    """
    if not treatments_data or "services" not in treatments_data:
        print("❌ Invalid treatments data format")
        return None

    print(f"Classifying treatment lines for model: {model_description}")

    # Check OpenAI API configuration
    if not check_openai_configured():
        return None

    # Load cache
    cache = load_cache()

    # Prepare output structure
    classified_data = {
        "metadata": {
            **treatments_data.get("metadata", {}),
            "model_description": model_description,
            "classification_date": datetime.now().isoformat()
        },
        "services": {}
    }

    services = treatments_data["services"]
    total_items = 0
    parts_count = 0
    inspection_count = 0

    # Process each service
    for service_key, service_data in services.items():
        # Extract original header and items based on format
        if isinstance(service_data, dict) and "items" in service_data:
            # New format with original_header (from updated step 2)
            original_header = service_data.get("original_header", service_key)
            items_dict = service_data.get("items", {})
        else:
            # Old format for backward compatibility
            original_header = service_key
            items_dict = service_data

        print(f"\n📋 Processing {service_key}...")
        if original_header != service_key:
            print(f"   Original header: {original_header}")

        # Collect all items from all models in this service
        all_items = []
        for model_name, items in items_dict.items():
            all_items.extend(items)

        if not all_items:
            print(f"   ⚠️ No items found for {service_key}")
            continue

        print(f"   Found {len(all_items)} items ({len(set(all_items))} unique)")

        # Classify unique items
        classifications = classify_unique_items(all_items, cache)

        # Build output for this service
        classified_items = []
        for model_name, items in items_dict.items():
            for item in items:
                category, confidence = classifications.get(item, ("INSPECTION", 0.5))
                classified_items.append({
                    "text": item,
                    "category": category,
                    "confidence": confidence,
                    "model_name": model_name
                })

                total_items += 1
                if category == "PARTS":
                    parts_count += 1
                else:
                    inspection_count += 1

        # Use service_key (normalized) for internal tracking, but save original_header
        classified_data["services"][service_key] = {
            "original_header": original_header,
            "items": classified_items
        }

    # Save updated cache
    save_cache(cache)

    print(f"\n✅ Classification completed:")
    print(f"   Total items: {total_items}")
    print(f"   Parts: {parts_count}")
    print(f"   Inspections: {inspection_count}")

    return classified_data

# Test function (for standalone testing)
def _test():
    """Test the step with sample data"""
    # Sample input from step 2 (new format with original headers)
    sample_data = {
        "metadata": {
            "model_dir": "Cayenne:\\Users\\MayPery\\PycharmProjects\\Kits\\Cars\\Panamera\\97ADS1",
            "oil_maintenance_pdf": "Oil maintenance.pdf"
        },
        "services": {
            "service_15000": {
                "original_header": "Every 15 tkm/10 tmls or 1 year",
                "items": {
                    "Panamera": [
                        "Fill in engine oil",
                        "Change oil filter",
                        "Drain engine oil",
                        "Check brake pads",
                        "Test battery voltage"
                    ]
                }
            }
        }
    }

    print("=" * 70)
    print("Testing Step 3: Classification with ChatGPT")
    print("=" * 70)

    result = classify_treatment_lines(sample_data, "Panamera GTS")

    if result:
        print("\n✅ Classification successful!")
        # Save to test output
        output_path = Path("test_step3_output.json")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n📄 Test output saved to: {output_path}")
    else:
        print("\n❌ Classification failed")

if __name__ == "__main__":
    _test()
