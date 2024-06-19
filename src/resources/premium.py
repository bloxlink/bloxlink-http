
from typing import Annotated
from datetime import timedelta
from enum import Enum, auto
import hikari
from pydantic import Field
from bloxlink_lib import BaseModel
from bloxlink_lib.database import fetch_guild_data, redis
from resources.user_permissions import get_user_type, UserTypes
from resources.bloxlink import bloxlink
from config import CONFIG

from .constants import SKU_TIERS


__all__ = ("PremiumStatus", "get_premium_status", "PremiumTier", "PremiumType")


class PremiumEnum(Enum):
    """Makes the printed enum only use the last part"""

    def __str__(self):
        return self.name

class PremiumTier(PremiumEnum):
    """Tier for the premium subscription"""

    BASIC = auto()
    PRO = auto()

class PremiumType(PremiumEnum):
    """Type of premium"""

    GUILD = auto()
    USER = auto()

class PremiumSource(PremiumEnum):
    """The source of where the premium comes from"""

    DISCORD_BILLING = auto()
    CHARGEBEE = auto()
    PREMIUM_OVERRIDE = auto()

class PremiumLength(PremiumEnum):
    """The length of the subscription"""

    MONTHLY = auto()
    YEARLY = auto()
    LIFETIME = auto()
    LENGTH_UNDEFINED = auto() # usually from automatic premium. no real length, but it can end

class PremiumFeatures(PremiumEnum):
    """The features that can be included in the subscription"""

    PREMIUM = auto()
    PRO = auto()


class PremiumStatus(BaseModel):
    """Represents the premium status of a guild or user."""

    active: bool = False
    type: PremiumType = None
    payment_source: PremiumSource = None
    payment_source_url: str = None
    tier: PremiumTier = None
    length: PremiumLength = None
    features: Annotated[list[PremiumFeatures], Field(default_factory=list)]
    discord_id: int = None # Guild or user ID that owns this subscription

    def __str__(self):
        buffer: list[str] = []

        if self.features:
            if PremiumFeatures.PREMIUM in self.features:
                buffer.append("Basic - Premium commands")
            if PremiumFeatures.PRO in self.features:
                buffer.append(
                    "Pro - Unlocks the Pro bot and a few [enterprise features](https://blox.link/pricing)"
                )

        return "\n".join(buffer) or "Not premium"

    @property
    def payment_hyperlink(self) -> str:
        """Returns a string with the payment source and a link to the payment source if the premium is active."""

        if self.active and self.payment_source != PremiumSource.PREMIUM_OVERRIDE:
            return f"[{self.payment_source}]({self.payment_source_url})"

        return self.payment_source or ""

    @property
    def payment_source_url(self) -> str | None:
        """Returns a link to the payment source if the premium is active."""

        if self.active:
            return "https://support.discord.com/hc/en-us/articles/9359445233303-Premium-App-Subscriptions-FAQ" if self.payment_source == PremiumSource.DISCORD_BILLING else f"https://blox.link/dashboard/guilds/{self.premium_discord_id}/premium"

        return None

def get_user_facing_tier_term(tier_name: str) -> tuple[str, str]:
    """Returns a user-facing tier name and term."""

    user_facing_tier: str | None = None
    term: str | None = None

    try:
        tier, term = tier_name.split("/")

        if tier == "basic":
            user_facing_tier = "Basic Premium"
        elif tier == "pro":
            user_facing_tier = "Pro"

    except ValueError:
        user_facing_tier = tier_name

    return user_facing_tier, term


def get_premium_features(premium_data: dict, tier: str) -> list[PremiumFeatures]:
    """Merges 'free' features from the database with the default features provided"""

    features: list[PremiumFeatures] = [PremiumFeatures.PREMIUM]

    if tier == "pro" or premium_data.get("patreon") or "pro" in tier:
        features.append(PremiumFeatures.PRO)

    return features


async def get_premium_status(
    *, guild_id: int | str = None, _user_id: int | str = None, interaction: hikari.CommandInteraction=None
) -> PremiumStatus:
    """Returns a PremiumStatus object dictating whether the guild has premium."""

    if interaction:
        # bloxlink staff premium override
        if get_user_type(interaction.user.id) in (UserTypes.BLOXLINK_STAFF, UserTypes.BLOXLINK_DEVELOPER):
            return PremiumStatus(
                active=True,
                type=PremiumType.GUILD,
                payment_source=PremiumSource.PREMIUM_OVERRIDE,
                payment_source_url="https://blox.link",
                discord_id=guild_id,
                tier=PremiumTier.PRO,
                length=PremiumLength.LENGTH_UNDEFINED,
                features=[PremiumFeatures.PREMIUM, PremiumFeatures.PRO],
            )

    if guild_id:
        return await _check_guild_premium(guild_id, interaction)

    # user premium
    raise NotImplementedError()


async def _check_guild_premium(guild_id: int, interaction: hikari.CommandInteraction = None) -> PremiumStatus:
    premium_data = (await fetch_guild_data(str(guild_id), "premium")).premium

    if interaction:
        for entitlement in interaction.entitlements:
            if entitlement.sku_id in SKU_TIERS:
                tier, term = get_user_facing_tier_term(SKU_TIERS[entitlement.sku_id])
                features = get_premium_features(premium_data, SKU_TIERS[entitlement.sku_id])

                return PremiumStatus(
                    active=True,
                    type=PremiumType.GUILD,
                    payment_source=PremiumSource.DISCORD_BILLING,
                    discord_id=guild_id,
                    tier=tier,
                    term=term,
                    features=features,
                )
    else:
        # check discord through REST
        redis_discord_billing_premium_key = f"premium:discord_billing:{guild_id}"
        redis_discord_billing_tier: bytes = await redis.get(redis_discord_billing_premium_key)
        has_discord_billing = redis_discord_billing_tier not in (None, "false")

        if not redis_discord_billing_tier:
            entitlements = await bloxlink.rest.fetch_entitlements(
                CONFIG.DISCORD_APPLICATION_ID,
                guild=str(guild_id),
                exclude_ended=True
            )

            has_discord_billing = bool(entitlements)
            redis_discord_billing_tier = SKU_TIERS[entitlements[0].sku_id] if has_discord_billing else None

            await redis.set(redis_discord_billing_premium_key, redis_discord_billing_tier if has_discord_billing else "false", expire=timedelta(seconds=100))

        if has_discord_billing:
            tier, term = get_user_facing_tier_term(redis_discord_billing_tier)
            features = get_premium_features(premium_data, redis_discord_billing_tier)

            return PremiumStatus(
                active=True,
                type=PremiumType.GUILD,
                payment_source=PremiumSource.DISCORD_BILLING,
                discord_id=guild_id,
                tier=tier,
                term=term,
                features=features,
            )

    # last resort: hit database for premium
    if premium_data and premium_data.get("active") and not premium_data.get("externalDiscord"):
        tier, term = get_user_facing_tier_term(premium_data["type"])
        features = get_premium_features(premium_data, premium_data.get("type", "basic/month"))

        return PremiumStatus(
            active=True,
            type=PremiumType.GUILD,
            payment_source=PremiumSource.CHARGEBEE,
            discord_id=guild_id,
            tier=tier,
            term=term,
            features=features,
        )

    return PremiumStatus(active=False)
