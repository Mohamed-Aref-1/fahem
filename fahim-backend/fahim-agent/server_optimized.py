from __future__ import annotations

import json
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings

settings = get_settings()

# ── Azure OpenAI embeddings ───────────────────────────────────────────────────
AZURE_EMBEDDING_ENDPOINT = (
    "https://text-embedd-resource.cognitiveservices.azure.com/"
    "openai/deployments/text-embedding-3-small/embeddings?api-version=2023-05-15"
)
AZURE_EMBEDDING_KEY = settings.AZURE_EMBEDDING_KEY

# ── DB engine ─────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    pool_size=20,
    max_overflow=50,
    pool_timeout=60,
    pool_pre_ping=True,
    pool_recycle=3600,
)
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

mcp = FastMCP(
    "fashion-recommender",
    host="0.0.0.0",
    port=settings.PORT,
)

TABLE = "fashion_products_ai2"

LANG_LABEL    = {"ar": "Arabic", "en": "English"}
COUNTRY_LABEL = {"uae": "UAE", "saudi": "Saudi Arabia"}

# ── Country normalization ─────────────────────────────────────────────────────
COUNTRY_MAP = {
    "ae":           "uae",
    "uae":          "uae",
    "dubai":        "uae",
    "emirates":     "uae",
    "u.a.e":        "uae",
    "sa":           "saudi",
    "sau":          "saudi",
    "saudi":        "saudi",
    "ksa":          "saudi",
    "saudi arabia": "saudi",
    "saudiarabia":  "saudi",
}

def _normalize_country(c: str) -> str:
    return COUNTRY_MAP.get(c.lower().strip(), c.lower().strip())

# ── Gender normalization ──────────────────────────────────────────────────────
GENDER_MAP = {
    "female":   "women",
    "woman":    "women",
    "women":    "women",
    "male":     "men",
    "man":      "men",
    "men":      "men",
    "boy":      "boys",
    "boys":     "boys",
    "girl":     "girls",
    "girls":    "girls",
    "unisex":   "unisex",
    "children": "children",
    "child":    "children",
    "kids":     "children",
}

def _normalize_gender(g: str) -> str:
    return GENDER_MAP.get(g.lower().strip(), g.lower().strip())

# ── Vocab columns with embedding twins ───────────────────────────────────────
VOCAB_COLUMNS = [
    "vlm_garment_type",
    "vlm_garment_subtype",
    "vlm_style",
    "vlm_aesthetic",
    "vlm_primary_occasion",
    "vlm_age_range",
    "vlm_pattern",
    "vlm_material_apparent",
    "vlm_brand_tier",
    "vlm_modesty_level",
    "vlm_trend_relevance",
    "vlm_texture",
    "vlm_fit_type",
    "vlm_color_family",
    "vlm_primary_color",
    "vlm_sleeve_length",
    "vlm_leg_coverage",
    "vlm_primary_color_arabic",
]

OCCASION_COLS = [
    "occ_work", "occ_casual_outing", "occ_formal_event", "occ_gym_sports",
    "occ_home_lounge", "occ_ramadan_eid", "occ_wedding_guest",
    "occ_beach_pool", "occ_date_night",
]
SEASON_COLS = [
    "season_summer", "season_winter", "season_spring_fall", "season_all_season",
]


def _json(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _parse_images(raw: Any, max_count: int = 3) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        urls = [str(u) for u in raw if u]
    else:
        s = str(raw).strip()
        if s.startswith("{") and s.endswith("}"):
            s = s[1:-1]
        urls = [u.strip().strip('"') for u in s.split(",") if u.strip()]
    return urls[:max_count]


async def _embed(text_input: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            AZURE_EMBEDDING_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "api-key": AZURE_EMBEDDING_KEY,
            },
            json={"input": text_input, "dimensions": 1024},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


async def _resolve_vocab(
    query_vec: list[float],
    column: str,
    country: str,
    language: str,
    top_k: int = 1,
) -> list[str]:
    embedding_col = f"{column}_embedding"
    vec_literal   = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT DISTINCT ON ({column})
                {column},
                1 - ({embedding_col} <=> CAST(:vec AS vector(1024))) AS similarity
            FROM {TABLE}
            WHERE country  = :country
              AND language = :language
              AND {column} IS NOT NULL
              AND {embedding_col} IS NOT NULL
            ORDER BY {column}, {embedding_col} <=> CAST(:vec AS vector(1024))
        """), {
            "vec":      vec_literal,
            "country":  country,
            "language": language,
        })).fetchall()

    if not rows:
        return []
    rows_sorted = sorted(rows, key=lambda r: r[1], reverse=True)
    return [r[0] for r in rows_sorted[:top_k]]


def _build_bool_conditions(flag_map: dict, conditions: list, params: dict):
    for col, val in flag_map.items():
        if val is not None:
            conditions.append(f"{col} = :{col}")
            params[col] = val


# ═════════════════════════════════════════════════════════════════════════════
# SESSION
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def start_session(user_language: str, country: str) -> str:
    """
    *** CALL THIS FIRST ON EVERY NEW CONVERSATION — BEFORE ANY OTHER TOOL ***

    This server contains fashion and accessories products available ONLY in
    UAE and Saudi Arabia, sold on the Noon.com platform.
    Products are available in Arabic (language='ar') and English (language='en').
    No other countries or languages are supported.

    LANGUAGE DETECTION:
      - User wrote in Arabic  → user_language = "ar"
      - User wrote in English → user_language = "en"
      - Language is LOCKED for the full conversation. Never change it.

    COUNTRY RULES:
      - ONLY supports: UAE and Saudi Arabia. Nothing else.
      - Accepted country values: "uae", "ae", "dubai", "emirates",
        "saudi", "ksa", "sa", "saudi arabia"
      - If user did NOT mention country, ask: "Are you shopping from UAE or Saudi Arabia?"
      - Wait for their answer BEFORE calling this tool.
      - If user mentions any other country, tell them only UAE and Saudi are supported.
      - Country is LOCKED for the full conversation. Never change it.

    GENDER VALUES in this database:
      - Always use: "men", "women", "boys", "girls", "unisex", "children"
      - Never use: "male", "female", "man", "woman" — these will not match.

    Args:
      user_language:  "ar" or "en"
      country:        "uae" / "ae" / "saudi" / "ksa" / "sa" etc.
    """
    lang = user_language.lower().strip()
    ctry = _normalize_country(country)

    if lang not in ("ar", "en"):
        return _json({"ok": False, "error": f"Invalid language '{lang}'. Must be 'ar' or 'en'."})
    if ctry not in ("uae", "saudi"):
        return _json({"ok": False, "error": f"Invalid country '{country}'. Must be UAE or Saudi Arabia."})

    async with SessionLocal() as db:
        row = (await db.execute(text(f"""
            SELECT COUNT(*) FROM {TABLE}
            WHERE country = :country AND language = :language
        """), {"country": ctry, "language": lang})).fetchone()

    count = row[0] if row else 0

    return _json({
        "ok": True,
        "session": {
            "language":           lang,
            "language_label":     LANG_LABEL[lang],
            "country":            ctry,
            "country_label":      COUNTRY_LABEL[ctry],
            "available_products": count,
        },
        "instructions": (
            f"Session locked: language='{lang}', country='{ctry}'. "
            f"Pass these EXACT values to ALL subsequent tool calls. "
            f"There are {count:,} products available. "
            f"GENDER VALUES — always use exactly: 'men', 'women', 'boys', 'girls', 'unisex', 'children'. "
            f"COUNTRY VALUES — always use exactly: 'uae' or 'saudi'. "
            f"TOOL SELECTION RULES: "
            f"(1) User describes a specific product → search_products. "
            f"(2) User browses by category/gender/occasion → get_products_by_filters. "
            f"(3) User wants deals/discounts → get_best_deals. "
            f"(4) User wants top-rated → get_top_rated_products. "
            f"(5) User asks about a specific product → get_product_by_sku. "
            f"(6) User asks what's available → get_filter_values. "
            f"ALWAYS show images + price + rating for every product. No exceptions."
        ),
    })


# ═════════════════════════════════════════════════════════════════════════════
# DISCOVERY
# ═════════════════════════════════════════════════════════════════════════════ 

@mcp.tool()
async def get_filter_values(country: str, language: str) -> str:
    """
    Return all valid filterable values for the current session.
    Call this when the user asks what categories, styles, aesthetics,
    occasions, or garment types are available.

    MANDATORY: country and language MUST come from start_session.

    Args:
      country:   from start_session — "uae" or "saudi"
      language:  from start_session — "ar" or "en"
    """
    ctry   = _normalize_country(country)
    lang   = language.lower().strip()
    params = {"country": ctry, "language": lang}
    base   = "WHERE country = :country AND language = :language"

    async with SessionLocal() as db:

        async def _counts(col: str):
            result = await db.execute(text(f"""
                SELECT {col}, COUNT(*) as cnt FROM {TABLE}
                {base} AND {col} IS NOT NULL AND {col} != ''
                GROUP BY {col} ORDER BY cnt DESC
            """), params)
            return result.fetchall()

        garment_types  = await _counts("vlm_garment_type")
        styles         = await _counts("vlm_style")
        aesthetics     = await _counts("vlm_aesthetic")
        occasions      = await _counts("vlm_primary_occasion")
        age_ranges     = await _counts("vlm_age_range")
        genders        = await _counts("vlm_gender")
        color_families = await _counts("vlm_color_family")
        brand_tiers    = await _counts("vlm_brand_tier")
        modesty_levels = await _counts("vlm_modesty_level")

    def _fmt(rows): return [{"value": r[0], "count": r[1]} for r in rows]

    return _json({
        "ok": True,
        "session_scope":     {"country": ctry, "language": lang},
        "garment_types":     _fmt(garment_types),
        "styles":            _fmt(styles),
        "aesthetics":        _fmt(aesthetics),
        "primary_occasions": _fmt(occasions),
        "age_ranges":        _fmt(age_ranges),
        "genders":           _fmt(genders),
        "color_families":    _fmt(color_families),
        "brand_tiers":       _fmt(brand_tiers),
        "modesty_levels":    _fmt(modesty_levels),
        "occasion_flags":    OCCASION_COLS,
        "season_flags":      SEASON_COLS,
        "note": "Pass exact 'value' strings to get_products_by_filters or search_products.",
    })


# ═════════════════════════════════════════════════════════════════════════════
# CORE SEARCH
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_products(
    query: str,
    country: str,
    language: str,
    top_k: int = 10,
    min_rating:  float | None = None,
    max_price:   float | None = None,
    min_price:   float | None = None,
    min_reviews: int   | None = None,
    gender:       str | None = None,
    color_family: str | None = None,
    ramadan_suitable:    bool | None = None,
    hijab_friendly:      bool | None = None,
    can_be_gifted:       bool | None = None,
    is_kids:             bool | None = None,
    is_abaya:            bool | None = None,
    is_jalabiya:         bool | None = None,
    is_kaftan:           bool | None = None,
    is_traditional_wear: bool | None = None,
    is_plus_size:        bool | None = None,
    is_petite:           bool | None = None,
    is_complete_outfit:  bool | None = None,
    is_bestseller:       bool | None = None,
    occ_work:            bool | None = None,
    occ_casual_outing:   bool | None = None,
    occ_formal_event:    bool | None = None,
    occ_gym_sports:      bool | None = None,
    occ_home_lounge:     bool | None = None,
    occ_ramadan_eid:     bool | None = None,
    occ_wedding_guest:   bool | None = None,
    occ_beach_pool:      bool | None = None,
    occ_date_night:      bool | None = None,
    season_summer:       bool | None = None,
    season_winter:       bool | None = None,
    season_spring_fall:  bool | None = None,
    season_all_season:   bool | None = None,
    garment_type:     str | None = None,
    garment_subtype:  str | None = None,
    style:            str | None = None,
    aesthetic:        str | None = None,
    primary_occasion: str | None = None,
    age_range:        str | None = None,
    pattern:          str | None = None,
    material:         str | None = None,
    brand_tier:       str | None = None,
    modesty_level:    str | None = None,
    trend_relevance:  str | None = None,
    texture:          str | None = None,
    fit_type:         str | None = None,
    primary_color:    str | None = None,
    sleeve_length:    str | None = None,
    leg_coverage:     str | None = None,
) -> str:
    """
    *** PRIMARY TOOL — use whenever the user describes a product they want ***

    TWO-STAGE SEARCH:
      Stage 1 — Vocab resolution: natural language filters resolved to exact
                DB strings via pre-computed embedding columns.
      Stage 2 — Semantic search: cosine similarity on the prose `embedding` column.

    COUNTRY — accepted values: "uae", "ae", "dubai", "saudi", "ksa", "sa" etc.
    GENDER  — always pass: "men", "women", "boys", "girls", "unisex", "children"

    MANDATORY: country and language MUST come from start_session.

    *** PRODUCT DISPLAY — NON-NEGOTIABLE ***
      - Images : render all image_urls as ![name](url), one per line
      - Price  : sale_price; show original + discount % if discounted
      - Rating : rating_value ⭐ (rating_count reviews)
    """
    top_k = min(top_k, 20)

    try:
        query_vec = await _embed(query)
    except Exception as e:
        return _json({"ok": False, "error": f"Embedding failed: {e}"})

    ctry = _normalize_country(country)
    lang = language.lower().strip()

    # ── Resolve vocab filters ─────────────────────────────────────────────────
    resolved: dict[str, str] = {}
    vocab_map = {
        "vlm_garment_type":      garment_type,
        "vlm_garment_subtype":   garment_subtype,
        "vlm_style":             style,
        "vlm_aesthetic":         aesthetic,
        "vlm_primary_occasion":  primary_occasion,
        "vlm_age_range":         age_range,
        "vlm_pattern":           pattern,
        "vlm_material_apparent": material,
        "vlm_brand_tier":        brand_tier,
        "vlm_modesty_level":     modesty_level,
        "vlm_trend_relevance":   trend_relevance,
        "vlm_texture":           texture,
        "vlm_fit_type":          fit_type,
        "vlm_primary_color":     primary_color,
        "vlm_sleeve_length":     sleeve_length,
        "vlm_leg_coverage":      leg_coverage,
    }
    for col, user_val in vocab_map.items():
        if user_val is None:
            continue
        hits = await _resolve_vocab(query_vec, col, ctry, lang, top_k=1)
        if hits:
            resolved[col] = hits[0]

    # ── Build WHERE clause ────────────────────────────────────────────────────
    vec_literal = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"

    conditions = ["country = :country", "language = :language"]
    params: dict[str, Any] = {
        "vec":      vec_literal,
        "country":  ctry,
        "language": lang,
        "top_k":    top_k,
    }

    for col, exact_val in resolved.items():
        placeholder = col.replace("vlm_", "r_")
        conditions.append(f"{col} = :{placeholder}")
        params[placeholder] = exact_val

    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _normalize_gender(gender)

    if color_family:
        conditions.append("vlm_color_family = :color_family")
        params["color_family"] = color_family

    if min_rating is not None:
        conditions.append("rating_value >= :min_rating")
        params["min_rating"] = min_rating
    if max_price is not None:
        conditions.append("sale_price <= :max_price")
        params["max_price"] = max_price
    if min_price is not None:
        conditions.append("sale_price >= :min_price")
        params["min_price"] = min_price
    if min_reviews is not None:
        conditions.append("rating_count >= :min_reviews")
        params["min_reviews"] = min_reviews

    _build_bool_conditions({
        "vlm_ramadan_suitable":    ramadan_suitable,
        "vlm_hijab_friendly":      hijab_friendly,
        "vlm_can_be_gifted":       can_be_gifted,
        "vlm_is_kids":             is_kids,
        "vlm_is_abaya":            is_abaya,
        "vlm_is_jalabiya":         is_jalabiya,
        "vlm_is_kaftan":           is_kaftan,
        "vlm_is_traditional_wear": is_traditional_wear,
        "vlm_is_plus_size":        is_plus_size,
        "vlm_is_petite":           is_petite,
        "vlm_is_complete_outfit":  is_complete_outfit,
        "is_bestseller":           is_bestseller,
    }, conditions, params)

    _build_bool_conditions({
        "occ_work":          occ_work,
        "occ_casual_outing": occ_casual_outing,
        "occ_formal_event":  occ_formal_event,
        "occ_gym_sports":    occ_gym_sports,
        "occ_home_lounge":   occ_home_lounge,
        "occ_ramadan_eid":   occ_ramadan_eid,
        "occ_wedding_guest": occ_wedding_guest,
        "occ_beach_pool":    occ_beach_pool,
        "occ_date_night":    occ_date_night,
    }, conditions, params)

    _build_bool_conditions({
        "season_summer":      season_summer,
        "season_winter":      season_winter,
        "season_spring_fall": season_spring_fall,
        "season_all_season":  season_all_season,
    }, conditions, params)

    where_clause = f"WHERE {' AND '.join(conditions)}"

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT
                sku, name, brand, sale_price, price, discount_percentage,
                rating_value, rating_count,
                vlm_description, vlm_garment_type, vlm_garment_subtype,
                vlm_gender, vlm_age_range, vlm_style, vlm_aesthetic,
                vlm_primary_color, vlm_color_family, vlm_primary_occasion,
                vlm_brand_tier, vlm_can_be_gifted, vlm_hijab_friendly,
                vlm_ramadan_suitable, vlm_pairs_well_with,
                vlm_style_keywords_english, vlm_style_keywords_arabic,
                vlm_similar_to_brands, vlm_one_line_arabic_description,
                country, language, product_url, is_bestseller, image_urls,
                1 - (embedding <=> CAST(:vec AS vector(1024))) AS similarity
            FROM {TABLE}
            {where_clause}
            ORDER BY embedding <=> CAST(:vec AS vector(1024))
            LIMIT :top_k
        """), params)).mappings().all()

    return _json({
        "ok": True,
        "AGENT_INSTRUCTION": (
            "For EVERY product show: "
            "(1) all image_urls as ![name](url) each on its own line, "
            "(2) sale_price; if discount_percentage > 0 show original + discount %, "
            "(3) rating_value ⭐ (rating_count reviews). "
            "Text-only or image-only replies are FORBIDDEN. "
            "After showing all products, ALWAYS end with: "
            "'🎁 Use coupon code **Hadiya5** at checkout on Noon.com to get a discount on your order!'"
        ),
        "query":          query,
        "session_scope":  {"country": ctry, "language": lang},
        "resolved_vocab": resolved,
        "total_returned": len(rows),
        "results": [
            {
                "sku":                 r["sku"],
                "name":               r["name"],
                "brand":              r["brand"],
                "sale_price":         r["sale_price"],
                "original_price":     r["price"],
                "discount_percentage":r["discount_percentage"],
                "rating_value":       r["rating_value"],
                "rating_count":       r["rating_count"],
                "description":        r["vlm_description"],
                "garment_type":       r["vlm_garment_type"],
                "garment_subtype":    r["vlm_garment_subtype"],
                "gender":             r["vlm_gender"],
                "age_range":          r["vlm_age_range"],
                "style":              r["vlm_style"],
                "aesthetic":          r["vlm_aesthetic"],
                "primary_color":      r["vlm_primary_color"],
                "color_family":       r["vlm_color_family"],
                "primary_occasion":   r["vlm_primary_occasion"],
                "brand_tier":         r["vlm_brand_tier"],
                "can_be_gifted":      r["vlm_can_be_gifted"],
                "hijab_friendly":     r["vlm_hijab_friendly"],
                "ramadan_suitable":   r["vlm_ramadan_suitable"],
                "pairs_well_with":    r["vlm_pairs_well_with"],
                "keywords_en":        r["vlm_style_keywords_english"],
                "keywords_ar":        r["vlm_style_keywords_arabic"],
                "similar_brands":     r["vlm_similar_to_brands"],
                "one_line_ar":        r["vlm_one_line_arabic_description"],
                "country":            r["country"],
                "language":           r["language"],
                "product_url":        r["product_url"],
                "is_bestseller":      r["is_bestseller"],
                "similarity_score":   round(float(r["similarity"]), 4),
                "image_urls":         _parse_images(r["image_urls"]),
            }
            for r in rows
        ],
    })


# ═════════════════════════════════════════════════════════════════════════════
# FILTER BROWSE
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_products_by_filters(
    country: str,
    language: str,
    garment_type:     str | None = None,
    garment_subtype:  str | None = None,
    gender:           str | None = None,
    age_range:        str | None = None,
    style:            str | None = None,
    aesthetic:        str | None = None,
    color_family:     str | None = None,
    brand_tier:       str | None = None,
    modesty_level:    str | None = None,
    primary_occasion: str | None = None,
    ramadan_suitable:    bool | None = None,
    hijab_friendly:      bool | None = None,
    can_be_gifted:       bool | None = None,
    is_kids:             bool | None = None,
    is_abaya:            bool | None = None,
    is_jalabiya:         bool | None = None,
    is_kaftan:           bool | None = None,
    is_traditional_wear: bool | None = None,
    is_plus_size:        bool | None = None,
    is_petite:           bool | None = None,
    is_complete_outfit:  bool | None = None,
    is_bestseller:       bool | None = None,
    occ_work:            bool | None = None,
    occ_casual_outing:   bool | None = None,
    occ_formal_event:    bool | None = None,
    occ_gym_sports:      bool | None = None,
    occ_home_lounge:     bool | None = None,
    occ_ramadan_eid:     bool | None = None,
    occ_wedding_guest:   bool | None = None,
    occ_beach_pool:      bool | None = None,
    occ_date_night:      bool | None = None,
    season_summer:       bool | None = None,
    season_winter:       bool | None = None,
    season_spring_fall:  bool | None = None,
    season_all_season:   bool | None = None,
    min_rating:  float | None = None,
    max_price:   float | None = None,
    min_price:   float | None = None,
    min_reviews: int   | None = None,
    top_k: int = 10,
) -> str:
    """
    Filter-based browse — no semantic search needed.

    USE THIS when user browses by category/gender/occasion without
    describing a specific product. Results sorted by rating DESC.

    COUNTRY — accepted: "uae", "ae", "dubai", "saudi", "ksa", "sa" etc.
    GENDER  — always pass: "men", "women", "boys", "girls", "unisex", "children"

    MANDATORY: country and language MUST come from start_session.

    *** PRODUCT DISPLAY — NON-NEGOTIABLE ***
      - Images : render all image_urls as ![name](url), one per line
      - Price  : sale_price; show original + discount % if discounted
      - Rating : rating_value ⭐ (rating_count reviews)
    """
    top_k = min(top_k, 30)

    ctry = _normalize_country(country)
    lang = language.lower().strip()

    conditions = ["country = :country", "language = :language"]
    params: dict[str, Any] = {
        "country":  ctry,
        "language": lang,
        "top_k":    top_k,
    }

    simple_str = {
        "vlm_garment_type":     garment_type,
        "vlm_garment_subtype":  garment_subtype,
        "vlm_style":            style,
        "vlm_aesthetic":        aesthetic,
        "vlm_color_family":     color_family,
        "vlm_brand_tier":       brand_tier,
        "vlm_modesty_level":    modesty_level,
        "vlm_primary_occasion": primary_occasion,
        "vlm_age_range":        age_range,
    }
    for col, val in simple_str.items():
        if val is not None:
            ph = col.replace("vlm_", "f_")
            conditions.append(f"{col} = :{ph}")
            params[ph] = val

    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _normalize_gender(gender)

    if min_rating is not None:
        conditions.append("rating_value >= :min_rating")
        params["min_rating"] = min_rating
    if max_price is not None:
        conditions.append("sale_price <= :max_price")
        params["max_price"] = max_price
    if min_price is not None:
        conditions.append("sale_price >= :min_price")
        params["min_price"] = min_price
    if min_reviews is not None:
        conditions.append("rating_count >= :min_reviews")
        params["min_reviews"] = min_reviews

    _build_bool_conditions({
        "vlm_ramadan_suitable":    ramadan_suitable,
        "vlm_hijab_friendly":      hijab_friendly,
        "vlm_can_be_gifted":       can_be_gifted,
        "vlm_is_kids":             is_kids,
        "vlm_is_abaya":            is_abaya,
        "vlm_is_jalabiya":         is_jalabiya,
        "vlm_is_kaftan":           is_kaftan,
        "vlm_is_traditional_wear": is_traditional_wear,
        "vlm_is_plus_size":        is_plus_size,
        "vlm_is_petite":           is_petite,
        "vlm_is_complete_outfit":  is_complete_outfit,
        "is_bestseller":           is_bestseller,
        "occ_work":                occ_work,
        "occ_casual_outing":       occ_casual_outing,
        "occ_formal_event":        occ_formal_event,
        "occ_gym_sports":          occ_gym_sports,
        "occ_home_lounge":         occ_home_lounge,
        "occ_ramadan_eid":         occ_ramadan_eid,
        "occ_wedding_guest":       occ_wedding_guest,
        "occ_beach_pool":          occ_beach_pool,
        "occ_date_night":          occ_date_night,
        "season_summer":           season_summer,
        "season_winter":           season_winter,
        "season_spring_fall":      season_spring_fall,
        "season_all_season":       season_all_season,
    }, conditions, params)

    where_clause = f"WHERE {' AND '.join(conditions)}"

    async with SessionLocal() as db:
        total = (await db.execute(text(f"""
            SELECT COUNT(*) FROM {TABLE} {where_clause}
        """), params)).fetchone()

        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, sale_price, price, discount_percentage,
                   rating_value, rating_count, vlm_description,
                   vlm_garment_type, vlm_garment_subtype, vlm_gender,
                   vlm_age_range, vlm_style, vlm_aesthetic,
                   vlm_primary_color, vlm_color_family, vlm_primary_occasion,
                   vlm_brand_tier, vlm_can_be_gifted, vlm_hijab_friendly,
                   vlm_ramadan_suitable, vlm_one_line_arabic_description,
                   country, language, product_url, is_bestseller, image_urls
            FROM {TABLE}
            {where_clause}
            ORDER BY rating_value DESC NULLS LAST, rating_count DESC NULLS LAST
            LIMIT :top_k
        """), params)).mappings().all()

    return _json({
        "ok": True,
        "AGENT_INSTRUCTION": (
            "For EVERY product show: "
            "(1) all image_urls as ![name](url) each on its own line, "
            "(2) sale_price; if discount_percentage > 0 show original + discount %, "
            "(3) rating_value ⭐ (rating_count reviews). "
            "Text-only or image-only replies are FORBIDDEN."
        ),
        "session_scope":  {"country": ctry, "language": lang},
        "total_matching": total[0] if total else 0,
        "total_returned": len(rows),
        "results": [
            {**dict(r), "image_urls": _parse_images(r["image_urls"])}
            for r in rows
        ],
    })


# ═════════════════════════════════════════════════════════════════════════════
# DEALS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_best_deals(
    country: str,
    language: str,
    top_k: int = 10,
    min_discount: float = 30.0,
    min_rating: float | None = 4.0,
    garment_type: str | None = None,
    gender:       str | None = None,
    ramadan_suitable: bool | None = None,
    hijab_friendly:   bool | None = None,
    occ_ramadan_eid:  bool | None = None,
    can_be_gifted:    bool | None = None,
) -> str:
    """
    Best discounted products for the session's country + language.
    Use when user asks for deals, discounts, cheapest, best value.

    COUNTRY — accepted: "uae", "ae", "dubai", "saudi", "ksa", "sa" etc.
    GENDER  — always pass: "men", "women", "boys", "girls", "unisex", "children"

    *** PRODUCT DISPLAY — NON-NEGOTIABLE ***
      - Images : render all image_urls as ![name](url), one per line
      - Price  : sale_price + original price + discount %
      - Rating : rating_value ⭐ (rating_count reviews)
    """
    ctry = _normalize_country(country)
    lang = language.lower().strip()

    conditions = [
        "country = :country", "language = :language",
        "discount_percentage >= :min_discount",
        "sale_price IS NOT NULL",
    ]
    params: dict[str, Any] = {
        "country":      ctry,
        "language":     lang,
        "min_discount": min_discount,
        "top_k":        top_k,
    }

    if min_rating is not None:
        conditions.append("rating_value >= :min_rating")
        params["min_rating"] = min_rating
    if garment_type:
        conditions.append("vlm_garment_type = :garment_type")
        params["garment_type"] = garment_type
    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _normalize_gender(gender)

    _build_bool_conditions({
        "vlm_ramadan_suitable": ramadan_suitable,
        "vlm_hijab_friendly":   hijab_friendly,
        "vlm_can_be_gifted":    can_be_gifted,
        "occ_ramadan_eid":      occ_ramadan_eid,
    }, conditions, params)

    where_clause = f"WHERE {' AND '.join(conditions)}"

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, price, sale_price, discount_percentage,
                   rating_value, rating_count, vlm_garment_type,
                   vlm_gender, vlm_description, vlm_one_line_arabic_description,
                   country, language, product_url, is_bestseller, image_urls
            FROM {TABLE}
            {where_clause}
            ORDER BY discount_percentage DESC
            LIMIT :top_k
        """), params)).mappings().all()

    return _json({
        "ok": True,
        "AGENT_INSTRUCTION": (
            "For EVERY product show: "
            "(1) all image_urls as ![name](url) each on its own line, "
            "(2) sale_price + original price + discount_percentage %, "
            "(3) rating_value ⭐ (rating_count reviews). "
            "Text-only or image-only replies are FORBIDDEN."
        ),
        "session_scope":  {"country": ctry, "language": lang},
        "total_returned": len(rows),
        "results": [
            {**dict(r), "image_urls": _parse_images(r["image_urls"])}
            for r in rows
        ],
    })


# ═════════════════════════════════════════════════════════════════════════════
# TOP RATED
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_top_rated_products(
    country: str,
    language: str,
    top_k: int = 10,
    min_rating_count: int = 50,
    garment_type: str | None = None,
    gender:       str | None = None,
    ramadan_suitable: bool | None = None,
    hijab_friendly:   bool | None = None,
    can_be_gifted:    bool | None = None,
) -> str:
    """
    Top-rated products for the session's country + language.
    Use when user asks for best rated, most popular, highest rated.

    COUNTRY — accepted: "uae", "ae", "dubai", "saudi", "ksa", "sa" etc.
    GENDER  — always pass: "men", "women", "boys", "girls", "unisex", "children"

    *** PRODUCT DISPLAY — NON-NEGOTIABLE ***
      - Images : render all image_urls as ![name](url), one per line
      - Price  : sale_price; show original + discount % if discounted
      - Rating : rating_value ⭐ (rating_count reviews)
    """
    ctry = _normalize_country(country)
    lang = language.lower().strip()

    conditions = [
        "country = :country", "language = :language",
        "rating_count >= :min_rating_count",
    ]
    params: dict[str, Any] = {
        "country":          ctry,
        "language":         lang,
        "min_rating_count": min_rating_count,
        "top_k":            top_k,
    }

    if garment_type:
        conditions.append("vlm_garment_type = :garment_type")
        params["garment_type"] = garment_type
    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _normalize_gender(gender)

    _build_bool_conditions({
        "vlm_ramadan_suitable": ramadan_suitable,
        "vlm_hijab_friendly":   hijab_friendly,
        "vlm_can_be_gifted":    can_be_gifted,
    }, conditions, params)

    where_clause = f"WHERE {' AND '.join(conditions)}"

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, sale_price, price, discount_percentage,
                   rating_value, rating_count, vlm_description,
                   vlm_garment_type, vlm_gender, vlm_one_line_arabic_description,
                   country, language, product_url, is_bestseller, image_urls
            FROM {TABLE}
            {where_clause}
            ORDER BY rating_value DESC, rating_count DESC
            LIMIT :top_k
        """), params)).mappings().all()

    return _json({
        "ok": True,
        "AGENT_INSTRUCTION": (
            "For EVERY product show: "
            "(1) all image_urls as ![name](url) each on its own line, "
            "(2) sale_price; if discount_percentage > 0 show original + discount %, "
            "(3) rating_value ⭐ (rating_count reviews). "
            "Text-only or image-only replies are FORBIDDEN."
        ),
        "session_scope":  {"country": ctry, "language": lang},
        "total_returned": len(rows),
        "results": [
            {**dict(r), "image_urls": _parse_images(r["image_urls"])}
            for r in rows
        ],
    })


# ═════════════════════════════════════════════════════════════════════════════
# PRODUCT DETAIL
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_product_by_sku(sku: str) -> str:
    """
    Retrieve EVERY column for a specific product by SKU.

    Call this when the user asks for more details about a product from
    previous results — sizing, materials, care, seller info, delivery,
    specifications, or any specific question about an item.

    Read ALL returned fields to answer the user accurately.

    *** PRODUCT DISPLAY — NON-NEGOTIABLE ***
      - Images : render ALL image_urls as ![name](url), one per line
      - Price  : sale_price; show original + discount % if discounted
      - Rating : rating_value ⭐ (rating_count reviews)
    """
    async with SessionLocal() as db:
        row = (await db.execute(text(f"""
            SELECT
                sku, name, brand, product_url,
                price, sale_price, discount_percentage,
                detail_price, detail_sale_price, detail_currency,
                rating_value, rating_count, is_bestseller,
                detail_stock,
                detail_is_free_delivery, detail_shipping_fee_message,
                detail_estimated_delivery, detail_estimated_delivery_date,
                estimated_delivery_date,
                detail_store_name, detail_seller_rating,
                detail_seller_rating_count, detail_seller_positive_rating,
                detail_seller_as_described_rate,
                category_1, category_2, category_3, category_4, category_5,
                category_breadcrumb, department,
                detail_long_description, detail_feature_bullets,
                detail_all_specifications_json,
                vlm_description, vlm_garment_type, vlm_garment_subtype,
                vlm_gender, vlm_is_kids, vlm_kids_age_group,
                vlm_style, vlm_aesthetic, vlm_pattern, vlm_fit_type,
                vlm_texture, vlm_sleeve_length, vlm_neckline, vlm_leg_coverage,
                vlm_is_layering_piece,
                occ_work, occ_casual_outing, occ_formal_event, occ_gym_sports,
                occ_home_lounge, occ_ramadan_eid, occ_wedding_guest,
                occ_beach_pool, occ_date_night,
                season_summer, season_winter, season_spring_fall, season_all_season,
                vlm_primary_occasion, vlm_age_range,
                vlm_body_type_suitable, vlm_is_plus_size, vlm_is_petite,
                vlm_primary_color, vlm_primary_color_arabic,
                vlm_color_family, vlm_is_versatile_color,
                vlm_has_multiple_colors_available,
                vlm_modesty_level, vlm_hijab_friendly, vlm_ramadan_suitable,
                vlm_is_abaya, vlm_is_jalabiya, vlm_is_kaftan,
                vlm_is_traditional_wear, vlm_regional_relevance,
                vlm_material_apparent, vlm_fabric_breathability,
                vlm_is_machine_washable_likely,
                vlm_brand_name, vlm_brand_tier, vlm_price_tier,
                vlm_is_complete_outfit, vlm_outfit_category, vlm_can_be_gifted,
                vlm_has_model_wearing,
                vlm_style_keywords_arabic, vlm_style_keywords_english,
                vlm_similar_to_brands, vlm_trend_relevance,
                vlm_pairs_well_with, vlm_one_line_arabic_description,
                country, language, all_colors, all_sizes, image_urls
            FROM {TABLE}
            WHERE sku = :sku
        """), {"sku": sku})).mappings().first()

    if not row:
        return _json({"ok": False, "error": f"No product found with SKU: {sku}"})

    product = {**dict(row), "image_urls": _parse_images(row["image_urls"], max_count=10)}

    return _json({
        "ok": True,
        "AGENT_INSTRUCTION": (
            "You now have the COMPLETE product record. "
            "Read ALL fields and use them to answer the user's question accurately. "
            "Show: all image_urls as ![name](url) each on its own line, "
            "sale_price (+ original + discount % if discounted), "
            "rating_value ⭐ (rating_count reviews). "
            "material → vlm_material_apparent | "
            "care → vlm_is_machine_washable_likely | "
            "sizing → all_sizes, vlm_fit_type | "
            "delivery → detail_estimated_delivery, detail_shipping_fee_message | "
            "seller → detail_store_name, detail_seller_rating. "
            "Never say 'I don't know' if the answer exists in these fields."
        ),
        "product": product,
    })


if __name__ == "__main__":
    try:
        mcp.run(transport="streamable-http")
    except KeyboardInterrupt:
        print("Shutting down fashion-recommender MCP server.")
        sys.exit(0)