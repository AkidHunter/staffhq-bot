# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
import asyncio
import json
import logging
import os
import sys
import time
import discord
from discord.ext import commands

class JsonFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        payload = {'level': record.levelname, 'logger': record.name, 'message': record.getMessage()}
        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)
        return json.dumps(payload)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger('staffhq.bot')
import config as cfg
from dashboard_client import client, DashboardError
COGS = ['cogs.activity', 'cogs.linking', 'cogs.alerts', 'cogs.roles', 'cogs.lookup', 'cogs.tos', 'cogs.appeals']
HEALTHCHECK_PATH = '/tmp/staffhq_bot_alive'
CONFIG_RETRIES = 3
CONFIG_BACKOFF = 10
CONFIG_NOT_SET_WAIT = 60

def write_healthcheck():
    try:
        with open(HEALTHCHECK_PATH, 'w') as f:
            f.write(str(time.time()))
    except OSError:
        pass

async def fetch_config():
    while True:
        last_err = None
        for attempt in range(1, CONFIG_RETRIES + 1):
            try:
                result = await client.fetch_bot_config()
            except Exception as e:
                last_err = e
                log.error('Config fetch failed (%d/%d): %s', attempt, CONFIG_RETRIES, e)
                if attempt < CONFIG_RETRIES:
                    await asyncio.sleep(CONFIG_BACKOFF)
                continue
            if result is None:
                log.info('Discord not configured yet, retrying in 60s')
                await asyncio.sleep(CONFIG_NOT_SET_WAIT)
                break
            return result
        else:
            log.error('Config fetch failed after %d attempts: %s', CONFIG_RETRIES, last_err)
            await client.close()
            sys.exit(1)

class StaffHQBot(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        self._ready_fired = False

    async def setup_hook(self):
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info('Loaded %s', cog)
            except Exception as e:
                log.error('Failed to load %s: %s', cog, e)
        self.loop.create_task(self.heartbeat_loop())
        self.loop.create_task(self.config_loop())
        self.loop.create_task(self.register_guilds())

    async def on_ready(self):
        if self._ready_fired:
            return
        self._ready_fired = True
        log.info('%s online in %d guild(s)', self.user, len(self.guilds))
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='staff activity'))
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                log.info('Commands synced to guild %s', guild.id)
            except Exception as e:
                log.warning('guild sync failed for %s: %s', guild.id, e)

    async def heartbeat_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            try:
                uid = str(self.user.id) if self.user else None
                await client.post_heartbeat('connected', bot_user_id=uid, guild_count=len(self.guilds))
                write_healthcheck()
            except Exception as e:
                log.error('Heartbeat failed: %s', e)
            await asyncio.sleep(cfg.HEARTBEAT_INTERVAL)

    async def config_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(cfg.CONFIG_REFRESH_INTERVAL)
            try:
                await client.fetch_bot_config()
            except Exception as e:
                log.error('Config refresh failed: %s', e)

    async def register_guilds(self):
        bot_guild_ids = {str(g.id) for g in self.guilds}
        for guild in self.guilds:
            try:
                await client.register_guild(guild_id=str(guild.id), guild_name=guild.name)
                log.info('Registered guild: %s', guild.name)
            except Exception as e:
                log.error('Guild registration failed for %s: %s', guild.name, e)
        try:
            data = await client.list_registered_guilds()
            for g in data.get('guilds', []):
                if g['guild_id'] not in bot_guild_ids:
                    await client.unregister_guild(guild_id=g['guild_id'])
                    log.info('Removed stale guild: %s', g['guild_id'])
        except Exception as e:
            log.error('Stale guild cleanup failed: %s', e)

    async def on_guild_join(self, guild):
        log.info('Joined %s (%s)', guild.name, guild.id)
        try:
            await client.register_guild(guild_id=str(guild.id), guild_name=guild.name)
            log.info('Registered guild: %s', guild.name)
        except Exception as e:
            log.error('Guild registration failed for %s: %s', guild.name, e)
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info('Commands synced to guild %s', guild.id)
        except Exception as e:
            log.warning('guild sync failed for %s: %s', guild.id, e)

    async def on_guild_remove(self, guild):
        log.info('Left %s (%s)', guild.name, guild.id)
        try:
            await client.unregister_guild(guild_id=str(guild.id))
            log.info('Unregistered guild: %s', guild.name)
        except Exception as e:
            log.error('Guild unregistration failed for %s: %s', guild.name, e)

    async def close(self):
        cog = self.get_cog('Activity')
        if cog:
            await cog.on_shutdown()
        try:
            await client.post_heartbeat('disconnected')
        except Exception:
            pass
        await client.close()
        await super().close()

async def main():
    bot_config = await fetch_config()
    token = bot_config.get('bot_token', '')
    if not token:
        log.error('No bot token returned from dashboard')
        await client.close()
        sys.exit(1)
    bot = StaffHQBot()
    try:
        async with bot:
            await bot.start(token)
    except KeyboardInterrupt:
        pass
    except discord.LoginFailure as e:
        log.error('Bad token: %s', e)
        sys.exit(1)
    except Exception as e:
        log.error('Startup error: %s', e)
        sys.exit(1)
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info('Stopped.')
