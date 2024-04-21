from resources.bloxlink import instance as bloxlink
from resources.commands import GenericCommand
from resources.constants import DEVELOPER_GUILDS
from bloxlink_lib.database import update_guild_data


@bloxlink.command(
    developer_only=True,
    guild_ids=DEVELOPER_GUILDS
)
class GameFieldsCommand(GenericCommand):
    """insert webhook info to db"""

    async def __main__(self, ctx):
        guild_id = ctx.guild_id

        webhooks = {
            "authentication": "oof",
            "userInfo": {
                "url": "https://feedback.joritochip.dev/bloxlink",
                "fieldMapping": {
                    "discordID": "discordId",
                    "robloxID": "robloxId",
                    "guildID": "serverId",
                    "robloxUsername": "robloxUsername",
                    "discordUsername": "discordUsername"

                }
            }
        }

        await update_guild_data(guild_id, webhooks=webhooks)

        await ctx.response.send("added binds")
