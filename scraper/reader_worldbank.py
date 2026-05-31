import argparse
import json
import time
import requests
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Kode ISO2 negara ASEAN
ASEAN_CODES = "ID;MY;TH;PH;VN;MM;KH;LA;SG;TL"

BASE_URL = "https://api.worldbank.org/v2"
ALL_INDICATORS = {
    "FP.CPI.TOTL.ZG":   "Inflasi harga konsumen (%)",
    "NY.GDP.PCAP.CD":   "GDP per kapita (USD)",
    "NY.GDP.MKTP.KD.ZG": "Pertumbuhan GDP (%)",
    "TM.VAL.FOOD.ZS.UN": "Impor pangan (% total impor)",
}


def fetch_indicator(indicator: str, start: int, end: int) -> list[dict]:
    url = f"{BASE_URL}/country/{ASEAN_CODES}/indicator/{indicator}"
    params = {
        "format": "json",
        "date": f"{start}:{end}",
        "per_page": 500,
        "page": 1,
    }

    all_data = []
    while True:
        print(f"[reader_worldbank] GET {indicator} | tahun {start}–{end} | halaman {params['page']}")
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[reader_worldbank] ERROR request: {e}")
            break

        payload = response.json()

        # World Bank API mengembalikan [metadata, data]
        if not isinstance(payload, list) or len(payload) < 2:
            print("[reader_worldbank] Format response tidak dikenali")
            break

        metadata, records = payload[0], payload[1]

        if not records:
            break

        all_data.extend(records)

        # Cek apakah masih ada halaman berikutnya
        total_pages = metadata.get("pages", 1)
        if params["page"] >= total_pages:
            break

        params["page"] += 1
        time.sleep(0.3)

    print(f"[reader_worldbank] Total record diterima untuk {indicator}: {len(all_data)}")
    return all_data

def records_to_dataframe(records: list[dict], indicator_code: str) -> pd.DataFrame:
    rows = []
    for r in records:
        if r.get("value") is None:
            continue
        rows.append({
            "indicator_code": indicator_code,
            "indicator_name": ALL_INDICATORS.get(indicator_code, indicator_code),
            "country_code":   r["country"]["id"],
            "country_name":   r["country"]["value"],
            "year":           int(r["date"]),
            "value":          float(r["value"]),
        })
    return pd.DataFrame(rows)

def save_batch(data: list[dict], batch_num: int, indicator: str) -> str:
    safe_indicator = indicator.replace(".", "_")
    out_path = RAW_DIR / f"raw_worldbank_batch_{batch_num}_{safe_indicator}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[reader_worldbank] Tersimpan -> {out_path}")
    return str(out_path)

def main():
    parser = argparse.ArgumentParser(description="World Bank API Reader — Fase 1 Extract")
    parser.add_argument("--batch",     type=int, required=True, help="Nomor batch (1, 2, atau 3)")
    parser.add_argument("--start",     type=int, required=True, help="Tahun mulai")
    parser.add_argument("--end",       type=int, required=True, help="Tahun selesai")
    parser.add_argument("--indicator", type=str, default="all",
                        help="Kode indikator World Bank, atau 'all' untuk semua indikator")
    args = parser.parse_args()

    indicators = list(ALL_INDICATORS.keys()) if args.indicator == "all" else [args.indicator]

    for ind in indicators:
        raw_records = fetch_indicator(ind, args.start, args.end)
        if raw_records:
            save_batch(raw_records, args.batch, ind)
        else:
            print(f"[reader_worldbank] Tidak ada data untuk {ind}")

if __name__ == "__main__":
    main()