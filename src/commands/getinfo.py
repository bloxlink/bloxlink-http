from hikari.commands import CommandOption, OptionType
import hikari

from bloxlink_lib import get_user
from resources.api.roblox import users
from resources.bloxlink import bloxlink
from resources.exceptions import UserNotVerified
from resources.commands import CommandContext, GenericCommand


@bloxlink.command(
    category="Account",
    defer=True,
    options=[
        CommandOption(
            type=OptionType.USER,
            name="discord_user",
            description="Retrieve the Roblox information of this user",
            is_required=False,
        ),
        CommandOption(
            type=OptionType.STRING,
            name="roblox_name",
            description="Retrieve the Roblox information by Roblox username",
            is_required=False,
        ),
        CommandOption(
            type=OptionType.STRING,
            name="roblox_id",
            description="Retrieve the Roblox information by Roblox ID",
            is_required=False,
        )
    ],
)
class GetInfoCommand(GenericCommand):
    """retrieve the Roblox information of a user"""

    async def __main__(self, ctx: CommandContext):
        lookup_kwargs = {}
        options = ctx.options
        target_user: hikari.User | hikari.InteractionMember = None

        if options.get("roblox_name"):
            lookup_kwargs["roblox_username"] = options["roblox_name"]
        elif options.get("roblox_id"):
            lookup_kwargs["roblox_id"] = options["roblox_id"]
        else:
            target_user = list(ctx.resolved.users.values())[0] if ctx.resolved else ctx.member
            lookup_kwargs["user"] = target_user

        try:
            roblox_account = await get_user(**lookup_kwargs, guild_id=ctx.guild_id)

        except UserNotVerified:
            if target_user == ctx.member:
                raise UserNotVerified("You are not verified with Bloxlink! Please run `/verify` to verify.") from None

            raise UserNotVerified("This user is not verified with Bloxlink!") from None

        info_embeds = await users.format_embed(roblox_account, target_user, ctx.guild_id)

        await ctx.response.send(embeds=info_embeds)
