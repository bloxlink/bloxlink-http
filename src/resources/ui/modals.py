import json
from typing import TypedDict
from pydantic import Field
import hikari
from bloxlink_lib import BaseModelArbitraryTypes
from bloxlink_lib.database import redis
from resources.ui.components import TextInput, CommandCustomID, BaseCustomID
from resources import response


class ModalCustomID(CommandCustomID):
    """Represents a custom ID for a modal component."""

    component_custom_id: str = Field(default="")


class ModalPromptArgs(TypedDict):
    """Arguments for modals used in prompts"""

    prompt_name: str
    original_custom_id: BaseCustomID
    user_id: int
    page_number: int
    prompt_message_id: int
    component_id: str

class ModalCommandArgs(TypedDict, total=False):
    """Arguments for modals used in commands"""

    subcommand_name: str


class Modal(BaseModelArbitraryTypes):
    """Represents a Discord Modal."""

    builder: hikari.impl.InteractionModalBuilder | None
    custom_id: BaseCustomID
    data: dict | None = None
    command_options: dict | None = None

    async def submitted(self):
        """Returns whether the modal was submitted."""

        if self.data is None:
            await self.get_data()

        return self.data is not None

    async def get_data(self, *keys: tuple[str]):
        """Returns the data from the modal."""

        modal_data = {}

        if self.data is not None:
            modal_data = self.data
        else:
            modal_data = await redis.get(f"modal_data:{self.custom_id}")

            if modal_data is None:
                return None

            modal_data = json.loads(modal_data) if modal_data else {}

        self.data = modal_data

        if keys:
            if len(keys) == 1:
                return modal_data.get(keys[0])

            return {key: modal_data.get(key) for key in keys}

        return self.data

    async def clear_data(self):
        """Clears the data from the modal."""

        await redis.delete(f"modal_data:{self.custom_id}")
        self.data = None


async def build_modal(title: str, components: list[TextInput], *, interaction: hikari.ComponentInteraction | hikari.CommandInteraction, command_name: str, prompt_data: ModalPromptArgs = None, command_data: ModalCommandArgs = None) -> Modal:
    """Build a modal response. This needs to be separately returned."""

    if prompt_data is None and command_data is None:
        raise ValueError("prompt_data and command_data cannot both be provided.")

    if prompt_data is not None and command_data is not None:
        raise ValueError("prompt_data and command_data cannot both be provided.")

    if command_data is not None:
        new_custom_id = ModalCustomID(
            command_name=command_name,
            subcommand_name=command_data.get("subcommand_name") or "",
            user_id=interaction.user.id,
        )
    elif prompt_data is not None:
        custom_id_format: ModalCustomID = (await response.Prompt.find_prompt(prompt_data["original_custom_id"], interaction)).custom_id_format

        new_custom_id = custom_id_format.from_str(interaction.custom_id).set_fields(
            command_name=command_name,
            subcommand_name="",
            prompt_name=prompt_data.get("prompt_name") or "",
            user_id=interaction.user.id,
            page_number=prompt_data.get("page_number") or 0,
            prompt_message_id=prompt_data.get("prompt_message_id") or 0,
            component_custom_id=prompt_data.get("component_id") or "",
        )

    modal_builder: hikari.impl.InteractionModalBuilder = None

    if not isinstance(interaction, hikari.ModalInteraction):
        modal_builder = interaction.build_modal_response(title, str(new_custom_id))

        for component in components:
            modal_action_row = hikari.impl.ModalActionRowBuilder()

            modal_action_row.add_text_input(
                component.custom_id,
                component.label,
                placeholder=component.placeholder,
                min_length=component.min_length or 1,
                max_length=component.max_length or 2000,
                required=component.required or False,
                style=hikari.TextInputStyle[component.style.name] or hikari.TextInputStyle.SHORT,
                value=component.value
            )

            modal_builder.add_component(modal_action_row)

    return Modal(
        builder=modal_builder,
        custom_id=new_custom_id,
        command_options=command_data.get("options") if command_data else None
    )
