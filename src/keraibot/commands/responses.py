import logging

from keraibot.core.config import TWITCH_API
from keraibot.core.commands import ChatCommand, Permission

bot_logger = logging.getLogger("kerai-bot.response")


def shoutout(*args):
    user = args[0]
    bot_logger.info(f"{user}, {args}")
    channel_info_response = TWITCH_API.channel_info_by_login(user)
    if not channel_info_response.ok:
        bot_logger.error(f"Couldn't find user {user}.")
        return
    channel_info = channel_info_response.json()["data"][0]
    user_login = channel_info["broadcaster_login"]
    user_name = channel_info["broadcaster_name"]
    category = channel_info["game_name"]
    if category:
        return (
            f"You should probably check out {user_name} "
            f"at https://twitch.tv/{user_login} "
            f"they were last playing {category}!"
        )


commands = [
    ChatCommand(
        name="sqlfluff",
        reply=lambda *args: (
            "The sql linter I work on from time to time: https://sqlfluff.com"
        ),
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
