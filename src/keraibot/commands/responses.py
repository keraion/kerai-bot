import logging

from keraibot.core.config import TWITCH_API
from keraibot.core.commands import ChatCommand, Permission

bot_logger = logging.getLogger("kerai-bot.response")

def shoutout(*args):
    user = args[0]
    bot_logger.info(f"{user}, {args}")
    channel_info = TWITCH_API.channel_info_by_login(user).json()
    bot_logger.info(f"{channel_info}")
    category = channel_info["data"][0]["game_name"]
    if category:
        return (
            f"You should probably check out {user} at https://twitch.tv/{user} "
            f"they were last playing {category}!"
        )


commands = [
    ChatCommand(
        name="sqlfluff",
        reply=lambda *args: "The sql linter I work on from time to time: https://sqlfluff.com",
    ),
    ChatCommand(
        name="status",
        reply=lambda *args: "The bot is running!",
    ),
    ChatCommand(
        name="so",
        reply=shoutout,
        permissions=Permission.BROADCASTER,
    ),
]
