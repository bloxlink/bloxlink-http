from enum import Enum
import aiohttp, asyncio

from requests.utils import requote_uri
from .secrets import PROXY_URL, BOT_API, BOT_API_AUTH
from .exceptions import RobloxAPIError, RobloxDown, RobloxNotFound
from json import loads

__all__ = (
    "fetch",
    "ReturnType"
)

session = None

class ReturnType(Enum):
    JSON = 1
    TEXT = 2
    BYTES = 3

async def fetch(
    method: str,
    url: str,
    params: dict = None,
    headers: dict = None,
    body: dict = None,
    return_data: ReturnType = ReturnType.JSON,
    raise_on_failure: bool = True,
    timeout: float = 20,
    proxy: bool = True
):
    params  = params or {}
    headers = headers or {}
    new_json = {}
    proxied = False

    global session

    if not session:
        session = aiohttp.ClientSession()

    is_roblox = "roblox.com" in url
    is_bot_api = BOT_API in url

    if proxy and PROXY_URL and is_roblox:
        old_url = url
        new_json["url"] = url
        new_json["data"] = body or {}
        url = PROXY_URL
        proxied = True
        method = "POST"

    else:
        new_json = body
        old_url = url

    if is_bot_api:
        headers["Authorization"] = BOT_API_AUTH

    url = requote_uri(url)

    for k, v in params.items():
        if isinstance(v, bool):
            params[k] = "true" if v else "false"

    try:
        async with session.request(method, url, json=new_json, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=timeout) if timeout else None) as response:
            if proxied:
                try:
                    response_json = await response.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    raise RobloxAPIError("Proxy server returned invalid JSON.")

                response_body = response_json["req"]["body"]
                response_status = response_json["req"]["status"]
                response.status = response_status

                if not isinstance(response_body, dict):
                    try:
                        response_body_json = loads(response_body)
                    except:
                        pass
                    else:
                        response_body = response_body_json
            else:
                response_status = response.status
                response_body = None

            if raise_on_failure:
                # TODO: These Roblox specific errors should only be omitted whee is_roblox.
                if response_status == 503:
                    raise RobloxDown()
                elif response_status == 404:
                    raise RobloxNotFound()
                elif response_status >= 400:
                    if proxied:
                        print(old_url, response_body, flush=True)
                    else:
                        print(old_url, await response.text(), flush=True)
                    raise RobloxAPIError()

                if return_data is ReturnType.JSON:
                    if not proxied:
                        try:
                            response_body = await response.json()
                        except aiohttp.client_exceptions.ContentTypeError:
                            raise RobloxAPIError()

                    if isinstance(response_body, dict):
                        return response_body, response
                    else:
                        return {}, response

            if return_data is ReturnType.TEXT:
                if proxied:
                    return str(response_body), response

                text = await response.text()

                return text, response

            elif return_data is ReturnType.JSON:
                if proxied:
                    if not isinstance(response_body, dict):
                        print("Roblox API Error: ", old_url, type(response_body), response_body, flush=True)

                        if raise_on_failure:
                            raise RobloxAPIError()

                    return response_body, response

                try:
                    json = await response.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    print(old_url, await response.text(), flush=True)

                    raise RobloxAPIError

                return json, response

            elif return_data is ReturnType.BYTES:
                return await response.read(), response

            return response

    except asyncio.TimeoutError:
        print(f"URL {old_url} timed out", flush=True)
        raise RobloxDown()