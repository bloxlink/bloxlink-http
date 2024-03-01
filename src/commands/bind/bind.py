import itertools
from abc import ABC
from typing import Literal

import hikari
from bloxlink_lib import GuildBind, build_binds_desc, get_badge, get_catalog_asset, get_gamepass, get_group
from bloxlink_lib.models.groups import RobloxGroup
from hikari.commands import CommandOption, OptionType

import resources.ui.modals as modal
from resources.binds import create_bind
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import BindConflictError, RobloxNotFound
from resources.response import Prompt, PromptCustomID, PromptPageData
from resources.ui.components import Button, RoleSelectMenu, TextInput, TextSelectMenu


class GenericBindPromptCustomID(PromptCustomID, ABC):
    """Custom ID for the GenericBindPrompt."""

    entity_id: int
    entity_type: str


class GenericBindPrompt(Prompt[GenericBindPromptCustomID]):
    """Generic prompt for binding Roblox entities to Discord roles."""

    override_prompt_name = "GBP"

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
            custom_id_format=GenericBindPromptCustomID,
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

        bind_type = self.custom_id.entity_type

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
                    bind_criteria = bind.criteria.model_dump()

                    # TODO: If no role exists in the bind, make one with the same name as the rank(??) and save.
                    # Maybe this should be done as part of the prior page, saves a request to roblox.

                    await create_bind(
                        interaction.guild_id,
                        bind_type=bind.type,
                        bind_id=self.custom_id.entity_id,
                        roles=bind.roles,
                        remove_roles=bind.remove_roles,
                        **bind_criteria,
                    )

                # FIXME: Overriding the prompt in place instead of editing.
                yield await self.edit_page(
                    title=f"New {bind_type} binds saved.",
                    description="The binds on this menu were saved to your server. "
                    "You can edit your binds at any time by running `/bind` again.",
                )
                yield await self.response.send(
                    "Your new binds have been saved to your server.", ephemeral=True
                )

                await self.finish()

            case _:
                # Not spawned from a button press on the generated prompt. Builds a new prompt.
                current_bind_desc = await build_binds_desc(
                    interaction.guild_id,
                    bind_id=self.custom_id.entity_id,
                    bind_type=bind_type,
                )

                await self.clear_data("discord_role")  # clear the data so we can re-use the menu

                prompt_fields = [
                    PromptPageData.Field(
                        name="Current binds",
                        value=current_bind_desc or "No binds exist. Create one below!",
                        inline=True,
                    ),
                ]

                if new_binds:
                    unsaved_binds = "\n".join([str(bind) for bind in new_binds])
                    # print(unsaved_binds)

                    prompt_fields.append(
                        PromptPageData.Field(
                            name="Unsaved Binds",
                            value=unsaved_binds,
                            inline=True,
                        )
                    )

                yield PromptPageData(
                    title=f"{'[UNSAVED CHANGES] ' if new_binds else ''}New {bind_type.capitalize()} Bind",
                    description="Here are the current binds for your server. Click the button below to make a new bind.",
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
                    ],
                )

    @Prompt.programmatic_page()
    async def bind_role(self, _interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """Prompts for a user to select which roles will be given for bind."""
        yield await self.response.defer()

        current_data = await self.current_data()

        bind_id = self.custom_id.entity_id
        bind_type = self.custom_id.entity_type

        yield PromptPageData(
            title="Bind Discord Role",
            description=f"Please select a Discord role to give to users who own this {bind_type}. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptComponents.discord_role_selector(min_values=1),
                # Button(
                #     label="Create new role",
                #     component_id="new_role",
                #     is_disabled=False,
                # ),
            ],
        )

        if fired_component_id == "new_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": True,
                },
                new_role={"label": "Use existing role", "component_id": "new_role-existing_role"},
            )
        elif fired_component_id == "new_role-existing_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": False,
                },
                new_role={"label": "Create new role", "component_id": "new_role"},
            )

        discord_role = current_data["discord_role"]["values"][0] if current_data.get("discord_role") else None

        # TODO: Handle "create new role" logic. Can't exit the prompt with that set currently.
        if discord_role:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]
            existing_pending_binds.append(
                GuildBind(
                    roles=[discord_role],
                    remove_roles=[],
                    criteria={
                        "type": bind_type,
                        "id": bind_id,
                    },
                )
            )

            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )
            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )
            yield await self.go_to(self.current_binds)

        if fired_component_id == "discord_role":
            await self.ack()


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

                    # TODO: If no role exists in the bind, make one with the same name as the rank(??) and save.
                    # Maybe this should be done as part of the prior page, saves a request to roblox.

                    await create_bind(
                        interaction.guild_id,
                        bind_type=bind.type,
                        bind_id=self.custom_id.group_id,
                        roles=bind.roles,
                        remove_roles=bind.remove_roles,
                        **bind_criteria,
                    )

                # FIXME: Overriding the prompt in place instead of editing.
                yield await self.edit_page(
                    title="New group binds saved.",
                    description="The binds on this menu were saved to your server. "
                    "You can edit your binds at any time by running `/bind` again.",
                )
                yield await self.response.send(
                    "Your new binds have been saved to your server.", ephemeral=True
                )

                await self.finish()

            case _:
                # Not spawned from a button press on the generated prompt. Builds a new prompt.
                current_bind_desc = await build_binds_desc(
                    interaction.guild_id,
                    bind_type="group",
                    bind_id=self.custom_id.group_id,
                )

                await self.clear_data(
                    "discord_role", "group_rank"
                )  # clear the data so we can re-use the menu

                prompt_fields = [
                    PromptPageData.Field(
                        name="Current binds",
                        value=current_bind_desc or "No binds exist. Create one below!",
                        inline=True,
                    ),
                ]

                if new_binds:
                    # print(new_binds)
                    # print(typed_new_binds)
                    unsaved_binds = "\n".join([str(bind) for bind in new_binds])
                    # print(unsaved_binds)

                    prompt_fields.append(
                        PromptPageData.Field(
                            name="Unsaved Binds",
                            value=unsaved_binds,
                            inline=True,
                        )
                    )

                yield PromptPageData(
                    title=f"{'[UNSAVED CHANGES] ' if new_binds else ''}New Group Bind",
                    description="Here are the current binds for your server. Click the button below to make a new bind.",
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
                    ],
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
            case "exact_match":
                yield await self.go_to(self.bind_rank_and_role)
            case "gte":
                yield await self.go_to(self.bind_rank_and_above)
            case "range" | "lte":
                yield await self.go_to(self.bind_range)
            case "in_group" | "not_in_group":
                yield await self.go_to(self.bind_role)

    @Prompt.programmatic_page()
    async def bind_rank_and_role(
        self, interaction: hikari.ComponentInteraction, fired_component_id: str | None
    ):
        """Prompts a user to choose a rank and a role to give.
        Used for exact-rank bindings, as well as >= and <= bindings."""

        if fired_component_id != "modal_roleset":
            yield await self.response.defer()

        group_id = self.custom_id.group_id
        roblox_group = await get_group(group_id)

        yield PromptPageData(
            title="Bind Group Rank",
            description="Please select one group rank and a corresponding Discord role to give. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptComponents.group_rank_selector(roblox_group=roblox_group, max_values=1),
                PromptComponents.discord_role_selector(min_values=1, max_values=1),
                Button(label="Custom Input", component_id="modal_roleset"),
            ],
        )

        # if fired_component_id == "new_role":
        #     await self.edit_component(
        #         discord_role={
        #             "is_disabled": True,
        #         },
        #         new_role={"label": "Use existing role", "component_id": "new_role-existing_role"},
        #     )
        # elif fired_component_id == "new_role-existing_role":
        #     await self.edit_component(
        #         discord_role={
        #             "is_disabled": False,
        #         },
        #         new_role={"label": "Create new role", "component_id": "new_role"},
        #     )

        if fired_component_id == "modal_roleset":
            modal = PromptComponents.roleset_selection_modal(
                title="Bind a Group Rank",
                interaction=interaction,
                prompt=self,
                fired_component_id=fired_component_id,
            )

            yield await self.response.send_modal(modal)

            if not await modal.submitted():
                return

            print(await modal.get_data())

        current_data = await self.current_data()

        discord_role = current_data["discord_role"]["values"][0] if current_data.get("discord_role") else None
        group_rank = (
            current_data["group_rank"]["values"][0]
            if current_data.get("group_rank") and current_data["group_rank"]["values"]
            else None
        )

        if discord_role and group_rank:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]
            existing_pending_binds.append(
                GuildBind(
                    roles=[discord_role],
                    remove_roles=[],
                    criteria={
                        "type": "group",
                        "id": group_id,
                        "group": {
                            "roleset": int(group_rank),
                        },
                    },
                )
            )

            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )
            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )
            yield await self.go_to(self.current_binds)

        if fired_component_id in ("group_rank", "discord_role"):
            await self.ack()

    @Prompt.programmatic_page()
    async def bind_rank_and_above(
        self, _interaction: hikari.ComponentInteraction, fired_component_id: str | None
    ):
        """
        Prompts a user to choose a rank and a role to give.
        Used for <= bindings.
        """

        yield await self.response.defer()

        group_id = self.custom_id.group_id
        roblox_group = await get_group(group_id)

        yield PromptPageData(
            title="Bind Group Rank And Above",
            description="Please choose the **lowest rank** for this bind. Everyone with this rank **and above** will be given this role.",
            components=[
                PromptComponents.group_rank_selector(roblox_group=roblox_group, max_values=1),
                PromptComponents.discord_role_selector(min_values=1, max_values=1)
                # Button(
                #     label="Create new role",
                #     component_id="new_role",
                #     is_disabled=False,
                # ),
            ],
        )

        if fired_component_id == "new_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": True,
                },
                new_role={"label": "Use existing role", "component_id": "new_role-existing_role"},
            )
        elif fired_component_id == "new_role-existing_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": False,
                },
                new_role={"label": "Create new role", "component_id": "new_role"},
            )

        current_data = await self.current_data()

        discord_role = current_data["discord_role"]["values"][0] if current_data.get("discord_role") else None
        group_rank = current_data["group_rank"]["values"][0] if current_data.get("group_rank") else None

        if discord_role and group_rank:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]
            existing_pending_binds.append(
                GuildBind(
                    roles=[discord_role],
                    remove_roles=[],
                    criteria={
                        "type": "group",
                        "id": group_id,
                        "group": {
                            "roleset": int(group_rank) * -1,  # negative rank means "current rank and above"
                        },
                    },
                )
            )

            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )
            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )
            yield await self.go_to(self.current_binds)

        if fired_component_id in ("group_rank", "discord_role"):
            await self.ack()

    @Prompt.programmatic_page()
    async def bind_range(self, _interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """Prompts a user to select two group ranks and a Discord role to give."""
        yield await self.response.defer()

        group_id = self.custom_id.group_id
        roblox_group = await get_group(group_id)

        yield PromptPageData(
            title="Bind Group Rank",
            description="Please select two group ranks and a corresponding Discord role to give. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptComponents.group_rank_selector(roblox_group=roblox_group, max_values=2),
                PromptComponents.discord_role_selector(min_values=1, max_values=1),
                # Button(
                #     label="Create new role",
                #     component_id="new_role",
                #     is_disabled=False,
                # ),
            ],
        )

        if fired_component_id == "new_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": True,
                },
                new_role={"label": "Use existing role", "component_id": "new_role-existing_role"},
            )
        elif fired_component_id == "new_role-existing_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": False,
                },
                new_role={"label": "Create new role", "component_id": "new_role"},
            )

        current_data = await self.current_data()

        discord_roles = current_data["discord_role"]["values"] if current_data.get("discord_role") else None
        group_ranks = (
            [int(x) for x in current_data["group_rank"]["values"]] if current_data.get("group_rank") else None
        )

        if discord_roles and group_ranks:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]
            existing_pending_binds.append(
                GuildBind(
                    roles=discord_roles,
                    remove_roles=[],
                    criteria={
                        "type": "group",
                        "id": group_id,
                        "group": {"min": min(group_ranks), "max": max(group_ranks)},
                    },
                )
            )
            await self.save_stateful_data(
                pending_binds=[
                    b.model_dump(by_alias=True, exclude_unset=True) for b in existing_pending_binds
                ]
            )
            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )
            yield await self.go_to(self.current_binds)

        if fired_component_id in ("group_rank", "discord_role"):
            await self.ack()

    @Prompt.programmatic_page()
    async def bind_role(self, _interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """Prompts for a user to select which roles will be given for bind.
        Used for guest bindings & all group member bindings.
        """
        yield await self.response.defer()

        current_data = await self.current_data()
        user_choice = current_data["criteria_select"]["values"][0]
        bind_flag = "guest" if user_choice == "not_in_group" else "everyone"

        desc_stem = "users not in the group" if bind_flag == "guest" else "group members"

        yield PromptPageData(
            title="Bind Discord Role",
            description=f"Please select a Discord role to give to {desc_stem}. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptComponents.discord_role_selector(min_values=0, max_values=1),
                # Button(
                #     label="Create new role",
                #     component_id="new_role",
                #     is_disabled=False,
                # ),
            ],
        )

        if fired_component_id == "new_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": True,
                },
                new_role={"label": "Use existing role", "component_id": "new_role-existing_role"},
            )
        elif fired_component_id == "new_role-existing_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": False,
                },
                new_role={"label": "Create new role", "component_id": "new_role"},
            )

        group_id = self.custom_id.group_id
        discord_role = current_data["discord_role"]["values"][0] if current_data.get("discord_role") else None

        # TODO: Handle "create new role" logic. Can't exit the prompt with that set currently.
        if discord_role:
            existing_pending_binds: list[GuildBind] = [
                GuildBind(**b) for b in current_data.get("pending_binds", [])
            ]
            existing_pending_binds.append(
                GuildBind(
                    roles=[discord_role],
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
            await self.response.send(
                "Bind added to your in-progress workflow. Click `Publish` to save your changes.",
                ephemeral=True,
            )
            yield await self.go_to(self.current_binds)

        if fired_component_id == "discord_role":
            await self.ack()


class GroupRolesConfirmationPrompt(Prompt[GroupPromptCustomID]):
    """Ask if the bot can create roles that match their rolesets."""

    override_prompt_name = "GRCP"

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
            custom_id_format=GroupPromptCustomID,
        )

    @Prompt.page(
        PromptPageData(
            title="Role Creation Confirmation",
            description=(
                "Would you like Bloxlink to create Discord roles for each of your group's roles?\n\n**Please note, even if you "
                "choose 'no', the bind will still be created.**"
            ),
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
        )
    )
    async def role_create_confirmation(
        self,
        interaction: hikari.CommandInteraction | hikari.ComponentInteraction,
        fired_component_id: str,
    ):
        """Default page for the prompt. Ask if the bot can create groupset roles."""

        guild_id = interaction.guild_id

        yield await self.response.defer()

        if fired_component_id:
            group = await get_group(self.custom_id.group_id)

            if fired_component_id == "yes":
                guild_roles = await bloxlink.fetch_roles(guild_id, key_as_role_name=True)

                for roleset in reversed(group.rolesets.values()):
                    if roleset.name not in guild_roles:
                        await bloxlink.rest.create_role(
                            guild_id,
                            name=roleset.name,
                        )

            if fired_component_id != "cancel":
                try:
                    await create_bind(
                        guild_id, bind_type="group", bind_id=self.custom_id.group_id, dynamic_roles=True
                    )
                except BindConflictError:
                    await self.response.send(
                        f"You already have a group binding for group [{group.name}](<{group.url}>). No changes were made.",
                        edit_original=True,
                    )
                    return

                await self.response.send(
                    f"Your group binding for group [{group.name}](<{group.url}>) has been saved. "
                    "When people join your server, they will receive a Discord role that corresponds to their group rank. ",
                    edit_original=True,
                )
            else:
                await self.response.send("No changes were made.", edit_original=True)


@bloxlink.command(
    category="Administration",
    defer=True,
    defer_with_ephemeral=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    dm_enabled=False,
    prompts=[GroupPrompt, GenericBindPrompt, GroupRolesConfirmationPrompt],
)
class BindCommand(GenericCommand):
    """bind Discord role(s) to Roblox entities"""

    async def __main__(self, ctx: CommandContext):
        raise NotImplementedError("This command has sub-commands and cannot be run directly.")

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

        try:
            await get_group(group_id)
        except RobloxNotFound:
            # Can't be ephemeral sadly bc of the defer state for the command.
            return await ctx.response.send_first(
                f"The group ID ({group_id}) you gave is either invalid or does not exist."
            )

        if bind_mode == "specific_roles":
            await ctx.response.send_prompt(
                GroupPrompt,
                custom_id_data={
                    "group_id": group_id,
                },
            )

        elif bind_mode == "entire_group":
            await ctx.response.send_prompt(
                GroupRolesConfirmationPrompt,
                custom_id_data={
                    "group_id": group_id,
                },
            )

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="asset_id",
                description="What is your asset ID?",
                is_required=True,
            )
        ]
    )
    async def asset(self, ctx: CommandContext):
        """Bind an asset to your server"""

        await self._handle_command(ctx, "catalogAsset")

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="badge_id",
                description="What is your badge ID?",
                is_required=True,
            )
        ]
    )
    async def badge(self, ctx: CommandContext):
        """Bind a badge to your server"""

        await self._handle_command(ctx, "badge")

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="gamepass_id",
                description="What is your gamepass ID?",
                is_required=True,
            )
        ]
    )
    async def gamepass(self, ctx: CommandContext):
        """Bind a gamepass to your server"""

        await self._handle_command(ctx, "gamepass")

    async def _handle_command(
        self,
        ctx: CommandContext,
        cmd_type: Literal["group", "catalogAsset", "badge", "gamepass"],
    ):
        """
        Handle initial command input and response.

        It is primarily intended to be used for the asset, badge, and gamepass types.
        The group command is handled by itself in its respective command method.
        """
        match cmd_type:
            case "catalogAsset" | "badge" | "gamepass":
                input_id = ctx.options[f"{cmd_type}_id" if cmd_type != "catalogAsset" else "asset_id"]

                try:
                    match cmd_type:
                        case "asset":
                            await get_catalog_asset(input_id)
                        case "badge":
                            await get_badge(input_id)
                        case "gamepass":
                            await get_gamepass(input_id)
                except RobloxNotFound:
                    return await ctx.response.send_first(
                        f"The {cmd_type} ID ({input_id}) you gave is either invalid or does not exist."
                    )

                await ctx.response.send_prompt(
                    GenericBindPrompt,
                    custom_id_data={
                        "entity_id": input_id,
                        "entity_type": cmd_type if cmd_type != "asset" else "catalogAsset",
                    },
                )


class PromptComponents:
    """Container for generic components that prompts may use."""

    @staticmethod
    def discord_role_selector(
        *, placeholder="Choose a Discord role", min_values=0, max_values=25, component_id="discord_role"
    ) -> RoleSelectMenu:
        """Create a discord role selection component for a prompt."""
        return RoleSelectMenu(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            component_id=component_id,
        )

    @staticmethod
    def group_rank_selector(
        *,
        roblox_group: RobloxGroup = None,
        placeholder: str = "Choose a group rank",
        min_values: int = 0,
        max_values: int = 2,
        component_id: str = "group_rank",
    ) -> TextSelectMenu:
        """Create a group rank/roleset selection menu for a prompt.

        Only returns a selector for the first 25 ranks, if a group has over 25 ranks, the user should have
        an alternative method to choose from the entire range.
        """
        if not roblox_group:
            raise ValueError("A roblox_group is required when using group_rank_selector.")

        first_25_rolesets = itertools.islice(roblox_group.rolesets.items(), 0, 25)

        return TextSelectMenu(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            component_id=component_id,
            options=[
                TextSelectMenu.Option(
                    label=str(roleset),
                    value=str(roleset_id),
                )
                for roleset_id, roleset in first_25_rolesets
                if roleset_id != 0
            ],
        )

    @staticmethod
    async def roleset_selection_modal(
        title: str,
        *,
        interaction: hikari.ComponentInteraction | hikari.CommandInteraction,
        prompt: "Prompt",
        fired_component_id: str,
    ) -> "modal.Modal":
        return await modal.build_modal(
            title=title or "Select a group rank",
            interaction=interaction,
            command_name=prompt.command_name,
            prompt_data={
                "original_custom_id": prompt.custom_id,
                "page_number": prompt.current_page_number,
                "prompt_name": prompt.__class__.__name__,
                "component_id": fired_component_id,
                "prompt_message_id": prompt.custom_id.prompt_message_id,
            },
            components=[
                TextInput(
                    label="Rank ID Input",
                    style=TextInput.TextInputStyle.SHORT,
                    placeholder="Type the ID(s) or range you want to use for this bind...",
                    custom_id="rank_input",
                    required=True,
                )
            ],
        )
