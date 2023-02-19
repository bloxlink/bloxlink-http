from __future__ import annotations
import re
import logging
import hikari
from .models import CommandContext
from .response import Response
from .diagnostics import report_error
from .exceptions import *
from config import DISCORD_APPLICATION_ID
from typing import Any, Callable


command_name_pattern = re.compile("(.+)Command")

slash_commands = {}


async def handle_command(interaction:hikari.CommandInteraction):
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
        subcommand_option: list[hikari.CommandInteractionOption] = list(filter(lambda o: o.type==hikari.OptionType.SUB_COMMAND, interaction.options or []))
        subcommand_name = subcommand_option[0].name if subcommand_option else None

    else:
        raise NotImplementedError()

    # get options
    if interaction.options:
        for option in interaction.options:
            if option.name == subcommand_name:
                command_options = {
                    o.name:o.value for o in option.options
                }
                break
        else:
            command_options = {
                o.name:o.value for o in interaction.options
            }


    response = Response(interaction)

    if command.defer:
        response.responded = True
        yield interaction.build_deferred_response()

    ctx = CommandContext(
        command_name=interaction.command_name,
        command_id=interaction.command_id,
        guild_id=interaction.guild_id,
        member=interaction.member,
        user=interaction.user,
        response=response,
        resolved=interaction.resolved,
        options=command_options
    )

    await try_command(command.execute(ctx, subcommand_name=subcommand_name), response)


async def handle_component(interaction: hikari.ComponentInteraction):
    custom_id = interaction.custom_id

    # iterate through commands and find the custom_id mapped function
    for command in slash_commands.values():
        for accepted_custom_id, custom_id_fn in command.accepted_custom_ids.items():
            if custom_id.startswith(accepted_custom_id):
                return await custom_id_fn(interaction)


def new_command(command: Any, **kwargs):
    new_command_class = command()

    command_name = command_name_pattern.search(command.__name__).group(1).lower()
    command_fn = getattr(new_command_class, "__main__", None) # None if it has sub commands
    subcommands: dict[str, Callable] = {}
    rest_subcommands: list[hikari.CommandOption] = []

    for attr_name in dir(new_command_class):
        attr = getattr(new_command_class, attr_name)

        if hasattr(attr, "__issubcommand__"):
            rest_subcommands.append(
                hikari.CommandOption(type=hikari.OptionType.SUB_COMMAND,
                                     name=attr.__name__,
                                     description=attr.__doc__,
                                     options=attr.__subcommandattrs__.get("options"))
            )
            subcommands[attr_name] = attr

    new_command = Command(command_name,
                          command_fn,
                          kwargs.get("category", "Miscellaneous"),
                          kwargs.get("permissions", None),
                          kwargs.get("defer", False),
                          new_command_class.__doc__,
                          kwargs.get("options"),
                          subcommands,
                          rest_subcommands,
                          kwargs.get("accepted_custom_ids"))

    slash_commands[command_name] = new_command

    logging.info(f"Registered command {command_name}")


async def sync_commands(bot: hikari.RESTBot):
    from resources.bloxlink import instance as bloxlink

    commands = []

    for new_command_data in slash_commands.values():
        command: hikari.commands.SlashCommandBuilder = bloxlink.rest.slash_command_builder(
            new_command_data.name, new_command_data.description)

        if new_command_data.rest_subcommands:
            for sucommand in new_command_data.rest_subcommands:
                command.add_option(sucommand)

        if new_command_data.permissions:
            command.set_default_member_permissions(new_command_data.permissions)

        if new_command_data.options:
            for option in new_command_data.options:
                command.add_option(option)

        commands.append(command)


    await bloxlink.rest.set_application_commands(
        application=DISCORD_APPLICATION_ID,
        commands=commands,
    )

    logging.info(f"Registered {len(slash_commands)} slash commands.")


async def try_command(fn: Callable, response: Response):
    try:
        await fn
    except UserNotVerified as message:
        await response.send(str(message) or "This user is not verified with Bloxlink!")
    except (BloxlinkForbidden, hikari.errors.ForbiddenError) as message:
        await response.send(str(message) or "I have encountered a permission error! Please make sure I have the appropriate permissions.")
    except RobloxNotFound as message:
        await response.send(str(message) or "This Roblox entity does not exist! Please check the ID and try again.")
    except RobloxDown:
        await response.send("Roblox appears to be down, so I was unable to process your command. "
                            "Please try again in a few minutes.")
    except Exception as ex:
        await response.edit_or_send("An error seems to have occurred, we have reported it!")
        # await report_error(ex, "...error details")

class Command:
    def __init__(
            self,
            command_name: str,
            fn: Callable=None, # None if it has sub commands
            category: str="Miscellaneous",
            permissions=None,
            defer: bool=False,
            description: str=None,
            options: list[hikari.commands.CommandOptions]=None,
            subcommands: dict[str, Callable]=None,
            rest_subcommands: list[hikari.CommandOption]=None,
            accepted_custom_ids: list[str] = None
        ):
        self.name = command_name
        self.fn = fn
        self.category = category
        self.permissions = permissions
        self.defer = defer
        self.description = description
        self.options = options
        self.subcommands = subcommands
        self.rest_subcommands = rest_subcommands
        self.accepted_custom_ids = accepted_custom_ids or {}

    async def execute(self, ctx: CommandContext, subcommand_name: str=None):
        # TODO: check for permissions

        if subcommand_name:
            await self.subcommands[subcommand_name](ctx)
        else:
            await self.fn(ctx)
