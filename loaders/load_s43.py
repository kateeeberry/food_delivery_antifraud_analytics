import csv
import getpass
from pathlib import Path

import psycopg

SCHEMA = "food_delivery_s43_raw"          # нова схема, стара food_delivery_raw не зачіпається
TABLES = ["users", "orders", "refunds", "couriers"]
FOLDER = Path(__file__).parent

conn_str = getpass.getpass("Neon connection string (вставити один раз і Enter): ")

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
        for t in TABLES:
            path = FOLDER / f"{t}.csv"
            with open(path, newline="", encoding="utf-8") as f:
                cols = next(csv.reader(f))
            col_defs = ", ".join(f'"{c}" text' for c in cols)
            cur.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{t}")
            cur.execute(f"CREATE TABLE {SCHEMA}.{t} ({col_defs})")
            with cur.copy(
                f"COPY {SCHEMA}.{t} FROM STDIN WITH (FORMAT csv, HEADER true)"
            ) as copy:
                with open(path, "rb") as f:
                    while chunk := f.read(1 << 20):
                        copy.write(chunk)
            cur.execute(f"SELECT count(*) FROM {SCHEMA}.{t}")
            print(t, cur.fetchone()[0])