import asyncio
import functools
import json
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Coroutine, Optional, Unpack

import hikari
import yuyo
from motor.motor_asyncio import AsyncIOMotorClient
from redis import RedisError

from bloxlink_lib import SnowflakeSet
from bloxlink_lib.database import redis
from resources.redis import RedisMessageCollector
from config import CONFIG

instance: "Bloxlink" = None


if TYPE_CHECKING:
    from resources.commands import NewCommandArgs



class Bloxlink(yuyo.AsgiBot):
    """The Bloxlink bot."""

    def __init__(self, *args, **kwargs):
        """Initialize the bot & the MongoDB connection."""
        global instance  # pylint: disable=global-statement

        super().__init__(*args, **kwargs)
        self.started_at = datetime.utcnow()
        self.mongo: AsyncIOMotorClient = AsyncIOMotorClient(CONFIG.MONGO_URL)
        self.mongo.get_io_loop = asyncio.get_running_loop

        self.redis_messages: RedisMessageCollector = None

        instance = self

    async def start(self) -> Coroutine[any, any, None]:
        """Start the bot"""

        self.redis_messages = RedisMessageCollector()

        return await super().start()

    @property
    def uptime(self) -> timedelta:
        """Current bot uptime."""
        return datetime.utcnow() - self.started_at

    async def relay[T](self, channel: str, model: T = None, payload: Optional[dict] = None, timeout: int = 2, wait_for_all: bool = True) -> list[T]:
        """Relay a message over Redis to the gateway.

        Args:
            channel (str): The pubsub channel to publish the message over.
            model (T): The model to parse the response into.
            payload (Optional[dict]): The data to include in the message being sent. Defaults to None.
            timeout (int, optional): Timeout time for a reply in seconds. Defaults to 2 seconds.

        Raises:
            RuntimeError: When Redis was unable to publish or get a response.
            TimeoutError: When the request has reached its timeout.

        Returns:
            list[T]: The list of responses from the gateway.
        """

        nonce = uuid.uuid4()
        reply_channel = f"REPLY:{nonce}"
        model = model or dict

        try:
            await self.redis_messages.pubsub.subscribe(reply_channel)
            await redis.publish(
                channel, json.dumps({"nonce": str(nonce), "data": payload}).encode("utf-8")
            )
            return await self.redis_messages.get_message(reply_channel, timeout=timeout, wait_for_all=wait_for_all, model=model)
        except RedisError as ex:
            raise RuntimeError("Failed to publish or wait for response") from ex
        except asyncio.TimeoutError:
            future = self.redis_messages._futures.get(reply_channel)

            if future:
                return (self.redis_messages._futures.pop(reply_channel))[3]

    async def fetch_discord_member(self, guild_id: int, user_id: int, *fields) -> dict | hikari.Member | None:
        """Get a discord member of a guild, first from the gateway, then from a HTTP request.

        Args:
            guild_id (int): The guild ID to find the user in.
            user_id (int): The user ID to find.

        Returns:
            dict | hikari.Member | None: User data as determined by the method of retrieval.
                Dict from the relay. hikari.Member from a HTTP request. None if the user was not found.
        """

        # TODO: implement this endpoint
        try:
            raise NotImplementedError()

            # res = await self.relay(
            #     "CACHE_LOOKUP",
            #     {
            #         "query": "guild.member",
            #         "data": {"guild_id": guild_id, "user_id": user_id},
            #         "fields": list(*fields),
            #     },
            # )

            # return res

        except (RuntimeError, TimeoutError, NotImplementedError):
            try:
                return await self.rest.fetch_member(guild_id, user_id)
            except hikari.NotFoundError:
                return None

    async def fetch_discord_guild(self, guild_id: int) -> dict:
        """Fetches a discord guild from the gateway.

        Args:
            guild_id (int): The guild to find.

        Returns:
            dict: The found guild if it exists.
        """
        # TODO: Implement fallback to fetch from HTTP methods.

        res = await self.relay(
            "CACHE_LOOKUP",
            {
                "query": "guild.data",
                "data": {
                    "guild_id": guild_id,
                },
            },
        )
        return res["data"]

    async def edit_user(
        self,
        member: hikari.Member,
        guild_id: str | int,
        *,
        add_roles: list[int] | SnowflakeSet = None,
        remove_roles: list[int] | SnowflakeSet = None,
        reason: str = "",
        nickname: str = None,
    ) -> hikari.Member:
        """Edits the guild-bound member."""

        remove_roles = SnowflakeSet(remove_roles or [])
        add_roles = SnowflakeSet(add_roles or [])
        new_roles = SnowflakeSet()

        if add_roles or remove_roles:
            new_roles.update(SnowflakeSet(member.role_ids).union(add_roles).difference(remove_roles))

        args = {
            "user": member.id,
            "guild": guild_id,
            "reason": reason or "",
        }

        if new_roles:
            args["roles"] = list(new_roles)

        if nickname:
            args["nickname"] = nickname

        return await self.rest.edit_member(**args)

    async def fetch_roles(self, guild_id: str | int, key_as_role_name: bool = False) -> dict[str, hikari.Role]:
        """guild.fetch_roles() but returns a dictionary instead"""

        return {str(role.name if key_as_role_name else role.id): role for role in await self.rest.fetch_roles(guild_id)}

    async def role_ids_to_names(self, guild_id: int, roles: list) -> str:
        """Get the names of roles based on the role ID.

        Args:
            guild_id (int): The guild to get the roles from.
            roles (list): The IDs of the roles to find the names for.

        Returns:
            str: Comma separated string of the names for all the role IDs given.
        """
        # TODO: Use redis -> gateway comms to get role data/role names.
        # For now this just makes a http request every time it needs it.

        guild_roles = await self.fetch_roles(guild_id)

        return ", ".join(
            [
                guild_roles.get(str(role_id)).name if guild_roles.get(str(role_id)) else "(Deleted Role)"
                for role_id in roles
            ]
        )

    @staticmethod
    def command(**command_attrs: "Unpack[NewCommandArgs]"):
        """Decorator to register a command."""

        from resources.commands import new_command # pylint: disable=import-outside-toplevel

        def wrapper(*args, **kwargs):
            return new_command(*args, **kwargs, **command_attrs)

        return wrapper

    @staticmethod
    def subcommand(**kwargs):
        """Decorator to register a subcommand."""

        def decorator(f):
            f.__issubcommand__ = True
            f.__subcommandattrs__ = kwargs

            @functools.wraps(f)
            def wrapper(self, *args):
                return f(self, *args)

            return wrapper

        return decorator
