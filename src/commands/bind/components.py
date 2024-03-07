import itertools

import hikari
from bloxlink_lib import GuildBind
from bloxlink_lib.models.groups import RobloxGroup
from thefuzz import process

import resources.ui.modals as modal
from resources.exceptions import RobloxAPIError
from resources.response import Prompt
from resources.ui.components import Button, RoleSelectMenu, TextInput, TextSelectMenu


class PromptComponents:
    """Container for generic components that prompts may use."""

    @staticmethod
    def discord_role_selector(
        *,
        placeholder: str = "Choose a Discord role",
        min_values: int = 0,
        max_values: int = 5,
        component_id: str = "discord_role",
        disabled: bool = False,
    ) -> RoleSelectMenu:
        """Create a discord role selection component for a prompt."""
        return RoleSelectMenu(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            component_id=component_id,
            is_disabled=disabled,
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
        menu_options = [
            TextSelectMenu.Option(
                label=str(roleset),
                value=str(roleset_id),
            )
            for roleset_id, roleset in first_25_rolesets
            if roleset_id != 0
        ]
        menu_options.reverse()

        return TextSelectMenu(
            placeholder=placeholder,
            min_values=min_values,
            max_values=max_values,
            component_id=component_id,
            options=menu_options,
        )

    @staticmethod
    async def roleset_selection_modal(
        title: str,
        *,
        interaction: hikari.ComponentInteraction | hikari.CommandInteraction,
        prompt: "Prompt",
        fired_component_id: str,
    ) -> "modal.Modal":
        """Send a modal to the user asking for some rank ID input."""
        return await modal.build_modal(
            title=title or "Select a group rank",
            interaction=interaction,
            command_name=prompt.command_name,
            prompt_data=modal.ModalPromptArgs(
                prompt_name=prompt.prompt_name,
                original_custom_id=prompt.custom_id,
                page_number=prompt.current_page_number,
                prompt_message_id=prompt.custom_id.prompt_message_id,
                component_id=fired_component_id,
            ),
            components=[
                TextInput(
                    label="Rank ID Input",
                    style=TextInput.TextInputStyle.SHORT,
                    placeholder="Type the name or ID of the rank for this bind.",
                    custom_id="rank_input",
                    required=True,
                )
            ],
        )

    @staticmethod
    async def multi_roleset_selection_modal(
        title: str,
        *,
        interaction: hikari.ComponentInteraction | hikari.CommandInteraction,
        prompt: "Prompt",
        fired_component_id: str,
    ) -> "modal.Modal":
        """Send a modal to the user asking for some rank ID input."""
        return await modal.build_modal(
            title=title or "Select a group rank",
            interaction=interaction,
            command_name=prompt.command_name,
            prompt_data=modal.ModalPromptArgs(
                prompt_name=prompt.prompt_name,
                original_custom_id=prompt.custom_id,
                page_number=prompt.current_page_number,
                prompt_message_id=prompt.custom_id.prompt_message_id,
                component_id=fired_component_id,
            ),
            components=[
                TextInput(
                    label="Minimum Rank Input",
                    style=TextInput.TextInputStyle.SHORT,
                    placeholder="Type the name or ID of the rank for this bind.",
                    custom_id="min_rank_input",
                    required=True,
                ),
                TextInput(
                    label="Maximum Rank Input",
                    style=TextInput.TextInputStyle.SHORT,
                    placeholder="Type the name or ID of the rank for this bind.",
                    custom_id="max_rank_input",
                    required=True,
                ),
            ],
        )

    @staticmethod
    async def unsaved_bind_selector(
        *,
        pending_binds: list[GuildBind] = None,
        component_id: str = "unbind_menu",
    ):
        """Return a selection menu allowing people to remove unsaved bindings."""
        if pending_binds is None:
            raise ValueError("A list of pending binds is required.")

        for bind in pending_binds:
            try:
                await bind.entity.sync()
            except RobloxAPIError:
                pass

        return TextSelectMenu(
            placeholder="Select which binds to remove here...",
            min_values=0,
            max_values=len(pending_binds),
            component_id=component_id,
            options=[
                TextSelectMenu.Option(
                    label=f"{index + 1}: {bind.short_description.replace('**', '')}...",
                    value=str(index),
                )
                for index, bind in enumerate(pending_binds)
            ],
        )

    @staticmethod
    def create_role_button(
        *, label: str = "Create a new role", component_id: str = "new_role", disabled: bool = False
    ):
        return Button(
            label=label,
            component_id=component_id,
            is_disabled=disabled,
        )

    @staticmethod
    async def new_role_modal(
        *,
        interaction: hikari.ComponentInteraction | hikari.CommandInteraction,
        prompt: "Prompt",
        fired_component_id: str,
        title: str = None,
    ) -> "modal.Modal":
        """Send a modal to the user asking for some rank ID input."""
        return await modal.build_modal(
            title=title or "Create a discord role",
            interaction=interaction,
            command_name=prompt.command_name,
            prompt_data=modal.ModalPromptArgs(
                prompt_name=prompt.prompt_name,
                original_custom_id=prompt.custom_id,
                page_number=prompt.current_page_number,
                prompt_message_id=prompt.custom_id.prompt_message_id,
                component_id=fired_component_id,
            ),
            components=[
                TextInput(
                    label="New role name",
                    style=TextInput.TextInputStyle.SHORT,
                    placeholder="Type the name of the role to create on submission.",
                    custom_id="role_name",
                    required=True,
                    max_length=100,
                )
            ],
        )


def parse_modal_rank_input(user_input: str, roblox_group: RobloxGroup) -> int:
    """Get a rank ID out from a modal TextInput.

    Args:
        user_input (str): Input from the user for that TextInput
        roblox_group (RobloxGroup): _description_

    Returns:
        int: The found rank ID. If there is no match, -1 is returned.
    """
    if not user_input.isdigit():
        # Fuzzy string match the user input to the roleset name.
        roleset_mapping = {key: roleset.name for key, roleset in roblox_group.rolesets.items()}
        _roleset_name, _, roleset_id = process.extractOne(query=user_input, choices=roleset_mapping)

        user_input = roleset_id
    else:
        if int(user_input) not in roblox_group.rolesets.keys():
            return -1

    return int(user_input)
