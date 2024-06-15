from resources.bloxlink import bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.ui.components import TextInput
from resources.constants import DEVELOPER_GUILDS


@bloxlink.command(
    category="Miscellaneous",
    developer_only=True,
    guild_ids=DEVELOPER_GUILDS
)
class ModalTestCommand(GenericCommand):
    """test modals"""

    async def __main__(self, ctx: CommandContext):
        modal = ctx.response.build_modal(
            title="Link a Group",
            components=[
                TextInput(
                    style=TextInput.TextInputStyle.SHORT,
                    placeholder="https://www.roblox.com/groups/3587262/Bloxlink-Space#!/about",
                    custom_id="group_id_input",
                    label="Type your Group URL or ID",
                    required=True
                ),
            ]
        )

        await ctx.response.send_modal(modal)

        return await ctx.response.send_first("pong")
