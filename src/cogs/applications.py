"""Applications system for DraXon OCULUS v3"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from datetime import datetime
import json

from src.utils.constants import (
    V3_SYSTEM_MESSAGES,
    APPLICATION_SETTINGS,
    DraXon_ROLES
)

logger = logging.getLogger('DraXon_OCULUS')

class Applications(commands.Cog):
    """DraXon Applications Management"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Applications cog initialized")

    @app_commands.command(name="draxon-apply")
    @app_commands.describe(
        position="Position to apply for",
        statement="Your position statement"
    )
    async def apply(
        self,
        interaction: discord.Interaction,
        position: str,
        statement: str
    ):
        """Apply for a DraXon position"""
        try:
            # Get position details
            position_query = """
            SELECT p.*, d.name as division_name
            FROM v3_positions p
            JOIN v3_divisions d ON p.division_id = d.id
            WHERE p.title = $1 AND p.status = 'OPEN'
            """
            position_data = await self.bot.db.fetchrow(position_query, position)
            
            if not position_data:
                await interaction.response.send_message(
                    "❌ Position not found or not open for applications.",
                    ephemeral=True
                )
                return

            # Check if user already has pending application
            pending_query = """
            SELECT * FROM v3_applications
            WHERE applicant_id = $1 AND status = 'PENDING'
            """
            pending = await self.bot.db.fetchrow(
                pending_query,
                str(interaction.user.id)  # Convert to string
            )
            
            if pending:
                await interaction.response.send_message(
                    "❌ You already have a pending application.",
                    ephemeral=True
                )
                return

            # Create application
            application_query = """
            INSERT INTO v3_applications (
                applicant_id, position_id, details, status, created_at
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """
            application_id = await self.bot.db.fetchval(
                application_query,
                str(interaction.user.id),  # Convert to string
                position_data['id'],
                statement,
                'PENDING',
                datetime.utcnow()
            )

            # Find HR channel for thread creation
            hr_channel = discord.utils.get(
                interaction.guild.channels,
                name='human-resources'  # Updated to use correct channel name
            )
            
            if not hr_channel:
                await interaction.response.send_message(
                    "❌ Error: HR channel not found.",
                    ephemeral=True
                )
                return

            # Create thread for application
            thread = await hr_channel.create_thread(
                name=f"Application: {position} - {interaction.user.display_name}",
                reason=f"Application for {position}"
            )

            # Format application message
            message = V3_SYSTEM_MESSAGES['APPLICATION']['THREAD_CREATED'].format(
                position=position,
                applicant=interaction.user.mention,
                rank=next((r.name for r in interaction.user.roles 
                          if r.name in DraXon_ROLES['leadership'] + 
                                     DraXon_ROLES['management'] +
                                     DraXon_ROLES['staff'] +
                                     DraXon_ROLES['restricted']), 'Unknown'),
                division=position_data['division_name'],
                details=statement,
                current=0,
                required=APPLICATION_SETTINGS['MIN_VOTES_REQUIRED'][position_data['required_rank']],
                voters="None yet"
            )

            await thread.send(message)

            # Create audit log entry
            audit_query = """
            INSERT INTO v3_audit_logs (
                action_type, actor_id, details
            ) VALUES ($1, $2, $3)
            """
            details = json.dumps({
                'application_id': str(application_id),
                'position': position,
                'division': position_data['division_name']
            })
            await self.bot.db.execute(
                audit_query,
                'APPLICATION_CREATE',
                str(interaction.user.id),  # Convert to string
                details
            )

            await interaction.response.send_message(
                f"✅ Application submitted for {position}. "
                f"Please monitor the thread in {hr_channel.mention}.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in apply command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while submitting your application.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Applications(bot))
