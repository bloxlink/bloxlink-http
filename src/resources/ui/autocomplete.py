from typing import TYPE_CHECKING
import hikari

from bloxlink_lib import BaseModel, RobloxUser, RobloxGroup, get_binds, get_group, find

from resources.api.roblox import users
from resources.exceptions import RobloxAPIError, RobloxNotFound

if TYPE_CHECKING:
    from resources.commands import CommandContext


class AutocompleteOption(BaseModel):
    """Represents an autocomplete option."""

    name: str
    value: str


async def bind_category_autocomplete(ctx: "CommandContext"):
    """Autocomplete for a bind category input based upon the binds the user has."""

    binds = await get_binds(ctx.guild_id)
    bind_types = set(bind.type for bind in binds)

    return ctx.response.send_autocomplete([AutocompleteOption(name=x, value=x.lower()) for x in bind_types])


async def bind_id_autocomplete(ctx: "CommandContext"):
    """Autocomplete for bind ID inputs, expects that there is an additional category option in the
    command arguments that must be set prior to this argument."""

    interaction = ctx.interaction

    choices = [
        # base option
        AutocompleteOption(name="View all your bindings", value="view_binds")
    ]

    options = {o.name.lower(): o for o in interaction.options}

    category_option = options["category"].value.lower().strip() if options.get("category") else None
    id_option = options["id"].value.lower().strip() if options.get("id") else None

    # Only show more options if the category option has been set by the user.
    if category_option:
        category_option = "catalogAsset" if category_option == "catalogasset" else category_option

        guild_binds = await get_binds(interaction.guild_id, category=category_option)

        if id_option:
            filtered_binds = filter(
                None,
                set(
                    bind.criteria.id
                    for bind in guild_binds
                    if bind.criteria.id and str(bind.criteria.id) == id_option
                ),
            )
        else:
            filtered_binds = filter(None, set(bind.criteria.id for bind in guild_binds))

        for bind in filtered_binds:
            choices.append(AutocompleteOption(name=str(bind), value=str(bind)))

    return ctx.response.send_autocomplete(choices)


async def roblox_user_lookup_autocomplete(ctx: "CommandContext"):
    """Return a matching Roblox user from the user's input."""

    interaction = ctx.interaction
    option = next(
        x for x in interaction.options if x.is_focused
    )  # Makes sure that we get the correct command input in a generic way
    user_input = str(option.value)

    user: RobloxUser = None
    result_list: list[str] = []

    if not user_input:
        return interaction.build_response([])

    try:
        user = await users.get_user_from_string(user_input)
    except (RobloxNotFound, RobloxAPIError):
        pass

    if user:
        result_list.append(AutocompleteOption(name=f"{user.username} ({user.id})", value=str(user.id)))
    else:
        result_list.append(
            AutocompleteOption(name="No user found. Please double check the username or ID.", value="no_user")
        )

    return ctx.response.send_autocomplete(result_list)

async def roblox_group_lookup_autocomplete(ctx: "CommandContext", focused_option: hikari.AutocompleteInteractionOption, relevant_options: list[hikari.AutocompleteInteractionOption]):
    """Return a matching Roblox group from the user's input."""

    result_list: list[str] = []
    group: RobloxGroup = None

    if not focused_option.value:
        return ctx.response.send_autocomplete([
            AutocompleteOption(name="Type your group URL or ID", value="no_group")
        ])

    try:
        group = await get_group(focused_option.value)
    except (RobloxNotFound, RobloxAPIError):
        pass

    if group:
        result_list.append(AutocompleteOption(name=f"{group.name} ({group.id})", value=str(group.id)))
    else:
        result_list.append(
            AutocompleteOption(name="No group found. Please double check the ID or URL.", value="no_group")
        )

    return ctx.response.send_autocomplete(result_list)

async def roblox_group_roleset_autocomplete(ctx: "CommandContext", focused_option: hikari.AutocompleteInteractionOption, relevant_options: list[hikari.AutocompleteInteractionOption]):
    """Return a matching Roblox roleset from the user's input."""

    group_id = find(lambda o: o.name == "group", relevant_options)

    if not (focused_option and group_id):
        return ctx.response.send_autocomplete(None)

    group: RobloxGroup = None
    result_list: list[str] = []

    try:
        group = await get_group(group_id.value)
    except (RobloxNotFound, RobloxAPIError):
        pass

    if group:
        group_rolesets = filter(lambda r: r.name.lower().startswith(focused_option.value.lower()), group.rolesets.values()) if focused_option.value else group.rolesets.values()

        for roleset in group_rolesets:
            result_list.append(AutocompleteOption(name=f"{roleset.name} ({roleset.rank})", value=str(roleset.rank)))

    else:
        result_list.append(
            AutocompleteOption(name="No group found. Please double check the ID or URL.", value="no_group")
        )

    return ctx.response.send_autocomplete(result_list)
