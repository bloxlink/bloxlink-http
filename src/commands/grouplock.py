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


@component_author_validation(author_segment=3)
async def grouplock_view_buttons(ctx: CommandContext):
    """Handle pagination left and right button presses."""
    interaction: hikari.ComponentInteraction = ctx.interaction
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=3)

    author_id = int(custom_id_data[0])
    page_number = int(custom_id_data[1])

    guild_id = interaction.guild_id
    guild_data = await bloxlink.fetch_guild_data(guild_id, "groupLock")

    grouplock_data = {group_id: GroupLock(**value) for group_id, value in guild_data.groupLock.items()}

    paginator = Paginator(
        guild_id,
        author_id,
        source_cmd_name="grouplock",
        max_items=ITEMS_PER_PAGE,
        items=grouplock_data.items(),
        page_number=page_number,
        custom_formatter=grouplock_view_paginator,
    )

    embed = await paginator.embed
    components = await paginator.components

    message.embeds[0] = embed

    await interaction.edit_message(message, embed=embed, components=components)
    return interaction.build_deferred_response()


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        "grouplock": grouplock_view_buttons,
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
            source_cmd_name="grouplock",
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
    embed.add_field("-" * 24, "\n\n".join(entries[:lim]), inline=True)
    embed.add_field("-" * 24, "\n\n".join(entries[lim:]), inline=True)

    return embed
