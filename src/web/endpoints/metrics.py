import asyncio
from asgi_prometheus import PrometheusMiddleware
from prometheus_client import Histogram, Gauge
from resources.commands import slash_commands
from ..webserver import application


prometheus = PrometheusMiddleware(application, metrics_url="/", group_paths=['/'])


commands_gauge = Gauge('commands_count', 'Number of commands registered')
# commands_histogram = Histogram('commands_histogram', 'Time spent on commands')



async def main():
    """Starts/records all of the Prometheus counters"""

    commands_gauge.set(len(slash_commands))


asyncio.run(main())
application.mount("/metrics", prometheus)
