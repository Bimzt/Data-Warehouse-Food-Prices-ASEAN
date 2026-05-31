# Data-Warehouse-Food-Prices-ASEAN
ETL pipeline and data warehouse for analyzing food commodity price trends across ASEAN countries, integrating WFP Global Food Prices dataset and World Bank economic indicators using Kimball star schema on PostgreSQL.

**Sumber Data:**
- WFP Global Food Prices Database (CSV) — via Kaggle
- World Bank Open Data API (JSON) — indikator inflasi, GDP, impor pangan

## Struktur Folder
```
project/
├── scraper/            # Extract — reader untuk WFP dan World Bank
├── etl/                # Transform — preprocessing dan integrasi data
├── sql/                # DDL, DML, view, index, extension PostgreSQL
├── data/
│   ├── raw/            # Output mentah dari scraper (CSV, JSON)
│   └── processed/      # Output bersih siap masuk DB
└── docs/               # Dokumentasi tambahan
```

## Alur Pipeline
```
[WFP CSV (Kaggle)]   ──┐
                       ├──► reader ──► raw/ ──► preprocess ──► processed/ ──► feeder ──► PostgreSQL
[World Bank API]     ──┘
```

## Cara Menjalankan

### 1. Install dependency
```bash
pip install -r requirements.txt
```

### 2. Konfigurasi
Salin `.env.example` ke `.env`, lalu isi:
```bash
cp .env.example .env
```

### 3. Jalankan pipeline lengkap
```bash
# Extract
python scraper/reader_wfp.py
python scraper/reader_worldbank.py

# Transform
python etl/preprocess.py

# Load
python etl/feeder.py
```

### 4. Atau jalankan via notebook
Buka `notebooks/pipeline.ipynb` dan jalankan semua cell secara berurutan.

## Requirements
Lihat `requirements.txt`
