"""Setup command for DraXon OCULUS"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from datetime import datetime
import json
import asyncpg

from src.utils.constants import (
    APP_VERSION,
    DraXon_ROLES,
    STATUS_EMOJIS,
    ROLE_HIERARCHY,
    DIVISIONS
)

logger = logging.getLogger('DraXon_OCULUS')

# ChannelSelectView class unchanged...

class SetupCog(commands.Cog):
    """DraXon OCULUS Setup and Configuration"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("Setup cog initialized")

    @app_commands.command(name="oculus-setup")
    @app_commands.describe(
        channels="Configure notification channels",
        divisions="Set up division structure",
        sync="Sync existing members"
    )
    @app_commands.checks.has_role("Magnate")
    async def oculus_setup(
        self,
        interaction: discord.Interaction,
        channels: Optional[bool] = False,
        divisions: Optional[bool] = False,
        sync: Optional[bool] = False
    ):
        """Configure DraXon OCULUS system"""
        try:
            if channels:
                embed = discord.Embed(
                    title="DraXon OCULUS Channel Setup",
                    description="Please select the channels for each notification type below.\n"
                               "All channels must be selected before confirming the setup.",
                    color=discord.Color.blue()
                )
                
                view = ChannelSelectView(self.bot)
                await interaction.response.send_message(
                    embed=embed,
                    view=view,
                    ephemeral=True
                )
                return

            # Create progress message for other options
            await interaction.response.send_message(
                "🔄 Starting DraXon OCULUS setup...",
                ephemeral=True
            )
            progress_msg = await interaction.original_response()

            if divisions:
                await progress_msg.edit(content="🏢 Setting up divisions...")
                await self._setup_divisions(interaction.guild)

            if sync:
                await progress_msg.edit(content="🔄 Syncing members...")
                await self._sync_members(interaction.guild)

            # Create audit log entry
            audit_query = """
            INSERT INTO v3_audit_logs (
                action_type, actor_id, details
            ) VALUES ($1, 
                (CASE 
                    WHEN pg_typeof(actor_id) = 'bigint'::regtype THEN $2::bigint
                    ELSE $2::text
                END),
                $3)
            """
            details = json.dumps({
                'channels': channels,
                'divisions': divisions,
                'sync': sync,
                'status': 'success'
            })
            await self.bot.db.execute(
                audit_query,
                'SYSTEM_SETUP',
                str(interaction.user.id),
                details
            )

            if not channels:  # Only show completion if not doing channel setup
                await progress_msg.edit(
                    content="✅ DraXon OCULUS setup completed successfully!"
                )

        except Exception as e:
            error_msg = f"❌ Error during setup: {str(e)}"
            if not channels:  # Only edit message if not doing channel setup
                await progress_msg.edit(content=error_msg)
            logger.error(f"Setup error: {e}")
            
            # Log error
            audit_query = """
            INSERT INTO v3_audit_logs (
                action_type, actor_id, details
            ) VALUES ($1, 
                (CASE 
                    WHEN pg_typeof(actor_id) = 'bigint'::regtype THEN $2::bigint
                    ELSE $2::text
                END),
                $3)
            """
            details = json.dumps({
                'status': 'error',
                'error': str(e)
            })
            await self.bot.db.execute(
                audit_query,
                'SYSTEM_SETUP',
                str(interaction.user.id),
                details
            )

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

            # Create division role if it doesn't exist
            role = discord.utils.get(guild.roles, name=f"{name} Division")
            if not role:
                role = await guild.create_role(
                    name=f"{name} Division",
                    reason="DraXon OCULUS Setup"
                )
            
            # Update division with role ID
            update_query = """
            UPDATE v3_divisions 
            SET role_id = (CASE 
                WHEN pg_typeof(role_id) = 'bigint'::regtype THEN $1::bigint
                ELSE $1::text
            END)
            WHERE name = $2
            """
            await self.bot.db.execute(update_query, str(role.id), name)

    async def _sync_members(self, guild: discord.Guild):
        """Sync existing members"""
        async for guild_member in guild.fetch_members():
            if guild_member.bot:
                continue

            # Check if member exists
            member_query = """
            SELECT * FROM v3_members 
            WHERE discord_id = (CASE 
                WHEN pg_typeof(discord_id) = 'bigint'::regtype THEN $1::bigint
                ELSE $1::text
            END)
            """
            member = await self.bot.db.fetchrow(member_query, str(guild_member.id))

            if not member:
                # Create new member without setting rank
                insert_query = """
                INSERT INTO v3_members (
                    discord_id, join_date
                ) VALUES (
                    (CASE 
                        WHEN EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'v3_members' 
                            AND column_name = 'discord_id' 
                            AND data_type = 'bigint'
                        ) THEN $1::bigint
                        ELSE $1::text
                    END),
                    $2
                )
                """
                await self.bot.db.execute(
                    insert_query,
                    str(guild_member.id),
                    datetime.utcnow()
                )

                # Log creation
                audit_query = """
                INSERT INTO v3_audit_logs (
                    action_type, actor_id, details
                ) VALUES ($1, 
                    (CASE 
                        WHEN pg_typeof(actor_id) = 'bigint'::regtype THEN $2::bigint
                        ELSE $2::text
                    END),
                    $3)
                """
                details = json.dumps({
                    'member_id': str(guild_member.id)
                })
                await self.bot.db.execute(
                    audit_query,
                    'MEMBER_CREATE',
                    str(self.bot.user.id),
                    details
                )

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
