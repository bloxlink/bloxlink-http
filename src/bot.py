import argparse
import logging
from datetime import timedelta
from os import environ as env

import hikari
import uvicorn
from bloxlink_lib import load_modules
from bloxlink_lib.database import redis

from config import CONFIG
from resources.bloxlink import Bloxlink

# Make sure bot is accessible from most modules. We load the bot first before loading most modules.
bot = Bloxlink(
    public_key=CONFIG.DISCORD_PUBLIC_KEY,
    token=CONFIG.DISCORD_TOKEN,
    token_type=hikari.TokenType.BOT,
    asgi_managed=False,
)

# Load a few modules
from resources.commands import handle_interaction, sync_commands
from resources.constants import MODULES
from web.webserver import webserver

parser = argparse.ArgumentParser()
parser.add_argument(
    "-s", "--sync-commands",
    action="store_true",
    help="sync commands and bypass the cooldown",
    required=False,
    default=False)
parser.add_argument(
    "-c", "--clear-redis",
    action="store_true",
    help="local only, clears redis",
    required=False,
    default=False)
parser.add_argument(
    "-d", "--debug",
    action="store_true",
    help="enable debug logging format",
    required=False,
    default=False)
args = parser.parse_args()


# Initialize the web server
# IMPORTANT NOTE: blacksheep expects a trailing /
# in the URL that is given to discord because this is a mount.
# Example: "example.org/bot/" works, but "example.org/bot" does not (this results in a 307 reply, which discord doesn't honor).
webserver.mount("/bot", bot)

@webserver.on_start
async def handle_start(_):
    """Start the bot and sync commands"""

    if args.debug:
        logging.basicConfig(level=logging.DEBUG, force=True, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")

    await bot.start()

    # only sync commands once every hour unless the --sync-commands flag is passed
    if args.sync_commands or not await redis.get("synced_commands"):
        await redis.set("synced_commands", "true", expire=timedelta(hours=1))
        await sync_commands(bot)
    else:
        logging.info("Skipping command sync. Run with --sync-commands or -s to force sync.")

    if CONFIG.BOT_RELEASE == "LOCAL" and args.clear_redis:
        await redis.flushall()
        logging.info("Cleared redis. Run with --clear-redis or -c to force clear.")


@webserver.on_stop
async def handle_stop(_):
    """Executes when the bot is stopped"""

    await bot.close()


if __name__ == "__main__":
    # Register the interaction handler for all interaction types.
    for interaction_type in (hikari.CommandInteraction, hikari.ComponentInteraction, hikari.AutocompleteInteraction, hikari.ModalInteraction):
        bot.interaction_server.set_listener(interaction_type, handle_interaction)

    load_modules(*MODULES, starting_path="src/")

    uvicorn.run(
        webserver,
        host=env.get("HOST", CONFIG.HOST),
        port=int(env.get("PORT", CONFIG.PORT)),
        log_config=None,
    )
