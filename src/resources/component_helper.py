import hikari

from resources.bloxlink import instance as bloxlink
import resources.commands as commands
from typing import Type, TypeVar
from attrs import fields

T = TypeVar('T')

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
                                emoji=option.emoji,
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
                        emoji=option.emoji,
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
                # print(component.custom_id)
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


def component_author_validation(author_segment: int = 2, ephemeral: bool = True, defer: bool = True):
    """Handle same-author validation for components.
    Utilized to ensure that the author of the command is the only one who can press buttons.

    Args:
        author_segment (int): The segment (as preferred by get_custom_id_data) where the original author's ID
            will be located in. Defaults to 2.
        ephemeral (bool): Set if the response should be ephemeral or not. Default is true.
            A user mention will be included in the response if not ephemeral.
        defer (bool): Set if the response should be deferred by the handler. Default is true.
    """

    def func_wrapper(func):
        async def response_wrapper(ctx: commands.CommandContext):
            interaction = ctx.interaction

            author_id = get_custom_id_data(interaction.custom_id, segment=author_segment)

            # Only accept input from the author of the command
            # Presumes that the original author ID is the second value in the custom_id.
            if str(interaction.member.id) != author_id:
                # Could just silently fail too... Can't defer before here or else the eph response
                # fails to show up.
                yield (
                    interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
                    .set_content(
                        f"You {f'(<@{interaction.member.id}>) ' if not ephemeral else ''}"
                        "are not the person who ran this command!"
                    )
                    .set_flags(hikari.MessageFlag.EPHEMERAL if ephemeral else None)
                )
                return
            else:
                if defer:
                    await interaction.create_initial_response(
                        hikari.ResponseType.DEFERRED_MESSAGE_UPDATE,
                        flags=hikari.MessageFlag.EPHEMERAL if ephemeral else None,
                    )

            # Trigger original method
            generator_or_coroutine = func(commands.build_context(interaction))
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    yield generator_response
            else:
                await generator_or_coroutine

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

def parse_custom_id(T: Type[T], custom_id: str) -> T:
    """Parses a custom_id into T.

    Args:
        T (Type[T]): The type to parse the custom_id into.
        custom_id (str): The custom_id to parse.

    Returns:
        T: The parsed custom_id.
    """

    return T(
        *custom_id.split(":")
    )

def get_custom_id(T: Type[T], **kwargs) -> str:
    """Constructs a custom_id string from keyword arguments based on the attrs dataclass structure.

    Args:
        T (Type[T]): The attrs dataclass type for which the custom_id will be constructed.
        **kwargs: Keyword arguments representing the field values of the dataclass.

    Returns:
        str: The custom_id string separated by colons.
    """
    # Create an instance of the attrs dataclass with the provided keyword arguments
    custom_id_instance = T(**kwargs)

    # Retrieve the field values in the order specified by the dataclass
    field_values = [str(getattr(custom_id_instance, field.name)) for field in fields(T)]

    # Create the custom_id string by joining the field values with colons
    custom_id_string = ":".join(field_values)

    return custom_id_string
