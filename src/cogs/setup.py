"""Setup command for DraXon OCULUS"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from datetime import datetime
import json

from src.utils.constants import (
    APP_VERSION,
    DraXon_ROLES,
    STATUS_EMOJIS,
    ROLE_HIERARCHY,
    DIVISIONS,  # Added DIVISIONS import
    RANK_CODES
)

logger = logging.getLogger('DraXon_OCULUS')

class SetupCog(commands.Cog):
    """DraXon OCULUS Setup and Configuration"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Setup cog initialized")

    @app_commands.command(name="oculus-setup")
    @app_commands.describe(
        channels="Configure notification channels",
        divisions="Set up division structure",
        roles="Set up role hierarchy",
        sync="Sync existing members"
    )
    @app_commands.checks.has_role("Magnate")
    async def oculus_setup(
        self,
        interaction: discord.Interaction,
        channels: Optional[bool] = False,
        divisions: Optional[bool] = False,
        roles: Optional[bool] = False,
        sync: Optional[bool] = False
    ):
        """Configure DraXon OCULUS system"""
        try:
            # Create progress message
            await interaction.response.send_message(
                "🔄 Starting DraXon OCULUS setup...",
                ephemeral=True
            )
            progress_msg = await interaction.original_response()

            if channels:
                await progress_msg.edit(content="🔄 Setting up channels...")
                await self._setup_channels(interaction.guild)

            if divisions:
                await progress_msg.edit(content="🏢 Setting up divisions...")
                await self._setup_divisions(interaction.guild)

            if roles:
                await progress_msg.edit(content="👥 Setting up roles...")
                await self._setup_roles(interaction.guild)

            if sync:
                await progress_msg.edit(content="🔄 Syncing members...")
                await self._sync_members(interaction.guild)

            # Create audit log entry
            audit_query = """
            INSERT INTO v3_audit_logs (
                action_type, actor_id, details
            ) VALUES ($1, $2::BIGINT, $3)
            """
            details = json.dumps({  # Convert dict to JSON string
                'channels': channels,
                'divisions': divisions,
                'roles': roles,
                'sync': sync,
                'status': 'success'
            })
            await self.bot.db.execute(
                audit_query,
                'SYSTEM_SETUP',
                interaction.user.id,
                details  # Pass JSON string
            )

            await progress_msg.edit(
                content="✅ DraXon OCULUS setup completed successfully!"
            )

        except Exception as e:
            error_msg = f"❌ Error during setup: {str(e)}"
            await progress_msg.edit(content=error_msg)
            logger.error(f"Setup error: {e}")
            
            # Log error
            audit_query = """
            INSERT INTO v3_audit_logs (
                action_type, actor_id, details
            ) VALUES ($1, $2::BIGINT, $3)
            """
            details = json.dumps({  # Convert dict to JSON string
                'status': 'error',
                'error': str(e)
            })
            await self.bot.db.execute(
                audit_query,
                'SYSTEM_SETUP',
                interaction.user.id,
                details  # Pass JSON string
            )

    async def _setup_channels(self, guild: discord.Guild):
        """Set up channels"""
        # Create category if it doesn't exist
        category = discord.utils.get(guild.categories, name="DraXon OCULUS")
        if not category:
            category = await guild.create_category(
                "DraXon OCULUS",
                reason="DraXon OCULUS Setup"
            )

        # Create required channels
        channels = {
            'incidents': "📢 Incidents",
            'promotion': "🎉 Promotions",
            'demotion': "🔄 Demotions",
            'reminder': "📋 Reminders"
        }

        for channel_type, channel_name in channels.items():
            channel = discord.utils.get(category.channels, name=channel_name)
            if not channel:
                channel = await category.create_text_channel(
                    channel_name,
                    reason="DraXon OCULUS Setup"
                )
            
            # Store channel ID
            setattr(self.bot, f"{channel_type}_channel_id", channel.id)

        # Save channel IDs to Redis
        await self.bot._save_channel_ids()

    async def _setup_divisions(self, guild: discord.Guild):
        """Set up divisions"""
        for name, description in DIVISIONS.items():
            # Insert division
            query = """
            INSERT INTO v3_divisions (name, description)
            VALUES ($1, $2)
            ON CONFLICT (name) DO NOTHING
            """
            await self.bot.db.execute(query, name, description)

    async def _setup_roles(self, guild: discord.Guild):
        """Set up roles"""
        # Create rank roles
        for rank_name, rank_code in RANK_CODES.items():
            role = await guild.create_role(
                name=rank_name,
                reason="DraXon OCULUS Setup"
            )
            
            # Log role creation
            audit_query = """
            INSERT INTO v3_audit_logs (
                action_type, actor_id, details
            ) VALUES ($1, $2::BIGINT, $3)
            """
            details = json.dumps({  # Convert dict to JSON string
                'role_name': rank_name,
                'role_id': str(role.id),
                'rank_code': rank_code
            })
            await self.bot.db.execute(
                audit_query,
                'ROLE_CREATE',
                self.bot.user.id,
                details  # Pass JSON string
            )

        # Create division roles
        divisions_query = "SELECT * FROM v3_divisions"
        divisions = await self.bot.db.fetch(divisions_query)
        
        for division in divisions:
            role = await guild.create_role(
                name=f"{division['name']} Division",
                reason="DraXon OCULUS Setup"
            )
            
            # Update division with role ID
            update_query = """
            UPDATE v3_divisions 
            SET role_id = $1::BIGINT 
            WHERE id = $2
            """
            await self.bot.db.execute(update_query, role.id, division['id'])

    async def _sync_members(self, guild: discord.Guild):
        """Sync existing members"""
        async for guild_member in guild.fetch_members():
            if guild_member.bot:
                continue

            # Check if member exists
            member_query = """
            SELECT * FROM v3_members 
            WHERE discord_id = $1::BIGINT
            """
            member = await self.bot.db.fetchrow(member_query, guild_member.id)

            if not member:
                # Create new member
                insert_query = """
                INSERT INTO v3_members (
                    discord_id, rank, join_date
                ) VALUES ($1::BIGINT, $2, $3)
                """
                await self.bot.db.execute(
                    insert_query,
                    guild_member.id,
                    'AP',
                    datetime.utcnow()
                )

                # Log creation
                audit_query = """
                INSERT INTO v3_audit_logs (
                    action_type, actor_id, details
                ) VALUES ($1, $2::BIGINT, $3)
                """
                details = json.dumps({  # Convert dict to JSON string
                    'member_id': str(guild_member.id),
                    'initial_rank': 'AP'
                })
                await self.bot.db.execute(
                    audit_query,
                    'MEMBER_CREATE',
                    self.bot.user.id,
                    details  # Pass JSON string
                )

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
