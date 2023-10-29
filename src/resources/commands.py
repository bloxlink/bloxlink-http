from __future__ import annotations

import logging
import re
from typing import Any, Callable

import hikari
from attrs import define

from resources.component_helper import parse_custom_id
from resources.exceptions import *
from resources.response import PromptCustomID, Response
from resources.secrets import DISCORD_APPLICATION_ID  # pylint: disable=no-name-in-module

command_name_pattern = re.compile("(.+)Command")

slash_commands = {}


class Command:
    """Base representation of a slash command on Discord"""

    def __init__(
        self,
        name: str,
        fn: Callable = None,  # None if it has sub commands
        category: str = "Miscellaneous",
        permissions=None,
        defer: bool = False,
        defer_with_ephemeral: bool = False,
        description: str = None,
        options: list[hikari.commands.CommandOptions] = None,
        subcommands: dict[str, Callable] = None,
        rest_subcommands: list[hikari.CommandOption] = None,
        accepted_custom_ids: list[str] = None,
        autocomplete_handlers: list[str] = None,
        dm_enabled: bool = None,
        prompts: list[Callable] = None,
    ):
        self.name = name
        self.fn = fn
        self.category = category
        self.permissions = permissions
        self.defer = defer
        self.defer_with_ephemeral = defer_with_ephemeral
        self.description = description
        self.options = options
        self.subcommands = subcommands
        self.rest_subcommands = rest_subcommands
        self.accepted_custom_ids = accepted_custom_ids or {}
        self.autocomplete_handlers = autocomplete_handlers or {}
        self.dm_enabled = dm_enabled
        self.prompts = prompts or []

    async def execute(self, ctx: CommandContext, subcommand_name: str = None):
        """Execute a command (or its subcommand)

        Args:
            ctx (CommandContext): Context for this command.
            subcommand_name (str, optional): Name of the subcommand to trigger. Defaults to None.
        """
        # TODO: check for permissions

        generator_or_coroutine = self.subcommands[subcommand_name](ctx) if subcommand_name else self.fn(ctx)

        if hasattr(generator_or_coroutine, "__anext__"):
            async for generator_response in generator_or_coroutine:
                yield generator_response

        else:
            await generator_or_coroutine


@define(slots=True)
class CommandContext:
    """Data related to a command that has been run.

    Attributes:
        command_name (str): The name of the command triggered.
        command_id (int): The ID of the command triggered.
        guild_id (int): The name of the command triggered.
        member (hikari.InteractionMember): The member that triggered this command.
        user (hikari.User): The user that triggered this command.
        resolved (hikari.ResolvedOptionData): Data of entities mentioned in command arguments that are
            resolved by Discord.
        options (dict): The options/arguments passed by the user to this command.
        interaction (hikari.CommandInteraction): The interaction object from Discord.
        response (Response): Bloxlink's wrapper for handling initial response sending.
    """

    command_name: str
    command_id: int
    guild_id: int
    member: hikari.InteractionMember
    user: hikari.User
    resolved: hikari.ResolvedOptionData
    options: dict[str, str | int]

    interaction: hikari.CommandInteraction

    response: Response


async def handle_interaction(interaction: hikari.Interaction):
    """
    One-stop shop for interaction (command, component, autocomplete) handling.
    Handles all errors from the handlers.

    Top level exceptions include default messages for custom exceptions that are defined in
    resources.exceptions.

    Caught exceptions currently consist of:
        - UserNotVerified
        - BloxlinkForbidden
        - hikari.errors.ForbiddenError
        - RobloxNotFound
        - RobloxDown
        - Message
        - Exception

    Args:
        interaction (hikari.Interaction): Interaction that was triggered.
    """

    correct_handler: Callable = None
    response = Response(interaction)

    if isinstance(interaction, hikari.CommandInteraction):
        correct_handler = handle_command
    elif isinstance(interaction, hikari.ComponentInteraction):
        correct_handler = handle_component
    elif isinstance(interaction, hikari.AutocompleteInteraction):
        correct_handler = handle_autocomplete
    else:
        raise NotImplementedError()

    try:
        async for command_response in correct_handler(interaction, response=response):
            yield command_response

    except UserNotVerified as message:
        await response.send(str(message) or "This user is not verified with Bloxlink!")
    except (BloxlinkForbidden, hikari.errors.ForbiddenError) as message:
        await response.send(
            str(message)
            or "I have encountered a permission error! Please make sure I have the appropriate permissions."
        )
    except RobloxNotFound as message:
        await response.send(
            str(message) or "This Roblox entity does not exist! Please check the ID and try again."
        )
    except RobloxDown:
        await response.send(
            "Roblox appears to be down, so I was unable to process your command. "
            "Please try again in a few minutes."
        )
    except Message as ex:
        await response.send(ex.message)
    except Exception as ex:
        logging.exception(ex)
        await response.send(
            "An unexpected error occurred while processing this command. "
            "Please try again in a few minutes."
        )


async def handle_command(interaction: hikari.CommandInteraction, response: Response):
    """Handle a command interaction."""
    command_name = interaction.command_name
    command_type = interaction.command_type

    command = None
    subcommand_name: str = None
    command_options: dict = None

    # find command
    if command_type == hikari.CommandType.SLASH:
        command: Command = slash_commands.get(command_name)

        if not command:
            return

        # subcommand checking
        subcommand_option: list[hikari.CommandInteractionOption] = list(
            filter(lambda o: o.type == hikari.OptionType.SUB_COMMAND, interaction.options or [])
        )
        subcommand_name = subcommand_option[0].name if subcommand_option else None

    else:
        raise NotImplementedError()

    # get options
    if interaction.options:
        for option in interaction.options:
            if option.name == subcommand_name and option.options:
                command_options = {o.name: o.value for o in option.options}
                break
        else:
            command_options = {o.name: o.value for o in interaction.options}

    if command.defer:
        yield await response.defer(ephemeral=command.defer_with_ephemeral)

    ctx = build_context(interaction, response=response, command=command, options=command_options)

    async for command_response in command.execute(ctx, subcommand_name=subcommand_name):
        yield command_response


async def handle_autocomplete(interaction: hikari.AutocompleteInteraction):
    """Handle an autocomplete interaction."""
    # Iterate through commands and find the autocomplete function that corresponds to the slash cmd option name.
    for command in slash_commands.values():
        if not command.autocomplete_handlers:
            continue

        if not command.name == interaction.command_name:
            continue

        for command_option in interaction.options:
            if not command_option.is_focused:
                continue

            autocomplete_fn = command.autocomplete_handlers.get(command_option.name)

            if not autocomplete_fn:
                logging.error(f'Command {command.name} has no auto-complete handler "{command_option.name}"!')
                return

            response = Response(interaction)
            generator_or_coroutine = autocomplete_fn(build_context(interaction, response=response))

            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    yield generator_response

            else:
                await generator_or_coroutine


async def handle_component(interaction: hikari.ComponentInteraction, response: Response):
    """Handle a component interaction."""
    custom_id = interaction.custom_id

    # iterate through commands and find the custom_id mapped function
    for command in slash_commands.values():
        # find matching custom_id handler
        for accepted_custom_id, custom_id_fn in command.accepted_custom_ids.items():
            if custom_id.startswith(accepted_custom_id):
                generator_or_coroutine = custom_id_fn(build_context(interaction, response=response))

                if hasattr(generator_or_coroutine, "__anext__"):
                    async for generator_response in generator_or_coroutine:
                        yield generator_response

                else:
                    await generator_or_coroutine

                return

        # find matching prompt handler
        for command_prompt in command.prompts:
            parsed_custom_id = parse_custom_id(PromptCustomID, custom_id)

            if (
                parsed_custom_id.command_name == command.name
                and parsed_custom_id.prompt_name == command_prompt.__name__
            ):
                new_prompt = command_prompt(command.name, response)
                new_prompt.insert_pages(command_prompt)

                await new_prompt.save_data(interaction)

                async for generator_response in new_prompt.handle(interaction):
                    yield generator_response

                return


def new_command(command: Any, **kwargs):
    """Registers a command with Bloxlink.

    This is only used for the wrapper function in resources.bloxlink on the bot object. Commands should not
    be added using this method directly.

    Args:
        command (Any): The command to register locally. (Presumably callable)
    """
    new_command_class = command()

    command_name = command_name_pattern.search(command.__name__).group(1).lower()
    command_fn = getattr(new_command_class, "__main__", None)  # None if it has sub commands
    subcommands: dict[str, Callable] = {}
    rest_subcommands: list[hikari.CommandOption] = []

    for attr_name in dir(new_command_class):
        attr = getattr(new_command_class, attr_name)

        if hasattr(attr, "__issubcommand__"):
            rest_subcommands.append(
                hikari.CommandOption(
                    type=hikari.OptionType.SUB_COMMAND,
                    name=attr.__name__,
                    description=attr.__doc__,
                    options=attr.__subcommandattrs__.get("options"),
                )
            )
            subcommands[attr_name] = attr

    command_attrs = {
        "name": command_name,
        "fn": command_fn,
        "category": kwargs.get("category", "Miscellaneous"),
        "permissions": kwargs.get("permissions", None),
        "defer": kwargs.get("defer", False),
        "defer_with_ephemeral": kwargs.get("defer_with_ephemeral", False),
        "description": new_command_class.__doc__,
        "options": kwargs.get("options"),
        "subcommands": subcommands,
        "rest_subcommands": rest_subcommands,
        "accepted_custom_ids": kwargs.get("accepted_custom_ids"),
        "autocomplete_handlers": kwargs.get("autocomplete_handlers"),
        "dm_enabled": kwargs.get("dm_enabled"),
        "prompts": kwargs.get("prompts"),
    }

    new_command = Command(**command_attrs)
    slash_commands[command_name] = new_command

    for alias in kwargs.get("aliases", []):
        command_attrs["name"] = alias
        new_alias_command = Command(**command_attrs)
        slash_commands[alias] = new_alias_command

        logging.info(f"Registered command alias {alias} of {command_name}")

    logging.info(f"Registered command {command_name}")


async def sync_commands(bot: hikari.RESTBot):
    """Publish our slash commands to Discord.

    Args:
        bot (hikari.RESTBot): The bot object to publish slash commands for.
    """
    commands = []

    for new_command_data in slash_commands.values():
        command: hikari.commands.SlashCommandBuilder = bot.rest.slash_command_builder(
            new_command_data.name, new_command_data.description
        )

        if new_command_data.rest_subcommands:
            for sucommand in new_command_data.rest_subcommands:
                command.add_option(sucommand)

        if new_command_data.permissions:
            command.set_default_member_permissions(new_command_data.permissions)

        if new_command_data.options:
            for option in new_command_data.options:
                command.add_option(option)

        if new_command_data.dm_enabled is not None:
            command.set_is_dm_enabled(new_command_data.dm_enabled)

        commands.append(command)

    await bot.rest.set_application_commands(
        application=DISCORD_APPLICATION_ID,
        commands=commands,
    )

    logging.info(f"Registered {len(slash_commands)} slash commands.")


def build_context(
    interaction: hikari.CommandInteraction | hikari.ComponentInteraction | hikari.AutocompleteInteraction,
    response: Response = None,
    command: Command = None,
    options=None,
) -> CommandContext:
    """Build a CommandContext from an interaction.

    Args:
        interaction (hikari.CommandInteraction | hikari.ComponentInteraction | hikari.AutocompleteInteraction): The interaction to build a context for.
        response (Response, optional): The response object for this interaction. Defaults to None. It will be created if not provided.
        command (Command, optional): The command that this interaction is for. Defaults to None. This is only useful for handlers to know the current command name.
        options (dict, optional): The options/arguments passed by the user to this command. Defaults to None. This is only useful to provide for subcommands.
    Returns:
        CommandContext: The built context.
    """
    return CommandContext(
        command_name=(
            command.name or interaction.command_name if hasattr(interaction, "command_name") else None
        ),
        command_id=interaction.command_id if hasattr(interaction, "command_id") else None,
        guild_id=interaction.guild_id,
        member=interaction.member,
        user=interaction.user,
        resolved=interaction.resolved if hasattr(interaction, "resolved") else None,
        options=(
            options or {o.name: o.value for o in interaction.options}
            if getattr(interaction, "options", None)
            else None
        ),
        interaction=interaction,
        response=response or Response(interaction),
    )
