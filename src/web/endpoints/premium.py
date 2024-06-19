from blacksheep import Request, ok
from blacksheep.server.controllers import APIController, get

from resources.premium import get_premium_status

from ..decorators import authenticate


class Premium(APIController):
    """Results in a path of <URL>/api/premium/..."""

    @get("/guilds/{guild_id}")
    @authenticate()
    async def check_guild_premium(self, guild_id: str, _request: Request):
        """Endpoint to check whether the guild has premium/pro."""

        premium_status = await get_premium_status(guild_id=guild_id)

        if premium_status.active:
            return ok({
                "premium": premium_status.active,
                "tier": premium_status.tier,
                "term": premium_status.term,
                "features": list(premium_status.features)
            })

        return ok({
            "premium": False,
        })

    @get("/users/{user_id}")
    @authenticate()
    async def check_user_premium(self, user_id: str, request: Request):
        """Endpoint to check whether the user has premium/pro."""

        raise NotImplementedError()
