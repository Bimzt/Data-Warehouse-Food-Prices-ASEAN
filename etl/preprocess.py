import json
import glob
import pandas as pd
from pathlib import Path

RAW_DIR       = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

ISO3_TO_NAME = {
    "IDN": "Indonesia",
    "KHM": "Cambodia",
    "LAO": "Lao PDR",
    "MMR": "Myanmar",
    "PHL": "Philippines",
    "SGP": "Singapore",
    "THA": "Thailand",
    "TLS": "Timor-Leste",
    "VNM": "Viet Nam",
    "MYS": "Malaysia",
}

WORLDBANK_ISO2_TO_ISO3 = {
    "ID": "IDN",
    "KH": "KHM",
    "LA": "LAO",
    "MM": "MMR",
    "PH": "PHL",
    "VN": "VNM",
}

COMMODITY_NORM = {
    "Rice - Retail":         "Rice",
    "Rice (local) - Retail": "Rice",
    "Wheat flour - Retail":  "Wheat Flour",
    "Maize - Retail":        "Maize",
    "Maize flour - Retail":  "Maize Flour",
    "Sugar - Retail":        "Sugar",
    "Palm oil - Retail":     "Palm Oil",
    "Cooking oil - Retail":  "Cooking Oil",
}

def normalize_commodity(name: str) -> str:
    if pd.isna(name):
        return "Unknown"
    clean = name.strip()
    return COMMODITY_NORM.get(clean, clean)


def load_wfp_batches() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW_DIR / "raw_wfp_batch_*.csv")))
    if not files:
        raise FileNotFoundError("Tidak ada file raw WFP ditemukan di data/raw")

    frames = []
    for f in files:
        print(f"[preprocess] Memuat WFP: {f}")
        df = pd.read_csv(f, low_memory=False)
        frames.append(df)

    raw = pd.concat(frames, ignore_index=True)
    print(f"[preprocess] Total baris WFP sebelum cleaning: {len(raw):,}")

    required = {"date", "countryiso3", "commodity", "unit", "currency", "price"}
    missing = required - set(raw.columns.str.lower())
    if missing:
        raise ValueError(f"Kolom berikut tidak ditemukan di CSV: {missing}")

    raw.columns = raw.columns.str.lower().str.strip()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw = raw.dropna(subset=["date"])
    raw = raw.drop_duplicates()
    raw = raw.dropna(subset=["price"])
    raw = raw[raw["price"] > 0]
    raw["commodity"] = raw["commodity"].apply(normalize_commodity)
    raw["year"]    = raw["date"].dt.year
    raw["month"]   = raw["date"].dt.month
    raw["quarter"] = raw["date"].dt.quarter
    raw["semester"] = raw["month"].apply(lambda m: 1 if m <= 6 else 2)

    raw["country_name"] = raw["countryiso3"].map(ISO3_TO_NAME)
    before = len(raw)
    raw = raw.dropna(subset=["country_name"])
    after = len(raw)
    if before != after:
        print(f"[preprocess] {before - after:,} baris dibuang karena kode negara tidak dikenali")

    print(f"[preprocess] Baris WFP setelah cleaning: {len(raw):,}")
    return raw

def load_worldbank_batches() -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW_DIR / "raw_worldbank_batch_*.json")))
    if not files:
        print("[preprocess] PERINGATAN: tidak ada file World Bank ditemukan, melewati.")
        return pd.DataFrame()

    frames = []
    for f in files:
        print(f"[preprocess] Memuat World Bank: {f}")
        with open(f, "r", encoding="utf-8") as fp:
            records = json.load(fp)

        rows = []
        for r in records:
            if r.get("value") is None:
                continue
            iso2 = r["country"]["id"]
            iso3 = WORLDBANK_ISO2_TO_ISO3.get(iso2)
            if iso3 is None:
                continue
            rows.append({
                "indicator_code": r["indicator"]["id"],
                "indicator_name": r["indicator"]["value"],
                "iso3":           iso3,
                "country_name":   ISO3_TO_NAME.get(iso3, iso3),
                "year":           int(r["date"]),
                "value":          float(r["value"]),
            })
        frames.append(pd.DataFrame(rows))

    if not frames:
        return pd.DataFrame()

    wb = pd.concat(frames, ignore_index=True).drop_duplicates()
    print(f"[preprocess] Total baris World Bank setelah load: {len(wb):,}")
    return wb

def build_dim_waktu(wfp: pd.DataFrame) -> pd.DataFrame:
    dim = wfp[["year", "month", "quarter", "semester"]].drop_duplicates().copy()
    dim = dim.sort_values(["year", "month"]).reset_index(drop=True)
    dim["waktu_id"] = dim.index + 1
    dim["periode"]  = dim["year"].astype(str) + "-" + dim["month"].astype(str).str.zfill(2)
    return dim[["waktu_id", "year", "month", "quarter", "semester", "periode"]]

def build_dim_negara(wfp: pd.DataFrame) -> pd.DataFrame:
    dim = wfp[["countryiso3", "country_name"]].drop_duplicates().copy()
    dim = dim.rename(columns={"countryiso3": "iso3"})
    dim = dim.sort_values("country_name").reset_index(drop=True)
    dim["negara_id"] = dim.index + 1
    dim["region"]    = "ASEAN"
    return dim[["negara_id", "country_name", "iso3", "region"]]

def build_dim_komoditas(wfp: pd.DataFrame) -> pd.DataFrame:
    cols = ["commodity"]
    if "category" in wfp.columns:
        cols.append("category")

    dim = wfp[cols].drop_duplicates().copy()
    dim.columns = ["commodity_name"] + (["category"] if "category" in wfp.columns else [])
    dim = dim.sort_values("commodity_name").reset_index(drop=True)
    dim["komoditas_id"] = dim.index + 1

    if "category" not in dim.columns:
        dim["category"] = "Uncategorized"

    return dim[["komoditas_id", "commodity_name", "category"]]


def build_dim_indikator(wb: pd.DataFrame) -> pd.DataFrame:
    if wb.empty:
        return pd.DataFrame(columns=["indikator_id", "indicator_code", "indicator_name"])

    dim = wb[["indicator_code", "indicator_name"]].drop_duplicates().copy()
    dim = dim.sort_values("indicator_code").reset_index(drop=True)
    dim["indikator_id"] = dim.index + 1
    return dim[["indikator_id", "indicator_code", "indicator_name"]]

def build_fact_harga_pangan(wfp: pd.DataFrame,
                             dim_waktu: pd.DataFrame,
                             dim_negara: pd.DataFrame,
                             dim_komoditas: pd.DataFrame) -> pd.DataFrame:
    fact = wfp.merge(
        dim_waktu[["waktu_id", "year", "month"]],
        on=["year", "month"], how="left"
    )
    fact = fact.merge(
        dim_negara[["negara_id", "country_name"]],
        on="country_name", how="left"
    )
    fact = fact.merge(
        dim_komoditas[["komoditas_id", "commodity_name"]],
        left_on="commodity", right_on="commodity_name", how="left"
    )

    agg_cols = ["waktu_id", "negara_id", "komoditas_id", "year", "unit", "currency"]
    fact_agg = fact.groupby(agg_cols, as_index=False).agg(
        avg_price=("price", "mean"),
        min_price=("price", "min"),
        max_price=("price", "max"),
        record_count=("price", "count"),
    ).round(4)

    fact_agg["tahun_partisi"] = fact_agg["year"].astype(int)
    fact_agg = fact_agg.drop(columns=["year"], errors="ignore")

    print(f"[preprocess] Baris fact_harga_pangan: {len(fact_agg):,}")
    return fact_agg


def build_fact_indikator_ekonomi(wb: pd.DataFrame,
                                  dim_negara: pd.DataFrame,
                                  dim_indikator: pd.DataFrame,
                                  dim_waktu: pd.DataFrame) -> pd.DataFrame:
    if wb.empty:
        print("[preprocess] World Bank kosong, fact_indikator_ekonomi tidak dibuat.")
        return pd.DataFrame()

    # Filter hanya tahun yang ada di dim_waktu
    valid_years = dim_waktu["year"].unique()
    wb_filtered = wb[wb["year"].isin(valid_years)].copy()
    skipped = len(wb) - len(wb_filtered)
    if skipped > 0:
        print(f"[preprocess] {skipped} baris WB di-skip")

    # Join negara_id
    fact = wb_filtered.merge(
        dim_negara[["negara_id", "iso3"]],
        on="iso3", how="left"
    )

    # Join indikator_id
    fact = fact.merge(
        dim_indikator[["indikator_id", "indicator_code"]],
        on="indicator_code", how="left"
    )

    waktu_jan = dim_waktu[dim_waktu["month"] == 1][["waktu_id", "year"]].copy()
    fact = fact.merge(waktu_jan, on="year", how="left")

    fact_out = fact[["waktu_id", "negara_id", "indikator_id", "year", "value"]].copy()
    fact_out = fact_out.rename(columns={"value": "indicator_value"})
    fact_out["tahun_partisi"] = fact_out["year"].astype(int)
    fact_out = fact_out.drop(columns=["year"])

    before = len(fact_out)
    fact_out = fact_out.dropna(subset=["waktu_id", "negara_id", "indikator_id"])
    after = len(fact_out)
    if before != after:
        print(f"[preprocess] {before - after} baris dibuang karena FK null")

    print(f"[preprocess] Baris fact_indikator_ekonomi: {len(fact_out):,}")
    return fact_out

def main():
    print("[preprocess] Memulai Fase 2 — Transform")
    wfp = load_wfp_batches()
    wb  = load_worldbank_batches()

    print("\n[preprocess] Membangun tabel dimensi")
    dim_waktu     = build_dim_waktu(wfp)
    dim_negara    = build_dim_negara(wfp)
    dim_komoditas = build_dim_komoditas(wfp)
    dim_indikator = build_dim_indikator(wb)

    print("\n[preprocess] Membangun tabel fakta")
    fact_harga    = build_fact_harga_pangan(wfp, dim_waktu, dim_negara, dim_komoditas)
    fact_indikator = build_fact_indikator_ekonomi(wb, dim_negara, dim_indikator, dim_waktu)

    print("\n[preprocess] Menyimpan output ke data/processed")
    outputs = {
        "fact_harga_pangan.csv":       fact_harga,
        "fact_indikator_ekonomi.csv":  fact_indikator,
        "dim_waktu.csv":               dim_waktu,
        "dim_negara.csv":              dim_negara,
        "dim_komoditas.csv":           dim_komoditas,
        "dim_indikator.csv":           dim_indikator,
    }
    for filename, df in outputs.items():
        if df.empty:
            print(f"  -> {filename} SKIP (kosong)")
            continue
        path = PROCESSED_DIR / filename
        df.to_csv(path, index=False)
        print(f"  -> {path} ({len(df):,} baris)")

    print("\n[preprocess] Fase 2 selesai.")


if __name__ == "__main__":
    main()