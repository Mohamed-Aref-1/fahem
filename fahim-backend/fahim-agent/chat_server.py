from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, AsyncGenerator

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("fahim")

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncAzureOpenAI, BadRequestError
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings

settings = get_settings()

# ── Azure OpenAI ──────────────────────────────────────────────────────────────
aoai = AsyncAzureOpenAI(
    api_key=settings.AZURE_OPENAI_KEY,
    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
    api_version="2024-12-01-preview",
    timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=10.0),
    max_retries=1,
)

# ── Embeddings ────────────────────────────────────────────────────────────────
AZURE_EMBEDDING_ENDPOINT = (
    "https://text-embedd-resource.cognitiveservices.azure.com/"
    "openai/deployments/text-embedding-3-small/embeddings?api-version=2023-05-15"
)
AZURE_EMBEDDING_KEY = settings.AZURE_EMBEDDING_KEY

# ── DB ────────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    pool_size=10,
    max_overflow=20,
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

TABLE = "fashion_products_ai2"

COUNTRY_MAP = {
    "ae": "uae", "uae": "uae", "dubai": "uae", "emirates": "uae",
    "u.a.e": "uae", "sa": "saudi", "sau": "saudi", "saudi": "saudi",
    "ksa": "saudi", "saudi arabia": "saudi", "saudiarabia": "saudi",
}
GENDER_MAP = {
    "female": "women", "woman": "women", "women": "women",
    "male": "men", "man": "men", "men": "men",
    "boy": "boys", "boys": "boys", "girl": "girls", "girls": "girls",
    "unisex": "unisex", "children": "children", "child": "children", "kids": "children",
}


def _nc(c: str) -> str:
    return COUNTRY_MAP.get(c.lower().strip(), c.lower().strip())


def _ng(g: str) -> str:
    return GENDER_MAP.get(g.lower().strip(), g.lower().strip())


def _j(data: Any) -> str:
    return json.dumps(data, default=str, ensure_ascii=False)


def _clean_url(url: str) -> str:
    """Strip the slug from a noon.com product URL, keeping only the SKU.
    Full URL: https://www.noon.com/uae-ar/{slug}/{SKU}/p/?o={variant}
    Clean URL: https://www.noon.com/uae-ar/{SKU}/p/
    This prevents Azure content filter from seeing slug words like 'sexy-...'."""
    if not url:
        return ""
    m = re.search(r"(https://www\.noon\.com/[^/]+/)(?:[^/]+/)?([A-Za-z0-9]{8,})/p/", url)
    if m:
        return f"{m.group(1)}{m.group(2)}/p/"
    return url


def _parse_images(raw: Any, max_count: int = 3) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(u) for u in raw if u][:max_count]
    s = str(raw).strip()
    # Handle Python list literals stored as strings: "['url1', 'url2']"
    if s.startswith("["):
        try:
            parsed = ast.literal_eval(s)
            if isinstance(parsed, list):
                return [str(u) for u in parsed if u][:max_count]
        except Exception:
            pass
    # Handle Postgres array literals: "{url1,url2}"
    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1]
    return [u.strip().strip('"').strip("'") for u in s.split(",") if u.strip()][:max_count]


async def _embed(text_input: str) -> list[float]:
    log.info("EMBED ▶ input: %r", text_input)
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            AZURE_EMBEDDING_ENDPOINT,
            headers={"Content-Type": "application/json", "api-key": AZURE_EMBEDDING_KEY},
            json={"input": text_input},
        )
        r.raise_for_status()
        vec = r.json()["data"][0]["embedding"]
        log.info("EMBED ◀ dim=%d  first5=%s", len(vec), vec[:5])
        return vec


# ═════════════════════════════════════════════════════════════════════════════
# TOOL IMPLEMENTATIONS
# ═════════════════════════════════════════════════════════════════════════════

async def search_products(
    query: str, country: str, language: str, top_k: int = 8,
    min_rating: float | None = None, max_price: float | None = None,
    min_price: float | None = None, gender: str | None = None,
    color_family: str | None = None, primary_color: str | None = None,
    garment_type: str | None = None,
    style: str | None = None, brand_tier: str | None = None,
    modesty_level: str | None = None, ramadan_suitable: bool | None = None,
    hijab_friendly: bool | None = None, is_abaya: bool | None = None,
    is_bestseller: bool | None = None, occ_work: bool | None = None,
    occ_casual_outing: bool | None = None, occ_formal_event: bool | None = None,
    occ_ramadan_eid: bool | None = None, occ_wedding_guest: bool | None = None,
    occ_beach_pool: bool | None = None, occ_date_night: bool | None = None,
) -> str:
    top_k = min(top_k, 20)
    try:
        query_vec = await _embed(query)
    except Exception as e:
        return _j({"ok": False, "error": f"Embedding failed: {e}"})

    ctry = _nc(country)
    lang = language.lower().strip()
    vec_literal = "[" + ",".join(f"{x:.8f}" for x in query_vec) + "]"

    conditions = ["country = :country", "language = :language"]
    params: dict[str, Any] = {"vec": vec_literal, "country": ctry, "language": lang, "top_k": top_k}

    for col, val in {
        "vlm_ramadan_suitable": ramadan_suitable,
        "vlm_hijab_friendly": hijab_friendly,
        "vlm_is_abaya": is_abaya,
        "is_bestseller": is_bestseller,
        "occ_work": occ_work,
        "occ_casual_outing": occ_casual_outing,
        "occ_formal_event": occ_formal_event,
        "occ_ramadan_eid": occ_ramadan_eid,
        "occ_wedding_guest": occ_wedding_guest,
        "occ_beach_pool": occ_beach_pool,
        "occ_date_night": occ_date_night,
    }.items():
        if val is not None:
            conditions.append(f"{col} = :{col}")
            params[col] = val

    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _ng(gender)
    if color_family:
        conditions.append("vlm_color_family = :color_family")
        params["color_family"] = color_family
    if primary_color:
        conditions.append("vlm_primary_color = :primary_color")
        params["primary_color"] = primary_color
    if garment_type:
        conditions.append("vlm_garment_type = :garment_type")
        params["garment_type"] = garment_type
    if style:
        conditions.append("vlm_style = :style")
        params["style"] = style
    if brand_tier:
        conditions.append("vlm_brand_tier = :brand_tier")
        params["brand_tier"] = brand_tier
    if modesty_level:
        conditions.append("vlm_modesty_level = :modesty_level")
        params["modesty_level"] = modesty_level
    if min_rating is not None:
        conditions.append("rating_value >= :min_rating")
        params["min_rating"] = min_rating
    if max_price is not None:
        conditions.append("sale_price <= :max_price")
        params["max_price"] = max_price
    if min_price is not None:
        conditions.append("sale_price >= :min_price")
        params["min_price"] = min_price

    where = "WHERE " + " AND ".join(conditions)
    log.info("SEARCH ▶ query=%r  country=%s  lang=%s  filters=%s",
             query, ctry, lang,
             {k: v for k, v in params.items() if k not in ("vec", "country", "language", "top_k")})

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, sale_price, price, discount_percentage,
                   rating_value, rating_count, vlm_description,
                   vlm_garment_type, vlm_gender, vlm_primary_color,
                   vlm_primary_occasion, vlm_hijab_friendly, vlm_ramadan_suitable,
                   vlm_pairs_well_with, country, language, product_url,
                   is_bestseller, image_urls,
                   1 - (embedding <=> CAST(:vec AS vector(1536))) AS similarity
            FROM {TABLE}
            {where}
            ORDER BY embedding <=> CAST(:vec AS vector(1536))
            LIMIT :top_k
        """), params)).mappings().all()

    log.info("SEARCH ◀ raw_rows=%d", len(rows))
    for i, r in enumerate(rows[:5]):
        log.info("  row[%d] sku=%-20s garment_type=%-20s gender=%-10s sim=%.4f  name=%r",
                 i, r["sku"], r["vlm_garment_type"], r["vlm_gender"],
                 float(r["similarity"]) if r["similarity"] is not None else 0,
                 (r["name"] or "")[:60])

    # Deduplicate by SKU (DB may have duplicate entries)
    seen: set[str] = set()
    unique: list[dict] = []
    for r in rows:
        if r["sku"] not in seen:
            seen.add(r["sku"])
            unique.append({
                "sku": r["sku"],
                "name": r["name"],
                "brand": r["brand"],
                "sale_price": r["sale_price"],
                "original_price": r["price"],
                "discount_percentage": r["discount_percentage"],
                "rating_value": r["rating_value"],
                "rating_count": r["rating_count"],
                "description": r["vlm_description"],
                "garment_type": r["vlm_garment_type"],
                "gender": r["vlm_gender"],
                "primary_color": r["vlm_primary_color"],
                "hijab_friendly": r["vlm_hijab_friendly"],
                "ramadan_suitable": r["vlm_ramadan_suitable"],
                "pairs_well_with": r["vlm_pairs_well_with"],
                "product_url": r["product_url"],
                "is_bestseller": r["is_bestseller"],
                "image_urls": _parse_images(r["image_urls"]),
                "similarity": round(float(r["similarity"]), 4),
            })

    log.info("SEARCH ◀ unique=%d", len(unique))

    # Filter out low-similarity results (noise / products not in catalog)
    MIN_SIM = 0.20
    relevant = [p for p in unique if p["similarity"] >= MIN_SIM]
    log.info("SEARCH ◀ relevant=%d (threshold=%.2f)", len(relevant), MIN_SIM)

    return _j({"ok": True, "total": len(relevant), "results": relevant})


async def get_products_by_filters(
    country: str, language: str, top_k: int = 10,
    garment_type: str | None = None, gender: str | None = None,
    style: str | None = None, color_family: str | None = None,
    primary_color: str | None = None,
    brand_tier: str | None = None, modesty_level: str | None = None,
    primary_occasion: str | None = None, age_range: str | None = None,
    ramadan_suitable: bool | None = None, hijab_friendly: bool | None = None,
    is_abaya: bool | None = None, is_bestseller: bool | None = None,
    occ_ramadan_eid: bool | None = None, occ_wedding_guest: bool | None = None,
    min_rating: float | None = None, max_price: float | None = None,
    min_price: float | None = None,
) -> str:
    top_k = min(top_k, 30)
    ctry = _nc(country)
    lang = language.lower().strip()

    conditions = ["country = :country", "language = :language"]
    params: dict[str, Any] = {"country": ctry, "language": lang, "top_k": top_k}

    for col, val in {
        "vlm_garment_type": garment_type, "vlm_style": style,
        "vlm_color_family": color_family, "vlm_primary_color": primary_color,
        "vlm_brand_tier": brand_tier,
        "vlm_modesty_level": modesty_level, "vlm_primary_occasion": primary_occasion,
        "vlm_age_range": age_range,
    }.items():
        if val is not None:
            ph = col.replace("vlm_", "f_")
            conditions.append(f"{col} = :{ph}")
            params[ph] = val

    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _ng(gender)
    if min_rating is not None:
        conditions.append("rating_value >= :min_rating")
        params["min_rating"] = min_rating
    if max_price is not None:
        conditions.append("sale_price <= :max_price")
        params["max_price"] = max_price
    if min_price is not None:
        conditions.append("sale_price >= :min_price")
        params["min_price"] = min_price

    for col, val in {
        "vlm_ramadan_suitable": ramadan_suitable, "vlm_hijab_friendly": hijab_friendly,
        "vlm_is_abaya": is_abaya, "is_bestseller": is_bestseller,
        "occ_ramadan_eid": occ_ramadan_eid, "occ_wedding_guest": occ_wedding_guest,
    }.items():
        if val is not None:
            conditions.append(f"{col} = :{col}")
            params[col] = val

    where = "WHERE " + " AND ".join(conditions)

    async with SessionLocal() as db:
        total = (await db.execute(text(f"SELECT COUNT(*) FROM {TABLE} {where}"), params)).fetchone()
        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, sale_price, price, discount_percentage,
                   rating_value, rating_count, vlm_description,
                   vlm_garment_type, vlm_gender, vlm_primary_color,
                   vlm_primary_occasion, vlm_hijab_friendly, vlm_ramadan_suitable,
                   country, language, product_url, is_bestseller, image_urls
            FROM {TABLE}
            {where}
            ORDER BY rating_value DESC NULLS LAST, rating_count DESC NULLS LAST
            LIMIT :top_k
        """), params)).mappings().all()

    seen: set[str] = set()
    unique = []
    for r in rows:
        if r["sku"] not in seen:
            seen.add(r["sku"])
            unique.append({**dict(r), "image_urls": _parse_images(r["image_urls"])})

    return _j({
        "ok": True,
        "total_matching": total[0] if total else 0,
        "total_returned": len(unique),
        "results": unique,
    })


async def get_best_deals(
    country: str, language: str, top_k: int = 10,
    min_discount: float = 0.0, min_rating: float | None = None,
    garment_type: str | None = None, gender: str | None = None,
    ramadan_suitable: bool | None = None, hijab_friendly: bool | None = None,
) -> str:
    ctry = _nc(country)
    lang = language.lower().strip()

    conditions = [
        "country = :country", "language = :language",
        "discount_percentage >= :min_discount", "sale_price IS NOT NULL",
    ]
    params: dict[str, Any] = {
        "country": ctry, "language": lang,
        "min_discount": min_discount, "top_k": top_k,
    }

    if min_rating is not None:
        conditions.append("rating_value >= :min_rating")
        params["min_rating"] = min_rating
    if garment_type:
        conditions.append("vlm_garment_type = :garment_type")
        params["garment_type"] = garment_type
    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _ng(gender)
    for col, val in {"vlm_ramadan_suitable": ramadan_suitable, "vlm_hijab_friendly": hijab_friendly}.items():
        if val is not None:
            conditions.append(f"{col} = :{col}")
            params[col] = val

    where = "WHERE " + " AND ".join(conditions)

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, price, sale_price, discount_percentage,
                   rating_value, rating_count, vlm_garment_type, vlm_gender,
                   vlm_description, country, language, product_url, is_bestseller, image_urls
            FROM {TABLE}
            {where}
            ORDER BY discount_percentage DESC
            LIMIT :top_k
        """), params)).mappings().all()

    return _j({
        "ok": True,
        "total_returned": len(rows),
        "results": [{**dict(r), "image_urls": _parse_images(r["image_urls"])} for r in rows],
    })


async def get_top_rated_products(
    country: str, language: str, top_k: int = 10,
    min_rating_count: int = 50, garment_type: str | None = None,
    gender: str | None = None, ramadan_suitable: bool | None = None,
    hijab_friendly: bool | None = None,
) -> str:
    ctry = _nc(country)
    lang = language.lower().strip()

    conditions = ["country = :country", "language = :language", "rating_count >= :min_rating_count"]
    params: dict[str, Any] = {
        "country": ctry, "language": lang,
        "min_rating_count": min_rating_count, "top_k": top_k,
    }

    if garment_type:
        conditions.append("vlm_garment_type = :garment_type")
        params["garment_type"] = garment_type
    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _ng(gender)
    for col, val in {"vlm_ramadan_suitable": ramadan_suitable, "vlm_hijab_friendly": hijab_friendly}.items():
        if val is not None:
            conditions.append(f"{col} = :{col}")
            params[col] = val

    where = "WHERE " + " AND ".join(conditions)

    async with SessionLocal() as db:
        rows = (await db.execute(text(f"""
            SELECT sku, name, brand, sale_price, price, discount_percentage,
                   rating_value, rating_count, vlm_description,
                   vlm_garment_type, vlm_gender, country, language,
                   product_url, is_bestseller, image_urls
            FROM {TABLE}
            {where}
            ORDER BY rating_value DESC, rating_count DESC
            LIMIT :top_k
        """), params)).mappings().all()

    return _j({
        "ok": True,
        "total_returned": len(rows),
        "results": [{**dict(r), "image_urls": _parse_images(r["image_urls"])} for r in rows],
    })


async def get_filter_values(
    country: str, language: str,
    garment_type: str | None = None,
    gender: str | None = None,
) -> str:
    ctry = _nc(country)
    lang = language.lower().strip()
    params: dict[str, Any] = {"country": ctry, "language": lang}
    conditions = ["country = :country", "language = :language"]

    if garment_type:
        conditions.append("vlm_garment_type = :garment_type")
        params["garment_type"] = garment_type
    if gender:
        conditions.append("vlm_gender = :gender")
        params["gender"] = _ng(gender)

    base = "WHERE " + " AND ".join(conditions)

    async with SessionLocal() as db:
        async def _counts(col: str):
            r = await db.execute(text(f"""
                SELECT {col}, COUNT(*) AS cnt FROM {TABLE}
                {base} AND {col} IS NOT NULL AND {col} != ''
                GROUP BY {col} ORDER BY cnt DESC LIMIT 20
            """), params)
            return r.fetchall()

        garment_types  = await _counts("vlm_garment_type")
        styles         = await _counts("vlm_style")
        color_families = await _counts("vlm_color_family")
        primary_colors = await _counts("vlm_primary_color")
        genders        = await _counts("vlm_gender")

    def _fmt(rows): return [{"value": r[0], "count": r[1]} for r in rows]
    return _j({
        "ok": True,
        "filtered_by": {"garment_type": garment_type, "gender": gender},
        "garment_types":  _fmt(garment_types),
        "styles":         _fmt(styles),
        "color_families": _fmt(color_families),
        "primary_colors": _fmt(primary_colors),
        "genders":        _fmt(genders),
    })


async def get_catalog_summary(country: str, language: str) -> str:
    ctry = _nc(country)
    lang = language.lower().strip()
    params: dict[str, Any] = {"country": ctry, "language": lang}
    base = "WHERE country = :country AND language = :language"

    async with SessionLocal() as db:
        total = (await db.execute(text(f"SELECT COUNT(*) FROM {TABLE} {base}"), params)).fetchone()[0]

        # Cross-tab: exact count per (garment_type, gender) pair
        cross = (await db.execute(text(f"""
            SELECT vlm_garment_type, vlm_gender, COUNT(*) AS cnt FROM {TABLE}
            {base}
              AND vlm_garment_type IS NOT NULL AND vlm_garment_type != ''
              AND vlm_gender       IS NOT NULL AND vlm_gender       != ''
            GROUP BY vlm_garment_type, vlm_gender
            ORDER BY vlm_garment_type, cnt DESC
        """), params)).fetchall()

        by_style = (await db.execute(text(f"""
            SELECT vlm_style, COUNT(*) AS cnt FROM {TABLE}
            {base} AND vlm_style IS NOT NULL AND vlm_style != ''
            GROUP BY vlm_style ORDER BY cnt DESC LIMIT 10
        """), params)).fetchall()

    # Restructure cross-tab into per-category dict
    categories: dict[str, dict] = {}
    for garment, gender, cnt in cross:
        if garment not in categories:
            categories[garment] = {"category": garment, "total": 0, "by_gender": {}}
        categories[garment]["total"] += cnt
        categories[garment]["by_gender"][gender] = cnt

    return _j({
        "ok": True,
        "total_products": total,
        "categories": sorted(categories.values(), key=lambda x: x["total"], reverse=True),
        "top_styles":  [{"style": r[0], "count": r[1]} for r in by_style],
        "note": "by_gender inside each category shows EXACT counts for that category+gender combination. Do NOT mix totals across categories.",
    })


async def get_product_by_sku(sku: str) -> str:
    async with SessionLocal() as db:
        row = (await db.execute(text(f"""
            SELECT sku, name, brand, product_url, price, sale_price, discount_percentage,
                   rating_value, rating_count, is_bestseller,
                   vlm_description, vlm_garment_type, vlm_garment_subtype,
                   vlm_gender, vlm_style, vlm_primary_color, vlm_color_family,
                   vlm_material_apparent, vlm_fit_type, vlm_sleeve_length,
                   vlm_modesty_level, vlm_hijab_friendly, vlm_ramadan_suitable,
                   vlm_is_abaya, vlm_pairs_well_with,
                   detail_long_description, detail_feature_bullets,
                   detail_estimated_delivery, detail_shipping_fee_message,
                   detail_store_name, detail_seller_rating,
                   all_colors, all_sizes, country, language, image_urls
            FROM {TABLE} WHERE sku = :sku
        """), {"sku": sku})).mappings().first()

    if not row:
        return _j({"ok": False, "error": f"No product found with SKU: {sku}"})

    return _j({"ok": True, "product": {**dict(row), "image_urls": _parse_images(row["image_urls"], max_count=10)}})


# ═════════════════════════════════════════════════════════════════════════════
# TOOL REGISTRY
# ═════════════════════════════════════════════════════════════════════════════

TOOL_MAP = {
    "search_products":         search_products,
    "get_products_by_filters": get_products_by_filters,
    "get_best_deals":          get_best_deals,
    "get_top_rated_products":  get_top_rated_products,
    "get_filter_values":       get_filter_values,
    "get_catalog_summary":     get_catalog_summary,
    "get_product_by_sku":      get_product_by_sku,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Semantic vector search. Use when user describes a specific item ('red abaya', 'casual dress for beach', 'sunglasses').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query":            {"type": "string"},
                    "country":          {"type": "string", "enum": ["uae", "saudi"]},
                    "language":         {"type": "string", "enum": ["ar", "en"]},
                    "top_k":            {"type": "integer", "default": 8},
                    "min_rating":       {"type": "number"},
                    "max_price":        {"type": "number"},
                    "min_price":        {"type": "number"},
                    "gender":           {"type": "string", "enum": ["men", "women", "boys", "girls", "unisex", "children"]},
                    "color_family":     {"type": "string", "description": "Broad color group, e.g. 'Red', 'Blue', 'Green'. Use EXACT English value from get_filter_values result."},
                    "primary_color":    {"type": "string", "description": "Specific color shade, e.g. 'Dark Green', 'Navy Blue', 'Rose Gold'. Use EXACT English value from get_filter_values result."},
                    "garment_type":     {"type": "string"},
                    "style":            {"type": "string"},
                    "brand_tier":       {"type": "string"},
                    "modesty_level":    {"type": "string"},
                    "ramadan_suitable": {"type": "boolean"},
                    "hijab_friendly":   {"type": "boolean"},
                    "is_abaya":         {"type": "boolean"},
                    "is_bestseller":    {"type": "boolean"},
                    "occ_work":         {"type": "boolean"},
                    "occ_casual_outing":{"type": "boolean"},
                    "occ_formal_event": {"type": "boolean"},
                    "occ_ramadan_eid":  {"type": "boolean"},
                    "occ_wedding_guest":{"type": "boolean"},
                    "occ_beach_pool":   {"type": "boolean"},
                    "occ_date_night":   {"type": "boolean"},
                },
                "required": ["query", "country", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_products_by_filters",
            "description": "Filter-based browse sorted by rating. Use when user browses by category or gender without describing a specific item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country":          {"type": "string", "enum": ["uae", "saudi"]},
                    "language":         {"type": "string", "enum": ["ar", "en"]},
                    "top_k":            {"type": "integer", "default": 10},
                    "garment_type":     {"type": "string"},
                    "gender":           {"type": "string", "enum": ["men", "women", "boys", "girls", "unisex", "children"]},
                    "style":            {"type": "string"},
                    "color_family":     {"type": "string", "description": "Broad color group. Use EXACT English value from get_filter_values result."},
                    "primary_color":    {"type": "string", "description": "Specific color shade, e.g. 'Dark Green', 'Navy Blue'. Use EXACT English value from get_filter_values result."},
                    "brand_tier":       {"type": "string"},
                    "modesty_level":    {"type": "string"},
                    "primary_occasion": {"type": "string"},
                    "age_range":        {"type": "string"},
                    "ramadan_suitable": {"type": "boolean"},
                    "hijab_friendly":   {"type": "boolean"},
                    "is_abaya":         {"type": "boolean"},
                    "is_bestseller":    {"type": "boolean"},
                    "occ_ramadan_eid":  {"type": "boolean"},
                    "occ_wedding_guest":{"type": "boolean"},
                    "min_rating":       {"type": "number"},
                    "max_price":        {"type": "number"},
                    "min_price":        {"type": "number"},
                },
                "required": ["country", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_best_deals",
            "description": "Use when user asks for deals, discounts, cheap, best value, or the most discounted item in a category. Set min_discount=0 to find any item with any discount sorted by highest discount first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country":          {"type": "string", "enum": ["uae", "saudi"]},
                    "language":         {"type": "string", "enum": ["ar", "en"]},
                    "top_k":            {"type": "integer", "default": 10},
                    "min_discount":     {"type": "number", "default": 0, "description": "Minimum discount percentage. Use 0 to find any discounted item. Use 30 only if user specifically wants big discounts."},
                    "min_rating":       {"type": "number"},
                    "garment_type":     {"type": "string"},
                    "gender":           {"type": "string", "enum": ["men", "women", "boys", "girls", "unisex", "children"]},
                    "ramadan_suitable": {"type": "boolean"},
                    "hijab_friendly":   {"type": "boolean"},
                },
                "required": ["country", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_rated_products",
            "description": "Use when user asks for best rated, most popular, or top products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country":           {"type": "string", "enum": ["uae", "saudi"]},
                    "language":          {"type": "string", "enum": ["ar", "en"]},
                    "top_k":             {"type": "integer", "default": 10},
                    "min_rating_count":  {"type": "integer", "default": 50},
                    "garment_type":      {"type": "string"},
                    "gender":            {"type": "string", "enum": ["men", "women", "boys", "girls", "unisex", "children"]},
                    "ramadan_suitable":  {"type": "boolean"},
                    "hijab_friendly":    {"type": "boolean"},
                },
                "required": ["country", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_filter_values",
            "description": "Use when user asks what colors, styles, or options are available — optionally filtered by garment_type and/or gender. Always pass garment_type and gender when the user asks about a specific category (e.g. 'what colors do men's watches come in?' → garment_type='Watch', gender='men').",
            "parameters": {
                "type": "object",
                "properties": {
                    "country":      {"type": "string", "enum": ["uae", "saudi"]},
                    "language":     {"type": "string", "enum": ["ar", "en"]},
                    "garment_type": {"type": "string", "description": "Filter to a specific category, e.g. 'Watch', 'Bag', 'Shoe'"},
                    "gender":       {"type": "string", "enum": ["men", "women", "boys", "girls", "unisex", "children"]},
                },
                "required": ["country", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_catalog_summary",
            "description": "Use when user asks what products you have, how many products are in the database, what categories exist, or wants an overview of the catalog.",
            "parameters": {
                "type": "object",
                "properties": {
                    "country":  {"type": "string", "enum": ["uae", "saudi"]},
                    "language": {"type": "string", "enum": ["ar", "en"]},
                },
                "required": ["country", "language"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_by_sku",
            "description": "Use when user asks for more details about a specific product from previous results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string"},
                },
                "required": ["sku"],
            },
        },
    },
]

# ═════════════════════════════════════════════════════════════════════════════
# SYSTEM PROMPT
# ═════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are Fahim (فاهم), a warm and knowledgeable shopping assistant for Noon.com fashion. You help users find the perfect fashion products and always give exclusive discount codes.

═══════════════════════════════
LANGUAGE — detect from user's first message and NEVER change:
• Arabic message → reply 100% in Arabic, warm and friendly tone
• English message → reply 100% in English
═══════════════════════════════
SUPPORTED SCOPE:
• Countries: UAE and Saudi Arabia ONLY
• Products: Fashion and accessories on Noon.com ONLY
• If user mentions another country → apologize warmly, explain only UAE/Saudi supported
═══════════════════════════════
CONVERSATION FLOW:
1. User sends first message → greet them, then if country is unknown ask ONCE: "هل تتسوق من الإمارات أم السعودية؟" / "Are you shopping from UAE or Saudi Arabia?"
2. Country known → write ONE warm short sentence acknowledging the request (e.g. "رائع! خلّيني أدور لك على أحسن ساعة نسائية 🔍" or "Great choice! Let me find the best options for you ✨"), THEN immediately call the tool. Never skip this sentence.
3. After getting tool results → show products in the rich format below.
4. If user follows up → same: one warm sentence, then call the tool.

Country mapping: uae/ae/dubai/emirates/الإمارات → "uae" | saudi/ksa/sa/السعودية → "saudi"
═══════════════════════════════
TOOL SELECTION — always call a tool, NEVER answer from memory:
• User names a specific product type ("فستان/dress", "ساعة/watch", "نظارة/sunglasses", "حقيبة/bag") → get_products_by_filters with garment_type set to the exact English value from the DB
• User describes a product with extra attributes ("فستان أحمر", "ساعة رجالية فاخرة") → search_products AND always pass garment_type so search stays within the right category
• User wants deals, discounts, cheap, sale, or "most discounted X" → get_best_deals (use min_discount=0 when asking for the most discounted item in a specific category)
• User wants best, most popular, top-rated → get_top_rated_products
• User asks what you have / how many products / overview of the catalog → get_catalog_summary
• User asks details on a specific product → get_product_by_sku
• User asks what colors / styles / sizes / categories / garment types are available → get_filter_values (shows primary_color and color_family from DB — answer ONLY from these results)
• User asks color of a specific product → use the primary_color field from the product result

⚠️ GARMENT TYPE FILTER — CRITICAL:
• Whenever the user names a product category (dress, watch, bag, sunglasses, shoe, etc.) you MUST pass garment_type to EVERY tool call (search_products, get_products_by_filters, get_best_deals, get_top_rated_products).
• Without garment_type, vector search will return jewelry, scarves, or other unrelated items that happen to share keywords like "حجاب" or "نسائي".
• Use the EXACT English garment_type value from the DB (e.g. "Dress", "Watch", "Bag", "Sunglasses", "Shoe"). If unsure, call get_filter_values first to find the exact value.

COLOR FILTER:
• ALWAYS use primary_color for color filtering — color_family is not reliably populated in the DB (especially for accessories like sunglasses, bags, watches).
• When user specifies any color ("أسود/black", "ذهبي/gold", "أزرق كحلي/navy blue") → call get_filter_values first with the relevant garment_type, then pass primary_color using the EXACT English value shown in the result.
• Example: user says "نظارة سوداء" → get_filter_values(garment_type="Sunglasses") → shows primary_color: Black (47) → pass primary_color="Black".
• ⚠️ CRITICAL: ALWAYS use the EXACT English value returned by get_filter_values — NEVER guess or translate color names. The DB only understands the exact English strings stored in it.

⚠️ CRITICAL: You MUST NEVER answer questions about available colors, styles, categories, or garment types from your own knowledge. The database is the only source of truth. Always call get_filter_values first and answer ONLY from the tool result.

GENDER FILTER:
• User says "نسائي / women / ladies" → pass gender="women" to every tool call.
• User says "رجالي / men / male" → pass gender="men" to every tool call.
• No gender mentioned → do NOT pass gender filter, search all.

SEARCH STRATEGY:
1. When user names a product type → use get_products_by_filters with garment_type (no embedding needed for category browsing).
2. When user describes attributes ("فستان أحمر للعمل") → use search_products with garment_type="Dress" AND the descriptive query. garment_type MUST always be passed to constrain results to the right category.
3. If 0 results → call get_filter_values to find the exact garment_type name in DB, then retry get_products_by_filters.
4. Only after all attempts return 0 → tell the user it's unavailable.
═══════════════════════════════
PRODUCT DISPLAY — use this EXACT format, no variations:

**[Brand] — [Product Name]**
![Product Name](first image URL from image_urls)
💰 [sale_price] [درهم for UAE / ريال for Saudi] ~~[original_price]~~ (خصم [discount]%)
⭐ [rating_value] ([rating_count] تقييم)
[🛒 اشتري على نون](product_url)

---

Rules (MANDATORY):
• Show 3 products maximum. Pick the best match for what the user asked.
• DO NOT repeat the product name in the body — only show it once in **bold** at the top.
• DO NOT include the description/name again after the image line.
• Image line: put ONLY the markdown image `![name](url)` — nothing else on that line.
• If image_urls is empty or missing, skip the image line entirely.
• If no discount (discount_percentage = 0 or null): show only the sale_price, no strikethrough.
• Only show products whose gender matches what the user asked for.
• After ALL products, ALWAYS add the coupon block.
═══════════════════════════════
COUPON — end every product reply with:
Arabic:   🎁 **كود خصم حصري: Fahim10** — استخدمه عند الدفع على نون للحصول على خصم إضافي! 🎉
English:  🎁 **Exclusive coupon: Fahim10** — use it at Noon.com checkout for an extra discount! 🎉
═══════════════════════════════
CURRENCY — always use the correct currency symbol:
• UAE (uae) → درهم
• Saudi Arabia (saudi) → ريال

TOOL PARAMETER VALUES (exact strings only):
• country: "uae" or "saudi"
• language: "ar" or "en"
• gender: "men", "women", "boys", "girls", "unisex", "children"
"""

def _format_tool_result(tool_name: str, raw: str) -> str:
    """Convert raw JSON tool output into clear readable text the model can't misinterpret."""
    try:
        data = json.loads(raw)
    except Exception:
        return raw

    if not data.get("ok"):
        return f"TOOL ERROR: {data.get('error', 'unknown')}"

    results = data.get("results", [])
    total   = data.get("total") or data.get("total_returned") or data.get("total_matching") or len(results)

    if tool_name == "get_catalog_summary":
        return raw  # catalog is a summary, keep as JSON

    if tool_name == "get_filter_values":
        lines = ["Available filter values in the database:\n"]
        for gt in data.get("garment_types", []):
            lines.append(f"  garment_type  : {gt['value']}  ({gt['count']} products)")
        lines.append("")
        for s in data.get("styles", []):
            lines.append(f"  style         : {s['value']}  ({s['count']} products)")
        lines.append("")
        for pc in data.get("primary_colors", []):
            lines.append(f"  primary_color : {pc['value']}  ({pc['count']} products)")
        lines.append("")
        for cf in data.get("color_families", []):
            lines.append(f"  color_family  : {cf['value']}  ({cf['count']} products)")
        lines.append("")
        for g in data.get("genders", []):
            lines.append(f"  gender        : {g['value']}  ({g['count']} products)")
        return "\n".join(lines)

    if not results:
        return "SEARCH RESULT: 0 products found."

    lines = [f"Search returned {total} products:\n"]
    for i, p in enumerate(results[:5], 1):
        images = p.get("image_urls") or []
        lines.append(f"── Product {i} ──────────────────")
        color = p.get('primary_color') or p.get('vlm_primary_color', '')
        garment = p.get('garment_type') or p.get('vlm_garment_type', '')
        gender = p.get('gender') or p.get('vlm_gender', '')
        lines.append(f"  sku          : {p.get('sku','')}")
        lines.append(f"  name         : {p.get('name','')}")
        lines.append(f"  brand        : {p.get('brand','')}")
        lines.append(f"  garment_type : {garment}")
        lines.append(f"  gender       : {gender}")
        lines.append(f"  primary_color: {color}")
        lines.append(f"  sale_price   : {p.get('sale_price','')}")
        lines.append(f"  original_price: {p.get('original_price','')}")
        lines.append(f"  discount     : {p.get('discount_percentage',0)}%")
        lines.append(f"  rating       : {p.get('rating_value','')} ({p.get('rating_count',0)} reviews)")
        lines.append(f"  url          : {_clean_url(p.get('product_url',''))}")
        lines.append(f"  image        : {images[0] if images else 'none'}")
        lines.append("")
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════════════════════
# AGENTIC LOOP
# ═════════════════════════════════════════════════════════════════════════════

TOOL_LABELS = {
    "search_products":         "🔍 Searching products",
    "get_products_by_filters": "🔍 Browsing catalog",
    "get_best_deals":          "💰 Finding best deals",
    "get_top_rated_products":  "⭐ Finding top-rated",
    "get_filter_values":       "📋 Loading categories",
    "get_catalog_summary":     "📊 Counting catalog",
    "get_product_by_sku":      "📦 Loading product details",
}


async def run_agent(messages: list[dict]) -> AsyncGenerator[tuple[str, Any], None]:
    history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    for _ in range(10):
        try:
            stream = await aoai.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT,
                messages=history,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
                stream=True,
            )
        except BadRequestError as e:
            if getattr(e, "code", None) == "content_filter" or "content_filter" in str(e):
                log.warning("Content filter triggered — retrying with sanitized history")
                # Strip image URLs and CDN links from tool messages then retry once
                clean = []
                for msg in history:
                    if msg.get("role") == "tool":
                        # Strip image CDN URLs and all noon.com URLs as fallback
                        sanitized = re.sub(r"https?://[^\s\n]+", "[url]", msg["content"])
                        clean.append({**msg, "content": sanitized})
                    else:
                        clean.append(msg)
                try:
                    stream = await aoai.chat.completions.create(
                        model=settings.AZURE_OPENAI_DEPLOYMENT,
                        messages=clean,
                        tools=TOOLS,
                        tool_choice="auto",
                        temperature=0.3,
                        stream=True,
                    )
                except Exception:
                    yield ("token", "عذراً، حدث خطأ مؤقت. من فضلك حاول مرة أخرى.")
                    return
            else:
                raise

        tool_calls: dict[int, dict] = {}
        content_parts: list[str] = []

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                content_parts.append(delta.content)
                # Buffer — only stream after we know no tool calls follow

            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                    if tc_delta.id:
                        tool_calls[idx]["id"] = tc_delta.id
                    if tc_delta.function and tc_delta.function.name:
                        tool_calls[idx]["name"] = tc_delta.function.name
                    if tc_delta.function and tc_delta.function.arguments:
                        tool_calls[idx]["arguments"] += tc_delta.function.arguments

        if not tool_calls:
            # Final response — no tools called, stream everything now
            full_response = "".join(content_parts)
            log.info("FINAL RESPONSE:\n%s", full_response)
            for part in content_parts:
                yield ("token", part)
            return

        history.append({
            "role": "assistant",
            "content": "".join(content_parts) or None,
            "tool_calls": [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls.values()
            ],
        })

        for i, tc in enumerate(tool_calls.values()):
            try:
                args = json.loads(tc["arguments"])
            except json.JSONDecodeError:
                args = {}

            # Build context-aware label for get_filter_values
            if tc["name"] == "get_filter_values":
                parts = []
                if args.get("garment_type"):
                    parts.append(args["garment_type"])
                if args.get("gender"):
                    parts.append(args["gender"])
                label = f"📋 Checking options{' for ' + ' '.join(parts) if parts else ''}"
            else:
                label = TOOL_LABELS.get(tc["name"], tc["name"])

            yield ("tool_start", {"name": tc["name"], "label": label, "index": i})

            fn = TOOL_MAP.get(tc["name"])
            if fn:
                try:
                    result = await fn(**args)
                except Exception as e:
                    result = _j({"ok": False, "error": str(e)})
            else:
                result = _j({"ok": False, "error": f"Unknown tool: {tc['name']}"})

            try:
                rd = json.loads(result)
                count = rd.get("total_returned") or rd.get("total") or rd.get("total_matching") or ""
            except Exception:
                count = ""

            log.info("Tool %s → %s results | args: %s", tc["name"], count, json.dumps(args, ensure_ascii=False)[:200])

            yield ("tool_done", {"name": tc["name"], "index": i, "count": count})

            formatted = _format_tool_result(tc["name"], result)
            log.info("Tool %s formatted (first 800):\n%s", tc["name"], formatted[:800])
            history.append({"role": "tool", "tool_call_id": tc["id"], "content": formatted})

    yield ("token", "\n\nعذراً، حدث خطأ. من فضلك حاول مرة أخرى.")


# ═════════════════════════════════════════════════════════════════════════════
# FASTAPI APP
# ═════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="Fahim Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    msgs = [{"role": m.role, "content": m.content} for m in req.messages]

    async def generate():
        try:
            async for event_type, event_data in run_agent(msgs):
                if event_type == "token":
                    data = json.dumps({"type": "token", "content": event_data}, ensure_ascii=False)
                elif event_type == "tool_start":
                    data = json.dumps({"type": "tool_start", **event_data}, ensure_ascii=False)
                elif event_type == "tool_done":
                    data = json.dumps({"type": "tool_done", **event_data}, ensure_ascii=False)
                else:
                    continue
                yield f"data: {data}\n\n"
        except Exception as e:
            log.exception("Agent error")
            data = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        finally:
            yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("chat_server:app", host="0.0.0.0", port=settings.WEB_PORT, reload=True)
