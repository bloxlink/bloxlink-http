import hikari
from hikari.commands import CommandOption, OptionType

from bloxlink_lib import RobloxUser, reverse_lookup
from resources.api.roblox import users
from resources.ui.autocomplete import roblox_user_lookup_autocomplete
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxNotFound


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    options=[
        CommandOption(
            type=OptionType.STRING,
            name="user",
            description="Please specify either a Roblox username or ID to search for.",
            is_required=True,
            autocomplete=True,
        ),
    ],
    autocomplete_handlers={
        "user": roblox_user_lookup_autocomplete,
    },
)
class ReverseSearchCommand(GenericCommand):
    """Find Discord users in your server that are linked to a certain Roblox account."""

    async def __main__(self, ctx: CommandContext):
        guild = ctx.guild_id
        target = ctx.options["user"]

        results: list[str] = []
        account: RobloxUser = None
        discord_ids: list[int] = []

        if target == "no_user":
            raise RobloxNotFound("The Roblox user you were searching for does not exist.")

        account = await users.get_user_from_string(target)

        if not account:
            raise RobloxNotFound("The Roblox user you were searching for does not exist.")

        discord_ids = await reverse_lookup(account.id)

        for discord_id in discord_ids:
            user = await bloxlink.fetch_discord_member(guild, discord_id, "id")

            if not user:
                continue

            if isinstance(user, hikari.Member):
                results.append(f"{user.mention} ({user.id})")

            elif isinstance(user, dict):
                user_id = user["data"]["id"]
                results.append(f"<@{user_id}> ({user_id})")

        embed = hikari.Embed(
            title=f"Reverse Search for {account.username}",
            description="\n".join(results) if results else "No results found.",
        )
        if account.avatar_url:
            embed.set_thumbnail(account.avatar_url)

        await ctx.response.send(embed=embed)
