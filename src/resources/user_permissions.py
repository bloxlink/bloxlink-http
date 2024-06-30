import logging
from enum import Enum, auto
from bloxlink_lib import defer_execution, get_accounts
from config import CONFIG
from resources.bloxlink import bloxlink
from resources.constants import DEVELOPERS



class UserTypes(Enum):
    """Types for users"""

    BLOXLINK_BLACKLISTED = 0
    BLOXLINK_USER        = auto()
    # BLOXLINK_PARTNER     = auto()
    BLOXLINK_STAFF       = auto()
    BLOXLINK_DEVELOPER   = auto()


special_users: dict[int, UserTypes] = {} # discord ID: UserType
special_users_roblox_accounts: dict[int, int] = {} # roblox ID: discord ID


@defer_execution
async def load_staff():
    """Fetches the Bloxlink team server and loads the staff into the database"""

    if CONFIG.STAFF_GUILD_ID and CONFIG.STAFF_ROLE_ID:
        logging.info("Loading Bloxlink staff...")
        team_members: list[int] = [m.id for m in await bloxlink.rest.fetch_members(CONFIG.STAFF_GUILD_ID) if not m.is_bot and CONFIG.STAFF_ROLE_ID in m.role_ids]

        for member_id in team_members:
            special_users[member_id] = UserTypes.BLOXLINK_STAFF

            for roblox_user in await get_accounts(member_id):
                special_users_roblox_accounts[roblox_user.id] = member_id

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

def get_special_users() -> list[int]:
    """Get all special users"""

    return [k for k, v in special_users.items() if v in (UserTypes.BLOXLINK_STAFF, UserTypes.BLOXLINK_DEVELOPER)]
