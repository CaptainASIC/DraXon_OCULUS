"""Division management for DraXon OCULUS v3"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from datetime import datetime, timezone

from src.utils.constants import (
    APP_VERSION,
    DIVISIONS
)

logger = logging.getLogger('DraXon_OCULUS')

class Divisions(commands.Cog):
    """DraXon Division Management"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Divisions cog initialized")

    @app_commands.command(name="draxon-division", description="Display DraXon division organization")
    async def division(self, interaction: discord.Interaction):
        """Display division organization structure"""
        try:
            embed = discord.Embed(
                title="📊 DraXon Division Organization",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            for division_name in DIVISIONS.keys():
                # Get division role
                division_role = discord.utils.get(interaction.guild.roles, name=division_name)
                if not division_role:
                    continue

                # Get Team Leaders in division
                team_leaders = [
                    member.display_name for member in division_role.members
                    if discord.utils.get(member.roles, name="Team Leader")
                ]

                # Count Employees in division
                employee_count = len([
                    member for member in division_role.members
                    if discord.utils.get(member.roles, name="Employee")
                ])

                # Format division info
                division_info = ""
                if team_leaders:
                    division_info += f"**Team Leaders:** {', '.join(team_leaders)}\n"
                division_info += f"**Employees:** {employee_count}"

                embed.add_field(
                    name=division_name,
                    value=division_info,
                    inline=False
                )

            embed.set_footer(text=f"DraXon OCULUS v{APP_VERSION}")
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in division command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while fetching division information.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Divisions(bot))
