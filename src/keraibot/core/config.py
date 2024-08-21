import configparser

from dotenv import dotenv_values

from keraibot.core.auth import TwitchAuth
from keraibot.core.commands import CommandManager

bot_cfg = configparser.ConfigParser()
bot_cfg.read("bot.cfg")

env = dotenv_values(bot_cfg["keraibot.auth"].get("env_file"))

CHAT_CHANNEL_USER_ID = bot_cfg["keraibot"].get("broadcaster_login")
BOT_USER_ID = bot_cfg["keraibot"].get("bot_login")
TWITCH_AUTH = TwitchAuth(
    client_id=env.get("CLIENT_ID"),
    client_secret=env.get("CLIENT_SECRET"),
    auth_json=bot_cfg["keraibot.auth"].get("auth_file"),
    redirect_url=bot_cfg["keraibot.auth"].get("redirect_url"),
    port=bot_cfg["keraibot.auth"].get("port"),
    scope=[
        "chat:read",
        "user:read:chat",
        "user:write:chat",
    ],
)

COMMANDS = CommandManager()