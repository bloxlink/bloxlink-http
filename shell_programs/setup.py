# BLOXLINK INSTALLATION FILE

import os
from subprocess import STDOUT, PIPE, Popen
from rich.console import Console
from rich.table import Table
import requests

console = Console()

user_config: dict[str, str] = {
    "DISCORD_APPLICATION_ID": "",
    "DISCORD_PUBLIC_KEY": "",
    "DISCORD_TOKEN": "",
    "MONGO_URL": "",
    "REDIS_URL": "",
    "HOST": "0.0.0.0",
    "PORT": "8010",
    "HTTP_BOT_AUTH": "CHANGE_ME",
    "BOT_API": "",
    "BOT_API_AUTH": "CHANGE_ME",
}

def spawn_process(command: str, hide_output: bool=True):
    p = Popen(
        command.split(" "),
        stdin=PIPE,
        stdout=PIPE,
        stderr=STDOUT,
    )

    if not hide_output:
        for line in p.stdout:
            print(line.decode("utf-8"), end="")

        p.wait()

def clear_console():
    spawn_process("cls" if os.name=="nt" else "clear", False)

def step(*steps: tuple[str | tuple[str]], start_with_clear_console: bool=False, spawn_processes: list[tuple[callable, str]] = ()) -> str:
    if start_with_clear_console:
        clear_console()

    input_step = steps[-1]

    for step in steps[:-1]:
        if isinstance(step, tuple):
            console.print(step[0], style=step[1])
        else:
            console.print(step)

    if isinstance(input_step, str):
        user_input = console.input(input_step)
    else:
        user_input = console.input(input_step[0])
        user_config[input_step[2]] = user_input

    for condition, command in spawn_processes:
        if condition(user_input.lower()):
            spawn_process(command)

    return user_input

def print_config():
    table = Table(title=".env", show_header=True, header_style="bold magenta")

    table.add_column("Name")
    table.add_column("Value")

    for key, value in user_config.items():
        table.add_row(key, f'"{value}"' if value else '""')

    console.print(table)

step(
    ("Welcome to the Bloxlink Installation File.", "bold red"),
    "This setup will populate a local .env file that you can use with Bloxlink.",
    "Press [bold cyan]Enter[/bold cyan] to continue.",
    start_with_clear_console=True
)

step(
    "First, you want to make sure you created a Discord application.",
    "Go to https://discord.com/developers/applications and create an application.",
    "Press [bold cyan]Enter[/bold cyan] to continue.",
    start_with_clear_console=True
)

discord_client_id = step(
    ("What is your [purple]Discord Application ID?[/purple] You can find this in the General Information tab. ", None, "DISCORD_APPLICATION_ID")
)

discord_public_key = step(
    ("What is your [purple]Discord public key?[/purple] You can find this in the General Information tab. ", None, "DISCORD_PUBLIC_KEY")
)

discord_token = step(
    ("What is the [purple]Discord token[/purple] for your application? You can find this in the Bot tab. ", None, "DISCORD_TOKEN")
)

step(
    "Do you already have a [purple]MongoDB[/purple] database setup? If not, a database will be created via Docker: [bold cyan]y/n[/bold cyan]: ",
    start_with_clear_console=True,
    spawn_processes=[
        (lambda c: c in ("n", "no"), "docker-compose up -d mongodb")
    ]
)

step(
    "Do you already have a [purple]Redis[/purple] database setup? If not, a database will be created via Docker: [bold cyan]y/n[/bold cyan]: ",
    start_with_clear_console=True,
    spawn_processes=[
        (lambda c: c in ("n", "no"), "docker-compose up -d redis")
    ]
)

clear_console()
print_config()