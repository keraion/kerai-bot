"""CLI for kerai-bot."""

import click

import keraibot.auth
import keraibot.bot

@click.group()
def cli() -> None:
    """kerai-bot, a twitch chatbot!"""

@cli.command()
def auth():
    """Authorize the bot from the `auth` command."""
    keraibot.auth.authorize()

@cli.command()
def run():
    """Start the bot."""
    keraibot.bot.main()
