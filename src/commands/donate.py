from unicodedata import category
from snowfin import Module, slash_command, Embed, Interaction, Button, EmbedField

class DonateCommand(Module):
    category = "Miscellaneous"

    @slash_command("donate")
    async def donate(self, ctx: Interaction):
        """learn how to receive Bloxlink Premium"""

        embed = Embed(
            title="Bloxlink Premium",
            description="Premium purchases help support Bloxlink!",
            fields=[
                EmbedField(
                    name="Server Premium",
                    value="Unlocks premium commands, lessens restrictions, no ads for your server verification page, and more for your server."
                ),
            ],
            color=0xdb2323
        )

        return embed, Button("Click for Server Premium", url="https://blox.link/premium")
           
