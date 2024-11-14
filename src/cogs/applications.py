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
    DraXon_ROLES,
    DIVISIONS
)

logger = logging.getLogger('DraXon_OCULUS')

class DivisionSelect(discord.ui.Select):
    """Dropdown for selecting division"""
    def __init__(self):
        options = [
            discord.SelectOption(
                label=division,
                description=desc[:100]  # Discord limits description to 100 chars
            )
            for division, desc in DIVISIONS.items()
            if division != 'HR'  # Exclude HR from options
        ]
        super().__init__(
            placeholder="Select a division",
            min_values=1,
            max_values=1,
            options=options
        )

class ApplyModal(discord.ui.Modal, title="Apply for Team Leader Position"):
    """Modal for applying to a position"""
    
    def __init__(self, bot, division):
        super().__init__()
        self.bot = bot
        self.division = division
        
        self.statement = discord.ui.TextInput(
            label="Position Statement",
            placeholder="Why are you interested in becoming a Team Leader for this division?",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=2000
        )
        
        self.add_item(self.statement)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get member ID from discord ID
            member_query = """
            SELECT id FROM v3_members
            WHERE discord_id = $1
            """
            member_id = await self.bot.db.fetchval(
                member_query,
                str(interaction.user.id)
            )
            
            if not member_id:
                # Create member if they don't exist
                member_query = """
                INSERT INTO v3_members (discord_id, rank, status)
                VALUES ($1, $2, $3)
                RETURNING id
                """
                member_id = await self.bot.db.fetchval(
                    member_query,
                    str(interaction.user.id),
                    'AP',  # Applicant rank
                    'ACTIVE'
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
                name=f"Application: {self.division} Team Leader - {interaction.user.display_name}",
                reason=f"Application for {self.division} Team Leader"
            )

            # Create application
            application_query = """
            INSERT INTO v3_applications (
                applicant_id, division_name, thread_id, statement, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """
            application_id = await self.bot.db.fetchval(
                application_query,
                member_id,
                self.division,
                str(thread.id),
                self.statement.value,
                'PENDING',
                datetime.utcnow()
            )

            # Format application message
            message = V3_SYSTEM_MESSAGES['APPLICATION']['THREAD_CREATED'].format(
                position=f"{self.division} Team Leader",
                applicant=interaction.user.mention,
                rank=next((r.name for r in interaction.user.roles 
                          if r.name in DraXon_ROLES['leadership'] + 
                                     DraXon_ROLES['management'] +
                                     DraXon_ROLES['staff'] +
                                     DraXon_ROLES['restricted']), 'Unknown'),
                division=self.division,
                details=self.statement.value,
                current=0,
                required=APPLICATION_SETTINGS['MIN_VOTES_REQUIRED']['TL'],
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
                'division': self.division
            })
            await self.bot.db.execute(
                audit_query,
                'APPLICATION_CREATE',
                str(interaction.user.id),
                details
            )

            await interaction.response.send_message(
                f"✅ Application submitted for {self.division} Team Leader. "
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
        """Apply for a Team Leader position"""
        try:
            # Check if user has Employee or higher role
            member_roles = [role.name for role in interaction.user.roles]
            if not any(role in member_roles for role in 
                      DraXon_ROLES['leadership'] + 
                      DraXon_ROLES['management'] + 
                      DraXon_ROLES['staff']):
                await interaction.response.send_message(
                    "❌ You must be an Employee or higher to apply for Team Leader positions.",
                    ephemeral=True
                )
                return
            
            # Create view with division select
            view = discord.ui.View()
            select = DivisionSelect()
            
            async def division_callback(interaction: discord.Interaction):
                division = select.values[0]
                modal = ApplyModal(self.bot, division)
                await interaction.response.send_modal(modal)
            
            select.callback = division_callback
            view.add_item(select)
            
            await interaction.response.send_message(
                "Please select a division to apply for:",
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in apply command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while preparing the application form.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Applications(bot))
