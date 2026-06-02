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
            rows.append({
                "indicator_code": r["indicator"]["id"],
                "indicator_name": r["indicator"]["value"],
                "country_code":   r["country"]["id"],
                "country_name":   r["country"]["value"],
                "year":           int(r["date"]),
                "value":          float(r["value"]),
            })
        frames.append(pd.DataFrame(rows))

    if not frames:
        return pd.DataFrame()

    wb = pd.concat(frames, ignore_index=True).drop_duplicates()
    print(f"[preprocess] Total baris World Bank setelah load: {len(wb):,}")
    print(f"[preprocess] Nama negara di World Bank: {sorted(wb['country_name'].unique().tolist())}")
    return wb


def build_dim_waktu(wfp: pd.DataFrame) -> pd.DataFrame:
    dim = wfp[["year", "month", "quarter"]].drop_duplicates().copy()
    dim = dim.sort_values(["year", "month"]).reset_index(drop=True)
    dim["waktu_id"] = dim.index + 1
    dim["periode"]  = dim["year"].astype(str) + "-" + dim["month"].astype(str).str.zfill(2)
    return dim[["waktu_id", "year", "month", "quarter", "periode"]]


def build_dim_negara(wfp: pd.DataFrame) -> pd.DataFrame:
    dim = wfp[["country_name"]].drop_duplicates().copy()
    dim = dim.sort_values("country_name").reset_index(drop=True)
    dim["negara_id"] = dim.index + 1
    dim["region"]    = "ASEAN"
    return dim[["negara_id", "country_name", "region"]]


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


def build_fact(wfp: pd.DataFrame,
               wb: pd.DataFrame,
               dim_waktu: pd.DataFrame,
               dim_negara: pd.DataFrame,
               dim_komoditas: pd.DataFrame) -> pd.DataFrame:

    # Join dimensi waktu
    fact = wfp.merge(
        dim_waktu[["waktu_id", "year", "month"]],
        on=["year", "month"], how="left"
    )

    fact = fact.merge(
        dim_negara[["negara_id", "country_name"]],
        on="country_name", how="left"
    )

    # Join dimensi komoditas
    fact = fact.merge(
        dim_komoditas[["komoditas_id", "commodity_name"]],
        left_on="commodity", right_on="commodity_name", how="left"
    )

    # Agregasi rata-rata harga bulanan per negara + komoditas
    agg_cols = ["waktu_id", "negara_id", "komoditas_id", "year"]
    fact_agg = fact.groupby(agg_cols, as_index=False).agg(
        avg_price=("price", "mean"),
        min_price=("price", "min"),
        max_price=("price", "max"),
        record_count=("price", "count"),
    ).round(4)

    if not wb.empty:
        wb_pivot = wb.pivot_table(
            index=["country_name", "year"],
            columns="indicator_code",
            values="value",
            aggfunc="mean"
        ).reset_index()
        wb_pivot.columns.name = None
        wb_pivot = wb_pivot.rename(columns={
            "FP.CPI.TOTL.ZG":    "fp_cpi_totl_zg",
            "NY.GDP.PCAP.CD":    "ny_gdp_pcap_cd",
            "NY.GDP.MKTP.KD.ZG": "ny_gdp_mktp_kd_zg",
            "TM.VAL.FOOD.ZS.UN": "tm_val_food_zs_un",
        })

        for col in ["fp_cpi_totl_zg", "ny_gdp_pcap_cd", "ny_gdp_mktp_kd_zg", "tm_val_food_zs_un"]:
            if col not in wb_pivot.columns:
                wb_pivot[col] = None

        # Join World Bank ke fact via negara_id + year
        wb_with_id = wb_pivot.merge(
            dim_negara[["negara_id", "country_name"]],
            on="country_name", how="left"
        ).drop(columns=["country_name"])

        fact_agg = fact_agg.merge(
            wb_with_id,
            on=["negara_id", "year"],
            how="left"
        )
        filled = fact_agg["fp_cpi_totl_zg"].notna().sum()
        print(f"[preprocess] Baris fact dengan data World Bank terisi: {filled:,} dari {len(fact_agg):,}")

    fact_agg["tahun_partisi"] = fact_agg["year"].astype(int)
    fact_agg = fact_agg.drop(columns=["year"], errors="ignore")

    print(f"[preprocess] Baris fact_harga_pangan: {len(fact_agg):,}")
    return fact_agg


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
    fact = build_fact(wfp, wb, dim_waktu, dim_negara, dim_komoditas)

    print("\n[preprocess] Menyimpan output ke data/processed")
    outputs = {
        "fact_harga_pangan.csv": fact,
        "dim_waktu.csv":         dim_waktu,
        "dim_negara.csv":        dim_negara,
        "dim_komoditas.csv":     dim_komoditas,
        "dim_indikator.csv":     dim_indikator,
    }
    for filename, df in outputs.items():
        path = PROCESSED_DIR / filename
        df.to_csv(path, index=False)
        print(f"  -> {path} ({len(df):,} baris)")

    print("\n[preprocess] Fase 2 selesai.")


if __name__ == "__main__":
    main()