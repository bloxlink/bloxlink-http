from typing import Literal

import hikari
from bloxlink_lib import get_badge, get_catalog_asset, get_gamepass, get_group
from hikari.commands import CommandOption, OptionType

from commands.bind.prompts.generic_bind import GenericBindPrompt
from commands.bind.prompts.group import GroupPrompt, GroupRolesConfirmationPrompt
from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxNotFound


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
                description="What is your catalog asset ID?",
                is_required=True,
            )
        ]
    )
    async def asset(self, ctx: CommandContext):
        """Bind a catalog asset to your server"""

        await self._handle_command(ctx, "asset")

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
        cmd_type: Literal["group", "asset", "badge", "gamepass"],
    ):
        """
        Handle initial command input and response.

        It is primarily intended to be used for the asset, badge, and gamepass types.
        The group command is handled by itself in its respective command method.
        """
        match cmd_type:
            case "asset" | "badge" | "gamepass":
                input_id = ctx.options[f"{cmd_type}_id"]

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
                        "entity_type": cmd_type,
                    },
                )
