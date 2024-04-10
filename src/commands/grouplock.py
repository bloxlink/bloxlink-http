import hikari
from hikari.commands import CommandOption, OptionType

from bloxlink_lib import get_group, CoerciveSet
from bloxlink_lib.database import fetch_guild_data, update_guild_data
from resources.ui.autocomplete import roblox_group_lookup_autocomplete, roblox_group_roleset_autocomplete
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxNotFound, Error


@bloxlink.command(
    category="Premium",
    defer=True,
    premium=True,
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
                name="roleset",
                description="What Roleset should be allowed in your server?",
                is_required=False,
                autocomplete=True,
            ),
            CommandOption(
                type=OptionType.STRING,
                name="verified_action",
                description="What action should be taken to VERIFIED users who aren't in your group?",
                is_required=False,
                choices=[
                    hikari.CommandChoice(name="Kick & DM them", value="kick"),
                    hikari.CommandChoice(name="DM them", value="dm"),
                ],
            ),
            CommandOption(
                type=OptionType.STRING,
                name="unverified_action",
                description="What action should be taken to UNVERIFIED users who aren't in your group?",
                is_required=False,
                choices=[
                    hikari.CommandChoice(name="Kick & DM them", value="kick"),
                    hikari.CommandChoice(name="DM them", value="dm"),
                ],
            ),
        ],
        autocomplete_handlers={
            "group": roblox_group_lookup_autocomplete,
            "roleset": roblox_group_roleset_autocomplete
        },
    )
    async def add(self, ctx: CommandContext):
        """Add a group lock to your server."""

        guild = ctx.guild_id

        group_value = ctx.options["group"]
        roleset_value = ctx.options.get("roleset")
        verified_action = ctx.options.get("verified_action")
        unverified_action = ctx.options.get("unverified_action")

        group_lock = (await fetch_guild_data(guild, "groupLock")).groupLock or {}
        group_lock_group = group_lock.get(group_value) or {}

        group_lock_rolesets: CoerciveSet[int] = CoerciveSet(int, group_lock_group.get("roleSets", []))

        if roleset_value:
            group_lock_rolesets.add(roleset_value)

        if group_value in group_lock and not roleset_value:
            raise RobloxNotFound("The Roblox group is already in your server's group lock")

        try:
            group = await get_group(group_value)
        except RobloxNotFound as e:
            raise RobloxNotFound("The Roblox group you were searching for does not exist.") from e

        if len(group_lock) >= 50 or len(group_lock_rolesets) >= 50:
            raise Error("You cannot have more than 50 groups and 50 rolesets in your server's group lock")

        group_lock[group_value] = {"groupName": group.name, "dmMessage": None, "roleSets": list(group_lock_rolesets), "verifiedAction": verified_action, "unverifiedAction": unverified_action}

        await update_guild_data(guild, groupLock=group_lock)

        await ctx.response.send("Successfully saved your **Group-Lock!**")
