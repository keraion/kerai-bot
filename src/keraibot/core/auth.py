"""OAuth2 authorization to Twitch."""

from functools import wraps
import http.server
import json
import logging
import socketserver
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Self
from urllib.parse import parse_qs, urlparse

import requests
from requests_oauthlib import OAuth2Session

from keraibot.core.errors import InvalidTokenError, NoTokenError

bot_logger = logging.getLogger("kerai-bot.auth")


@dataclass
class TwitchAuthToken:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: list[str]
    token_type: str

    @classmethod
    def from_json(cls, json_data):
        return cls(
            json_data["access_token"],
            json_data["refresh_token"],
            json_data["expires_in"],
            json_data["scope"],
            json_data["token_type"],
        )


class TwitchAuth:
    def __init__(
        self,
        twitch_auth_url: Optional[str] = None,
        client_id: str = None,
        client_secret: str = None,
        redirect_url: str = "http://localhost",
        auth_json: str = "data/auth.json",
        port: int = 8080,
        scope: list[str] = None,
    ) -> None:
        twitch_auth_url = twitch_auth_url or "https://id.twitch.tv/oauth2"
        self.auth_endpoint = f"{twitch_auth_url}/authorize"
        self.token_endpoint = f"{twitch_auth_url}/token"
        self.validate_endpoint = f"{twitch_auth_url}/validate"
        self.revoke_endpoint = f"{twitch_auth_url}/revoke"
        self.client_id = client_id
        self.client_secret = client_secret
        self.port = port
        self.redirect_url = f"{redirect_url}:{port}"
        self.auth_file = Path(auth_json)
        self.scope = scope or []
        self._token = None

    def load_token(self):
        if not self.auth_file.exists():
            bot_logger.error("No token found.")
            raise NoTokenError()
        with self.auth_file.open("r", encoding="utf8") as jfp:
            token_json = json.load(jfp)
        return token_json

    @property
    def token(self):
        if self._token is None:
            self._token = TwitchAuthToken.from_json(self.load_token())
        return self._token

    @staticmethod
    def requires_token(func):
        @wraps(func)
        def aux(self: Self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except InvalidTokenError:
                self.refresh_token()
                return func(self, *args, **kwargs)

        return aux

    def authorize(auth_self):  # pylint: disable=no-self-argument
        oauth = OAuth2Session(
            auth_self.client_id,
            redirect_uri=auth_self.redirect_url,
            scope=auth_self.scope,
        )

        class OAuthHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                """Suppresses all logging. We don't want to reveal secrets."""
                return

            def do_GET(self):
                try:
                    # Extract the authorization code from the URL
                    parsed_url = urlparse(self.path)
                    query_dict = parse_qs(parsed_url.query)
                    code = query_dict["code"][0]

                    # Exchange the authorization code for a token
                    token = oauth.fetch_token(
                        auth_self.token_endpoint,
                        code=code,
                        client_secret=auth_self.client_secret,
                        include_client_id=True,
                    )

                    with auth_self.auth_file.open("w", encoding="utf8") as jfp:
                        json.dump(token, jfp)
                    auth_self._token()

                    # Respond to the browser
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(
                        b"Authorization successful! You can close this window."
                    )
                except Exception as exc:
                    bot_logger.error(f"Error occurred: {exc}")
                    self.send_response(500)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"An error occurred. Please try again.")
                finally:
                    # Shutdown the server after handling the request
                    threading.Thread(target=httpd.shutdown).start()

        # Redirect user to OAuth provider to authorize
        authorization_url, _state = oauth.authorization_url(auth_self.auth_endpoint)
        print(f"Please go to {authorization_url} and authorize access.")

        # Start the server in a new thread so it doesn't block
        try:
            with socketserver.TCPServer(("", auth_self.port), OAuthHandler) as httpd:
                server_thread = threading.Thread(target=httpd.serve_forever)
                server_thread.start()
                bot_logger.info(f"Serving at port {auth_self.port}")

                # The server will stop once the code is received and processed
                server_thread.join()
        except Exception as e:
            bot_logger.error(f"Failed to start server on port {auth_self.port}: {e}")
        finally:
            # Ensures the server is properly shut down and the port is cleared
            if "httpd" in locals():
                httpd.server_close()
            bot_logger.info(f"Port {auth_self.port} cleared.")
        auth_self.validate()

    @requires_token
    def refresh_token(self):
        response = requests.post(
            self.token_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.token.refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if response.ok:
            with self.auth_file.open("w", encoding="utf8") as jfp:
                json.dump(response.json(), jfp)
            self._token = None
            self.validate()
        else:
            bot_logger.error("Unable to refresh token.")
            raise InvalidTokenError()

    async def async_validate(self):
        bot_logger.info("Running validation.")
        self.validate()

    @requires_token
    def validate(self):
        response = requests.get(
            self.validate_endpoint,
            headers={"Authorization": f"OAuth {self.token.access_token}"},
            timeout=10,
        )
        if not response.ok:
            bot_logger.error("Unable to validate token.")
            bot_logger.error(response.text)
            raise InvalidTokenError(f"{response.status_code}: {response.text}")
        bot_logger.info("Token validated!")

    @requires_token
    def invalidate(self):
        response = requests.post(
            self.revoke_endpoint,
            data={
                "client_id": self.client_id,
                "token": self.token.access_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        if not response.ok:
            bot_logger.error("Unable to invalidate token.")
            bot_logger.error(response.text)
            raise InvalidTokenError(f"{response.status_code}: {response.text}")
        self.auth_file.unlink()
        self._token = None
        bot_logger.info("Token invalidated!")
