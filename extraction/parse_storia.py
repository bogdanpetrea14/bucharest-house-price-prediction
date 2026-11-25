"""Parsare: data/raw/storia/*.json -> data/final/storia.csv (+ storia_clean.csv).

Un fisier JSON = un anunt = un rand. Descrierea si datele personale NU se salveaza,
doar flag-uri derivate din ea. Fiecare pas de filtrare e numarat (tabelul de pierderi).
"""
import html
import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw" / "storia"
FINAL_DIR = ROOT / "data" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

# Locatia implicita din centru (observata in date: ~44.4355, 26.1027, radius=100)
DEFAULT_LAT, DEFAULT_LON = 44.4355, 26.1027
DEFAULT_TOL = 0.005  # grade (~500 m)

# Praguri pentru valori implauzibile (justificate dupa percentile in EDA)
PPM_MIN, PPM_MAX = 500, 12000      # EUR / m2
AREA_MIN, AREA_MAX = 15, 400       # m2


# ---------- helpere ----------
def first(value):
    """Listele cu un element (['2']) -> elementul; altfel valoarea."""
    if isinstance(value, list):
        return value[0] if value else None
    return value


def to_float(value):
    value = first(value)
    if value in (None, ""):
        return np.nan
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return np.nan


def parse_floor(raw):
    """floor_3 -> 3, ground_floor -> 0, cellar -> -1, floor_higher_10 -> 11, garret -> NaN."""
    raw = first(raw)
    if raw is None:
        return np.nan
    if raw == "ground_floor":
        return 0
    if raw == "cellar":
        return -1
    if raw == "floor_higher_10":
        return 11
    m = re.fullmatch(r"floor_(\d+)", raw)
    return int(m.group(1)) if m else np.nan


def get_location_levels(ad):
    locs = (ad.get("location") or {}).get("reverseGeocoding", {}).get("locations", []) or []
    return {l.get("locationLevel"): l.get("name") for l in locs}


def sector_number(name):
    if not name:
        return np.nan
    m = re.search(r"(\d)", name)
    return int(m.group(1)) if m else np.nan


def price_currency(ad):
    for ch in ad.get("characteristics", []) or []:
        if ch.get("key") == "price":
            return ch.get("currency")
    return None


def clean_text(raw):
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    return re.sub(r"\s+", " ", text).lower()


def description_flags(desc_raw):
    d = clean_text(desc_raw)
    # sectorul mentionat in text (doar daca e unul singur, neambiguu)
    sect = set(re.findall(r"sect(?:or(?:ul)?)?\.?\s*([1-6])\b", d))
    return {
        "desc_sector": int(next(iter(sect))) if len(sect) == 1 else np.nan,
        "txt_metro": int("metrou" in d),
        "txt_renovated": int(bool(re.search(r"renovat|reabilitat|modernizat|recent refacut", d))),
        "txt_new_building": int(bool(re.search(r"bloc nou|constructie noua|finalizat|ansamblu", d))),
        "txt_parking": int(bool(re.search(r"parcare|garaj", d))),
        "txt_rented": int(bool(re.search(r"inchiriat|chiria|chiriasi", d.replace("î", "i").replace("â", "a")))),
        "txt_vat": int("tva" in d),
        "txt_len": len(d),
    }


# ---------- parsarea unui anunt ----------
def parse_ad(ad):
    t = ad.get("target") or {}
    loc = ad.get("location") or {}
    coords = loc.get("coordinates") or {}
    levels = get_location_levels(ad)
    extras = t.get("Extras_types") or []
    equip = t.get("Equipment_types") or []
    created = ad.get("createdAt")

    row = {
        "id": ad.get("id"),
        "created_at": created[:10] if created else None,
        "offer_type": t.get("OfferType"),
        "category_type": (ad.get("adCategory") or {}).get("type"),
        "proper_type": t.get("ProperType"),
        "currency": price_currency(ad),
        "seller_id": t.get("seller_id"),
        "seller_type": t.get("user_type"),
        "creation_source": ad.get("creationSource"),
        "price_eur": to_float(t.get("Price")),
        "area": to_float(t.get("Area")),
        "rooms": to_float(t.get("Rooms_num")),
        "floor": parse_floor(t.get("Floor_no")),
        "floor_raw": first(t.get("Floor_no")),
        "building_floors": to_float(t.get("Building_floors_num")),
        "build_year": to_float(t.get("Build_year")),
        "market": first(t.get("MarketType")),
        "construction_status": first(t.get("Construction_status")),
        "heating": first(t.get("Heating")),
        "building_material": first(t.get("Building_material")),
        "building_type": first(t.get("Building_type")),
        "divisioning_type": first(t.get("Divisioning_type")),
        "windows_type": first(t.get("Windows_type")),
        "has_lift": int("lift" in extras),
        "has_balcony": int("balcony" in extras),
        "has_ac": int("air_conditioning" in extras),
        "separate_kitchen": int("separate_kitchen" in extras),
        "furnished": int("furniture" in equip),
        "county": levels.get("county"),
        "sector": sector_number(levels.get("sector")),
        "district": levels.get("district"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "coord_radius": (loc.get("mapDetails") or {}).get("radius"),
    }
    row.update(description_flags(ad.get("description")))
    return row


# ---------- pipeline ----------
def main():
    rows, corrupt = [], 0
    files = sorted(RAW_DIR.glob("*.json"))
    for p in files:
        try:
            ad = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            corrupt += 1
            continue
        rows.append(parse_ad(ad))
    df = pd.DataFrame(rows)

    funnel = [("fisiere raw", len(files)), ("citite (fara corupte)", len(df))]

    def step(name, mask):
        nonlocal df
        before = len(df)
        df = df[mask(df)].copy()
        funnel.append((f"- {name}", before - len(df)))

    # 1. filtre structurale
    step("nu e vanzare de apartament", lambda d: (d.category_type == "SELL") & (d.proper_type == "apartament") & (d.offer_type == "vanzare"))
    step("moneda != EUR", lambda d: d.currency == "EUR")
    step("in afara Bucurestiului (fara sector)", lambda d: d.sector.notna() & (d.county == "Bucuresti"))
    step("pret sau suprafata lipsa/<=0", lambda d: (d.price_eur > 0) & (d.area > 0))
    step("fara coordonate", lambda d: d.lat.notna() & d.lon.notna() & (d.lat != 0))
    funnel.append(("= valide (storia.csv)", len(df)))

    # 2. derivate + flag-uri de calitate (marcam, nu stergem)
    df["price_per_m"] = df.price_eur / df.area
    df["floor_higher_10"] = (df.floor_raw == "floor_higher_10").astype(int)
    df["is_attic_or_cellar"] = df.floor_raw.isin(["garret", "cellar"]).astype(int)
    df["suspect_location"] = (
        (df.coord_radius.fillna(0) > 0)
        & ((df.lat - DEFAULT_LAT).abs() < DEFAULT_TOL)
        & ((df.lon - DEFAULT_LON).abs() < DEFAULT_TOL)
    ).astype(int)
    df["sector_mismatch"] = (df.desc_sector.notna() & (df.desc_sector != df.sector)).astype(int)
    df["floor_gt_building"] = (df.floor > df.building_floors).astype(int)
    df["implausible"] = (
        (df.price_per_m < PPM_MIN) | (df.price_per_m > PPM_MAX)
        | (df.area < AREA_MIN) | (df.area > AREA_MAX)
        | (df.build_year.notna() & ((df.build_year < 1800) | (df.build_year > 2030)))
    ).astype(int)

    # duplicate: aceeasi combinatie vanzator+pret+suprafata+etaj+coordonate; pastram cel mai recent
    key = ["seller_id", "price_eur", "area", "floor", "rooms"]
    df["_lat"], df["_lon"] = df.lat.round(4), df.lon.round(4)
    df = df.sort_values("created_at", ascending=False)
    df["is_duplicate"] = df.duplicated(subset=key + ["_lat", "_lon"], keep="first").astype(int)
    df = df.drop(columns=["_lat", "_lon"]).sort_values("id")

    # 3. salvare
    df.to_csv(FINAL_DIR / "storia.csv", index=False)
    clean = df[(df.is_duplicate == 0) & (df.implausible == 0)]
    clean.to_csv(FINAL_DIR / "storia_clean.csv", index=False)

    # 4. raport
    print("\n=== PIERDERI ===")
    for name, n in funnel:
        print(f"{name:45s} {n:>7d}")
    print(f"{'corupte':45s} {corrupt:>7d}")
    print(f"\nflaguri in storia.csv ({len(df)} randuri):")
    for c in ["is_duplicate", "implausible", "suspect_location", "sector_mismatch", "floor_gt_building"]:
        print(f"  {c:20s} {int(df[c].sum()):>6d}  ({df[c].mean():.1%})")
    print(f"\nstoria_clean.csv: {len(clean)} randuri")
    print("\nanunturi pe sector (clean):")
    print(clean.sector.value_counts().sort_index().to_string())
    print("\nvalori lipsa (clean, %):")
    print((clean.isna().mean() * 100).round(1).sort_values(ascending=False).head(15).to_string())


if __name__ == "__main__":
    main()
