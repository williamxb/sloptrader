import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
import logging
from database import setup_db

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Setup Database
setup_db()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    logger.info('------')

async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("No DISCORD_TOKEN found in environment variables. Please set it in a .env file.")
        return

    # Check if car data needs generating (first startup)
    if not os.path.exists("autotrader_data.py"):
        logger.info("First startup detected: Generating AutoTrader car data dictionary. This will take ~30 seconds...")
        try:
            import scripts.update_car_data
            await scripts.update_car_data.main()
            logger.info("Car data generated successfully!")
        except Exception as e:
            logger.error(f"Failed to generate car data: {e}")

    async with bot:
        await bot.load_extension("cogs.notifier")
        await bot.load_extension("cogs.commands")
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
