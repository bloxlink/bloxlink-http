import logging
from enum import Enum
from bloxlink_lib import defer_execution
from config import CONFIG
from resources.bloxlink import bloxlink
from resources.constants import DEVELOPERS



class UserTypes(Enum):
    """Types for users"""

    BLOXLINK_BLACKLISTED = 0
    BLOXLINK_USER        = 1
    BLOXLINK_PARTNER     = 2
    BLOXLINK_STAFF       = 3
    BLOXLINK_DEVELOPER   = 4


special_users: dict[int, UserTypes] = {}


@defer_execution
async def load_staff():
    """Fetches the Bloxlink team server and loads the staff into the database"""

    if CONFIG.STAFF_GUILD_ID and CONFIG.STAFF_ROLE_ID:
        logging.info("Loading Bloxlink staff...")
        team_guild = await bloxlink.rest.fetch_guild(CONFIG.STAFF_GUILD_ID)
        team_role = await team_guild.fetch_role(CONFIG.STAFF_ROLE_ID)

        for member in team_role.members:
            special_users[member.id] = UserTypes.BLOXLINK_STAFF

        logging.info("Loaded Bloxlink staff")
    else:
        logging.info("Skipping Bloxlink staff loading")


@defer_execution
async def load_developers():
    """Fetches the developers and loads them into the database"""

    logging.info("Loading Bloxlink developers...")

    if DEVELOPERS:
        logging.info("Loading Bloxlink developers...")

        for developer_id in DEVELOPERS:
            special_users[developer_id] = UserTypes.BLOXLINK_DEVELOPER
    else:
        logging.info("Skipping Bloxlink developer loading")


async def load_blacklisted():
    """Fetches the blacklisted users"""

    raise NotImplementedError()

def get_user_type(user_id: int) -> UserTypes:
    """Get the type of a user"""

    return special_users.get(user_id, UserTypes.BLOXLINK_USER)
