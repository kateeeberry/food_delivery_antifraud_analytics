-- 01_cleaning.sql
-- Перевірка якості й підготовка даних (findings розділи 1-2). Схеми: food_delivery_raw, food_delivery_clean.
-- Кожен запит має очікуваний результат у коментарі; назви колонок звірено з information_schema.

-- 1.1 Кількості рядків у таблицях (очікується: orders 500550; payments 502413; users 50228; app_events 2688541)
SELECT 'orders' AS t, count(*) FROM food_delivery_raw.orders
UNION ALL SELECT 'payments', count(*) FROM food_delivery_raw.payments
UNION ALL SELECT 'users', count(*) FROM food_delivery_raw.users
UNION ALL SELECT 'app_events', count(*) FROM food_delivery_raw.app_events
UNION ALL SELECT 'couriers', count(*) FROM food_delivery_raw.couriers
UNION ALL SELECT 'restaurants', count(*) FROM food_delivery_raw.restaurants
UNION ALL SELECT 'refunds', count(*) FROM food_delivery_raw.refunds
UNION ALL SELECT 'promo_redemptions', count(*) FROM food_delivery_raw.promo_redemptions
UNION ALL SELECT 'support_tickets', count(*) FROM food_delivery_raw.support_tickets
UNION ALL SELECT 'fx_rates', count(*) FROM food_delivery_raw.fx_rates;

-- 1.2 created_at без 'Z' = берлінський час (очікується: 12519 замовлень, 2025-03-10..2025-03-24)
SELECT count(*) AS orders_no_z, min(created_at) AS first_ts, max(created_at) AS last_ts
FROM food_delivery_raw.orders
WHERE created_at::text NOT LIKE '%Z';

-- 1.3 Тестові акаунти (очікується: 150 акаунтів, 1717 замовлень)
SELECT count(DISTINCT u.user_id) AS test_users, count(o.order_id) AS test_orders
FROM food_delivery_raw.users u
LEFT JOIN food_delivery_raw.orders o ON o.user_id = u.user_id
WHERE u.email_domain = 'foodapp-test.internal';

-- 1.4 Виконані без courier_id / без delivered_at (очікується: 1391 / 929 у clean; у raw із тестовими акаунтами було б 1397 / 931)
SELECT
  count(*) FILTER (WHERE courier_id IS NULL)     AS no_courier,
  count(*) FILTER (WHERE delivered_at_utc IS NULL) AS no_delivered_at
FROM food_delivery_clean.orders
WHERE is_fulfilled;

-- 1.5 Замовлення з >1 списанням captured (очікується: 1863 у raw)
SELECT count(*) AS orders_with_dup_capture
FROM (
  SELECT order_id
  FROM food_delivery_raw.payments
  WHERE status = 'captured'
  GROUP BY order_id
  HAVING count(*) > 1
) t;

-- 1.6 Дублі у чистому шарі (очікується: 1855)
SELECT count(*) AS duplicate_failed
FROM food_delivery_clean.payments
WHERE status_clean = 'duplicate_failed';

-- 1.7 Від'ємні total_eur (очікується: 18)
SELECT count(*) AS negative_total
FROM food_delivery_clean.orders
WHERE total_eur < 0;
