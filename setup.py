# BLOXLINK INSTALLATION FILE

import os
from subprocess import STDOUT, PIPE, Popen
# import requests


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

def step(*steps: tuple[str], start_with_clear_console: bool=False, spawn_processes: list[tuple[callable, str]] = ()) -> str:
    if start_with_clear_console:
        clear_console()

    for step in steps[:-1]:
        print(step, flush=True)

    user_input = input(steps[len(steps)-1]).lower()

    for condition, command in spawn_processes:
        if condition(user_input):
            spawn_process(command)

    return user_input


step(
    "Welcome to the Bloxlink Installation File.",
    "This setup will populate a local .env file that you can use with Bloxlink.",
    "Press Enter to continue.",
    start_with_clear_console=True
)

step(
    "First, you want to make sure you created a Discord application.",
    "Go to https://discord.com/developers/applications and create an application.",
    "Press Enter to continue.",
    start_with_clear_console=True
)

discord_client_id = step(
    "What is your Discord Application ID? You can find this in the General Information tab. "
)

discord_public_key = step(
    "What is your Discord public key? You can find this in the General Information tab. "
)

discord_token = step(
    "What is the Discord token for your application? You can find this in the Bot tab. ",
)

has_existing_mongodb = step(
    "Do you already have a MongoDB database setup? If not, a database will be created via Docker: y/n: ",
    start_with_clear_console=True,
    spawn_processes=[
        (lambda c: c in ("n", "no"), "docker-compose up -d mongodb")
    ]
)

has_existing_redis = step(
    "Do you already have a Redis database setup? If not, a database will be created via Docker: y/n: ",
    start_with_clear_console=True,
    spawn_processes=[
        (lambda c: c in ("n", "no"), "docker-compose up -d redis")
    ]
)

