from typing import get_args

import hikari
from bloxlink_lib import VALID_BIND_TYPES, GuildBind, get_binds

from resources.binds import generate_binds_embed
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.ui.pagination import Paginator, PaginatorCustomID
from resources.ui.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.ui.components import component_author_validation, BaseCommandCustomID

MAX_BINDS_PER_PAGE = 5


class ViewbindsCustomID(PaginatorCustomID):
    """Represents a custom ID for /unbind command."""

    category: VALID_BIND_TYPES
    id: int | None = None


async def embed_formatter(page_number: int, items: list[GuildBind], _guild_id: str | int, max_pages: int):
    """Generates the components for the viewbinds page.

    Args:
        page_number (int): The page number of the page to build.
        items (list): The bindings to show on the page.
        _guild_id (str | int): Unused, the ID of the guild that the command was run in.
        max_pages (int): The page number of the last page that can be built.

    Returns:
        hikari.Embed: The formatted embed.
    """

    embed = hikari.Embed(title="Bloxlink Role Binds")

    if not items:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    embed.description = (
        "Use </bind:836429412810358807> to make a new bind, "  # FIXME: command IDs
        "or </unbind:836429412810358805> to delete a bind."
    )

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    await generate_binds_embed(items, embed)

    return embed


def viewbinds_item_filter(items: list[GuildBind]):
    """Sorts the given binds."""

    return sorted(items, key=lambda item: item.criteria.id)


@component_author_validation(parse_into=ViewbindsCustomID, ephemeral=False, defer=False)
async def viewbinds_button(ctx: CommandContext, custom_id: ViewbindsCustomID):
    """Handle pagination left and right button presses."""
    # TODO: Support deferring via yield for paginator.
    ctx.response.defer_through_rest = True
    await ctx.response.defer()

    interaction = ctx.interaction

    author_id = custom_id.user_id
    page_number = custom_id.page_number

    category = custom_id.category
    id_filter = custom_id.id

    guild_id = interaction.guild_id

    guild_data = await get_binds(guild_id, bind_id=id_filter, category=category)

    paginator = Paginator(
        guild_id,
        author_id,
        max_items=MAX_BINDS_PER_PAGE,
        items=guild_data,
        page_number=page_number,
        custom_formatter=embed_formatter,
        custom_id_format=ViewbindsCustomID(
            command_name="viewbinds",
            user_id=author_id,
            category=category,
            id=id_filter,
        ),
        item_filter=viewbinds_item_filter,
    )

    embed = await paginator.embed
    components = await paginator.components

    await ctx.response.send(embed=embed, components=components, edit_original=True)


@bloxlink.command(
    category="Account",
    defer=True,
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
        BaseCommandCustomID(
            command_name="viewbinds",
            section="button"
        ): viewbinds_button,
    },
    autocomplete_handlers={
        "category": bind_category_autocomplete,
        "id": bind_id_autocomplete,
    },
)
class ViewBindsCommand(GenericCommand):
    """View your binds for your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"].lower()
        id_option = ctx.options["id"] if ctx.options["id"] != "view_binds" else None

        guild_id = ctx.guild_id
        user_id = ctx.user.id

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
            custom_id_format=ViewbindsCustomID(
                command_name="viewbinds",
                user_id=user_id,
                category=category,
                id=id_option,
            ),
            item_filter=viewbinds_item_filter,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)
