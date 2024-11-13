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

class ApplyModal(discord.ui.Modal, title="Apply for Position"):
    """Modal for applying to a position"""
    
    def __init__(self, bot, positions):
        super().__init__()
        self.bot = bot
        self.positions = positions
        
        # Create dropdown-style input for position
        position_list = "\n".join(
            f"- {pos['title']} ({pos['division_name']})" 
            for pos in positions
        )
        self.position = discord.ui.TextInput(
            label="Position",
            placeholder=f"Choose from available positions:\n{position_list}",
            required=True,
            max_length=100
        )
        
        self.statement = discord.ui.TextInput(
            label="Position Statement",
            placeholder="Why are you interested in this position?",
            required=True,
            style=discord.TextStyle.paragraph
        )
        
        self.add_item(self.position)
        self.add_item(self.statement)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate position
            position_titles = [
                f"{pos['title']} ({pos['division_name']})" 
                for pos in self.positions
            ]
            if self.position.value not in position_titles:
                await interaction.response.send_message(
                    f"❌ Invalid position. Must be one of:\n{chr(10).join(position_titles)}",
                    ephemeral=True
                )
                return
                
            # Get selected position
            selected_position = next(
                p for p in self.positions 
                if f"{p['title']} ({p['division_name']})" == self.position.value
            )
            
            # Create application
            application_query = """
            INSERT INTO v3_applications (
                applicant_id, position_id, details, status, created_at
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING id
            """
            application_id = await self.bot.db.fetchval(
                application_query,
                str(interaction.user.id),
                selected_position['id'],
                self.statement.value,
                'PENDING',
                datetime.utcnow()
            )

            # Find HR channel for thread creation
            hr_channel = discord.utils.get(
                interaction.guild.channels,
                name='human-resources'
            )
            
            if not hr_channel:
                await interaction.response.send_message(
                    "❌ Error: HR channel not found.",
                    ephemeral=True
                )
                return

            # Create thread for application
            thread = await hr_channel.create_thread(
                name=f"Application: {selected_position['title']} - {interaction.user.display_name}",
                reason=f"Application for {selected_position['title']}"
            )

            # Format application message
            message = V3_SYSTEM_MESSAGES['APPLICATION']['THREAD_CREATED'].format(
                position=selected_position['title'],
                applicant=interaction.user.mention,
                rank=next((r.name for r in interaction.user.roles 
                          if r.name in DraXon_ROLES['leadership'] + 
                                     DraXon_ROLES['management'] +
                                     DraXon_ROLES['staff'] +
                                     DraXon_ROLES['restricted']), 'Unknown'),
                division=selected_position['division_name'],
                details=self.statement.value,
                current=0,
                required=APPLICATION_SETTINGS['MIN_VOTES_REQUIRED'][selected_position['required_rank']],
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
                'position': selected_position['title'],
                'division': selected_position['division_name']
            })
            await self.bot.db.execute(
                audit_query,
                'APPLICATION_CREATE',
                str(interaction.user.id),
                details
            )

            await interaction.response.send_message(
                f"✅ Application submitted for {selected_position['title']}. "
                f"Please monitor the thread in {hr_channel.mention}.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in apply modal: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while submitting your application.",
                ephemeral=True
            )

class Applications(commands.Cog):
    """DraXon Applications Management"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Applications cog initialized")

    @app_commands.command(name="draxon-apply")
    async def apply(self, interaction: discord.Interaction):
        """Apply for a DraXon position"""
        try:
            # Get open positions
            position_query = """
            SELECT p.*, d.name as division_name
            FROM v3_positions p
            JOIN v3_divisions d ON p.division_id = d.id
            WHERE p.status = 'OPEN'
            """
            positions = await self.bot.db.fetch(position_query)
            
            if not positions:
                await interaction.response.send_message(
                    "❌ No positions are currently open for applications.",
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
                str(interaction.user.id)
            )
            
            if pending:
                await interaction.response.send_message(
                    "❌ You already have a pending application.",
                    ephemeral=True
                )
                return
            
            # Create and show modal
            modal = ApplyModal(self.bot, positions)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in apply command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while preparing the application form.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Applications(bot))
