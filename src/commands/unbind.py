from typing import get_args

import hikari
from bloxlink_lib import VALID_BIND_TYPES, GuildBind

from resources.binds import delete_bind, generate_binds_embed, get_binds
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxAPIError
from resources.pagination import Paginator, PaginatorCustomID
from resources.ui.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.ui.components import BaseCustomID, Component, TextSelectMenu, component_author_validation

MAX_BINDS_PER_PAGE = 10


class UnbindCustomID(PaginatorCustomID):
    """Represents a custom ID for /unbind command."""

    category: VALID_BIND_TYPES
    id: int | None = None


class TextOptionValue(BaseCustomID):
    """Represents the value for the text menu."""

    type: VALID_BIND_TYPES
    id: int | None = None
    index: int


async def embed_formatter(
    page_number: int, items: list[GuildBind], _guild_id: str | int, max_pages: int
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

    embed = hikari.Embed(title="Remove a Binding")

    if not items:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    embed.description = "Select which bind(s) you want to remove from the menu below!"

    if max_pages > 1:
        embed.description += (
            "\n\n> Don't see the binding that you're looking for? "
            "Use the buttons below to have the menu scroll to a new page."
        )

    await generate_binds_embed(items, embed)

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    return embed


async def component_generator(items: list[GuildBind], custom_id: UnbindCustomID) -> list[Component] | None:
    """Generate the components for the paginator."""

    text_menu = TextSelectMenu(
        custom_id=UnbindCustomID(
            command_name="unbind",
            user_id=custom_id.user_id,
            category=custom_id.category,
            id=custom_id.id,
            section="sel_discard",
        ),
        placeholder="Select which bind should be removed",
        min_values=1,
        max_values=len(items),
    )

    if not items:
        return None

    for i, bind in enumerate(items):
        bind_type = bind.type.title()
        bind_name = str(bind.entity).replace("**", "")

        try:
            await bind.entity.sync()
        except RobloxAPIError:
            pass

        text_menu.options.append(
            TextSelectMenu.Option(
                label=bind.short_description.replace("**", "")[:100],
                value=str(
                    TextOptionValue(
                        type=bind.type,
                        id=bind.criteria.id,
                        index=i,
                    )
                ),
                description=f"{bind_type}: {bind_name}",
            )
        )

    return [text_menu]


@component_author_validation(parse_into=UnbindCustomID, defer=True)
async def unbind_pagination_button(ctx: CommandContext, custom_id: UnbindCustomID):
    """Handle the left and right buttons for pagination."""

    interaction = ctx.interaction

    author_id = custom_id.user_id
    page_number = custom_id.page_number

    category = custom_id.category
    id_filter = custom_id.id

    guild_id = interaction.guild_id

    bindings = await get_binds(guild_id, category=category, bind_id=id_filter)

    paginator = Paginator(
        guild_id,
        author_id,
        max_items=MAX_BINDS_PER_PAGE,
        items=bindings,
        page_number=page_number,
        custom_formatter=embed_formatter,
        component_generation=component_generator,
        custom_id_format=UnbindCustomID(
            command_name="unbind", user_id=author_id, category=category, id=id_filter
        ),
        include_cancel_button=True,
    )

    embed = await paginator.embed
    components = await paginator.components

    await ctx.response.send(embed=embed, components=components, edit_original=True)


@component_author_validation(parse_into=UnbindCustomID, defer=True)
async def unbind_discard_binding(ctx: CommandContext, custom_id: UnbindCustomID):
    """Handles the removal of a binding from the list."""

    response = ctx.response

    interaction = ctx.interaction
    guild_id = interaction.guild_id
    user_id = interaction.user.id

    page_number = custom_id.page_number
    category = custom_id.category
    id_filter = custom_id.id

    guild_binds = await get_binds(interaction.guild_id, category=category, bind_id=id_filter)

    selected_values = interaction.values

    bind_deletions: list[GuildBind] = []

    # We need to retrieve the page they were on and find the corresponding bind based on the index
    paginator = Paginator(
        guild_id,
        user_id,
        max_items=MAX_BINDS_PER_PAGE,
        items=guild_binds,
        page_number=page_number,
        custom_formatter=embed_formatter,
        component_generation=component_generator,
        custom_id_format=UnbindCustomID(
            command_name="unbind", user_id=user_id, category=category, id=id_filter
        ),
        include_cancel_button=True,
        item_filter=viewbinds_item_filter,
    )

    for value in selected_values:
        parsed_value = TextOptionValue.from_str(value)
        bind = paginator.current_items[parsed_value.index]

        if bind and bind.type != parsed_value.type:
            # probably the wrong bind, error out
            return await response.send_first(
                "You selected a bind that doesn't match the type you're trying to unbind.", ephemeral=True
            )

        bind_deletions.append(bind)

    await delete_bind(guild_id, *bind_deletions)

    await response.send("Your chosen bindings have been removed.", ephemeral=True)


@component_author_validation(parse_into=UnbindCustomID, defer=False)
async def unbind_cancel_button(ctx: CommandContext, _custom_id: UnbindCustomID):
    """Handle the cancel button press."""

    interaction = ctx.interaction
    response = ctx.response

    await bloxlink.rest.delete_message(interaction.channel_id, interaction.message)

    return await response.send_first("Prompt cancelled.", ephemeral=True)


def viewbinds_item_filter(items: list[GuildBind]):
    """Sorts the given binds."""

    return sorted(items, key=lambda item: item.criteria.id)


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    options=[
        hikari.commands.CommandOption(
            type=hikari.commands.OptionType.STRING,
            name="category",
            description="Choose what type of binds you want to see.",
            is_required=True,
            autocomplete=True,
        ),
        hikari.commands.CommandOption(
            type=hikari.commands.OptionType.STRING,
            name="id",
            description="Select which ID you want to see your bindings for.",
            is_required=True,
            autocomplete=True,
        ),
    ],
    accepted_custom_ids={
        "unbind:page": unbind_pagination_button,
        "unbind:sel_discard": unbind_discard_binding,
        "unbind:cancel": unbind_cancel_button,
    },
    autocomplete_handlers={
        "category": bind_category_autocomplete,
        "id": bind_id_autocomplete,
    },
    dm_enabled=False,
)
class UnbindCommand(GenericCommand):
    """Delete some binds from your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"] if ctx.options["id"] != "view_binds" else None

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        category = "catalogAsset" if category == "catalogasset" else category.lower()
        if category not in get_args(VALID_BIND_TYPES):
            await ctx.response.send(
                content="The category you gave was not valid. Please choose from the autocomplete options!"
            )
            return

        guild_binds = await get_binds(
            guild_id, bind_id=int(id_option) if id_option and id_option.isdigit() else None, category=category
        )

        paginator = Paginator(
            guild_id,
            user_id,
            max_items=MAX_BINDS_PER_PAGE,
            items=guild_binds,
            custom_formatter=embed_formatter,
            component_generation=component_generator,
            custom_id_format=UnbindCustomID(
                command_name="unbind", user_id=user_id, category=category, id=id_option
            ),
            include_cancel_button=True,
            item_filter=viewbinds_item_filter,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)
