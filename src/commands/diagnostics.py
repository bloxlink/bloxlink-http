from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
from hikari import Embed
from hikari.emojis import Emoji 
from datetime import datetime, timezone


@bloxlink.command(
    category="Miscellaneous",
    defer=False
)
class DiagnosticsCommand:
    """Gets the internal status of the bot."""

    # NOTE: These could be moved into resources.emojis but they are only used in this command.
    OK_EMOJI = Emoji.parse(":small_blue_diamond:")
    ERROR_EMOJI = Emoji.parse(":small_red_triangle_down:")

    def _status_str(self, label: str, is_ok: bool) -> str:
        return f"{self.OK_EMOJI if is_ok else self.ERROR_EMOJI} {label}"

    async def __main__(self, ctx: CommandContext):
        # Not truly the time received but close enough.
        received_at_ping = datetime.now(tz=timezone.utc) - ctx.response.interaction.created_at
        ping_seconds = received_at_ping.total_seconds()*1000
        
        await ctx.response.loading("We are fetching diagnostic information.")
        
        embed = Embed(title="Diagnostics", description=f"Ping: {ping_seconds:.0f}ms")
        embed.color = "#2f3136"
        # embed.color = "#db2323"

        embed.add_field("Services", f"""
{self._status_str("Database", bloxlink.is_mongo_ok())}
{self._status_str(f"Redis", await bloxlink.is_redis_ok())}
{self._status_str(f"Common API", bloxlink.is_bot_api_ok())}""")
        
        await ctx.response.edit(embed=embed)