from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.binds import count_binds, get_bind_desc, create_bind
from resources.models import CommandContext
from resources.component_helper import (
    check_all_modified,
    set_custom_id_data,
    set_components,
    get_custom_id_data,
)
from hikari.commands import CommandOption, OptionType
import hikari
import re

# Obscure unicode character, counts as 2 chars for length but is unique enough for splitting w/o worry.
SPLIT_CHAR = "\U0001D15D"
GROUP_RANK_CRITERIA = {
    "equ": "Rank must match exactly...",
    "gte": "Rank must be greater than or equal to...",
    "lte": "Rank must be less than or equal to...",
    "rng": "Rank must be within 2 rolesets...",
    "gst": "User must NOT be a member of this group.",
    "all": "User must be a member of this group.",
}
GROUP_RANK_CRITERIA_TEXT = {
    "equ": "People with the rank",
    "gte": "People with a rank greater than or equal to",
    "lte": "People with a rank less than or equal to",
    "rng": "People with a rank between",
    "gst": "People who are not in this group",
    "all": "People who are in this group",
}


async def bind_menu_select_criteria(interaction: hikari.ComponentInteraction):
    message = interaction.message

    # depending on choice, show more select menus to message
    bind_choice = interaction.values[0]

    show_roleset_menu = False
    show_discord_role_menu = False

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    group_id = get_custom_id_data(interaction.custom_id, 4)

    if bind_choice in ("equ", "gte", "lte", "rng"):
        show_roleset_menu = True

    print("select_criteria", interaction.custom_id)

    if show_roleset_menu:
        group = await get_group(group_id)

        roleset_menu = bloxlink.rest.build_message_action_row().add_text_menu(
            f"bind:sel_rank:{original_message_id}:{bind_choice}",
            placeholder="Bind this Group rank",
            min_values=1 if bind_choice != "rng" else 2,
            max_values=1 if bind_choice != "rng" else 2,
        )

        for roleset_value, roleset_name in group.rolesets.items():
            if roleset_name != "Guest" and len(roleset_menu.options) < 25:
                roleset_menu.add_option(roleset_name, roleset_name)

        message.embeds[0].description = (
            "Very good! Now, choose the roleset from your group " "that should receive the role."
        )

        await set_components(message, components=[roleset_menu.parent])
    else:
        # Skip to the role selection prompt.
        # Copy-pasted code, need a better solution for building these prompts as necessary.
        # Extrapolate to a method?
        role_menu = (
            bloxlink.rest.build_message_action_row()
            .add_text_menu(f"bind:sel_role:{original_message_id}::{bind_choice}", min_values=1)
            .set_placeholder("Attach this Discord role to the Group Roleset")
        )

        guild = await interaction.fetch_guild()
        for role_id, role in guild.roles.items():
            if role.name != "@everyone" and len(role_menu.options) < 25:
                role_menu.add_option(role.name, f"{role.name}{SPLIT_CHAR}{str(role_id)}")

        role_menu.set_max_values(len(role_menu.options))

        message.embeds[0].description = (
            "Finally, choose the role from your "
            "server that you want members to receive "
            "who qualify for the bind.\nNo existing role? "
            "No problem! Click the 'Create Role' button above!"
        )

        await set_components(message, components=[role_menu.parent])

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    message = interaction.message
    roleset_choices = interaction.values

    guild = await interaction.fetch_guild()

    print("select_roleset", interaction.custom_id)

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    bind_choice = get_custom_id_data(interaction.custom_id, 4)
    # print("here", original_message_id)

    # show discord role menu
    roleset_str = (
        f"{roleset_choices[0]}{f'{SPLIT_CHAR}{roleset_choices[1]}' if len(roleset_choices) > 1 else ''}"
    )
    role_menu = (
        bloxlink.rest.build_message_action_row()
        .add_text_menu(
            f"bind:sel_role:{original_message_id}:{roleset_str}:{bind_choice}",
            min_values=1,
        )
        .set_placeholder("Attach this Discord role to the Group Roleset")
    )

    for role_id, role in guild.roles.items():
        if role.name != "@everyone" and len(role_menu.options) < 25:
            role_menu.add_option(role.name, f"{role.name}{SPLIT_CHAR}{str(role_id)}")

    role_menu.set_max_values(len(role_menu.options))

    message.embeds[0].description = (
        "Finally, choose the role from your "
        "server that you want members to receive "
        "who qualify for the bind.\nNo existing role? "
        "No problem! Click the 'Create Role' button above!"
    )

    original_message_id = get_custom_id_data(interaction.id, 5)

    await set_components(message, components=[role_menu.parent])

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


async def bind_menu_select_role(interaction: hikari.ComponentInteraction):
    message = interaction.message

    print("inter vals", interaction.values)
    role_data = {}
    for item in interaction.values:
        item_data = item.split(SPLIT_CHAR)
        role_data[item_data[1]] = item_data[0]

    print("select_role", interaction.custom_id)

    custom_data = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=5)
    original_message_id = custom_data[0]
    roleset_data = custom_data[1]
    if SPLIT_CHAR in roleset_data:
        roleset_data = roleset_data.split(SPLIT_CHAR)
    bind_choice = custom_data[2]

    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    new_description = original_message.embeds[0].description.split("\n")

    if "Pending changes:" not in new_description:
        new_description.append("Pending changes:")

    prefix = GROUP_RANK_CRITERIA_TEXT.get(bind_choice, "[ERROR] No matching criteria.")
    content = ""
    if bind_choice in ("equ", "gte", "lte"):
        content = roleset_data
    elif bind_choice in ("gst", "all"):
        content = "<GROUP ID> (TBD)"
    elif bind_choice == "rng":
        min_rank = roleset_data[0]
        max_rank = roleset_data[1]

        content = f"{min_rank}** and **{max_rank}"

    suffix = ", ".join(f"<@&{val}>" for val in role_data.keys())
    new_description.append(
        f"_{prefix} **{content}** will receive " f"role{'s' if len(role_data.keys()) > 1  else ''} {suffix}_"
    )

    new_embed = hikari.Embed(title="New Group Bind [UNSAVED CHANGES]", description="\n".join(new_description))

    original_message.embeds[0] = new_embed

    await original_message.edit(embed=new_embed)
    await message.delete()

    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content(
            f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
            " and click the Save button to save the bind to your server!"
        )
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )

    # await interaction.edit_initial_response(
    #     f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
    #     " and click the Save button to save the bind to your server!")


async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    custom_id = interaction.custom_id

    channel_id = interaction.channel_id
    guild_id = interaction.guild_id

    member = interaction.member
    message = interaction.message

    guild = await interaction.fetch_guild()

    await interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    custom_id_data = custom_id.split(":")

    group_id = custom_id_data[2] if len(custom_id_data) >= 3 else None

    if not group_id:
        return

    group = await get_group(group_id)

    # print(group)

    # embed = message.embeds[0]

    # custom_id_data = custom_id.split(":")

    # role_data = (custom_id_data[2] if len(custom_id_data) >= 3 else "").split(",")

    # await message.edit(embed=embed)

    embed = hikari.Embed(
        title="Binding Role Interactive Wizard",
        description=(
            "This menu will let you connect a Group rank to a "
            "Discord role.\nPlease choose the criteria for this bind."
        ),
    )

    # roleset_menu = (
    #     bloxlink.rest.build_message_action_row().add_select_menu(f"bind_menu:select_menu:add_role:roleset_menu:{message.id}")
    #     .set_placeholder("Bind this Group rank")
    # )

    # for roleset_value, roleset_name in group.rolesets.items():
    #     if len(roleset_menu.options) < 25:
    #         roleset_menu = roleset_menu.add_option(roleset_name, str(roleset_value)).add_to_menu()

    # roleset_menu = roleset_menu.add_to_container()

    # role_menu = (
    #     bloxlink.rest.build_message_action_row().add_select_menu(f"bind_menu:select_menu:add_role:role_menu:{message.id}")
    #     .set_placeholder("..to this Discord role")
    # )

    # for role_id, role in guild.roles.items():
    #     if role.name != "@everyone" and len(role_menu.options) < 25:
    #         role_menu = role_menu.add_option(role.name, str(role_id)).add_to_menu()

    # role_menu = role_menu.add_to_container()

    criteria_menu = (
        bloxlink.rest.build_message_action_row()
        .add_text_menu(f"bind:sel_crit:{message.id}:{group_id}", min_values=1, max_values=1)
        .set_placeholder("Choose condition")
    )

    for key, val in GROUP_RANK_CRITERIA.items():
        criteria_menu.add_option(val, key)

    await interaction.execute(embed=embed, components=[criteria_menu.parent])


async def bind_menu_save_button(interaction: hikari.ComponentInteraction):
    message = interaction.message
    guild_id = interaction.guild_id

    embed = message.embeds[0]
    bindings = embed.description.split("\n")[2:]

    group_id = get_custom_id_data(interaction.custom_id, segment=3)
    for bind in bindings:
        # remove underscores
        bind = bind[1:-1]
        bind_type = ""

        for criteria_type, criteria_vals in GROUP_RANK_CRITERIA_TEXT.items():
            if criteria_vals in bind:
                bind_type = criteria_type
                break

        # Get all role IDs, need to rework if adding roles to remove.
        # Probably will split on the text "roles to remove" if it exists first.
        role_ids = re.findall(r"(\d{17,})", bind)
        # Get all matches in-between double asterisks
        named_ranks = re.findall(r"\*\*(.*?)\*\*", bind)

        group_data = await get_group(group_id)
        group_rolesets = group_data.rolesets.items()

        rank_ids = []
        for rank in named_ranks:
            for k, v in group_rolesets:
                if v == rank:
                    rank_ids.append(k)

        if bind_type == "equ":
            await create_bind(
                guild_id, bind_type="group", bind_id=int(group_id), roles=role_ids, roleset=rank_ids[0]
            )

        elif bind_type == "gte":
            # TODO: Consider changing so only "min" option is set.
            await create_bind(
                guild_id, bind_type="group", bind_id=int(group_id), roles=role_ids, roleset=-abs(rank_ids[0])
            )

        elif bind_type == "lte":
            await create_bind(
                guild_id, bind_type="group", bind_id=int(group_id), roles=role_ids, max=rank_ids[0]
            )

        elif bind_type == "rng":
            await create_bind(
                guild_id,
                bind_type="group",
                bind_id=int(group_id),
                roles=role_ids,
                min=rank_ids[0],
                max=rank_ids[1],
            )

        elif bind_type == "gst":
            await create_bind(guild_id, bind_type="group", bind_id=int(group_id), roles=role_ids, guest=True)

        elif bind_type == "all":
            await create_bind(
                guild_id, bind_type="group", bind_id=int(group_id), roles=role_ids, everyone=True
            )

        else:
            print("No matching bind type was found.")

    reset_embed = hikari.Embed(
        title="New Group Bind", description=await get_bind_desc(interaction.guild_id, int(group_id))
    )
    await message.edit(embed=reset_embed)

    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content("Saved your binds")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        "bind_menu:add_roles_button": bind_menu_add_role_button,
        "bind:sel_rank": bind_menu_select_roleset,
        "bind:sel_role": bind_menu_select_role,
        "bind:sel_crit": bind_menu_select_criteria,
        "bind_menu:save_button": bind_menu_save_button,
    },
)
class BindCommand:
    """bind Discord role(s) to Roblox entities"""

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="group_id",
                description="What is your group ID?",
                is_required=True,
            ),
            CommandOption(
                type=OptionType.STRING,
                name="bind_mode",
                description="How should we merge your group with Discord?",
                choices=[
                    hikari.CommandChoice(
                        name="Bind all current and future group roles", value="entire_group"
                    ),
                    hikari.CommandChoice(name="Choose specific group roles", value="specific_roles"),
                ],
                is_required=True,
            ),
        ]
    )
    async def group(self, ctx: CommandContext):
        """bind a group to your server"""

        group_id = ctx.options["group_id"]
        bind_mode = ctx.options["bind_mode"]

        group = await get_group(group_id)

        bind_count = await count_binds(ctx.guild_id, group.id)

        if bind_mode == "specific_roles":
            embed = hikari.Embed(
                title="New Group Bind",
                description="No binds exist for this group! Click the button below to create your first bind."
                if bind_count == 0
                else await get_bind_desc(ctx.guild_id, group.id),
            )

            button_menu = (
                bloxlink.rest.build_message_action_row()
                .add_interactive_button(
                    hikari.ButtonStyle.PRIMARY,
                    f"bind_menu:add_roles_button:{group_id}",
                    label="Bind new role",
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SUCCESS,
                    f"bind_menu:save_button:{group_id}",
                    label="Save changes",
                )
            )

            await ctx.response.send(embed=embed, components=button_menu)

            # We're done here. Button clicks invoke above functions
