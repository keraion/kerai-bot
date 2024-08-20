from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class ChatCommand:
    name: str
    reply: Optional[str]
    cooldown_seconds: Optional[int] = 30
    last_sent: Optional[datetime] = None

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

    def new_command(self, command):
        self.commands[command.name] = command

    def get(self, name):
        return self.commands[name]
