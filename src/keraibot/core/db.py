import logging
import sqlite3
import aiosqlite


logger = logging.getLogger("kerai-bot.dbi")


class DatabaseInterface:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def create_database(self, rebuild=False):
        await self.create_response_table(rebuild)

    async def create_response_table(self, rebuild=False):
        async with aiosqlite.connect(self.db_path) as conn:
            if rebuild:
                await conn.execute("DROP TABLE IF EXISTS response;")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS response (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    response_name text NOT NULL UNIQUE,
                    response_text text NOT NULL
                )
                ;
                """
            )

    async def get_responses(self):
        async with aiosqlite.connect(self.db_path) as conn:
            cur = await conn.execute(
                "SELECT response_name, response_text FROM response"
            )
            return await cur.fetchall()

    async def add_response(
        self, command: str, response_text: str, statement_type: str = "INSERT"
    ):
        async with aiosqlite.connect(self.db_path) as conn:
            try:
                await conn.execute(
                    f"""{statement_type} INTO response 
                    (response_name, response_text) VALUES (?, ?)""",
                    (command, response_text),
                )
                await conn.commit()
            except sqlite3.IntegrityError:
                logger.error(f"Unable to add new command {command}")
                return False
            except Exception:
                logger.error(f"Unable to add command {command}")
                return False
            return True


if __name__ == "__main__":
    dbi = DatabaseInterface("data/bot.db")
