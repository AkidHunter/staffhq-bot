# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
import asyncio
import time
from typing import Any
import aiohttp
import config as cfg

def now_ms():
    return int(time.time() * 1000)

class DashboardError(Exception):

    def __init__(self, status, code, message):
        super().__init__(f"{status} {code or ''}: {message}".strip())
        self.status = status
        self.code = code
        self.message = message

class DashboardClient:

    def __init__(self, base_url, api_key):
        self._base_url = base_url.rstrip('/')
        self._headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json', 'User-Agent': 'staffhq-bot/1.0'}
        self._session = None
        self._lock = asyncio.Lock()
        self.guild_id = None
        self.alert_channel_id = None
        self.discord_client_id = None
        self._tier: str | None = None
        self.appeals_channel_prefix: str | None = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            async with self._lock:
                if self._session is None or self._session.closed:
                    self._session = aiohttp.ClientSession(headers=self._headers, timeout=aiohttp.ClientTimeout(total=15))
        return self._session

    async def close(self):
        if self._session and (not self._session.closed):
            await self._session.close()
        self._session = None

    async def _request(self, method, path, *, json=None, params=None):
        session = await self._get_session()
        url = f'{self._base_url}{path}'
        last_err: Exception | None = None
        for attempt in range(3):
            if attempt > 0:
                await asyncio.sleep(2 ** (attempt - 1))
            try:
                async with session.request(method, url, json=json, params=params) as resp:
                    if resp.status == 204:
                        return {}
                    try:
                        payload = await resp.json()
                    except Exception:
                        text = await resp.text()
                        raise DashboardError(resp.status, None, text[:200])
                    if resp.status >= 500:
                        last_err = DashboardError(resp.status, None, f'Server error {resp.status}')
                        continue
                    if resp.status >= 400:
                        err = payload.get('error', {}) if isinstance(payload, dict) else {}
                        raise DashboardError(resp.status, err.get('code'), err.get('message') or 'Unknown error')
                    return payload if isinstance(payload, dict) else {}
            except DashboardError:
                raise
            except (aiohttp.ClientConnectionError, aiohttp.ServerConnectionError) as e:
                last_err = e
                continue
        if last_err is not None:
            raise last_err
        raise DashboardError(500, None, 'Request failed after retries')

    async def fetch_bot_config(self):
        try:
            data = await self._request('GET', '/api/v1/bot/config')
        except DashboardError as e:
            if e.status == 409 and e.code == 'DISCORD_NOT_CONFIGURED':
                return None
            raise
        self.guild_id = data.get('guild_id') or None
        self.alert_channel_id = data.get('alert_channel_id') or None
        self.discord_client_id = data.get('client_id') or None
        if 'tier' in data:
            self._tier = data.get('tier') or None
        self.appeals_channel_prefix = data.get('appeals_channel_prefix') or None
        return data

    def branded_footer(self, default_text: str) -> str | None:
        if self._tier and self._tier.lower() == 'max':
            return None
        return default_text

    async def post_heartbeat(self, status, message=None, bot_user_id=None, guild_count=None):
        body = {'status': status}
        if message:
            body['message'] = message
        if bot_user_id:
            body['bot_user_id'] = bot_user_id
        if guild_count is not None:
            body['guild_count'] = guild_count
        await self._request('POST', '/api/v1/bot/heartbeat', json=body)

    async def register_guild(self, *, guild_id, guild_name):
        try:
            await self._request('POST', '/api/v1/bot/registered-guilds', json={'guild_id': guild_id, 'guild_name': guild_name})
        except DashboardError as e:
            if e.status == 409:
                pass
            else:
                raise

    async def list_registered_guilds(self):
        return await self._request('GET', '/api/v1/bot/registered-guilds')

    async def unregister_guild(self, *, guild_id):
        try:
            await self._request('DELETE', '/api/v1/bot/registered-guilds', json={'guild_id': guild_id})
        except DashboardError:
            pass

    async def record_activity(self, *, guild_id, discord_id, activity_type, channel_id=None, channel_name=None, content=None, value=1, recorded_at=None):
        await self._request('POST', '/api/v1/bot/activity', json={'guild_id': guild_id, 'discord_id': discord_id, 'activity_type': activity_type, 'channel_id': channel_id, 'channel_name': channel_name, 'content': content, 'value': value, 'recorded_at': recorded_at or now_ms()})

    async def record_voice_session(self, *, guild_id, discord_id, channel_id, channel_name, joined_at, left_at, duration):
        await self._request('POST', '/api/v1/bot/voice', json={'guild_id': guild_id, 'discord_id': discord_id, 'channel_id': channel_id, 'channel_name': channel_name, 'joined_at': joined_at, 'left_at': left_at, 'duration': duration})

    async def init_discord_link(self, *, guild_id, discord_id, discord_username, link_token, expires_at):
        await self._request('POST', '/api/v1/bot/discord-links', json={'guild_id': guild_id, 'discord_id': discord_id, 'discord_username': discord_username, 'link_token': link_token, 'expires_at': expires_at})

    async def whois(self, *, guild_id, discord_id):
        data = await self._request('GET', '/api/v1/bot/discord-links', params={'guild_id': guild_id, 'discord_id': discord_id})
        if not data.get('linked'):
            return None
        return {'username': data.get('username'), 'uuid': data.get('uuid'), 'linked_at': data.get('linked_at')}

    async def unlink(self, *, guild_id, discord_id):
        return await self._request('DELETE', '/api/v1/bot/discord-links', json={'guild_id': guild_id, 'discord_id': discord_id})

    async def fetch_punishments(self, *, guild_id):
        return await self._request('GET', '/api/v1/bot/punishments', params={'guild_id': guild_id})

    async def fetch_appeals(self, *, guild_id):
        return await self._request('GET', '/api/v1/bot/appeals', params={'guild_id': guild_id})

    async def fetch_tps_alerts(self, *, guild_id):
        return await self._request('GET', '/api/v1/bot/alerts', params={'guild_id': guild_id})

    async def record_role_changes(self, *, events):
        if not events:
            return
        await self._request('POST', '/api/v1/bot/role-changes', json={'events': events})

    async def lookup_player(self, *, guild_id, username):
        try:
            return await self._request('GET', '/api/v1/bot/lookup', params={'type': 'player', 'guild_id': guild_id, 'player': username})
        except DashboardError as e:
            if e.status == 404:
                return None
            raise

    async def lookup_chat(self, *, guild_id, username, limit=10):
        try:
            data = await self._request('GET', '/api/v1/bot/lookup', params={'type': 'chat', 'guild_id': guild_id, 'player': username, 'limit': str(limit)})
            return data.get('messages', [])
        except DashboardError as e:
            if e.status == 404:
                return []
            raise

    async def lookup_punishments(self, *, guild_id, username, limit=10):
        try:
            data = await self._request('GET', '/api/v1/bot/lookup', params={'type': 'punishments', 'guild_id': guild_id, 'player': username, 'limit': str(limit)})
            return data.get('punishments', [])
        except DashboardError as e:
            if e.status == 404:
                return []
            raise

    async def lookup_flags(self, *, guild_id, username, limit=10):
        try:
            data = await self._request('GET', '/api/v1/bot/lookup', params={'type': 'flags', 'guild_id': guild_id, 'player': username, 'limit': str(limit)})
            return data.get('flags', [])
        except DashboardError as e:
            if e.status == 404:
                return []
            raise

    async def lookup_online(self, *, guild_id):
        return await self._request('GET', '/api/v1/bot/lookup', params={'type': 'online', 'guild_id': guild_id})

    async def fetch_active_bans(self, guild_id: str, discord_id: str):
        try:
            return await self._request('GET', '/api/v1/bot/discord-links/active-bans', params={'guild_id': guild_id, 'discord_id': discord_id})
        except DashboardError as e:
            if e.status == 404:
                return None
            raise

    async def submit_appeal(self, guild_id: str, discord_user_id: str, channel_id: str, punishment_id: int | None, reason: str):
        return await self._request('POST', '/api/v1/bot/appeals', json={'guild_id': guild_id, 'discord_user_id': discord_user_id, 'discord_channel_id': channel_id, 'punishment_id': punishment_id, 'reason': reason})

    async def fetch_appeal_notifications(self, guild_id: str):
        return await self._request('GET', '/api/v1/bot/appeal-notifications', params={'guild_id': guild_id})

    async def ack_appeal_notifications(self, appeal_ids: list[int]):
        if not appeal_ids:
            return
        return await self._request('POST', '/api/v1/bot/appeal-notifications/ack', json={'appeal_ids': appeal_ids})
client = DashboardClient(cfg.DASHBOARD_API_URL, cfg.STAFFHQ_API_KEY)
