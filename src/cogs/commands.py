"""General commands for DraXon OCULUS"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from datetime import datetime

from ..utils.constants import APP_VERSION, BUILD_DATE, BOT_DESCRIPTION

logger = logging.getLogger('DraXon_OCULUS')

class CommandsCog(commands.Cog):
    """General commands cog"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Commands cog initialized")

    @app_commands.command(
        name="oculus-about",
        description="Display information about DraXon OCULUS"
    )
    async def about(self, interaction: discord.Interaction):
        """Display bot information and available commands"""
        try:
            # Check if user has Magnate role
            is_magnate = discord.utils.get(interaction.user.roles, name="Magnate") is not None
            
            embed = discord.Embed(
                title="🔍 DraXon OCULUS",
                description=BOT_DESCRIPTION,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Add version info
            embed.add_field(
                name="Version Info",
                value=f"Version: {APP_VERSION}\nBuild Date: {BUILD_DATE}",
                inline=False
            )
            
            # Add basic commands for all users
            basic_commands = (
                "🔗 `/draxon-link` - Link your RSI account\n"
            )
            embed.add_field(
                name="Available Commands",
                value=basic_commands,
                inline=False
            )
            
            # Add management commands for Magnates
            if is_magnate:
                management_commands = (
                    "📊 `/draxon-org` - Display organization member list\n"
                    "🔄 `/draxon-compare` - Compare Discord and RSI members\n"
                    "🔄 `/draxon-refresh` - Refresh RSI organization data"
                )
                embed.add_field(
                    name="Management Commands",
                    value=management_commands,
                    inline=False
                )
            
            # Add bot statistics
            stats = await self.bot.get_bot_stats()
            stats_text = (
                f"Guilds: {stats.get('guilds', 0)}\n"
                f"Total Members: {stats.get('total_members', 0)}\n"
                f"Uptime: {int(stats.get('uptime', 0))} seconds"
            )
            embed.add_field(
                name="Statistics",
                value=stats_text,
                inline=False
            )
            
            # Add footer
            embed.set_footer(text="DraXon Industries")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching bot information.",
                ephemeral=True
            )

async def setup(bot):
    """Safe setup function for commands cog"""
    try:
        if not bot.get_cog('CommandsCog'):
            await bot.add_cog(CommandsCog(bot))
            logger.info('Commands cog loaded successfully')
        else:
            logger.info('Commands cog already loaded, skipping')
    except Exception as e:
        logger.error(f'Error loading Commands cog: {e}')
        raise
