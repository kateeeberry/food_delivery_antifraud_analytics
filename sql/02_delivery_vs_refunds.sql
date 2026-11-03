-- 02_delivery_vs_refunds.sql
-- Швидкість доставки і повернення (findings розділ 6, знахідки 7-11 і тест Г4).
-- Валідна тривалість (semantic_layer.yaml): виконане, delivered_at_utc IS NOT NULL, delivered_at_utc >= created_at_utc.
-- courier_id тут не потрібен: умова про кур'єра є лише в правилі suspicious_courier (04_antifraud_rules.sql).

-- 2.1 Від'ємні тривалості (очікується: 231)
SELECT count(*) AS negative_duration
FROM food_delivery_clean.orders
WHERE is_fulfilled
  AND delivered_at_utc IS NOT NULL
  AND delivered_at_utc < created_at_utc;

-- 2.2 Розподіл валідних доставок за бінами (очікується: усього 463084)
WITH valid AS (
  SELECT order_id,
         ROUND(EXTRACT(EPOCH FROM (delivered_at_utc - created_at_utc)) / 60, 2) AS dur
  FROM food_delivery_clean.orders
  WHERE is_fulfilled
    AND delivered_at_utc IS NOT NULL
    AND delivered_at_utc >= created_at_utc
)
SELECT
  CASE WHEN dur < 30  THEN '1) <30'
       WHEN dur < 45  THEN '2) 30-45'
       WHEN dur < 60  THEN '3) 45-60'
       WHEN dur < 90  THEN '4) 60-90'
       WHEN dur < 120 THEN '5) 90-120'
       ELSE                '6) 120+' END AS bin,
  count(*) AS orders
FROM valid
GROUP BY 1
ORDER BY 1;

-- 2.3 late_delivery: до і після 60 хв (очікується: 583/448596 = 0.13% і 995/14488 = 6.87%)
WITH valid AS (
  SELECT order_id,
         ROUND(EXTRACT(EPOCH FROM (delivered_at_utc - created_at_utc)) / 60, 2) AS dur
  FROM food_delivery_clean.orders
  WHERE is_fulfilled
    AND delivered_at_utc IS NOT NULL
    AND delivered_at_utc >= created_at_utc
),
late AS (
  SELECT DISTINCT order_id FROM food_delivery_raw.refunds WHERE reason = 'late_delivery'
)
SELECT
  (v.dur >= 60) AS long_delivery,
  count(*)                       AS orders,
  count(l.order_id)              AS late_refunds,
  round(100.0 * count(l.order_id) / count(*), 2) AS pct
FROM valid v
LEFT JOIN late l ON l.order_id = v.order_id
GROUP BY 1
ORDER BY 1;

-- 2.4 Причини повернень у бінi <30 хв (очікується: 5813 із 5828 = not_delivered)
WITH valid AS (
  SELECT order_id,
         ROUND(EXTRACT(EPOCH FROM (delivered_at_utc - created_at_utc)) / 60, 2) AS dur
  FROM food_delivery_clean.orders
  WHERE is_fulfilled
    AND delivered_at_utc IS NOT NULL
    AND delivered_at_utc >= created_at_utc
)
SELECT r.reason, count(DISTINCT r.order_id) AS refunded_orders
FROM valid v
JOIN food_delivery_raw.refunds r ON r.order_id = v.order_id
WHERE v.dur < 30
GROUP BY 1
ORDER BY 2 DESC;
