from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import sqlite3
from typing import Callable, Optional

bot_logger = logging.getLogger("kerai-bot.command_manager")


class Permission(Enum):
    VIEWER = 1
    # FOLLOWER = 2 # TODO
    # VIP = 4 # TODO
    # MOD = 8 # TODO
    BROADCASTER = 16


@dataclass
class ChatCommand:
    name: str
    reply: Optional[callable]
    cooldown_seconds: Optional[int] = 30
    last_sent: Optional[datetime] = None
    permissions: Permission = Permission.VIEWER

    @property
    def cooldown(self) -> Optional[timedelta]:
        return timedelta(seconds=self.cooldown_seconds or 30)

    @property
    def reset_time(self) -> Optional[datetime]:
        if self.last_sent:
            return self.last_sent + self.cooldown
        return None

    @property
    def can_send(self) -> bool:
        if not self.reply:
            return False
        if self.reset_time is None:
            return True
        return datetime.now() >= self.reset_time


class CommandManager:
    commands: dict[str, ChatCommand] = {}
    functions: dict[str, Callable] = {}

    def register_command(self, command):
        self.commands[command.name] = command

    def get(self, name):
        return self.commands.get(name)

    def load_commands_from_db(self, db_file):
        with closing(sqlite3.connect(db_file)) as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT name, response, is_function, cooldown, permission 
                FROM commands;
                """
            )
            while rows := cur.fetchmany(100):
                for row in rows:
                    self.register_command(self.create_command_from_row(row))

    def create_command_from_row(self, row):
        name, response, is_function, cooldown, permission = row
        if is_function:
            reply = self.functions.get(response)
        else:
            reply = self.functions.get("reply")(response)
        if not reply:
            raise ValueError

        return ChatCommand(
            name=name,
            reply=reply,
            cooldown_seconds=cooldown,
            permissions=Permission(permission),
        )
