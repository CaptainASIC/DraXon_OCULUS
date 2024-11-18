"""RSI account integration for DraXon OCULUS"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import discord
from discord import app_commands
from discord.ext import commands
import logging
import json
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import asyncio

from src.utils.constants import (
    COMPARE_STATUS,
    CACHE_SETTINGS,
    SYSTEM_MESSAGES,
    RSI_CONFIG
)
from src.utils.rsi_scraper import RSIScraper
from src.config.settings import get_settings

logger = logging.getLogger('DraXon_OCULUS')

class UpdateAccountView(discord.ui.View):
    """View for updating linked account"""
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Update Handle", style=discord.ButtonStyle.primary)
    async def update_handle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show modal to update RSI handle"""
        modal = LinkAccountModal()
        modal.cog = self.cog
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Sync Existing", style=discord.ButtonStyle.secondary)
    async def sync_existing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sync existing linked account"""
        await interaction.response.defer(ephemeral=True)
        try:
            async with self.cog.bot.db.acquire() as conn:
                existing = await conn.fetchrow(
                    'SELECT handle FROM rsi_members WHERE discord_id = $1',
                    str(interaction.user.id)
                )
                
                if not existing:
                    await interaction.followup.send(
                        "❌ No linked account found to sync.",
                        ephemeral=True
                    )
                    return

                # Get fresh user info
                user_info = await self.cog.get_user_info(existing['handle'])
                if not user_info:
                    await interaction.followup.send(
                        "❌ Failed to fetch updated account information.",
                        ephemeral=True
                    )
                    return

                # Process the account link
                success = await self.cog.process_account_link(interaction, user_info)
                if not success:
                    await interaction.followup.send(
                        "❌ Failed to sync account. Please try again later.",
                        ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Error syncing account: {e}")
            await interaction.followup.send(
                "❌ An error occurred while syncing your account.",
                ephemeral=True
            )

class LinkAccountModal(discord.ui.Modal, title='Link RSI Account'):
    def __init__(self):
        super().__init__()
        self.handle = discord.ui.TextInput(
            label='RSI Handle',
            placeholder='Enter your RSI Handle (case sensitive)...',
            required=True,
            max_length=50
        )
        self.add_item(self.handle)
        self.cog = None

    async def on_submit(self, interaction: discord.Interaction):
        """Handle account linking modal submission"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            if not self.cog:
                raise ValueError("Modal not properly initialized")
                
            logger.info(f"Processing RSI handle link: {self.handle.value}")
            
            # Get user info
            user_info = await self.cog.get_user_info(self.handle.value)
            if not user_info:
                await interaction.followup.send(
                    "❌ Invalid RSI Handle or RSI website error. Please check your handle and try again.",
                    ephemeral=True
                )
                return

            # Process the account link
            success = await self.cog.process_account_link(interaction, user_info)
            if not success:
                await interaction.followup.send(
                    "❌ Failed to link account. Please try again later.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error processing account link: {e}")
            await interaction.followup.send(
                "❌ An error occurred while linking your account.",
                ephemeral=True
            )

class RSIIntegrationCog(commands.Cog):
    """Handles RSI account integration and organization tracking"""
    
    def __init__(self, bot):
        self.bot = bot
        self.settings = get_settings()
        self.scraper = RSIScraper(self.bot.session, self.bot.redis)
        logger.info("RSI Integration cog initialized")

    async def get_org_info(self) -> Optional[Dict[str, Any]]:
        """Get organization information"""
        try:
            return await self.scraper.get_organization_info(RSI_CONFIG['ORGANIZATION_SID'])
        except Exception as e:
            logger.error(f"Error fetching org info: {e}")
            return None

    async def get_user_info(self, handle: str) -> Optional[Dict[str, Any]]:
        """Get user information"""
        try:
            return await self.scraper.get_user_info(handle)
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            return None

    async def get_org_members(self) -> List[Dict[str, Any]]:
        """Get all organization members"""
        try:
            # Check Redis cache
            cache_key = f'org_members:{RSI_CONFIG["ORGANIZATION_SID"]}'
            cached = await self.bot.redis.get(cache_key)
            if cached:
                return json.loads(cached)

            members = []
            page = 1
            
            while True:
                page_members = await self.scraper.get_organization_members(
                    RSI_CONFIG['ORGANIZATION_SID'],
                    page
                )
                
                if not page_members:
                    break

                members.extend(page_members)
                
                if len(page_members) < RSI_CONFIG['MEMBERS_PER_PAGE']:
                    break
                    
                page += 1
                await asyncio.sleep(1)  # Rate limiting

            # Cache the results
            if members:
                await self.bot.redis.set(
                    cache_key,
                    json.dumps(members),
                    ex=CACHE_SETTINGS['ORG_DATA_TTL']
                )
                logger.info(f"Cached {len(members)} org members")
            else:
                logger.error("No org members found")

            return members

        except Exception as e:
            logger.error(f"Error fetching org members: {e}")
            return []

    async def process_account_link(self, 
                                 interaction: discord.Interaction,
                                 user_data: Dict[str, Any]) -> bool:
        """Process account linking and verification"""
        try:
            profile = user_data.get('profile', {})
            main_org = user_data.get('organization', {})
            affiliations = user_data.get('affiliation', [])

            if not profile:
                await interaction.followup.send(
                    "❌ Could not retrieve profile information.",
                    ephemeral=True
                )
                return False

            # Check DraXon membership
            is_main_org = main_org.get('sid') == RSI_CONFIG['ORGANIZATION_SID']
            is_affiliate = any(
                org.get('sid') == RSI_CONFIG['ORGANIZATION_SID'] 
                for org in affiliations
            )

            if not is_main_org and not is_affiliate:
                await interaction.followup.send(
                    "⚠️ Your RSI Handle was found, but you don't appear to be a member "
                    "of our organization. Please join our organization first and try again.",
                    ephemeral=True
                )
                return False

            # Get DraXon org data
            draxon_org = (
                main_org if is_main_org else 
                next(org for org in affiliations 
                     if org.get('sid') == RSI_CONFIG['ORGANIZATION_SID'])
            )

            # Convert timestamp to datetime
            current_time = datetime.utcnow()

            # Prepare data for storage
            rsi_data = {
                'discord_id': str(interaction.user.id),
                'sid': profile.get('id', '').replace('#', ''),
                'handle': profile.get('handle'),
                'display_name': profile.get('display'),
                'enlisted': profile.get('enlisted'),
                'org_sid': draxon_org.get('sid'),
                'org_name': draxon_org.get('name'),
                'org_rank': draxon_org.get('rank'),
                'org_stars': draxon_org.get('stars', 0),
                'org_status': 'Main' if is_main_org else 'Affiliate',
                'verified': True,
                'last_updated': current_time,
                'raw_data': user_data
            }

            # Store in database
            async with self.bot.db.acquire() as conn:
                async with conn.transaction():
                    # Store member data
                    await conn.execute('''
                        INSERT INTO rsi_members (
                            discord_id, handle, sid, display_name, enlisted,
                            org_status, org_rank, org_stars, verified,
                            last_updated, raw_data
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                        ON CONFLICT (discord_id) DO UPDATE
                        SET handle = EXCLUDED.handle,
                            sid = EXCLUDED.sid,
                            display_name = EXCLUDED.display_name,
                            enlisted = EXCLUDED.enlisted,
                            org_status = EXCLUDED.org_status,
                            org_rank = EXCLUDED.org_rank,
                            org_stars = EXCLUDED.org_stars,
                            verified = EXCLUDED.verified,
                            last_updated = EXCLUDED.last_updated,
                            raw_data = EXCLUDED.raw_data
                    ''', str(interaction.user.id), rsi_data['handle'], rsi_data['sid'],
                        rsi_data['display_name'], rsi_data['enlisted'], rsi_data['org_status'],
                        rsi_data['org_rank'], rsi_data['org_stars'], rsi_data['verified'],
                        rsi_data['last_updated'], json.dumps(rsi_data['raw_data']))

                    # Log verification
                    await conn.execute('''
                        INSERT INTO verification_history (
                            discord_id, action, status, timestamp, details
                        ) VALUES ($1, $2, $3, NOW(), $4)
                    ''', str(interaction.user.id), 'link', True, 
                        json.dumps({
                            'handle': rsi_data['handle'],
                            'org_status': rsi_data['org_status']
                        }))

            # Create response embed
            embed = discord.Embed(
                title="✅ RSI Account Successfully Linked!",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            # Account Information
            embed.add_field(
                name="Account Information",
                value=f"🔹 Handle: {rsi_data['handle']}\n"
                      f"🔹 Display Name: {rsi_data['display_name']}\n"
                      f"🔹 Citizen ID: {rsi_data['sid']}\n"
                      f"🔹 Enlisted: {rsi_data['enlisted'][:10]}",
                inline=False
            )
            
            # Organization Status
            embed.add_field(
                name="Organization Status",
                value=f"🔹 Organization: {rsi_data['org_name']}\n"
                      f"🔹 Status: {rsi_data['org_status']}\n"
                      f"🔹 Rank: {rsi_data['org_rank']}\n"
                      f"🔹 Stars: {'⭐' * rsi_data['org_stars']}",
                inline=False
            )

            # Cache member data
            await self.bot.redis.set(
                f'member:{interaction.user.id}',
                json.dumps({**rsi_data, 'last_updated': rsi_data['last_updated'].isoformat()}),
                ex=CACHE_SETTINGS['MEMBER_DATA_TTL']
            )

            await interaction.followup.send(embed=embed, ephemeral=True)
            return True

        except Exception as e:
            logger.error(f"Error processing account link: {e}")
            return False

    @app_commands.command(
        name="draxon-link",
        description="Link your RSI account with Discord"
    )
    async def link_account(self, interaction: discord.Interaction):
        """Command to link RSI account"""
        try:
            # Check if already linked
            async with self.bot.db.acquire() as conn:
                existing = await conn.fetchrow(
                    'SELECT * FROM rsi_members WHERE discord_id = $1',
                    str(interaction.user.id)
                )
                
                if existing:
                    view = UpdateAccountView(self)
                    await interaction.response.send_message(
                        "⚠️ You already have a linked RSI account. Would you like to update your handle or sync your existing account?",
                        view=view,
                        ephemeral=True
                    )
                    return

            # Show link modal
            modal = LinkAccountModal()
            modal.cog = self
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"Error in link_account command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while processing your request.",
                ephemeral=True
            )

async def setup(bot):
    """Safe setup function for RSI integration cog"""
    try:
        if not bot.get_cog('RSIIntegrationCog'):
            await bot.add_cog(RSIIntegrationCog(bot))
            logger.info('RSI Integration cog loaded successfully')
        else:
            logger.info('RSI Integration cog already loaded, skipping')
    except Exception as e:
        logger.error(f'Error loading RSI Integration cog: {e}')
        raise
