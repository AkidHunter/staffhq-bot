# StaffHQ - Copyright (c) 2026 AcidHunter. All rights reserved.
# Proprietary software. See LICENSE for terms.
import os
from dotenv import load_dotenv
load_dotenv()

def required(key):
    val = os.getenv(key, '').strip()
    if not val:
        raise ValueError(f'{key} is not set')
    return val

def optional(key, default=''):
    return os.getenv(key, default).strip()
STAFFHQ_API_KEY = required('STAFFHQ_API_KEY')
DASHBOARD_API_URL = optional('DASHBOARD_API_URL', 'https://dash.staffhq.net')
ALERT_POLL_INTERVAL = int(optional('ALERT_POLL_INTERVAL', '30'))
CONFIG_REFRESH_INTERVAL = int(optional('CONFIG_REFRESH_INTERVAL', '300'))
HEARTBEAT_INTERVAL = int(optional('HEARTBEAT_INTERVAL', '30'))
_channels = optional('DISCORD_TRACKED_CHANNEL_IDS')
TRACKED_CHANNEL_IDS = {int(c.strip()) for c in _channels.split(',') if c.strip()} if _channels else set()
