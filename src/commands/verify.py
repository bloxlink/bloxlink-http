from bloxlink_lib import get_user_account
from resources import binds
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand


@bloxlink.command(
    category="Account",
    defer=True,
    aliases=["getrole"]
)
class VerifyCommand(GenericCommand):
    """Link your Roblox account to your Discord account and get your server roles."""

    async def __main__(self, ctx: CommandContext):
        roblox_account = await get_user_account(ctx.user, raise_errors=False)

        try:
            await binds.confirm_account(ctx.member, ctx.guild_id, ctx.response, roblox_account)

        finally:
            message_response = await binds.apply_binds(
                ctx.member, ctx.guild_id, roblox_account, moderate_user=True
            )

            await ctx.response.send(
                content=message_response.content,
                embed=message_response.embed,
                components=message_response.action_rows
            )
