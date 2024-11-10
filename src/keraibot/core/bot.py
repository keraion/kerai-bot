import asyncio
import logging
import sys
from datetime import datetime, timedelta
from functools import partial
from typing import Optional

from twitchAPI.chat import (
    Chat,
    ChatCommand,
    ChatMessage,
    EventData,
    JoinedEvent,
    JoinEvent,
    LeftEvent,
)
from twitchAPI.eventsub.websocket import EventSubWebsocket
from twitchAPI.helper import first
from twitchAPI.oauth import UserAuthenticationStorageHelper
from twitchAPI.object.eventsub import ChannelAdBreakBeginEvent
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, ChatEvent

from keraibot.core.config import CHAT_CHANNEL_USER_ID, TWITCH_AUTH
from keraibot.core.db import DatabaseInterface
from keraibot.core.errors import InvalidTokenError, MissingScopeError, NoTokenError

bot_logger = logging.getLogger("kerai-bot.chat")
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

DBI = DatabaseInterface("data/bot.db")


async def on_ready(broadcaster_name: str, ready_event: EventData):
    print("Bot is ready for work, joining channels")
    await ready_event.chat.join_room(broadcaster_name)


async def on_message(msg: ChatMessage):
    bot_logger.info(f"{msg.user.name}: {msg.text}")


async def on_joined(joined_event: JoinedEvent):
    print(joined_event.user_name, joined_event.room_name)


async def on_join(join_event: JoinEvent):
    bot_logger.info(f"JOIN {join_event.chat.username}: {join_event.user_name}")


async def on_leave(left_event: LeftEvent):
    bot_logger.info(f"LEAVE {left_event.chat.username}: {left_event.user_name}")


timer_dict: dict[str, Optional[datetime]] = {}
response_dict: dict[str, str] = {}


async def add_response_command(cmd: ChatCommand):
    """Add the command to the database then register the command."""
    if not cmd.user.mod and cmd.user.name != cmd.room.name:
        return

    if not (
        cmd.parameter
        and (params := cmd.parameter.split(maxsplit=1))
        and len(params) == 2
    ):
        return

    command = params[0].lstrip("!")
    response = params[1]

    if await DBI.add_response(command, response):
        response_dict.update({command: response})
        cmd.chat.register_command(command, get_response)
        await cmd.reply(f"{command} command was added.")
    else:
        await cmd.reply(f"{command} already exists.")


async def edit_response_command(cmd: ChatCommand):
    """Edits an existing command in the database."""
    if not cmd.user.mod and cmd.user.name != cmd.room.name:
        return

    if not (
        cmd.parameter
        and (params := cmd.parameter.split(maxsplit=1))
        and len(params) == 2
    ):
        return

    command = params[0].lstrip("!")
    response = params[1]

    if command not in response_dict:
        await cmd.reply(f"Unable to update {command}.")

    if await DBI.add_response(command, response, "REPLACE"):
        response_dict.update({command: response})
        await cmd.reply(f"{command} command was updated.")
    else:
        await cmd.reply(f"Unable to update {command}.")


async def shoutout(cmd: ChatCommand):
    if cmd.user.mod or cmd.user.name == cmd.room.name:
        if len(cmd.parameter) == 0:
            return
        user_param = cmd.parameter.split()[0]
        user = await first(cmd.chat.twitch.get_users(logins=[user_param]))
        if not user:
            return
        channel_info = await cmd.chat.twitch.get_channel_information(user.id)
        if not channel_info:
            return
        user_login = channel_info[0].broadcaster_login
        user_name = channel_info[0].broadcaster_name
        category = channel_info[0].game_name
        await cmd.send(
            f"You should probably check out {user_name} at "
            f"https://twitch.tv/{user_login} they were last doing things in {category}!"
        )


async def get_response(cmd: ChatCommand):
    if timer_dict.get(cmd.name) and timer_dict.get(cmd.name) > datetime.now():
        return
    timer_dict[cmd.name] = datetime.now() + timedelta(seconds=30)
    await cmd.send(response_dict.get(cmd.name))


async def on_ad_start(twitch: Twitch, bot_id: str, ad_break: ChannelAdBreakBeginEvent):
    duration = ad_break.event.duration_seconds
    await twitch.send_chat_announcement(
        ad_break.event.broadcaster_user_id,
        bot_id,
        f"Heads up! {duration} seconds ads are starting. Take"
        " this time to stretch, grab water, or just look away from the screen"
        " for a bit.",
    )
    await asyncio.sleep(duration)
    await twitch.send_chat_announcement(
        ad_break.event.broadcaster_user_id,
        bot_id,
        "Ads are finishing up now. Thanks for sticking around!",
    )


async def do_auth(_twitch, scope: list[AuthScope]):
    try:
        try:
            TWITCH_AUTH.validate(scope)
        except InvalidTokenError:
            # Can we refresh the token?
            TWITCH_AUTH.refresh_token(scope)
    except (NoTokenError, MissingScopeError):
        TWITCH_AUTH.authorize(scope=scope)
    return TWITCH_AUTH.token.token, TWITCH_AUTH.token.refresh


async def run_bot(broadcaster_name: str):
    await DBI.create_database()
    twitch = await Twitch(TWITCH_AUTH.client_id, TWITCH_AUTH.client_secret)
    target_scopes = [
        AuthScope.USER_WRITE_CHAT,
        AuthScope.USER_READ_CHAT,
        AuthScope.CHAT_READ,
        AuthScope.CHAT_EDIT,
        AuthScope.CHANNEL_READ_ADS,
        AuthScope.MODERATOR_MANAGE_ANNOUNCEMENTS,
    ]
    token_helper = UserAuthenticationStorageHelper(
        twitch, target_scopes, TWITCH_AUTH.auth_file, do_auth
    )
    await token_helper.bind()
    user = await first(twitch.get_users(logins=[broadcaster_name]))
    bot = await first(twitch.get_users())
    print(user.id, bot.id)

    chat = await Chat(twitch)

    # listen to when the bot is done starting up and ready to join channels
    on_ready_broadcaster = partial(on_ready, broadcaster_name)
    chat.register_event(ChatEvent.READY, on_ready_broadcaster)
    chat.register_event(ChatEvent.MESSAGE, on_message)
    chat.register_event(ChatEvent.JOIN, on_join)
    chat.register_event(ChatEvent.JOINED, on_joined)
    chat.register_event(ChatEvent.USER_LEFT, on_leave)

    chat.register_command("so", shoutout)
    chat.register_command("addcmd", add_response_command)
    chat.register_command("editcmd", edit_response_command)

    for response in await DBI.get_responses():
        response_dict[response[0]] = response[1]
        chat.register_command(response[0], get_response)

    chat.start()

    on_ad_start_twitch = partial(on_ad_start, twitch, bot.id)
    eventsub = EventSubWebsocket(twitch)
    eventsub.start()
    await eventsub.listen_channel_ad_break_begin(user.id, on_ad_start_twitch)

    # lets run till we press enter in the console
    try:
        input("press ENTER to stop\n")
    finally:
        # now we can close the chat bot and the twitch api client
        chat.stop()
        eventsub.stop()
        await twitch.close()


def main():
    asyncio.run(run_bot(CHAT_CHANNEL_USER_ID))


if __name__ == "__main__":
    main()
