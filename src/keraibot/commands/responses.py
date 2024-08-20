from keraibot.core.commands import ChatCommand


commands = [
    ChatCommand(
        name="sqlfluff",
        reply="The sql linter I work on from time to time: https://sqlfluff.com",
    ),
    ChatCommand(
        name="status",
        reply="The bot is running!",
    ),
]
