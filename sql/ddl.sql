-- DDL: Star Schema untuk Analisis Harga Pangan ASEAN
-- Database : PostgreSQL (Supabase)
-- Dibuat   : UAS Data Warehouse 2025/2026

-- Aktifkan extension untuk performa OLAP
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- TABEL DIMENSI

-- Dimensi Waktu
CREATE TABLE IF NOT EXISTS dim_waktu (
    waktu_id  SERIAL PRIMARY KEY,
    year      SMALLINT    NOT NULL,
    month     SMALLINT    NOT NULL,
    quarter   SMALLINT    NOT NULL,
    periode   VARCHAR(7)  NOT NULL,
    UNIQUE (year, month)
);

-- Index untuk filter cepat per tahun
CREATE INDEX IF NOT EXISTS idx_dim_waktu_year
    ON dim_waktu (year);

-- Dimensi Negara
CREATE TABLE IF NOT EXISTS dim_negara (
    negara_id    SERIAL PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL,
    region       VARCHAR(50)  NOT NULL DEFAULT 'ASEAN',
    UNIQUE (country_name)
);

-- Dimensi Komoditas
CREATE TABLE IF NOT EXISTS dim_komoditas (
    komoditas_id   SERIAL PRIMARY KEY,
    commodity_name VARCHAR(200) NOT NULL,
    category       VARCHAR(100),
    UNIQUE (commodity_name)
);

-- Index trgm untuk pencarian nama komoditas (fuzzy search)
CREATE INDEX IF NOT EXISTS idx_komoditas_trgm
    ON dim_komoditas USING gin (commodity_name gin_trgm_ops);

-- Dimensi Indikator Ekonomi (World Bank)
CREATE TABLE IF NOT EXISTS dim_indikator (
    indikator_id   SERIAL PRIMARY KEY,
    indicator_code VARCHAR(50)  NOT NULL,
    indicator_name VARCHAR(300) NOT NULL,
    UNIQUE (indicator_code)
);

-- TABEL FAKTA — dengan PARTITION by tahun

CREATE TABLE IF NOT EXISTS fact_harga_pangan (
    fact_id       SERIAL,
    waktu_id      INT        NOT NULL REFERENCES dim_waktu(waktu_id),
    negara_id     INT        NOT NULL REFERENCES dim_negara(negara_id),
    komoditas_id  INT        NOT NULL REFERENCES dim_komoditas(komoditas_id),

    -- Ukuran harga
    avg_price     NUMERIC(12,4),
    min_price     NUMERIC(12,4),
    max_price     NUMERIC(12,4),
    record_count  INT,

    -- Indikator ekonomi World Bank (denormalisasi untuk performa OLAP)
    fp_cpi_totl_zg      NUMERIC(10,4),
    ny_gdp_pcap_cd      NUMERIC(14,2),
    ny_gdp_mktp_kd_zg   NUMERIC(10,4),
    tm_val_food_zs_un   NUMERIC(10,4),

    PRIMARY KEY (fact_id, waktu_id)
);

-- MATERIALIZED VIEW — agregasi bulanan per negara

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_harga_bulanan_negara AS
SELECT
    dw.year,
    dw.month,
    dw.quarter,
    dn.country_name,
    dk.commodity_name,
    dk.category,
    AVG(f.avg_price)   AS avg_price,
    MIN(f.min_price)   AS min_price,
    MAX(f.max_price)   AS max_price,
    SUM(f.record_count) AS total_records,
    AVG(f.fp_cpi_totl_zg)   AS inflasi_pct,
    AVG(f.ny_gdp_pcap_cd)   AS gdp_per_kapita
FROM fact_harga_pangan f
JOIN dim_waktu     dw ON f.waktu_id     = dw.waktu_id
JOIN dim_negara    dn ON f.negara_id    = dn.negara_id
JOIN dim_komoditas dk ON f.komoditas_id = dk.komoditas_id
GROUP BY
    dw.year, dw.month, dw.quarter,
    dn.country_name,
    dk.commodity_name, dk.category
WITH DATA;

-- Index pada materialized view untuk query analitik
CREATE INDEX IF NOT EXISTS idx_mv_harga_year_country
    ON mv_harga_bulanan_negara (year, country_name);

CREATE INDEX IF NOT EXISTS idx_mv_harga_commodity
    ON mv_harga_bulanan_negara (commodity_name);