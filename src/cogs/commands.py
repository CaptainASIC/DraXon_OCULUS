"""General commands for DraXon OCULUS"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from src.utils.constants import (
    APP_VERSION,
    BOT_DESCRIPTION,
    DraXon_ROLES,
    STATUS_EMOJIS,
    ROLE_HIERARCHY,
    COMMAND_HELP
)

logger = logging.getLogger('DraXon_OCULUS')

class CommandsCog(commands.Cog):
    """Cog for handling bot commands"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Commands cog initialized")

    @app_commands.command(name="oculus-about", description="Display information about OCULUS and available commands")
    async def about(self, interaction: discord.Interaction):
        """Display information about OCULUS and available commands"""
        try:
            # Get user's roles
            member_roles = [role.name for role in interaction.user.roles]
            
            # Build available commands list based on roles
            commands = COMMAND_HELP['all'].copy()  # Everyone gets these
            
            if any(role in member_roles for role in DraXon_ROLES['staff']):
                commands.extend(COMMAND_HELP['staff'])
            
            if any(role in member_roles for role in DraXon_ROLES['management']):
                commands.extend(COMMAND_HELP['management'])
            
            if any(role in member_roles for role in DraXon_ROLES['leadership']):
                commands.extend(COMMAND_HELP['leadership'])
            
            # Format embed
            embed = discord.Embed(
                title="DraXon OCULUS",
                description=f"Version {APP_VERSION}\n{BOT_DESCRIPTION}",
                color=discord.Color.blue()
            )
            
            # Add commands field
            commands_text = "\n".join(f"`{cmd}` - {desc}" for cmd, desc in commands)
            embed.add_field(
                name="Available Commands",
                value=commands_text,
                inline=False
            )

            # Add support information
            embed.add_field(
                name="🔧 Support",
                value="If you encounter any issues or need assistance, "
                      "please contact a server administrator.",
                inline=False
            )

            embed.set_footer(text=f"DraXon OCULUS v{APP_VERSION} • Commands available based on your roles")
            
            # Add timestamp to know when help was last viewed
            await self.bot.redis.hset(
                f'help_viewed:{interaction.user.id}',
                mapping={
                    'timestamp': datetime.utcnow().isoformat(),
                    'version': APP_VERSION
                }
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while displaying bot information.",
                ephemeral=True
            )

    @app_commands.command(name="refresh-channels", 
                         description="Manually refresh DraXon OCULUS channels")
    @app_commands.checks.has_role("Magnate")
    async def refresh_channels(self, interaction: discord.Interaction):
        """Manually trigger channel refresh"""
        try:
            members_cog = self.bot.get_cog('MembersCog')
            status_cog = self.bot.get_cog('RSIStatusMonitorCog')
            
            if not members_cog or not status_cog:
                await interaction.response.send_message(
                    "❌ Required cogs not found. Make sure MembersCog and RSIStatusMonitorCog are loaded.",
                    ephemeral=True
                )
                return

            # Update channels
            await members_cog.update_member_counts()
            await status_cog.check_status()  # This will trigger channel updates
            
            await interaction.response.send_message(
                "✅ Channels refreshed successfully!", 
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error refreshing channels: {e}")
            await interaction.response.send_message(
                "❌ Failed to refresh channels. Check logs for details.", 
                ephemeral=True
            )

    @app_commands.command(name="force-check", 
                         description="Force check for new incidents and status")
    @app_commands.checks.has_role("Magnate")
    async def force_check(self, interaction: discord.Interaction):
        """Manually trigger status and incident checks"""
        try:
            status_monitor = self.bot.get_cog('RSIStatusMonitorCog')
            incident_monitor = self.bot.get_cog('RSIIncidentMonitorCog')
            
            if not status_monitor or not incident_monitor:
                await interaction.response.send_message(
                    "❌ Required monitors not available.",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Perform checks
            current_status = await status_monitor.check_status()
            incident = await incident_monitor.get_latest_incident(force=True)
            
            # Create status embed
            status_embed = status_monitor.format_status_embed()  # Removed await
            
            # Create incident embed if there is one
            embeds = [status_embed]
            if incident:
                incident_embed = incident_monitor.create_incident_embed(incident)
                embeds.append(incident_embed)
            
            await interaction.followup.send(
                content="✅ Manual check completed successfully!",
                embeds=embeds,
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in force check: {e}")
            await interaction.followup.send(
                "❌ Error during manual check. Check logs for details.",
                ephemeral=True
            )

    async def cog_command_error(self, interaction: discord.Interaction, 
                               error: app_commands.AppCommandError):
        """Handle command errors for this cog"""
        if isinstance(error, app_commands.errors.MissingRole):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        else:
            logger.error(f"Command error in {interaction.command.name}: {error}")
            await interaction.response.send_message(
                "❌ An error occurred while processing the command.",
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
        logger.error(f'Error loading commands cog: {e}')
        raise
