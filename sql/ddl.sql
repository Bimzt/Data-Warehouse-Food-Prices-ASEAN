-- DDL Data Warehouse: Analisis Tren Harga Pangan ASEAN
-- Constellation Schema (Kimball)
-- UAS Data Warehouse 2025/2026 | S1 Sains Data UNESA

-- EXTENSIONS

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- DIMENSION TABLES

CREATE TABLE IF NOT EXISTS dim_waktu (
    waktu_id        SERIAL      PRIMARY KEY,
    year            SMALLINT    NOT NULL,
    month           SMALLINT    NOT NULL CHECK (month BETWEEN 1 AND 12),
    quarter         SMALLINT    NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    semester        SMALLINT    CHECK (semester BETWEEN 1 AND 2),
    periode         VARCHAR(20),
    is_latest_year  BOOLEAN     DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dim_negara (
    negara_id       SERIAL      PRIMARY KEY,
    country_name    VARCHAR(100) NOT NULL,
    iso3            CHAR(3)     NOT NULL UNIQUE,
    region          VARCHAR(50),
    subregion       VARCHAR(50),
    income_group    VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_komoditas (
    komoditas_id    SERIAL      PRIMARY KEY,
    commodity_name  VARCHAR(100) NOT NULL,
    category        VARCHAR(50),
    unit            VARCHAR(20),
    unit_type       VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS dim_indikator (
    indikator_id        SERIAL      PRIMARY KEY,
    indicator_code      VARCHAR(30) NOT NULL UNIQUE,
    indicator_name      VARCHAR(150) NOT NULL,
    unit_of_measure     VARCHAR(50)
);

-- FACT TABLE 1: fact_harga_pangan

CREATE TABLE IF NOT EXISTS fact_harga_pangan (
    id_fakta        BIGSERIAL,
    waktu_id        INT         NOT NULL REFERENCES dim_waktu(waktu_id),
    negara_id       INT         NOT NULL REFERENCES dim_negara(negara_id),
    komoditas_id    INT         NOT NULL REFERENCES dim_komoditas(komoditas_id),
    avg_price       NUMERIC(15, 4),
    min_price       NUMERIC(15, 4),
    max_price       NUMERIC(15, 4),
    record_count    INT,
    unit            VARCHAR(20),
    currency        VARCHAR(10),
    tahun_partisi   SMALLINT    NOT NULL,
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

-- FACT TABLE 2: fact_indikator_ekonomi

CREATE TABLE IF NOT EXISTS fact_indikator_ekonomi (
    id_fakta_ind    BIGSERIAL,
    waktu_id        INT         NOT NULL REFERENCES dim_waktu(waktu_id),
    negara_id       INT         NOT NULL REFERENCES dim_negara(negara_id),
    indikator_id    INT         NOT NULL REFERENCES dim_indikator(indikator_id),
    indicator_value NUMERIC(20, 6),
    tahun_partisi   SMALLINT    NOT NULL,
    PRIMARY KEY (id_fakta_ind, tahun_partisi)
) PARTITION BY RANGE (tahun_partisi);

CREATE TABLE IF NOT EXISTS fact_indikator_ekonomi_pre2024
    PARTITION OF fact_indikator_ekonomi
    FOR VALUES FROM (2000) TO (2024);

CREATE TABLE IF NOT EXISTS fact_indikator_ekonomi_2024
    PARTITION OF fact_indikator_ekonomi
    FOR VALUES FROM (2024) TO (2025);

CREATE TABLE IF NOT EXISTS fact_indikator_ekonomi_2025
    PARTITION OF fact_indikator_ekonomi
    FOR VALUES FROM (2025) TO (2026);

CREATE TABLE IF NOT EXISTS fact_indikator_ekonomi_default
    PARTITION OF fact_indikator_ekonomi
    DEFAULT;

-- INDEX

-- fact_harga_pangan
CREATE INDEX IF NOT EXISTS idx_fact_waktu_id
    ON fact_harga_pangan (waktu_id);
CREATE INDEX IF NOT EXISTS idx_fact_negara_id
    ON fact_harga_pangan (negara_id);
CREATE INDEX IF NOT EXISTS idx_fact_komoditas_id
    ON fact_harga_pangan (komoditas_id);
CREATE INDEX IF NOT EXISTS idx_fact_negara_waktu
    ON fact_harga_pangan (negara_id, waktu_id, komoditas_id);

-- fact_indikator_ekonomi
CREATE INDEX IF NOT EXISTS idx_ind_waktu_id
    ON fact_indikator_ekonomi (waktu_id);
CREATE INDEX IF NOT EXISTS idx_ind_negara_id
    ON fact_indikator_ekonomi (negara_id);
CREATE INDEX IF NOT EXISTS idx_ind_indikator_id
    ON fact_indikator_ekonomi (indikator_id);
CREATE INDEX IF NOT EXISTS idx_ind_negara_indikator_waktu
    ON fact_indikator_ekonomi (negara_id, indikator_id, waktu_id);

-- dim_waktu
CREATE INDEX IF NOT EXISTS idx_waktu_year_month
    ON dim_waktu (year, month);
CREATE INDEX IF NOT EXISTS idx_waktu_year_proxy
    ON dim_waktu (year) WHERE month = 1;

-- dim_negara
CREATE INDEX IF NOT EXISTS idx_negara_iso3
    ON dim_negara (iso3);
CREATE INDEX IF NOT EXISTS idx_negara_nama_trgm
    ON dim_negara USING GIN (country_name gin_trgm_ops);

-- dim_komoditas
CREATE INDEX IF NOT EXISTS idx_komoditas_nama_trgm
    ON dim_komoditas USING GIN (commodity_name gin_trgm_ops);

-- MATERIALIZED VIEWS

-- View 1: mv_harga_bulanan
-- Sumber: fact_harga_pangan (bulanan)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_harga_bulanan AS
SELECT
    w.year,
    w.month,
    w.quarter,
    w.semester,
    n.country_name,
    n.iso3,
    n.region,
    k.commodity_name,
    k.category,
    k.unit                      AS satuan_komoditas,
    AVG(f.avg_price)            AS rata_harga,
    MIN(f.min_price)            AS min_harga,
    MAX(f.max_price)            AS max_harga,
    SUM(f.record_count)         AS total_observasi
FROM fact_harga_pangan f
JOIN dim_waktu     w ON f.waktu_id     = w.waktu_id
JOIN dim_negara    n ON f.negara_id    = n.negara_id
JOIN dim_komoditas k ON f.komoditas_id = k.komoditas_id
GROUP BY
    w.year, w.month, w.quarter, w.semester,
    n.country_name, n.iso3, n.region,
    k.commodity_name, k.category, k.unit
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_harga_bulanan
    ON mv_harga_bulanan (year, month, country_name, commodity_name);


-- View 2: mv_indikator_tahunan
-- Sumber: fact_indikator_ekonomi (tahunan)
-- Logika BENAR: MAX(CASE WHEN) bukan AVG dari nilai repetisi
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_indikator_tahunan AS
SELECT
    w.year,
    n.country_name,
    n.iso3,
    n.region,
    n.income_group,
    MAX(CASE WHEN i.indicator_code = 'FP.CPI.TOTL.ZG'
        THEN fi.indicator_value END)     AS cpi_inflation,
    MAX(CASE WHEN i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
        THEN fi.indicator_value END)     AS gdp_growth,
    MAX(CASE WHEN i.indicator_code = 'NY.GDP.PCAP.CD'
        THEN fi.indicator_value END)     AS gdp_per_kapita,
    MAX(CASE WHEN i.indicator_code = 'TM.VAL.FOOD.ZS.UN'
        THEN fi.indicator_value END)     AS food_import_pct
FROM fact_indikator_ekonomi fi
JOIN dim_waktu     w ON fi.waktu_id     = w.waktu_id
JOIN dim_negara    n ON fi.negara_id    = n.negara_id
JOIN dim_indikator i ON fi.indikator_id = i.indikator_id
GROUP BY
    w.year,
    n.country_name, n.iso3, n.region, n.income_group
WITH DATA;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_indikator_tahunan
    ON mv_indikator_tahunan (year, country_name);
