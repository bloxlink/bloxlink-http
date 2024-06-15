from hikari import Embed

from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand


@bloxlink.command()
class InviteCommand(GenericCommand):
    """invite the bot to your server"""

    async def __main__(self, ctx: CommandContext):
        embed = Embed(
            title="Invite Bloxlink", description="To add Bloxlink to your server, click the link below."
        )
        embed.add_field(
            name="Frequently Asked Questions",
            value="1.) I don't see my server when I try to invite the bot!\n> There are 2 possibilities:\n> a) you don't have the Manage Server role permission\n> b) you aren't logged on the correct account; go to https://discord.com/ and log out.",
        )

        button_row = bloxlink.rest.build_message_action_row()
        button_row.add_link_button("https://blox.link/invite", label="Invite Bloxlink")
        button_row.add_link_button("https://blox.link/support", label="Need help?", emoji="❔")

        return await ctx.response.send_first(embed=embed, components=[button_row], build_components=False)
