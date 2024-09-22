import asyncio
import json
import logging
import signal
import sys
from typing import Optional

import requests
from websockets import WebSocketClientProtocol
import websockets.client

from keraibot.core.command_manager import Permission
from keraibot.core.config import (
    COMMANDS,
    TWITCH_AUTH,
    TWITCH_API,
    CHAT_CHANNEL_USER_ID,
    BOT_USER_ID,
)


TWITCH_EVENTSUB_SUBSCRIPTIONS = f"{TWITCH_API.api_url}/eventsub/subscriptions"
TWITCH_CHAT_MESSAGES = f"{TWITCH_API.api_url}/chat/messages"

bot_logger = logging.getLogger("kerai-bot.chat")


class TwitchEventSub:
    websocket_id: str

    async def run_client(
        self,
        websocket_url: str = "wss://eventsub.wss.twitch.tv/ws",
    ):
        async with websockets.client.connect(websocket_url) as websocket:
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
                        case "session_reconnect":
                            self.websocket_id = message_json["payload"]["session"]["id"]
                            await self.run_client(
                                message_json["payload"]["session"]["reconnect_url"],
                            )
                            websocket.close()
                        case "notification":
                            handle_notification(message_json)
                        case _:
                            bot_logger.info(message_json)
                except websockets.ConnectionClosed:
                    continue

    @TWITCH_AUTH.requires_token
    async def add_eventsub_listeners(self):
        response = requests.post(
            TWITCH_EVENTSUB_SUBSCRIPTIONS,
            data=json.dumps(
                {
                    "type": "channel.chat.message",
                    "version": 1,
                    "condition": {
                        "broadcaster_user_id": TWITCH_API.get_id_from_login(
                            CHAT_CHANNEL_USER_ID
                        ),
                        "user_id": TWITCH_API.get_id_from_login(BOT_USER_ID),
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
            bot_logger.error(
                "Failed to subscribe to channel.chat.message. "
                f"API call returned status code {response.status_code}"
            )
            data = response.json()
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
        TWITCH_CHAT_MESSAGES,
        data=json.dumps(
            {
                "broadcaster_id": TWITCH_API.get_id_from_login(CHAT_CHANNEL_USER_ID),
                "sender_id": TWITCH_API.get_id_from_login(BOT_USER_ID),
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
    broadcaster_id: str = message_json["payload"]["event"]["broadcaster_user_id"]
    user_id: str = message_json["payload"]["event"]["chatter_user_id"]
    if not user_message.startswith("!"):
        return
    command_name, *command_args = user_message.split(" ")
    command_name = command_name.removeprefix("!")
    if (command := COMMANDS.get(command_name)) is None:
        bot_logger.info("Command not found!")
        return
    if command.can_send and has_permissions(
        user_id, broadcaster_id, command.permissions
    ):
        message = command.reply(*command_args)
        bot_logger.info(message)
        if message:
            send_message(message)


def has_permissions(user: str, broadcaster_id: str, command_permissions: Permission):
    # This is a cheap check, go first
    match command_permissions:
        case Permission.VIEWER:
            return True
        case Permission.BROADCASTER:
            return is_broadcaster(user, broadcaster_id)
    return False


def is_broadcaster(user: str, broadcaster_id: str):
    if user == broadcaster_id:
        return True
    return False
