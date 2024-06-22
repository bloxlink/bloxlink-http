from __future__ import annotations

from datetime import timedelta

from bloxlink_lib import RobloxUser, get_user, fetch, StatusCodes
from bloxlink_lib.database import fetch_guild_data, redis
import hikari

from resources.constants import VERIFY_URL, VERIFY_URL_GUILD
from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.premium import get_premium_status


async def get_user_from_string(target: str) -> RobloxUser:
    """Get a RobloxAccount from a given target string (either an ID or username)

    Args:
        target (str): Roblox ID or username of the account to sync.

    Raises:
        RobloxNotFound: When no user is found.
        *Other exceptions may be raised such as RobloxAPIError from get_user*

    Returns:
        RobloxAccount: The synced RobloxAccount of the user requested.
    """

    account = None

    if target.isdigit():
        try:
            account = await get_user(roblox_id=target)
        except (RobloxNotFound, RobloxAPIError):
            pass

    # Fallback to parse input as a username if the input was not a valid id.
    if not account:
        account = await get_user(roblox_username=target)

    return account


async def format_embed(roblox_account: RobloxUser, user: hikari.User = None, guild_id: int = None) -> list[hikari.Embed]:
    """Create an embed displaying information about a user.

    Args:
        roblox_account (RobloxAccount): The user to display information for.
        user (hikari.User, optional): Discord user for this roblox account. Defaults to None.

    Returns:
        hikari.Embed: Embed with information about a roblox account.
    """

    await roblox_account.sync()

    embeds: list[hikari.Embed] = []

    embed = hikari.Embed(
        title=str(user) if user else roblox_account.display_name,
        url=roblox_account.profile_link,
    )
    embeds.append(embed)

    embed.add_field(name="Username", value=f"@{roblox_account.username}", inline=True)
    embed.add_field(name="ID", value=str(roblox_account.id), inline=True)
    embed.add_field(
        name="Description",
        value=roblox_account.description[:500] if roblox_account.description else "None provided",
        inline=False,
    )

    if roblox_account.avatar:
        embed.set_thumbnail(roblox_account.avatar_url)

    if guild_id:
        guild_data = await fetch_guild_data(guild_id, "webhooks")
        webhooks = guild_data.webhooks

        if webhooks and webhooks.userInfo:
            userinfo_webhook = webhooks.userInfo

            json_response, response = await fetch(
                "POST",
                userinfo_webhook.url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": webhooks.authentication
                },
                body={
                    userinfo_webhook.fieldMapping.discordID: user.id if user else None,
                    userinfo_webhook.fieldMapping.robloxID: roblox_account.id,
                    userinfo_webhook.fieldMapping.guildID: guild_id,
                    userinfo_webhook.fieldMapping.robloxUsername: roblox_account.username,
                    userinfo_webhook.fieldMapping.discordUsername: user.username if user else None,
                },
                raise_on_failure=False
            )

            if response.status == StatusCodes.OK and json_response.get("fields"):
                custom_embed = hikari.Embed(
                    title=json_response.get("title"),
                    url=json_response.get("titleURL"),
                    color=json_response.get("color") or "#f1e970",
                    description=json_response.get("description")
                )

                custom_embed.set_author(name=roblox_account.username, icon=roblox_account.avatar_url)
                custom_embed.set_footer(text="The information above is not endorsed by Bloxlink.")

                if json_response.get("bannerImage"):
                    custom_embed.set_image(json_response["bannerImage"])

                if json_response.get("thumbnailImage"):
                    custom_embed.set_thumbnail(json_response["thumbnailImage"])

                for field in json_response.get("fields", []):
                    if isinstance(field, dict) and "name" in field and "value" in field:
                        custom_embed.add_field(name=field["name"], value=str(field["value"]), inline=field.get("inline", False))

                if 0 < custom_embed.total_length() <= 2500:
                    embeds.append(custom_embed)

    return embeds


async def get_verification_link(
    user_id: int | str, guild_id: int | str = None, interaction: hikari.ComponentInteraction = None
) -> str:
    """Get the verification link for a user. The link is different depending the server has premium or not.

    Args:
        user_id (int | str): The user to get the verification link for.
        guild_id (int | str, optional): The guild ID to get the verification link for. Defaults to None.
        interaction (hikari.ComponentInteraction, optional): The interaction to check for premium status. Defaults to None.

    Returns:
        str: The verification link for the user.
    """

    if guild_id:
        guild_id = str(guild_id)
        premium_status = await get_premium_status(guild_id=guild_id, interaction=interaction)

        if premium_status.active:
            return VERIFY_URL_GUILD.format(guild_id=guild_id)

    return VERIFY_URL
