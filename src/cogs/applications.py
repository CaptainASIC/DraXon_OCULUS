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
    DIVISIONS,
    ROLE_HIERARCHY
)

logger = logging.getLogger('DraXon_OCULUS')

class PositionModal(discord.ui.Modal, title="Create Position"):
    """Modal for creating a new position"""
    
    def __init__(self):
        super().__init__()
        
        self.title_input = discord.ui.TextInput(
            label="Position Title",
            placeholder="Enter the position title",
            required=True,
            max_length=100
        )
        
        # Create dropdown-style input for division
        divisions_list = ", ".join(DIVISIONS.keys())
        self.division = discord.ui.TextInput(
            label="Division",
            placeholder=f"Choose from: {divisions_list}",
            required=True,
            max_length=50
        )
        
        # Create dropdown-style input for rank
        # Filter ranks to exclude leadership roles
        available_ranks = [r for r in ROLE_HIERARCHY if r not in DraXon_ROLES['leadership']]
        ranks_list = ", ".join(available_ranks)
        self.required_rank = discord.ui.TextInput(
            label="Required Rank",
            placeholder=f"Choose from: {ranks_list}",
            required=True,
            max_length=50
        )
        
        self.add_item(self.title_input)
        self.add_item(self.division)
        self.add_item(self.required_rank)

    async def on_submit(self, interaction: discord.Interaction):
        # Validate division
        if self.division.value not in DIVISIONS:
            await interaction.response.send_message(
                f"❌ Invalid division. Must be one of: {', '.join(DIVISIONS.keys())}",
                ephemeral=True
            )
            return False
            
        # Validate rank
        available_ranks = [r for r in ROLE_HIERARCHY if r not in DraXon_ROLES['leadership']]
        if self.required_rank.value not in available_ranks:
            await interaction.response.send_message(
                f"❌ Invalid rank. Must be one of: {', '.join(available_ranks)}",
                ephemeral=True
            )
            return False
            
        return True

class ApplyModal(discord.ui.Modal, title="Apply for Position"):
    """Modal for applying to a position"""
    
    def __init__(self, positions):
        super().__init__()
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
            return False
            
        return True

class Applications(commands.Cog):
    """DraXon Applications Management"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Applications cog initialized")

    @app_commands.command(name="draxon-position")
    @app_commands.describe(
        title="Position title",
        division="Division for the position",
        required_rank="Required rank for the position"
    )
    async def position(self, interaction: discord.Interaction):
        """Create a new DraXon position"""
        try:
            # Create and show modal
            modal = PositionModal()
            await interaction.response.send_modal(modal)
            
            # Wait for modal submission
            await modal.wait()
            
            if modal.is_submitted():
                # Validate submission
                if not await modal.on_submit(interaction):
                    return
                
                # Get division ID
                division_query = "SELECT id FROM v3_divisions WHERE name = $1"
                division_id = await self.bot.db.fetchval(
                    division_query,
                    modal.division.value
                )
                
                # Create position
                position_query = """
                INSERT INTO v3_positions (
                    title, division_id, required_rank, status
                ) VALUES ($1, $2, $3, $4)
                RETURNING id
                """
                position_id = await self.bot.db.fetchval(
                    position_query,
                    modal.title_input.value,
                    division_id,
                    modal.required_rank.value[:3].upper(),  # Convert to code (e.g., EXE)
                    'OPEN'
                )
                
                # Create audit log
                audit_query = """
                INSERT INTO v3_audit_logs (
                    action_type, actor_id, details
                ) VALUES ($1, $2, $3)
                """
                details = json.dumps({
                    'position_id': position_id,
                    'title': modal.title_input.value,
                    'division': modal.division.value,
                    'required_rank': modal.required_rank.value
                })
                await self.bot.db.execute(
                    audit_query,
                    'POSITION_CREATE',
                    str(interaction.user.id),
                    details
                )
                
                await interaction.followup.send(
                    f"✅ Position '{modal.title_input.value}' created successfully.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in position command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while creating the position.",
                ephemeral=True
            )

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
            modal = ApplyModal(positions)
            await interaction.response.send_modal(modal)
            
            # Wait for modal submission
            await modal.wait()
            
            if modal.is_submitted():
                # Validate submission
                if not await modal.on_submit(interaction):
                    return
                
                # Get selected position
                selected_position = next(
                    p for p in positions 
                    if f"{p['title']} ({p['division_name']})" == modal.position.value
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
                    modal.statement.value,
                    'PENDING',
                    datetime.utcnow()
                )

                # Find HR channel for thread creation
                hr_channel = discord.utils.get(
                    interaction.guild.channels,
                    name='human-resources'
                )
                
                if not hr_channel:
                    await interaction.followup.send(
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
                    details=modal.statement.value,
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

                await interaction.followup.send(
                    f"✅ Application submitted for {selected_position['title']}. "
                    f"Please monitor the thread in {hr_channel.mention}.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in apply command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while submitting your application.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Applications(bot))
