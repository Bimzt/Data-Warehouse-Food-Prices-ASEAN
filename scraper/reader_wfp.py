import argparse
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Daftar negara ASEAN berdasarkan nama di dataset WFP
ASEAN_COUNTRIES = [
    "IDN", "MYS", "THA", "PHL",
    "VNM", "MMR", "KHM", "LAO",
    "SGP", "TLS"
]

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def load_wfp(csv_path: str) -> pd.DataFrame:
    print(f"[reader_wfp] Membaca file: {csv_path}")
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"[reader_wfp] Total baris dimuat: {len(df):,}")
    return df


def filter_batch(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    mask_year = df["date"].dt.year.between(start_year, end_year)
    mask_country = df["countryiso3"].str.strip().isin(ASEAN_COUNTRIES)

    result = df[mask_year & mask_country].copy()
    print(f"[reader_wfp] Baris setelah filter ({start_year}–{end_year}, ASEAN): {len(result):,}")
    return result


def save_batch(df: pd.DataFrame, batch_num: int) -> str:
    out_path = RAW_DIR / f"raw_wfp_batch_{batch_num}.csv"
    df.to_csv(out_path, index=False)
    print(f"[reader_wfp] Tersimpan -> {out_path}")
    return str(out_path)

WFP_FILES = {
    2024: Path("data") / "raw" / "wfp_food_prices_global_2024.csv",
    2025: Path("data") / "raw" / "wfp_food_prices_global_2025.csv",
}

def main():
    parser = argparse.ArgumentParser(description="WFP CSV Reader — Fase 1 Extract")
    parser.add_argument("--batch",  type=int, required=True, help="Nomor batch (1, 2, atau 3)")
    parser.add_argument("--start",  type=int, required=True, help="Tahun mulai")
    parser.add_argument("--end",    type=int, required=True, help="Tahun selesai")
    args = parser.parse_args()
    years = range(args.start, args.end + 1)
    frames = []
    for year in years:
        path = WFP_FILES.get(year)
        if not path or not Path(path).exists():
            print(f"File untuk tahun {year} tidak ditemukan ({path}), dilewati.")
            continue
        df = load_wfp(path)
        frames.append(df)
    if not frames:
        print("Tidak ada file yang berhasil dimuat.")
        return
    combined = pd.concat(frames, ignore_index=True)
    batch_df = filter_batch(combined, args.start, args.end)
    save_batch(batch_df, args.batch)

if __name__ == "__main__":
    main()
