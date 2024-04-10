from resources.bloxlink import instance as bloxlink
from resources.commands import GenericCommand
from resources.constants import DEVELOPER_GUILDS
from bloxlink_lib.database import update_guild_data


@bloxlink.command(
    developer_only=True,
    guild_ids=DEVELOPER_GUILDS
)
class QuickBindCommand(GenericCommand):
    """insert some fake binds"""

    async def __main__(self, ctx):
        guild_id = ctx.guild_id

        binds = [
            # {
            #     "roles": ["1046988399208321024"],
            #     # "removeRoles": ["1046308369151041556", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "criteria": {
            #         "type": "group",
            #         "id": 1
            #     }
            # },
            # {
            #     "roles": ["1046988399208321024"],
            #     # "removeRoles": ["1046308369151041556", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "criteria": {
            #         "type": "group",
            #         "id": 2
            #     }
            # },
            # {
            #     "roles": ["1234567890123"],
            #     "removeRoles": ["1234567890123", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "criteria": {
            #         "type": "group",
            #         "id": 1,
            #         "min": 1,
            #         "max": 5
            #     }
            # },
            # {
            #     "roles": ["1234567890123"],
            #     "removeRoles": ["1234567890123", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "bind": {
            #         "type": "group",
            #         "id": 2,
            #         "roleset": -200,
            #     }
            # },
            # {
            #     "roles": ["1234567890123"],
            #     "removeRoles": ["1234567890123", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "bind": {
            #         "type": "group",
            #         "id": 2,
            #         "everyone": True,
            #     }
            # },
            {
                "roles": ["1202091765562355812"],
                "removeRoles": [],
                "nickname": "{roblox-name}",
                "criteria": {
                    "type": "group",
                    "id": 3587262,
                    "group": {
                        "everyone": True,
                        "guest": False
                    }
                }
            },
            {
                "roles": ["821463332670013520"],
                # "removeRoles": ["997690205177905233"],
                "nickname": "{roblox-name}",
                "criteria": {
                    "type": "unverified",
                    "id": None
                }
            },
            {
                "roles": ["997690205177905233"],
                # "removeRoles": ["997690205177905233"],
                "nickname": "{roblox-name}",
                "criteria": {
                    "type": "verified",
                    "id": None
                }
            },
            {
                "roles": ["1203872460567609354"],
                # "removeRoles": ["997690205177905233"],
                "nickname": "{roblox-name}",
                "criteria": {
                    "type": "badge",
                    "id": 2153913164
                }
            },
        ]

        await update_guild_data(guild_id, binds=binds)

        await ctx.response.send("added binds")
