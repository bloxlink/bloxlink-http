from datetime import timedelta
from hikari import Embed

from bloxlink_lib import BaseModel
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand


class StatsResponse(BaseModel):
    """Response from the stats command."""

    node_id: int
    guild_count: int
    user_count: int
    uptime: timedelta



@bloxlink.command(
    category="Miscellaneous",
    defer=True,
    developer_only=True
)
class StatsCommand(GenericCommand):
    """view Bloxlink information"""

    async def __main__(self, ctx: CommandContext):
        embed = Embed()


        try:
            stats = await bloxlink.relay("REQUEST_STATS",
                                         model=StatsResponse,
                                         payload=None,
                                         timeout=timedelta(seconds=10).seconds,
                                         wait_for_all=True)
        except TimeoutError:
            print("timeout")
            return

        print("stats", stats)

        print(stats[0].node_id)

        await ctx.response.send(content=stats)
