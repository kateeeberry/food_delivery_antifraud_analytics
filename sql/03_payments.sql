-- 03_payments.sql
-- Невдалі платежі за методом, платформою, містом (findings розділ 3).
-- Очікується: 500688 платежів, 7398 failed, 1855 duplicate_failed; розріз як у таблиці findings.
-- method з payments, city з orders (join за order_id), platform з users (join за user_id; один рядок на користувача).

WITH p AS (
  SELECT pay.order_id, pay.method, pay.status_clean, u.platform, o.city
  FROM food_delivery_clean.payments pay
  JOIN food_delivery_clean.orders o ON o.order_id = pay.order_id   -- за order_id, не user_id
  JOIN food_delivery_raw.users    u ON u.user_id  = pay.user_id    -- 1 рядок на user_id, розмноження немає
)
SELECT 'Метод' AS dimension, method AS segment,
       count(*) AS payments,
       count(*) FILTER (WHERE status_clean = 'failed')           AS failed,
       count(*) FILTER (WHERE status_clean = 'duplicate_failed') AS duplicate,
       round(100.0 * count(*) FILTER (WHERE status_clean = 'failed')           / count(*), 2) AS pct_failed,
       round(100.0 * count(*) FILTER (WHERE status_clean = 'duplicate_failed') / count(*), 2) AS pct_dup
FROM p GROUP BY 2
UNION ALL
SELECT 'Платформа', platform, count(*),
       count(*) FILTER (WHERE status_clean = 'failed'),
       count(*) FILTER (WHERE status_clean = 'duplicate_failed'),
       round(100.0 * count(*) FILTER (WHERE status_clean = 'failed')           / count(*), 2),
       round(100.0 * count(*) FILTER (WHERE status_clean = 'duplicate_failed') / count(*), 2)
FROM p GROUP BY 2
UNION ALL
SELECT 'Місто', city, count(*),
       count(*) FILTER (WHERE status_clean = 'failed'),
       count(*) FILTER (WHERE status_clean = 'duplicate_failed'),
       round(100.0 * count(*) FILTER (WHERE status_clean = 'failed')           / count(*), 2),
       round(100.0 * count(*) FILTER (WHERE status_clean = 'duplicate_failed') / count(*), 2)
FROM p GROUP BY 2
ORDER BY 1, 3 DESC;
