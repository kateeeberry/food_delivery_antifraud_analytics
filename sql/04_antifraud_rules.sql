-- 04_antifraud_rules.sql
-- Три правила антифроду (findings 11-13), семантика: semantic_layer.yaml
-- Схеми: food_delivery_clean (очищені замовлення), food_delivery_raw (users, refunds)
-- Порогові значення робочі й зафіксовані до оцінювання: 10 замовлень / медіана < 10 хв;
-- >= 3 акаунти на пристрої і >= 80% з WELCOME10; >= 5 замовлень і >= 30% з поверненням.
-- Це версії запитів з воркфлоу n8n (antifraud_daily): підсумковий запит кожного правила.

-- ===== 1. suspicious_courier =====
with valid as (
  select
    courier_id,
    ROUND(EXTRACT(EPOCH FROM (delivered_at_utc - created_at_utc)) / 60, 2) AS duration
  from food_delivery_clean.orders
  where is_fulfilled
    and delivered_at_utc IS NOT NULL
    and delivered_at_utc >= created_at_utc
    and courier_id is not null
),
suspicious as (
  select
    courier_id,
    count(*) as orders,
    round((percentile_cont(0.5) within group (order by duration))::numeric, 1) as median_min
  from valid
  group by 1
  having count(*) >= 10
     and percentile_cont(0.5) within group (order by duration) < 10
)
select
  count(*) as couriers,
  string_agg(
    'courier ' || courier_id || ': ' || orders || ' orders, median ' || median_min || ' min',
    E'\n' order by orders desc
  ) as list
from suspicious;

-- ===== 2. promo_ring_device =====
with rings as (
  select device_id
  from food_delivery_raw.users
  where email_domain <> 'foodapp-test.internal'
  group by 1
  having count(*) >= 3
),
per_device as (
    select
    g.device_id,
    count(distinct u.user_id) as accounts,
    count(distinct u.user_id) filter (where o.promo_code = 'WELCOME10') as promo_accounts
  from rings g
  join food_delivery_raw.users u
    on u.device_id = g.device_id
   and u.email_domain <> 'foodapp-test.internal'
  left join food_delivery_clean.orders o on o.user_id = u.user_id
  group by 1
),
ring_devices as (
  select device_id, accounts,
         row_number() over (order by accounts desc, device_id) as rn
  from per_device
  where promo_accounts * 1.0 / accounts >= 0.8
)
select
  count(*) as devices,
  coalesce(sum(accounts), 0) as accounts,
  string_agg('device ' || device_id || ': ' || accounts || ' accounts', E'\n' order by rn)
    filter (where rn <= 5) as top5
from ring_devices;

-- ===== 3. refund_abuser_user =====
with refunded as (
  select distinct order_id
  from food_delivery_raw.refunds
),
per_user as (
  select
    o.user_id,
    count(*) as orders,
    count(rf.order_id) as refunded_orders
  from food_delivery_clean.orders o
  left join refunded rf on rf.order_id = o.order_id
  where o.is_fulfilled
  group by 1
  having count(*) >= 5
),
flagged as (
  select user_id, orders, refunded_orders,
         row_number() over (order by refunded_orders desc, user_id) as rn
  from per_user
  where refunded_orders * 1.0 / orders >= 0.3
)
select
  count(*) as users,
  string_agg('user ' || user_id || ': ' || refunded_orders || ' of ' || orders || ' orders refunded', E'\n' order by rn)
    filter (where rn <= 10) as top10
from flagged;

-- ===== Підтвердження порогів і складу (findings 12-13) =====

-- 4.1 Розподіл акаунтів на пристрої, без тестових
-- (очікується: 1 акаунт - 48850 пристроїв; 2 - 500; 3-8 - разом 40 пристроїв, 228 акаунтів; розрив між 2 і 3)
WITH d AS (
  SELECT device_id, count(*) AS accounts
  FROM food_delivery_raw.users
  WHERE email_domain <> 'foodapp-test.internal'
  GROUP BY 1
)
SELECT accounts, count(*) AS devices, sum(accounts) AS users
FROM d
GROUP BY 1
ORDER BY 1;

-- 4.2 Розподіл користувачів за часткою повернень (>= 5 виконаних замовлень)
-- (очікується: усього 18253 користувачі; >=30%: 115 = 30-40%: 50, 40-50%: 32, 50-60%: 20, 60-70%: 5, 70-80%: 7, 80%+: 1)
WITH refunded AS (
  SELECT DISTINCT order_id FROM food_delivery_raw.refunds
),
per_user AS (
  SELECT o.user_id,
         count(*) AS orders,
         count(rf.order_id) AS refunded_orders
  FROM food_delivery_clean.orders o
  LEFT JOIN refunded rf ON rf.order_id = o.order_id
  WHERE o.is_fulfilled
  GROUP BY 1
  HAVING count(*) >= 5
)
SELECT
  CASE WHEN refunded_orders * 1.0 / orders < 0.3 THEN '0) <30%'
       WHEN refunded_orders * 1.0 / orders < 0.4 THEN '1) 30-40%'
       WHEN refunded_orders * 1.0 / orders < 0.5 THEN '2) 40-50%'
       WHEN refunded_orders * 1.0 / orders < 0.6 THEN '3) 50-60%'
       WHEN refunded_orders * 1.0 / orders < 0.7 THEN '4) 60-70%'
       WHEN refunded_orders * 1.0 / orders < 0.8 THEN '5) 70-80%'
       ELSE '6) 80%+' END AS refund_share_bin,
  count(*) AS users
FROM per_user
GROUP BY 1
ORDER BY 1;

-- 4.3 Склад причин повернень у групі refund_abuser_user (>=30%)
-- (очікується: 938 повернень: not_delivered 483, missing_items 412, quality 23, wrong_order 11, late_delivery 9)
WITH refunded AS (
  SELECT DISTINCT order_id FROM food_delivery_raw.refunds
),
per_user AS (
  SELECT o.user_id, count(*) AS orders, count(rf.order_id) AS refunded_orders
  FROM food_delivery_clean.orders o
  LEFT JOIN refunded rf ON rf.order_id = o.order_id
  WHERE o.is_fulfilled
  GROUP BY 1
  HAVING count(*) >= 5
),
flagged AS (
  SELECT user_id FROM per_user WHERE refunded_orders * 1.0 / orders >= 0.3
)
SELECT r.reason, count(*) AS refunds
FROM food_delivery_raw.refunds r
JOIN food_delivery_clean.orders o ON o.order_id = r.order_id AND o.is_fulfilled
WHERE o.user_id IN (SELECT user_id FROM flagged)
GROUP BY 1
ORDER BY 2 DESC;
