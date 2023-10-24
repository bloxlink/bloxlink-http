import logging
from attrs import define
from typing import Literal

import hikari

import resources.prompts as prompts
import resources.roblox.users as users
from resources.bloxlink import UserData
from resources.bloxlink import instance as bloxlink
from resources.constants import RED_COLOR
from resources.exceptions import UserNotVerified
from resources.roblox.groups import RobloxGroup
from resources.utils import default_field


@define
class Restriction:
    """Representation of how a restriction applies to a user, if at all."""

    removed: bool = False
    action: str | None = Literal["kick", "ban", "dm", None]
    restriction: str | None = Literal["ageLimit", "groupLock", "disallowAlts", "banEvader", None]
    metadata: dict = default_field({"unverified": True})

    def prompt(self, guild_name: str) -> prompts.EmbedPrompt:
        """Return an Embed describing why the user was restricted.

        This prompt will be either DM'd to users or sent in replacement of the typical
        verification success message.
        The only time it is not sent for a restriction is for the disallowAlts restriction, where instead
        a reason will be appended to the success embed as a warning.

        Args:
            guild_name (str): Name of the guild that the user was trying to verify in.

        Returns:
            EmbedPrompt: User-facing embed.
        """
        embed = hikari.Embed()

        embed.set_author(name=f"You could not be verified in {guild_name.capitalize()}!")

        unverified: bool = self.metadata["unverified"]
        description = "You are not verified with Bloxlink!"

        try:
            if unverified:
                raise UserNotVerified()

            match self.restriction:
                case "ageLimit":
                    age_limit_data = self.metadata["ageLimit"]
                    description = (
                        "Your linked Roblox account is not old enough to verify in this server!\n"
                        f"Your account needs to be {age_limit_data[0]} days old, "
                        f"and is only {age_limit_data[1]} days old."
                    )

                case "groupLock":
                    group: RobloxGroup = self.metadata["group"]
                    roleset_restriction = self.metadata["roleset"]
                    dm_message = self.metadata["dmMessage"]

                    if roleset_restriction:
                        description = (
                            "You are not the required rank in "
                            f"[{group.name}](https://www.roblox.com/groups/{group.id})!"
                        )
                    else:
                        description = (
                            "This server requires that you join "
                            f"[{group.name}](https://www.roblox.com/groups/{group.id}) "
                            "before you can verify!"
                        )

                    if dm_message:
                        description += f"\nMessage from the server admins:\n>>> *{dm_message}*"

                case "disallowAlts":
                    # unused?
                    description = (
                        "This server allows you be verified to one Discord account at a time."
                        "Because of this your other accounts linked to your Roblox account have been kicked"
                        "from this server."
                    )

                case "banEvader":
                    description = "You have been removed because you are evading a ban in this server."

        except UserNotVerified:
            pass

        embed.color = RED_COLOR
        embed.description = description

        return prompts.EmbedPrompt(embed=embed, components=[])

    async def moderate(self, user_id: int, guild: hikari.Guild):
        """DM, Kick, or Ban a user based on the determined restriction.

        Args:
            user_id (int): ID of the user to moderate.
            guild (hikari.Guild): The guild that the user is verifying in.
        """
        if self.removed or self.action is None or self.restriction is None:
            return

        prompt = self.prompt(guild.name)
        try:
            # Only DM if the user is being kicked or banned.
            if self.action != "dm":
                channel = await bloxlink.rest.create_dm_channel(user_id)
                await channel.send(embed=prompt.embed)

        except (hikari.BadRequestError, hikari.ForbiddenError, hikari.NotFoundError) as e:
            logging.warning(e)

        try:
            log_reason = self._log_reason()
            if self.action == "kick":
                await bloxlink.rest.kick_user(guild.id, user_id, reason=log_reason)
            elif self.action == "ban":
                await bloxlink.rest.ban_user(guild.id, user_id, reason=log_reason)

        except (hikari.ForbiddenError, hikari.NotFoundError):
            pass
        else:
            if self.action != "dm":
                self.removed = True

    def _log_reason(self) -> str:
        """Generate a string for the audit log entry when a user is kicked or banned.

        Returns:
            str: The resulting audit log string.
        """
        response: str = f"RESTRICTED: {self.restriction}, "

        unverified: bool = self.metadata["unverified"]
        description = "Not verified with Bloxlink."

        try:
            if unverified:
                raise UserNotVerified()

            match self.restriction:
                case "ageLimit":
                    age_limit_data = self.metadata["ageLimit"]
                    description = (
                        "User's Roblox account does not meet the agelimit. "
                        f"{age_limit_data[1]} < {age_limit_data[0]} days."
                    )

                case "groupLock":
                    group: RobloxGroup = self.metadata["group"]
                    roleset_restriction = self.metadata["roleset"]

                    if roleset_restriction:
                        description = f"User is not the required rank in the group {str(group)}"
                    else:
                        description = f"User is not in the group {str(group)}"

                case "banEvader":
                    banned_id = self.metadata["banned_user"]
                    description = f"User is an alt of the banned account {banned_id}"

                case _:
                    description = "User matched a restriction."
        except UserNotVerified:
            pass

        return response + description


async def check_guild_restrictions(guild_id: hikari.Snowflake, user_info: dict) -> Restriction | None:
    """Check if a user should be kept from verifying in this guild_id.

    Args:
        guild_id (hikari.Snowflake): ID of the guild that the user is verifying in.
        user_info (dict): Information of the user
            Expected to have "id": the user id, and "account" which is a RobloxAccount.

    Returns:
        Restriction | None: Restriction info if the user should be restricted.
    """
    guild_data = await bloxlink.fetch_guild_data(
        guild_id,
        "ageLimit",
        "disallowAlts",
        "disallowBanEvaders",
        "groupLock",
    )

    user_id = user_info["id"]
    user_acc: users.RobloxAccount = user_info["account"]

    # TODO: If server has premium and user_acc
    if user_acc:
        bloxlink_user: UserData = await bloxlink.fetch_user_data(user_id, "robloxID", "robloxAccounts")

        accounts = bloxlink_user.robloxAccounts["accounts"]
        accounts.append(bloxlink_user.robloxID)
        accounts = list(set(accounts))

        result = await check_premium_restrictions(
            guild_data.disallowAlts,
            guild_data.disallowBanEvaders,
            user_id,
            guild_id,
            accounts,
        )

        if result:
            return result

    if guild_data.ageLimit:
        if not user_acc:
            return Restriction(action="kick", restriction="ageLimit", metadata={"unverified": True})

        if user_acc.age_days < guild_data.ageLimit:
            return Restriction(
                action="kick",
                restriction="ageLimit",
                metadata={"unverified": False, "ageLimit": (guild_data.ageLimit, user_acc.age_days)},
            )

    if guild_data.groupLock:
        if not user_acc:
            kick_unverified = any(
                g.get("unverifiedAction", "kick") == "kick" for g in guild_data.groupLock.values()
            )

            return Restriction(
                action="kick" if kick_unverified else "dm",
                restriction="groupLock",
                metadata={"unverified": True},
            )

        if user_acc.groups is None:
            await user_acc.sync(includes=["groups"])

        for group_id, group_data in guild_data.groupLock.items():
            action = group_data.get("verifiedAction", "dm")
            required_rolesets = group_data.get("roleSets")

            dm_message = group_data.get("dmMessage")

            group_match: RobloxGroup = user_acc.groups.get(group_id)
            group = group_match if group_match is not None else RobloxGroup(group_id)
            await group.sync()

            if group_match is None:
                return Restriction(
                    action=action,
                    restriction="groupLock",
                    metadata={"unverified": False, "group": group, "dmMessage": dm_message, "roleset": False},
                )

            user_roleset = group_match.user_roleset["rank"]
            for roleset in required_rolesets:
                if isinstance(roleset, list):
                    # List of accepted role IDs.
                    if user_roleset in roleset:
                        break
                elif isinstance(roleset, int):
                    # exact match (x) or inverse match (rolesets above x)
                    if (user_roleset == roleset) or (roleset < 0 and abs(roleset) <= user_roleset):
                        break

            else:
                # no match was found - restrict the user.
                return Restriction(
                    action=action,
                    restriction="groupLock",
                    metadata={"unverified": False, "group": group, "dmMessage": dm_message, "roleset": True},
                )


async def check_premium_restrictions(
    check_alts: bool,
    check_ban_evaders: str | None,
    user_id: int,
    guild_id: int,
    user_accounts: list,
) -> Restriction | None:
    """Check for alts and ban evaders within a server for a user.

    Args:
        check_alts (bool): Should we check for alts
        check_ban_evaders (str | None): Should we check for ban evaders
        user_id (int): Discord ID of the user being updated
        guild_id (int): Guild ID where the user is being updated
        user_accounts (list): Roblox accounts linked to this user_id

    Returns:
        Restriction | None: Restriction info if the user is ban evading or an alt account
            was found.
    """
    if not check_alts and (not check_ban_evaders or check_ban_evaders is None):
        return

    matches = []
    for account in user_accounts:
        matches.extend(await bloxlink.reverse_lookup(account, user_id))

    alts_found: bool = False
    for user in matches:
        # sanity check, shouldn't be included but just in case.
        if str(user_id) == user:
            continue

        if check_alts:
            member = await bloxlink.fetch_discord_member(guild_id, user, "id")

            if member is not None:
                # We kick the old user here because otherwise the restriction will remove the original
                # user based on the code setup.

                try:
                    await bloxlink.rest.kick_user(
                        guild_id, user, reason=f"User is an alt of {user_id} and disallowAlts is enabled."
                    )

                    alts_found = True

                except (hikari.NotFoundError, hikari.ForbiddenError):
                    pass

                # We don't return so we can continue checking for more alts if they exist & kick them too.
                # Plus, returning will prevent ban evader checking.

        if check_ban_evaders:
            try:
                await bloxlink.rest.fetch_ban(guild_id, user)
            except hikari.NotFoundError:
                continue
            except hikari.ForbiddenError:
                continue
            else:
                return Restriction(
                    action="ban",
                    restriction="banEvader",
                    metadata={"unverified": False, "banned_user": user},
                )

        if alts_found:
            return Restriction(
                action="dm",
                restriction="disallowAlts",
                metadata={"unverified": False},
            )
