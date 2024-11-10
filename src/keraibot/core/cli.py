"""CLI for kerai-bot."""

import click

from keraibot.core.config import TWITCH_AUTH
import keraibot.core.bot


@click.group()
def cli() -> None:
    """kerai-bot, a twitch chatbot!"""


@cli.command()
def invalidate():
    """CLI to invalidate a token."""
    TWITCH_AUTH.invalidate()


@cli.command()
def run():
    """Start the bot."""
    keraibot.core.bot.main()
