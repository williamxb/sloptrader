import discord
from discord.ext import commands
from discord import app_commands
import database
import logging
from typing import List, Optional

try:
    from autotrader_data import CAR_DATA
except ImportError:
    CAR_DATA = {}

logger = logging.getLogger('discord')

from autotrader import AutoTraderClient
at_client = AutoTraderClient()

async def make_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    makes = list(CAR_DATA.keys())
    return [
        app_commands.Choice(name=make, value=make)
        for make in makes if current.lower() in make.lower()
    ][:25]

async def model_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    make = interaction.namespace.make
    
    if make and make in CAR_DATA:
        models = CAR_DATA[make]
    else:
        models = []

    return [
        app_commands.Choice(name=model, value=model)
        for model in models if current.lower() in model.lower()
    ][:25]

async def trim_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    make = interaction.namespace.make
    model = interaction.namespace.model
    
    if not make or not model:
        return []
        
    trims = await at_client.fetch_trims(make, model)
    return [
        app_commands.Choice(name=trim, value=trim)
        for trim in trims if current.lower() in trim.lower()
    ][:25]

class Commands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addsearch", description="Add a new AutoTrader search alert to this channel")
    @app_commands.describe(
        make="The make of the car",
        model="The model of the car",
        trim="The trim (optional, e.g. M Sport)",
        min_year="Minimum year",
        max_year="Maximum year",
        postcode="Your postcode (optional, defaults to sw1a1aa)",
        write_off="Write-off status (defaults to Include All)"
    )
    @app_commands.autocomplete(make=make_autocomplete, model=model_autocomplete, trim=trim_autocomplete)
    @app_commands.choices(write_off=[
        app_commands.Choice(name="Include All", value="Include"),
        app_commands.Choice(name="Exclude All", value="Exclude"),
        app_commands.Choice(name="Only Show Write-offs", value="Only"),
    ])
    async def addsearch(
        self, 
        interaction: discord.Interaction, 
        make: str, 
        model: Optional[str] = None, 
        trim: Optional[str] = None,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        max_mileage: Optional[int] = None,
        postcode: Optional[str] = "sw1a1aa",
        write_off: app_commands.Choice[str] = None
    ):
        write_off_val = write_off.value if write_off else "Include"
        filters = []
        
        # Build the exact filter array expected by the AutoTrader GraphQL API
        filters.append({"filter": "make", "selected": [make]})
        
        if model:
            filters.append({"filter": "model", "selected": [model]})
        if trim:
            filters.append({"filter": "aggregated_trim", "selected": [trim]})
        
        if min_year or max_year:
            if min_year:
                filters.append({"filter": "min_year_manufactured", "selected": [str(min_year)]})
            if max_year:
                filters.append({"filter": "max_year_manufactured", "selected": [str(max_year)]})
                
        if min_price:
            filters.append({"filter": "min_price", "selected": [str(min_price)]})
        if max_price:
            filters.append({"filter": "max_price", "selected": [str(max_price)]})
            
        if max_mileage:
            filters.append({"filter": "maximum_mileage", "selected": [str(max_mileage)]})
            
        if postcode:
            filters.append({"filter": "postcode", "selected": [postcode]})

        # Always add total price search type
        filters.append({"filter": "price_search_type", "selected": ["total"]})

        # Save to database mapped to this channel
        search_id = database.add_search(interaction.channel_id, filters, write_off_val)
        
        await interaction.response.send_message(f"✅ Search #{search_id} added successfully! I will post new cars here.")

    @app_commands.command(name="listsearches", description="List all active searches for this channel")
    async def listsearches(self, interaction: discord.Interaction):
        searches = database.get_searches_for_channel(interaction.channel_id)
        if not searches:
            await interaction.response.send_message("No active searches in this channel. Use `/addsearch` to create one!")
            return
            
        response = "**Active Searches in this channel:**\n"
        for s in searches:
            # Format the filters nicely
            filter_text = ", ".join([f"{f['filter']}: {f['selected'][0]}" for f in s['filters'] if f['filter'] not in ('postcode', 'price_search_type')])
            response += f"**ID {s['id']}**: {filter_text} | **Write-offs:** {s.get('write_off', 'Exclude')}\n"
            
        await interaction.response.send_message(response)

    @app_commands.command(name="removesearch", description="Remove an active search from this channel")
    @app_commands.describe(search_id="The ID of the search to remove (find via /listsearches)")
    async def removesearch(self, interaction: discord.Interaction, search_id: int):
        success = database.remove_search(search_id, interaction.channel_id)
        if success:
            await interaction.response.send_message(f"✅ Search #{search_id} has been removed.")
        else:
            await interaction.response.send_message(f"❌ Could not find Search #{search_id} in this channel.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Commands(bot))
