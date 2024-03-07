import math
from typing import Any, Sequence, Coroutine, Literal

import hikari

from resources.constants import UNICODE_LEFT, UNICODE_RIGHT
from resources.ui.components import CommandCustomID, Component, Button, Separator


class PaginatorCustomID(CommandCustomID):
    """Represents the custom ID for the paginator"""

    page_number: int = 0

    def model_post_init(self, __context: Any) -> None:
        self.type = "paginator"

class PaginatorCancelCustomID(CommandCustomID):
    """Represents the custom ID for the paginator cancel button"""

    type: Literal["cancel"] = "cancel"


class Paginator[T: PaginatorCustomID]:
    """Dynamically create prompts that may require more than one embed to cleanly show data."""

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        items: Sequence[T],
        page_number: int=0,
        max_items: int=10,
        custom_formatter: Coroutine | None=None,
        component_generation: Coroutine | None=None,
        custom_id_format: PaginatorCustomID = PaginatorCustomID,
        item_filter: Coroutine | None = None,
        include_cancel_button: bool=False,
    ):
        """Create a paginator handler.

        Args:
            guild_id: The ID of the guild where the command that required pagination was ran.
            user_id: The ID of the user who ran the command.
            items (list): The list of items that need to be paginated.
            command_name (str): The name of the command. Used for component custom IDs.
            page_number (int, optional): The current page number. Defaults to 0.
            max_items (int, optional): The maximum number of items per page. Defaults to 10.
            custom_formatter (Callable, optional): The formatter to use to style the embed. Defaults to None.
                Expects the arguments: (page_number: int, items: list, guild_id: int | str, max_pages: int)
                Where the items are only the items for this page.
            component_generation (Callable, optional): A function to generate the components that will be added
                to this prompt in addition to the page flip buttons. Defaults to None.
                Expects the arguments: (items: list, user_id: str | int, extra_custom_ids: str)
            extra_custom_ids (str, optional): This will be passed to the component_generation callable. Defaults to "".
                Used to provide additional information to the additional components dynamically.
            item_filter (Callable, optional): Callable used to filter the entire item list. Defaults to None.
            include_cancel_button (bool, optional): Optionally include a button to cancel this prompt. Defaults to False.
        """

        self.guild_id = guild_id
        self.user_id = user_id

        self.page_number = page_number

        self.items = items if not item_filter else item_filter(items)
        self.max_pages = math.ceil(len(self.items) / max_items)
        self.max_items = max_items

        self.custom_formatter = custom_formatter
        self.component_generation = component_generation

        self.custom_id_format = custom_id_format
        self.include_cancel_button = include_cancel_button

    @property
    def current_items(self) -> list[T]:
        """Get the items that apply to this page number."""

        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )

        return self.items[offset:max_items]

    @property
    async def embed(self) -> hikari.Embed:
        """The embed that will be displayed to the user."""

        if self.custom_formatter:
            embed: hikari.Embed = await self.custom_formatter(
                self.page_number, self.current_items, self.guild_id, self.max_pages
            )
        else:
            embed = hikari.Embed(description="\n".join(str(item) for item in self.current_items))
            embed.set_footer(f"Page {self.page_number + 1}/{self.max_pages or 1}")

        self._embed = embed

        return embed

    @embed.setter
    def embed(self, value: hikari.Embed):
        self._embed = value

    @property
    async def components(self) -> list[Component]:
        """The components for this prompt."""

        components: list[Component] = [
            Button(
                custom_id = self.custom_id_format.set_fields(
                    page_number=self.page_number-1,
                    section="page"
                ),
                label=UNICODE_LEFT,
                is_disabled=self.page_number <= 0,
                style=Button.ButtonStyle.SECONDARY
            ),
            Button(
                custom_id = self.custom_id_format.set_fields(
                    page_number=self.page_number+1,
                    section="page"
                ),
                label=UNICODE_RIGHT,
                is_disabled=self.page_number + 1 >= self.max_pages,
                style=Button.ButtonStyle.SECONDARY
            ),
        ]

        if self.include_cancel_button:
            components.append(
                Button(
                    custom_id = self.custom_id_format.set_fields(
                        section="cancel"
                    ),
                    label="Cancel",
                    style=Button.ButtonStyle.SECONDARY
                ),
            )

        components.append(Separator())

        if self.component_generation:
            generated_components = await self.component_generation(
                self.current_items,
                self.custom_id_format,
            )

            if generated_components:
                components.extend(generated_components)

        self._components = components

        return components

    @components.setter
    def components(self, value: Sequence[Component]):
        self._components = value
