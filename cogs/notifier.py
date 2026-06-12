import discord
from discord.ext import commands, tasks
import logging
from autotrader import AutoTraderClient
from database import is_advert_seen, mark_advert_seen, get_all_searches
import os

logger = logging.getLogger('discord')

class Notifier(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.at_client = AutoTraderClient()
        self.check_autotrader.start()

    def cog_unload(self):
        self.check_autotrader.cancel()

    @tasks.loop(minutes=15)
    async def check_autotrader(self):
        logger.info("Checking AutoTrader for dynamic searches...")
        
        searches = get_all_searches()
        if not searches:
            logger.info("No active searches found in the database.")
            return
            
        total_new_cars = 0
        for search in searches:
            channel_id = search["channel_id"]
            user_id = search.get("user_id")
            filters = search["filters"]
            write_off_pref = search.get("write_off", "Include")
            
            # Clone filters to avoid mutating the dict reference
            api_filters = list(filters)
            
            if write_off_pref == "Exclude":
                api_filters.append({"filter": "is_writeoff", "selected": ["exclude"]})
            elif write_off_pref == "Only":
                api_filters.append({"filter": "is_writeoff", "selected": ["true"]})
            else:
                api_filters.append({"filter": "is_writeoff", "selected": ["include"]})
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"Could not find channel with ID {channel_id} for Search #{search['id']}")
                continue

            listings = await self.at_client.fetch_listings(api_filters)
            
            for car in listings:
                advert_id = car.get("advertId")
                if not advert_id:
                    continue
                
                # Promoted listings ignore price/mileage filters
                if car.get("type") != "NATURAL_LISTING":
                    continue

                if not is_advert_seen(advert_id):
                    mark_advert_seen(advert_id)
                    total_new_cars += 1
                    
                    title = car.get("title", "Unknown Title")
                    subtitle = car.get("subTitle", "")
                    price = car.get("price", "Unknown Price")
                    link = f"https://www.autotrader.co.uk/car-details/{advert_id}"
                    
                    badges = car.get("badges", [])
                    mileage = "Unknown Mileage"
                    year = "Unknown Year"
                    price_indicator = ""
                    
                    if badges:
                        for badge in badges:
                            btype = badge.get("type", "")
                            btext = badge.get("displayText", "")
                            if btype == "MILEAGE":
                                mileage = btext
                            elif btype == "REGISTERED_YEAR":
                                year = btext
                            elif btype and btype.startswith("PI_"):
                                price_indicator = btext
                                
                    # If there's an attention grabber, append it to subtitle
                    attention = car.get("attentionGrabber")
                    if attention:
                        subtitle = f"{attention} • {subtitle}"
                    
                    # Extract listed date from advert_id
                    listed_date = "Unknown"
                    if isinstance(advert_id, str) and len(advert_id) >= 8 and advert_id[:8].isdigit():
                        listed_date = f"{advert_id[:4]}-{advert_id[4:6]}-{advert_id[6:8]}"
                        
                    # Fetch extra details via GraphQL (with HTML scrape fallback)
                    tracking = car.get("trackingContext", {}).get("advertContext", {})
                    make = tracking.get("make")
                    model = tracking.get("model")
                    exact_price = tracking.get("price")
                    
                    details = await self.at_client.fetch_advert_details(advert_id, make=make, model=model, exact_price=exact_price)
                    colour = details.get("colour", "Unknown")
                    specs = details.get("specs", [])

                    # Build embed
                    embed = discord.Embed(
                        title=f"New Listing: {title}",
                        url=link,
                        color=discord.Color.blue()
                    )
                    
                    # Format: price | mileage | year | price_indicator
                    headline = f"**{price}**"
                    if mileage != "Unknown Mileage":
                        headline += f" | {mileage}"
                    if year != "Unknown Year":
                        headline += f" | {year}"
                    if price_indicator:
                        headline += f" | *{price_indicator}*"
                        
                    embed.add_field(name="Details", value=headline, inline=False)
                    
                    if colour != "Unknown":
                        embed.add_field(name="Colour", value=colour, inline=True)
                    if listed_date != "Unknown":
                        embed.add_field(name="Listed Date", value=listed_date, inline=True)
                        
                    if specs:
                        # Grab a few specs to keep it tidy
                        specs_text = "\n".join(specs[:5])
                        embed.add_field(name="Specs", value=specs_text, inline=False)
                        
                    embed.add_field(name="Description", value=subtitle, inline=False)
                    
                    # Add search ID to footer (and fallback warning if needed)
                    footer_text = f"Search #{search['id']}"
                    if details.get("fallback"):
                        footer_text += " • ⚠️ Details via HTML fallback"
                    embed.set_footer(text=footer_text)
                    
                    # Make the image large
                    images = car.get("images", [])
                    if images and len(images) > 0 and isinstance(images[0], str):
                        embed.set_image(url=images[0])
                    
                    try:
                        content = f"<@{user_id}>" if user_id else None
                        await channel.send(content=content, embed=embed)
                    except discord.Forbidden:
                        logger.error(f"Missing permissions to send messages in channel {channel_id}")
                    except Exception as e:
                        logger.error(f"Failed to send message: {e}")

        logger.info(f"Finished checking AutoTrader. Found {total_new_cars} total new cars across {len(searches)} searches.")

    @check_autotrader.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Notifier(bot))
