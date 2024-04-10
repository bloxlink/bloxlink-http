from typing import Literal, Annotated

import hikari
from pydantic import Field
from bloxlink_lib import MemberSerializable, fetch_typed, StatusCodes, get_user, RobloxUser, get_accounts, reverse_lookup, BaseModelArbitraryTypes, BaseModel

from resources.bloxlink import instance as bloxlink
from resources.exceptions import Message, UserNotVerified
from resources.constants import RED_COLOR, SERVER_INVITE
from resources.response import Response
from resources.ui.components import Component, Button
from resources.api.roblox.users import get_verification_link
from config import CONFIG


class RestrictionResponse(BaseModel):
    unevaluated: list[Literal["disallowAlts", "disallowBanEvaders"]] = Field(default_factory=list)
    is_restricted: bool = False
    reason: str | None
    reason_suffix: str | None
    action: Literal["kick", "ban", "dm"] | None
    source: Literal["ageLimit", "groupLock", "disallowAlts", "banEvader"] | None
    # warnings: list[str] = Field(default_factory=list)


class Restriction(BaseModelArbitraryTypes):
    """Representation of how a restriction applies to a user, if at all."""

    guild_id: int
    member: hikari.Member | MemberSerializable
    roblox_user: RobloxUser | None
    guild_name: str = None

    restricted: bool = False
    reason: str | None = None
    action: Literal["kick", "ban", "dm", None] = None
    source: Literal["ageLimit", "groupLock", "disallowAlts", "banEvader", None] = None
    warnings: list[Annotated[str, Field(default_factory=list)]] = None
    unevaluated: list[Literal["disallowAlts", "disallowBanEvaders"]] = Field(default_factory=list)
    reason_suffix: str | None = None

    alts: list[int] = Field(default_factory=list)
    banned_discord_id: int = None

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
            f"{CONFIG.BOT_API}/restrictions/evaluate/{self.guild_id}",
            headers={"Authorization": CONFIG.BOT_API_AUTH},
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
        self.reason_suffix = restriction_data.reason_suffix
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

        matches: list[int] = []
        roblox_accounts = await get_accounts(self.member)

        for account in roblox_accounts:
            matches.extend(await reverse_lookup(account, self.member.id))

        for user_id in matches:
            try:
                await bloxlink.rest.fetch_ban(self.guild_id, user_id)
            except hikari.NotFoundError:
                continue
            except hikari.ForbiddenError:
                self.warnings.append("I don't have permission to check the server bans.")
                break
            else:
                self.banned_discord_id = user_id
                self.restricted = True
                self.source = "banEvader"
                self.reason = f"User is evading a ban on user {user_id}."
                self.action = "ban" # TODO: let admins pick
                break

    async def moderate(self):
        """Kick or Ban a user based on the determined restriction."""

        # Only DM users if they're being removed; reason will show in main guild regardless.
        if self.action in ("kick", "ban", "dm"):
            await self.dm_user()

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
        """DM a user about their restriction."""

        components: list[Component] = []

        embed = hikari.Embed()
        embed.title = "User Restricted"
        embed.color = RED_COLOR

        reason_suffix = ""

        verification_url = await get_verification_link(self.member.id, self.guild_id)

        embed.description = (f"You could not verify in **{self.guild_name or 'the server'}** because {self.reason_suffix}."
                             "\n\n> *Think this is in error? Try using the buttons below to switch your account, "
                             f"or join our [support server](<{SERVER_INVITE}>) and use `/verify` there.*"
                            )

        components.extend([
            Button(
                style=Button.ButtonStyle.LINK,
                label="Verify with Bloxlink",
                url=verification_url,
            ),
            Button(
                style=Button.ButtonStyle.LINK,
                label="Join Bloxlink HQ",
                url=SERVER_INVITE,
            ),
        ])

        try:
            # Only DM if the user is being kicked or banned. Reason is shown to user in guild otherwise.
            if self.action:
                channel = await bloxlink.rest.create_dm_channel(self.member.id)
                await (Response(interaction=None).send(channel=channel, embed=embed, components=components))

        except (hikari.BadRequestError, hikari.ForbiddenError, hikari.NotFoundError):
            pass
