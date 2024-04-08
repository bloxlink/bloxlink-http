import hikari
from hikari.commands import CommandOption, OptionType

from bloxlink_lib import RobloxUser, get_group
from resources.ui.autocomplete import roblox_group_lookup_autocomplete, roblox_group_roleset_autocomplete
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxNotFound


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
)
class GroupLockCommand(GenericCommand):
    """prevent users from joining your server if they aren't in a certain Roblox group."""

    async def __main__(self, ctx: CommandContext):
        raise NotImplementedError("This command has sub-commands and cannot be run directly.")

    @bloxlink.subcommand(
        name="add",
        options=[
            CommandOption(
                type=OptionType.STRING,
                name="group",
                description="Please specify your group ID or URL.",
                is_required=True,
                autocomplete=True,
            ),
            CommandOption(
                type=OptionType.STRING,
                name="rolesets",
                description="What Roleset should be allowed in your server? You can specify multiple.",
                is_required=True,
                autocomplete=True,
            ),
        ],
        autocomplete_handlers={
            "group": roblox_group_lookup_autocomplete,
            "rolesets": roblox_group_roleset_autocomplete
        },
    )
    async def add(self, ctx: CommandContext):
        """Add a group lock to your server."""

        guild = ctx.guild_id
        target = ctx.options["group"]

        results: list[str] = []
        account: RobloxUser = None
        discord_ids: list[int] = []

        if target == "no_group":
            raise RobloxNotFound("The Roblox group you were searching for does not exist.")

        try:
            group = await get_group(target)
        except RobloxNotFound as e:
            raise RobloxNotFound("The Roblox user you were searching for does not exist.") from e

