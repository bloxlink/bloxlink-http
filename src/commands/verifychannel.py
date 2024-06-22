import hikari
from bloxlink_lib import get_user_account
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.ui.components import Button, TextInput, DeprecatedCustomID
from resources.ui.modals import build_modal
from resources.premium import get_premium_status
from resources import binds
from resources.api.roblox import users


VERIFY_BUTTON_ID = DeprecatedCustomID(
    content="verify_view:verify_button",
)

async def verify_button_click(ctx: CommandContext):
    yield await ctx.response.defer(True)

    roblox_account = await get_user_account(ctx.user, raise_errors=False)

    try:
        await binds.confirm_account(ctx.member, ctx.guild_id, ctx.response, roblox_account)

    finally:
        message_response = await binds.apply_binds(
            ctx.member, ctx.guild_id, roblox_account, moderate_user=True
        )

    if roblox_account:
        await ctx.response.send(
            embed=message_response.embed,
            components=message_response.action_rows,
            ephemeral=True
        )
    else:
        verification_url = await users.get_verification_link(ctx.user.id, ctx.guild_id, interaction=ctx.interaction)

        await ctx.response.send(
            f"You are not verified with Bloxlink! You can verify by going to {verification_url}",
            ephemeral=True
        )


@bloxlink.command(
    category="Administration",
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        VERIFY_BUTTON_ID: verify_button_click
    }
)
class VerifyChannelCommand(GenericCommand):
    """post a message that users can interact with to get their roles"""

    async def __main__(self, ctx: CommandContext):
        guild_id = ctx.guild_id

        guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)
        premium_status = await get_premium_status(guild_id=guild_id, interaction=ctx.interaction)

        button_text = "Verify with Bloxlink"
        message_text = "Welcome to **{server-name}!** Click the button below to Verify with Bloxlink and gain access to the rest of the server."

        if premium_status.active:
            modal = await build_modal(
                title="Verification Channel",
                command_data={},
                interaction=ctx.interaction,
                command_name=ctx.command_name,
                components=[
                    TextInput(
                        label="Verification Button Text",
                        custom_id="verify_channel:modal:verification_button_input",
                        value=button_text,
                        style=TextInput.TextInputStyle.SHORT,
                        required=True
                    ),
                    TextInput(
                        label="Verification Message",
                        custom_id="verify_channel:modal:verification_message_input",
                        value=message_text,
                        style=TextInput.TextInputStyle.PARAGRAPH,
                        min_length=1,
                        max_length=2000,
                        required=True
                    )
                ]
            )

            yield await ctx.response.send_modal(modal)

            if not await modal.submitted():
                return

            modal_data = await modal.get_data()

            button_text = modal_data["verify_channel:modal:verification_button_input"]
            message_text = modal_data["verify_channel:modal:verification_message_input"]

        else:
            yield await ctx.response.defer(True)


        button_menu = [
            Button(
                custom_id=str(VERIFY_BUTTON_ID),
                label=button_text,
                style=Button.ButtonStyle.SUCCESS,
            ),
            Button(
                label="Need help?",
                url="https://www.youtube.com/playlist?list=PLz7SOP-guESE1V6ywCCLc1IQWiLURSvBE",
            )
        ]

        await ctx.response.send(
            message_text.format(**{
                "server-name": guild.name
            }),
            components=button_menu,
            channel=await ctx.interaction.fetch_channel()
        )

        await ctx.response.send("Posted!", ephemeral=True)
