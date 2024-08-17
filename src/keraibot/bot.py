import sys
import logging

from keraibot.errors import InvalidTokenError, NoTokenError
from keraibot.auth import validate, refresh_token

bot_logger = logging.getLogger("kerai-bot")
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main():
    try:
        try:
            validate()
        except InvalidTokenError:
            # Can we refresh the token?
            refresh_token()
    except NoTokenError:
        bot_logger.error("Not authorized, try running `kerai-bot auth`")
        sys.exit(1)

    bot_logger.info("Authorized, starting bot...")
    # TODO: the rest of the owl.


if __name__ == "__main__":
    main()
