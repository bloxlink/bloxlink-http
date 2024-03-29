from typing import Literal

import hikari
from pydantic import Field
from bloxlink_lib import MemberSerializable, fetch_typed, StatusCodes, get_user, RobloxUser, get_accounts, reverse_lookup, BaseModelArbitraryTypes, BaseModel

from resources.bloxlink import instance as bloxlink
from resources.exceptions import Message, UserNotVerified
from config import CONFIG


class RestrictionResponse(BaseModel):
    unevaluated: list[Literal["disallowAlts", "disallowBanEvaders"]] = Field(default_factory=list)
    is_restricted: bool = False
    reason: str | None
    action: Literal["kick", "ban", "dm"] | None
    source: Literal["ageLimit", "groupLock", "disallowAlts", "banEvader"] | None
    # warnings: list[str]


class Restriction(BaseModelArbitraryTypes):
    """Representation of how a restriction applies to a user, if at all."""

    guild_id: int

    restricted: bool = False
    reason: str = None
    action: Literal["kick", "ban", "dm", None] = None
    source: Literal["ageLimit", "groupLock", "disallowAlts", "banEvader", None] = None
    warnings: list[str] = Field(default_factory=list)
    unevaluated: list[Literal["disallowAlts", "disallowBanEvaders"]] = Field(default_factory=list)

    alts: list[int] = Field(default_factory=list)
    banned_discord_id: int = None

    member: hikari.Member | MemberSerializable = None
    roblox_user: RobloxUser | None = None

    _synced: bool = False


    async def sync(self):
        """Fetch restriction data from the API."""

        if self._synced:
            return

        if not self.roblox_user:
            try:
                self.roblox_user = await get_user(self.member.id, guild_id=self.guild_id)
            except UserNotVerified:
                pass

        restriction_data, restriction_response = await fetch_typed(
            RestrictionResponse,
            f"{CONFIG.BIND_API}/restrictions/evaluate/{self.guild_id}/{self.member.id}",
            headers={"Authorization": CONFIG.BIND_API_AUTH},
            method="POST",
            body={
                "member": MemberSerializable.from_hikari(self.member).model_dump(),
                "roblox_user": self.roblox_user.model_dump(by_alias=True) if self.roblox_user else None,
            },
        )

        if restriction_response.status != StatusCodes.OK:
            raise Message(f"Failed to fetch restriction data for {self.member.id} in {self.guild_id}")

        self.restricted = restriction_data.is_restricted
        self.reason = restriction_data.reason
        self.action = restriction_data.action
        self.source = restriction_data.source
        # self.warnings = restriction_data.warnings
        self.unevaluated = restriction_data.unevaluated

        if self.unevaluated and self.roblox_user:
            if "disallowAlts" in self.unevaluated:
                await self.check_alts()

            if "disallowBanEvaders" in self.unevaluated:
                await self.check_ban_evading()

        self._synced = True

    async def check_alts(self):
        """Check if the user has alternate accounts in this server."""

        matches: list[int] = []
        roblox_accounts = await get_accounts(self.member.id)

        for account in roblox_accounts:
            for user in await reverse_lookup(account, self.member.id):
                member = await bloxlink.fetch_discord_member(self.guild_id, user, "id")

                if member:
                    matches.append(int(member.id))

        if matches:
            self.source = "disallowAlts"
            self.reason = f"User has alternate accounts in this server: {', '.join(matches)}"

        self.alts = matches

    async def check_ban_evading(self):
        """Check if the user is evading a ban in this server."""

        matches = []
        roblox_accounts = await get_accounts(self.member.id)

        for account in roblox_accounts:
            matches.append(await reverse_lookup(account, self.member.id))

        for user in matches:
            try:
                await bloxlink.rest.fetch_ban(self.guild_id, user)
            except (hikari.NotFoundError, hikari.ForbiddenError):
                continue
            else:
                self.banned_discord_id = int(user.id)
                self.restricted = True
                self.source = "banEvader"
                self.reason = f"User is evading a ban on user {user.id}."
                self.action = "ban" # FIXME
                break

    async def moderate(self):
        """Kick or Ban a user based on the determined restriction."""

        # Only DM users if they're being removed; reason will show in main guild otherwise.
        # if self.action in ("kick", "ban"):
        #     await self.dm_user()

        reason = (
            f"({self.source}): {self.reason[:450]}"  # pylint: disable=unsubscriptable-object
            if self.reason
            else f"User was removed because they matched this server's {self.source} settings."
        )

        actioning_users: list[int] = []

        if self.banned_discord_id:
            actioning_users.append(self.banned_discord_id)

        if self.alts:
            actioning_users.extend(self.alts)

        for user_id in actioning_users:
            if self.action == "kick":
                await bloxlink.rest.kick_user(self.guild_id, user_id, reason=reason)

            elif self.action == "ban":
                await bloxlink.rest.ban_user(self.guild_id, user_id, reason=reason)

    async def dm_user(self):
        # components = []

        # embed = hikari.Embed()
        # embed.title = "User Restricted"
        # embed.color = RED_COLOR

        # reason_suffix = ""
        # match self.source:
        #     # fmt:off
        #     case "ageLimit":
        #         reason_suffix = "this server requires users to have a Roblox account older than a certain age"
        #     case "groupLock":
        #         reason_suffix = "this server requires users to be in, or have a specific rank in, a Roblox group"
        #     case "banEvader":
        #         reason_suffix = "this server does not allow ban evasion"
        #     # fmt:on

        # embed.description = f"You could not verify in **{guild.name}** because {reason_suffix}."

        # if self.source not in {"banEvader", "disallowAlts"}:
        #     embed.add_field(name="Reason", value=self.reason)
        #     embed.description += (
        #         "\n\n> *Think this is in error? Try using the buttons below to switch your account, "
        #         "or join our guild and use `/verify` there.*"
        #     )

        #     verification_url = await users.get_verification_link(user_id, guild.id)

        #     button_row = bloxlink.rest.build_message_action_row()
        #     button_row.add_link_button(verification_url, label="Verify with Bloxlink")
        #     button_row.add_link_button(SERVER_INVITE, label="Join Bloxlink HQ")

        #     components.append(button_row)

        # try:
        #     # Only DM if the user is being kicked or banned. Reason is shown to user in guild otherwise.
        #     if self.action != "dm":
        #         channel = await bloxlink.rest.create_dm_channel(user_id)
        #         await channel.send(embed=embed, components=components)

        # except (hikari.BadRequestError, hikari.ForbiddenError, hikari.NotFoundError) as e:
        #     logging.warning(e)

        raise NotImplementedError() # TODO