# Data-Warehouse-Food-Prices-ASEAN
Food price volatility remains a critical challenge across ASEAN nations, where millions depend on affordable access to staple commodities. Without a centralized and structured data system, identifying trends, anomalies, and economic correlations becomes difficult for analysts and policymakers alike.
This project addresses that gap by building an end-to-end ETL pipeline and data warehouse that consolidates WFP Global Food Prices data with World Bank macroeconomic indicators including inflation, GDP per capita, and food import dependency across 10 ASEAN countries from 2024 to 2025.
Built on the Kimball star schema methodology with PostgreSQL as the backend, the system enables efficient OLAP queries through materialized views, indexing, and PostgreSQL extensions. The result is a structured, queryable foundation for analyzing how economic conditions correlate with food price movements at the commodity and country level across the region.

**Sumber Data:**
- WFP Global Food Prices Database (CSV) — via Kaggle
- World Bank Open Data API (JSON) — indikator inflasi, GDP, impor pangan

## Struktur Folder
```
project/
├── scraper/            # Extract — reader untuk WFP dan World Bank
├── etl/                # Transform — preprocessing dan integrasi data
├── sql/                # DDL, DML, view, index, extension PostgreSQL
└── data/
    ├── raw/            # Output mentah dari scraper (CSV, JSON)
    └── processed/      # Output bersih siap masuk DB
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
