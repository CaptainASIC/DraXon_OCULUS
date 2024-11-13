"""Application system for DraXon OCULUS v3"""

import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
from datetime import datetime, timezone

from src.utils.constants import (
    RANK_CODES,
    DIVISIONS,
    APPLICATION_SETTINGS,
    V3_SYSTEM_MESSAGES
)

logger = logging.getLogger('DraXon_OCULUS')

class VotingView(discord.ui.View):
    def __init__(self, bot, application_id: int, required_voters: List[dict]):
        super().__init__(timeout=APPLICATION_SETTINGS['VOTE_TIMEOUT'])
        self.bot = bot
        self.application_id = application_id
        self.required_voters = required_voters

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "APPROVE")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._handle_vote(interaction, "REJECT")

    async def _handle_vote(self, interaction: discord.Interaction, vote_type: str):
        """Handle vote submission"""
        # Check if user is allowed to vote
        voter_query = """
        SELECT * FROM v3_members 
        WHERE discord_id = $1::BIGINT
        """
        voter = await self.bot.db.fetchrow(voter_query, interaction.user.id)
        
        if not any(v['id'] == voter['id'] for v in self.required_voters):
            await interaction.response.send_message(
                "❌ You are not authorized to vote on this application.",
                ephemeral=True
            )
            return

        # Check if already voted
        vote_query = """
        SELECT * FROM v3_votes 
        WHERE application_id = $1 AND voter_id = $2
        """
        existing_vote = await self.bot.db.fetchrow(
            vote_query,
            self.application_id,
            voter['id']
        )

        if existing_vote:
            await interaction.response.send_message(
                "❌ You have already voted on this application.",
                ephemeral=True
            )
            return

        # Create vote modal for comment
        class VoteModal(discord.ui.Modal, title=f"{vote_type} Application"):
            comment = discord.ui.TextInput(
                label="Comment",
                style=discord.TextStyle.paragraph,
                placeholder="Provide a reason for your vote...",
                required=True,
                max_length=1000
            )

            async def on_submit(self, modal_inter: discord.Interaction):
                # Record vote
                vote_insert = """
                INSERT INTO v3_votes (
                    application_id, voter_id, vote, comment
                ) VALUES ($1, $2, $3, $4)
                """
                await self.bot.db.execute(
                    vote_insert,
                    self.application_id,
                    voter['id'],
                    vote_type,
                    str(self.comment)
                )

                # Get all votes
                votes_query = """
                SELECT * FROM v3_votes 
                WHERE application_id = $1
                """
                votes = await self.bot.db.fetch(votes_query, self.application_id)

                if len(votes) >= len(self.required_voters):
                    # Process final decision
                    approvals = sum(1 for v in votes if v['vote'] == "APPROVE")
                    
                    # Update application status
                    status = "APPROVED" if approvals == len(self.required_voters) else "REJECTED"
                    update_query = """
                    UPDATE v3_applications 
                    SET status = $1 
                    WHERE id = $2 
                    RETURNING *
                    """
                    application = await self.bot.db.fetchrow(
                        update_query,
                        status,
                        self.application_id
                    )
                    
                    # Get position title
                    pos_query = """
                    SELECT title FROM v3_positions 
                    WHERE id = $1
                    """
                    position = await self.bot.db.fetchrow(
                        pos_query,
                        application['position_id']
                    )

                    await interaction.channel.send(
                        V3_SYSTEM_MESSAGES['APPLICATION'][status].format(
                            position=position['title']
                        )
                    )

                await modal_inter.response.send_message(
                    f"✅ Vote recorded: {vote_type}",
                    ephemeral=True
                )

        await interaction.response.send_modal(VoteModal())

class Applications(commands.Cog):
    """DraXon Applications System"""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Applications cog initialized")

    @app_commands.command(name="draxon-apply")
    async def apply(self, interaction: discord.Interaction):
        """Apply for a position within DraXon"""
        
        # Get member's current rank and division
        member_query = """
        SELECT * FROM v3_members 
        WHERE discord_id = $1::BIGINT
        """
        member = await self.bot.db.fetchrow(member_query, interaction.user.id)
        
        if not member:
            await interaction.response.send_message(
                "❌ You must be a DraXon member to apply for positions.",
                ephemeral=True
            )
            return

        # Check if member has pending applications
        pending_query = """
        SELECT * FROM v3_applications 
        WHERE applicant_id = $1 AND status = 'PENDING'
        """
        pending = await self.bot.db.fetchrow(pending_query, member['id'])

        if pending:
            await interaction.response.send_message(
                "❌ You already have a pending application.",
                ephemeral=True
            )
            return

        # Get divisions
        divisions_query = "SELECT * FROM v3_divisions"
        divisions = await self.bot.db.fetch(divisions_query)
        
        # Create division selection dropdown
        division_select = discord.ui.Select(
            placeholder="Select a division",
            options=[
                discord.SelectOption(
                    label=div['name'],
                    description=div['description'][:100],
                    value=str(div['id'])
                ) for div in divisions
            ]
        )

        async def division_callback(inter: discord.Interaction):
            # Get available positions for selected division
            positions_query = """
            SELECT * FROM v3_positions 
            WHERE division_id = $1 AND status = 'OPEN'
            """
            positions = await self.bot.db.fetch(positions_query, int(division_select.values[0]))

            if not positions:
                await inter.response.send_message(
                    "❌ No open positions available in this division.",
                    ephemeral=True
                )
                return

            # Create position selection dropdown
            position_select = discord.ui.Select(
                placeholder="Select a position",
                options=[
                    discord.SelectOption(
                        label=pos['title'],
                        description=f"Required Rank: {pos['required_rank']}",
                        value=str(pos['id'])
                    ) for pos in positions
                ]
            )

            async def position_callback(pos_inter: discord.Interaction):
                # Create application modal
                class ApplicationModal(discord.ui.Modal, title="DraXon Position Application"):
                    experience = discord.ui.TextInput(
                        label="Previous Experience",
                        style=discord.TextStyle.paragraph,
                        placeholder="Describe your relevant experience...",
                        required=True,
                        max_length=1000
                    )
                    
                    statement = discord.ui.TextInput(
                        label="Position Statement",
                        style=discord.TextStyle.paragraph,
                        placeholder="Why do you want this position?",
                        required=True,
                        max_length=1000
                    )
                    
                    additional = discord.ui.TextInput(
                        label="Additional Information",
                        style=discord.TextStyle.paragraph,
                        placeholder="Any other relevant information...",
                        required=False,
                        max_length=1000
                    )

                    async def on_submit(self, modal_inter: discord.Interaction):
                        # Get position details
                        position_query = """
                        SELECT p.*, d.name as division_name 
                        FROM v3_positions p 
                        JOIN v3_divisions d ON p.division_id = d.id 
                        WHERE p.id = $1
                        """
                        position = await self.bot.db.fetchrow(
                            position_query, 
                            int(position_select.values[0])
                        )

                        # Create application thread
                        thread = await interaction.channel.create_thread(
                            name=f"Application: {position['title']}",
                            type=discord.ChannelType.private_thread
                        )

                        # Create application record
                        app_query = """
                        INSERT INTO v3_applications (
                            applicant_id, position_id, thread_id, 
                            previous_experience, position_statement, additional_info
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING id
                        """
                        app_id = await self.bot.db.fetchval(
                            app_query,
                            member['id'],
                            position['id'],
                            thread.id,
                            str(self.experience),
                            str(self.statement),
                            str(self.additional)
                        )

                        # Get required voters
                        required_voters = await self._get_required_voters(position['required_rank'])
                        voter_mentions = [f"• <@{v['discord_id']}> ⌛" for v in required_voters]

                        # Create voting view
                        voting_view = VotingView(self.bot, app_id, required_voters)

                        # Send initial thread message
                        await thread.send(
                            V3_SYSTEM_MESSAGES['APPLICATION']['THREAD_CREATED'].format(
                                position=position['title'],
                                applicant=interaction.user.mention,
                                rank=member['rank'],
                                division=position['division_name'],
                                details=f"""
Previous Experience:
{self.experience}

Position Statement:
{self.statement}

Additional Information:
{self.additional if self.additional else 'None provided'}
                                """,
                                current=0,
                                required=len(required_voters),
                                voters="\n".join(voter_mentions)
                            ),
                            view=voting_view
                        )

                        await modal_inter.response.send_message(
                            "✅ Application submitted successfully!",
                            ephemeral=True
                        )

                # Show application modal
                await pos_inter.response.send_modal(ApplicationModal())

            position_select.callback = position_callback
            view = discord.ui.View()
            view.add_item(position_select)
            await inter.response.edit_message(view=view)

        division_select.callback = division_callback
        view = discord.ui.View()
        view.add_item(division_select)
        await interaction.response.send_message(
            "Select a division to apply for:",
            view=view,
            ephemeral=True
        )

    async def _get_required_voters(self, position_rank: str) -> List[dict]:
        """Get required voters based on position rank"""
        if position_rank == 'EXE':
            query = """
            SELECT * FROM v3_members 
            WHERE rank IN ('CR', 'MG')
            """
        elif position_rank == 'TL':
            query = """
            SELECT * FROM v3_members 
            WHERE rank IN ('EXE', 'CR')
            """
        else:  # EMP
            query = """
            SELECT * FROM v3_members 
            WHERE rank IN ('TL', 'EXE')
            """
        return await self.bot.db.fetch(query)

async def setup(bot):
    await bot.add_cog(Applications(bot))
