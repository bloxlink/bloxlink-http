from typing import Literal, Annotated
from os import getcwd, environ
from dotenv import load_dotenv
from pydantic import Field
from bloxlink_lib import Config as BLOXLINK_CONFIG

load_dotenv(f"{getcwd()}/.env")


class Config(BLOXLINK_CONFIG):
    """Type definition for config values."""

    #############################
    DISCORD_APPLICATION_ID: str
    DISCORD_PUBLIC_KEY: str
    BOT_RELEASE: Literal["LOCAL", "CANARY", "MAIN", "PRO"] = "LOCAL"
    #############################
    BOT_API: str
    BOT_API_AUTH: str
    #############################
    HOST: str
    PORT: Annotated[int, Field(default=8010)]
    HTTP_BOT_AUTH: str
    STAFF_GUILD_ID: int = None
    STAFF_ROLE_ID: int = None


CONFIG: Config = Config(
    **{field:value for field, value in environ.items() if field in Config.model_fields}
)
