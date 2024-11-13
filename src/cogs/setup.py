"""Setup command for DraXon OCULUS"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional
from datetime import datetime

from src.utils.constants import (
    APP_VERSION,
    DraXon_ROLES,
    STATUS_EMOJIS,
    ROLE_HIERARCHY
)

logger = logging.getLogger('DraXon_OCULUS')

class ChannelSelectView(discord.ui.View):
    """View for channel selection during setup"""
    
    def __init__(self, bot, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.incidents_channel = None
        self.promotion_channel = None
        self.demotion_channel = None
        self.reminder_channel = None

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Incidents Channel",
        min_values=1,
        max_values=1
    )
    async def incidents_select(self, interaction: discord.Interaction, 
                             select: discord.ui.Select):
        """Handle incidents channel selection"""
        self.incidents_channel = select.values[0]
        select.disabled = True
        select.placeholder = f"Incidents Channel: {self.incidents_channel.name}"
        await self.check_completion(interaction)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Promotion Channel",
        min_values=1,
        max_values=1
    )
    async def promotion_select(self, interaction: discord.Interaction, 
                             select: discord.ui.Select):
        """Handle promotion channel selection"""
        self.promotion_channel = select.values[0]
        select.disabled = True
        select.placeholder = f"Promotion Channel: {self.promotion_channel.name}"
        await self.check_completion(interaction)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Demotion Channel",
        min_values=1,
        max_values=1
    )
    async def demotion_select(self, interaction: discord.Interaction, 
                             select: discord.ui.Select):
        """Handle demotion channel selection"""
        self.demotion_channel = select.values[0]
        select.disabled = True
        select.placeholder = f"Demotion Channel: {self.demotion_channel.name}"
        await self.check_completion(interaction)

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="Select Reminder Channel",
        min_values=1,
        max_values=1
    )
    async def reminder_select(self, interaction: discord.Interaction, 
                            select: discord.ui.Select):
        """Handle reminder channel selection"""
        self.reminder_channel = select.values[0]
        select.disabled = True
        select.placeholder = f"Reminder Channel: {self.reminder_channel.name}"
        await self.check_completion(interaction)

    @discord.ui.button(label="Reset Selections", style=discord.ButtonStyle.secondary)
    async def reset_button(self, interaction: discord.Interaction, 
                          button: discord.ui.Button):
        """Reset all selections"""
        for child in self.children:
            if isinstance(child, discord.ui.ChannelSelect):
                child.disabled = False
                child.placeholder = child.placeholder.split(":")[0]
        
        self.incidents_channel = None
        self.promotion_channel = None
        self.demotion_channel = None
        self.reminder_channel = None
        
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Confirm Setup", style=discord.ButtonStyle.green, disabled=True)
    async def confirm_button(self, interaction: discord.Interaction, 
                           button: discord.ui.Button):
        """Process the final setup"""
        try:
            # Store channel IDs in Redis
            channel_data = {
                'incidents': str(self.incidents_channel.id),
                'promotion': str(self.promotion_channel.id),
                'demotion': str(self.demotion_channel.id),
                'reminder': str(self.reminder_channel.id)
            }
            
            await self.bot.redis.hmset('channel_ids', channel_data)
            
            # Update bot's channel IDs
            self.bot.incidents_channel_id = self.incidents_channel.id
            self.bot.promotion_channel_id = self.promotion_channel.id
            self.bot.demotion_channel_id = self.demotion_channel.id
            self.bot.reminder_channel_id = self.reminder_channel.id

            # Create confirmation embed
            embed = discord.Embed(
                title="✅ Setup Complete",
                description="Channel configuration has been updated:",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Channel Assignments",
                value=f"📢 Incidents: {self.incidents_channel.mention}\n"
                      f"🎉 Promotions: {self.promotion_channel.mention}\n"
                      f"🔄 Demotions: {self.demotion_channel.mention}\n"
                      f"📋 Reminders: {self.reminder_channel.mention}",
                inline=False
            )

            # Disable all components
            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"Error in setup confirmation: {e}")
            await interaction.response.send_message(
                "❌ An error occurred during setup. Please try again.",
                ephemeral=True
            )

    async def check_completion(self, interaction: discord.Interaction):
        """Check if all channels have been selected"""
        all_selected = all([
            self.incidents_channel,
            self.promotion_channel,
            self.demotion_channel,
            self.reminder_channel
        ])
        
        # Enable/disable confirm button based on completion
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Confirm Setup":
                child.disabled = not all_selected
        
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        """Handle timeout by disabling all components"""
        for child in self.children:
            child.disabled = True

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
                # Show channel selection UI
                embed = discord.Embed(
                    title="DraXon OCULUS Channel Setup",
                    description="Please select the channels for each notification type below.\n"
                               "All channels must be selected before confirming the setup.",
                    color=discord.Color.blue()
                )
                
                view = ChannelSelectView(self.bot)
                await progress_msg.edit(content=None, embed=embed, view=view)

                # Wait for channel selection to complete
                await view.wait()
                if not all([view.incidents_channel, view.promotion_channel, 
                           view.demotion_channel, view.reminder_channel]):
                    await progress_msg.edit(
                        content="❌ Setup cancelled - channel selection incomplete.",
                        embed=None,
                        view=None
                    )
                    return

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
            await self.bot.db.execute(
                audit_query,
                'SYSTEM_SETUP',
                interaction.user.id,
                {
                    'channels': channels,
                    'divisions': divisions,
                    'roles': roles,
                    'sync': sync,
                    'status': 'success'
                }
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
            await self.bot.db.execute(
                audit_query,
                'SYSTEM_SETUP',
                interaction.user.id,
                {
                    'status': 'error',
                    'error': str(e)
                }
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
            await self.bot.db.execute(
                audit_query,
                'ROLE_CREATE',
                self.bot.user.id,
                {
                    'role_name': rank_name,
                    'role_id': str(role.id),  # Store as string to avoid int32 overflow
                    'rank_code': rank_code
                }
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
                    datetime.now(timezone.utc)
                )

                # Log creation
                audit_query = """
                INSERT INTO v3_audit_logs (
                    action_type, actor_id, details
                ) VALUES ($1, $2::BIGINT, $3)
                """
                await self.bot.db.execute(
                    audit_query,
                    'MEMBER_CREATE',
                    self.bot.user.id,
                    {
                        'member_id': str(guild_member.id),  # Store as string to avoid int32 overflow
                        'initial_rank': 'AP'
                    }
                )

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
