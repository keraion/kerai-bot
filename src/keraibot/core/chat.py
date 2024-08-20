import asyncio
from datetime import datetime
import json
import logging
import signal
import sys
from functools import lru_cache

import requests
import websockets.client

from keraibot.core.config import COMMANDS, TWITCH_AUTH, CHAT_CHANNEL_USER_ID, BOT_USER_ID

TWITCH_EVENTSUB_URL = "wss://eventsub.wss.twitch.tv/ws"

bot_logger = logging.getLogger("kerai-bot.chat")


@TWITCH_AUTH.requires_token
@lru_cache
def get_id_from_login(login: str):
    response = requests.get(
        "https://api.twitch.tv/helix/users",
        data=json.dumps({"login": login}),
        headers={
            "Authorization": f"Bearer {TWITCH_AUTH.token.access_token}",
            "Client-Id": TWITCH_AUTH.client_id,
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    if response.ok:
        user_id = response.json()["data"][0]["id"]
        bot_logger.info(f"{login}'s id is {user_id}")
        return user_id


class TwitchEventSub:
    websocket_id: str

    async def run_client(self):
        async with websockets.client.connect(TWITCH_EVENTSUB_URL) as websocket:
            # Close the connection when receiving SIGTERM.
            loop = asyncio.get_running_loop()

            def handle_sigterm():
                loop.create_task(websocket.close())

            loop.add_signal_handler(signal.SIGTERM, handle_sigterm)

            # Process messages
            async for message in websocket:
                try:
                    message_json = json.loads(message)
                    message_type = message_json["metadata"]["message_type"]
                    match message_type:
                        case "session_welcome":
                            self.websocket_id = message_json["payload"]["session"]["id"]
                            await self.add_eventsub_listeners()
                        case "session_keepalive":
                            pass
                        case "notification":
                            handle_notification(message_json)
                        case _:
                            bot_logger.info(message_json)
                except websockets.ConnectionClosed:
                    continue

    @TWITCH_AUTH.requires_token
    async def add_eventsub_listeners(self):
        response = requests.post(
            "https://api.twitch.tv/helix/eventsub/subscriptions",
            data=json.dumps(
                {
                    "type": "channel.chat.message",
                    "version": 1,
                    "condition": {
                        "broadcaster_user_id": get_id_from_login(CHAT_CHANNEL_USER_ID),
                        "user_id": get_id_from_login(BOT_USER_ID),
                    },
                    "transport": {
                        "method": "websocket",
                        "session_id": self.websocket_id,
                    },
                }
            ),
            headers={
                "Authorization": f"Bearer {TWITCH_AUTH.token.access_token}",
                "Client-Id": TWITCH_AUTH.client_id,
                "Content-Type": "application/json",
            },
            timeout=10,
        )
        if response.status_code != 202:
            data = response.json()
            bot_logger.error(
                "Failed to subscribe to channel.chat.message. "
                f"API call returned status code {response.status_code}"
            )
            bot_logger.error(data)
            sys.exit(1)
        else:
            data = response.json()
            bot_logger.info(
                f"Subscribed to channel.chat.message [{data.get('data')[0].get('id')}]"
            )


def handle_notification(message_json):
    user_login = message_json["payload"]["event"]["chatter_user_login"]
    user_message = message_json["payload"]["event"]["message"]["text"]
    bot_logger.info(f"{user_login}: {user_message}")
    bot_logger.debug(message_json)
    handle_command(message_json)


@TWITCH_AUTH.requires_token
def send_message(msg):
    response = requests.post(
        "https://api.twitch.tv/helix/chat/messages",
        data=json.dumps(
            {
                "broadcaster_id": get_id_from_login(CHAT_CHANNEL_USER_ID),
                "sender_id": get_id_from_login(BOT_USER_ID),
                "message": msg,
            }
        ),
        headers={
            "Authorization": f"Bearer {TWITCH_AUTH.token.access_token}",
            "Client-Id": TWITCH_AUTH.client_id,
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    if response.status_code != 200:
        data = response.json()
        bot_logger.error(
            "Failed to send chat message. "
            f"API call returned status code {response.status_code}"
        )
        bot_logger.error(data)
    else:
        data = response.json()
        bot_logger.info(f"Sent message: [{msg}]")


def handle_command(message_json):
    user_message: str = message_json["payload"]["event"]["message"]["text"]
    if not user_message.startswith("!"):
        return
    command_name, *command_args = user_message.split(" ")
    command_name = command_name.removeprefix("!")
    if (command := COMMANDS.get(command_name)) is None:
        bot_logger.info("Command not found!")
        return
    if command.can_send:
        send_message(command.reply)
