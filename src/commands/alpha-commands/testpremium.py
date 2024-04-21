import hikari
from bloxlink_lib.database import update_guild_data, fetch_guild_data
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.constants import DEVELOPER_GUILDS


@bloxlink.command(
    developer_only=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    # guild_ids=DEVELOPER_GUILDS
)
class TestPremiumCommand(GenericCommand):
    """adds/remove premium from server"""

    async def __main__(self, ctx: CommandContext):
        guild_id = ctx.interaction.guild_id

        added_premium: bool = False

        try:
            if not ctx.interaction.entitlements:
                await bloxlink.rest.create_test_entitlement(
                    ctx.interaction.application_id,
                    sku="1106314705867378928",
                    owner_id=guild_id,
                    owner_type=hikari.monetization.EntitlementOwnerType.GUILD
                )
                added_premium = True
            else:
                await bloxlink.rest.delete_test_entitlement(
                    ctx.interaction.application_id,
                    ctx.interaction.entitlements[0].id
                )
        except hikari.errors.BadRequestError:
            existing_premium = (await fetch_guild_data(guild_id, "premium")).premium or {}
            added_premium = not existing_premium.get("active")

            await update_guild_data(guild_id, premium={"active": added_premium, "type": "pro/lifetime"})

        return await ctx.response.send_first(f"Successfully **{'added' if added_premium else 'removed'}** premium.")
