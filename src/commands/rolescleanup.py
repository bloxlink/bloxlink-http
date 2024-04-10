from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.constants import DEVELOPER_GUILDS
import hikari


@bloxlink.command(
    category="Miscellaneous",
    developer_only=False,
    defer=True,
    defer_with_ephemeral=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    # guild_ids=DEVELOPER_GUILDS
)
class RolesCleanupCommand(GenericCommand):
    """clean up any roles without a color"""

    async def __main__(self, ctx: CommandContext):
        guild_id = ctx.guild_id

        roles = await bloxlink.fetch_roles(guild_id)

        for role in roles.values():
            if str(role.color) == "#000000" and not role.is_managed and role.name != "@everyone":
                try:
                    await bloxlink.rest.delete_role(guild_id, role.id)
                except hikari.ForbiddenError:
                    pass

        await ctx.response.send("Roles cleaned up.")
