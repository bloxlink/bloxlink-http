import json
from datetime import datetime, timedelta

import hikari

from bloxlink_lib import BaseModel, parse_into
from bloxlink_lib.database import redis

from resources.bloxlink import instance as bloxlink
from resources.exceptions import Message
from resources.commands import CommandContext, GenericCommand
from resources.ui.components import Button, CommandCustomID, component_author_validation
from resources.ui import ProgressBar

CHUNK_LIMIT = 100


class Response(BaseModel):
    """Response from the verifyall endpoint"""

    success: bool
    nonce: str = None

class ProgressCustomID(CommandCustomID):
    """Custom ID for the progress button"""

    nonce: str

class VerifyAllProgress(BaseModel):
    """Progress of the verifyall scan"""

    started_at: datetime
    ended_at: datetime | None = None
    members_processed: int
    total_members: int
    current_chunk: int
    total_chunks: int



@component_author_validation(parse_into=ProgressCustomID, defer=False)
async def get_progress(ctx: CommandContext, custom_id: ProgressCustomID):
    """Get the progress of the verifyall scan"""

    nonce = custom_id.nonce
    progress: dict | None = json.loads(await redis.get(f"progress:{nonce}")) if await redis.exists(f"progress:{nonce}") else None

    response = ctx.response
    message = ctx.interaction.message

    if not progress:
        await response.send("Could not fetch progress. Perhaps it's been too long since you used this command.", ephemeral=True)
        return

    parsed_progress = parse_into(progress, VerifyAllProgress)

    fields = [
        f"Started: <t:{int(parsed_progress.started_at.timestamp())}:R>",
        f"Members processed: {parsed_progress.members_processed}/{parsed_progress.total_members}",
        f"Chunks processed: {parsed_progress.current_chunk}/{parsed_progress.total_chunks}",
        "Progress: " + str(ProgressBar(progress=parsed_progress.current_chunk, total=parsed_progress.total_chunks))
    ]

    if parsed_progress.ended_at:
        fields.insert(1, f"Ended: <t:{int(parsed_progress.ended_at.timestamp())}:R>")

    embed = hikari.Embed(
        title="Progress Update" if not parsed_progress.ended_at else "Scan Complete",
        description="\n".join(fields),
    )
    embed.set_footer(text="Progress bar is updated at every chunk completed")

    if parsed_progress.ended_at:
        for action_row in message.components:
            for component in action_row.components:
                component.is_disabled = True

    if message.embeds[0] != embed:
        await response.edit_message(embed=embed, components=message.components)

    await response.send("Progress updated!", ephemeral=True)

@component_author_validation(parse_into=ProgressCustomID, defer=False)
async def cancel_progress(ctx: CommandContext, custom_id: ProgressCustomID):
    """Cancel the verifyall scan."""

    nonce = custom_id.nonce
    progress: dict | None = json.loads(await redis.get(f"progress:{nonce}")) if await redis.exists(f"progress:{nonce}") else None

    response = ctx.response
    message = ctx.interaction.message

    if not progress:
        await response.send("Could not fetch progress. Perhaps it's been too long since you used this command.", ephemeral=True)
        return

    await redis.set(f"progress:{nonce}:cancelled", "1", expire=timedelta(days=2))

    parsed_progress = parse_into(progress, VerifyAllProgress)

    fields = [
        f"Started: <t:{int(parsed_progress.started_at.timestamp())}:R>",
        f"Ended: <t:{int(datetime.now().timestamp())}:R>",
        f"Members processed: {parsed_progress.members_processed}/{parsed_progress.total_members}",
        f"Chunks processed: {parsed_progress.current_chunk}/{parsed_progress.total_chunks}",
        "Progress: " + str(ProgressBar(progress=parsed_progress.current_chunk, total=parsed_progress.total_chunks))
    ]

    embed = hikari.Embed(
        title="Scan Complete (Cancelled)",
        description="\n".join(fields),
    )

    for action_row in message.components:
        for component in action_row.components:
            component.is_disabled = True

    if message.embeds[0] != embed:
        await response.edit_message(embed=embed, components=message.components)

    await response.send("Successfully cancelled the scan.", ephemeral=True)




@bloxlink.command(
    category="Premium",
    premium=True,
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD | hikari.Permissions.MANAGE_ROLES,
    accepted_custom_ids={
        "verifyall:verifyall_progress_button": get_progress,
        "verifyall:verifyall_cancel_button": cancel_progress
    },
    cooldown=timedelta(days=1),
    cooldown_key="cooldown:{guild_id}",
)
class VerifyallCommand(GenericCommand):
    """Update everyone in your server"""

    async def __main__(self, ctx: CommandContext):
        """
        Sets up a scan to update everyone in a guild.

        Makes a request to the gateway over redis to chunk the guild members.
        The gateway then will sent a request to the update endpoint (endpoints/update_user.py)
        where the users will then be handled to be updated.
        """

        guild_id = ctx.interaction.guild_id
        response = ctx.response

        progress_responses = await bloxlink.relay(
            "VERIFYALL",
            model=Response,
            payload={
                "guild_id": guild_id,
                "channel_id": ctx.interaction.channel_id,
                "chunk_limit": CHUNK_LIMIT,
            },
            timeout=10,
            wait_for_all=False,
        )

        progress_response = progress_responses[0] if progress_responses else None

        if not progress_response:
            raise Message(
                "There was an issue when trying to update all your server members. Try again later."
            )

        embed = hikari.Embed(
            title="Now Updating Everyone...",
            description="Your server members will be updated shortly!\nPlease feel free to press the Progress button for the latest progress.",
        )

        components = [
            Button(
                label="Progress",
                custom_id=str(ProgressCustomID(
                    nonce=progress_response.nonce,
                    command_name="verifyall",
                    user_id=ctx.user.id,
                    section="verifyall_progress_button")
                ),
            ),
            Button(
                label="Stop Scan",
                custom_id=str(ProgressCustomID(
                    nonce=progress_response.nonce,
                    command_name="verifyall",
                    user_id=ctx.user.id,
                    section="verifyall_cancel_button")
                ),
                style=Button.ButtonStyle.DANGER
            )
        ]

        await response.send(embed=embed, components=components)
