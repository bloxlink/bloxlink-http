import math
from unicodedata import category
from snowfin import Module, slash_command, slash_option, Embed, Interaction, Button, EmbedField, Select, SelectOption, select_callback, button_callback, Components, EditResponse, MessageResponse

CMDS_PER_PAGE = 8

class CommandsCommand(Module):
    category = "Miscellaneous"

    def render_command_list(self, category: str = "Miscellaneous", page: int = 1, edit: bool = False) -> tuple[Embed, Select, Button, Button]:
        embed = Embed(
            description="Roblox Verification made easy! Features everything you need to integrate your Discord server with Roblox.\n",
            color=0xdb2323,
        )

        commands = []

        if not category:
            category = "Miscellaneous"
        
        all_cats = []
        for cmd in self.client.commands:
            if cmd.module.category == category:
                commands.append(cmd)
            if cmd.module.category not in all_cats:
                all_cats.append(cmd.module.category)

        commands = commands[(page - 1) * CMDS_PER_PAGE:page * CMDS_PER_PAGE]

        for command in commands:
            embed.description += f"\n[**{command.name}**](https://blox.link/commands/{command.name})\n<:reply_end:875993580836126720>{command.description}"

        components = Components(
            Select(
                custom_id="command_list_category",
                options=[
                    SelectOption(
                        label=cat,
                        value=cat,
                        default=cat == category
                    ) for cat in all_cats
                ],
            ),
            Button("Previous", custom_id=f"command_list_page:{category}:{page - 1}", disabled=page == 1),
            Button("Next", custom_id=f"command_list_page:{category}:{page + 1}", disabled=page * CMDS_PER_PAGE >= len(commands)),
        )

        return (EditResponse if edit else MessageResponse)(
            embed=embed,
            components=components,
        )

    @select_callback("command_list_category")
    async def command_list_category(self, ctx: Interaction):
        category = next(iter(ctx.data.values), "Miscellanous")
        return self.render_command_list(category, edit=True)

    @button_callback("command_list_page:{category}:{page}")
    async def command_list_page(self, ctx: Interaction, category: str, page: int):
        return self.render_command_list(category, page, edit=True)

    @slash_command("commands")
    @slash_option("command", "please specify the command name", type=3, required=False)
    async def commands(self, ctx: Interaction, command: str = None):
        """view the commmand list, or get help for a specific command"""

        if command is None:
            return self.render_command_list()

        cmd = next((c for c in self.client.commands if c.name.lower() == command.lower()), None)

        if cmd is None:
            return "This command does not exist! Please use `/commands` to view a full list of commands."

        return Embed(
            title=f"/{cmd.name}",
            description=cmd.description,
            color=0xdb2323,
            fields=[
                EmbedField(
                    name="Category",
                    value=cmd.module.category,
                    inline=True
                ),
            ]
        )
           
