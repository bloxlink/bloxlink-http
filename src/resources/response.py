import functools
import json
import logging
import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Generic, Type, TypeVar, Self

import hikari
from pydantic import Field
from bloxlink_lib import BaseModel, UNDEFINED, BloxlinkException
from bloxlink_lib.database import redis

import resources.ui.components as Components
import resources.commands as commands
import resources.ui.modals as modal
from resources.bloxlink import instance as bloxlink
from resources.ui.embeds import InteractiveMessage

from .exceptions import CancelCommand, PageNotFound

if TYPE_CHECKING:
    from resources.ui.autocomplete import AutocompleteOption


class PromptEmbed(InteractiveMessage):
    """Represents a prompt consisting of an embed & components for the message."""

    page_number: int = 0


class PromptCustomID(Components.CommandCustomID):
    """Represents a custom ID for a prompt component."""

    prompt_name: str
    page_number: int = 0
    component_custom_id: str = None
    prompt_message_id: int = None

    def model_post_init(self, __context):
        self.type = "prompt"


class PromptPageData(BaseModel):
    """Represents the data for a page of a prompt."""

    description: str
    components: list[Components.Component] = Field(default_factory=list)
    title: str = None
    fields: list["Field"] = Field(default_factory=list)
    color: int = None

    class Field(BaseModel):  # TODO: RENAME THIS TO PromptField
        """Represents a field in a prompt embed."""

        name: str
        value: str
        inline: bool = False


class Page(BaseModel):
    """Represents a page of a prompt."""

    func: Callable
    details: PromptPageData
    page_number: int
    programmatic: bool = False
    edited: bool = False


T = TypeVar("T", bound="PromptCustomID")


class Response:
    """Response to a discord interaction.

    Attributes:
        interaction (hikari.CommandInteraction): Interaction that this response is for.
        user_id (hikari.Snowflake): The user ID who triggered this interaction.
        responded (bool): Has this interaction been responded to. Default is False.
        deferred (bool): Is this response a deferred response. Default is False.
    """

    def __init__(
        self, interaction: hikari.CommandInteraction | hikari.ComponentInteraction | hikari.ModalInteraction
    ):
        self.interaction = interaction
        self.user_id = interaction.user.id
        self.responded = False
        self.deferred = False
        self.defer_through_rest = False

    async def defer(self, ephemeral: bool = False):
        """Defer this interaction. This needs to be yielded and called as the first response.

        Args:
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
        """

        if self.responded:
            # raise AlreadyResponded("Cannot defer a response that has already been responded to.")
            return

        self.responded = True
        self.deferred = True

        if self.defer_through_rest:
            if ephemeral:
                return await self.interaction.create_initial_response(
                    hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, flags=hikari.messages.MessageFlag.EPHEMERAL
                )

            return await self.interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)

        if self.interaction.type == hikari.InteractionType.APPLICATION_COMMAND:
            return self.interaction.build_deferred_response().set_flags(
                hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None
            )

        return self.interaction.build_deferred_response(
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE
        ).set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)

    async def send_first(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        ephemeral: bool = False,
        edit_original: bool = False,
        build_components: bool = True,
    ):
        """Directly respond to Discord with this response. This should not be called more than once. This needs to be yielded.

        Args:
            content (str, optional): Message content to send. Defaults to None.
            embed (hikari.Embed, optional): Embed to send. Defaults to None.
            components (list, optional): Components to attach to the message. Defaults to None.
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
            edit_original (bool, optional): Should this edit the original message. Defaults to False.
            build_components (bool, optional): Should this convert custom components to hikari components. Defaults to True.
        """

        logging.debug("responded=%s", self.responded)

        if components and build_components:
            components = Components.clean_action_rows(
                functools.reduce(
                    lambda a, c: c.build(a), components, [bloxlink.rest.build_message_action_row()]
                )
            )

        if self.responded:
            if edit_original:
                return await self.interaction.edit_initial_response(
                    content, embed=embed, components=components
                )

            return await self.send(content, embed=embed, components=components, ephemeral=ephemeral)

        self.responded = True

        match self.interaction:
            case hikari.CommandInteraction() | hikari.ModalInteraction():
                response_builder = (
                    self.interaction.build_response()
                    .set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)
                    .set_mentions_everyone(False)
                    .set_role_mentions(False)
                )
            case hikari.ComponentInteraction():
                response_builder = (
                    self.interaction.build_response(
                        hikari.ResponseType.MESSAGE_CREATE
                        if not edit_original
                        else hikari.ResponseType.MESSAGE_UPDATE
                    )
                    .set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)
                    .set_mentions_everyone(False)
                    .set_role_mentions(False)
                )

            case _:
                raise NotImplementedError()

        if content:
            response_builder.set_content(content)
        # else:
        #     response_builder.clear_content()

        if embed:
            response_builder.add_embed(embed)
        # else:
        #     response_builder.clear_embeds()

        if components:
            for component in components:
                response_builder.add_component(component)
        else:
            response_builder.clear_components()

        # print(response_builder)

        return response_builder

    async def send(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list[Components.Component] = None,
        ephemeral: bool = False,
        channel: hikari.GuildTextChannel = None,
        channel_id: str | int = None,
        build_components: bool = True,
        fetch_message=False,
        edit_original: bool = False,
        **kwargs,
    ) -> hikari.Message | None:
        """Send this Response to discord. This function only sends via REST and ignores the initial webhook response.

        Args:
            content (str, optional): Message content to send. Defaults to None.
            embed (hikari.Embed, optional): Embed to send. Defaults to None.
            components (list, optional): Components to attach to the message. Defaults to None.
            ephemeral (bool, optional): Whether this message be ephemeral. Defaults to False.
            channel (hikari.GuildTextChannel, optional): Channel to send the message to. This will send as a regular message, not as an interaction response. Defaults to None.
            channel_id (int, str, optional): Channel ID to send the message to. This will send as a regular message, not as an interaction response. Defaults to None.
            build_components (bool, optional): Whether this convert custom components to hikari components. Defaults to True.
            fetch_message (bool, optional): Whether to fetch the message through HTTP. Defaults to False.
            **kwargs: match what hikari expects for interaction.execute() or interaction.create_initial_response()
        """

        if embed and embed.total_length() == 0:
            # allows for empty embeds
            embed = None

        if embed:
            kwargs["embeds"] = [embed]

        if channel and channel_id:
            raise ValueError("Cannot specify both channel and channel_id.")

        if components and build_components:
            components = Components.clean_action_rows(
                functools.reduce(
                    lambda a, c: c.build(a), components, [bloxlink.rest.build_message_action_row()]
                )
            )

        if channel:
            return await channel.send(
                content, components=components, mentions_everyone=False, role_mentions=False, **kwargs
            )

        if channel_id:
            return await (await bloxlink.rest.fetch_channel(channel_id)).send(
                content, components=components, mentions_everyone=False, role_mentions=False, **kwargs
            )

        if ephemeral:
            kwargs["flags"] = hikari.messages.MessageFlag.EPHEMERAL

        if self.deferred:
            self.deferred = False
            self.responded = True

            kwargs.pop("flags", None)  # edit_initial_response doesn't support ephemeral

            return await self.interaction.edit_initial_response(content, components=components, **kwargs)

        if self.responded:
            return await self.interaction.execute(
                content, components=components, mentions_everyone=False, role_mentions=False, **kwargs
            )

        self.responded = True

        if edit_original:
            return await self.interaction.edit_initial_response(
                content, components=components, mentions_everyone=False, role_mentions=False, **kwargs
            )

        await self.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE,
            content,
            components=components,
            mentions_everyone=False,
            role_mentions=False,
            **kwargs,
        )

        if fetch_message:
            return await self.interaction.fetch_initial_response()

    async def edit_message(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list[hikari.ActionRowComponent] = None,
    ):
        """Edit the original message of the interaction."""

        message = self.interaction.message

        if not message:
            raise ValueError("Cannot edit a message that doesn't exist.")

        if embed:
            message.embeds[0] = embed

        if content:
            message.content = content

        await Components.set_components(message, components=components)

    async def send_modal(self, modal: "modal.Modal"):
        """Send a modal response. This needs to be yielded."""

        # check if the modal was already submitted
        if isinstance(self.interaction, hikari.ModalInteraction):
            return

        self.responded = True

        # we save the command options so we can re-execute the command correctly
        if modal.command_options:
            await redis.set(
                f"modal_command_options:{modal.custom_id}", modal.command_options, expire=timedelta(hours=1)
            )

        return modal.builder

    def send_autocomplete(self, items: list["AutocompleteOption"]):
        """Send an autocomplete response to Discord. Limited to 25 items."""

        return self.interaction.build_response(
            [hikari.impl.AutocompleteChoiceBuilder(c.name.title(), c.value) for c in items[:25]]
        )

    async def send_prompt(self, prompt: Type["Prompt"], custom_id_data: dict = None):
        """Prompt the user with the first page of the prompt."""

        if self.interaction.type not in (
            hikari.InteractionType.APPLICATION_COMMAND,
            hikari.InteractionType.MODAL_SUBMIT,
        ):
            raise NotImplementedError("Can only call prompt() from a slash command or modal.")

        new_prompt = await prompt.new_prompt(
            prompt_instance=prompt,
            interaction=self.interaction,
            response=self,
            command_name=self.interaction.command_name,
            custom_id_data=custom_id_data,
        )

        hash_ = uuid.uuid4().hex
        logging.debug("prompt() hash=%s", hash_)

        return await new_prompt.run_page(
            custom_id_data, hash_=hash_, changing_page=True, initial_prompt=True
        ).__anext__()

    async def send_premium_upsell(self, raise_exception=True):
        """Send a premium upsell message. This cancels out of the command."""

        self.responded = True

        await self.interaction.create_premium_required_response()

        if raise_exception:
            raise CancelCommand()


class Prompt(Generic[T]):
    override_prompt_name: str = None

    def __init__(
        self,
        command_name: str,
        response: Response,
        *,
        custom_id_format: Type[T] = PromptCustomID,
        start_with_fresh_data: bool = True,
    ):
        self.pages: list[Page] = []
        self.current_page_number = 0
        self.current_page: Page = None
        self.response = response
        self.command_name = command_name
        self.prompt_name = self.override_prompt_name or self.__class__.__name__
        self.custom_id_format: Type[T] = custom_id_format
        self._pending_embed_changes = {}
        self.guild_id = response.interaction.guild_id
        self.start_with_fresh_data = start_with_fresh_data

        self.custom_id: T = None  # this is set in prompt.new_prompt()

        self.edited = False

        response.defer_through_rest = True

    @staticmethod
    async def new_prompt(
        prompt_instance: Type["Prompt"],
        interaction: hikari.ComponentInteraction | hikari.CommandInteraction | hikari.ModalInteraction,
        command_name: str,
        response: Response,
        custom_id_data: dict[str, Any] = None,
    ):
        """Return a new initialized Prompt"""

        prompt_instance = prompt_instance or Prompt

        prompt = prompt_instance(
            command_name=command_name,
            response=response,
        )

        prompt.insert_pages(prompt_instance)

        match interaction:
            case hikari.ComponentInteraction():
                await prompt.save_data_from_interaction(interaction)

            case hikari.CommandInteraction():
                if prompt.start_with_fresh_data:
                    await prompt.clear_data()

                prompt.custom_id = prompt.custom_id_format(
                    command_name=command_name,
                    prompt_name=prompt.prompt_name,
                    page_number=0,
                    user_id=response.user_id,
                    prompt_message_id=0,
                    **(custom_id_data or {}),
                )

        return prompt

    @staticmethod
    async def find_prompt(custom_id: Components.BaseCustomID, interaction: hikari.ComponentInteraction | hikari.ModalInteraction, response: Response=None, command:'commands.Command'=None) -> Self | None:
        """Returns the matching prompt from the command."""

        if not command:
            for command_ in filter(lambda c: c.prompts, commands.slash_commands.values()):
                for command_prompt in command_.prompts:
                    try:
                        parsed_custom_id = PromptCustomID.from_str(str(custom_id)) # TODO
                    except (TypeError, IndexError):
                        # Keeps prompts from preventing normal components from firing on iteration.
                        # Since we check for a valid handler
                        continue


                    if (
                        parsed_custom_id.command_name == command_.name
                        and parsed_custom_id.prompt_name in (command_prompt.override_prompt_name, command_prompt.__name__)
                    ):
                        command = command_
                        break

                if command:
                    break

        if not command:
            raise BloxlinkException("No matching command found.")

        for command_prompt in command.prompts:
            try:
                parsed_custom_id = PromptCustomID.from_str(str(custom_id)) # TODO
            except (TypeError, IndexError):
                # Keeps prompts from preventing normal components from firing on iteration.
                # Since we check for a valid handler
                continue

            if (
                parsed_custom_id.command_name == command.name
                and parsed_custom_id.prompt_name in (command_prompt.override_prompt_name, command_prompt.__name__)
            ):
                new_prompt = await command_prompt.new_prompt(
                    prompt_instance=command_prompt,
                    interaction=interaction,
                    response=response or Response(interaction),
                    command_name=command.name,
                )

                return new_prompt

    @staticmethod
    def page(page_details: PromptPageData):
        """Decorator to mark a function as a page."""

        def wrapper(func: Callable):
            func.__page_details__ = page_details
            func.__programmatic_page__ = False
            func.__page__ = True
            return func

        return wrapper

    @staticmethod
    def programmatic_page():
        """Decorator to mark a function as a programmatic page."""

        def wrapper(func: Callable):
            func.__page_details__ = None
            func.__programmatic_page__ = True
            func.__page__ = True
            return func

        return wrapper

    async def build_page(self, page: Page, custom_id_data: dict = None, hash_=None):
        """Build a PromptEmbed from a prompt and page."""

        action_rows: list[Components.Component] = []
        embed = hikari.Embed(
            description=page.details.description,
            title=page.details.title or "Prompt",
        )

        # the message will only exist if this is a component interaction
        if (
            isinstance(self.response.interaction, hikari.ComponentInteraction)
            and not self.custom_id.prompt_message_id
        ):
            self.custom_id.prompt_message_id = self.response.interaction.message.id

        self.custom_id.page_number = page.page_number

        if page.details.components:
            for component in page.details.components:
                print("setting custom id", self.custom_id_format)
                component_custom_id = self.custom_id.set_fields(
                    component_custom_id=component.component_id,
                    prompt_message_id=self.custom_id.prompt_message_id,
                )
                component.custom_id = str(component_custom_id)

            action_rows = Components.clean_action_rows(
                functools.reduce(
                    lambda a, c: c.build(a),
                    page.details.components,
                    [bloxlink.rest.build_message_action_row()],
                )
            )

        if page.details.fields:
            for field in page.details.fields:
                embed.add_field(field.name, field.value, inline=field.inline)

        if page.details.color:
            embed.color = page.details.color

        if self._pending_embed_changes:
            if self._pending_embed_changes.get("description"):
                embed.description = self._pending_embed_changes["description"]
                self._pending_embed_changes.pop("description")

            if self._pending_embed_changes.get("title"):
                embed.title = self._pending_embed_changes["title"]
                self._pending_embed_changes.pop("title")

        return PromptEmbed(
            embed=embed, action_rows=action_rows if action_rows else None, page_number=page.page_number
        )

    def insert_pages(self, prompt: Type["Prompt"]):
        """Get all pages from the prompt.

        This needs to be called OUTSIDE of self to get the class attributes in insertion-order.

        """

        page_number = 0

        for (
            attr_name,
            attr,
        ) in prompt.__dict__.items():  # so we can get the class attributes in insertion-order
            if hasattr(attr, "__page__"):
                if getattr(attr, "__programmatic_page__", False):
                    self.pages.append(
                        Page(
                            func=getattr(self, attr_name),
                            programmatic=True,
                            details=PromptPageData(description="Unparsed programmatic page", components=[]),
                            page_number=page_number,
                        )
                    )
                else:
                    self.pages.append(
                        Page(
                            func=getattr(self, attr_name),
                            details=attr.__page_details__,
                            page_number=page_number,
                        )
                    )

                page_number += 1

    async def populate_programmatic_page(
        self, interaction: hikari.ComponentInteraction, fired_component_id: str | None = None
    ):
        logging.debug("current_page=%s", self.current_page)

        if self.current_page.programmatic:
            generator_or_coroutine = self.current_page.func(interaction, fired_component_id)
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    if not generator_response:
                        continue

                    if isinstance(generator_response, PromptPageData):
                        page_details = generator_response
            else:
                page_details: PromptPageData = await generator_or_coroutine

            self.current_page.details = page_details

    async def entry_point(self, interaction: hikari.ComponentInteraction | hikari.ModalInteraction):
        """Entry point when a component is called. Redirect to the correct page."""


        self.custom_id = self.custom_id_format.from_str(interaction.custom_id)
        self.current_page_number = self.custom_id.page_number
        self.current_page = self.pages[self.current_page_number]

        if interaction.user.id != self.custom_id.user_id:
            yield await self.response.send_first(
                f"This prompt can only be used by <@{self.custom_id.user_id}>.", ephemeral=True
            )
            return

        hash_ = uuid.uuid4().hex
        logging.debug("entry_point() hash=%s", hash_)

        async for generator_response in self.run_page(hash_=hash_):
            if isinstance(generator_response, hikari.Message):
                continue
            logging.debug(hash_, "generator_response entry_point()", generator_response)
            yield generator_response

    async def run_page(
        self, custom_id_data: dict = None, hash_=None, changing_page=False, initial_prompt=False
    ):
        """Run the current page."""

        hash_ = hash_ or uuid.uuid4().hex

        self.current_page = self.pages[self.current_page_number]

        logging.debug(
            hash_, "run_page() current page=", self.current_page_number, self.current_page.details.title
        )

        generator_or_coroutine = self.current_page.func(
            self.response.interaction,
            self.custom_id.component_custom_id if self.custom_id and not changing_page else None,
        )

        # if this is a programmatic page, we need to run it first
        if self.current_page.programmatic:
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    if not generator_response:
                        continue

                    if isinstance(generator_response, PromptPageData):
                        page_details = generator_response
                    else:
                        yield generator_response
            else:
                page_details: PromptPageData = await generator_or_coroutine

            self.current_page.details = page_details
            built_page = await self.build_page(self.current_page, custom_id_data, hash_)

            # this stops the page from being sent if the user has already moved on
            if self.current_page.page_number != self.current_page_number or self.current_page.edited:
                return

            # prompt() requires below send_first, but entry_point() doesn't since it calls other functions
            if initial_prompt:
                yield await self.response.send_first(
                    embed=built_page.embed,
                    components=built_page.action_rows,
                    edit_original=True,
                    build_components=False,
                )
                return

        logging.debug(
            hash_,
            "building page run_page(), current page=",
            self.current_page_number,
            self.current_page.details.title,
        )

        if changing_page:
            # we only build the page (embed) if we're changing pages

            built_page = await self.build_page(self.current_page, custom_id_data, hash_)

            logging.debug(hash_, "run_page() built page", built_page.embed.title)

            if built_page.page_number != self.current_page_number:
                return

            yield await self.response.send_first(
                embed=built_page.embed,
                components=built_page.action_rows,
                edit_original=True,
                build_components=False,
            )

        if not self.current_page.programmatic:
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    if generator_response:
                        # if not changing_page and isinstance(generator_or_coroutine, PromptPageData):
                        #     continue

                        yield generator_response
            else:
                async_result = await generator_or_coroutine
                if async_result:
                    yield async_result

    async def current_data(self, *, key_name: str = None, raise_exception: bool = True):
        """Get the data for the current page from Redis."""

        redis_data = await redis.get(
            f"prompt_data:{self.command_name}:{self.prompt_name}:{self.response.interaction.user.id}"
        )

        if not redis_data:
            if raise_exception:
                raise CancelCommand("Previous data not found. Please restart this command.")

            return {}

        return json.loads(redis_data).get(key_name) if key_name else json.loads(redis_data)

    async def save_data_from_interaction(self, interaction: hikari.ComponentInteraction):
        """Save the data from the interaction from the current page to Redis."""

        custom_id = PromptCustomID.from_str(interaction.custom_id)
        component_custom_id = custom_id.component_custom_id

        data = await self.current_data(raise_exception=False)
        data[component_custom_id] = Components.component_values_to_dict(interaction)

        await redis.set(
            f"prompt_data:{self.command_name}:{self.prompt_name}:{interaction.user.id}",
            data,
            expire=timedelta(hours=1),
        )

    async def save_stateful_data(self, ex: int = 3600, **save_data):
        """Save custom data for this prompt to Redis."""

        data = await self.current_data(raise_exception=False) or {}
        data.update(save_data)

        await redis.set(
            f"prompt_data:{self.command_name}:{self.prompt_name}:{self.response.interaction.user.id}",
            data,
            expire=ex,
        )

    async def clear_data(self, *remove_data_keys: list[str]):
        """Clear the data for the current page from Redis."""

        if remove_data_keys:
            data = await self.current_data(raise_exception=False) or {}

            for key in remove_data_keys:
                data.pop(key, None)

            await redis.set(
                f"prompt_data:{self.command_name}:{self.prompt_name}:{self.response.interaction.user.id}",
                data,
                expire=timedelta(hours=1),
            )
        else:
            await redis.delete(
                f"prompt_data:{self.command_name}:{self.prompt_name}:{self.response.interaction.user.id}"
            )

    async def previous(self, _content: str = None):
        """Go to the previous page of the prompt."""

        self.current_page_number -= 1

        return await self.run_page(changing_page=True).__anext__()

    async def next(self, _content: str = None):
        """Go to the next page of the prompt."""

        self.current_page_number += 1

        return await self.run_page(changing_page=True).__anext__()

    async def go_to(self, page: Callable, **kwargs):
        """Go to a specific page of the prompt."""

        for this_page in self.pages:
            if this_page.func == page:
                self.current_page_number = this_page.page_number
                break
        else:
            raise PageNotFound(f"Page {page} not found.")

        hash_ = uuid.uuid4().hex
        logging.debug("go_to() hash=%s", hash_)

        if kwargs:
            for attr_name, attr_value in kwargs.items():
                self._pending_embed_changes[attr_name] = attr_value

        return await self.run_page(hash_=hash_, changing_page=True).__anext__()

    async def finish(self, *, disable_components=True):
        """Finish the prompt."""

        await self.clear_data()
        await self.ack()

        if disable_components:
            if self.custom_id.prompt_message_id:
                message = await bloxlink.rest.fetch_message(
                    self.response.interaction.channel_id, self.custom_id.prompt_message_id
                )
            else:
                message = self.response.interaction.message

            for action_row in message.components:
                for component in action_row.components:
                    component.is_disabled = True

            await Components.set_components(message, components=message.components)

    async def ack(self):
        """Acknowledge the interaction. This should be used if no response will be sent."""

        self.current_page.edited = True

        if not self.response.responded:
            # this stops the interaction from erroring
            await self.response.interaction.create_initial_response(
                hikari.ResponseType.DEFERRED_MESSAGE_UPDATE
            )

    async def edit_component(self, **component_data):
        """Edit a component on the current page."""

        hash_ = uuid.uuid4().hex
        logging.debug("edit_component() hash=%s", hash_)

        if self.current_page.programmatic:
            await self.populate_programmatic_page(self.response.interaction)

        for component in self.current_page.details.components:
            for component_custom_id, kwargs in component_data.items():
                if component.component_id == component_custom_id:
                    for attr_name, attr_value in kwargs.items():
                        if attr_name == "component_id":
                            component.component_id = attr_value
                        else:
                            setattr(component, attr_name, attr_value)

        built_page = await self.build_page(self.current_page, hash_=hash_)

        self.current_page.edited = True

        await bloxlink.rest.edit_message(
            self.response.interaction.channel_id,
            self.custom_id.prompt_message_id,
            embed=built_page.embed,
            components=built_page.action_rows,
        )

    async def edit_page(self, components: dict=UNDEFINED, content: str=None, embed: hikari.Embed=UNDEFINED, **new_page_data):
        """Edit the current page."""

        hash_ = uuid.uuid4().hex
        logging.debug("edit_page() hash=%s", hash_)

        self.edited = True

        if self.current_page.programmatic:
            await self.populate_programmatic_page(self.response.interaction)

        for attr_name, attr_value in new_page_data.items():
            self._pending_embed_changes[attr_name] = attr_value

        if components:
            for component_custom_id, kwargs in components.items():
                for component in self.current_page.details.components:
                    if component.component_id == component_custom_id:
                        for attr_name, attr_value in kwargs.items():
                            if attr_name == "component_id":
                                component.component_id = attr_value
                            else:
                                setattr(component, attr_name, attr_value)

        built_page = await self.build_page(self.current_page, hash_=hash_)

        await bloxlink.rest.edit_message(
            self.response.interaction.channel_id,
            self.custom_id.prompt_message_id,
            content=content,
            embed=built_page.embed if embed is UNDEFINED else embed,
            components=built_page.action_rows if components is not UNDEFINED else None,
        )
