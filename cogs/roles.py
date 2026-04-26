# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import asyncio
from typing import Any
import discord
from discord.ext import commands, tasks
from dashboard_client import client, now_ms, DashboardError
FLUSH_INTERVAL_S = 5
MAX_BATCH = 100

class RolesCog(commands.Cog, name='Roles'):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._buffer: list[dict] = []
        self._flush_task.start()

    def cog_unload(self) -> None:
        self._flush_task.cancel()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.bot:
            return
        now = now_ms()
        guild_id = str(after.guild.id)
        discord_id = str(after.id)
        before_roles = {r.id: r for r in before.roles}
        after_roles = {r.id: r for r in after.roles}
        added = [r for rid, r in after_roles.items() if rid not in before_roles]
        removed = [r for rid, r in before_roles.items() if rid not in after_roles]
        for role in added:
            self._buffer.append({'discord_id': discord_id, 'guild_id': guild_id, 'role_id': str(role.id), 'role_name': role.name, 'action': 'added', 'changed_at': now})
        for role in removed:
            self._buffer.append({'discord_id': discord_id, 'guild_id': guild_id, 'role_id': str(role.id), 'role_name': role.name, 'action': 'removed', 'changed_at': now})
        if len(self._buffer) >= MAX_BATCH:
            await self._flush()

    @tasks.loop(seconds=FLUSH_INTERVAL_S)
    async def _flush_task(self) -> None:
        await self._flush()

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = (self._buffer[:MAX_BATCH], self._buffer[MAX_BATCH:])
        try:
            await client.record_role_changes(events=batch)
        except DashboardError as exc:
            print(f'[roles] record_role_changes failed: {exc}')

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RolesCog(bot))
