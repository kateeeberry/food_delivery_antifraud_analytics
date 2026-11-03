#!/usr/bin/env python3
"""
Synthetic food-delivery marketplace: Germany (5 cities), prices in EUR (base currency), calendar year 2025.
Fixed seed => reproducible. Writes CSV tables + a separate _ground_truth/ folder with everything
that was deliberately injected (defects, fraud, decoys), so detection can be scored later.

Usage: python generate_food_delivery_data.py --seed 42 --users 50000 --target_orders 500000 --out food_delivery_data
"""
import argparse, json, os
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--users", type=int, default=50000)
ap.add_argument("--target_orders", type=int, default=500000)
ap.add_argument("--out", default="food_delivery_data")
a = ap.parse_args()
rng = np.random.default_rng(a.seed)
OUT = a.out
GT = os.path.join(OUT, "_ground_truth")
os.makedirs(GT, exist_ok=True)

# ----------------------------------------------------------------------------- constants
START = pd.Timestamp("2025-01-01")
ND = 365
DAYS = pd.date_range(START, periods=ND, freq="D")
TZ = "Europe/Berlin"
CITIES = np.array(["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt"])
CITY_W = np.array([.32, .20, .20, .16, .12])
CITY_PRICE = {"Berlin": .98, "Hamburg": 1.03, "Munich": 1.12, "Cologne": .97, "Frankfurt": 1.08}
CITY_BASE_MIN = {"Berlin": 31, "Hamburg": 29, "Munich": 30, "Cologne": 28, "Frankfurt": 29}
FRA_IDX = int((pd.Timestamp("2025-06-01") - START).days)  # Frankfurt launch day index
CH = np.array(["organic", "paid_social", "search", "referral", "partner"])
CH_W = np.array([.30, .28, .20, .14, .08])
MEAN_LIFE = {"organic": 170, "paid_social": 85, "search": 140, "referral": 230, "partner": 110}
METH = np.array(["card", "paypal", "sepa", "applepay", "klarna"])
METH_W = np.array([.50, .25, .10, .09, .06])
DOMAINS = np.array(["gmail.com", "web.de", "gmx.de", "t-online.de", "icloud.com", "outlook.com", "other"])
DOM_W = np.array([.35, .15, .12, .08, .10, .10, .10])
HOUR_W = np.array([1, .6, .3, .2, .2, .3, .6, 1.2, 2, 2.5, 3.5, 6, 9, 8, 5, 3.5,
                   4, 6, 10, 11, 9, 6, 3.5, 2], float)
HOUR_W /= HOUR_W.sum()

dow_m = np.array([.92, .90, .95, 1.0, 1.15, 1.2, 1.1])
MONTH_M = {1: 1.10, 2: 1.08, 3: 1.0, 4: .98, 5: .97, 6: .95, 7: .93, 8: .93, 9: 1.0, 10: 1.03, 11: 1.06, 12: 1.08}
HOL = {"2025-01-01": .7, "2025-05-01": .85, "2025-10-03": .85, "2025-12-24": .5,
       "2025-12-25": .6, "2025-12-26": .8, "2025-12-31": .9}
dw = dow_m[DAYS.dayofweek.values] * np.array([MONTH_M[m] for m in DAYS.month])
for k, v in HOL.items():
    dw[DAYS == pd.Timestamp(k)] *= v
dw[DAYS >= pd.Timestamp("2025-09-01")] *= 1.03   # fee increase + FALL15 start overlap (known confounder)
C = np.concatenate([[0], np.cumsum(dw)])


def rand_tod(n):
    h = rng.choice(24, n, p=HOUR_W)
    return pd.to_timedelta(h * 3600 + rng.integers(0, 3600, n), unit="s")


def local_to_utc(s):
    return s.dt.tz_localize(TZ, ambiguous=False, nonexistent="shift_forward").dt.tz_convert("UTC")


def iso(s):
    return s.dt.strftime("%Y-%m-%dT%H:%M:%SZ")


gt_def = []   # injected data defects
gt_ent = []   # injected anomalous / decoy entities

# ----------------------------------------------------------------------------- users
NB = a.users
n_rings = 40
ring_sizes = rng.integers(3, 9, n_rings)
NR = int(ring_sizes.sum())
NT = NB + NR

city = np.empty(NT, dtype=object)
chan = np.empty(NT, dtype=object)
ring_id = np.full(NT, -1)
city[:NB] = rng.choice(CITIES, NB, p=CITY_W)
chan[:NB] = rng.choice(CH, NB, p=CH_W)
sw = np.linspace(1, 1.8, ND); sw /= sw.sum()
pre = rng.random(NB) < .30
sd = np.zeros(NT, dtype=int)
sd[:NB] = np.where(pre, -rng.integers(1, 400, NB), rng.choice(ND, NB, p=sw))
fra = np.where(city[:NB] == "Frankfurt")[0]
fw = np.linspace(1, 1.8, ND - FRA_IDX); fw /= fw.sum()
sd[fra] = rng.choice(np.arange(FRA_IDX, ND), len(fra), p=fw)
pos = NB
for r, m in enumerate(ring_sizes):
    bd = int(rng.integers(10, 340))
    c = rng.choice(CITIES[:4], p=CITY_W[:4] / CITY_W[:4].sum())
    for _ in range(int(m)):
        city[pos] = c
        chan[pos] = rng.choice(["paid_social", "organic"])
        sd[pos] = bd + int(rng.integers(0, 4))
        ring_id[pos] = r
        pos += 1

plat = rng.choice(["ios", "android", "web"], NT, p=[.45, .42, .13])
tok = rng.choice(2 ** 32, size=2 * NT, replace=False)
device = np.array([f"dev_{x:08x}" for x in tok[:NT]], dtype=object)
cardfp = np.array([f"fp_{x:08x}" for x in tok[NT:]], dtype=object)
domain = rng.choice(DOMAINS, NT, p=DOM_W).astype(object)
pref = rng.choice(METH, NT, p=METH_W).astype(object)

# benign decoys: households sharing device + card (NOT fraud)
hh = rng.choice(NB, 1000, replace=False)
for i in range(500):
    device[hh[500 + i]] = device[hh[i]]
    cardfp[hh[500 + i]] = cardfp[hh[i]]
    gt_ent.append(("user", int(hh[i]) + 1, "benign_household_shared_device", f"hh_{i}"))
    gt_ent.append(("user", int(hh[500 + i]) + 1, "benign_household_shared_device", f"hh_{i}"))
# promo-abuse rings: shared device + card across 3-8 accounts
for r in range(n_rings):
    mem = np.where(ring_id == r)[0]
    device[mem] = device[mem[0]]
    cardfp[mem] = cardfp[mem[0]]
    pref[mem] = "card"
    for u in mem:
        gt_ent.append(("user", int(u) + 1, "promo_abuse_ring", f"ring_{r}"))
# internal test accounts
cand = np.setdiff1d(np.arange(NB), hh)
test_ids = rng.choice(cand, 150, replace=False)
domain[test_ids] = "foodapp-test.internal"
for u in test_ids:
    gt_ent.append(("user", int(u) + 1, "test_account", ""))
is_test_user = np.zeros(NT, bool); is_test_user[test_ids] = True

su_local = pd.Series(START + pd.to_timedelta(sd, unit="D") + rand_tod(NT))
signup_utc = local_to_utc(su_local)

# ----------------------------------------------------------------------------- restaurants & couriers
R = 4200
r_city = rng.choice(CITIES, R, p=CITY_W)
CUIS = np.array(["Turkish/Döner", "Italian", "Burger", "Asian", "Indian", "German", "Vegan", "Pizza", "Sushi", "Mexican"])
r_cuis = rng.choice(CUIS, R, p=[.20, .14, .12, .10, .08, .10, .05, .09, .06, .06])
r_tier = rng.choice([1, 2, 3], R, p=[.45, .40, .15])
r_pop = rng.pareto(1.3, R) + 1
r_comm = np.round(np.array([.18, .22, .27])[r_tier - 1] + rng.normal(0, .015, R), 3)

NC = 1600
c_city = rng.choice(CITIES, NC, p=CITY_W)
c_veh = rng.choice(["bike", "ebike", "scooter", "car"], NC, p=[.35, .35, .2, .1])
fraud_c_ids = rng.choice(np.where(c_city != "Frankfurt")[0], 25, replace=False)
c_w = rng.gamma(2, 1, NC)
c_w[fraud_c_ids] *= 3
for c_ in fraud_c_ids:
    gt_ent.append(("courier", int(c_) + 1, "courier_fake_deliveries", ""))

# ----------------------------------------------------------------------------- orders: who / when
mean_life = pd.Series(chan).map(MEAN_LIFE).astype(float).values
life = rng.exponential(mean_life) + 7
act_start = np.maximum(sd, 0)
act_end = np.minimum(np.floor(sd + life).astype(int), ND - 1)
act_days = np.maximum(act_end - act_start + 1, 0)
g = rng.gamma(.55, 1.0, NT)       # heavy-tailed per-user order intensity
g[NB:] = 0                        # ring users get explicit orders below
E = (g * act_days / 30).sum()
k = (a.target_orders - 11 * n_rings) / E
n_ord = rng.poisson(k * g * act_days / 30)
uid = np.repeat(np.arange(NT), n_ord)
s_, e_ = act_start[uid], act_end[uid]
u_ = rng.uniform(C[s_], C[e_ + 1])
day = np.clip(np.searchsorted(C, u_, side="right") - 1, s_, e_)
n_base = len(uid)

ring_uid, ring_day = [], []
for u in np.where(ring_id >= 0)[0]:
    for _ in range(int(rng.integers(1, 4))):
        ring_uid.append(u)
        ring_day.append(min(sd[u] + int(rng.integers(0, 11)), ND - 1))
uid_all = np.concatenate([uid, np.array(ring_uid, int)])
day_all = np.concatenate([day, np.array(ring_day, int)])
ring_all = np.concatenate([np.zeros(n_base, bool), np.ones(len(ring_uid), bool)])
n = len(uid_all)

loc = pd.Series(START + pd.to_timedelta(day_all, unit="D") + rand_tod(n))
created = local_to_utc(loc)
su = signup_utc.iloc[uid_all].reset_index(drop=True)
bad = created < su
shift = pd.Series(pd.to_timedelta(rng.integers(120, 1800, n), unit="s"))
created = created.where(~bad, su + shift)       # an order cannot precede signup

o = pd.DataFrame({"uid": uid_all, "ring": ring_all, "created": created})
o = o.sort_values("created", kind="stable").reset_index(drop=True)
uid = o.uid.values
ring = o.ring.values
cr = o.created
ocity = city[uid]
local = cr.dt.tz_convert(TZ)
lh = local.dt.hour.values
ld = local.dt.tz_localize(None).dt.normalize()
peak = (lh >= 18) & (lh <= 20)
seq = o.groupby("uid").cumcount().values
first = (seq == 0) & (sd[uid] >= 0)

# ----------------------------------------------------------------------------- order attributes
rest = np.empty(n, dtype=int)
for c_ in CITIES:
    m = ocity == c_
    idx = np.where(r_city == c_)[0]
    p = r_pop[idx] / r_pop[idx].sum()
    rest[m] = rng.choice(idx, int(m.sum()), p=p)

crt = np.empty(n, dtype=int)
courier = np.empty(n, dtype=int)
for c_ in CITIES:
    m = ocity == c_
    idx = np.where(c_city == c_)[0]
    p = c_w[idx] / c_w[idx].sum()
    courier[m] = rng.choice(idx, int(m.sum()), p=p)

city_mult = pd.Series(ocity).map(CITY_PRICE).astype(float).values
tier_mult = np.array([1.0, 1.35, 1.8])[r_tier[rest] - 1]
sub = rng.lognormal(np.log(21), .45, n) * tier_mult * city_mult * np.where(ring, 1.8, 1.0)
sub = np.round(np.clip(sub, 6, 250), 2)
items = 1 + rng.poisson(sub / 11)
tm = is_test_user[uid]
sub[tm] = rng.choice([1.00, 0.01, 99.99, 1000.00], int(tm.sum()))

fee = np.where(ld.values >= np.datetime64("2025-09-01"), 2.99, 2.49)
fee = np.round(fee + np.where(peak & (rng.random(n) < .35), .8, 0.0), 2)

promo = np.full(n, None, dtype=object)
disc = np.zeros(n)
has = np.zeros(n, bool)
w = ring | (first & (rng.random(n) < .55))
promo[w] = "WELCOME10"; disc[w] = np.minimum(.10 * sub[w], 8); has |= w
ldv = ld.values
sm = (~has) & (ldv >= np.datetime64("2025-06-15")) & (ldv <= np.datetime64("2025-08-15")) & (sub >= 25) & (rng.random(n) < .14)
promo[sm] = "SUMMER5"; disc[sm] = 5; has |= sm
fm = (~has) & (ldv >= np.datetime64("2025-09-01")) & (ldv <= np.datetime64("2025-10-31")) & (rng.random(n) < .18)
promo[fm] = "FALL15"; disc[fm] = np.minimum(.15 * sub[fm], 10); has |= fm
dm_ = (~has) & (rng.random(n) < .04)
promo[dm_] = "FREEDEL"; disc[dm_] = fee[dm_]; has |= dm_
disc = np.round(disc, 2)

r_ = rng.random(n)
status = np.select([r_ < .035, r_ < .055, r_ < .07],
                   ["cancelled_by_user", "cancelled_by_restaurant", "failed_payment"], "delivered")
deliv = status == "delivered"

mins = pd.Series(ocity).map(CITY_BASE_MIN).astype(float).values + 8 * peak + rng.gamma(4, 2.2, n)
mins += np.where(rng.random(n) < .06, rng.exponential(25, n), 0)
mins += np.where((ocity == "Frankfurt") & (ldv < np.datetime64("2025-07-01")), 6, 0)  # launch teething
fraud_c = np.isin(courier, fraud_c_ids)
mins = np.where(fraud_c, rng.uniform(4, 9, n), mins)
mins = np.round(mins, 1)
deliv_true = cr + pd.to_timedelta(mins, unit="m")

tip = np.where(deliv & (rng.random(n) < .55), np.round(sub * rng.uniform(.05, .15, n), 2), 0.0)
total = np.round(np.clip(sub + fee + tip - disc, 0, None), 2)

# ----------------------------------------------------------------------------- refunds
p_ref = np.where(deliv, .018 + .10 * (mins > 55), 0.0)
p_ref = np.where(deliv & fraud_c, .30, p_ref)
dl_counts = pd.Series(uid[deliv]).value_counts()
elig = dl_counts[dl_counts >= 8].index.values
elig = np.setdiff1d(elig, np.concatenate([test_ids, np.where(ring_id >= 0)[0]]))
abusers = rng.choice(elig, 60, replace=False)
for u in abusers:
    gt_ent.append(("user", int(u) + 1, "refund_abuser", ""))
ab = np.isin(uid, abusers) & deliv
p_ref = np.where(ab, .45, p_ref)
ref_idx = np.where(rng.random(n) < p_ref)[0]
kk = len(ref_idx)
reason = rng.choice(["missing_items", "quality", "wrong_order"], kk, p=[.4, .4, .2]).astype(object)
late = (rng.random(kk) < .6) & (mins[ref_idx] > 55)
reason[late] = "late_delivery"
forced = fraud_c[ref_idx] | ab[ref_idx]
reason[fraud_c[ref_idx]] = "not_delivered"
reason[ab[ref_idx] & ~fraud_c[ref_idx]] = rng.choice(["not_delivered", "missing_items"], int((ab[ref_idx] & ~fraud_c[ref_idx]).sum()))
frac = np.where(forced | (rng.random(kk) < .35), 1.0, rng.uniform(.2, .8, kk))
ref_amt = np.round(total[ref_idx] * frac, 2)
ref_ts = deliv_true.iloc[ref_idx].reset_index(drop=True) + pd.to_timedelta(rng.integers(600, 172800, kk), unit="s")

# ----------------------------------------------------------------------------- inject order-level defects
dl = np.where(deliv)[0]
perm = rng.permutation(dl)
pos_ = 0
def take(cnt):
    global pos_
    out = perm[pos_:pos_ + cnt]; pos_ += cnt
    return out

n_cn = int(.003 * len(dl)); idx_cn = take(n_cn)
n_dn = int(.002 * len(dl)); idx_dn = take(n_dn)
n_bt = max(int(.0005 * len(dl)), 1); idx_bt = take(n_bt)
idx_ng = take(18)

courier_out = np.where(deliv, courier + 1, -1).astype(float)
courier_out[~deliv] = np.nan
courier_out[idx_cn] = np.nan
deliv_out = deliv_true.copy().where(deliv)
deliv_out.iloc[idx_dn] = pd.NaT
deliv_out.iloc[idx_bt] = (cr.iloc[idx_bt] - pd.to_timedelta(rng.integers(60, 1800, n_bt), unit="s")).array
total_out = total.copy()
total_out[idx_ng] = -np.abs(total_out[idx_ng])
gt_def += [
    ("orders", "delivered_order_without_courier_id", len(idx_cn), "random delivered orders"),
    ("orders", "delivered_order_without_delivered_at", len(idx_dn), "random delivered orders"),
    ("orders", "delivered_at_before_created_at", len(idx_bt), "random delivered orders"),
    ("orders", "negative_total_eur", len(idx_ng), "random delivered orders"),
]
# refund amount > order total
ref_over = rng.random(kk) < .0015
ref_amt[ref_over] = np.round(total[ref_idx][ref_over] * rng.uniform(1.2, 3, int(ref_over.sum())), 2)
gt_def.append(("refunds", "refund_amount_exceeds_order_total", int(ref_over.sum()), "random refunds"))

# timezone bug: created_at stored as LOCAL naive time during an ingestion bug window
created_str = iso(cr)
win = (cr >= pd.Timestamp("2025-03-10", tz="UTC")) & (cr < pd.Timestamp("2025-03-24", tz="UTC"))
created_str[win] = local.dt.strftime("%Y-%m-%d %H:%M:%S")[win]
gt_def.append(("orders", "created_at_local_time_without_tz_suffix", int(win.sum()), "created 2025-03-10..2025-03-23 (UTC)"))

# vocabulary drift: delivered -> completed from 2025-08-01
drift = deliv & (cr >= pd.Timestamp("2025-08-01", tz="UTC")).values
status_out = pd.Series(status).where(~drift, "completed")
gt_def.append(("orders", "status_delivered_renamed_to_completed", int(drift.sum()), "from 2025-08-01 (UTC)"))

oid = np.arange(n) + 100001
orders = pd.DataFrame({
    "order_id": oid, "user_id": uid + 1, "restaurant_id": rest + 1,
    "courier_id": pd.Series(courier_out).astype("Int64"), "city": ocity,
    "created_at": created_str.values, "status": status_out.values, "items_count": items,
    "subtotal_eur": sub, "delivery_fee_eur": fee, "discount_eur": disc, "tip_eur": tip,
    "total_eur": total_out, "promo_code": promo, "delivered_at": iso(deliv_out).values,
})
for i in np.where(ring)[0]:
    pass
gt_ent += [("order", int(x), "promo_abuse_ring_order", "") for x in oid[ring]]
gt_ent += [("order", int(x), "test_account_order", "") for x in oid[tm]]
gt_ent += [("order", int(x), "fake_delivery_courier_order", "") for x in oid[fraud_c & deliv]]

# ----------------------------------------------------------------------------- restaurants table
r_first = pd.Series(ldv).groupby(rest).min()
onb = np.empty(R, dtype="datetime64[ns]")
for i in range(R):
    if r_city[i] == "Frankfurt":
        onb[i] = np.datetime64("2025-04-15") + np.timedelta64(int(rng.integers(0, 44)), "D")
    else:
        onb[i] = START.to_datetime64() - np.timedelta64(int(rng.integers(30, 1200)), "D")
newr = rng.random(R) < .08
for i in np.where(newr & (r_city != "Frankfurt"))[0]:
    if i in r_first.index:
        onb[i] = r_first[i].to_datetime64() - np.timedelta64(int(rng.integers(0, 8)), "D")
restaurants = pd.DataFrame({"restaurant_id": np.arange(R) + 1, "city": r_city, "cuisine": r_cuis,
                            "price_tier": r_tier, "commission_rate": r_comm,
                            "onboarded_at": pd.to_datetime(onb).strftime("%Y-%m-%d")})
hire = np.empty(NC, dtype="datetime64[ns]")
for i in range(NC):
    if c_city[i] == "Frankfurt":
        hire[i] = np.datetime64("2025-04-20") + np.timedelta64(int(rng.integers(0, 38)), "D")
    else:
        hire[i] = START.to_datetime64() - np.timedelta64(int(rng.integers(30, 900)), "D")
couriers = pd.DataFrame({"courier_id": np.arange(NC) + 1, "city": c_city, "vehicle_type": c_veh,
                         "hired_at": pd.to_datetime(hire).strftime("%Y-%m-%d")})

users = pd.DataFrame({"user_id": np.arange(NT) + 1, "signup_ts": iso(signup_utc).values, "city": city,
                      "acquisition_channel": chan, "platform": plat, "device_id": device,
                      "email_domain": domain})

# ----------------------------------------------------------------------------- payments
method = np.where(rng.random(n) < .85, pref[uid], rng.choice(METH, n, p=METH_W))
pay_status = np.where(deliv, "captured", np.where(status == "failed_payment", "failed", "voided"))
fp = np.where(np.isin(method, ["card", "applepay"]), cardfp[uid], None)
pay_ts = cr + pd.to_timedelta(rng.integers(2, 25, n), unit="s")
payments = pd.DataFrame({"order_id": oid, "user_id": uid + 1, "method": method, "amount_eur": total,
                         "status": pay_status, "card_fingerprint": fp, "created_at": iso(pay_ts).values})
cap = np.where(pay_status == "captured")[0]
dup = rng.choice(cap, int(.004 * len(cap)), replace=False)
dp = payments.iloc[dup].copy()
dp["created_at"] = iso(pay_ts.iloc[dup] + pd.to_timedelta(rng.integers(1, 40, len(dup)), unit="s")).values
payments = pd.concat([payments, dp], ignore_index=True).sort_values("created_at", kind="stable").reset_index(drop=True)
payments.insert(0, "payment_id", np.arange(len(payments)) + 1)
gt_def.append(("payments", "duplicate_capture_for_same_order", len(dup), "second captured row seconds after the first"))
gt_ent += [("order", int(x), "duplicate_payment_capture", "") for x in oid[dup]]

# ----------------------------------------------------------------------------- promo redemptions, refunds, tickets
pm = np.where(promo != None)[0]  # noqa: E711
promos = pd.DataFrame({"order_id": oid[pm], "user_id": uid[pm] + 1, "promo_code": promo[pm],
                       "discount_eur": disc[pm], "redeemed_at": iso(cr.iloc[pm]).values})
promos.insert(0, "redemption_id", np.arange(len(promos)) + 1)

refunds = pd.DataFrame({"refund_id": np.arange(kk) + 1, "order_id": oid[ref_idx], "user_id": uid[ref_idx] + 1,
                        "amount_eur": ref_amt, "reason": reason, "created_at": iso(ref_ts).values})

cat_map = {"late_delivery": "late_delivery", "missing_items": "missing_items", "quality": "quality",
           "wrong_order": "wrong_order", "not_delivered": "not_delivered"}
t_a = ref_idx[rng.random(kk) < .7]
t_a_cat = [cat_map[x] for x in pd.Series(reason, index=ref_idx).loc[t_a]]
t_b = np.where(deliv & fraud_c & (rng.random(n) < .25))[0]
t_c = np.where(deliv & (rng.random(n) < .01))[0]
t_idx = np.concatenate([t_a, t_b, t_c])
t_cat = np.concatenate([t_a_cat, ["not_delivered"] * len(t_b), rng.choice(["payment", "other", "app_issue"], len(t_c))])
t_ts = deliv_true.iloc[t_idx].reset_index(drop=True) + pd.to_timedelta(rng.integers(300, 21600, len(t_idx)), unit="s")
tickets = pd.DataFrame({"order_id": oid[t_idx], "user_id": uid[t_idx] + 1, "category": t_cat,
                        "created_at": iso(t_ts).values,
                        "resolution_hours": np.round(rng.gamma(2, 6, len(t_idx)), 1)})
tickets = tickets.sort_values("created_at", kind="stable").reset_index(drop=True)
tickets.insert(0, "ticket_id", np.arange(len(tickets)) + 1)

# ----------------------------------------------------------------------------- app events (with a tracking outage)
plat_o = plat[uid]
off0 = rng.integers(360, 1200, n); off1 = off0 - rng.integers(60, 180, n); off2 = rng.integers(30, 90, n)
fr = []
for off, et in [(off0, "app_open"), (off1, "add_to_cart"), (off2, "checkout_start"), (np.zeros(n, int), "order_placed")]:
    fr.append(pd.DataFrame({"user_id": uid + 1, "session_id": np.arange(n),
                            "event_ts": cr.values - pd.to_timedelta(off, unit="s").values,
                            "event_type": et, "platform": plat_o}))
m_ab = int(.8 * n)
src = rng.integers(0, n, m_ab)
t0 = cr.iloc[src].values - pd.to_timedelta(rng.integers(3600, 172800, m_ab), unit="s").values
ab_df = pd.DataFrame({"user_id": uid[src] + 1, "session_id": n + np.arange(m_ab), "event_ts": t0,
                      "event_type": "app_open", "platform": plat[uid[src]]})
c2 = rng.random(m_ab) < .6
a2 = ab_df[c2].copy(); a2["event_type"] = "add_to_cart"; a2["event_ts"] += pd.Timedelta(seconds=90)
c3 = rng.random(len(a2)) < .2
a3 = a2[c3].copy(); a3["event_type"] = "checkout_start"; a3["event_ts"] += pd.Timedelta(seconds=110)
ev = pd.concat(fr + [ab_df, a2, a3], ignore_index=True)
ev["event_ts"] = pd.to_datetime(ev["event_ts"], utc=True)
ev = ev[ev.event_ts >= pd.Timestamp("2025-01-01", tz="UTC")]
gap = (ev.event_ts >= pd.Timestamp("2025-07-14 11:00", tz="UTC")) & (ev.event_ts < pd.Timestamp("2025-07-14 16:00", tz="UTC"))
gt_def.append(("app_events", "tracking_outage_no_events", int(gap.sum()), "2025-07-14 11:00-16:00 UTC (rows removed)"))
ev = ev[~gap].sort_values("event_ts", kind="stable").reset_index(drop=True)
ev["event_ts"] = iso(ev["event_ts"])
ev.insert(0, "event_id", np.arange(len(ev)) + 1)

gt_def.append(("users", "test_accounts_email_domain_foodapp-test.internal", len(test_ids), "orders have odd amounts"))

# ----------------------------------------------------------------------------- write
# synthetic daily EUR->USD reference rates (own random stream: does not change any other table)
fx_rng = np.random.default_rng(a.seed + 1)
knots_d = np.array([0, 59, 104, 181, 243, 364])
knots_r = np.array([1.035, 1.04, 1.13, 1.17, 1.16, 1.17])
fx = np.interp(np.arange(ND), knots_d, knots_r) + fx_rng.normal(0, .003, ND)
fx_rates = pd.DataFrame({"rate_date": DAYS.strftime("%Y-%m-%d"), "base": "EUR", "quote": "USD",
                         "rate": np.round(fx, 4)})
fx_rates.to_csv(f"{OUT}/fx_rates.csv", index=False)
users.to_csv(f"{OUT}/users.csv", index=False)
restaurants.to_csv(f"{OUT}/restaurants.csv", index=False)
couriers.to_csv(f"{OUT}/couriers.csv", index=False)
orders.to_csv(f"{OUT}/orders.csv", index=False)
payments.to_csv(f"{OUT}/payments.csv", index=False)
promos.to_csv(f"{OUT}/promo_redemptions.csv", index=False)
refunds.to_csv(f"{OUT}/refunds.csv", index=False)
tickets.to_csv(f"{OUT}/support_tickets.csv", index=False)
ev.to_csv(f"{OUT}/app_events.csv.gz", index=False, compression="gzip")
pd.DataFrame(gt_def, columns=["table", "defect", "rows_affected", "where"]).to_csv(f"{GT}/ground_truth_defects.csv", index=False)
pd.DataFrame(gt_ent, columns=["entity_type", "entity_id", "label", "group"]).to_csv(f"{GT}/ground_truth_entities.csv", index=False)
with open(f"{OUT}/generation_params.json", "w") as f:
    json.dump({"seed": a.seed, "users_base": NB, "users_total": int(NT), "orders": int(n),
               "period": "2025-01-01..2025-12-31", "currency": "EUR", "timezone_of_business": TZ}, f, indent=2)
print("orders", n, "users", NT, "refunds", kk, "tickets", len(tickets), "events", len(ev), "payments", len(payments))
