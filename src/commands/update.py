import hikari

from bloxlink_lib import get_user_account
from resources import binds
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import Message


@bloxlink.command(
    category="Account",
    defer=True,
    options=[
        hikari.commands.CommandOption(
            type=hikari.commands.OptionType.USER,
            name="user",
            description="update this user",
            is_required=True,
        )
    ],
    permissions=hikari.Permissions.MANAGE_GUILD | hikari.Permissions.MANAGE_ROLES,
)
class UpdateCommand(GenericCommand):
    """update the roles and nickname of a specific user"""

    async def __main__(self, ctx: CommandContext):
        try:
            target_user = list(ctx.resolved.members.values())[0] if ctx.resolved else ctx.member
        except IndexError:
            raise Message(
                message="Could not identify the user you were updating. Are they still in the server?",
            ) from None

        roblox_account = await get_user_account(target_user, raise_errors=False)

        message_response = await binds.apply_binds(
            target_user, ctx.guild_id, roblox_account, update_embed_for_unverified=True, moderate_user=True
        )

        await ctx.response.send(embed=message_response.embed, components=message_response.action_rows)
