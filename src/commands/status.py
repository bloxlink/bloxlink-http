from hikari import Embed

from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.premium import get_premium_status
from resources.exceptions import PremiumRequired


@bloxlink.command(
    category="Premium",
    pro_bypass=True,
)
class StatusCommand(GenericCommand):
    """view your premium status"""

    async def __main__(self, ctx: CommandContext):
        premium_status = await get_premium_status(guild_id=ctx.guild_id, interaction=ctx.interaction)
        embed = Embed()

        if not premium_status.active:
            raise PremiumRequired()

        embed.description = ":heart: Thanks for being a **premium subscriber!**"
        embed.color = 0xFDC333
        embed.add_field(name="Premium Status", value="Active", inline=True)
        embed.add_field(name="Tier", value=premium_status.tier, inline=True)
        embed.add_field(name="Payment Source", value=premium_status.payment_name_url, inline=True)
        embed.add_field(name="Unlocked Features", value=str(premium_status), inline=True)

        return await ctx.response.send_first(embed=embed)
