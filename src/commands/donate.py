from hikari import Embed

from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.ui.components import Button


@bloxlink.command(
    pro_bypass=True,
)
class DonateCommand(GenericCommand):
    """Learn how to receive Bloxlink Premium"""

    async def __main__(self, ctx: CommandContext):
        embed = Embed(
            title="Bloxlink Premium", description="Premium purchases help support Bloxlink!", color=0x00B2FF
        )

        embed.add_field(
            name="Server Premium",
            value="Unlocks premium commands, lessens restrictions, no ads for your server verification page, and more for your server.",
            inline=False,
        )

        button_menu = [
            Button(
                label="Click for Server Premium",
                url=f"https://blox.link/dashboard/guilds/{ctx.guild_id}/premium"
                    if ctx.guild_id
                    else "https://blox.link/",
                style=Button.ButtonStyle.LINK,
            )
        ]

        return await ctx.response.send_first(embed=embed, components=button_menu)
