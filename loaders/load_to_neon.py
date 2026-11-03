import gzip, csv, getpass, psycopg
from pathlib import Path

DATA = Path(".")   # CSV лежать поруч зі скриптом
url = getpass.getpass("Neon connection string: ")   # у файлі не зберігається

files = {
    "users": "users.csv", "restaurants": "restaurants.csv",
    "couriers": "couriers.csv", "orders": "orders.csv",
    "payments": "payments.csv", "promo_redemptions": "promo_redemptions.csv",
    "refunds": "refunds.csv", "support_tickets": "support_tickets.csv",
    "fx_rates": "fx_rates.csv", "app_events": "app_events.csv.gz",
}
ONLY = list(files)        # спершу тест на одній таблиці; потім: ONLY = list(files)

def open_text(p):
    return gzip.open(p, "rt", encoding="utf-8", newline="") if p.suffix == ".gz" \
        else open(p, "r", encoding="utf-8", newline="")

with psycopg.connect(url) as conn:
    conn.execute("CREATE SCHEMA IF NOT EXISTS food_delivery_raw")
    for t in ONLY:
        p = DATA / files[t]
        with open_text(p) as fh:
            cols = next(csv.reader(fh))
        conn.execute(f'DROP TABLE IF EXISTS food_delivery_raw."{t}"')
        conn.execute(f'CREATE TABLE food_delivery_raw."{t}" ('
                     + ", ".join(f'"{c}" text' for c in cols) + ")")
        with open_text(p) as fh, conn.cursor().copy(
            f'COPY food_delivery_raw."{t}" FROM STDIN WITH (FORMAT csv, HEADER true)'
        ) as cp:
            while chunk := fh.read(1 << 20):
                cp.write(chunk)
        n = conn.execute(f'SELECT count(*) FROM food_delivery_raw."{t}"').fetchone()[0]
        print(t, n)