# fmt: off
MODULES: list[str] = [
	"commands",
    "resources",
    "web.endpoints",
]

DEFAULTS = {
    "nicknameTemplate": "{smart-name}"
}

LIMITS = {
    "BINDS": {
        "FREE": 60,
        "PREMIUM": 200,
        "MAX": 500
    },
    "RESTRICTIONS": {
        "FREE": 25,
        "PREMIUM": 250
    }
}

SKU_TIERS: dict[int, str] = {
	1022662272188952627: "basic/month",
	1156326821785260102: "pro/month",
	1106314705867378928: "basic/month" # test sku
}

RED_COLOR       = 0xdb2323
INVISIBLE_COLOR = 0x36393E
ORANGE_COLOR    = 0xCE8037
GOLD_COLOR      = 0xFDC333
CYAN_COLOR      = 0x4DD3CC
PURPLE_COLOR    = 0xa830c5
GREEN_COLOR     = 0x0ec37e
BROWN_COLOR     = 0xa2734a
BLURPLE_COLOR   = 0x4a58a2
YELLOW_COLOR    = 0xf1c40f
PINK_COLOR      = 0xf47fff

REPLY_EMOTE = "<:Reply:870665583593660476>"
REPLY_CONT = "<:ReplyCont:870764844012412938>"

UNICODE_LEFT = "\u276E"
UNICODE_RIGHT = "\u276F"
UNICODE_BLANK = "\u2800"

# Obscure unicode character, counts as 2 chars for length.
# Useful for custom_ids where user input is included but we need to split.
SPLIT_CHAR = "\U0001D15D"

# Utilized for bind command logic.
GROUP_RANK_CRITERIA: dict[str, str] = {
    "equ": "Rank must exactly match...",
    "gte": "Rank must be greater than or equal to...",
    "lte": "Rank must be less than or equal to...",
    "rng": "Rank must be between or equal to two other ranks...",
    "gst": "User must NOT be a member of this group.",
    "all": "User must be a member of this group.",
}
GROUP_RANK_CRITERIA_TEXT: dict[str, str] = {
    "equ": "People with the rank",
    "gte": "People with a rank greater than or equal to",
    "lte": "People with a rank less than or equal to",
    "rng": "People with a rank between",
    "gst": "People who are not in **this group**",
    "all": "People who are in **this group**",
}

DEVELOPERS: list[int] = [84117866944663552, 156872400145874944]
DEVELOPER_GUILDS: list[int] = [439265180988211211, 1022176542379479091]

VERIFY_URL_GUILD = "https://blox.link/dashboard/verifications/verify?page=username&guild={guild_id}"
VERIFY_URL = "https://blox.link/dashboard/verifications"

SERVER_INVITE = "https://blox.link/support"
