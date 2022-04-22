from unicodedata import category
from snowfin import Module, slash_command, MessageResponse, Interaction
from resources.bloxlink import Bloxlink

class PingCommand(Module):
    """A module that responds to ping commands"""

    category = "Miscellaneous"

    @slash_command("ping")
    async def ping(self, ctx: Interaction):
        """measure the latency between the bot and Discord"""

        return MessageResponse(f"pong! {0}ms", ephemeral=True)
