import logging
from functools import lru_cache, wraps
from typing import Self

import requests

from keraibot.core.auth import TwitchAuth

bot_logger = logging.getLogger("kerai-bot.api")


class TwitchAPI:
    def __init__(self, auth: TwitchAuth) -> None:
        self.auth = auth

    @staticmethod
    def requires_auth(func):
        @wraps(func)
        def aux(self: Self, *args, **kwargs):
            wrap_func = self.auth.requires_token(func)
            return wrap_func(self, *args, **kwargs)

        return aux

    @requires_auth
    def channel_info_by_login(self, login: str):
        broadcaster_id = self.get_id_from_login(login)
        response = requests.get(
            "https://api.twitch.tv/helix/channels",
            params={"broadcaster_id": broadcaster_id},
            headers={
                "Authorization": f"Bearer {self.auth.token.access_token}",
                "Client-Id": self.auth.client_id,
            },
            timeout=10,
        )
        return response

    @requires_auth
    def user_info_by_login(self, login: str):
        response = requests.get(
            "https://api.twitch.tv/helix/users",
            params={"login": login},
            headers={
                "Authorization": f"Bearer {self.auth.token.access_token}",
                "Client-Id": self.auth.client_id,
            },
            timeout=10,
        )
        return response

    @requires_auth
    @lru_cache
    def get_id_from_login(self, login: str):
        response = self.user_info_by_login(login)
        if response.ok and response.json()["data"]:
            user_id = response.json()["data"][0]["id"]
            bot_logger.info(f"{login}'s id is {user_id}")
            return user_id
