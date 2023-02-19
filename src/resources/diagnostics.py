from os import environ as env
from threading import Lock
from hikari import Embed, CommandInteraction
from .utils import fetch
from .secrets import REPORT_WEBHOOK_URL
from types import TracebackType, CodeType
import requests
import inspect


async def report_error(ex: Exception, message: str | None = None):
    # TODO: Implement sentry logging.
    try:
        raise NotImplementedError()
    except Exception as ex:
        print(f"Failed to report an exception: {ex}")
    else:
        print(f"An exception has been reported: {message if message else 'No message provided.'}")

    