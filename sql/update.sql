-- BLOK 0: SAFETY CHECK

SELECT 'fact_harga_pangan'  AS tabel, COUNT(*) AS total_baris FROM fact_harga_pangan
UNION ALL
SELECT 'dim_negara',                  COUNT(*)               FROM dim_negara
UNION ALL
SELECT 'dim_komoditas',               COUNT(*)               FROM dim_komoditas
UNION ALL
SELECT 'dim_waktu',                   COUNT(*)               FROM dim_waktu
UNION ALL
SELECT 'dim_indikator',               COUNT(*)               FROM dim_indikator;


-- BLOK 1: BACKUP DATA INDIKATOR DARI fact_harga_pangan

CREATE TABLE IF NOT EXISTS _migration_indikator_backup AS
SELECT
    negara_id,
    waktu_id,
    tahun_partisi,
    fp_cpi_totl_zg,
    ny_gdp_mktp_kd_zg,
    ny_gdp_pcap_cd,
    tm_val_food_zs_un
FROM fact_harga_pangan;
SELECT COUNT(*) AS total_backup FROM _migration_indikator_backup;

-- BLOK 2: PERBAIKI dim_negara

ALTER TABLE dim_negara
    ADD COLUMN IF NOT EXISTS iso3         CHAR(3),
    ADD COLUMN IF NOT EXISTS subregion    VARCHAR(50),
    ADD COLUMN IF NOT EXISTS income_group VARCHAR(50);

UPDATE dim_negara SET iso3 = country_name;
UPDATE dim_negara SET country_name = 'Indonesia'          WHERE iso3 = 'IDN';
UPDATE dim_negara SET country_name = 'Cambodia'           WHERE iso3 = 'KHM';
UPDATE dim_negara SET country_name = 'Lao PDR'            WHERE iso3 = 'LAO';
UPDATE dim_negara SET country_name = 'Myanmar'            WHERE iso3 = 'MMR';
UPDATE dim_negara SET country_name = 'Philippines'        WHERE iso3 = 'PHL';
UPDATE dim_negara SET country_name = 'Timor-Leste'        WHERE iso3 = 'TLS';
UPDATE dim_negara SET
    subregion    = 'Southeast Asia',
    income_group = 'Lower middle income'
WHERE iso3 = 'IDN';

UPDATE dim_negara SET
    subregion    = 'Southeast Asia',
    income_group = 'Lower middle income'
WHERE iso3 = 'KHM';

UPDATE dim_negara SET
    subregion    = 'Southeast Asia',
    income_group = 'Lower middle income'
WHERE iso3 = 'LAO';

UPDATE dim_negara SET
    subregion    = 'Southeast Asia',
    income_group = 'Lower middle income'
WHERE iso3 = 'MMR';

UPDATE dim_negara SET
    subregion    = 'Southeast Asia',
    income_group = 'Lower middle income'
WHERE iso3 = 'PHL';

UPDATE dim_negara SET
    subregion    = 'Southeast Asia',
    income_group = 'Lower middle income'
WHERE iso3 = 'TLS';
ALTER TABLE dim_negara
    ALTER COLUMN iso3 SET NOT NULL;

ALTER TABLE dim_negara
    ADD CONSTRAINT dim_negara_iso3_unique UNIQUE (iso3);
SELECT negara_id, country_name, iso3, subregion, income_group
FROM dim_negara ORDER BY negara_id;


-- BLOK 3: TAMBAH KOLOM BARU KE DIMENSI LAIN

ALTER TABLE dim_komoditas
    ADD COLUMN IF NOT EXISTS unit      VARCHAR(20),
    ADD COLUMN IF NOT EXISTS unit_type VARCHAR(20);

ALTER TABLE dim_waktu
    ADD COLUMN IF NOT EXISTS semester      SMALLINT,
    ADD COLUMN IF NOT EXISTS is_latest_year BOOLEAN DEFAULT FALSE;

UPDATE dim_waktu
SET semester = CASE WHEN month <= 6 THEN 1 ELSE 2 END;

UPDATE dim_waktu
SET is_latest_year = TRUE
WHERE year = (SELECT MAX(year) FROM dim_waktu);

ALTER TABLE dim_indikator
    ADD COLUMN IF NOT EXISTS unit_of_measure VARCHAR(50);

UPDATE dim_indikator SET unit_of_measure = '%'   WHERE indicator_code = 'FP.CPI.TOTL.ZG';
UPDATE dim_indikator SET unit_of_measure = '%'   WHERE indicator_code = 'NY.GDP.MKTP.KD.ZG';
UPDATE dim_indikator SET unit_of_measure = 'USD' WHERE indicator_code = 'NY.GDP.PCAP.CD';
UPDATE dim_indikator SET unit_of_measure = '%'   WHERE indicator_code = 'TM.VAL.FOOD.ZS.UN';

SELECT * FROM dim_indikator;

-- BLOK 4: BUAT fact_indikator_ekonomi

CREATE TABLE IF NOT EXISTS fact_indikator_ekonomi (
    id_fakta_ind    BIGSERIAL,
    waktu_id        INT         NOT NULL REFERENCES dim_waktu(waktu_id),
    negara_id       INT         NOT NULL REFERENCES dim_negara(negara_id),
    indikator_id    INT         NOT NULL REFERENCES dim_indikator(indikator_id),
    value           NUMERIC(20, 6),
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

-- BLOK 5: MIGRATE DATA INDIKATOR KE fact_indikator_ekonomi

INSERT INTO fact_indikator_ekonomi
    (waktu_id, negara_id, indikator_id, value, tahun_partisi)

SELECT DISTINCT ON (b.negara_id, w.waktu_id, i.indikator_id)
    w.waktu_id,
    b.negara_id,
    i.indikator_id,
    b.fp_cpi_totl_zg AS value,
    b.tahun_partisi
FROM _migration_indikator_backup b
JOIN dim_waktu     w ON w.year = b.tahun_partisi AND w.month = 1
JOIN dim_indikator i ON i.indicator_code = 'FP.CPI.TOTL.ZG'
WHERE b.fp_cpi_totl_zg IS NOT NULL

UNION ALL

SELECT DISTINCT ON (b.negara_id, w.waktu_id, i.indikator_id)
    w.waktu_id, b.negara_id, i.indikator_id,
    b.ny_gdp_mktp_kd_zg, b.tahun_partisi
FROM _migration_indikator_backup b
JOIN dim_waktu     w ON w.year = b.tahun_partisi AND w.month = 1
JOIN dim_indikator i ON i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
WHERE b.ny_gdp_mktp_kd_zg IS NOT NULL

UNION ALL

SELECT DISTINCT ON (b.negara_id, w.waktu_id, i.indikator_id)
    w.waktu_id, b.negara_id, i.indikator_id,
    b.ny_gdp_pcap_cd, b.tahun_partisi
FROM _migration_indikator_backup b
JOIN dim_waktu     w ON w.year = b.tahun_partisi AND w.month = 1
JOIN dim_indikator i ON i.indicator_code = 'NY.GDP.PCAP.CD'
WHERE b.ny_gdp_pcap_cd IS NOT NULL

UNION ALL

SELECT DISTINCT ON (b.negara_id, w.waktu_id, i.indikator_id)
    w.waktu_id, b.negara_id, i.indikator_id,
    b.tm_val_food_zs_un, b.tahun_partisi
FROM _migration_indikator_backup b
JOIN dim_waktu     w ON w.year = b.tahun_partisi AND w.month = 1
JOIN dim_indikator i ON i.indicator_code = 'TM.VAL.FOOD.ZS.UN'
WHERE b.tm_val_food_zs_un IS NOT NULL;
SELECT
    i.indicator_code,
    COUNT(*) AS total_baris,
    COUNT(value) AS non_null_value
FROM fact_indikator_ekonomi fi
JOIN dim_indikator i ON fi.indikator_id = i.indikator_id
GROUP BY i.indicator_code
ORDER BY i.indicator_code;

-- BLOK 6: DROP KOLOM INDIKATOR DARI fact_harga_pangan
-- JANGAN jalankan sebelum verifikasi blok 5 OK

ALTER TABLE fact_harga_pangan
    DROP COLUMN IF EXISTS fp_cpi_totl_zg,
    DROP COLUMN IF EXISTS ny_gdp_mktp_kd_zg,
    DROP COLUMN IF EXISTS ny_gdp_pcap_cd,
    DROP COLUMN IF EXISTS tm_val_food_zs_un;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'fact_harga_pangan'
ORDER BY ordinal_position;


-- BLOK 7: INDEX BARU

CREATE INDEX IF NOT EXISTS idx_ind_waktu_id
    ON fact_indikator_ekonomi (waktu_id);

CREATE INDEX IF NOT EXISTS idx_ind_negara_id
    ON fact_indikator_ekonomi (negara_id);

CREATE INDEX IF NOT EXISTS idx_ind_indikator_id
    ON fact_indikator_ekonomi (indikator_id);

CREATE INDEX IF NOT EXISTS idx_ind_negara_indikator_waktu
    ON fact_indikator_ekonomi (negara_id, indikator_id, waktu_id);

CREATE INDEX IF NOT EXISTS idx_waktu_year_proxy
    ON dim_waktu (year) WHERE month = 1;

CREATE INDEX IF NOT EXISTS idx_negara_iso3
    ON dim_negara (iso3);

-- BLOK 8: REBUILD MATERIALIZED VIEWS
-- Drop dulu karena struktur berubah (kolom baru di dim)

DROP MATERIALIZED VIEW IF EXISTS mv_indikator_tahunan;
DROP MATERIALIZED VIEW IF EXISTS mv_harga_bulanan;

CREATE MATERIALIZED VIEW mv_harga_bulanan AS
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
    k.unit,
    AVG(f.avg_price)    AS rata_harga,
    MIN(f.min_price)    AS min_harga,
    MAX(f.max_price)    AS max_harga,
    SUM(f.record_count) AS total_observasi
FROM fact_harga_pangan f
JOIN dim_waktu     w ON f.waktu_id     = w.waktu_id
JOIN dim_negara    n ON f.negara_id    = n.negara_id
JOIN dim_komoditas k ON f.komoditas_id = k.komoditas_id
GROUP BY
    w.year, w.month, w.quarter, w.semester,
    n.country_name, n.iso3, n.region,
    k.commodity_name, k.category, k.unit
WITH DATA;

CREATE UNIQUE INDEX idx_mv_harga_bulanan
    ON mv_harga_bulanan (year, month, country_name, commodity_name);

CREATE MATERIALIZED VIEW mv_indikator_tahunan AS
SELECT
    w.year,
    n.country_name,
    n.iso3,
    n.region,
    n.income_group,
    MAX(CASE WHEN i.indicator_code = 'FP.CPI.TOTL.ZG'
        THEN fi.value END)  AS cpi_inflation,
    MAX(CASE WHEN i.indicator_code = 'NY.GDP.MKTP.KD.ZG'
        THEN fi.value END)  AS gdp_growth,
    MAX(CASE WHEN i.indicator_code = 'NY.GDP.PCAP.CD'
        THEN fi.value END)  AS gdp_per_kapita,
    MAX(CASE WHEN i.indicator_code = 'TM.VAL.FOOD.ZS.UN'
        THEN fi.value END)  AS food_import_pct
FROM fact_indikator_ekonomi fi
JOIN dim_waktu     w ON fi.waktu_id     = w.waktu_id
JOIN dim_negara    n ON fi.negara_id    = n.negara_id
JOIN dim_indikator i ON fi.indikator_id = i.indikator_id
GROUP BY
    w.year,
    n.country_name, n.iso3, n.region, n.income_group
WITH DATA;

CREATE UNIQUE INDEX idx_mv_indikator_tahunan
    ON mv_indikator_tahunan (year, country_name);


-- BLOK 9: CLEANUP BACKUP TABLE
-- Jalankan HANYA setelah semua blok di atas verified OK

-- DROP TABLE IF EXISTS _migration_indikator_backup;


-- BLOK 10: FINAL VERIFICATION

SELECT
    'fact_harga_pangan'       AS fact_table,
    COUNT(*)                  AS total_baris
FROM fact_harga_pangan
UNION ALL
SELECT
    'fact_indikator_ekonomi',
    COUNT(*)
FROM fact_indikator_ekonomi;

SELECT
    i.indicator_code,
    i.indicator_name,
    COUNT(fi.id_fakta_ind) AS total_fakta
FROM dim_indikator i
LEFT JOIN fact_indikator_ekonomi fi ON i.indikator_id = fi.indikator_id
GROUP BY i.indicator_code, i.indicator_name
ORDER BY i.indicator_code;
SELECT * FROM mv_indikator_tahunan ORDER BY year, country_name;