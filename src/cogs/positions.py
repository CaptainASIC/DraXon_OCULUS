"""Position management for DraXon OCULUS v3"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from datetime import datetime, timezone
import json

from src.utils.constants import (
    RANK_CODES,
    DIVISIONS,
    DraXon_ROLES
)

logger = logging.getLogger('DraXon_OCULUS')

class Positions(commands.Cog):
    """DraXon Position Management"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Positions cog initialized")

    @app_commands.command(name="draxon-position")
    @app_commands.describe(
        action="Action to perform (list/add/remove)",
        name="Position name (for add/remove)",
        division="Division name (for add)",
        rank_required="Required rank code (for add)"
    )
    async def position(
        self,
        interaction: discord.Interaction,
        action: str,
        name: Optional[str] = None,
        division: Optional[str] = None,
        rank_required: Optional[str] = None
    ):
        """Manage DraXon positions"""
        
        # Check permissions - allow Magnate role
        user_roles = [role.name for role in interaction.user.roles]
        is_authorized = any(role in DraXon_ROLES['leadership'] for role in user_roles)
        
        if not is_authorized:
            await interaction.response.send_message(
                "❌ You don't have permission to manage positions.",
                ephemeral=True
            )
            return

        if action.lower() == "list":
            await self._list_positions(interaction)
        elif action.lower() == "add":
            if not all([name, division, rank_required]):
                await interaction.response.send_message(
                    "❌ Name, division, and rank_required are required for adding positions.",
                    ephemeral=True
                )
                return
            await self._add_position(interaction, name, division, rank_required)
        elif action.lower() == "remove":
            if not name:
                await interaction.response.send_message(
                    "❌ Position name is required for removal.",
                    ephemeral=True
                )
                return
            await self._remove_position(interaction, name)
        else:
            await interaction.response.send_message(
                "❌ Invalid action. Use list, add, or remove.",
                ephemeral=True
            )

    async def _list_positions(self, interaction: discord.Interaction):
        """List all positions by division"""
        embed = discord.Embed(
            title="DraXon Positions Overview",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )

        # Get all divisions and their positions
        for division_name in DIVISIONS:
            # Get positions for this division
            positions_query = """
            SELECT p.*, m.discord_id as holder_id
            FROM v3_divisions d
            LEFT JOIN v3_positions p ON d.id = p.division_id
            LEFT JOIN v3_members m ON p.holder_id = m.id
            WHERE d.name = $1
            ORDER BY p.title
            """
            positions = await self.bot.db.fetch(positions_query, division_name)
            
            # Format positions text
            position_text = ""
            if positions and any(p['id'] is not None for p in positions):
                for pos in positions:
                    if pos['id'] is not None:  # Check if position exists
                        status = "🟢 OPEN" if pos['status'] == "OPEN" else "🔴 FILLED"
                        holder = f"<@{pos['holder_id']}>" if pos['holder_id'] else "None"
                        position_text += f"📍 **{pos['title']}** ({status})\n"
                        position_text += f"└ Required Rank: {pos['required_rank']}\n"
                        position_text += f"└ Current Holder: {holder}\n\n"
            else:
                position_text = "No positions defined\n"

            embed.add_field(
                name=f"__{division_name}__",
                value=position_text,
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    async def _add_position(
        self,
        interaction: discord.Interaction,
        name: str,
        division_name: str,
        rank_required: str
    ):
        """Add a new position"""
        # Validate rank code
        if rank_required.upper() not in ['EXE', 'TL', 'EMP']:
            await interaction.response.send_message(
                "❌ Invalid rank code. Use EXE, TL, or EMP.",
                ephemeral=True
            )
            return

        # Get division
        division_query = """
        SELECT * FROM v3_divisions 
        WHERE name = $1
        """
        division = await self.bot.db.fetchrow(division_query, division_name)

        if not division:
            await interaction.response.send_message(
                "❌ Invalid division name.",
                ephemeral=True
            )
            return

        # Check if position already exists
        existing_query = """
        SELECT * FROM v3_positions 
        WHERE title = $1 AND division_id = $2
        """
        existing = await self.bot.db.fetchrow(existing_query, name, division['id'])

        if existing:
            await interaction.response.send_message(
                "❌ Position already exists in this division.",
                ephemeral=True
            )
            return

        # Create position
        position_query = """
        INSERT INTO v3_positions (title, division_id, required_rank, status)
        VALUES ($1, $2, $3, $4)
        """
        await self.bot.db.execute(
            position_query,
            name,
            division['id'],
            rank_required.upper(),
            'OPEN'
        )

        # Log action
        audit_query = """
        INSERT INTO v3_audit_logs (action_type, actor_id, details)
        VALUES ($1, $2::BIGINT, $3)
        """
        details = json.dumps({
            'position': name,
            'division': division_name,
            'rank_required': rank_required.upper()
        })
        await self.bot.db.execute(
            audit_query,
            'POSITION_CREATE',
            interaction.user.id,
            details
        )

        await interaction.response.send_message(
            f"✅ Position '{name}' created in {division_name} division.",
            ephemeral=True
        )

    async def _remove_position(self, interaction: discord.Interaction, name: str):
        """Remove a position"""
        # Find position
        position_query = """
        SELECT p.*, d.name as division_name 
        FROM v3_positions p
        JOIN v3_divisions d ON p.division_id = d.id
        WHERE p.title = $1
        """
        position = await self.bot.db.fetchrow(position_query, name)

        if not position:
            await interaction.response.send_message(
                "❌ Position not found.",
                ephemeral=True
            )
            return

        # Check if position has applications
        apps_query = """
        SELECT * FROM v3_applications 
        WHERE position_id = $1 AND status = 'PENDING'
        """
        applications = await self.bot.db.fetchrow(apps_query, position['id'])

        if applications:
            await interaction.response.send_message(
                "❌ Cannot remove position with pending applications.",
                ephemeral=True
            )
            return

        # Remove position
        delete_query = "DELETE FROM v3_positions WHERE id = $1"
        await self.bot.db.execute(delete_query, position['id'])

        # Log action
        audit_query = """
        INSERT INTO v3_audit_logs (action_type, actor_id, details)
        VALUES ($1, $2::BIGINT, $3)
        """
        details = json.dumps({
            'position': name,
            'division': position['division_name']
        })
        await self.bot.db.execute(
            audit_query,
            'POSITION_DELETE',
            interaction.user.id,
            details
        )

        await interaction.response.send_message(
            f"✅ Position '{name}' removed from {position['division_name']} division.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Positions(bot))
