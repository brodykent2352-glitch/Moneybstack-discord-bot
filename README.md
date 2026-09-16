# Discord Ticket + Welcome + Giveaway + Staff Bot

## Features
- Persistent Ticket Bot-style panel with Create Ticket / Close Ticket buttons
- Private ticket channels with optional support role and category
- Welcome embeds when members join
- Giveaway system with button entry, automatic ending, winner selection, and reroll
- Staff application panel with a Discord modal
- Staff application review buttons
- Persistent data stored in `bot_data.json`
- Slash commands

## Slash commands
- `/ticketpanel` - sends the ticket panel
- `/staffpanel` - sends the staff application panel
- `/giveaway duration:<minutes> winners:<number> prize:<text>` - starts a giveaway
- `/reroll giveaway_id:<id>` - rerolls a finished giveaway
- `/ping` - latency check

## Setup
1. Install Python 3.10+.
2. Run:
   `pip install -r requirements.txt`
3. Rename `.env.example` to `.env`.
4. Put your Discord bot token in `DISCORD_TOKEN`.
5. Fill in the Discord role/channel/category IDs.
6. Invite the bot with the `bot` and `applications.commands` scopes.
7. Give it permissions to manage channels, send messages, embed links, read message history, and view channels.
8. Run:
   `python bot.py`

## Discord Developer Portal
Enable the **Server Members Intent** and **Message Content Intent** under Bot settings.

The bot stores giveaway entries and application records in `bot_data.json`.
