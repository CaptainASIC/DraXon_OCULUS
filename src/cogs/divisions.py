"""Division management for DraXon OCULUS v3"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from datetime import datetime, timezone

from src.utils.constants import (
    RANK_CODES,
    DIVISIONS
)

logger = logging.getLogger('DraXon_OCULUS')

class Divisions(commands.Cog):
    """DraXon Division Management"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Divisions cog initialized")

    @app_commands.command(name="draxon-division")
    @app_commands.describe(
        action="Action to perform (info/members/stats)",
        division="Division name"
    )
    async def division(
        self,
        interaction: discord.Interaction,
        action: str,
        division: Optional[str] = None
    ):
        """View division information and statistics"""
        
        if action.lower() == "info":
            await self._show_division_info(interaction, division)
        elif action.lower() == "members":
            await self._show_division_members(interaction, division)
        elif action.lower() == "stats":
            await self._show_division_stats(interaction, division)
        else:
            await interaction.response.send_message(
                "❌ Invalid action. Use info, members, or stats.",
                ephemeral=True
            )

    async def _show_division_info(
        self,
        interaction: discord.Interaction,
        division_name: Optional[str] = None
    ):
        """Show division information"""
        if division_name:
            # Show specific division
            division_query = """
            SELECT d.*, 
                   COUNT(m.id) as member_count,
                   COUNT(p.id) FILTER (WHERE p.status = 'OPEN') as open_positions
            FROM v3_divisions d
            LEFT JOIN v3_members m ON d.id = m.division_id
            LEFT JOIN v3_positions p ON d.id = p.division_id
            WHERE d.name = $1
            GROUP BY d.id
            """
            division = await self.bot.db.fetchrow(division_query, division_name)

            if not division:
                await interaction.response.send_message(
                    "❌ Division not found.",
                    ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"DraXon {division['name']} Division",
                description=division['description'],
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            # Get leadership
            leaders_query = """
            SELECT * FROM v3_members 
            WHERE division_id = $1 AND rank IN ('EXE', 'TL')
            ORDER BY rank
            """
            leaders = await self.bot.db.fetch(leaders_query, division['id'])

            # Add fields
            embed.add_field(
                name="Total Members",
                value=str(division['member_count']),
                inline=True
            )
            embed.add_field(
                name="Open Positions",
                value=str(division['open_positions']),
                inline=True
            )
            embed.add_field(
                name="Leadership",
                value="\n".join([
                    f"• {leader['rank']}: <@{leader['discord_id']}>"
                    for leader in leaders
                ]) or "None",
                inline=False
            )

            await interaction.response.send_message(embed=embed)

        else:
            # Show all divisions overview
            divisions_query = """
            SELECT d.*, 
                   COUNT(m.id) as member_count,
                   COUNT(p.id) FILTER (WHERE p.status = 'OPEN') as open_positions
            FROM v3_divisions d
            LEFT JOIN v3_members m ON d.id = m.division_id
            LEFT JOIN v3_positions p ON d.id = p.division_id
            GROUP BY d.id
            ORDER BY d.name
            """
            divisions = await self.bot.db.fetch(divisions_query)
            
            embed = discord.Embed(
                title="DraXon Divisions Overview",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            for division in divisions:
                embed.add_field(
                    name=division['name'],
                    value=f"""
{division['description']}

👥 Members: {division['member_count']}
📍 Open Positions: {division['open_positions']}
                    """,
                    inline=False
                )

            await interaction.response.send_message(embed=embed)

    async def _show_division_members(
        self,
        interaction: discord.Interaction,
        division_name: Optional[str] = None
    ):
        """Show division members"""
        if not division_name:
            await interaction.response.send_message(
                "❌ Please specify a division name.",
                ephemeral=True
            )
            return

        division_query = """
        SELECT * FROM v3_divisions 
        WHERE name = $1
        """
        division = await self.bot.db.fetchrow(division_query, division_name)

        if not division:
            await interaction.response.send_message(
                "❌ Division not found.",
                ephemeral=True
            )
            return

        members_query = """
        SELECT * FROM v3_members 
        WHERE division_id = $1 
        ORDER BY rank, discord_id
        """
        members = await self.bot.db.fetch(members_query, division['id'])

        embed = discord.Embed(
            title=f"DraXon {division['name']} Division Members",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )

        # Group members by rank
        rank_groups = {
            'EXE': [],
            'TL': [],
            'EMP': [],
            'AP': []
        }

        for member in members:
            if member['rank'] in rank_groups:
                rank_groups[member['rank']].append(member)

        # Add fields for each rank group
        for rank, rank_members in rank_groups.items():
            if rank_members:
                embed.add_field(
                    name=f"{rank} ({len(rank_members)})",
                    value="\n".join([
                        f"• <@{m['discord_id']}>" for m in rank_members
                    ]),
                    inline=False
                )

        await interaction.response.send_message(embed=embed)

    async def _show_division_stats(
        self,
        interaction: discord.Interaction,
        division_name: Optional[str] = None
    ):
        """Show division statistics"""
        if division_name:
            # Show specific division stats
            division = await self.bot.db.fetchrow(
                "SELECT * FROM v3_divisions WHERE name = $1",
                division_name
            )

            if not division:
                await interaction.response.send_message(
                    "❌ Division not found.",
                    ephemeral=True
                )
                return

            embed = await self._create_division_stats_embed(division)
            await interaction.response.send_message(embed=embed)

        else:
            # Show comparative stats for all divisions
            divisions_query = """
            SELECT d.name,
                   COUNT(m.id) as member_count,
                   COUNT(p.id) as position_count,
                   COUNT(a.id) as application_count
            FROM v3_divisions d
            LEFT JOIN v3_members m ON d.id = m.division_id
            LEFT JOIN v3_positions p ON d.id = p.division_id
            LEFT JOIN v3_applications a ON p.id = a.position_id
            GROUP BY d.id, d.name
            ORDER BY d.name
            """
            divisions = await self.bot.db.fetch(divisions_query)
            
            embed = discord.Embed(
                title="DraXon Divisions Statistics",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )

            total_members = 0
            total_positions = 0
            total_applications = 0

            for division in divisions:
                total_members += division['member_count']
                total_positions += division['position_count']
                total_applications += division['application_count']

                embed.add_field(
                    name=division['name'],
                    value=f"""
👥 Members: {division['member_count']}
📍 Positions: {division['position_count']}
📋 Applications: {division['application_count']}
                    """,
                    inline=True
                )

            # Add totals
            embed.add_field(
                name="Total Statistics",
                value=f"""
👥 Total Members: {total_members}
📍 Total Positions: {total_positions}
📋 Total Applications: {total_applications}
                """,
                inline=False
            )

            await interaction.response.send_message(embed=embed)

    async def _create_division_stats_embed(self, division: dict) -> discord.Embed:
        """Create detailed stats embed for a division"""
        embed = discord.Embed(
            title=f"DraXon {division['name']} Division Statistics",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )

        # Member stats
        members_query = """
        SELECT rank, COUNT(*) as count 
        FROM v3_members 
        WHERE division_id = $1 
        GROUP BY rank
        """
        rank_counts = await self.bot.db.fetch(members_query, division['id'])

        rank_stats = {rank: 0 for rank in ['EXE', 'TL', 'EMP', 'AP']}
        for row in rank_counts:
            rank_stats[row['rank']] = row['count']

        embed.add_field(
            name="Member Distribution",
            value="\n".join([
                f"{rank}: {count}" for rank, count in rank_stats.items()
            ]),
            inline=True
        )

        # Position stats
        positions_query = """
        SELECT 
            COUNT(*) FILTER (WHERE status = 'OPEN') as open_positions,
            COUNT(*) FILTER (WHERE status != 'OPEN') as filled_positions,
            COUNT(*) as total_positions
        FROM v3_positions 
        WHERE division_id = $1
        """
        position_stats = await self.bot.db.fetchrow(positions_query, division['id'])

        embed.add_field(
            name="Position Status",
            value=f"""
Open: {position_stats['open_positions']}
Filled: {position_stats['filled_positions']}
Total: {position_stats['total_positions']}
            """,
            inline=True
        )

        # Application stats
        apps_query = """
        SELECT status, COUNT(*) as count 
        FROM v3_applications a
        JOIN v3_positions p ON a.position_id = p.id
        WHERE p.division_id = $1
        GROUP BY status
        """
        app_counts = await self.bot.db.fetch(apps_query, division['id'])

        status_counts = {
            'PENDING': 0,
            'APPROVED': 0,
            'REJECTED': 0
        }
        for row in app_counts:
            status_counts[row['status']] = row['count']

        embed.add_field(
            name="Application History",
            value="\n".join([
                f"{status}: {count}" for status, count in status_counts.items()
            ]),
            inline=True
        )

        return embed

async def setup(bot):
    await bot.add_cog(Divisions(bot))
