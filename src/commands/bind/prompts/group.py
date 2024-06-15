import hikari
from bloxlink_lib import GuildBind, build_binds_desc, get_group
from bloxlink_lib.models.groups import RobloxGroup

from commands.bind.components import PromptComponents, parse_modal_rank_input
from resources.binds import create_bind
from resources.bloxlink import bloxlink
from resources.constants import GREEN_COLOR
from resources.exceptions import BindConflictError, RobloxAPIError, RobloxNotFound
from resources.response import Prompt, PromptCustomID, PromptPageData
from resources.ui.components import Button, TextSelectMenu


class GroupPromptCustomID(PromptCustomID):
    """Custom ID for the GroupPrompt."""

    group_id: int


class GroupPrompt(Prompt[GroupPromptCustomID]):
    """Prompt for binding a Roblox group to Discord role(s)."""

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
            custom_id_format=GroupPromptCustomID,
            start_with_fresh_data=False,
        )

    @Prompt.programmatic_page()
    async def current_binds(
        self,
        interaction: hikari.CommandInteraction | hikari.ComponentInteraction,
        fired_component_id: str | None,
    ):
        """Default page for the prompt. Shows users what binds they have made, and unsaved binds if any."""

        new_binds = [
            GuildBind(**b) for b in (await self.current_data(raise_exception=False)).get("pending_binds", [])
        ]

        match fired_component_id:
            case "new_bind":
                # Create an empty page first, we don't need the original page content to be generated again.
                # Code throws if a page is not yielded prior to trying to go to next.
                # This would in theory cause an issue if we were using self.previous()? untested.
                yield PromptPageData(title="", description="", fields=[], components=[])

                yield await self.next()

            case "publish":
                # Establish a baseline prompt. Same reasoning as the new_bind case.
                yield PromptPageData(title="", description="", fields=[], components=[])

                for bind in new_binds:
                    # Used to generically pass rank specifications to create_bind.
                    bind_criteria = bind.criteria.model_dump(exclude_unset=True)

                    for role in bind.pending_new_roles:
                        # Create any new roles.
                        # New roles are stored via the name given, use that name to make the role & store that instead.
                        new_role = await bloxlink.rest.create_role(
                            interaction.guild_id,
                            name=role,
                            reason="Creating new role from /bind command input.",
                        )
                        bind.roles.append(str(new_role.id))

                    await create_bind(
                        interaction.guild_id,
                        bind_type=bind.type,
                        bind_id=self.custom_id.group_id,
                        roles=bind.roles,
                        remove_roles=bind.remove_roles,
                        **bind_criteria,
                    )

                # TODO: Hack so we can change field names with edit_page.
                current_embed = interaction.message.embeds[0]
                current_embed.title = "New group binds saved."
                current_embed.description = "The binds on this menu were saved to your server. You can edit your binds at any time by running `/bind` again."
                current_embed.edit_field(1, "Created Binds")
                current_embed.color = GREEN_COLOR

                # FIXME: Overriding the prompt in place instead of editing.
                # Disabling components here in case self.finish() doesn't fire properly for some reason.
                await self.edit_page(
                    embed=current_embed,
                    components={
                        "new_bind": {"is_disabled": True},
                        "publish": {"is_disabled": True},
                        "delete_bind": {"is_disabled": True},
                    },
                )

                yield await self.response.send(
                    "Your new binds have been saved to your server.", ephemeral=True
                )

                await self.finish()

            case "delete_bind":
                yield PromptPageData(title="", description="", fields=[], components=[])

                yield await self.go_to(self.remove_unsaved_bind)

            case _:
                # Not spawned from a button press on the generated prompt. Builds a new prompt.
                current_bind_desc = await build_binds_desc(
                    interaction.guild_id,
                    bind_type="group",
                    bind_id=self.custom_id.group_id,
                )

                await self.clear_data(
                    "discord_role", "group_rank", "unbind_menu", "group_name"
                )  # clear the data so we can re-use the menu

                prompt_fields = [
                    PromptPageData.Field(
                        name="Current binds",
                        value=current_bind_desc or "No binds exist. Create one below!",
                        inline=True,
                    ),
                ]

                if new_binds:
                    try:
                        for bind in new_binds:
                            await bind.entity.sync()
                    except RobloxAPIError:
                        pass

                    unsaved_binds = "\n".join([str(bind) for bind in new_binds])

                    prompt_fields.append(
                        PromptPageData.Field(
                            name="Unsaved Binds",
                            value=unsaved_binds,
                            inline=True,
                        )
                    )

                group_name = await self.current_data(key_name="group_name", raise_exception=False)
                if not group_name:
                    try:
                        roblox_group = await get_group(self.custom_id.group_id)
                    except RobloxNotFound:
                        # Syncing failed for some reason, catch so the prompt doesn't die & cause issues.
                        pass

                    group_name = str(roblox_group).replace("**", "")

                    await self.save_stateful_data(group_name=group_name)

                yield PromptPageData(
                    title=f"{'[UNSAVED CHANGES] ' if new_binds else ''}New Group Bind",
                    description="Here are the current binds for your server for that Group. Use the buttons below to make a new bind!",
                    fields=prompt_fields,
                    components=[
                        Button(
                            label="Create a new bind",
                            component_id="new_bind",
                            is_disabled=len(new_binds) >= 5,
                        ),
                        Button(
                            label="Publish",
                            component_id="publish",
                            is_disabled=len(new_binds) == 0,
                            style=Button.ButtonStyle.SUCCESS,
                        ),
                        Button(
                            label="Remove an unsaved bind",
                            component_id="delete_bind",
                            style=Button.ButtonStyle.DANGER,
                            is_disabled=len(new_binds) == 0,
                        ),
                    ],
                    footer_text=f"Group: {group_name}",
                )

    @Prompt.page(
        PromptPageData(
            title="Make a Group Bind",
            description="This menu will guide you through the process of binding a group to your server.\nPlease choose the criteria for this bind.",
            components=[
                TextSelectMenu(
                    placeholder="Select a condition",
                    min_values=0,
                    max_values=1,
                    component_id="criteria_select",
                    options=[
                        TextSelectMenu.Option(
                            label="Rank must match exactly...",
                            value="exact_match",
                        ),
                        TextSelectMenu.Option(
                            label="Rank must be greater than or equal to...",
                            value="gte",
                        ),
                        TextSelectMenu.Option(
                            label="Rank must be less than or equal to...",
                            value="lte",
                        ),
                        TextSelectMenu.Option(
                            label="Rank must be between two rolesets...",
                            value="range",
                        ),
                        TextSelectMenu.Option(
                            label="User MUST be a member of this group",
                            value="in_group",
                        ),
                        TextSelectMenu.Option(
                            label="User must NOT be a member of this group",
                            value="not_in_group",
                        ),
                    ],
                ),
            ],
        )
    )
    async def create_bind_page(
        self, interaction: hikari.ComponentInteraction, _fired_component_id: str | None
    ):
        """Prompt telling users to choose which bind type is being made."""
        match interaction.values[0]:
            case "exact_match" | "gte" | "lte":
                yield await self.go_to(self.bind_rank_and_role)
            case "range":
                yield await self.go_to(self.bind_range)
            case "in_group" | "not_in_group":
                yield await self.go_to(self.bind_role)

    @Prompt.programmatic_page()
    async def bind_rank_and_role(
        self, interaction: hikari.ComponentInteraction, fired_component_id: str | None
    ):
        """Handle ==, <=, and >= bind types from a single location."""

        if fired_component_id and fired_component_id not in ("modal_roleset", "new_role"):
            yield await self.response.defer()

        current_data = await self.current_data()
        user_choice = current_data["criteria_select"]["values"][0]

        match user_choice:
            case "gte":
                title = "Bind Group Rank And Above"
                description = (
                    "Please choose the **lowest rank** for this bind. "
                    "Everyone with this rank **and above** will be given this role."
                )
                modal_title = "Select a minimum group rank."

            case "lte":
                title = "Bind Group Rank And Below"
                description = (
                    "Please choose the **highest** group rank to give for this bind along with a corresponding Discord role to give. "
                    "Everyone with this group rank **and below** will receive that role. "
                    "No existing Discord role? No problem, just click `Create new role`."
                )
                modal_title = "Select a maximum group rank."

            case _:
                title = "Bind Group Rank"
                description = (
                    "Please select one group rank and a corresponding Discord role to give. "
                    "No existing Discord role? No problem, just click `Create new role`."
                )
                modal_title = "Select a group rank."

        group_id = self.custom_id.group_id
        # TODO: Consider try/except all get_group calls.
        roblox_group = await get_group(group_id)

        components = [
            PromptComponents.discord_role_selector(min_values=1),
            PromptComponents.create_role_button(),
        ]

        # Only allow modal input if there's over 25 ranks.
        if len(roblox_group.rolesets) > 25:
            components.append(Button(label="Select a group rank", component_id="modal_roleset"))
        else:
            components.insert(
                1, PromptComponents.group_rank_selector(roblox_group=roblox_group, max_values=1)
            )

        yield PromptPageData(
            title=title,
            description=description,
            components=components,
            footer_text=f"Group: {current_data.get('group_name', group_id)}",
        )

        discord_role = current_data["discord_role"]["values"] if current_data.get("discord_role") else None
        group_rank = (
            current_data["group_rank"]["values"][0]
            if current_data.get("group_rank") and current_data["group_rank"]["values"]
            else None
        )

        match fired_component_id:
            case "new_role":
                local_modal = await PromptComponents.new_role_modal(
                    interaction=interaction,
                    prompt=self,
                    fired_component_id=fired_component_id,
                )

                # Disable the discord role select menu.
                await self.edit_component(
                    discord_role={
                        "is_disabled": True,
                    },
                    new_role={"label": "Use an existing role", "component_id": "new_role-er"},
                )

                yield await self.response.send_modal(local_modal)

                if not await local_modal.submitted():
                    return

                modal_data = await local_modal.get_data()
                role_name = modal_data["role_name"]

                # Update all instances of discord_role
                await self.save_stateful_data(discord_role={"values": [role_name]})
                current_data["discord_role"] = {"values": [role_name]}
                discord_role = [role_name]

                if not group_rank:
                    await self.response.send(
                        f"The Discord role name `{role_name}` has been stored for this bind.", ephemeral=True
                    )
                else:
                    await self.ack()

            case "new_role-er":
                # Enable the discord role select menu
                await self.edit_component(
                    discord_role={
                        "is_disabled": False,
                    },
                    new_role={"label": "Create new role", "component_id": "new_role"},
                )

                # Clear discord_role data.
                if current_data.get("discord_role"):
                    current_data.pop("discord_role")
                discord_role = None
                await self.clear_data("discord_role")

                return

            case "modal_roleset":
                local_modal = await PromptComponents.roleset_selection_modal(
                    title=modal_title,
                    interaction=interaction,
                    prompt=self,
                    fired_component_id=fired_component_id,
                )

                yield await self.response.send_modal(local_modal)

                if not await local_modal.submitted():
                    return

                modal_data = await local_modal.get_data()
                rank_id = parse_modal_rank_input(modal_data["rank_input"], roblox_group)

                if rank_id == -1:
                    yield await self.response.send_first(
                        "That ID does not match a group rank in your roblox group! Please try again.",
                        ephemeral=True,
                    )
                    return

                # Update all instances of group_rank
                await self.save_stateful_data(group_rank={"values": [rank_id]})
                current_data["group_rank"] = {"values": [rank_id]}
                group_rank = rank_id

                if not discord_role:
                    await self.response.send(
                        f"The rank ID `{rank_id}` has been stored for this bind.", ephemeral=True
                    )
                else:
                    await self.ack()

        if discord_role and group_rank:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]

            group_criteria = {}
            if user_choice == "gte":
                group_criteria = {
                    "roleset": int(group_rank) * -1
                }  # negative rank means "current rank and above"
            elif user_choice == "lte":
                group_criteria = {"min": 1, "max": int(group_rank)}
            else:
                group_criteria = {"roleset": int(group_rank)}

            if not discord_role[0].isdigit():
                existing_pending_binds.append(
                    GuildBind(
                        roles=[],
                        remove_roles=[],
                        pending_new_roles=[discord_role[0]],
                        criteria={
                            "type": "group",
                            "id": group_id,
                            "group": group_criteria,
                        },
                    )
                )

            else:
                existing_pending_binds.append(
                    GuildBind(
                        roles=discord_role,
                        remove_roles=[],
                        criteria={
                            "type": "group",
                            "id": group_id,
                            "group": group_criteria,
                        },
                    )
                )

            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )

            # Start heading to main prompt before telling the user the bind was added.
            yield await self.go_to(self.current_binds)

            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )

        if fired_component_id in ("group_rank", "discord_role"):
            await self.ack()

    @Prompt.programmatic_page()
    async def bind_range(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """Prompts a user to select two group ranks and a Discord role to give."""

        if fired_component_id and fired_component_id not in ("modal_roleset", "new_role"):
            yield await self.response.defer()

        group_id = self.custom_id.group_id
        roblox_group = await get_group(group_id)

        components = [
            PromptComponents.discord_role_selector(min_values=1),
            PromptComponents.create_role_button(),
        ]

        # Only allow modal input if there's over 25 ranks.
        if len(roblox_group.rolesets) > 25:
            components.append(Button(label="Select group ranks", component_id="modal_roleset"))
        else:
            components.insert(
                1, PromptComponents.group_rank_selector(roblox_group=roblox_group, min_values=2)
            )

        current_data = await self.current_data()

        yield PromptPageData(
            title="Bind Group Range",
            description="Please select two group ranks and a corresponding Discord role to give. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=components,
            footer_text=f"Group: {current_data.get('group_name', group_id)}",
        )

        discord_roles = current_data["discord_role"]["values"] if current_data.get("discord_role") else None
        group_ranks = (
            [int(x) for x in current_data["group_rank"]["values"]] if current_data.get("group_rank") else None
        )

        match fired_component_id:
            case "new_role":
                local_modal = await PromptComponents.new_role_modal(
                    interaction=interaction,
                    prompt=self,
                    fired_component_id=fired_component_id,
                )

                # Disable the discord role select menu.
                await self.edit_component(
                    discord_role={
                        "is_disabled": True,
                    },
                    new_role={"label": "Use an existing role", "component_id": "new_role-er"},
                )

                yield await self.response.send_modal(local_modal)

                if not await local_modal.submitted():
                    return

                modal_data = await local_modal.get_data()
                role_name = modal_data["role_name"]

                # Update all instances of discord_role(s)
                await self.save_stateful_data(discord_role={"values": [role_name]})
                current_data["discord_role"] = {"values": [role_name]}
                discord_roles = [role_name]

                if not group_ranks:
                    await self.response.send(
                        f"The Discord role name `{role_name}` has been stored for this bind.", ephemeral=True
                    )
                else:
                    await self.ack()

            case "new_role-er":
                # Enable the discord role select menu
                await self.edit_component(
                    discord_role={
                        "is_disabled": False,
                    },
                    new_role={"label": "Create new role", "component_id": "new_role"},
                )

                # Clear discord_role(s) data.
                if current_data.get("discord_role"):
                    current_data.pop("discord_role")
                discord_roles = None
                await self.clear_data("discord_role")

                return

            case "modal_roleset":
                local_modal = await PromptComponents.multi_roleset_selection_modal(
                    title="Input group rank range",
                    interaction=interaction,
                    prompt=self,
                    fired_component_id=fired_component_id,
                )

                yield await self.response.send_modal(local_modal)

                if not await local_modal.submitted():
                    return

                modal_data = await local_modal.get_data()
                min_rank_id = parse_modal_rank_input(modal_data["min_rank_input"], roblox_group)
                max_rank_id = parse_modal_rank_input(modal_data["max_rank_input"], roblox_group)

                if min_rank_id == -1 or max_rank_id == -1:
                    yield await self.response.send_first(
                        "One of the given IDs does not match a group rank in your roblox group! Please try again.",
                        ephemeral=True,
                    )
                    return

                if min_rank_id == max_rank_id:
                    yield await self.response.send_first(
                        "Those two group ranks are the same! Please make sure you are inputting two different group ranks.",
                        ephemeral=True,
                    )
                    return

                await self.save_stateful_data(group_rank={"values": [min_rank_id, max_rank_id]})
                # Force the saved rank_id into the memory instance of current_data.
                current_data["group_rank"] = {"values": [min_rank_id, max_rank_id]}
                group_ranks = [int(min_rank_id), int(max_rank_id)]

                if not discord_roles:
                    await self.response.send(
                        f"The rank IDs `{min_rank_id}` and `{max_rank_id}` have been stored for this bind.",
                        ephemeral=True,
                    )
                else:
                    await self.ack()

        if discord_roles and group_ranks:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]

            bind_criteria = {
                "type": "group",
                "id": group_id,
                "group": {"min": min(group_ranks), "max": max(group_ranks)},
            }

            if not discord_roles[0].isdigit():
                existing_pending_binds.append(
                    GuildBind(
                        roles=[],
                        remove_roles=[],
                        pending_new_roles=[discord_roles[0]],
                        criteria=bind_criteria,
                    )
                )

            else:
                existing_pending_binds.append(
                    GuildBind(
                        roles=discord_roles,
                        remove_roles=[],
                        criteria=bind_criteria,
                    )
                )

            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )

            # Start heading to main prompt before telling the user the bind was added.
            yield await self.go_to(self.current_binds)

            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )

        if fired_component_id in ("group_rank", "discord_role"):
            await self.ack()

    @Prompt.programmatic_page()
    async def bind_role(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """Prompts for a user to select which roles will be given for bind.
        Used for guest bindings & all group member bindings.
        """

        if fired_component_id != "new_role":
            yield await self.response.defer()

        current_data = await self.current_data()
        user_choice = current_data["criteria_select"]["values"][0]
        bind_flag = "guest" if user_choice == "not_in_group" else "everyone"

        desc_stem = "users not in the group" if bind_flag == "guest" else "group members"

        group_id = self.custom_id.group_id

        yield PromptPageData(
            title="Bind Discord Role",
            description=f"Please select a Discord role to give to {desc_stem}. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptComponents.discord_role_selector(min_values=1),
                PromptComponents.create_role_button(),
            ],
            footer_text=f"Group: {current_data.get('group_name', group_id)}",
        )

        match fired_component_id:
            case "new_role":
                local_modal = await PromptComponents.new_role_modal(
                    interaction=interaction,
                    prompt=self,
                    fired_component_id=fired_component_id,
                )

                yield await self.response.send_modal(local_modal)

                if not await local_modal.submitted():
                    return

                modal_data = await local_modal.get_data()
                role_name = modal_data["role_name"]

                current_data["discord_role"] = {"values": [role_name]}

                await self.ack()

        group_id = self.custom_id.group_id
        discord_role = current_data["discord_role"]["values"] if current_data.get("discord_role") else None

        if discord_role:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]

            # Creating a new role, only accept 1 input.
            if not discord_role[0].isdigit():
                existing_pending_binds.append(
                    GuildBind(
                        roles=[],
                        remove_roles=[],
                        pending_new_roles=[discord_role[0]],
                        criteria={
                            "type": "group",
                            "id": group_id,
                            "group": {
                                bind_flag: True,
                            },
                        },
                    )
                )

            else:
                existing_pending_binds.append(
                    GuildBind(
                        roles=discord_role,
                        remove_roles=[],
                        criteria={
                            "type": "group",
                            "id": group_id,
                            "group": {
                                bind_flag: True,
                            },
                        },
                    )
                )

            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )

            yield await self.go_to(self.current_binds)

            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )

        if fired_component_id == "discord_role":
            await self.ack()

    @Prompt.programmatic_page()
    async def remove_unsaved_bind(
        self, _interaction: hikari.ComponentInteraction, fired_component_id: str | None
    ):
        """Prompt someone to remove an unsaved binding from the list."""

        current_data = await self.current_data()
        new_binds = [GuildBind(**b) for b in current_data.get("pending_binds", [])]

        components = [Button(label="Return", component_id="return", style=Button.ButtonStyle.SECONDARY)]
        if len(new_binds) > 0:
            components.insert(0, (await PromptComponents.unsaved_bind_selector(pending_binds=new_binds)))

        unsaved_binds_str = "\n".join([f"{index}. {str(bind)[2:]}" for index, bind in enumerate(new_binds)])
        yield PromptPageData(
            title="Remove an unsaved bind.",
            description=f"Use the selection menu below to remove some of your unsaved binds.\n{unsaved_binds_str}",
            components=components,
        )

        match fired_component_id:
            case "return":
                yield await self.go_to(self.current_binds)
                return

            case "unbind_menu":
                user_choice = current_data["unbind_menu"]["values"] if current_data.get("unbind_menu") else []

                # Iterate from back to the start
                for choice in sorted([int(x) for x in user_choice], reverse=True):
                    new_binds.pop(choice)

                await self.save_stateful_data(
                    pending_binds=[b.model_dump(by_alias=True, exclude_unset=True) for b in new_binds]
                )

                response_text = (
                    "The binds you have selected have been removed."
                    if len(user_choice) != 0
                    else "No changes have been made."
                )
                yield await self.response.send_first(response_text, ephemeral=True)

                # Cause the selection component to update
                await self.edit_component()


class GroupRolesConfirmationPrompt(Prompt[GroupPromptCustomID]):
    """Ask if the bot can create roles that match their rolesets."""

    override_prompt_name = "GRCP"

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
            custom_id_format=GroupPromptCustomID,
        )

    @Prompt.programmatic_page()
    async def role_create_confirmation_pgrm(
        self,
        interaction: hikari.CommandInteraction | hikari.ComponentInteraction,
        fired_component_id: str,
    ):
        yield await self.response.defer()

        group = RobloxGroup(id=self.custom_id.group_id)
        try:
            await group.sync()
        except (RobloxAPIError, RobloxNotFound):
            pass

        yield PromptPageData(
            title="Role Creation Confirmation",
            description=f"Would you like Bloxlink to create Discord roles for each of your [group]({group.url})'s roles?"
            "\n\n**Please note, even if you choose 'no', the bind will still be created.**",
            components=[
                Button(
                    label="Yes",
                    component_id="yes",
                    style=Button.ButtonStyle.SUCCESS,
                ),
                Button(
                    label="No",
                    component_id="no",
                    style=Button.ButtonStyle.DANGER,
                ),
                Button(
                    label="Cancel",
                    component_id="cancel",
                    style=Button.ButtonStyle.SECONDARY,
                ),
            ],
            footer_text=f"Group: {str(group).replace('**', '')}",
        )

        guild_id = interaction.guild_id

        match fired_component_id:
            case "yes":
                guild_roles = await bloxlink.fetch_roles(guild_id, key_as_role_name=True)

                for roleset in reversed(group.rolesets.values()):
                    if roleset.name not in guild_roles:
                        await bloxlink.rest.create_role(
                            guild_id,
                            name=roleset.name,
                        )

            case "cancel":
                await self.response.send(
                    content="Cancelled. No changes were made.",
                    edit_original=True,
                    embeds=[],
                )
                return

        # Safeguard to not create a bind when we're not supposed to.
        if not fired_component_id:
            return

        try:
            await create_bind(
                guild_id, bind_type="group", bind_id=self.custom_id.group_id, dynamic_roles=True
            )
        except BindConflictError:
            await self.response.send(
                content=f"You already have a group binding for [{group.name}](<{group.url}>). No changes were made.",
                edit_original=True,
                embeds=[],
            )
            return

        await self.response.send(
            content=(
                f"Your group binding for [{group.name}](<{group.url}>) has been saved. "
                "When people join your server, they will receive a Discord role that corresponds to their group rank. "
            ),
            edit_original=True,
            embeds=[],
        )
