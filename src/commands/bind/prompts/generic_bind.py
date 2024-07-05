import hikari
from bloxlink_lib import GuildBind, build_binds_desc, create_entity

from commands.bind.components import PromptComponents
from resources.binds import create_bind
from resources.bloxlink import bloxlink
from resources.constants import GREEN_COLOR
from resources.exceptions import RobloxAPIError
from resources.response import Prompt, PromptCustomID, PromptPageData
from resources.ui.components import Button


class GenericBindPromptCustomID(PromptCustomID):
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
                        bind_id=self.custom_id.entity_id,
                        roles=bind.roles,
                        remove_roles=bind.remove_roles,
                        **bind_criteria,
                    )

                # TODO Hack so we can change field names with edit_page.
                current_embed = interaction.message.embeds[0]
                current_embed.title = f"New {bind_type} binds saved."
                current_embed.description = "The binds on this menu were saved to your server. You can edit your binds at any time by running `/bind` again."
                current_embed.edit_field(1, "Created binds")
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
                    bind_id=self.custom_id.entity_id,
                    bind_type=bind_type,
                )

                await self.clear_data(
                    "discord_role", "unbind_menu", "entity_str"
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
                    # print(unsaved_binds)

                    prompt_fields.append(
                        PromptPageData.Field(
                            name="Unsaved Binds",
                            value=unsaved_binds,
                            inline=True,
                        )
                    )

                entity_str = await self.current_data(key_name="entity_str", raise_exception=False)
                if not entity_str:
                    roblox_entity = create_entity(bind_type, self.custom_id.entity_id)

                    try:
                        await roblox_entity.sync()
                    except RobloxAPIError:
                        pass

                    entity_str = str(roblox_entity).replace("**", "")

                    await self.save_stateful_data(entity_str=entity_str)

                yield PromptPageData(
                    title=f"{'[UNSAVED CHANGES] ' if new_binds else ''}New {bind_type.capitalize()} Bind",
                    description=f"Here are the current binds for your server for that {bind_type.capitalize()}. Click the button below to make a new bind.",
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
                    footer_text=f"{bind_type.capitalize()}: {entity_str}",
                )

    @Prompt.programmatic_page()
    async def bind_role(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """Prompts for a user to select which roles will be given for bind."""

        if fired_component_id != "new_role":
            yield await self.response.defer()

        bind_id = self.custom_id.entity_id
        bind_type = self.custom_id.entity_type

        current_data = await self.current_data()

        yield PromptPageData(
            title="Bind Discord Role",
            description=f"Please select a Discord role to give to users who own this {bind_type}. "
            "No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptComponents.discord_role_selector(min_values=1),
                PromptComponents.create_role_button(),
            ],
            footer_text=f"{bind_type.capitalize()}: {current_data.get('entity_str', bind_id)}",
        )

        current_data = await self.current_data()

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
                            "type": bind_type,
                            "id": bind_id,
                        },
                    )
                )
            else:
                existing_pending_binds.append(
                    GuildBind(
                        roles=discord_role,
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
