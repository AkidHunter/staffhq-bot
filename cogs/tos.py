# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
ACCENT = 6514417
TOS_SECTIONS = [{'title': '1. Acceptance of Terms', 'text': 'By creating an account or using any part of StaffHQ, you agree to these Terms of Service. These terms apply to all users, including server owners, administrators, and staff members.'}, {'title': '2. Description of Service', 'text': 'StaffHQ is a multi-tenant SaaS staff management dashboard for Minecraft server networks. We reserve the right to modify, suspend, or discontinue any part of the service at any time.'}, {'title': '3. Account Registration', 'text': 'You must provide accurate information and keep it up to date. You are responsible for maintaining the security of your account. You must be at least 16 years of age to use StaffHQ.'}, {'title': '4. Subscriptions and Payments', 'text': 'StaffHQ is sold as a prepaid subscription. You pay upfront for a billing cycle. **No auto-renewal.** You initiate each renewal yourself. Payments are processed by MCSets.'}, {'title': '5. Refund Policy', 'text': '**All purchases are final.** StaffHQ does not offer refunds for subscription payments. If you believe a charge was made in error, contact support@staffhq.net. Nothing in this section affects your statutory rights under applicable consumer protection laws.'}, {'title': '6. Free Trial', 'text': 'StaffHQ offers a 7-day free trial of the Pro plan. No payment information required. If you do not subscribe within 3 days of trial expiry, all data may be permanently deleted.'}, {'title': '7. Acceptable Use', 'text': 'Do not use StaffHQ to violate any law, collect data in violation of privacy law, attempt unauthorized access, introduce malicious code, abuse other users, or resell access without written permission.'}, {'title': '8. Data and Content Ownership', 'text': 'You retain ownership of all data you upload or generate. We do not sell your data or use it for advertising. See our Privacy Policy for full details.'}, {'title': '9. Service Availability', 'text': 'StaffHQ is provided on a best-effort, "as available" basis. We aim for high availability but do not guarantee uninterrupted access.'}, {'title': '10. Data Breach Response', 'text': 'If a breach occurs, we will notify affected account holders via email within 72 hours. We will provide an incident report identifying what happened, what data categories were affected (e.g. player UUIDs, usernames, IPs, chat messages), and what remediation steps were taken. Liability is governed by section 12.'}, {'title': '11. Termination', 'text': 'You may cancel at any time. For paid subscribers, data is retained for 30 days after suspension. If you reactivate within that window, your data is fully restored. After 30 days, your tenant database is permanently deleted.'}, {'title': '12. Limitation of Liability', 'text': 'StaffHQ shall not be liable for any indirect, incidental, special, or consequential damages. Total aggregate liability shall not exceed the amount you paid in the 12 months preceding the claim.'}, {'title': '13. Changes to These Terms', 'text': 'We may update these terms from time to time. Continued use after changes constitutes acceptance. For significant changes, we will notify you via email or an in-dashboard notice.'}]

class Tos(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='tos', description='Post the StaffHQ Terms of Service summary')
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def tos(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message('This command must be used in a server.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        embeds: list[discord.Embed] = []
        header = discord.Embed(title='StaffHQ Terms of Service', description='Last updated: April 2026\n\nThis is a summary for quick reference. The full Terms of Service are at [staffhq.net/terms](https://staffhq.net/terms).', color=ACCENT)
        header.set_thumbnail(url='https://staffhq.net/logo-mark.svg')
        embeds.append(header)
        current_text = ''
        for section in TOS_SECTIONS:
            entry = f"**{section['title']}**\n{section['text']}\n\n"
            if len(current_text) + len(entry) > 3800:
                embeds.append(discord.Embed(description=current_text.strip(), color=ACCENT))
                current_text = entry
            else:
                current_text += entry
        if current_text.strip():
            embeds.append(discord.Embed(description=current_text.strip(), color=ACCENT))
        footer = discord.Embed(description='**Contact:** support@staffhq.net\n**Full terms:** [staffhq.net/terms](https://staffhq.net/terms)\n**Privacy policy:** [staffhq.net/privacy](https://staffhq.net/privacy)', color=ACCENT)
        embeds.append(footer)
        await interaction.channel.send(embeds=embeds)
        await interaction.followup.send('TOS posted.', ephemeral=True)

    @tos.error
    async def tos_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message('You need administrator permissions to use this command.', ephemeral=True)
        elif isinstance(error, app_commands.NoPrivateMessage):
            await interaction.response.send_message('This command can only be used in a server.', ephemeral=True)
        else:
            await interaction.response.send_message('Something went wrong.', ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Tos(bot))
