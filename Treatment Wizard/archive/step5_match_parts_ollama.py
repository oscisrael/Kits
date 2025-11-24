"""
step5_match_parts.py

Step 5: Match classified treatment lines (PARTS) to PET part numbers

INPUT:
- classified_data (from step 3)
- pet_data (from step 4)
- model_description (for oil capacity lookup)

OUTPUT: Final matched data with part numbers for each service

Features:
- OLLAMA-powered intelligent matching between service lines and PET parts
- Special rules for specific models (Panamera/Cayenne oil filter add-ons)
- Oil capacity calculation from model
- Original PDF headers as keys
- Sorted by interval with time-dependent last
- Caching to avoid redundant LLM calls
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import re
from collections import OrderedDict
import requests

# Add foundation_codes to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))
from oil_capacity_config import get_oil_capacity

# ============================================================================
# OLLAMA Configuration
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

# Global cache for OLLAMA responses (per model run)
_ollama_cache = {}

# Shorter, more focused system prompt
SYSTEM_PROMPT = """You are a Porsche PET parts matcher.
Match the SERVICE LINE to the best PET part.

RULES:
- Return ONLY the part number
- If unsure, return "NO_MATCH"

KEY KNOWLEDGE:
- FFL-8/FFL-4 = PDK oil
- 75W90 = Differential oil
- Mobil 1 = Engine oil
- DOT 4 = Brake fluid
- Filter "with seal" includes sealing ring
"""


def query_ollama(prompt: str, context: str = "") -> str:
    """
    Query OLLAMA with a prompt

    Args:
        prompt: The user prompt
        context: Additional context (optional)

    Returns:
        OLLAMA response text
    """
    # Check cache first
    cache_key = f"{prompt}|{context}"
    if cache_key in _ollama_cache:
        print(f"  💾 Cache hit!")
        return _ollama_cache[cache_key]

    full_prompt = f"{SYSTEM_PROMPT}\n\n{context}\n\n{prompt}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 50  # Limit output tokens for faster response
        }
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)  # ✅ Increased to 120s
        response.raise_for_status()
        result = response.json()
        answer = result.get("response", "").strip()

        # Cache the result
        _ollama_cache[cache_key] = answer

        return answer

    except requests.exceptions.Timeout:
        print(f"  ⚠️ OLLAMA timeout (120s) - try again or reduce PET list")
        return "NO_MATCH"

    except requests.exceptions.RequestException as e:
        print(f"  ⚠️ OLLAMA request failed: {e}")
        return "NO_MATCH"

    except Exception as e:
        print(f"  ⚠️ Unexpected error: {e}")
        return "NO_MATCH"


def simple_keyword_filter(service_line: str, pet_rows: List[Dict], top_n: int = 10) -> List[Dict]:
    """
    Pre-filter PET parts using simple keyword matching to reduce candidates

    Args:
        service_line: Service line text
        pet_rows: All PET parts
        top_n: Number of top candidates to return

    Returns:
        Filtered list of PET parts (max top_n items)
    """
    service_lower = service_line.lower()

    # Keywords to look for
    keywords = []

    # Extract important keywords
    if "engine oil" in service_lower or "fill in" in service_lower:
        keywords = ["oil", "mobil", "engine", "ffl", "v04"]
    elif "oil filter" in service_lower:
        keywords = ["filter", "oil", "cartridge"]
    elif "brake" in service_lower:
        keywords = ["brake", "fluid", "dot"]
    elif "air filter" in service_lower:
        keywords = ["air", "filter"]
    elif "cabin filter" in service_lower or "pollen" in service_lower:
        keywords = ["cabin", "pollen", "filter"]
    elif "spark plug" in service_lower:
        keywords = ["spark", "plug"]
    elif "coolant" in service_lower:
        keywords = ["coolant", "antifreeze"]
    elif "differential" in service_lower:
        keywords = ["differential", "75w90", "transmission"]
    elif "pdk" in service_lower or "transmission" in service_lower:
        keywords = ["transmission", "ffl", "pdk", "gearbox"]
    else:
        # Generic keywords
        keywords = service_lower.split()[:3]

    # Score each PET part
    scored_parts = []
    for pet_row in pet_rows:
        desc = pet_row.get('Description', '').lower()
        remark = pet_row.get('Remark', '').lower()
        combined = f"{desc} {remark}"

        score = sum(1 for kw in keywords if kw in combined)

        if score > 0:
            scored_parts.append((score, pet_row))

    # Sort by score and return top N
    scored_parts.sort(key=lambda x: x[0], reverse=True)

    return [part for score, part in scored_parts[:top_n]]


def best_pet_match_with_ollama(service_line: str, pet_rows: List[Dict],
                               model_name: str) -> List[Dict]:
    """
    Find best matching PET parts for a service line using OLLAMA

    Args:
        service_line: Service line text (e.g., "Fill in engine oil")
        pet_rows: List of PET parts
        model_name: Model name for context

    Returns:
        List of matched parts (usually 1 item)
    """
    if not pet_rows:
        return []

    # ✅ Pre-filter to reduce candidates
    filtered_pets = simple_keyword_filter(service_line, pet_rows, top_n=10)

    if not filtered_pets:
        print(f"  ⚠️ No candidates after pre-filter")
        filtered_pets = pet_rows[:10]  # Fallback to first 10

    print(f"  📉 Filtered from {len(pet_rows)} to {len(filtered_pets)} candidates")

    # Build context with filtered PET parts only
    pet_context = "Available PET parts:\n"
    for idx, pet_row in enumerate(filtered_pets):
        part_num = pet_row.get('Part Number', '')
        desc = pet_row.get('Description', '')
        remark = pet_row.get('Remark', '')

        pet_context += f"{idx + 1}. {part_num}: {desc}"
        if remark:
            pet_context += f" ({remark})"
        pet_context += "\n"

    # Build prompt (shorter)
    prompt = f"""SERVICE: "{service_line}"
MODEL: {model_name}

Return ONLY the part number of the best match."""

    # Query OLLAMA
    print(f"  🤖 Querying OLLAMA for: {service_line[:50]}...")
    answer = query_ollama(prompt, pet_context)

    # Parse answer
    if "NO_MATCH" in answer.upper():
        print(f"  ⚠️ OLLAMA: No match found")
        return []

    # Extract part number from answer
    matched_part_num = None

    # Try to find part number in answer
    for pet_row in filtered_pets:
        part_num = pet_row.get('Part Number', '')
        # Normalize spaces/dashes
        part_num_normalized = part_num.replace(' ', '').replace('-', '')
        answer_normalized = answer.replace(' ', '').replace('-', '')

        if part_num_normalized.lower() in answer_normalized.lower():
            matched_part_num = part_num
            break

    if not matched_part_num:
        print(f"  ⚠️ OLLAMA returned unclear answer: {answer[:100]}")
        return []

    # Find the full part data
    for pet_row in filtered_pets:
        if pet_row.get('Part Number', '') == matched_part_num:
            print(f"  ✅ OLLAMA matched: {matched_part_num}")
            return [{
                'part_number': matched_part_num,
                'description': pet_row.get('Description', ''),
                'remark': pet_row.get('Remark', ''),
                'quantity': pet_row.get('Qty', '1'),
                'score': 1.0
            }]

    return []


def apply_special_rules(service_line: str, model_name: str,
                       matches: List[Dict]) -> List[Dict]:
    """
    Apply special matching rules based on model and service type

    Args:
        service_line: Service line text
        model_name: Model name
        matches: Initial matches

    Returns:
        List of matched parts (with additions for oil filter case)
    """
    service_lower = service_line.lower()
    model_lower = model_name.lower()

    # Check if Panamera or Cayenne
    is_panamera = 'panamera' in model_lower
    is_cayenne = 'cayenne' in model_lower

    # Rule 1: Change oil filter - add drain plug and washer (Panamera/Cayenne only)
    if (is_panamera or is_cayenne) and "change oil filter" in service_lower:
        if matches:
            result = [matches[0]]

            # Add drain plug
            result.append({
                'part_number': 'PAF911679',
                'description': 'Oil drain plug',
                'remark': 'פקק לאגן שמן',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True
            })

            # Add drain washer
            result.append({
                'part_number': 'PAF013849',
                'description': 'Oil drain washer',
                'remark': 'שייבה לאגן שמן',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True
            })

            print(f"  🔧 Added oil drain plug + washer for Panamera/Cayenne")
            return result
        else:
            return matches

    # Rule 2: Fill in engine oil - prefer X version based on model
    if 'fill in' in service_lower and 'engine oil' in service_lower:
        if matches:
            # Extract X versions
            x_versions = []
            for match in matches:
                desc = match.get('description', '')
                x_ver = extract_x_version(desc)
                if x_ver > 0:
                    x_versions.append((x_ver, match))

            if x_versions:
                # Sort by X version
                x_versions.sort(key=lambda x: x[0], reverse=True)

                # Prefer highest X version for performance models
                if 'gts' in model_lower or 'turbo' in model_lower:
                    return [x_versions[0][1]]  # Highest X
                else:
                    return [x_versions[-1][1]]  # Lowest X

    # Default: return matches as-is
    return matches[:1] if matches else []


def match_parts_to_services(classified_data: Dict, pet_data: List[Dict],
                            model_description: str) -> Optional[Dict]:
    """
    Match PARTS lines from classified treatments to PET part numbers using OLLAMA

    Args:
        classified_data: Classified treatment data from step 3
        pet_data: PET part data from step 4
        model_description: Model description for oil capacity lookup

    Returns:
        Matched data with original headers
    """
    if not classified_data or "services" not in classified_data:
        print("❌ Invalid classified data format")
        return None

    if not pet_data:
        print("❌ No PET data provided")
        return None

    print(f"🤖 Matching parts with OLLAMA (model: {OLLAMA_MODEL})")
    print(f"Model: {model_description}")

    # Get oil capacity
    oil_capacity = get_oil_capacity(model_description)
    if oil_capacity:
        print(f"✅ Oil capacity: {oil_capacity}L")
    else:
        print("⚠️ No oil capacity defined for this model")
        oil_capacity = None

    # Prepare output
    matched_data = {}
    services = classified_data["services"]
    total_parts = 0
    matched_parts = 0
    not_found = 0

    # Process each service
    for service_key, service_data in services.items():
        original_header = service_data.get("original_header", service_key)
        print(f"\n📋 Processing {service_key} ({original_header})...")

        items = service_data.get("items", [])
        if not items:
            print(f"  ⚠️ No items found for {service_key}")
            continue

        model_name = model_description

        service_output = {
            "model": model_name,
            "oil_capacity": oil_capacity,
            "matched_parts": []
        }

        # Process each item
        for item in items:
            text = item.get("text", "")
            category = item.get("category", "")
            confidence = item.get("confidence", 0.5)

            # Only match PARTS category
            if category != "PARTS":
                continue

            total_parts += 1

            # Find matches with OLLAMA
            matches = best_pet_match_with_ollama(text, pet_data, model_name)

            # Apply special rules
            matches = apply_special_rules(text, model_name, matches)

            # Handle oil quantity
            quantity = "1"
            if "engine oil" in text.lower() or "fill in" in text.lower():
                if oil_capacity:
                    quantity = str(oil_capacity)

            # Build output
            if matches:
                for match in matches:
                    is_addon = match.get('is_addon', False)

                    if is_addon:
                        service_line_text = f"{text} ({match.get('remark', '')})"
                    else:
                        service_line_text = text

                    service_output["matched_parts"].append({
                        "SERVICE LINE": service_line_text,
                        "CATEGORY": category,
                        "CONFIDENCE": confidence,
                        "PART NUMBER": match.get('part_number', 'NOT FOUND'),
                        "DESCRIPTION": match.get('description', ''),
                        "REMARK": match.get('remark', ''),
                        "QUANTITY": quantity if "oil" in text.lower() and not is_addon else match.get('quantity', '1'),
                        "MATCH SCORE": round(match.get('score', 0), 3)
                    })

                matched_parts += len(matches)
                print(f"  ✅ {text[:40]}... → {len(matches)} part(s)")
            else:
                service_output["matched_parts"].append({
                    "SERVICE LINE": text,
                    "CATEGORY": category,
                    "CONFIDENCE": confidence,
                    "PART NUMBER": "NOT FOUND",
                    "DESCRIPTION": "",
                    "REMARK": "",
                    "QUANTITY": quantity,
                    "MATCH SCORE": 0.0
                })
                not_found += 1
                print(f"  ⚠️ {text[:40]}... → NOT FOUND")

        matched_data[original_header] = service_output

    print(f"\n✅ Matching completed:")
    print(f"  Total PARTS lines: {total_parts}")
    print(f"  Successfully matched: {matched_parts}")
    print(f"  Not found: {not_found}")
    print(f"  OLLAMA cache size: {len(_ollama_cache)}")

    if not_found > 0:
        print(f"\n⚠️ Warning: {not_found} parts could not be matched")

    # Sort services by interval
    sorted_matched_data = sort_services_by_interval(matched_data)

    return sorted_matched_data


def _test():
    """Test the step with OLLAMA"""
    print("="*70)
    print("Testing Step 5: Parts Matching with OLLAMA")
    print("="*70)

    # Test OLLAMA connection
    try:
        test_response = query_ollama("Test connection. Reply with OK.")
        print(f"\n✅ OLLAMA connection test: {test_response[:50]}")
    except Exception as e:
        print(f"\n❌ OLLAMA connection failed: {e}")
        return

    # Sample test would go here
    print("\n✅ OLLAMA is ready for use!")


if __name__ == "__main__":
    _test()
