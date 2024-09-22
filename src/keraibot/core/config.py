import configparser
import os

from dotenv import dotenv_values

from keraibot.core.api import TwitchAPI
from keraibot.core.auth import TwitchAuth
from keraibot.core.command_manager import CommandManager
from keraibot.core.commands import default_command_functions

bot_cfg = configparser.ConfigParser()
bot_cfg.read("bot.cfg")

env = dotenv_values(bot_cfg["keraibot.auth"].get("env_file"))

if env.get("OAUTHLIB_INSECURE_TRANSPORT"):
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = env.get("OAUTHLIB_INSECURE_TRANSPORT")

CHAT_CHANNEL_USER_ID = bot_cfg["keraibot"].get("broadcaster_login")
BOT_USER_ID = bot_cfg["keraibot"].get("bot_login")
TWITCH_AUTH = TwitchAuth(
    client_id=env.get("CLIENT_ID"),
    client_secret=env.get("CLIENT_SECRET"),
    auth_json=bot_cfg["keraibot.auth"].get("auth_file"),
    redirect_url=bot_cfg["keraibot.auth"].get("redirect_url"),
    port=int(bot_cfg["keraibot.auth"].get("port", 8080)),
    scope=[
        "chat:read",
        "user:read:chat",
        "user:write:chat",
    ],
)
TWITCH_API = TwitchAPI(TWITCH_AUTH)
COMMANDS = CommandManager()
COMMANDS.functions.update(default_command_functions(TWITCH_API))
COMMANDS.load_commands_from_db(bot_cfg["keraibot.commands"].get("db"))
