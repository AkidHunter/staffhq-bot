# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import secrets
import discord
from discord import app_commands
from discord.ext import commands
from dashboard_client import client, now_ms, DashboardError
CODE_TTL_MS = 5 * 60 * 1000

def _generate_code(length: int=6) -> str:
    return ''.join((secrets.choice('0123456789') for _ in range(length)))

class LinkingCog(commands.Cog, name='Linking'):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name='link', description='Link your Minecraft account to Discord')
    @app_commands.describe(minecraft_username='Your exact Minecraft username (case-sensitive)')
    @app_commands.checks.cooldown(1, 30.0, key=lambda i: i.user.id)
    @app_commands.guild_only()
    async def cmd_link(self, interaction: discord.Interaction, minecraft_username: str) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await self._do_link(interaction, minecraft_username)
        except Exception:
            import traceback
            traceback.print_exc()
            await interaction.followup.send('An unexpected error occurred. Please try again later or contact a server admin.', ephemeral=True)

    async def _do_link(self, interaction: discord.Interaction, minecraft_username: str) -> None:
        if interaction.guild is None:
            await interaction.followup.send('This command must be used in a server.', ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        discord_id = str(interaction.user.id)
        discord_username = str(interaction.user)
        now = now_ms()
        expires = now + CODE_TTL_MS
        code = _generate_code()
        try:
            await client.init_discord_link(guild_id=guild_id, discord_id=discord_id, discord_username=discord_username, link_token=code, expires_at=expires)
        except DashboardError as exc:
            if exc.code == 'ALREADY_LINKED':
                await interaction.followup.send('You are already linked to a Minecraft account.\nAsk an admin to `/unlink` you first if you want to change accounts.', ephemeral=True)
                return
            if exc.code == 'GUILD_NOT_REGISTERED':
                await interaction.followup.send('This Discord server is not linked to a StaffHQ tenant. Ask the server owner to register it in the dashboard.', ephemeral=True)
                return
            await interaction.followup.send(f'Failed to start link: {exc.message}', ephemeral=True)
            return
        embed = discord.Embed(title='Link Your Minecraft Account', description=f'Join the Minecraft server as **{minecraft_username}** and run:\n\n```\n/staffhq link {code}\n```\nThis code expires in **5 minutes**.', color=discord.Color.blurple())
        embed.set_footer(text='If the code expires, run /link again.')
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name='unlink', description='[Admin] Unlink a Discord account from Minecraft')
    @app_commands.describe(user='The Discord user to unlink')
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    async def cmd_unlink(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send('This command must be used in a server.', ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        try:
            result = await client.unlink(guild_id=guild_id, discord_id=str(user.id))
        except DashboardError as exc:
            if exc.code == 'GUILD_NOT_REGISTERED':
                await interaction.followup.send('This Discord server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'Unlink failed: {exc.message}', ephemeral=True)
            return
        if not result.get('unlinked'):
            await interaction.followup.send(f'{user.mention} has no active link.', ephemeral=True)
            return
        username = result.get('username') or 'an unknown account'
        await interaction.followup.send(f'Unlinked {user.mention} from **{username}**.', ephemeral=True)

    @app_commands.command(name='whois', description='Look up the Minecraft account linked to a Discord user')
    @app_commands.describe(user='The Discord user to look up')
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.guild_only()
    async def cmd_whois(self, interaction: discord.Interaction, user: discord.Member) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.guild is None:
            await interaction.followup.send('This command must be used in a server.', ephemeral=True)
            return
        guild_id = str(interaction.guild.id)
        try:
            row = await client.whois(guild_id=guild_id, discord_id=str(user.id))
        except DashboardError as exc:
            if exc.code == 'GUILD_NOT_REGISTERED':
                await interaction.followup.send('This Discord server is not linked to a StaffHQ tenant.', ephemeral=True)
                return
            await interaction.followup.send(f'Lookup failed: {exc.message}', ephemeral=True)
            return
        if not row:
            await interaction.followup.send(f'{user.mention} is not linked to any Minecraft account.', ephemeral=True)
            return
        linked_ts = int(row['linked_at']) // 1000
        embed = discord.Embed(title=f'Linked account for {user.display_name}', color=discord.Color.green())
        embed.add_field(name='Minecraft', value=row['username'], inline=True)
        embed.add_field(name='UUID', value=row['uuid'], inline=True)
        embed.add_field(name='Linked', value=f'<t:{linked_ts}:R>', inline=True)
        embed.set_thumbnail(url=f"https://mc-heads.net/avatar/{row['uuid']}/64")
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            try:
                await interaction.response.send_message(f"You're on cooldown. Try again in {error.retry_after:.1f}s.", ephemeral=True)
            except discord.InteractionResponded:
                pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkingCog(bot))
