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
    COMMAND_HELP
)

logger = logging.getLogger('DraXon_OCULUS')

class VoteView(discord.ui.View):
    """View for voting on applications"""
    def __init__(self, bot, application_id: int):
        super().__init__(timeout=None)  # Buttons should not timeout
        self.bot = bot
        self.application_id = application_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="vote_approve")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_vote(interaction, "APPROVE")

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="vote_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_vote(interaction, "DENY")

    async def handle_vote(self, interaction: discord.Interaction, vote_type: str):
        try:
            # Check if user has management or leadership role
            member_roles = [role.name for role in interaction.user.roles]
            if not any(role in member_roles for role in 
                      DraXon_ROLES['leadership'] + 
                      DraXon_ROLES['management']):
                await interaction.response.send_message(
                    "❌ Only management and leadership can vote on applications.",
                    ephemeral=True
                )
                return

            # Get application details
            app_query = """
            SELECT a.*, m.discord_id 
            FROM v3_applications a
            JOIN v3_members m ON a.applicant_id = m.id
            WHERE a.id = $1
            """
            application = await self.bot.db.fetchrow(app_query, self.application_id)
            
            if not application:
                await interaction.response.send_message(
                    "❌ Application not found.",
                    ephemeral=True
                )
                return

            if application['status'] != 'PENDING':
                await interaction.response.send_message(
                    "❌ This application has already been processed.",
                    ephemeral=True
                )
                return

            # Get voter's member ID
            voter_query = """
            SELECT id FROM v3_members
            WHERE discord_id = $1
            """
            voter_id = await self.bot.db.fetchval(
                voter_query,
                str(interaction.user.id)
            )

            # Check if already voted
            vote_check = """
            SELECT id FROM v3_votes
            WHERE application_id = $1 AND voter_id = $2
            """
            existing_vote = await self.bot.db.fetchval(
                vote_check,
                self.application_id,
                voter_id
            )

            if existing_vote:
                await interaction.response.send_message(
                    "❌ You have already voted on this application.",
                    ephemeral=True
                )
                return

            # Record vote
            vote_query = """
            INSERT INTO v3_votes (application_id, voter_id, vote)
            VALUES ($1, $2, $3)
            """
            await self.bot.db.execute(
                vote_query,
                self.application_id,
                voter_id,
                vote_type
            )

            # Get current vote count
            vote_count = """
            SELECT COUNT(*) FROM v3_votes
            WHERE application_id = $1 AND vote = 'APPROVE'
            """
            approve_count = await self.bot.db.fetchval(vote_count, self.application_id)
            required_votes = APPLICATION_SETTINGS['MIN_VOTES_REQUIRED']['TL']

            # Send vote update message
            update_msg = V3_SYSTEM_MESSAGES['APPLICATION']['VOTE_UPDATE'].format(
                voter=interaction.user.mention,
                vote=vote_type,
                current=approve_count,
                required=required_votes
            )
            await interaction.response.send_message(update_msg)

            # Check if application should be approved/rejected
            if approve_count >= required_votes:
                await self.process_approval(interaction, application)
            elif vote_type == "DENY":
                await self.process_rejection(interaction, application)

        except Exception as e:
            logger.error(f"Error handling vote: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while processing your vote.",
                ephemeral=True
            )

    async def process_approval(self, interaction: discord.Interaction, application):
        try:
            # Update application status
            await self.bot.db.execute(
                "UPDATE v3_applications SET status = 'APPROVED' WHERE id = $1",
                self.application_id
            )

            # Get the applicant's member object
            applicant = await interaction.guild.fetch_member(int(application['discord_id']))
            if not applicant:
                await interaction.followup.send("❌ Could not find applicant member.")
                return

            # Get current roles
            current_roles = [role.name for role in applicant.roles]

            # Only remove Employee role if they're not already Team Leader or higher
            if not any(role in current_roles for role in 
                      DraXon_ROLES['leadership'] + 
                      DraXon_ROLES['management']):
                # Remove Employee role if they have it
                employee_role = discord.utils.get(interaction.guild.roles, name="Employee")
                if employee_role and employee_role in applicant.roles:
                    await applicant.remove_roles(employee_role)

                # Add Team Leader role
                team_leader_role = discord.utils.get(interaction.guild.roles, name="Team Leader")
                if team_leader_role:
                    await applicant.add_roles(team_leader_role)

            # Add division role
            division_role = discord.utils.get(interaction.guild.roles, name=application['division_name'])
            if division_role:
                await applicant.add_roles(division_role)

            # Send approval message
            approval_msg = V3_SYSTEM_MESSAGES['APPLICATION']['APPROVED'].format(
                position=f"{application['division_name']} Team Leader",
                applicant=applicant.mention,
                division=application['division_name']
            )
            await interaction.followup.send(approval_msg)

            # Disable the voting buttons
            self.approve.disabled = True
            self.deny.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            logger.error(f"Error processing approval: {e}")
            await interaction.followup.send("❌ An error occurred while processing the approval.")

    async def process_rejection(self, interaction: discord.Interaction, application):
        try:
            # Update application status
            await self.bot.db.execute(
                "UPDATE v3_applications SET status = 'REJECTED' WHERE id = $1",
                self.application_id
            )

            # Get the applicant's member object
            applicant = await interaction.guild.fetch_member(int(application['discord_id']))
            
            # Send rejection message
            rejection_msg = V3_SYSTEM_MESSAGES['APPLICATION']['REJECTED'].format(
                position=f"{application['division_name']} Team Leader",
                applicant=applicant.mention if applicant else "Applicant"
            )
            await interaction.followup.send(rejection_msg)

            # Disable the voting buttons
            self.approve.disabled = True
            self.deny.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            logger.error(f"Error processing rejection: {e}")
            await interaction.followup.send("❌ An error occurred while processing the rejection.")

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

            # Create and send message with vote buttons
            vote_view = VoteView(self.bot, application_id)
            await thread.send(message, view=vote_view)

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

    @app_commands.command(name="oculus-about")
    async def about(self, interaction: discord.Interaction):
        """Display information about OCULUS and available commands"""
        try:
            # Get user's roles
            member_roles = [role.name for role in interaction.user.roles]
            
            # Build available commands list based on roles
            commands = COMMAND_HELP['all'].copy()  # Everyone gets these
            
            if any(role in member_roles for role in DraXon_ROLES['staff']):
                commands.extend(COMMAND_HELP['staff'])
            
            if any(role in member_roles for role in DraXon_ROLES['management']):
                commands.extend(COMMAND_HELP['management'])
            
            if any(role in member_roles for role in DraXon_ROLES['leadership']):
                commands.extend(COMMAND_HELP['leadership'])
            
            # Format embed
            embed = discord.Embed(
                title="DraXon OCULUS",
                description=f"Version {APP_VERSION}\n{BOT_DESCRIPTION}",
                color=discord.Color.blue()
            )
            
            # Add commands field
            commands_text = "\n".join(f"`{cmd}` - {desc}" for cmd, desc in commands)
            embed.add_field(
                name="Available Commands",
                value=commands_text,
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in about command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while displaying bot information.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Applications(bot))
