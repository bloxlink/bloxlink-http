from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.constants import DEVELOPER_GUILDS
import hikari


@bloxlink.command(
    category="Miscellaneous",
    developer_only=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    # guild_ids=DEVELOPER_GUILDS
)
class ClearServerDataCommand(GenericCommand):
    """removes the Bloxlink data from the server"""

    async def __main__(self, ctx: CommandContext):
        guild_id = ctx.guild_id

        await bloxlink.mongo.bloxlink["guilds"].delete_one({"_id": str(guild_id)})

        await ctx.response.send("Server data deleted.")
