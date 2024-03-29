from typing import TYPE_CHECKING

from bloxlink_lib import BaseModel, RobloxUser, RobloxGroup, get_binds, get_group

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
