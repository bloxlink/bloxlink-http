from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Unpack

import hikari
from bloxlink_lib import (
    VALID_BIND_TYPES,
    BaseModel,
    BindCriteriaDict,
    GuildBind,
    GuildSerializable,
    MemberSerializable,
    SnowflakeSet,
    StatusCodes,
    count_binds,
    create_entity,
    fetch_typed,
    get_binds,
    parse_template,
)
from bloxlink_lib.database import fetch_guild_data, fetch_user_data, update_guild_data, update_user_data
from pydantic import Field

from config import CONFIG
from resources import restriction
from resources.api.roblox import users
from resources.bloxlink import instance as bloxlink
from resources.constants import LIMITS, ORANGE_COLOR
from resources.exceptions import (
    BindConflictError,
    BindException,
    BloxlinkForbidden,
    Message,
    PremiumRequired,
    RobloxNotFound,
)
from resources.premium import get_premium_status
from resources.ui.components import Button, Component
from resources.ui.embeds import InteractiveMessage

if TYPE_CHECKING:
    from resources.response import Response


# Set to True to remove the old bind fields from the database (groupIDs and roleBinds)
POP_OLD_BINDS: bool = False


class UpdateEndpointResponse(BaseModel):
    """The payload that is sent from the bind API when updating a user's roles and nickname."""

    nickname: str | None

    add_roles: list[int] = Field(alias="addRoles")
    remove_roles: list[int] = Field(alias="removeRoles")
    missing_roles: list[str] = Field(alias="missingRoles")


async def create_bind(
    guild_id: int | str,
    bind_type: VALID_BIND_TYPES,
    bind_id: int,
    *,
    roles: list[str] = None,
    remove_roles: list[str] = None,
    nickname: str = None,
    dynamic_roles: bool = False,
    **criteria_data: Unpack[BindCriteriaDict],
):
    """Creates a new guild bind. If it already exists, the roles will be appended to the existing entry.

    Upon bind creation role IDs are checked to ensure that the roles being given by the binding are valid
    IDs.

    Args:
        guild_id (int | str): The ID of the guild.
        bind_type (ValidBindType): The type of bind being created.
        bind_id (int): The ID of the entity this bind is for.
        roles (list[str], optional): Role IDs to be given to users for this bind. Defaults to None.
        remove_roles (list[str], optional): Role IDs to be removed from users for this bind. Defaults to None.
        dynamic_roles (bool, optional): Whether the entire group is linked. Defaults to False.
        nickname (str, optional): The nickname template for this bind. Defaults to None.

    Raises:
        BindConflictError: When a duplicate binding is found in the database,
        BindException: _description_
        BindException: _description_
    """

    bind_count = await count_binds(guild_id)
    roles = roles or []
    remove_roles = remove_roles or []

    if dynamic_roles:
        if bind_type == "group":
            criteria_data["group"] = criteria_data.get("group", {})
            criteria_data["group"]["dynamicRoles"] = True
        else:
            raise NotImplementedError("Dynamic roles are currently only supported for group binds.")

    if bind_count >= LIMITS["BINDS"]["FREE"]:
        premium_status = await get_premium_status(guild_id=guild_id)

        if bind_count >= LIMITS["BINDS"]["MAX"]:
            raise BindException("You have reached the maximum number of binds for this server.")

        if (bind_count >= LIMITS["BINDS"]["FREE"] and not premium_status.active) or (
            bind_count >= LIMITS["BINDS"]["PREMIUM"] and premium_status.active and premium_status.tier != "pro"  # fmt: skip
        ):
            raise PremiumRequired()

    guild_binds = await get_binds(str(guild_id))

    new_bind = GuildBind(
        roles=roles,
        removeRoles=remove_roles,
        nickname=nickname,
        criteria={
            "type": bind_type,
            "id": bind_id,
            **criteria_data,
        },
    )

    # Check to see if there is a binding in place matching the given input
    existing_binds: list[GuildBind] = []

    for bind in guild_binds:
        if bind == new_bind:
            existing_binds.append(bind)

    if not existing_binds:
        guild_binds.append(new_bind)

        await update_guild_data(
            guild_id, binds=[b.model_dump(exclude_unset=True, by_alias=True) for b in guild_binds]
        )

        return

    # merge the bind data
    if bind_id:
        # group, badge, gamepass, and asset binds
        if len(existing_binds) > 1:
            # invalid bind. binds with IDs should only have one entry in the db.
            raise BindConflictError(
                "Binds with IDs should only have one entry. More than one duplicate was found."
            )

        if roles:
            # Remove invalid guild roles
            guild_roles = set((await bloxlink.fetch_roles(guild_id)).keys())
            existing_roles = set(existing_binds[0].roles + roles)

            # Moves binding to the end of the array, if we wanted order to stay could get the
            # index, then remove, then insert again at that index.
            guild_binds.remove(existing_binds[0])

            existing_binds[0].roles = list(guild_roles & existing_roles)
            guild_binds.append(existing_binds[0])

        if remove_roles:
            # Override roles to remove rather than append.
            guild_binds.remove(existing_binds[0])

            existing_binds[0].remove_roles = remove_roles
            guild_binds.append(existing_binds[0])

        await update_guild_data(
            guild_id, binds=[b.model_dump(exclude_unset=True, by_alias=True) for b in guild_binds]
        )

    else:
        # everything else (verified/unverified binds)
        raise NotImplementedError("This bind type is not yet supported.")


async def delete_bind(
    guild_id: int | str,
    *binds: tuple[GuildBind],
):
    """Remove a bind from the database.

    This works through performing a $pull from the binds array in the database.
    Alternatively you could update the entire binds array to have everything except the binding(s) being
    removed.

    Args:
        guild_id (int | str): The ID of the guild.
        bind_type (ValidBindType): The type of binding that is being removed.
        bind_id (int): The ID of the entity that this bind is for.
    """

    guild_binds = await get_binds(str(guild_id))

    for bind in binds:
        guild_binds.remove(bind)

    await update_guild_data(
        guild_id, binds=[b.model_dump(exclude_unset=True, by_alias=True) for b in guild_binds]
    )


async def calculate_bound_roles(
    guild: hikari.RESTGuild,
    member: hikari.Member | MemberSerializable,
    roblox_user: users.RobloxAccount = None,
) -> UpdateEndpointResponse:
    # Get user roles + nickname
    update_data, update_data_response = await fetch_typed(
        UpdateEndpointResponse,
        f"{CONFIG.BOT_API}/binds/{guild.id}/{member.id}",
        method="POST",
        headers={"Authorization": CONFIG.BOT_API},
        body={
            "guild_roles": GuildSerializable.from_hikari(guild).model_dump(by_alias=True)["roles"],
            "guild_name": guild.name,
            "member": MemberSerializable.from_hikari(member).model_dump(by_alias=True),
            "roblox_user": roblox_user.model_dump(by_alias=True) if roblox_user else None,
        },
    )

    if update_data_response.status != StatusCodes.OK:
        raise Message("Something went wrong internally when trying to update this user!")

    return update_data


async def apply_binds(
    member: hikari.Member | MemberSerializable,
    guild_id: hikari.Snowflake,
    roblox_account: users.RobloxAccount = None,
    *,
    moderate_user: bool = False,
    update_embed_for_unverified: bool = False,
    mention_roles: bool = True,
) -> InteractiveMessage:
    """Apply bindings to a user, (apply the Verified & Unverified roles, nickname template, and custom bindings).

    Args:
        member (hikari.Member | dict): Information of the member being updated.
            For dicts, the valid keys are as follows:
            "role_ids", "id", "username" (or "name"), "nickname", "avatar_url"
        guild_id (hikari.Snowflake): The ID of the guild where the user is being updated.
        roblox_account (users.RobloxAccount, optional): The linked account of the user if one exists. May
            or may not be their primary account, could be a guild-specific link. Defaults to None.
        moderate_user (bool, optional): Check if any restrictions (age limit, group lock,
            ban evasion, alt detection) apply to this user. Defaults to False.
        update_embed_for_unverified (bool, optional): Should the embed be updated to show the roles added/removed
            for unverified users? Defaults to False.
        mention_roles (bool, optional): Whether the roles be mentioned in the embed. Otherwise, shows role names. Defaults to True.

    Raises:
        Message: Raised if there was an issue getting a server's bindings.
        RuntimeError: Raised if the nickname endpoint on the bot API encountered an issue.
        BloxlinkForbidden: Raised when Bloxlink does not have permissions to give roles to a user.

    Returns:
        InteractiveMessage: The embed that will be shown to the user, may or may not include the components that
            will be shown, depending on if the user is restricted or not.
    """

    if member.is_bot:
        return InteractiveMessage(embed_description=("Sorry, bots cannot be updated."))

    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)
    guild_roles = guild.roles
    guild_data = await fetch_guild_data(guild_id, "verifiedDM")

    embed = hikari.Embed()
    components: list[Component] = []
    warnings: list[str] = []

    add_roles = SnowflakeSet(type="role", str_reference=guild_roles if not mention_roles else None)
    remove_roles = SnowflakeSet(type="role", str_reference=guild_roles if not mention_roles else None)
    nickname: str = None

    removed_user = False

    # Check restrictions
    restriction_check = restriction.Restriction(
        member=member,
        guild_id=guild_id,
        roblox_user=roblox_account,
        guild_name=guild.name,
    )
    await restriction_check.sync()

    if restriction_check.restricted:
        # Don't tell the user which account they're evading with.
        if restriction_check.source == "banEvader":
            warnings.append(
                f"({restriction_check.source}): User is evading a ban from a previous Discord account."
            )
        else:
            warnings.append(f"({restriction_check.source}): {restriction_check.reason}")

        # Remove the user if we're moderating.
        if moderate_user:
            try:
                await restriction_check.moderate()
            except (hikari.ForbiddenError, hikari.NotFoundError):
                warnings.append("User could not be removed from the server.")
            else:
                warnings.append("User was removed from the server.")
                removed_user = True

        # User won't see the response. Stop early. Bot tries to DM them before they are removed.
        if removed_user:
            return InteractiveMessage(
                embed_description=(
                    "User was removed from this server as per this server's settings.\n"
                    "> *Admins, confused? Check the Discord audit log for the reason why this user was removed from the server.*"
                )
            )

        return InteractiveMessage(
            embed_description=(
                "Sorry, you are restricted from verifying in this server. Server admins: please run `/restriction view` to learn why."
            )
        )

    update_payload = await calculate_bound_roles(guild=guild, member=member, roblox_user=roblox_account)

    add_roles.update(update_payload.add_roles)
    remove_roles.update(update_payload.remove_roles)
    nickname = update_payload.nickname

    if update_payload.missing_roles:
        for role_name in update_payload.missing_roles:
            try:
                new_role: hikari.Role = await bloxlink.rest.create_role(
                    guild_id, name=role_name, reason="Creating missing role"
                )
                add_roles.add(new_role.id)
                guild_roles[new_role.id] = new_role  # so str_reference can be updated

            except hikari.ForbiddenError:
                return InteractiveMessage(
                    embed_description=("I don't have permission to create roles on this server.")
                )

    # Apply roles and nickname to the user
    # We do roles and nickname separately so if the nickname fails, the roles still apply.
    # (It would take more HTTP requests to fetch the top roles of both the user and the bot)
    if add_roles or remove_roles:
        try:
            await bloxlink.edit_user(
                member=member, guild_id=guild_id, add_roles=add_roles, remove_roles=remove_roles
            )
        except hikari.ForbiddenError:
            raise BloxlinkForbidden("I don't have permission to add roles to this user.") from None

    if nickname and guild.owner_id != member.id:
        try:
            await bloxlink.edit_user(member=member, guild_id=guild_id, nickname=nickname)
        except hikari.ForbiddenError:
            warnings.append("I don't have permission to change this user's nickname.")

    # Build response embed
    if roblox_account or update_embed_for_unverified or CONFIG.BOT_RELEASE == "LOCAL":
        if add_roles or remove_roles or warnings or nickname:
            embed.title = "Member Updated"
        else:
            embed.title = "Member Unchanged"

        embed.set_author(
            name=member.username,
            icon=member.avatar_url or None,
            url=roblox_account.profile_link if roblox_account else None,
        )

        if add_roles:
            embed.add_field(
                name="Added Roles",
                value=str(add_roles),
                inline=True,
            )

        if remove_roles:
            embed.add_field(
                name="Removed Roles",
                value=str(remove_roles),
                inline=True,
            )

        if nickname:
            embed.add_field(name="Nickname", value=nickname, inline=True)

        if warnings:
            embed.add_field(name=f"Warning{'s' if len(warnings) >= 2 else ''}", value="\n".join(warnings))

    else:
        # Default msg for unverified users.
        components = [
            Button(
                label="Verify with Bloxlink",
                url=await users.get_verification_link(
                    user_id=member.id,
                    guild_id=guild_id,
                ),
            ),
            Button(
                label="Stuck? See a Tutorial",
                url="https://www.youtube.com/watch?v=SbDltmom1R8&list=PLz7SOP-guESE1V6ywCCLc1IQWiLURSvBE&index=1&ab_channel=Bloxlink",
            ),
        ]

    return InteractiveMessage(
        content="To verify with Bloxlink, click the link below."
        if not roblox_account
        else await parse_template(
            guild_id=guild_id,
            guild_name=guild.name,
            member=member,
            roblox_user=roblox_account,
            template=guild_data.verifiedDM,
            max_length=False,
        ),
        embed=embed,
        action_rows=components,
    )


async def confirm_account(
    member: hikari.Member,
    guild_id: hikari.Snowflake,
    response: Response,
    roblox_account: users.RobloxAccount | None,
):
    """Send a request for the user to confirm their account"""

    if CONFIG.BOT_RELEASE in ("LOCAL", "CANARY"):
        return

    if roblox_account:
        premium_status = await get_premium_status(guild_id=guild_id)

        roblox_accounts = (await fetch_user_data(member.id, "robloxAccounts")).robloxAccounts
        user_confirms = roblox_accounts.get("confirms", {})

        if not premium_status.active and str(guild_id) not in user_confirms:
            user_confirms[str(guild_id)] = roblox_account.id
            roblox_accounts["confirms"] = user_confirms
            await update_user_data(member.id, robloxAccounts=roblox_accounts)

            embed = hikari.Embed(
                title="Select Account",
                description="Please click the link below to select an account for this server.",
                color=ORANGE_COLOR,
            )

            message = await response.send(
                embed=embed,
                components=[
                    Button(label="Select Account", url=f"https://blox.link/confirm/v2/{guild_id}"),
                ],
                ephemeral=True,
                fetch_message=True,
            )

            try:
                await bloxlink.relay(
                    f"account_confirm:{guild_id}:{roblox_account.id}", None, timedelta(minutes=2).seconds
                )
            except (TimeoutError, RuntimeError):
                pass

            try:
                await message.delete()
            except (hikari.ForbiddenError, hikari.NotFoundError):
                pass


async def generate_binds_embed(items: list[GuildBind], embed: hikari.Embed):
    """Syncs the entities of the given binds and adds them to the embed."""

    bind_list: dict[str, list[str]] = {}

    for bind in items:
        await bind.entity.sync()

        bind_entity = str(bind.entity)

        if bind_entity not in bind_list:
            bind_list[bind_entity] = []

        bind_list[bind_entity].append(str(bind))

    for bind_entity, bind_strings in bind_list.items():
        embed.add_field(name=bind_entity, value="\n".join(bind_strings))
