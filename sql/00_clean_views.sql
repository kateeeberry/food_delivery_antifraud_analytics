-- 00_clean_views.sql
-- Чистий шар food_delivery_clean (views над food_delivery_raw). Експортовано з pg_views 2026-11-03.
-- Правила: тестові акаунти виключені; created_at без 'Z' = Europe/Berlin -> UTC;
-- is_fulfilled = status IN ('delivered','completed'); повторні captured-платежі = duplicate_failed.
-- Порядок: спочатку orders, потім payments (payments залежить від orders).

CREATE SCHEMA IF NOT EXISTS food_delivery_clean;

CREATE OR REPLACE VIEW food_delivery_clean.orders AS
 SELECT order_id,
    user_id,
    restaurant_id,
    courier_id,
    city,
    status,
    (status = ANY (ARRAY['delivered'::text, 'completed'::text])) AS is_fulfilled,
        CASE
            WHEN (created_at ~~ '%Z'::text) THEN (created_at)::timestamp with time zone
            ELSE ((created_at)::timestamp without time zone AT TIME ZONE 'Europe/Berlin'::text)
        END AS created_at_utc,
    (delivered_at)::timestamp with time zone AS delivered_at_utc,
    (subtotal_eur)::numeric AS subtotal_eur,
    (delivery_fee_eur)::numeric AS delivery_fee_eur,
    (discount_eur)::numeric AS discount_eur,
    (tip_eur)::numeric AS tip_eur,
    (total_eur)::numeric AS total_eur,
    promo_code
   FROM food_delivery_raw.orders o
  WHERE (NOT (EXISTS ( SELECT 1
           FROM food_delivery_raw.users u
          WHERE ((u.user_id = o.user_id) AND (u.email_domain = 'foodapp-test.internal'::text)))));

CREATE OR REPLACE VIEW food_delivery_clean.payments AS
 SELECT payment_id,
    order_id,
    user_id,
    method,
    (amount_eur)::numeric AS amount_eur,
        CASE
            WHEN ((status = 'captured'::text) AND (row_number() OVER (PARTITION BY order_id, status ORDER BY created_at, (payment_id)::bigint) > 1)) THEN 'duplicate_failed'::text
            ELSE status
        END AS status_clean,
    (created_at)::timestamp with time zone AS created_at_utc
   FROM food_delivery_raw.payments p
  WHERE (EXISTS ( SELECT 1
           FROM food_delivery_clean.orders o
          WHERE (o.order_id = p.order_id)));
