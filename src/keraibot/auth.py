"""OAuth2 authorization to Twitch."""

import http.server
import json
import logging
from pathlib import Path
import socketserver
import threading
from urllib.parse import parse_qs, urlparse

import requests

from dotenv import dotenv_values
from requests_oauthlib import OAuth2Session

from keraibot.errors import InvalidTokenError, NoTokenError

AUTH_ENDPOINT = "https://id.twitch.tv/oauth2/authorize"
TOKEN_ENDPOINT = "https://id.twitch.tv/oauth2/token"
VALIDATE_ENDPOINT = "https://id.twitch.tv/oauth2/validate"
REVOKE_ENDPOINT = "https://id.twitch.tv/oauth2/revoke"
PORT = 8080
AUTH_JSON = "data/auth.json"
config = dotenv_values(".env")

bot_logger = logging.getLogger("kerai-bot")


def authorize():
    oauth = OAuth2Session(
        config.get("CLIENT_ID"),
        redirect_uri=config.get("REDIRECT_URI"),
        scope=["chat:read"],
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
                    TOKEN_ENDPOINT,
                    code=code,
                    client_secret=config["CLIENT_SECRET"],
                    include_client_id=True,
                )

                with open(AUTH_JSON, "w", encoding="utf8") as jfp:
                    json.dump(token, jfp)

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
    authorization_url, state = oauth.authorization_url(AUTH_ENDPOINT)
    print(f"Please go to {authorization_url} and authorize access.")

    # Start the server in a new thread so it doesn't block
    try:
        with socketserver.TCPServer(("", PORT), OAuthHandler) as httpd:
            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.start()
            bot_logger.info(f"Serving at port {PORT}")

            # The server will stop once the code is received and processed
            server_thread.join()
    except Exception as e:
        bot_logger.error(f"Failed to start server on port {PORT}: {e}")
    finally:
        # Ensures the server is properly shut down and the port is cleared
        if "httpd" in locals():
            httpd.server_close()
        bot_logger.info(f"Port {PORT} cleared.")
    validate()


def refresh_token():
    auth_path = Path(AUTH_JSON)
    if not auth_path.exists():
        bot_logger.error("No token found for refresh.")
        raise NoTokenError()
    with auth_path.open("r", encoding="utf8") as jfp:
        token = json.load(jfp)
    response = requests.post(
        TOKEN_ENDPOINT,
        data={
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": config["CLIENT_ID"],
            "client_secret": config["CLIENT_SECRET"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if response.ok:
        with open(AUTH_JSON, "w", encoding="utf8") as jfp:
            json.dump(response.json(), jfp)
        validate()
    else:
        bot_logger.error("Unable to refresh token.")
        raise InvalidTokenError()


def validate():
    auth_path = Path(AUTH_JSON)
    if not auth_path.exists():
        bot_logger.error("No token found to validate.")
        raise NoTokenError()
    with auth_path.open("r", encoding="utf8") as jfp:
        token = json.load(jfp)
    response = requests.get(
        VALIDATE_ENDPOINT,
        headers={"Authorization": f"OAuth {token['access_token']}"},
        timeout=10,
    )
    if not response.ok:
        bot_logger.error("Unable to validate token.")
        bot_logger.error(response.text)
        raise InvalidTokenError(f"{response.status_code}: {response.text}")
    bot_logger.info("Token validated!")


def invalidate():
    auth_path = Path(AUTH_JSON)
    if not auth_path.exists():
        bot_logger.error("No token found to invalidate.")
        raise NoTokenError()
    with auth_path.open("r", encoding="utf8") as jfp:
        token = json.load(jfp)
    response = requests.post(
        REVOKE_ENDPOINT,
        data={
            "client_id": config["CLIENT_ID"],
            "token": token["access_token"],
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if not response.ok:
        bot_logger.error("Unable to invalidate token.")
        bot_logger.error(response.text)
        raise InvalidTokenError(f"{response.status_code}: {response.text}")
    auth_path.unlink()
    bot_logger.info("Token invalidated!")
