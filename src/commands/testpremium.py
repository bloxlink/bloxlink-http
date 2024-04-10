import hikari
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
        if not ctx.interaction.entitlements:
            await bloxlink.rest.create_test_entitlement(
                ctx.interaction.application_id,
                sku="1106314705867378928",
                owner_id=ctx.guild_id,
                owner_type=hikari.monetization.EntitlementOwnerType.GUILD
            )
        else:
            await bloxlink.rest.delete_test_entitlement(
                ctx.interaction.application_id,
                ctx.interaction.entitlements[0].id
            )

        return await ctx.response.send_first(f"Successfully **{'added' if not ctx.interaction.entitlements else 'removed'}** premium.")
