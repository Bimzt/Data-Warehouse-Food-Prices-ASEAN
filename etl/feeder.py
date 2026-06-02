import argparse
import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROCESSED_DIR = Path("data/processed")

# Urutan load penting: dimensi harus masuk sebelum fakta (foreign key)
LOAD_ORDER = [
    "dim_waktu",
    "dim_negara",
    "dim_komoditas",
    "dim_indikator",
    "fact_harga_pangan",
]

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise EnvironmentError(
            "DATABASE_URL tidak ditemukan di .env\n"
        )
    conn = psycopg2.connect(db_url)
    print("[feeder] Koneksi ke PostgreSQL berhasil.")
    return conn


def run_ddl(conn, ddl_path: str = "sql/ddl.sql"):
    if not Path(ddl_path).exists():
        print(f"[feeder] PERINGATAN: {ddl_path} tidak ditemukan, melewati DDL.")
        return
    with open(ddl_path, "r", encoding="utf-8") as f:
        ddl = f.read()
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()
    print(f"[feeder] DDL berhasil dijalankan dari {ddl_path}")


def drop_tables(conn):
    tables = ["fact_harga_pangan", "dim_waktu", "dim_negara", "dim_komoditas", "dim_indikator"]
    with conn.cursor() as cur:
        for t in tables:
            cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
    conn.commit()
    print("[feeder] Semua tabel berhasil di-drop.")


def load_table(conn, table_name: str, df: pd.DataFrame):
    if df.empty:
        print(f"[feeder] {table_name}: DataFrame kosong, dilewati.")
        return

    cols   = list(df.columns)
    values = [tuple(row) for row in df.itertuples(index=False, name=None)]

    values = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in values
    ]

    col_str = ", ".join(cols)
    query   = f"INSERT INTO {table_name} ({col_str}) VALUES %s ON CONFLICT DO NOTHING"

    with conn.cursor() as cur:
        execute_values(cur, query, values)

    conn.commit()
    print(f"[feeder] {table_name}: {len(df):,} baris dimuat.")


def main():
    parser = argparse.ArgumentParser(description="Feeder — Fase 3 Load ke PostgreSQL")
    parser.add_argument("--reset", action="store_true",
                        help="Drop & recreate semua tabel sebelum load (hati-hati!)")
    args = parser.parse_args()

    conn = get_connection()

    if args.reset:
        print("[feeder] --reset aktif: menghapus semua tabel")
        drop_tables(conn)

    # Jalankan DDL untuk membuat tabel jika belum ada
    run_ddl(conn)

    # Load setiap tabel sesuai urutan
    print("\n[feeder] Memulai load data")
    for table_name in LOAD_ORDER:
        csv_path = PROCESSED_DIR / f"{table_name}.csv"
        if not csv_path.exists():
            print(f"[feeder] {table_name}: file tidak ditemukan ({csv_path}), dilewati.")
            continue

        df = pd.read_csv(csv_path)
        load_table(conn, table_name, df)

    conn.close()
    print("\n[feeder] Fase 3 selesai. Koneksi ditutup.")


if __name__ == "__main__":
    main()