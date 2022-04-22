from unicodedata import category
from snowfin import Module, slash_command, Embed, EmbedFooter, Interaction, Button, EmbedField
from resources.bloxlink import Bloxlink

from snowfin.embed import Empty

class InviteCommand(Module):
    category = "Miscellaneous"

    @slash_command("invite")
    async def invite(self, ctx: Interaction):
        """invite the bot to your server"""

        return (
            Embed(
                title="Invite Bloxlink",
                description="To add Bloxlink to your server, click the button below.",
                color=0xdb2323,
                footer=EmbedFooter(
                    text="Thanks for choosing Bloxlink!",
                    icon_url=self.client.user.avatar_url if self.client.user else Empty
                ),
                fields=[EmbedField(
                    name="Frequently Asked Questions",
                    value="**Q:** I don't see my server when I invite the bot!" \
                        "\n**A:** Make sure you have the `Manage Server` role permission and are logged into the correct account via https://discord.com"
                )]
            ),
            Button("Invite Bloxlink", url="https://blox.link/invite"),
            Button("Support Server", url="https://blox.link/support")
        )

