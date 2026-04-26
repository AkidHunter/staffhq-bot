# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import discord
from discord.ext import commands
import config as cfg
from dashboard_client import client, now_ms, DashboardError

class ActivityCog(commands.Cog, name='Activity'):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._reconciled = False
        self._active_voice: dict[str, tuple[str, str, str, int]] = {}

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if self._reconciled:
            return
        self._reconciled = True
        now = now_ms()
        for guild in self.bot.guilds:
            for vc in guild.voice_channels:
                for member in vc.members:
                    if member.bot:
                        continue
                    discord_id = str(member.id)
                    if discord_id not in self._active_voice:
                        self._active_voice[discord_id] = (str(guild.id), str(vc.id), vc.name, now)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return
        if cfg.TRACKED_CHANNEL_IDS and message.channel.id not in cfg.TRACKED_CHANNEL_IDS:
            return
        channel_name = message.channel.name if hasattr(message.channel, 'name') else ''
        try:
            await client.record_activity(guild_id=str(message.guild.id), discord_id=str(message.author.id), activity_type='message', channel_id=str(message.channel.id), channel_name=channel_name, content=message.content or None, value=1)
        except DashboardError as exc:
            print(f'[activity] record_activity failed: {exc}')

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.bot:
            return
        discord_id = str(member.id)
        guild_id = str(member.guild.id)
        now = now_ms()
        joined_channel = after.channel and (not before.channel)
        left_channel = before.channel and (not after.channel)
        switched_channel = before.channel and after.channel and (before.channel.id != after.channel.id)
        if (left_channel or switched_channel) and discord_id in self._active_voice:
            prev_guild_id, prev_channel_id, prev_channel_name, joined_at = self._active_voice.pop(discord_id)
            duration_s = max(0, now - joined_at) // 1000
            try:
                await client.record_voice_session(guild_id=prev_guild_id, discord_id=discord_id, channel_id=prev_channel_id, channel_name=prev_channel_name, joined_at=joined_at, left_at=now, duration=duration_s)
                await client.record_activity(guild_id=prev_guild_id, discord_id=discord_id, activity_type='voice_leave', channel_id=prev_channel_id, channel_name=prev_channel_name, value=duration_s, recorded_at=now)
            except DashboardError as exc:
                print(f'[activity] voice_leave failed: {exc}')
        if (joined_channel or switched_channel) and after.channel:
            channel_id = str(after.channel.id)
            channel_name = after.channel.name
            self._active_voice[discord_id] = (guild_id, channel_id, channel_name, now)
            try:
                await client.record_activity(guild_id=guild_id, discord_id=discord_id, activity_type='voice_join', channel_id=channel_id, channel_name=channel_name, value=1, recorded_at=now)
            except DashboardError as exc:
                print(f'[activity] voice_join failed: {exc}')

    async def on_shutdown(self) -> None:
        now = now_ms()
        for discord_id, (guild_id, channel_id, channel_name, joined_at) in self._active_voice.items():
            duration_s = max(0, now - joined_at) // 1000
            try:
                await client.record_voice_session(guild_id=guild_id, discord_id=discord_id, channel_id=channel_id, channel_name=channel_name, joined_at=joined_at, left_at=now, duration=duration_s)
            except DashboardError as exc:
                print(f'[activity] drain failed for {discord_id}: {exc}')
        self._active_voice.clear()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityCog(bot))
