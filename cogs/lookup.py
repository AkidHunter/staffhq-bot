# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import datetime
import discord
from discord import app_commands
from discord.ext import commands
from dashboard_client import client, DashboardError
PUNISHMENT_EMOJI: dict[str, str] = {'ban': '🔨 BAN', 'tempban': '⏳ TEMPBAN', 'mute': '🔇 MUTE', 'tempmute': '⏳ MUTE', 'kick': '👢 KICK', 'warn': '⚠️ WARN', 'note': '📝 NOTE'}
PUNISHMENT_COLOR = {'ban': discord.Color.red(), 'tempban': discord.Color.orange(), 'mute': discord.Color.gold(), 'tempmute': discord.Color.yellow(), 'kick': discord.Color.greyple(), 'warn': discord.Color.blue(), 'note': discord.Color.light_grey()}

def _ms_to_relative(ms: int | None) -> str:
    if not ms:
        return 'unknown'
    return f'<t:{int(ms) // 1000}:R>'

def _ms_to_short(ms: int | None) -> str:
    if not ms:
        return 'unknown'
    return f'<t:{int(ms) // 1000}:f>'

def _playtime_str(seconds: int | None) -> str:
    if not seconds:
        return '0h'
    hours, remainder = divmod(int(seconds), 3600)
    minutes = remainder // 60
    if hours >= 1:
        return f'{hours}h {minutes}m'
    return f'{minutes}m'

def _guild_id(interaction: discord.Interaction) -> str | None:
    if interaction.guild is None:
        return None
    return str(interaction.guild.id)

async def _check_guild(interaction: discord.Interaction) -> str | None:
    gid = _guild_id(interaction)
    if gid is None:
        await interaction.followup.send('This command must be used in a server.', ephemeral=True)
        return None
    return gid

class LookupCog(commands.Cog, name='Lookup'):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='investigate', description='Show player info, recent punishments, and recent AC flags')
    @app_commands.describe(player='Minecraft username to look up (exact, case-insensitive)')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def cmd_investigate(self, interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = await _check_guild(interaction)
        if guild_id is None:
            return
        try:
            data = await client.lookup_player(guild_id=guild_id, username=player)
        except DashboardError as exc:
            if exc.code == 'FORBIDDEN':
                await interaction.followup.send('This server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'API error: {exc.message}', ephemeral=True)
            return
        if data is None:
            await interaction.followup.send(f'Player **{player}** not found.', ephemeral=True)
            return
        p = data.get('player') or {}
        uuid: str = p.get('uuid') or ''
        username: str = p.get('username') or player
        is_online: bool = bool(p.get('is_online'))
        is_staff: bool = bool(p.get('is_staff'))
        playtime_s = p.get('total_playtime')
        last_seen_ms = p.get('last_seen')
        status_icon = '🟢' if is_online else '⚫'
        staff_badge = ' **[STAFF]**' if is_staff else ''
        embed = discord.Embed(title=f'{status_icon} {username}{staff_badge}', color=discord.Color.green() if is_online else discord.Color.greyple())
        embed.add_field(name='UUID', value=uuid or 'unknown', inline=False)
        embed.add_field(name='Status', value='Online' if is_online else 'Offline', inline=True)
        embed.add_field(name='Playtime', value=_playtime_str(playtime_s), inline=True)
        embed.add_field(name='Last seen', value=_ms_to_relative(last_seen_ms), inline=True)
        punishments: list[dict] = data.get('recent_punishments') or []
        if punishments:
            lines = []
            for pu in punishments:
                ptype = pu.get('type', 'punish')
                badge = PUNISHMENT_EMOJI.get(ptype, ptype.upper())
                reason = pu.get('reason') or 'No reason'
                when = _ms_to_relative(pu.get('issued_at'))
                lines.append(f'**{badge}** - {reason} {when}')
            embed.add_field(name='Recent punishments', value='\n'.join(lines), inline=False)
        else:
            embed.add_field(name='Recent punishments', value='None on record', inline=False)
        flags: list[dict] = data.get('recent_anticheat_flags') or []
        if flags:
            lines = []
            for fl in flags:
                check = fl.get('check_name') or '?'
                vl = fl.get('violation_level')
                vl_str = f'VL {vl:.1f}' if vl is not None else 'VL ?'
                when = _ms_to_relative(fl.get('flagged_at'))
                lines.append(f'**{check}** {vl_str} {when}')
            embed.add_field(name='Recent AC flags', value='\n'.join(lines), inline=False)
        else:
            embed.add_field(name='Recent AC flags', value='None on record', inline=False)
        if uuid:
            embed.set_thumbnail(url=f'https://mc-heads.net/avatar/{uuid}/64')
        footer = client.branded_footer('StaffHQ lookup')
        if footer is not None:
            embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name='chatlog', description='Show recent chat messages and commands for a player')
    @app_commands.describe(player='Minecraft username', count='Number of messages to show (default 10, max 20)')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def cmd_chatlog(self, interaction: discord.Interaction, player: str, count: int=10) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = await _check_guild(interaction)
        if guild_id is None:
            return
        count = max(1, min(20, count))
        try:
            messages = await client.lookup_chat(guild_id=guild_id, username=player, limit=count)
        except DashboardError as exc:
            if exc.code == 'FORBIDDEN':
                await interaction.followup.send('This server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'API error: {exc.message}', ephemeral=True)
            return
        if not messages:
            await interaction.followup.send(f'No chat history found for **{player}**.', ephemeral=True)
            return
        messages = list(reversed(messages))
        lines = []
        for msg in messages:
            sent_ms = msg.get('sent_at')
            entry_type = msg.get('entry_type', 'chat')
            text = msg.get('message') or ''
            if sent_ms:
                dt = datetime.datetime.fromtimestamp(int(sent_ms) / 1000, tz=datetime.timezone.utc)
                time_str = dt.strftime('%H:%M')
            else:
                time_str = '??:??'
            prefix = '/' if entry_type == 'command' else ''
            lines.append(f'[{time_str}] {prefix}{text}')
        block = '\n'.join(lines)
        if len(block) > 1900:
            block = block[:1900] + '\n... (truncated)'
        embed = discord.Embed(title=f'Chat log: {player}', description=f'```\n{block}\n```', color=discord.Color.blurple())
        embed.set_footer(text=f'Last {len(messages)} entries (newest last)')
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name='punishments', description='Show punishment history for a player')
    @app_commands.describe(player='Minecraft username')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def cmd_punishments(self, interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = await _check_guild(interaction)
        if guild_id is None:
            return
        try:
            rows = await client.lookup_punishments(guild_id=guild_id, username=player, limit=10)
        except DashboardError as exc:
            if exc.code == 'FORBIDDEN':
                await interaction.followup.send('This server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'API error: {exc.message}', ephemeral=True)
            return
        if not rows:
            await interaction.followup.send(f'No punishments found for **{player}**.', ephemeral=True)
            return
        embed = discord.Embed(title=f'Punishments: {player}', color=discord.Color.red())
        for pu in rows:
            ptype = pu.get('type', 'punish')
            badge = PUNISHMENT_EMOJI.get(ptype, ptype.upper())
            is_active = bool(pu.get('is_active'))
            reason = pu.get('reason') or 'No reason provided'
            staff = pu.get('staff_username') or 'Console'
            issued_ms = pu.get('issued_at')
            status_mark = '' if is_active else ' ~~(inactive)~~'
            field_name = f'{badge}{status_mark}'
            field_value = f'**Reason:** {reason}\n**By:** {staff}\n**Issued:** {_ms_to_short(issued_ms)}'
            embed.add_field(name=field_name, value=field_value, inline=False)
        embed.set_footer(text=f'Showing up to 10 most recent. red=active, gray=expired/pardoned')
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name='flags', description='Show anticheat flag history for a player')
    @app_commands.describe(player='Minecraft username')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.checks.cooldown(1, 10.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def cmd_flags(self, interaction: discord.Interaction, player: str) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = await _check_guild(interaction)
        if guild_id is None:
            return
        try:
            rows = await client.lookup_flags(guild_id=guild_id, username=player, limit=10)
        except DashboardError as exc:
            if exc.code == 'FORBIDDEN':
                await interaction.followup.send('This server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'API error: {exc.message}', ephemeral=True)
            return
        if not rows:
            await interaction.followup.send(f'No anticheat flags found for **{player}**.', ephemeral=True)
            return
        embed = discord.Embed(title=f'AC Flags: {player}', color=discord.Color.orange())
        for fl in rows:
            check = fl.get('check_name') or 'Unknown'
            vl = fl.get('violation_level')
            vl_str = f'{vl:.1f}' if vl is not None else '?'
            plugin = fl.get('source_plugin') or 'unknown'
            flagged_ms = fl.get('flagged_at')
            experimental = fl.get('is_experimental')
            exp_mark = ' *(experimental)*' if experimental else ''
            field_name = f'**{check}**{exp_mark} - VL {vl_str}'
            field_value = f'**Plugin:** {plugin}\n**When:** {_ms_to_short(flagged_ms)}'
            embed.add_field(name=field_name, value=field_value, inline=False)
        embed.set_footer(text='Showing up to 10 most recent flags')
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name='online', description='Show who is currently online on the Minecraft server(s)')
    @app_commands.guild_only()
    async def cmd_online(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        guild_id = await _check_guild(interaction)
        if guild_id is None:
            return
        try:
            data = await client.lookup_online(guild_id=guild_id)
        except DashboardError as exc:
            if exc.code == 'FORBIDDEN':
                await interaction.followup.send('This server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'API error: {exc.message}', ephemeral=True)
            return
        servers: list[dict] = data.get('servers') or []
        online_players: list[dict] = data.get('online_players') or []
        online_staff: list[dict] = data.get('online_staff') or []
        total: int = data.get('total_player_count') or len(online_players)
        embed = discord.Embed(title="Who's Online", color=discord.Color.green() if total > 0 else discord.Color.greyple())
        if servers:
            for srv in servers:
                name = srv.get('name') or '?'
                status = srv.get('status', 'offline')
                count = srv.get('player_count') or 0
                tps = srv.get('tps')
                mem_used = srv.get('memory_used_mb')
                mem_max = srv.get('memory_max_mb')
                status_icon = '🟢' if status == 'online' else '🔴'
                parts = [f"{status_icon} **{count}** player{('s' if count != 1 else '')}"]
                if tps is not None:
                    parts.append(f'TPS: {tps:.1f}')
                if mem_used is not None and mem_max is not None:
                    parts.append(f'Mem: {mem_used}/{mem_max} MB')
                elif mem_used is not None:
                    parts.append(f'Mem: {mem_used} MB')
                embed.add_field(name=name, value=' | '.join(parts), inline=False)
        embed.add_field(name=f'Total online ({total})', value=str(total) + ' player' + ('s' if total != 1 else ''), inline=True)
        if online_staff:
            staff_names = [s.get('username') or '?' for s in online_staff]
            embed.add_field(name=f'Staff online ({len(staff_names)})', value=', '.join(staff_names) or 'None', inline=False)
        else:
            embed.add_field(name='Staff online', value='None', inline=False)
        footer = client.branded_footer('StaffHQ live data')
        if footer is not None:
            embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            try:
                await interaction.response.send_message(f"You're on cooldown. Try again in {error.retry_after:.1f}s.", ephemeral=True)
            except discord.InteractionResponded:
                pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LookupCog(bot))
