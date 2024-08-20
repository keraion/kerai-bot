import asyncio
import logging
import sys

from keraibot.core.config import TWITCH_AUTH
from keraibot.core.errors import InvalidTokenError, NoTokenError
from keraibot.core.utils import scheduled_task
from keraibot.core.chat import TwitchEventSub

bot_logger = logging.getLogger("kerai-bot.bot")
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def run_bot():
    try:
        try:
            TWITCH_AUTH.validate()
        except InvalidTokenError:
            # Can we refresh the token?
            TWITCH_AUTH.refresh_token()
    except NoTokenError:
        bot_logger.error("Not authorized, try running `kerai-bot auth`")
        sys.exit(1)

    bot_logger.info("Authorized")
    asyncio.ensure_future(scheduled_task(3600, TWITCH_AUTH.async_validate))
    bot_logger.info("Starting bot...")
    eventsub = TwitchEventSub()
    await eventsub.run_client()


def main():
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
