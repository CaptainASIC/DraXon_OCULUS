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
        name="draxon-help",
        description="Display available DraXon OCULUS commands"
    )
    async def help(self, interaction: discord.Interaction):
        """Display available commands based on user's role"""
        try:
            # Check if user has Magnate role
            is_magnate = discord.utils.get(interaction.user.roles, name="Magnate") is not None
            
            embed = discord.Embed(
                title="🔍 DraXon OCULUS Commands",
                description="Available commands for your role:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # Add basic commands for all users
            basic_commands = (
                "🔗 `/draxon-link`\n"
                "Link your RSI account with Discord\n\n"
                "❓ `/draxon-help`\n"
                "Display this help message"
            )
            embed.add_field(
                name="Basic Commands",
                value=basic_commands,
                inline=False
            )
            
            # Add management commands for Magnates
            if is_magnate:
                management_commands = (
                    "📊 `/draxon-org`\n"
                    "Display organization member list\n\n"
                    "🔄 `/draxon-compare`\n"
                    "Compare Discord and RSI members\n\n"
                    "🔄 `/draxon-refresh`\n"
                    "Refresh RSI organization data"
                )
                embed.add_field(
                    name="Management Commands",
                    value=management_commands,
                    inline=False
                )
            
            # Add footer with version
            embed.set_footer(text=f"DraXon OCULUS v{APP_VERSION}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in help command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching command information.",
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
