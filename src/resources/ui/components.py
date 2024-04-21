from __future__ import annotations

from typing import Type, Literal, Self, Annotated
from enum import Enum
from abc import ABC, abstractmethod
from pydantic import Field, field_validator
from bloxlink_lib import BaseModelArbitraryTypes, BaseModel
import hikari

from resources.bloxlink import instance as bloxlink
from resources import commands


class BaseCustomID(BaseModel):
    """Base class for interactive custom IDs."""

    @classmethod
    def from_str(cls: Type[Self], custom_id: str, **kwargs) -> Self:
        """Converts a custom_id string into a custom_id object."""

        # Split the custom_id into parts
        parts = custom_id.split(':')
        attrs_parts: dict[str, str] = {field_tuple[0]: parts[index] for index, field_tuple in enumerate(cls.model_fields_index())}

        for field_name, value in dict(attrs_parts).items():
            if value == "":
                del attrs_parts[field_name]

        # Create an instance of the attrs dataclass with the custom_id values
        custom_id_instance = cls(**attrs_parts, **kwargs)

        # Return the dataclass instance, discarding additional values
        return custom_id_instance

    def set_fields(self, **kwargs) -> Self:
        """Sets the fields in the custom_id object."""

        # Split the existing custom_id into parts
        parts = str(self).split(':')
        attrs_parts: dict[str, str] = {field_tuple[0]: parts[index] for index, field_tuple in enumerate(self.model_fields_index())}

        for field_name, value in dict(attrs_parts).items():
            if value == "":
                del attrs_parts[field_name]

        # Update specified fields with the provided keyword arguments
        for field_name, value in kwargs.items():
            setattr(self, field_name, value)

        return self

    def __str__(self):
        field_values: list[str] = []

        for field_name in self.model_fields:
            field_value = getattr(self, field_name)

            if field_value is None:
                field_values.append("")
            else:
                field_values.append(str(field_value))

        return ":".join(field_values)

    def __hash__(self) -> int:
        return hash(str(self))

    def __add__(self, other: Self) -> str:
        return f"{str(self)}:{str(other)}"

class UnsupportedCustomID(BaseCustomID):
    """Old custom ID from V3. Only has one attribute, the unsupported custom id."""

    content: str

class BaseCommandCustomID(BaseCustomID):
    """Very basic custom ID. Used to map custom ID -> handler in a command."""

    command_name: str
    section: str = "" # used to differentiate between different sections of the same command

class CommandCustomID(BaseCommandCustomID):
    """Custom ID containing more information for commands."""

    command_name: str
    section: str = "" # used to differentiate between different sections of the same command
    subcommand_name: str = ""
    type: Literal["command", "prompt", "paginator"] = "command"
    user_id: int = 0


class Component(BaseModelArbitraryTypes, ABC):
    """Abstract base class for components."""

    type: Literal[
        hikari.ComponentType.BUTTON,
        hikari.ComponentType.TEXT_SELECT_MENU,
        hikari.ComponentType.ROLE_SELECT_MENU,
        hikari.ComponentType.TEXT_INPUT,
    ] = None
    custom_id: str | CommandCustomID = None # only None for prompt page initializations, it's set by the prompt handler
    component_id: str = None # used for prompts

    @field_validator("custom_id", mode="before")
    @classmethod
    def transform_custom_id(cls: Type[Self], custom_id: str | CommandCustomID) -> str:
        return str(custom_id)

    @abstractmethod
    def build(self, action_rows:list[hikari.impl.MessageActionRowBuilder]) -> list[hikari.impl.MessageActionRowBuilder]:
        """Builds the component into a Hikari component and appends it to the last action row. The action row is returned for chaining."""

        raise NotImplementedError()


class Button(Component):
    """Base class for buttons."""

    class ButtonStyle(Enum):
        """Button styles."""

        PRIMARY = 1
        SECONDARY = 2
        SUCCESS = 3
        DANGER = 4
        LINK = 5

    label: str
    style: ButtonStyle = ButtonStyle.PRIMARY
    is_disabled: bool = False
    emoji: hikari.Emoji = None
    url: str = None
    type: Annotated[hikari.ComponentType.BUTTON, Field(default=hikari.ComponentType.BUTTON)]

    def model_post_init(self, __context):
        if self.url:
            self.style = Button.ButtonStyle.LINK


    def build(self, action_rows:list[hikari.impl.MessageActionRowBuilder]):
        current_action_row = action_rows[len(action_rows)-1]

        if self.style == Button.ButtonStyle.LINK:
            current_action_row.add_link_button(
                self.url,
                label=self.label,
                # emoji=self.emoji,
                is_disabled=self.is_disabled,
            )
        else:
            current_action_row.add_interactive_button(
                hikari.ButtonStyle[self.style.name],
                self.custom_id,
                label=self.label,
                # emoji=self.emoji,
                is_disabled=self.is_disabled,
            )


        return action_rows

class SelectMenu(Component, ABC):
    """Abstract base class for select menus."""

    placeholder: str = "Select an option..."
    min_values: int = 1
    max_values: int = None
    min_length: int = 1
    max_length: int = None
    is_disabled: bool = False


class RoleSelectMenu(SelectMenu):
    """Base class for role select menus."""

    placeholder: str = "Select a role..."
    type: Annotated[hikari.ComponentType.ROLE_SELECT_MENU, Field(default=hikari.ComponentType.ROLE_SELECT_MENU)]

    def build(self, action_rows:list[hikari.impl.MessageActionRowBuilder]):
        # Role menus take up one full action row.
        new_action_row = bloxlink.rest.build_message_action_row()
        action_rows.append(new_action_row)

        new_action_row.add_select_menu(
            hikari.ComponentType.ROLE_SELECT_MENU,
            self.custom_id,
            placeholder=self.placeholder,
            min_values=self.min_values,
            max_values=self.max_values,
            is_disabled=self.is_disabled,
        )

        # Next component gets an empty action row
        action_rows.append(bloxlink.rest.build_message_action_row())

        return action_rows


class TextSelectMenu(SelectMenu):
    """Base class for text select menus."""

    options: Annotated[list['Option'], Field(default_factory=list)]
    type: Annotated[hikari.ComponentType.TEXT_SELECT_MENU, Field(default=hikari.ComponentType.TEXT_SELECT_MENU)]

    class Option(BaseModelArbitraryTypes):
        """Option for a text select menu."""

        label: str
        value: str
        description: str = None
        emoji: hikari.Emoji = None
        is_default: bool = False

    def build(self, action_rows:list[hikari.impl.MessageActionRowBuilder]):
        # Text menus take up one full action row.
        new_action_row = bloxlink.rest.build_message_action_row()
        action_rows.append(new_action_row)

        text_menu = new_action_row.add_text_menu(
            self.custom_id,
            placeholder=self.placeholder,
            min_values=self.min_values,
            max_values=self.max_values,
            is_disabled=self.is_disabled,
        )

        for option in self.options:
            text_menu.add_option(
                option.label,
                option.value,
                description=option.description,
                is_default=option.is_default,
            )

        # Next component gets an empty action row
        action_rows.append(bloxlink.rest.build_message_action_row())

        return action_rows


class TextInput(Component):
    """Base class for modal text inputs."""

    class TextInputStyle(Enum):
        """Text input styles."""

        SHORT = 1
        PARAGRAPH = 2

    label: str
    placeholder: str = None
    value: str = None
    min_length: int = 1
    max_length: int = None
    required: bool = False
    style: TextInputStyle = TextInputStyle.SHORT
    type: Annotated[hikari.ComponentType.TEXT_INPUT, Field(default=hikari.ComponentType.TEXT_INPUT)]

    def build(self, action_rows:list[hikari.impl.MessageActionRowBuilder]):
        # Text inputs take up one full action row.
        modal_action_row = hikari.impl.ModalActionRowBuilder()
        action_rows.append(modal_action_row)

        modal_action_row.add_text_input(
            self.custom_id,
            self.label,
            placeholder=self.placeholder,
            min_length=self.min_length or 1,
            max_length=self.max_length or 2000,
            required=self.required or False,
            style=hikari.TextInputStyle[self.style.name] or hikari.TextInputStyle.SHORT,
            value=self.value
        )

        return action_rows


class Separator(Component):
    """Used to build a new ActionRow for the next set of components."""

    def build(self, action_rows:list[hikari.impl.MessageActionRowBuilder]):
        new_action_row = bloxlink.rest.build_message_action_row()

        action_rows.append(new_action_row)

        return action_rows


def clean_action_rows(action_rows:list[hikari.impl.MessageActionRowBuilder]) -> list[hikari.impl.MessageActionRowBuilder]:
    """Removes empty action rows from the list. Empty action rows may appear from using Component.build()."""

    return list(filter(lambda action_row: len(action_row.components) > 0, action_rows))


async def get_component(message: hikari.Message, custom_id: str):
    """Get a component in a message based on the custom_id"""
    for action_row in message.components:
        for component in action_row.components:
            if component.custom_id.startswith(custom_id):
                return component


async def set_components(message: hikari.Message, *, values: list = None, components: list = None):
    """Update the components on a message

    Args:
        message (hikari.Message): The message to set the components for.
        values (list, optional): Unused + unsure what this is for. Defaults to None.
        components (list, optional): The components to set on this message. Defaults to None.
    """

    new_components = []
    components = components or []
    values = values or []

    iterate_components = []

    for action_row_or_component in components or message.components:
        if hasattr(action_row_or_component, "build"):
            iterate_components.append(action_row_or_component)
        else:
            # Keep action row components together.
            temp = []
            for component in action_row_or_component.components:
                temp.append(component)
            iterate_components.append(temp)

    for component in iterate_components:
        if hasattr(component, "build"):
            new_components.append(component)

        elif isinstance(component, list):
            # Components in a list = in an action row.
            row = bloxlink.rest.build_message_action_row()

            for subcomponent in component:
                if isinstance(subcomponent, hikari.SelectMenuComponent):
                    if subcomponent.type == hikari.ComponentType.TEXT_SELECT_MENU:
                        new_select_menu = row.add_text_menu(
                            subcomponent.custom_id,
                            placeholder=subcomponent.placeholder,
                            min_values=subcomponent.min_values,
                            max_values=subcomponent.max_values,
                            is_disabled=subcomponent.is_disabled,
                        )
                        for option in subcomponent.options:
                            new_select_menu = new_select_menu.add_option(
                                option.label,
                                option.value,
                                description=option.description,
                                emoji=option.emoji if option.emoji else hikari.undefined.UNDEFINED,
                                is_default=option.is_default,
                            )

                elif isinstance(subcomponent, hikari.ButtonComponent):
                    # add_x_button seems to only accept labels OR emojis, which isn't valid anymore to my knowledge
                    # might be worth mentioning to hikari devs to look into/investigate more.
                    if subcomponent.style == hikari.ButtonStyle.LINK:
                        row.add_link_button(
                            subcomponent.url,
                            label=subcomponent.label
                            if not subcomponent.emoji
                            else hikari.undefined.UNDEFINED,
                            emoji=subcomponent.emoji if subcomponent.emoji else hikari.undefined.UNDEFINED,
                            is_disabled=subcomponent.is_disabled,
                        )
                    else:
                        row.add_interactive_button(
                            subcomponent.style,
                            subcomponent.custom_id,
                            label=subcomponent.label
                            if not subcomponent.emoji
                            else hikari.undefined.UNDEFINED,
                            emoji=subcomponent.emoji if subcomponent.emoji else hikari.undefined.UNDEFINED,
                            is_disabled=subcomponent.is_disabled,
                        )

            new_components.append(row)

        elif isinstance(component, hikari.SelectMenuComponent):
            new_select_menu = row.add_select_menu(
                subcomponent.type,
                subcomponent.custom_id,
                placeholder=subcomponent.placeholder,
                min_values=subcomponent.min_values,
                max_values=subcomponent.max_values,
                is_disabled=subcomponent.is_disabled,
            )

            if subcomponent.type == hikari.ComponentType.TEXT_SELECT_MENU:
                for option in subcomponent.options:
                    new_select_menu = new_select_menu.add_option(
                        option.label,
                        option.value,
                        description=option.description,
                        emoji=option.emoji if option.emoji else hikari.undefined.UNDEFINED,
                        is_default=option.is_default,
                    )

            new_components.append(new_select_menu)

        elif isinstance(component, hikari.ButtonComponent):
            row = bloxlink.rest.build_message_action_row()

            # add_x_button seems to only accept labels OR emojis, which isn't valid anymore to my knowledge
            # might be worth mentioning to hikari devs to look into/investigate more.
            if component.style == hikari.ButtonStyle.LINK:
                row.add_link_button(
                    component.url,
                    label=component.label if not component.emoji else hikari.undefined.UNDEFINED,
                    emoji=component.emoji if component.emoji else hikari.undefined.UNDEFINED,
                    is_disabled=component.is_disabled,
                )
            else:
                row.add_interactive_button(
                    component.style,
                    component.custom_id,
                    label=component.label if not component.emoji else hikari.undefined.UNDEFINED,
                    emoji=component.emoji if component.emoji else hikari.undefined.UNDEFINED,
                    is_disabled=component.is_disabled,
                )

            new_components.append(row)

    await message.edit(embeds=message.embeds, components=new_components)

async def disable_components(
    interaction: hikari.ComponentInteraction | hikari.CommandInteraction,
    message: hikari.Message=None,
    channel_id: int=None,
    message_id: int=None
):
    if not message:
        if message_id and channel_id:
            message = await bloxlink.rest.fetch_message(
                channel_id,
                message_id
            )
        elif interaction:
            message = interaction.message
        else:
            raise ValueError("interaction is required if message or (message_id and channel_id) is not provided")

    for action_row in message.components:
        for component in action_row.components:
            component.is_disabled = True

    await set_components(message, components=message.components)

def get_custom_id_data(
    custom_id: str,
    segment: int = None,
    segment_min: int = None,
    segment_max: int = None,
    message: hikari.Message = None,
) -> str | tuple | None:
    """Extrapolate data from a given custom_id. Splits around the ":" character.

    Args:
        custom_id (str): The custom id to get data from.
        segment (int, optional): Gets a specific part of the ID. Must be >= 1. Defaults to None.
        segment_min (int, optional): For a range, starts at the minimum here and goes until segment_max or
            the end of the segments. Must be >= 1. Defaults to None.
        segment_max (int, optional): For a range, the maximum boundary of segments to retrieve. Defaults to None.
        message (hikari.Message, optional): Message to get the custom_id from. Defaults to None.
            Expects custom_id to be a prefix, will search for the custom_id to use based on components
            on this message.

    Returns:
        str | tuple | None: The matching segment(s). str for a single segment, tuple for ranges, None for no match.
    """
    if message:
        for action_row in message.components:
            for component in action_row.components:
                if component.custom_id.startswith(custom_id):
                    custom_id = component.custom_id

    if isinstance(custom_id, hikari.Snowflake):
        custom_id = str(custom_id)

    custom_id_data = custom_id.split(":")
    segment_data = None

    if segment:
        segment_data = custom_id_data[segment - 1] if len(custom_id_data) >= segment else None
    elif segment_min:
        segment_data = tuple(
            custom_id_data[segment_min - 1 : (segment_max if segment_max else len(custom_id_data))]
        )

    return segment_data


async def set_custom_id_data(message: hikari.Message, custom_id: str, segment: int, values: list | str):
    """Sets additional data in a custom_id at, or after, a specific index.

    Args:
        message (hikari.Message): The message to get the component to update.
        custom_id (str): The custom_id string that is currently set.
        segment (int): The index to start setting the data at (starts at 1).
        values (list | str): The data to add to the custom_id string.
    """
    component = await get_component(message, custom_id=custom_id)

    if isinstance(values, str):
        values = [values]

    if component:
        custom_id_data = component.custom_id.split(":")

        if len(custom_id_data) < segment:
            for _ in range(segment - len(custom_id_data)):
                custom_id_data.append("")

            custom_id = ":".join(custom_id_data)

        segment_data = (custom_id_data[segment - 1] if len(custom_id_data) >= segment else "").split(",")

        if segment_data[0] == "":
            # fix blank lists
            segment_data.pop(0)

        for value in values:
            value = value.strip()
            if value not in segment_data:
                segment_data.append(value)

        custom_id_data[segment - 1] = ",".join(segment_data)
        component.custom_id = ":".join(custom_id_data)

        await set_components(message, values=values)


async def check_all_modified(message: hikari.Message, *custom_ids: tuple[str]) -> bool:
    """Check if a custom_id(s) exists in a message.

    Args:
        message (hikari.Message): The message to search for custom IDs on.
        *custom_ids (tuple[str]): The IDs to search for.

    Returns:
        bool: If all of the given custom_id(s) were set on one of the components for this message.
    """
    for action_row in message.components:
        for component in action_row.components:
            if component.custom_id in custom_ids:
                return False

    return True


def component_author_validation(parse_into: CommandCustomID=CommandCustomID, ephemeral: bool=True, defer: bool=True):
    """Handle same-author validation for components.
    Utilized to ensure that the author of the command is the only one who can press buttons.

    Args:
        ephemeral (bool): Set if the response should be ephemeral or not. Default is true.
            A user mention will be included in the response if not ephemeral.
        defer (bool): Set if the response should be deferred by the handler. Default is true.
    """

    def func_wrapper(func):
        async def response_wrapper(ctx: commands.CommandContext, custom_id: BaseCustomID | None=None ):
            interaction = ctx.interaction
            parsed_custom_id = custom_id or parse_into.from_str(interaction.custom_id)

            command_context = commands.build_context(interaction)
            response = command_context.response

            # Only accept input from the author of the command
            if interaction.member.id != parsed_custom_id.user_id:
                yield await response.send_first("You are not the person who ran this command.", ephemeral=True)
                return

            if defer:
                yield await response.defer(ephemeral)

            # Trigger original method
            try:
                yield await func(command_context, parsed_custom_id)
            except TypeError:
                yield await func(command_context)

            return

        return response_wrapper

    return func_wrapper


def component_values_to_dict(interaction: hikari.ComponentInteraction):
    """Converts the values from a component into a dict.

    Args:
        interaction (hikari.ComponentInteraction): The interaction to get the values from.

    Returns:
        dict: dict representation of the values.
    """
    return {
            "values": interaction.values,
            "resolved": {
                "users": [str(user_id) for user_id in interaction.resolved.users] if interaction.resolved else [],
                "members": [str(member_id) for member_id in interaction.resolved.members] if interaction.resolved else [],
                "roles": [str(role_id) for role_id in interaction.resolved.roles] if interaction.resolved else [],
                "channels": [str(channel_id) for channel_id in interaction.resolved.channels] if interaction.resolved else [],
                "messages": [str(message_id) for message_id in interaction.resolved.messages] if interaction.resolved else [],
                # "attachments": interaction.resolved.attachments if interaction.resolved else [],
            },
        }
