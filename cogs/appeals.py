# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import asyncio
import logging
import discord
from discord.ext import commands
from dashboard_client import client
log = logging.getLogger(__name__)

class AppealsCog(commands.Cog, name='Appeals'):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.TextChannel):
            return
        prefix = getattr(client, 'appeals_channel_prefix', None)
        if not prefix:
            return
        if not channel.name.startswith(prefix):
            return
        try:
            await self._handle_appeal_channel(channel)
        except Exception:
            log.exception('appeals: failed to handle channel %s', channel.id)

    async def _handle_appeal_channel(self, channel: discord.TextChannel) -> None:
        opener_id: int | None = None
        for _ in range(8):
            await asyncio.sleep(3)
            async for msg in channel.history(limit=20, oldest_first=True):
                if not msg.author.bot:
                    opener_id = msg.author.id
                    break
            if opener_id:
                break
        if not opener_id:
            for member in channel.members:
                if not member.bot and channel.permissions_for(member).send_messages:
                    opener_id = member.id
                    break
        if not opener_id:
            await channel.send('Could not identify the ticket opener. Please have the user post in the channel.')
            return
        data = await client.fetch_active_bans(str(channel.guild.id), str(opener_id))
        if data is None:
            return
        if data.get('player_id') is None:
            await channel.send(f'<@{opener_id}> Your Discord account is not linked to a Minecraft account. Use /link <username> in this server, then open a new ticket.')
            return
        bans = data.get('active_bans', [])
        if not bans:
            await channel.send(f'<@{opener_id}> You have no active bans to appeal.')
            return
        await self._prompt_appeal(channel, opener_id, bans)

    async def _prompt_appeal(self, channel: discord.TextChannel, opener_id: int, bans: list) -> None:
        if len(bans) == 1:
            ban = bans[0]
            view = SingleBanView(client, opener_id, channel, ban)
            embed = discord.Embed(title='Appeal your ban', description=f"You are appealing your **{ban['type']}** for reason: {ban['reason']}", color=discord.Color.blurple())
            await channel.send(content=f'<@{opener_id}>', embed=embed, view=view)
        else:
            view = MultiBanView(client, opener_id, channel, bans)
            embed = discord.Embed(title='Select the ban you want to appeal', description=f'You have {len(bans)} active bans. Pick one below.', color=discord.Color.blurple())
            await channel.send(content=f'<@{opener_id}>', embed=embed, view=view)

class AppealReasonModal(discord.ui.Modal, title='Appeal reason'):
    reason = discord.ui.TextInput(label='Why should this ban be lifted?', style=discord.TextStyle.paragraph, min_length=10, max_length=2000, required=True)

    def __init__(self, dashboard_client, opener_id: int, channel: discord.TextChannel, punishment_id: int) -> None:
        super().__init__()
        self.dashboard_client = dashboard_client
        self.opener_id = opener_id
        self.channel = channel
        self.punishment_id = punishment_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message('Only the ticket opener can submit this appeal.', ephemeral=True)
            return
        result = await self.dashboard_client.submit_appeal(str(interaction.guild.id), str(self.opener_id), str(self.channel.id), self.punishment_id, str(self.reason.value))
        if result.get('success'):
            await interaction.response.send_message('Appeal submitted. Staff will review it shortly.')
        else:
            code = result.get('code', 'UNKNOWN')
            msg_map = {'DUPLICATE_PENDING': 'You already have a pending appeal for this ban.', 'NOT_LINKED': 'Your Discord account is not linked to a Minecraft account.', 'NO_ACTIVE_BAN': 'You have no active bans to appeal.', 'INVALID_PUNISHMENT': 'That punishment is not eligible for appeal.'}
            await interaction.response.send_message(msg_map.get(code, f'Could not submit appeal: {code}'))

class SingleBanView(discord.ui.View):

    def __init__(self, dashboard_client, opener_id: int, channel: discord.TextChannel, ban: dict) -> None:
        super().__init__(timeout=600)
        self.dashboard_client = dashboard_client
        self.opener_id = opener_id
        self.channel = channel
        self.ban = ban

    @discord.ui.button(label='Write appeal', style=discord.ButtonStyle.primary)
    async def on_click(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message('Only the ticket opener can submit this appeal.', ephemeral=True)
            return
        await interaction.response.send_modal(AppealReasonModal(self.dashboard_client, self.opener_id, self.channel, int(self.ban['id'])))

class MultiBanView(discord.ui.View):

    def __init__(self, dashboard_client, opener_id: int, channel: discord.TextChannel, bans: list) -> None:
        super().__init__(timeout=600)
        self.dashboard_client = dashboard_client
        self.opener_id = opener_id
        self.channel = channel
        self.bans = bans
        options = [discord.SelectOption(label=f"{b['type']} - {(b['reason'] or '(no reason)')[:50]}", value=str(b['id']), description=f"Issued {b.get('issued_at')}") for b in bans[:25]]
        select = discord.ui.Select(placeholder='Pick the ban to appeal', options=options, min_values=1, max_values=1)
        select.callback = self._on_pick
        self.add_item(select)

    async def _on_pick(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.opener_id:
            await interaction.response.send_message('Only the ticket opener can submit this appeal.', ephemeral=True)
            return
        picked_id = int(interaction.data['values'][0])
        await interaction.response.send_modal(AppealReasonModal(self.dashboard_client, self.opener_id, self.channel, picked_id))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AppealsCog(bot))
