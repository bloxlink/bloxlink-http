import hikari
from bloxlink_lib import find, get_group
from bloxlink_lib.database import fetch_guild_data, update_guild_data

from resources.binds import create_bind
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.constants import BROWN_COLOR, DEFAULTS
from resources.exceptions import RobloxNotFound
from resources.response import Prompt, PromptPageData
from resources.ui.components import Button, TextInput, TextSelectMenu
from resources.ui.modals import build_modal

SETUP_OPTIONS = {
    "nicknameTemplate": {
        "description": "The nickname template that Bloxlink will use to nickname users. You can choose a preset template, or choose your own nickname format.",
        "options": {
            "{smart-name}": (
                "Name users as: Display Name (@Roblox Username)",
                "Users will be nicknamed as: `Display Name (@Roblox Username)`. This is the default setting."
            ),
            "{roblox-name}": (
                "Name users as: Roblox Username",
                "Users will be nicknamed as: `Roblox Username`."
            ),
            "{display-name}": (
                "Name users as: Roblox Display Name",
                "Users will be nicknamed as: `Roblox Display Name`."
            ),
            "{discord-name}": (
                "Name users as: Discord Username",
                "Users will be nicknamed as: `Discord Username`."
            ),
            "{disable-nicknaming}": (
                "Do not nickname users",
                "Users will not be nicknamed."
            ),
            "custom": (
                "Choose my own nickname format...",
                "You can choose your own nickname format."
            ),
        }
    },
    "verifiedRoleName": {
        "description": "The name of the role that Bloxlink will give to users when they verify.",
    },
}



class SetupPrompt(Prompt):
    """Setup prompt"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Thank you for choosing Bloxlink, the most popular Roblox-Discord integration! In a few simple prompts, we'll configure Bloxlink for your server."
                         ""
            ),
            components=[
                Button(
                    label="Next",
                    component_id="intro_next",
                    is_disabled=False,
                ),
                Button(
                    label="Cancel",
                    component_id="intro_cancel",
                    is_disabled=False,
                    style=Button.ButtonStyle.SECONDARY
                ),
            ]
        )
    )
    async def intro_page(self, _interaction: hikari.CommandInteraction | hikari.ComponentInteraction, fired_component_id: str | None):
        """The first page of the prompt."""

        match fired_component_id:
            case "intro_next":
                return await self.next()
            case "intro_cancel":
                return await self.finish()

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Should your members be given a different nickname? Please note that by default, Bloxlink will name users as: `Display Name (@Roblox Username)`.\n\n"
                         "You can select a preset template, or choose your own nickname format. You can even set a prefix (text before the nickname) and/or a suffix (text after the nickname)."
            ),
            components=[
                TextSelectMenu(
                    placeholder="Select a nickname preset...",
                    min_values=0,
                    max_values=1,
                    component_id="preset_nickname_select",
                    options=[
                        TextSelectMenu.Option(
                            label=option_data[0],
                            value=option_name,
                        )
                        for option_name, option_data in SETUP_OPTIONS.get("nicknameTemplate").get("options").items()
                    ],
                ),
                Button(
                    label="Add a nickname prefix or suffix (optional)",
                    component_id="nickname_prefix_suffix",
                    is_disabled=False,
                ),
                Button(
                    label="Skip, leave unchanged",
                    component_id="nickname_skip",
                    is_disabled=False,
                    style=Button.ButtonStyle.SECONDARY
                ),
                Button(
                    label="Next",
                    component_id="nickname_submit",
                    is_disabled=True,
                    style=Button.ButtonStyle.SUCCESS
                )
            ],
        )
    )
    async def nickname_page(self, interaction: hikari.ComponentInteraction | hikari.ModalInteraction, fired_component_id: str):
        """The second page of the prompt."""

        guild_nickname = (await fetch_guild_data(self.guild_id, "nicknameTemplate")).nicknameTemplate

        setup_nickname = await self.current_data(key_name="nicknameTemplate", raise_exception=False) or guild_nickname
        setup_nickname_prefix = await self.current_data(key_name="nicknameTemplate_prefix", raise_exception=False) or ""
        setup_nickname_suffix = await self.current_data(key_name="nicknameTemplate_suffix", raise_exception=False) or ""

        match fired_component_id:
            case "preset_nickname_select":
                select_nickname = (await self.current_data(key_name="preset_nickname_select")).get("values")[0]

                if select_nickname == "custom":
                    modal = await build_modal(
                        title="Add a Custom Nickname",
                        command_name=self.command_name,
                        interaction=interaction,
                        prompt_data = {
                            "page_number": self.current_page_number,
                            "prompt_name": self.__class__.__name__,
                            "component_id": fired_component_id,
                            "prompt_message_id": self.custom_id.prompt_message_id,
                            "original_custom_id": self.custom_id,
                        },
                        components=[
                            TextInput(
                                label="Type your nickname template...",
                                style=TextInput.TextInputStyle.SHORT,
                                value=DEFAULTS.get("nicknameTemplate"),
                                custom_id="nickname_prefix_input",
                                required=True
                            ),
                        ]
                    )

                    yield await self.response.send_modal(modal)

                    if not await modal.submitted():
                        return

                    setup_nickname = await modal.get_data("nickname_prefix_input")

                else:
                    setup_nickname = select_nickname

                await self.save_stateful_data(nicknameTemplate=setup_nickname)

                await self.ack()

                await self.edit_page(
                    components={
                        "nickname_submit": {
                            "is_disabled": False,
                        },
                    }
                )

            case "nickname_prefix_suffix":
                modal = await build_modal(
                    title="Add a Nickname Prefix and/or Suffix",
                    command_name=self.command_name,
                    interaction=interaction,
                    prompt_data = {
                        "page_number": self.current_page_number,
                        "prompt_name": self.__class__.__name__,
                        "component_id": fired_component_id,
                        "prompt_message_id": self.custom_id.prompt_message_id,
                        "original_custom_id": self.custom_id,
                    },
                    components=[
                        TextInput(
                            label="This will be shown FIRST in the nickname",
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="Type your nickname prefix...",
                            custom_id="nickname_prefix_input",
                            required=False
                        ),
                        TextInput(
                            label="This will be shown LAST in the nickname",
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="Type your nickname suffix...",
                            custom_id="nickname_suffix_input",
                            required=False
                        ),
                    ]
                )

                yield await self.response.send_modal(modal)

                if not await modal.submitted():
                    return

                modal_data = await modal.get_data()

                setup_nickname_prefix = modal_data.get("nickname_prefix_input") or ""
                setup_nickname_suffix = modal_data.get("nickname_suffix_input") or ""

                await self.save_stateful_data(nicknameTemplate_prefix=setup_nickname_prefix, nicknameTemplate_suffix=setup_nickname_suffix)

                if setup_nickname:
                    yield await self.response.send_first("Saved your response. Please click Next to continue.", ephemeral=True)
                else:
                    yield await self.response.send_first("Saved your response. Please select a nickname from the dropdown, then click Next.", ephemeral=True)

            case "nickname_skip":
                await self.save_stateful_data(nicknameTemplate=None)
                yield await self.next()

            case "nickname_submit":
                yield await self.next()

    @Prompt.programmatic_page()
    async def verified_role_page(self, interaction: hikari.ComponentInteraction | hikari.ModalInteraction, fired_component_id: str):
        """The third page of the prompt."""

        yield PromptPageData(
            title="Setup Bloxlink",
            description=(
                "Do you want to change the name of your **Verified role**? "
                "This is the role that Bloxlink will give to users when they verify.\n\n"
                # TODO: SHOW THE CURRENT NAME OF THE VERIFIED ROLE
            ),
            components=[
                Button(
                    label="Leave as default (Verified)",
                    component_id="verified_role_default",
                    is_disabled=False,
                ),
                Button(
                    label="Change the name",
                    component_id="verified_role_change_name",
                    is_disabled=False,
                ),
                Button(
                    label="Disable the Verified role",
                    component_id="verified_role_disable",
                    is_disabled=False,
                    style=Button.ButtonStyle.DANGER
                ),
                Button(
                    label="Next",
                    component_id="verified_role_submit",
                    is_disabled=True,
                    style=Button.ButtonStyle.SUCCESS
                )
            ],
        )

        match fired_component_id:
            case "verified_role_change_name":
                modal = await build_modal(
                    title="Change Verified Role Name",
                    command_name=self.command_name,
                    interaction=interaction,
                    prompt_data = {
                        "page_number": self.current_page_number,
                        "prompt_name": self.__class__.__name__,
                        "component_id": fired_component_id,
                        "prompt_message_id": self.custom_id.prompt_message_id,
                        "original_custom_id": self.custom_id,
                    },
                    components=[
                        TextInput(
                            label="Type your new verified role name...",
                            style=TextInput.TextInputStyle.SHORT,
                            value="Verified",
                            custom_id="verified_role_new_name",
                            required=True
                        ),
                    ]
                )

                yield await self.response.send_modal(modal)

                if not await modal.submitted():
                    return

                new_verified_role_name = await modal.get_data("verified_role_new_name")

                await self.save_stateful_data(verifiedRoleName=new_verified_role_name)

                await self.edit_page(
                    components={
                        "verified_role_submit": {
                            "is_disabled": False,
                        },
                        "verified_role_default": {
                            "is_disabled": True,
                        },
                        "verified_role_disable": {
                            "is_disabled": True,
                        },
                    }
                )

                await self.response.send(f"Setting the verified role name to `{new_verified_role_name}`! Please click Next to continue.", ephemeral=True)

            case "verified_role_disable":
                await self.save_stateful_data(verifiedRoleName="{disable}")

                yield await self.next()

            case "verified_role_default" | "verified_role_submit":
                yield await self.next()

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Would you like to link a **Roblox group** to your server? This will create Discord roles that match "
                         "your Roblox group and assign it to server members.\n\n**Important:** if you require more advanced "
                         "group management, you can use the `/bind` command to link specific Roblox groups to specific Discord roles."
            ),
            components=[
                Button(
                    label="Link a group",
                    component_id="group_link",
                    is_disabled=False,
                ),
                Button(
                    label="Skip, leave unchanged",
                    component_id="group_skip",
                    is_disabled=False,
                    style=Button.ButtonStyle.SECONDARY
                ),
                Button(
                    label="Next",
                    component_id="group_submit",
                    is_disabled=True,
                    style=Button.ButtonStyle.SUCCESS
                )
            ],
        )
    )
    async def group_page(self, interaction: hikari.ComponentInteraction | hikari.ModalInteraction, fired_component_id: str):
        """The fourth page of the prompt."""

        match fired_component_id:
            case "group_link":
                modal = await build_modal(
                    title="Link a Group",
                    command_name=self.command_name,
                    interaction=interaction,
                    prompt_data = {
                        "page_number": self.current_page_number,
                        "prompt_name": self.__class__.__name__,
                        "component_id": fired_component_id,
                        "prompt_message_id": self.custom_id.prompt_message_id,
                        "original_custom_id": self.custom_id,
                    },
                    components=[
                        TextInput(
                            label="Type your Group URL or ID",
                            style=TextInput.TextInputStyle.SHORT,
                            placeholder="https://www.roblox.com/groups/3587262/Bloxlink-Space#!/about",
                            custom_id="group_id_input",
                            required=True
                        ),
                    ]
                )

                yield await self.response.send_modal(modal)

                if not await modal.submitted():
                    return

                group_id = await modal.get_data("group_id_input")

                try:
                    group = await get_group(group_id)
                except RobloxNotFound:
                    yield await self.response.send_first("That group does not exist! Please try again.", ephemeral=True)
                    return

                await self.save_stateful_data(groupID=group.id)

                await self.edit_page(
                    components={
                        "group_submit": {
                            "is_disabled": False,
                        },
                        "group_skip": {
                            "is_disabled": True,
                        },
                    }
                )

                await self.response.send(
                    f"Adding group **{group.name}** ({group.id})! Please click Next to continue.",
                    ephemeral=True
                )

            case "group_skip" | "group_submit":
                yield await self.next()

    @Prompt.programmatic_page()
    async def setup_finish(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        """The final page of the prompt."""

        yield await self.response.defer()

        setup_data = await self.current_data()
        guild_data = await fetch_guild_data(self.guild_id)

        nickname_template = setup_data.get("nicknameTemplate") or guild_data.nicknameTemplate or DEFAULTS.get("nicknameTemplate")
        verified_role_name = setup_data.get("verifiedRoleName")
        group_id = setup_data.get("groupID")
        nickname_template_prefix = setup_data.get("nicknameTemplate_prefix") or ""
        nickname_template_suffix = setup_data.get("nicknameTemplate_suffix") or ""

        to_change = {}

        new_nickname_template = f"{nickname_template_prefix}{nickname_template}{nickname_template_suffix}"
        setup_option = SETUP_OPTIONS.get("nicknameTemplate").get("options").get(new_nickname_template)

        to_change["nicknameTemplate"] = (
            new_nickname_template,
            "New Nickname Template",
            setup_option[1] if setup_option else "Users will be nicknamed to your custom nickname template.",
            True
        )

        if verified_role_name and verified_role_name != "{disable}":
            to_change["verifiedRoleName"] = (
                verified_role_name,
                "New Verified Role",
                "Users will be given this Verified role when they verify.",
                True
            )
        elif verified_role_name == "{disable}":
            to_change["verifiedRoleName"] = (
                "Disabled",
                "New Verified Role",
                "Users will not be given a Verified role when they verify.",
                True
            )
        else:
            create_verified_role = not guild_data.verifiedRole

            if guild_data.verifiedRole:
                guild = await bloxlink.rest.fetch_guild(self.guild_id)
                verified_role = find(lambda r_id, r: str(r_id) == guild_data.verifiedRole, guild.roles.items())

                if not verified_role:
                    create_verified_role = True
                else:
                    verified_role = verified_role[1]

            if create_verified_role:
                # verifiedRole might be null but there might be a role named Verified
                guild_roles = await bloxlink.rest.fetch_roles(self.guild_id)
                verified_role = find(lambda r: r.name == "Verified", guild_roles) or await bloxlink.rest.create_role(self.guild_id, name="Verified")
                await update_guild_data(self.guild_id, verifiedRole=str(verified_role.id))

            to_change["verifiedRoleName"] = (
                verified_role.name,
                "New Verified Role",
                "Users will be given this Verified role when they verify.",
                True
            )

        if group_id:
            group = await get_group(group_id)
            to_change["groupID"] = (
                f"[{group.name}]({group.url})",
                "Linking group",
                f"Users in group **{group.name}** will get a Discord role that corresponds to their group rank.",
                False
            )

        embed_options = []

        for option_data in to_change.values():
            embed_options.append(f"{option_data[1]} -> {'`' if option_data[3] else ''}{option_data[0]}{'`' if option_data[3] else ''}\n> {option_data[2]}")

        yield PromptPageData(
            title="Setup Confirmation",
            description=(
                "You have reached the end of setup. Please confirm the following settings before finishing.\n\n" +
                ("\n\n".join(embed_options))
            ),
            color=BROWN_COLOR,
            components=[
                Button(
                    label="Finish",
                    component_id="setup_finish",
                    is_disabled=False,
                    style=Button.ButtonStyle.SUCCESS
                ),
                Button(
                    label="Cancel",
                    component_id="setup_cancel",
                    is_disabled=False,
                    style=Button.ButtonStyle.SECONDARY
                )
            ],
        )

        match fired_component_id:
            case "setup_finish":
                pending_db_changes = {}

                if to_change.get("groupID"):
                    await create_bind(
                        self.guild_id,
                        bind_type="group",
                        bind_id=group_id,
                        dynamic_roles=True
                    )

                if to_change.get("nicknameTemplate"):
                    pending_db_changes["nicknameTemplate"] = to_change["nicknameTemplate"][0]

                if to_change.get("verifiedRoleName"):
                    if to_change["verifiedRoleName"][0] == "Disabled":
                        pending_db_changes["verifiedRoleEnabled"] = False
                    else:
                        verified_role_name = to_change["verifiedRoleName"][0]
                        pending_db_changes["verifiedRoleEnabled"] = True

                        # create role if it doesn't exist
                        guild = await bloxlink.rest.fetch_guild(self.guild_id)

                        if not find(lambda r: r.name == verified_role_name, guild.roles.values()):
                            verified_role = await bloxlink.rest.create_role(self.guild_id, name=verified_role_name)
                            pending_db_changes["verifiedRole"] = str(verified_role.id)

                if pending_db_changes:
                    await update_guild_data(self.guild_id, **pending_db_changes)

                await self.edit_page(content="Successfully saved the configuration to your server.", embed=None)

            case "setup_cancel":
                yield await self.finish()


@bloxlink.command(
    category="Administration",
    defer_with_ephemeral=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    dm_enabled=False,
    prompts=[SetupPrompt],
)
class SetupCommand(GenericCommand):
    """setup Bloxlink for your server"""

    async def __main__(self, ctx: CommandContext):
        return await ctx.response.send_prompt(SetupPrompt)
