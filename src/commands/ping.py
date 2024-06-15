from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand


@bloxlink.command(
    category="Miscellaneous",
)
class PingCommand(GenericCommand):
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        return await ctx.response.send_first("pong")
