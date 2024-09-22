import csv
import sqlite3
from contextlib import closing


def rebuild_commands():
    with closing(sqlite3.connect("data/bot.db")) as conn:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS commands;")
        cur.execute(
            """
            CREATE TABLE commands (
                command_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name text NOT NULL UNIQUE,
                response text NOT NULL,
                is_function boolean NOT NULL DEFAULT FALSE,
                cooldown int NOT NULL DEFAULT 30,
                permission int NOT NULL DEFAULT 1
            )
            ;
            """
        )


def reload_commands():
    with closing(sqlite3.connect("data/bot.db")) as conn, open(
        "data/data.csv", "r", encoding="utf8"
    ) as csv_fh:
        cur = conn.cursor()
        dr = csv.DictReader(csv_fh)
        cur.executemany(
            """INSERT OR REPLACE INTO commands 
                (name, response, is_function, cooldown, permission)
                VALUES
                (:name, :response, :is_function, :cooldown, :permission);
            """,
            dr,
        )
        conn.commit()


if __name__ == "__main__":
    # rebuild_commands()
    reload_commands()
