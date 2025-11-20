"""
step5_match_parts.py - ENHANCED WITH OPENAI HYBRID MATCHING

Step 5: Match classified treatment lines (PARTS) to PET part numbers

Hybrid Approach:
1. Keywords matching (fast, free)
2. OpenAI Embeddings similarity (semantic, cached)
3. GPT-4o-mini explanations (for uncertain matches)

Updated rules:
1. Engine oil: Always prefer HIGHEST X version (X4 > X3 > X2)
2. Panamera/Cayenne oil filter: Must be "with seal" (NOT "complete")
3. Air cleaner filter: Engine air filter
4. Particle filter: Cabin/pollen/dust filter
5. Transfer gear: Transfer box gear oil
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import re
from collections import OrderedDict
import pickle
import numpy as np
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent / 'foundation_codes'))
from oil_capacity_config import get_oil_capacity

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cache directory
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
EMBEDDINGS_CACHE_FILE = CACHE_DIR / "pet_embeddings_cache.pkl"

ILL_NO_CATEGORIES = {
    '103': 'Spark plugs',
    '104': 'Engine oil system',
    '105': 'Coolant system',
    '106': 'Air intake/filters',
    '304': 'Transfer case',
    '305': 'Differential/axle oils',
    '320': 'PDK/Transmission',
    '604': 'Brake system',
    '814': 'Climate control filters',
}


# ============================================================================
# EMBEDDING CACHE CLASS
# ============================================================================

class EmbeddingCache:
    """
    Cache for PET part embeddings
    Key: description text (not part number, as it changes)
    Value: embedding vector
    """
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, List[float]]:
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    cache = pickle.load(f)
                print(f"📂 Loaded {len(cache)} embeddings from cache")
                return cache
            except Exception as e:
                print(f"⚠️ Cache load error: {e}. Starting fresh.")
                return {}
        return {}

    def save_cache(self):
        try:
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
            print(f"💾 Saved {len(self.cache)} embeddings to cache")
        except Exception as e:
            print(f"❌ Cache save error: {e}")

    def get(self, text: str) -> Optional[List[float]]:
        return self.cache.get(text)

    def set(self, text: str, embedding: List[float]):
        self.cache[text] = embedding


# ============================================================================
# HYBRID MATCHER CLASS
# ============================================================================

class HybridMatcher:
    """
    Hybrid matcher combining keywords + OpenAI embeddings
    Fallback strategy: keywords → embeddings → explanation
    """
    def __init__(self, pet_rows: List[Dict]):
        self.pet_rows = pet_rows
        self.embedding_cache = EmbeddingCache(EMBEDDINGS_CACHE_FILE)
        self.embedding_model = "text-embedding-3-small"  # Cheaper & faster
        self.stats = {
            "total_calls": 0,
            "keyword_only": 0,
            "semantic_used": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "explanation_calls": 0
        }

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding with caching"""
        # Check cache first
        cached = self.embedding_cache.get(text)
        if cached:
            self.stats["cache_hits"] += 1
            return cached

        # Call API
        try:
            response = client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding
            self.embedding_cache.set(text, embedding)
            self.stats["api_calls"] += 1
            return embedding
        except Exception as e:
            print(f"❌ Embedding API error: {e}")
            return None

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    def get_explanation(self, service_line: str, matched_part: Dict, score: float) -> str:
        """
        Ask GPT-4o-mini to explain why this part was chosen
        Only called when match score is uncertain (0.4-0.7)
        """
        try:
            self.stats["explanation_calls"] += 1

            prompt = f"""You are a Porsche parts matching expert. Explain in 1-2 sentences why this part matches the service requirement.

Service Required: {service_line}

Matched Part:
- Part Number: {matched_part.get('Part Number', '')}
- Description: {matched_part.get('Description', '')}
- Remark: {matched_part.get('Remark', '')}
- Match Score: {score:.2f}

Provide a clear, technical explanation in English."""

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.3
            )

            explanation = response.choices[0].message.content.strip()
            return explanation

        except Exception as e:
            print(f"❌ Explanation API error: {e}")
            return ""

    def semantic_match(self, service_line: str, candidates: List[Dict], top_k: int = 5) -> List[Tuple[Dict, float]]:
        """
        Perform semantic matching using embeddings
        Returns: [(part_dict, similarity_score), ...]
        """
        # Get service line embedding
        service_embedding = self.get_embedding(service_line)
        if not service_embedding:
            return []

        # Calculate similarities for all candidates
        similarities = []
        for part in candidates:
            # Create rich text representation
            part_text = f"{part.get('Description', '')} {part.get('Remark', '')}".strip()

            part_embedding = self.get_embedding(part_text)
            if part_embedding:
                similarity = self.cosine_similarity(service_embedding, part_embedding)
                similarities.append((part, similarity))

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]

    def hybrid_match(self, service_line: str, keyword_matches: List[Dict],
                     keyword_scores: List[float], model_name: str) -> List[Dict]:
        """
        Combine keyword matching with semantic matching

        Strategy:
        1. If keyword score >= 0.7: Trust keywords
        2. If keyword score < 0.5 or no match: Use semantic
        3. If 0.5 <= score < 0.7: Combine both (weighted)
        """
        self.stats["total_calls"] += 1

        # Case 1: Strong keyword match - trust it
        max_kw_score = max(keyword_scores) if keyword_scores else 0

        if keyword_matches and max_kw_score >= 0.7:
            self.stats["keyword_only"] += 1
            print(f"  ✅ Strong keyword match (score: {max_kw_score:.2f})")
            best_match = keyword_matches[0].copy()
            best_match['match_method'] = 'keywords'
            best_match['hybrid_score'] = max_kw_score
            best_match['explanation'] = ""
            return [best_match]

        # Case 2: Weak or no keyword match - use semantic on ALL PET
        if not keyword_matches or max_kw_score < 0.5:
            self.stats["semantic_used"] += 1
            print(f"  🔍 Using semantic matching (keyword score: {max_kw_score:.2f})")

            semantic_results = self.semantic_match(service_line, self.pet_rows, top_k=3)

            if semantic_results:
                best_part, semantic_score = semantic_results[0]

                # Get explanation if score is uncertain
                explanation = ""
                if 0.4 <= semantic_score <= 0.7:
                    explanation = self.get_explanation(service_line, best_part, semantic_score)

                result = {
                    'part_number': best_part.get('Part Number', ''),
                    'description': best_part.get('Description', ''),
                    'remark': best_part.get('Remark', ''),
                    'ill_no': best_part.get('Ill-No.', ''),
                    'quantity': best_part.get('Qty', '1'),
                    'score': semantic_score,
                    'match_method': 'semantic',
                    'hybrid_score': semantic_score,
                    'explanation': explanation
                }

                print(f"  🎯 Semantic: {result['description'][:50]} (score: {semantic_score:.2f})")
                if explanation:
                    print(f"  💡 {explanation[:80]}...")

                return [result]
            else:
                return []

        # Case 3: Medium keyword match - combine with semantic
        self.stats["semantic_used"] += 1
        print(f"  ⚖️ Combining keyword + semantic (keyword: {max_kw_score:.2f})")

        # Get semantic scores for keyword candidates
        semantic_results = self.semantic_match(service_line,
                                               [kw['original_pet_row'] for kw in keyword_matches[:5]],
                                               top_k=3)

        # Weighted combination: 40% keywords, 60% semantic
        combined_scores = []
        for i, kw_match in enumerate(keyword_matches[:3]):
            kw_score = keyword_scores[i] if i < len(keyword_scores) else 0

            # Find semantic score for this part
            semantic_score = 0
            for sem_part, sem_score in semantic_results:
                if sem_part.get('Part Number') == kw_match.get('part_number'):
                    semantic_score = sem_score
                    break

            # Weighted average
            hybrid_score = 0.4 * kw_score + 0.6 * semantic_score

            # Get explanation if uncertain
            explanation = ""
            if 0.4 <= hybrid_score <= 0.7:
                explanation = self.get_explanation(service_line, kw_match['original_pet_row'], hybrid_score)

            result = kw_match.copy()
            result['match_method'] = 'hybrid'
            result['hybrid_score'] = hybrid_score
            result['keyword_score'] = kw_score
            result['semantic_score'] = semantic_score
            result['explanation'] = explanation

            combined_scores.append(result)

        # Sort by hybrid score
        combined_scores.sort(key=lambda x: x['hybrid_score'], reverse=True)

        if combined_scores:
            best = combined_scores[0]
            print(f"  🎯 Hybrid: {best.get('description', '')[:50]}")
            print(f"     KW: {best['keyword_score']:.2f}, Sem: {best['semantic_score']:.2f}, Final: {best['hybrid_score']:.2f}")
            if best.get('explanation'):
                print(f"  💡 {best['explanation'][:80]}...")

        return combined_scores[:1] if combined_scores else []

    def finalize(self):
        """Save cache and print statistics"""
        self.embedding_cache.save_cache()
        self.print_stats()

    def print_stats(self):
        """Print usage statistics"""
        print("\n" + "="*70)
        print("📊 HYBRID MATCHING STATISTICS")
        print("="*70)
        print(f"Total matching calls: {self.stats['total_calls']}")
        print(f"Keyword only: {self.stats['keyword_only']}")
        print(f"Semantic used: {self.stats['semantic_used']}")
        print(f"Embedding cache hits: {self.stats['cache_hits']}")
        print(f"Embedding API calls: {self.stats['api_calls']}")
        print(f"GPT explanation calls: {self.stats['explanation_calls']}")

        total_embedding_requests = self.stats['cache_hits'] + self.stats['api_calls']
        if total_embedding_requests > 0:
            cache_efficiency = self.stats['cache_hits'] / total_embedding_requests * 100
            print(f"Cache efficiency: {cache_efficiency:.1f}%")

        # Estimate cost
        embedding_cost = self.stats['api_calls'] * 0.00002  # ~$0.02 per 1K tokens
        explanation_cost = self.stats['explanation_calls'] * 0.0015  # ~$0.15 per 100 tokens
        total_cost = embedding_cost + explanation_cost

        print(f"\n💰 Estimated API cost: ${total_cost:.4f}")
        print(f"   - Embeddings: ${embedding_cost:.4f}")
        print(f"   - Explanations: ${explanation_cost:.4f}")
        print("="*70)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def sort_services_by_interval(services: Dict) -> Dict:
    time_dependent = {}
    km_services = {}
    for key, value in services.items():
        if "time-dependent" in key.lower() or "time dependent" in key.lower():
            time_dependent[key] = value
        else:
            km_services[key] = value

    def extract_km_from_header(header):
        match = re.search(r'(\d+)\s*tkm', header.lower())
        if match:
            return int(match.group(1)) * 1000
        return 999999

    sorted_km_services = OrderedDict(
        sorted(km_services.items(), key=lambda x: extract_km_from_header(x[0]))
    )

    for key, value in time_dependent.items():
        sorted_km_services[key] = value

    return sorted_km_services


def extract_x_version(description: str) -> int:
    """Extract X version (X3, X4, X10, etc.)"""
    match = re.search(r'x(\d+)', description.lower())
    if match:
        return int(match.group(1))
    return -1


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'75\s*w\s*-?\s*90', '75w90', text)
    text = re.sub(r'ffl\s*-?\s*(\d+)', r'ffl\1', text)
    text = re.sub(r'dot\s*-?\s*(\d+)', r'dot\1', text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_ill_no_base(ill_no: str) -> str:
    if not ill_no:
        return ''
    match = re.match(r'(\d{3})', str(ill_no))
    if match:
        return match.group(1)
    return ''


def get_service_keywords(service_line: str) -> List[str]:
    service_lower = service_line.lower()
    keywords = []

    if "engine oil" in service_lower or "fill in" in service_lower:
        keywords.extend(["engine", "oil", "mobil", "v04"])
    if "oil filter" in service_lower:
        keywords.extend(["oil", "filter", "cartridge"])
    if "brake" in service_lower and "fluid" in service_lower:
        keywords.extend(["brake", "fluid", "dot"])
    if "air filter" in service_lower or "air cleaner" in service_lower:
        keywords.extend(["air", "filter", "engine", "intake"])
    if "cabin" in service_lower or "pollen" in service_lower or "particle filter" in service_lower:
        keywords.extend(["cabin", "pollen", "filter", "dust", "microfilter", "odour", "allergen"])
    if "spark" in service_lower and "plug" in service_lower:
        keywords.extend(["spark", "plug"])
    if "coolant" in service_lower:
        keywords.extend(["coolant", "additive"])
    if "pdk" in service_lower:
        keywords.extend(["pdk", "transmission", "ffl"])
    if "rear" in service_lower and ("differential" in service_lower or "final drive" in service_lower):
        keywords.extend(["rear", "differential", "final", "drive", "75w90"])
    if ("all-wheel" in service_lower or "all wheel" in service_lower) and (
        "final drive" in service_lower or "differential" in service_lower):
        keywords.extend(["front", "differential", "axle", "transmission", "fluid"])
    if "front" in service_lower and (
        "differential" in service_lower or "axle" in service_lower or "final drive" in service_lower):
        keywords.extend(["front", "differential", "axle", "transmission", "fluid"])
    if "transfer" in service_lower and ("gear" in service_lower or "case" in service_lower or "box" in service_lower):
        keywords.extend(["transfer", "box", "gear", "oil", "transmission", "fluid"])

    return keywords


# ============================================================================
# KEYWORD MATCHING (EXISTING LOGIC)
# ============================================================================

def calculate_match_score_porsche(service_line: str, pet_part: Dict) -> float:
    service_norm = normalize_text(service_line)
    part_number = pet_part.get('Part Number', '')
    description = pet_part.get('Description', '')
    remark = pet_part.get('Remark', '')
    ill_no = pet_part.get('Ill-No.', '')
    pet_norm = normalize_text(f"{description} {remark}")
    ill_base = get_ill_no_base(ill_no)

    keywords = get_service_keywords(service_line)
    keyword_score = 0
    if keywords:
        for keyword in keywords:
            if keyword in pet_norm:
                keyword_score += 1
        keyword_score = keyword_score / len(keywords)

    boost = 0
    penalty = 0

    # CRITICAL RULE: Oil filter for Panamera/Cayenne MUST be "with seal"
    if "oil filter" in service_norm and "change" in service_norm:
        if "with seal" in pet_norm or "insert" in pet_norm:
            boost += 0.7
        if "complete" in pet_norm or "discontinued" in pet_norm:
            penalty += 0.9

    # CRITICAL RULE: Air cleaner = Engine air filter
    if "air cleaner" in service_norm or ("air filter" in service_norm and "cabin" not in service_norm):
        if "engine" in pet_norm or "intake" in pet_norm or "air filter" in pet_norm:
            boost += 0.6
        if "cabin" in pet_norm or "pollen" in pet_norm:
            penalty += 0.9

    # CRITICAL RULE: Particle filter = Cabin/pollen/dust filter
    if "particle filter" in service_norm or "cabin" in service_norm or "pollen" in service_norm:
        if "cabin" in pet_norm or "pollen" in pet_norm or "dust" in pet_norm or "microfilter" in pet_norm or (
            "odour" in pet_norm and "allergen" in pet_norm):
            boost += 0.6
        if "engine" in pet_norm and "air" in pet_norm and "cabin" not in pet_norm:
            penalty += 0.9

    # Transfer case/box oil
    if "transfer" in service_norm and ("gear" in service_norm or "box" in service_norm):
        if "transfer" in pet_norm and ("box" in pet_norm or "gear" in pet_norm):
            boost += 0.7
        if ill_base == "304":
            boost += 0.3

    # PDK transmission oil
    if "pdk" in service_norm:
        if ("ffl8" in pet_norm or "ffl4" in pet_norm):
            boost += 0.6
        else:
            penalty += 0.9
        if ill_base == '320':
            boost += 0.2

    # Rear differential/final drive
    if "rear" in service_norm and ("differential" in service_norm or "final" in service_norm):
        if "75w90" in pet_norm:
            boost += 0.6
        elif "ffl" in pet_norm:
            penalty += 0.9
        if ill_base == '305':
            boost += 0.2

    # Front differential / All-wheel final drive
    if ("front" in service_norm and (
        "differential" in service_norm or "final" in service_norm or "axle" in service_norm)) or \
       ("all-wheel" in service_norm or "all wheel" in service_norm) or \
       ("4-wheel" in service_norm or "4 wheel" in service_norm):
        if ("transmission" in pet_norm and "fluid" in pet_norm) or \
           ("front" in pet_norm and ("axle" in pet_norm or "differential" in pet_norm)):
            boost += 0.7
        if "ffl" in pet_norm and "front" not in pet_norm:
            penalty += 0.5
        if ill_base == '305':
            boost += 0.3

    # Engine oil
    if ("engine oil" in service_norm or "fill in" in service_norm) and "filter" not in service_norm:
        if ill_base == '104':
            boost += 0.3
        if "filter" in pet_norm:
            penalty += 0.5

    # Penalty for discontinued parts
    if "discontinued" in pet_norm:
        penalty += 0.3

    # Brake fluid
    if "brake" in service_norm and "fluid" in service_norm:
        if "dot" in pet_norm or ill_base == '604':
            boost += 0.4

    # Spark plugs
    if "spark" in service_norm and "plug" in service_norm:
        if ill_base == '103':
            boost += 0.4

    # Coolant
    if "coolant" in service_norm:
        if ill_base == '105':
            boost += 0.3

    final_score = keyword_score + boost - penalty
    return max(0, min(1, final_score))


def best_pet_match_porsche(service_line: str, pet_rows: List[Dict], model_name: str,
                           hybrid_matcher: Optional[HybridMatcher] = None) -> List[Dict]:
    """
    Enhanced matching with hybrid approach
    """
    if not pet_rows:
        return []

    # Step 1: Keyword matching
    scored_parts = []
    for pet_row in pet_rows:
        part_num = pet_row.get('Part Number', '')
        description = pet_row.get('Description', '')
        remark = pet_row.get('Remark', '')
        ill_no = pet_row.get('Ill-No.', '')

        score = calculate_match_score_porsche(service_line, pet_row)

        if score > 0.3:
            scored_parts.append({
                'part_number': part_num,
                'description': description,
                'remark': remark,
                'ill_no': ill_no,
                'quantity': pet_row.get('Qty', '1'),
                'score': score,
                'original_pet_row': pet_row  # Keep for semantic matching
            })

    scored_parts.sort(key=lambda x: x['score'], reverse=True)

    # Step 2: Apply hybrid matching if available
    if hybrid_matcher:
        keyword_matches = scored_parts[:5]
        keyword_scores = [p['score'] for p in keyword_matches]

        hybrid_results = hybrid_matcher.hybrid_match(service_line, keyword_matches,
                                                     keyword_scores, model_name)

        if hybrid_results:
            best_match = hybrid_results[0]
            print(f"  ✅ Matched: {best_match['part_number']} ({best_match.get('match_method', 'keyword')})")
            return hybrid_results

    # Step 3: Fallback to keyword only
    if scored_parts:
        best_match = scored_parts[0]
        print(f"  ✅ Matched: {best_match['part_number']} (Ill-No: {best_match['ill_no']}, score: {best_match['score']:.2f})")
        return [best_match]
    else:
        print(f"  ⚠️ No match found")
        return []


# ============================================================================
# SPECIAL RULES
# ============================================================================

def apply_special_rules(service_line: str, model_name: str, matches: List[Dict]) -> List[Dict]:
    service_lower = service_line.lower()
    model_lower = model_name.lower()
    is_panamera = 'panamera' in model_lower
    is_cayenne = 'cayenne' in model_lower

    # Rule 1: Oil filter for Panamera/Cayenne - add drain plug and washer
    if (is_panamera or is_cayenne) and "change oil filter" in service_lower:
        if matches:
            result = [matches[0]]
            result.append({
                'part_number': 'PAF911679',
                'description': 'Oil drain plug',
                'remark': 'פקק לאגן שמן',
                'ill_no': '',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True,
                'explanation': ''
            })
            result.append({
                'part_number': 'PAF013849',
                'description': 'Oil drain washer',
                'remark': 'שייבה לאגן שמן',
                'ill_no': '',
                'quantity': '1',
                'score': 1.0,
                'is_addon': True,
                'explanation': ''
            })
            print(f"  🔧 Added oil drain plug + washer")
            return result
        else:
            return matches

    # Rule 2: Engine oil - ALWAYS prefer HIGHEST X version
    if ('fill in' in service_lower and 'engine oil' in service_lower) or 'engine oil' in service_lower:
        if matches:
            all_candidates = []
            for match in matches:
                desc = match.get('description', '')
                x_ver = extract_x_version(desc)
                all_candidates.append((x_ver, match))

            x_versions = [(x, m) for x, m in all_candidates if x > 0]

            if x_versions:
                x_versions.sort(key=lambda x: x[0], reverse=True)
                highest_x = x_versions[0][1]
                print(f"  🔝 Selected HIGHEST X version: X{x_versions[0][0]}")
                return [highest_x]

    # Rule 3: Air cleaner - replace filter element
    if "air cleaner" in service_lower and "replace filter element" in service_lower:
        for match in matches:
            desc_lower = match.get('description', '').lower()
            if "air filter element" in desc_lower:
                print(f"  🌬️ Matched air filter element")
                return [match]

    # Rule 4: Particle filter - replace filter element
    if "particle filter" in service_lower and "replace filter element" in service_lower:
        for match in matches:
            desc_lower = match.get('description', '').lower()
            if (("odour" in desc_lower and "allergen" in desc_lower and "filter" in desc_lower) or
                ("odour and allergen filter" in desc_lower)):
                print(f"  🧼 Matched odour and allergen filter")
                return [match]

    return matches[:1] if matches else []


# ============================================================================
# MAIN MATCHING PIPELINE
# ============================================================================

def match_parts_to_services(classified_data: Dict, pet_data: List[Dict],
                           model_description: str, use_hybrid: bool = True) -> Optional[Dict]:
    """
    Main matching pipeline with optional hybrid mode
    """
    if not classified_data or "services" not in classified_data:
        print("❌ Invalid classified data")
        return None

    if not pet_data:
        print("❌ No PET data")
        return None

    print(f"🔧 Matching parts with {'Hybrid (Keywords + OpenAI)' if use_hybrid else 'Keywords only'}")
    print(f"Model: {model_description}")
    print(f"PET parts: {len(pet_data)}")

    oil_capacity = get_oil_capacity(model_description)
    if oil_capacity:
        print(f"✅ Oil capacity: {oil_capacity}L")
    else:
        print("⚠️ No oil capacity defined")
        oil_capacity = None

    # Initialize hybrid matcher if enabled
    hybrid_matcher = HybridMatcher(pet_data) if use_hybrid else None

    matched_data = {}
    services = classified_data["services"]
    total_parts = 0
    matched_parts = 0
    not_found = 0

    for service_key, service_data in services.items():
        original_header = service_data.get("original_header", service_key)
        print(f"\n📋 Processing {service_key} ({original_header})...")

        items = service_data.get("items", [])
        if not items:
            print(f"  ⚠️ No items found")
            continue

        model_name = model_description
        service_output = {
            "model": model_name,
            "oil_capacity": oil_capacity,
            "matched_parts": []
        }

        for item in items:
            text = item.get("text", "")
            category = item.get("category", "")
            confidence = item.get("confidence", 0.5)

            if category != "PARTS":
                continue

            total_parts += 1

            # Match with hybrid or keyword only
            matches = best_pet_match_porsche(text, pet_data, model_name, hybrid_matcher)
            matches = apply_special_rules(text, model_name, matches)

            quantity = "1"
            if "engine oil" in text.lower() or "fill in" in text.lower():
                if oil_capacity:
                    quantity = str(oil_capacity)

            if matches:
                for match in matches:
                    is_addon = match.get('is_addon', False)
                    service_line_text = f"{text} ({match.get('remark', '')})" if is_addon else text

                    part_data = {
                        "SERVICE LINE": service_line_text,
                        "CATEGORY": category,
                        "CONFIDENCE": confidence,
                        "PART NUMBER": match.get('part_number', 'NOT FOUND'),
                        "DESCRIPTION": match.get('description', ''),
                        "REMARK": match.get('remark', ''),
                        "QUANTITY": quantity if "oil" in text.lower() and not is_addon else match.get('quantity', '1'),
                        "MATCH SCORE": round(match.get('hybrid_score', match.get('score', 0)), 3)
                    }

                    # Add explanation if available
                    if match.get('explanation'):
                        part_data["EXPLANATION"] = match['explanation']

                    if match.get('match_method'):
                        part_data["MATCH METHOD"] = match['match_method']

                    service_output["matched_parts"].append(part_data)

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
    print(f"   Total PARTS lines: {total_parts}")
    print(f"   Successfully matched: {matched_parts}")
    print(f"   Not found: {not_found}")

    if not_found > 0:
        print(f"\n⚠️ Warning: {not_found} parts not matched")

    # Finalize hybrid matcher (save cache + stats)
    if hybrid_matcher:
        hybrid_matcher.finalize()

    sorted_matched_data = sort_services_by_interval(matched_data)
    return sorted_matched_data


# ============================================================================
# TEST
# ============================================================================

def _test():
    print("="*70)
    print("Testing Step 5: Hybrid Matching (Keywords + OpenAI)")
    print("="*70)
    print("\n✅ Ready!")
    print("Features:")
    print("  1. Keywords matching (fast, free)")
    print("  2. OpenAI Embeddings (semantic, cached)")
    print("  3. GPT-4o-mini explanations (for uncertain matches)")
    print("\nUpdated rules:")
    print("  1. Engine oil: HIGHEST X version preferred")
    print("  2. Panamera/Cayenne oil filter: Must be 'with seal'")
    print("  3. Air cleaner: Engine air filter")
    print("  4. Particle filter: Cabin/pollen/dust filter")
    print("  5. Transfer gear: Transfer box gear oil")


if __name__ == "__main__":
    _test()
