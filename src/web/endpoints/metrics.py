import asyncio
from asgi_prometheus import PrometheusMiddleware
from prometheus_client import Counter, Histogram
from resources.commands import slash_commands
from ..webserver import webserver


prometheus = PrometheusMiddleware(webserver, metrics_url="/", group_paths=['/'])


commands_counter = Counter('commands_counter', 'Number of commands registered')
# commands_histogram = Histogram('commands_histogram', 'Time spent on commands')



async def main():
    """Starts/records all the Prometheus counters"""

    commands_counter.inc(len(slash_commands))


asyncio.run(main())
webserver.mount("/metrics", prometheus)
