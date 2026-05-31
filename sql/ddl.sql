-- DDL Data Warehouse: Analisis Tren Harga Pangan ASEAN
-- Star Schema + Fitur OLAP Lanjut PostgreSQL
-- UAS Data Warehouse 2025/2026 | S1 Sains Data UNESA

-- 1. EXTENSIONS

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 2. DIMENSION TABLES

CREATE TABLE IF NOT EXISTS dim_waktu (
    waktu_id    SERIAL PRIMARY KEY,
    year        SMALLINT    NOT NULL,
    month       SMALLINT    NOT NULL CHECK (month BETWEEN 1 AND 12),
    quarter     SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    periode     VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dim_negara (
    negara_id       SERIAL PRIMARY KEY,
    country_name    VARCHAR(100) NOT NULL,
    region          VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_komoditas (
    komoditas_id    SERIAL PRIMARY KEY,
    commodity_name  VARCHAR(100) NOT NULL,
    category        VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_indikator (
    indikator_id        SERIAL PRIMARY KEY,
    indicator_code      VARCHAR(30) NOT NULL UNIQUE,
    indicator_name      VARCHAR(150) NOT NULL
);

-- 3. FACT TABLE dengan PARTITION BY RANGE (year)

CREATE TABLE IF NOT EXISTS fact_harga_pangan (
    id_fakta            BIGSERIAL,
    waktu_id            INT             NOT NULL REFERENCES dim_waktu(waktu_id),
    negara_id           INT             NOT NULL REFERENCES dim_negara(negara_id),
    komoditas_id        INT             NOT NULL REFERENCES dim_komoditas(komoditas_id),
    avg_price           NUMERIC(15, 4),
    min_price           NUMERIC(15, 4),
    max_price           NUMERIC(15, 4),
    record_count        INT,
    fp_cpi_totl_zg      NUMERIC(15, 4),
    ny_gdp_mktp_kd_zg   NUMERIC(15, 4),
    ny_gdp_pcap_cd      NUMERIC(15, 4),
    tm_val_food_zs_un   NUMERIC(15, 4),
    tahun_partisi       SMALLINT        NOT NULL,
    PRIMARY KEY (id_fakta, tahun_partisi)
) PARTITION BY RANGE (tahun_partisi);

CREATE TABLE IF NOT EXISTS fact_harga_pangan_2024
    PARTITION OF fact_harga_pangan
    FOR VALUES FROM (2024) TO (2025);

CREATE TABLE IF NOT EXISTS fact_harga_pangan_2025
    PARTITION OF fact_harga_pangan
    FOR VALUES FROM (2025) TO (2026);

CREATE TABLE IF NOT EXISTS fact_harga_pangan_default
    PARTITION OF fact_harga_pangan
    DEFAULT;

-- 4. INDEX

CREATE INDEX IF NOT EXISTS idx_fact_waktu_id     ON fact_harga_pangan (waktu_id);
CREATE INDEX IF NOT EXISTS idx_fact_negara_id    ON fact_harga_pangan (negara_id);
CREATE INDEX IF NOT EXISTS idx_fact_komoditas_id ON fact_harga_pangan (komoditas_id);

CREATE INDEX IF NOT EXISTS idx_fact_negara_waktu
    ON fact_harga_pangan (negara_id, waktu_id, komoditas_id);

CREATE INDEX IF NOT EXISTS idx_waktu_year_month
    ON dim_waktu (year, month);

CREATE INDEX IF NOT EXISTS idx_komoditas_nama_trgm
    ON dim_komoditas USING GIN (commodity_name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_negara_nama_trgm
    ON dim_negara USING GIN (country_name gin_trgm_ops);


-- 5. MATERIALIZED VIEWS

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_harga_bulanan AS
SELECT
    w.year,
    w.month,
    w.quarter,
    n.country_name,
    n.region,
    k.commodity_name,
    k.category,
    AVG(f.avg_price)    AS rata_harga,
    MIN(f.min_price)    AS min_harga,
    MAX(f.max_price)    AS max_harga,
    SUM(f.record_count) AS total_observasi
FROM fact_harga_pangan f
JOIN dim_waktu      w ON f.waktu_id     = w.waktu_id
JOIN dim_negara     n ON f.negara_id    = n.negara_id
JOIN dim_komoditas  k ON f.komoditas_id = k.komoditas_id
GROUP BY
    w.year, w.month, w.quarter,
    n.country_name, n.region,
    k.commodity_name, k.category
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_harga_bulanan
    ON mv_harga_bulanan (year, month, country_name, commodity_name);


CREATE MATERIALIZED VIEW IF NOT EXISTS mv_indikator_tahunan AS
SELECT
    w.year,
    n.country_name,
    n.region,
    AVG(f.fp_cpi_totl_zg)    AS avg_cpi,
    AVG(f.ny_gdp_mktp_kd_zg) AS avg_gdp_growth,
    AVG(f.ny_gdp_pcap_cd)    AS avg_gdp_per_kapita,
    AVG(f.tm_val_food_zs_un) AS avg_food_import
FROM fact_harga_pangan f
JOIN dim_waktu  w ON f.waktu_id  = w.waktu_id
JOIN dim_negara n ON f.negara_id = n.negara_id
GROUP BY
    w.year,
    n.country_name, n.region
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_indikator_tahunan
    ON mv_indikator_tahunan (year, country_name);
