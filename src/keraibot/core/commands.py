import logging

bot_logger = logging.getLogger("kerai-bot.command")


def shoutout(twitch_api):
    def shoutout_response(user, *args):
        bot_logger.info(f"{user}, {args}")
        channel_info_response = twitch_api.channel_info_by_login(user)
        if not channel_info_response.ok:
            bot_logger.error(f"Couldn't find user {user}.")
            return
        channel_info = channel_info_response.json()["data"][0]
        user_login = channel_info["broadcaster_login"]
        user_name = channel_info["broadcaster_name"]
        category = channel_info["game_name"]
        if category:
            return (
                f"You should probably check out {user_name} "
                f"at https://twitch.tv/{user_login} "
                f"they were last playing {category}!"
            )

    return shoutout_response


def reply_with_message(msg: str):
    def reply(*_args):
        return msg

    return reply


def default_command_functions(twitch_api):
    functions = {}
    functions["reply"] = reply_with_message
    functions["shoutout"] = shoutout(twitch_api)
    return functions
