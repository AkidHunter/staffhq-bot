# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import discord
from discord.ext import commands, tasks
import config as cfg
from dashboard_client import client, DashboardError
PUNISHMENT_COLORS: dict[str, discord.Color] = {'ban': discord.Color.red(), 'tempban': discord.Color.orange(), 'mute': discord.Color.gold(), 'tempmute': discord.Color.yellow(), 'kick': discord.Color.greyple(), 'warn': discord.Color.blue(), 'note': discord.Color.light_grey()}
PUNISHMENT_EMOJI: dict[str, str] = {'ban': '🔨', 'tempban': '⏳🔨', 'mute': '🔇', 'tempmute': '⏳🔇', 'kick': '👢', 'warn': '⚠️', 'note': '📝'}

class AlertsCog(commands.Cog, name='Alerts'):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.dashboard_client = client

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.poll_punishments.is_running():
            self.poll_punishments.start()

    async def cog_unload(self) -> None:
        self.poll_punishments.cancel()

    @tasks.loop(seconds=cfg.ALERT_POLL_INTERVAL)
    async def poll_punishments(self) -> None:
        guild_id = self.dashboard_client.guild_id
        if not guild_id:
            print('[alerts] guild_id not yet available: skipping poll', flush=True)
            return
        try:
            await self._check_guild(guild_id)
        except Exception as exc:
            print(f'[alerts] error polling guild {guild_id}: {exc}')

    @poll_punishments.before_loop
    async def before_poll(self) -> None:
        await self.bot.wait_until_ready()

    async def _check_guild(self, guild_id: str) -> None:
        await self._check_punishment_alerts(guild_id)
        await self._check_tps_alerts(guild_id)
        await self._check_appeal_alerts(guild_id)
        await self._check_appeal_notifications(guild_id)

    async def _resolve_alert_channel(self, channel_id_raw) -> discord.TextChannel | None:
        if not channel_id_raw:
            print('[alerts] alert_channel_id not configured: skipping post', flush=True)
            return None
        try:
            channel_id = int(channel_id_raw)
        except (TypeError, ValueError):
            print(f'[alerts] invalid alert_channel_id {channel_id_raw!r}: skipping', flush=True)
            return None
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            print(f'[alerts] channel {channel_id} not found or not a text channel')
            return None
        return channel

    async def _check_punishment_alerts(self, guild_id: str) -> None:
        try:
            data = await self.dashboard_client.fetch_punishments(guild_id=guild_id)
        except DashboardError as exc:
            print(f'[alerts] fetch_punishments failed for {guild_id}: {exc}')
            return
        rows = data.get('punishments') or []
        if not rows:
            return
        channel_id_raw = data.get('alert_channel_id') or self.dashboard_client.alert_channel_id
        channel = await self._resolve_alert_channel(channel_id_raw)
        if channel is None:
            return
        for row in rows:
            embed = self._build_embed(row)
            try:
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                print(f'[alerts] failed to send embed to {channel.id}: {exc}')

    async def _check_tps_alerts(self, guild_id: str) -> None:
        try:
            data = await self.dashboard_client.fetch_tps_alerts(guild_id=guild_id)
        except DashboardError as exc:
            print(f'[alerts] fetch_tps_alerts failed for {guild_id}: {exc}')
            return
        rows = data.get('alerts') or []
        if not rows:
            return
        channel_id_raw = data.get('alert_channel_id') or self.dashboard_client.alert_channel_id
        channel = await self._resolve_alert_channel(channel_id_raw)
        if channel is None:
            return
        for row in rows:
            embed = self._build_tps_embed(row)
            try:
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                print(f'[alerts] failed to send TPS embed to {channel.id}: {exc}')

    async def _check_appeal_alerts(self, guild_id: str) -> None:
        try:
            data = await self.dashboard_client.fetch_appeals(guild_id=guild_id)
        except DashboardError as exc:
            print(f'[alerts] fetch_appeals failed for {guild_id}: {exc}')
            return
        rows = data.get('appeals') or []
        if not rows:
            return
        channel_id_raw = data.get('alert_channel_id') or self.dashboard_client.alert_channel_id
        channel = await self._resolve_alert_channel(channel_id_raw)
        if channel is None:
            return
        for row in rows:
            embed = self._build_appeal_embed(row)
            try:
                await channel.send(embed=embed)
            except discord.DiscordException as exc:
                print(f'[alerts] failed to send appeal embed to {channel.id}: {exc}')

    async def _check_appeal_notifications(self, guild_id: str) -> None:
        try:
            data = await self.dashboard_client.fetch_appeal_notifications(guild_id)
        except DashboardError as exc:
            print(f'[alerts] fetch_appeal_notifications failed for {guild_id}: {exc}')
            return
        notifications = data.get('notifications') or []
        if not notifications:
            return
        ids_to_ack: list[int] = []
        for n in notifications:
            channel_id_str = n.get('discord_channel_id')
            if not channel_id_str:
                ids_to_ack.append(n['id'])
                continue
            try:
                channel = await self.bot.fetch_channel(int(channel_id_str))
            except (discord.NotFound, discord.Forbidden):
                ids_to_ack.append(n['id'])
                continue
            except discord.HTTPException:
                continue
            except Exception:
                continue
            if not isinstance(channel, discord.TextChannel):
                ids_to_ack.append(n['id'])
                continue
            embed = self._build_decision_embed(n)
            try:
                await channel.send(embed=embed)
                ids_to_ack.append(n['id'])
            except (discord.NotFound, discord.Forbidden) as exc:
                print(f'[alerts] channel {channel_id_str} gone or no access, acking: {exc}')
                ids_to_ack.append(n['id'])
            except discord.DiscordException as exc:
                print(f'[alerts] transient send failure for {channel_id_str}, will retry: {exc}')
        if ids_to_ack:
            try:
                await self.dashboard_client.ack_appeal_notifications(ids_to_ack)
            except DashboardError as exc:
                print(f'[alerts] ack_appeal_notifications failed: {exc}')

    def _build_decision_embed(self, n: dict) -> discord.Embed:
        status = n.get('status', '')
        rejection_reason = n.get('rejection_reason') or ''
        reviewer_notes = n.get('reviewer_notes') or ''
        username = n.get('player_username') or 'Unknown'
        if status == 'rejected':
            reason_map = {'NOT_LINKED': 'The ticket opener has no linked Minecraft account.', 'NO_ACTIVE_BAN': 'The ticket opener has no active bans.', 'INVALID_PUNISHMENT': 'The selected punishment is not eligible for appeal.'}
            description = reason_map.get(rejection_reason, rejection_reason or 'Appeal could not be processed.')
            embed = discord.Embed(title='Appeal could not be created', description=description, color=discord.Color.orange())
        elif status == 'approved':
            description = 'Your ban has been lifted.'
            if reviewer_notes:
                description += f'\n\nStaff note: {reviewer_notes}'
            embed = discord.Embed(title='Appeal approved', description=description, color=discord.Color.green())
            embed.add_field(name='Player', value=username, inline=True)
        else:
            description = 'The staff reviewed your appeal and declined.'
            if reviewer_notes:
                description += f'\n\nStaff note: {reviewer_notes}'
            embed = discord.Embed(title='Appeal denied', description=description, color=discord.Color.red())
            embed.add_field(name='Player', value=username, inline=True)
        return embed

    def _build_appeal_embed(self, row: dict) -> discord.Embed:
        player = row.get('target_username') or 'Unknown'
        player_uuid = row.get('target_uuid') or ''
        punishment_type = row.get('punishment_type') or 'ban'
        appeal_reason = row.get('reason') or ''
        submitted_ms = int(row.get('submitted_at') or 0)
        submitted_ts = submitted_ms // 1000
        if len(appeal_reason) > 500:
            appeal_reason = appeal_reason[:500] + '...'
        embed = discord.Embed(title=f'New appeal: {player}', color=discord.Color.blue())
        embed.add_field(name='Player', value=player, inline=True)
        embed.add_field(name='Punishment type', value=punishment_type, inline=True)
        embed.add_field(name='Appeal reason', value=appeal_reason or 'None', inline=False)
        embed.add_field(name='Submitted', value=f'<t:{submitted_ts}:R>', inline=True)
        embed.set_footer(text='Review at dash.staffhq.net/punishments/appeals')
        if player_uuid:
            embed.set_thumbnail(url=f'https://crafatar.com/avatars/{player_uuid}?size=64&overlay')
        return embed

    def _build_embed(self, row: dict) -> discord.Embed:
        ptype: str = row.get('type', 'punish')
        color = PUNISHMENT_COLORS.get(ptype, discord.Color.default())
        emoji = PUNISHMENT_EMOJI.get(ptype, '📋')
        target = row.get('target_username') or 'Unknown'
        target_uuid = row.get('target_uuid') or ''
        staff = row.get('staff_username') or 'Console'
        server = row.get('server_name') or 'Unknown server'
        reason = row.get('reason') or 'No reason provided'
        issued_ms = int(row.get('issued_at') or 0)
        issued_ts = issued_ms // 1000
        expires_ms = row.get('expires_at')
        plugin = row.get('source_plugin') or 'unknown'
        embed = discord.Embed(title=f'{emoji} {ptype.upper()}: {target}', color=color)
        embed.add_field(name='Target', value=target, inline=True)
        embed.add_field(name='Staff', value=staff, inline=True)
        embed.add_field(name='Server', value=server, inline=True)
        embed.add_field(name='Reason', value=reason, inline=False)
        embed.add_field(name='Issued', value=f'<t:{issued_ts}:R>', inline=True)
        if expires_ms:
            expires_ts = int(expires_ms) // 1000
            embed.add_field(name='Expires', value=f'<t:{expires_ts}:R>', inline=True)
        embed.set_footer(text=f'via {plugin}')
        if target_uuid:
            embed.set_thumbnail(url=f'https://crafatar.com/avatars/{target_uuid}?size=64&overlay')
        return embed

    def _build_tps_embed(self, row: dict) -> discord.Embed:
        alert_type: str = row.get('type', 'tps_drop')
        server_name: str = row.get('server_name') or 'Unknown server'
        message: str = row.get('message') or 'TPS alert'
        timestamp_ms: int = int(row.get('timestamp') or 0)
        timestamp_s = timestamp_ms // 1000
        if alert_type == 'tps_recover':
            color = discord.Color.green()
            emoji = '✅'
            title = f'{emoji} TPS Recovered: {server_name}'
        else:
            color = discord.Color.red()
            emoji = '⚠️'
            title = f'{emoji} TPS Drop: {server_name}'
        embed = discord.Embed(title=title, description=message, color=color)
        embed.add_field(name='Server', value=server_name, inline=True)
        if timestamp_s:
            embed.add_field(name='Time', value=f'<t:{timestamp_s}:R>', inline=True)
        footer = self.dashboard_client.branded_footer('StaffHQ TPS Monitor')
        if footer is not None:
            embed.set_footer(text=footer)
        return embed

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AlertsCog(bot))
