import discord
import os
from dotenv import load_dotenv

def run_bot():
    load_dotenv() # Loads the .env file
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')

    intents = discord.Intents.default()
    intents.message_content = True # A required setting
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'{client.user} has connected to Discord!')

    client.run(TOKEN)