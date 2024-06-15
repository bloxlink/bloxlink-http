import hikari
from hikari.commands import CommandOption, OptionType

from bloxlink_lib import get_group, CoerciveSet, RobloxAPIError, GroupLock
from bloxlink_lib.database import fetch_guild_data, update_guild_data
from resources.ui.autocomplete import roblox_group_lookup_autocomplete, roblox_group_roleset_autocomplete, AutocompleteOption
from resources.ui import TextSelectMenu, Component, component_author_validation, disable_components, BaseCommandCustomID
from resources.ui.pagination import Paginator, PaginatorCustomID
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxNotFound, Error


MAX_GROUPS_PER_PAGE = 5

class TextOptionValue(PaginatorCustomID):
    """Represents the value for the text menu."""

    group_id: str



async def return_paginator_items(ctx: CommandContext) -> list[tuple[str, GroupLock]]:
    """Return the items for the paginator"""

    group_lock = (await fetch_guild_data(ctx.guild_id, "groupLock")).groupLock or {}

    return list(group_lock.items())

@component_author_validation(parse_into=PaginatorCustomID, defer=True)
async def discard_group(ctx: CommandContext, custom_id: PaginatorCustomID):
    """Handles the removal of a group from the list."""

    response = ctx.response
    interaction = ctx.interaction
    guild_id = interaction.guild_id
    selected_values = interaction.values

    for value in selected_values:
        parsed_value = TextOptionValue.from_str(value)
        group_id = parsed_value.group_id
        group_lock = (await fetch_guild_data(guild_id, "groupLock")).groupLock or {}

        if not group_lock.get(group_id):
            raise Error("This group is not in your group lock.")

        del group_lock[group_id]
        await update_guild_data(guild_id, groupLock=group_lock)


    await response.send("Successfully **removed** this group from your **Group-Lock!**")
    await disable_components(interaction)


async def grouplock_autocomplete(ctx: CommandContext, focused_option: hikari.AutocompleteInteractionOption, relevant_options: list[hikari.AutocompleteInteractionOption]):
    """Return a matching Roblox group from the user's input."""

    guild_id = ctx.guild_id

    result_list: list[AutocompleteOption] = []
    group_lock = (await fetch_guild_data(guild_id, "groupLock")).groupLock or {}

    if not group_lock:
        return ctx.response.send_autocomplete([
            AutocompleteOption(name="No group locks exist.", value="no_group")
        ])

    for group_id in group_lock.keys():
        try:
            group = await get_group(group_id)
        except (RobloxNotFound, RobloxAPIError):
            result_list.append(
                AutocompleteOption(name=group_id, value=group_id)
            )
        else:
            result_list.append(
                AutocompleteOption(name=f"{group.name} ({group.id})", value=str(group.id))
            )

    return ctx.response.send_autocomplete(result_list)

async def generate_page_embed(items: tuple[str, GroupLock], embed: hikari.Embed):
    """Generate the embed for the page."""

    for group_id, group_lock in items:
        embed.add_field(
            name=f"{group_lock.groupName} ({group_id})",
            value=(f"> **Allow these rolesets ONLY:** {', '.join([str(r) for r in group_lock.roleSets]) or 'None. Users must be in the group.'}\n"
                f"> **DM Message:** {(group_lock.dmMessage or '(Use default)')[:200]}\n"
                f"> **Action when users AREN'T verified:** {group_lock.unverifiedAction or 'kick'}\n"
                f"> **Action when users ARE verified:** {group_lock.verifiedAction or 'kick'}\n"
            )
        )

async def component_generator(items: tuple[str, GroupLock], custom_id: PaginatorCustomID) -> list[Component] | None:
    """Generate the components for the paginator."""

    text_menu = TextSelectMenu(
        custom_id=PaginatorCustomID(
            command_name="grouplock",
            user_id=custom_id.user_id,
            section="discard",
        ),
        placeholder="Select which group should be removed",
        min_values=1,
        max_values=len(items),
    )

    if not items:
        return None

    for group_id, group_lock in items:
        text_menu.options.append(
            TextSelectMenu.Option(
                label=f"{(group_lock.groupName + " ") if group_lock.groupName else ''}({group_id})"[:100],
                value=str(
                    TextOptionValue(
                        group_id=group_id,
                        user_id=custom_id.user_id,
                        command_name="grouplock"
                    )
                ),
            )
        )

    return [text_menu]

async def embed_formatter(
    page_number: int, items: tuple[str, dict], _guild_id: str | int, max_pages: int
) -> hikari.Embed:
    """Generates the embed for the page.

    Args:
        page_number (int): The page number of the page to build.
        items (list): The bindings to show on the page.
        _guild_id (str | int): Unused, the ID of the guild that the command was run in.
        max_pages (int): The page number of the last page that can be built.

    Returns:
        hikari.Embed: The formatted embed.
    """

    embed = hikari.Embed(title="Remove a Group Lock")

    if not items:
        embed.description = (
            "> You have no groups added to your group-lock. "
            "Use `/grouplock add` to make a new group-lock."
        )
        return embed

    embed.description = "Select which groups(s) you want to remove from the menu below!"

    if max_pages > 1:
        embed.description += (
            "\n\n> Don't see the group that you're looking for? "
            "Use the buttons below to have the menu scroll to a new page."
        )

    await generate_page_embed(items, embed)

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    return embed

@bloxlink.command(
    category="Premium",
    defer=True,
    premium=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        BaseCommandCustomID(
            command_name="grouplock",
            section="discard",
        ): discard_group,
        # "grouplock:cancel": unbind_cancel_button,
    },
    paginator_options={
        "return_items": return_paginator_items,
        "format_items": embed_formatter,
        "component_generator": component_generator,
        "filter_items": None
    }
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
        verified_action = ctx.options.get("verified_action") or "kick"
        unverified_action = ctx.options.get("unverified_action") or "kick"

        group_lock: dict[str, GroupLock] = (await fetch_guild_data(guild, "groupLock")).groupLock or {}
        group_lock_group = group_lock.get(group_value) or GroupLock(
            groupName="",
            dmMessage=None,
            roleSets=[],
            verifiedAction=verified_action,
            unverifiedAction=unverified_action
        )

        group_lock_rolesets: CoerciveSet[int] = CoerciveSet(int, group_lock_group.roleSets)

        if roleset_value:
            group_lock_rolesets.add(roleset_value)

        if group_value in group_lock and not roleset_value:
            raise Error("The Roblox group is already in your server's group lock")

        try:
            group = await get_group(group_value)
        except RobloxNotFound as e:
            raise RobloxNotFound("The Roblox group you were searching for does not exist.") from e

        if len(group_lock) >= 50 or len(group_lock_rolesets) >= 50:
            raise Error("You cannot have more than 50 groups and 50 rolesets in your server's group lock")

        group_lock_group.groupName = group.name
        group_lock_group.roleSets = list(group_lock_rolesets)

        group_lock[group_value] = group_lock_group

        await update_guild_data(guild, groupLock={k:v.model_dump() for k,v in group_lock.items()})

        await ctx.response.send("Successfully saved your **Group-Lock!**")

    @bloxlink.subcommand(
        name="remove",
    )
    async def remove(self, ctx: CommandContext):
        """Remove a group lock to your server."""

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        paginator = Paginator(
            guild_id,
            user_id,
            max_items=MAX_GROUPS_PER_PAGE,
            items=await return_paginator_items(ctx),
            custom_formatter=embed_formatter,
            component_generation=component_generator,
            custom_id_format=PaginatorCustomID(
                command_name="grouplock",
                user_id=user_id,
            ),
            include_cancel_button=True,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)

    @bloxlink.subcommand(
        name="list",
    )
    async def list(self, ctx: CommandContext):
        """List all groups in your server's group lock."""

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        paginator = Paginator(
            guild_id,
            user_id,
            max_items=MAX_GROUPS_PER_PAGE,
            items=await return_paginator_items(ctx),
            custom_formatter=embed_formatter,
            component_generation=None,
            custom_id_format=PaginatorCustomID(
                command_name="grouplock",
                user_id=user_id,
                # generate_components=False
            ),
            include_cancel_button=False,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)
