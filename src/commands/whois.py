from resources.bloxlink import instance as bloxlink
import resources.users as users
from resources.models import CommandContext
from resources.exceptions import UserNotVerified
from hikari.commands import CommandOption, OptionType
from hikari import ButtonStyle
from resources.emojis import ROBLOX_SIMPLE_EMOJI
from resources.utils import fetch
from resources.exceptions import RobloxNotFound


@bloxlink.command(
    category="Account",
    defer=True,
    options=[
        CommandOption(
            type=OptionType.USER,
            name="user",
            description="Retrieve the Roblox information of this user",
            is_required=False
        )
    ]
)
class WhoisCommand:
    """Retrieve the Roblox information of a user."""

    async def __main__(self, ctx: CommandContext):
        target_user = list(ctx.resolved.users.values())[0] if ctx.resolved else ctx.member
        
        try:
            roblox_account: users.RobloxAccount = await users.get_user_account(target_user)
        except UserNotVerified:
            if target_user == ctx.member:
                raise UserNotVerified("You are not verified with Bloxlink!")
            else:
                raise UserNotVerified("This user is not verified with Bloxlink!")

        is_online = False

        try:
            status, req = await fetch("GET", f"https://api.roblox.com/users/{roblox_account.id}/onlinestatus/", raise_on_failure=False)
            is_online: bool = status["IsOnline"] if req.status == 200 else False
        except Exception: 
            raise RobloxNotFound()
            
        info_embed = await users.format_embed(roblox_account, target_user) 
        row = bloxlink.rest.build_message_action_row(
            ).add_button(ButtonStyle.LINK, roblox_account.profile_url
                ).set_label("Visit Profile"
                ).set_emoji(ROBLOX_SIMPLE_EMOJI
                ).add_to_container(        
            ).add_button(ButtonStyle.SUCCESS if is_online else ButtonStyle.SECONDARY, "online_status"
                ).set_label("Online" if is_online else "Offline"
                ).set_is_disabled(True
                ).add_to_container()
            
        await ctx.response.send(embed=info_embed, components=[row])