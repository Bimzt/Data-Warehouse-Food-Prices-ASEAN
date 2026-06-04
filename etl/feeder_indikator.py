import os
import json
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path("data/raw")
JSON_FILES = {
    "FP.CPI.TOTL.ZG":    RAW_DIR / "raw_worldbank_batch_1_FP_CPI_TOTL_ZG.json",
    "NY.GDP.PCAP.CD":    RAW_DIR / "raw_worldbank_batch_1_NY_GDP_PCAP_CD.json",
    "NY.GDP.MKTP.KD.ZG": RAW_DIR / "raw_worldbank_batch_1_NY_GDP_MKTP_KD_ZG.json",
    "TM.VAL.FOOD.ZS.UN": RAW_DIR / "raw_worldbank_batch_1_TM_VAL_FOOD_ZS_UN.json",
}

ISO2_TO_ISO3 = {
    "ID": "IDN",
    "KH": "KHM",
    "LA": "LAO",
    "MM": "MMR",
    "PH": "PHL",
    "TL": "TLS",
}

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise EnvironmentError("DATABASE_URL tidak ditemukan di .env")
    conn = psycopg2.connect(db_url)
    print("[feeder_indikator] Koneksi ke PostgreSQL berhasil.")
    return conn

def load_lookup_tables(conn):
    with conn.cursor() as cur:
        # negara
        cur.execute("SELECT iso3, negara_id FROM dim_negara")
        negara_map = {row[0]: row[1] for row in cur.fetchall()}

        # indikator
        cur.execute("SELECT indicator_code, indikator_id FROM dim_indikator")
        indikator_map = {row[0]: row[1] for row in cur.fetchall()}

        # waktu — hanya ambil month=1 sebagai year proxy
        cur.execute("SELECT year, waktu_id FROM dim_waktu WHERE month = 1")
        waktu_map = {row[0]: row[1] for row in cur.fetchall()}

    print(f"[feeder_indikator] Lookup loaded:")
    print(f"  negara_map  : {negara_map}")
    print(f"  indikator_map: {indikator_map}")
    print(f"  waktu_map   : {waktu_map}")
    return negara_map, indikator_map, waktu_map


def parse_json(filepath: Path, indicator_code: str,
               negara_map: dict, indikator_map: dict, waktu_map: dict) -> list[tuple]:
    if not filepath.exists():
        print(f"[feeder_indikator] File tidak ditemukan: {filepath}, dilewati.")
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        records = json.load(f)

    rows = []
    skipped_null = 0
    skipped_negara = 0
    skipped_waktu = 0

    for r in records:
        if r.get("value") is None:
            skipped_null += 1
            continue

        iso2 = r["country"]["id"]
        if iso2 not in ISO2_TO_ISO3:
            skipped_negara += 1
            continue

        iso3 = ISO2_TO_ISO3[iso2]
        if iso3 not in negara_map:
            skipped_negara += 1
            continue

        year = int(r["date"])
        if year not in waktu_map:
            skipped_waktu += 1
            continue

        negara_id    = negara_map[iso3]
        indikator_id = indikator_map[indicator_code]
        waktu_id     = waktu_map[year]
        value        = float(r["value"])
        tahun_partisi = year

        rows.append((waktu_id, negara_id, indikator_id, value, tahun_partisi))

    print(f"[feeder_indikator] {indicator_code}: "
          f"{len(rows)} baris valid | "
          f"skip null={skipped_null}, skip negara={skipped_negara}, skip waktu={skipped_waktu}")
    return rows


def insert_to_fact(conn, rows: list[tuple], indicator_code: str):
    if not rows:
        print(f"[feeder_indikator] {indicator_code}: tidak ada baris untuk diinsert.")
        return

    query = """
        INSERT INTO fact_indikator_ekonomi
            (waktu_id, negara_id, indikator_id, value, tahun_partisi)
        VALUES %s
        ON CONFLICT DO NOTHING
    """
    with conn.cursor() as cur:
        execute_values(cur, query, rows)
    conn.commit()
    print(f"[feeder_indikator] {indicator_code}: {len(rows)} baris berhasil diinsert.")


def verify(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                i.indicator_code,
                COUNT(*)        AS total_baris,
                MIN(w.year)     AS tahun_min,
                MAX(w.year)     AS tahun_max,
                COUNT(DISTINCT fi.negara_id) AS jumlah_negara
            FROM fact_indikator_ekonomi fi
            JOIN dim_indikator i ON fi.indikator_id = i.indikator_id
            JOIN dim_waktu     w ON fi.waktu_id     = w.waktu_id
            GROUP BY i.indicator_code
            ORDER BY i.indicator_code
        """)
        rows = cur.fetchall()

    print("\n[feeder_indikator] === VERIFIKASI fact_indikator_ekonomi ===")
    print(f"{'indicator_code':<25} {'total_baris':>12} {'tahun_min':>10} {'tahun_max':>10} {'negara':>8}")
    print("-" * 70)
    for row in rows:
        print(f"{row[0]:<25} {row[1]:>12} {row[2]:>10} {row[3]:>10} {row[4]:>8}")

    # Cek negara mana yang masih missing per indikator
    cur = conn.cursor()
    cur.execute("""
        SELECT
            i.indicator_code,
            n.iso3,
            n.country_name,
            COUNT(fi.id_fakta_ind) AS total_fakta
        FROM dim_indikator i
        CROSS JOIN dim_negara n
        LEFT JOIN fact_indikator_ekonomi fi
            ON fi.indikator_id = i.indikator_id
            AND fi.negara_id   = n.negara_id
        GROUP BY i.indicator_code, n.iso3, n.country_name
        HAVING COUNT(fi.id_fakta_ind) = 0
        ORDER BY i.indicator_code, n.iso3
    """)
    missing = cur.fetchall()
    cur.close()

    if missing:
        print("\n[feeder_indikator] === KOMBINASI MASIH MISSING ===")
        print(f"{'indicator_code':<25} {'iso3':>6} {'country_name':<20}")
        print("-" * 55)
        for row in missing:
            print(f"{row[0]:<25} {row[1]:>6} {row[2]:<20}")
    else:
        print("\n[feeder_indikator] Tidak ada kombinasi missing!")


def main():
    conn = get_connection()
    negara_map, indikator_map, waktu_map = load_lookup_tables(conn)

    print("\n[feeder_indikator] Truncate data lama di fact_indikator_ekonomi")
    with conn.cursor() as cur:
        cur.execute("TRUNCATE fact_indikator_ekonomi")
    conn.commit()
    print("[feeder_indikator] Truncate selesai.")

    print()
    for indicator_code, filepath in JSON_FILES.items():
        rows = parse_json(filepath, indicator_code, negara_map, indikator_map, waktu_map)
        insert_to_fact(conn, rows, indicator_code)

    verify(conn)

    conn.close()
    print("\n[feeder_indikator] Selesai. Koneksi ditutup.")


if __name__ == "__main__":
    main()
