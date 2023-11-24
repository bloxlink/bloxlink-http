import hikari
from hikari.commands import CommandOption, OptionType

from resources.binds import join_bind_strings
from resources.bloxlink import GroupLock
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.component_helper import component_author_validation, get_custom_id_data
from resources.constants import RED_COLOR, UNICODE_BLANK
from resources.pagination import Paginator

ITEMS_PER_PAGE = 2
DELETE_ITEMS_PER_PAGE = 3


@component_author_validation(author_segment=4, defer=False)
async def grouplock_view_buttons(ctx: CommandContext):
    """Handle pagination left and right button presses."""
    interaction: hikari.ComponentInteraction = ctx.interaction
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=4)

    author_id = int(custom_id_data[0])
    page_number = int(custom_id_data[1])

    guild_id = interaction.guild_id
    guild_data = await bloxlink.fetch_guild_data(guild_id, "groupLock")

    grouplock_data = {group_id: GroupLock(**value) for group_id, value in guild_data.groupLock.items()}

    paginator = Paginator(
        guild_id,
        author_id,
        source_cmd_name="grouplock:view",
        max_items=ITEMS_PER_PAGE,
        items=grouplock_data.items(),
        page_number=page_number,
        custom_formatter=grouplock_view_paginator,
    )

    embed = await paginator.embed
    components = await paginator.components

    message.embeds[0] = embed

    yield (
        interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)
        .clear_attachments()
        .add_embed(embed)
        .add_component(*components)
    )

    # await interaction.create_initial_response(
    #     hikari.ResponseType.MESSAGE_UPDATE, embed=embed, components=components
    # )

    # # await interaction.edit_message(message, embed=embed, components=components)
    # return interaction.build_deferred_response(
    #     hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    # )


@component_author_validation(author_segment=4, defer=False)
async def grouplock_delete_page_buttons(ctx: CommandContext):
    """Handle pagination left and right button presses."""
    interaction: hikari.ComponentInteraction = ctx.interaction
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=4)

    author_id = int(custom_id_data[0])
    page_number = int(custom_id_data[1])

    guild_id = interaction.guild_id
    guild_data = await bloxlink.fetch_guild_data(guild_id, "groupLock")

    grouplock_data = {group_id: GroupLock(**value) for group_id, value in guild_data.groupLock.items()}

    paginator = Paginator(
        guild_id,
        author_id,
        source_cmd_name="grouplock:delete",
        max_items=DELETE_ITEMS_PER_PAGE,
        items=grouplock_data.items(),
        custom_formatter=grouplock_delete_paginator,
        component_generation=grouplock_delete_components,
        page_number=page_number,
    )

    embed = await paginator.embed
    components = await paginator.components

    message.embeds[0] = embed

    response = (
        interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE).clear_attachments().add_embed(embed)
    )
    # Can't simply .add_component(*components) because of a positional argument error 🙄
    for component in components:
        response.add_component(component)

    yield response


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        "grouplock:view": grouplock_view_buttons,
        "grouplock:delete": grouplock_delete_page_buttons,
        # "grouplock:sel_delete": None,
    },
    dm_enabled=False,
)
class GroupLockCommand:
    """Manage the grouplock in this server."""

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="group",
                description="A Roblox group ID",
                is_required=True,
            ),
        ]
    )
    async def add(self, ctx: CommandContext):
        """Add a group to the grouplock."""

        await ctx.interaction.edit_initial_response(content="WIP.")

    @bloxlink.subcommand()
    async def delete(self, ctx: CommandContext):
        """Remove a group from the grouplock."""

        interaction = ctx.interaction
        author_id = ctx.member.id

        guild_id = interaction.guild_id
        guild_data = await bloxlink.fetch_guild_data(guild_id, "groupLock")

        grouplock_data = {group_id: GroupLock(**value) for group_id, value in guild_data.groupLock.items()}

        paginator = Paginator(
            guild_id,
            author_id,
            source_cmd_name="grouplock:delete",
            max_items=DELETE_ITEMS_PER_PAGE,
            items=grouplock_data.items(),
            custom_formatter=grouplock_delete_paginator,
            component_generation=grouplock_delete_components,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)

    @bloxlink.subcommand()
    async def view(self, ctx: CommandContext):
        """View the groups in your grouplock."""

        interaction = ctx.interaction
        author_id = ctx.member.id

        guild_id = interaction.guild_id
        guild_data = await bloxlink.fetch_guild_data(guild_id, "groupLock")

        grouplock_data = {group_id: GroupLock(**value) for group_id, value in guild_data.groupLock.items()}

        paginator = Paginator(
            guild_id,
            author_id,
            source_cmd_name="grouplock:view",
            max_items=ITEMS_PER_PAGE,
            items=grouplock_data.items(),
            custom_formatter=grouplock_view_paginator,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)


async def grouplock_view_paginator(
    page_number: int, items: list, _guild_id: int | str, max_pages: int
) -> hikari.Embed:
    """Generates the embed for the grouplock paginator."""
    embed = hikari.Embed()
    embed.title = "**Bloxlink Group Lock**"
    embed.color = RED_COLOR

    if len(items) == 0:
        embed.description = (
            "> You don't have any groups set in your grouplock! Try using `/grouplock add` to add one."
        )
        return embed

    embed.description = (
        "Use </grouplock add:1165777765908353105> to make another grouplock, "
        f"or </grouplock delete:1165777765908353105> to delete one.\n{UNICODE_BLANK}"
    )
    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    entries = []
    for entry in items:
        group_id = entry[0]
        data: GroupLock = entry[1]

        entry_items = [
            f"**{data.groupName if data.groupName else 'Unknown Group'}** ({group_id})",
            f"DM Message: `{data.dmMessage}`" if data.dmMessage else None,
            f"Rolesets: {data.roleSets}" if data.roleSets else None,
            f"Verified action: `{data.verifiedAction.capitalize() if data.verifiedAction else 'Kick'}`",
            f"Unverified action: `{data.unverifiedAction.capitalize() if data.unverifiedAction else 'Kick'}`",
        ]
        entry_items = list(filter(None, entry_items))
        entries.append(join_bind_strings(entry_items))

    lim = len(entries) // 2
    if lim != 0:
        embed.add_field("-" * 24, "\n\n".join(entries[:lim]), inline=True)
    embed.add_field("-" * 24, "\n\n".join(entries[lim:]), inline=True)

    return embed


async def grouplock_delete_paginator(
    page_number: int, items: list, _guild_id: int | str, max_pages: int
) -> hikari.Embed:
    embed = hikari.Embed()
    embed.title = "**Bloxlink Group Lock**"
    embed.color = RED_COLOR

    if len(items) == 0:
        embed.description = "> You have no grouplocks made! Use `/grouplock add` to make a new one."
        return embed

    embed.description = "**Select which grouplock(s) you want to remove from the menu below!**"

    if max_pages != 1:
        embed.description += (
            "\n\n> Don't see the grouplock that you're looking for? "
            "Use the buttons below to have the menu scroll to a new page."
        )

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")
    return embed


async def grouplock_delete_components(items: list, user_id: int | str, extra_custom_ids: str):
    """Generates the selection component for the /grouplock delete command."""
    selection_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"grouplock:sel_delete:{user_id}:{extra_custom_ids}",
        placeholder="Select which grouplock should be removed.",
        min_values=1,
    )

    if not items:
        selection_menu.set_is_disabled(True)
        selection_menu.add_option("No group locks to remove", "N/A")
        selection_menu.set_placeholder(
            "You have no group locks to remove. Use /grouplock add to make some first!"
        )
        return selection_menu.parent

    for entry in items:
        group_id = entry[0]
        data: GroupLock = entry[1]

        label = f"{data.groupName if data.groupName else '(Name Unavailable)'} ({group_id})"

        selection_menu.add_option(
            label[:100],
            str(group_id),
            description=f"Rank(s): {data.roleSets if data.roleSets else 'N/A'}",
        )

    selection_menu.set_max_values(len(selection_menu.options))

    return selection_menu.parent
