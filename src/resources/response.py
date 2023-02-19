import hikari
from .emojis import LOADING_EMOJI


class Response:
    def __init__(self, interaction: hikari.CommandInteraction):
        self.interaction = interaction
        self.responded = False
        self.deferred = False

    async def send(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        **kwargs):

        if self.responded:
            await self.interaction.execute(content, embed=embed, component=components, **kwargs)
        else:
            self.responded = True

            await self.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                content, embed=embed, component=components, **kwargs
            )
            
    async def edit(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        **kwargs):

        if self.responded or self.deferred:
            await self.interaction.edit_initial_response(content, embed=embed, component=components, **kwargs)
        else:
            raise RuntimeError("Cannot edit initial message before one has been sent.")
        
    async def edit_or_send(self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        **kwargs):
        '''Helper function to edit or send a message depending if one has already been sent.'''
        
        if self.responded or self.deferred:
            await self.edit(content, embed, components, **kwargs)
        else:
            await self.send(content, embed, components, **kwargs)

    async def loading(self, content: str):
        '''Responds to the message with a seemingly deferred loading message to the user.'''
        await self.edit_or_send(embed = hikari.Embed(description=f"{LOADING_EMOJI}\t  {content}", color="#2f3136"))

