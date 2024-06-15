# BLOXLINK INSTALLATION FILE

import os
from subprocess import STDOUT, PIPE, Popen
from rich.console import Console
from rich.table import Table
# import requests
from dotenv import load_dotenv, set_key

load_dotenv(f"{os.getcwd()}/.env")

console = Console()
user_config: dict[str, str] = {
    "DISCORD_APPLICATION_ID": os.environ.get("DISCORD_APPLICATION_ID"),
    "DISCORD_PUBLIC_KEY": os.environ.get("DISCORD_PUBLIC_KEY"),
    "DISCORD_TOKEN": os.environ.get("DISCORD_TOKEN"),
    "MONGO_HOST": os.environ.get("MONGO_HOST", "mongodb"),
    "MONGO_PORT": os.environ.get("MONGO_PORT", "27017"),
    "MONGO_USER": os.environ.get("MONGO_USER", "admin"),
    "MONGO_PASSWORD": os.environ.get("MONGO_PASSWORD", "admin123"),
    "REDIS_HOST": os.environ.get("REDIS_HOST", "redis"),
    "REDIS_PORT": os.environ.get("REDIS_PORT", "6379"),
    "REDIS_PASSWORD": os.environ.get("REDIS_PASSWORD", "admin123"),
    "HOST": os.environ.get("HOST", "0.0.0.0"),
    "PORT": os.environ.get("PORT", "8010"),
    "HTTP_BOT_AUTH": os.environ.get("HTTP_BOT_AUTH", "oof"),
    "BOT_API": os.environ.get("BOT_API", "http://bot-api/api"),
    "BOT_API_AUTH": os.environ.get("BOT_API_AUTH", "oof"),
}

def spawn_process(command: str, hide_output: bool=True):
    """Spawn a process and optionally wait for the output"""

    with Popen(
        command.split(" "),
        stdin=PIPE,
        stdout=PIPE,
        stderr=STDOUT,
    ) as p:
        if not hide_output:
            for line in p.stdout:
                print(line.decode("utf-8"), end="")

            p.wait()

def clear_console():
    """Clear the console"""

    spawn_process("cls" if os.name=="nt" else "clear", False)

def step(*steps: tuple[str | tuple[str]], start_with_clear_console: bool=False, spawn_processes: list[tuple[callable, str]] = ()) -> str:
    """Ask the user for input and save it to the config."""

    if start_with_clear_console:
        clear_console()

    input_step = steps[-1]

    for step_ in steps[:-1]:
        if isinstance(step_, tuple):
            console.print(step_[0], style=step_[1])
        else:
            console.print(step_)

    try:
        if isinstance(input_step, str):
            user_input = console.input(input_step)
        else:
            user_input = console.input(input_step[0])

            if user_input:
                user_config[input_step[2]] = user_input

        for condition, command in spawn_processes:
            if condition(user_input.lower()):
                spawn_process(command)
    except KeyboardInterrupt:
        # don't print trace back
        exit()

    return user_input

def ask_for_save_config():
    """Ask the user whether they want to save, and if so, save."""

    table = Table(title=".env", show_header=True, header_style="bold magenta")

    table.add_column("Name")
    table.add_column("Value", width=50)

    for key, value in user_config.items():
        table.add_row(key, f'"{value}"' if value else '""')

    console.print(table)

    save_config = step(
        "Save .env? [bold cyan]y/N[/bold cyan]: "
    )

    clear_console()

    if save_config.lower() in ("y", "yes"):
        with open(f"{os.getcwd()}/.env", "w", encoding="utf-8"):
            for key, value in user_config.items():
                set_key(f"{os.getcwd()}/.env", key, value)

        console.print("Bloxlink HTTP is now configured. Please double-check the .env file and update accordingly.", style="bold green")
    else:
        console.print("Config not saved.")

    console.print("\n")
    console.print(
        "IMPORTANT: you must run a reverse proxy to accept requests over HTTPS.\n"
        "You can run [purple]ssh -R 80:localhost:8010 serveo.net[/purple] in your terminal to start the reverse proxy. "
        "You can use any forwarding service; localhost.run and ngrok are other alternatives.\n\n"
        "[purple]Copy the URL, start the bot web server and paste it in your Discord dashboard under General Information -> Interactions Endpoint Url.[/purple]",
        "You can run the bot using [purple]docker-compose up bloxlink-http[/purple]."
    )


def ask_to_run_bot():
    """Ask the user whether they want to run the bot."""

    run_bot = step(
        "Run the bot? [bold cyan]y/N[/bold cyan]: ",
    )

    if run_bot.lower() in ("y", "yes"):
        console.print("Starting bot...", style="bold green")
        spawn_process("docker-compose up bloxlink-http", hide_output=False)


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

step(
    ("What is your [purple]Discord Application ID?[/purple] You can find this in the General Information tab. ", None, "DISCORD_APPLICATION_ID")
)

step(
    ("What is your [purple]Discord public key?[/purple] You can find this in the General Information tab. ", None, "DISCORD_PUBLIC_KEY")
)

step(
    ("What is the [purple]Discord token[/purple] for your application? You can find this in the Bot tab. ", None, "DISCORD_TOKEN")
)

step(
    "Do you already have a [purple]MongoDB[/purple] database setup? If not, a database will be created via Docker: [bold cyan]Y/n[/bold cyan]: ",
    start_with_clear_console=True,
    spawn_processes=[
        (lambda c: c in ("n", "no"), "docker-compose up -d mongodb")
    ]
)

step(
    "Do you already have a [purple]Redis[/purple] database setup? If not, a database will be created via Docker: [bold cyan]Y/n[/bold cyan]: ",
    start_with_clear_console=True,
    spawn_processes=[
        (lambda c: c in ("n", "no"), "docker-compose up -d redis")
    ]
)

clear_console()
ask_for_save_config()

ask_to_run_bot()
