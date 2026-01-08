# Palladium Discord Bot

Generates Palladium/Road Hogs-style attributes + bonuses, animal type, and mutant background via a Discord slash command.

## Setup
- Python 3.10+ recommended (works on 3.12)
- Create a bot in Discord Developer Portal and get the Bot Token
- Invite with scopes: bot + applications.commands

## Install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

## Configure
cp .env.example .env
edit .env and set DISCORD_TOKEN and (optionally) GUILD_ID

## Run
source .venv/bin/activate
python bot.py
