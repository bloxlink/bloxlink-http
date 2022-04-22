from unicodedata import category
from snowfin import Module, slash_command, Interaction, Embed, EmbedAuthor, EmbedField

import math
from psutil import Process
from os import getpid

class StatsCommand(Module):
    category = "Miscellaneous"

    @slash_command("stats")
    async def stats(self, ctx: Interaction):
        """view the current stats of BloxLink"""

        all_seconds = self.client.uptime.total_seconds()

        days = int(all_seconds // 86400); all_seconds %= 86400
        hours = int((all_seconds % 86400) // 3600); all_seconds %= 3600
        minutes = int((all_seconds % 3600) // 60); all_seconds %= 60

        uptime_str = f"{(str(days)+'d ') if days > 0 else ''}{hours}h {minutes}m {int(all_seconds)}s"

        process = Process(getpid())
        process_mem = math.floor(process.memory_info()[0] / float(2 ** 20))

        return Embed(
            description="Roblox Verification made easy! Features everything you need to integrate your Discord server with Roblox.",
            color=0xdb2323,
            fields=[
                EmbedField(
                    name="Node Uptime",
                    value=uptime_str,
                    inline=True
                ),
                EmbedField(
                    name="Node Memory Usage",
                    value=f"{process_mem:,} MB",
                    inline=True
                ),
                EmbedField(
                    name="Resources",
                    value="[**Website**](https://blox.link) | [**Discord**](https://blox.link.suppport) | [**Invite Bot**](https://blox.link/invite) | [**Premium**](https://blox.link/premium)" \
                        "\n\n [**Repository**](https://github.com/bloxlink/bloxlink-http)",
                    inline=False
                )
            ]
        )