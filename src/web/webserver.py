import logging
from blacksheep import Application, get

from blacksheep.server.controllers import APIController, Controller

application = Application()


@application.after_start
async def after_start_print_routes(application: Application):
    """Prints all registered routes after the webserver starts"""

    logging.info(f"Routes registered: {dict(application.router.routes)}")

@get("/")
async def root():
    """Returns a 200 OK when the webserver is running"""

    return "The webserver is alive & responding."
