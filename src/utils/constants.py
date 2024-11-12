"""Constants for DraXon OCULUS"""

import os
from pathlib import Path

# Version and description
APP_VERSION = "3.0.0"
BOT_DESCRIPTION = "DraXon Organizational Command & Unified Leadership Implementation System"

# Directory paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = ROOT_DIR / 'logs'
DATA_DIR = ROOT_DIR / 'data'

# RSI Configuration
RSI_CONFIG = {
    'STATUS_URL': 'https://status.robertsspaceindustries.com/api/v2/status',
    'INCIDENTS_URL': 'https://status.robertsspaceindustries.com/api/v2/incidents/unresolved',
    'SERVICES': {
        'RSI Platform': 'rsi-platform',
        'Star Citizen (PU)': 'star-citizen',
        'Arena Commander': 'arena-commander'
    },
    'STATUS_CODES': {
        'operational': 'operational',
        'partial_outage': 'partial_outage',
        'major_outage': 'major_outage',
        'maintenance': 'maintenance',
        'investigating': 'investigating'
    },
    'UPDATE_INTERVAL': 60,  # seconds
    'TIMEOUT': 10,  # seconds
    'RETRY_ATTEMPTS': 3,
    'RETRY_DELAY': 5,  # seconds
    'HEADERS': {
        'User-Agent': 'DraXon OCULUS Bot',
        'Accept': 'application/json'
    }
}

# Database settings
DB_SETTINGS = {
    'MIN_CONNECTIONS': 5,
    'MAX_CONNECTIONS': 20,
    'MAX_QUERIES': 50000,
    'TIMEOUT': 30,  # seconds
    'COMMAND_TIMEOUT': 30,  # seconds
    'POOL_RECYCLE': 300,  # 5 minutes
    'POOL_SIZE': 10,
    'MIN_SIZE': 5,
    'MAX_SIZE': 20,
    'MAX_OVERFLOW': 10,
    'POOL_TIMEOUT': 30,
    'ECHO': False,
    'ECHO_POOL': False,
    'POOL_PRE_PING': True,
    'POOL_USE_LIFO': True,
    'POOL_RESET_ON_RETURN': True
}

# Cache settings
CACHE_SETTINGS = {
    'STATUS_TTL': 300,  # 5 minutes
    'INCIDENT_TTL': 3600,  # 1 hour
    'MEMBER_TTL': 3600,  # 1 hour
    'RETRY_ATTEMPTS': 3,
    'RETRY_DELAY': 1,  # seconds
    'POOL_SIZE': 10,
    'POOL_TIMEOUT': 30,  # seconds
    'REDIS_RETRY_COUNT': 3,
    'REDIS_RETRY_DELAY': 1,  # seconds
    'REDIS_SOCKET_TIMEOUT': 5,  # seconds
    'REDIS_SOCKET_CONNECT_TIMEOUT': 5,  # seconds
    'REDIS_SOCKET_KEEPALIVE': True,
    'REDIS_HEALTH_CHECK_INTERVAL': 30,  # seconds
    'REDIS_MAX_CONNECTIONS': 10,
    'REDIS_MAX_IDLE_TIME': 300,  # 5 minutes
    'REDIS_ENCODING': 'utf-8',
    'REDIS_DECODE_RESPONSES': True,
    'REDIS_RETRY_ON_TIMEOUT': True,
    'REDIS_RETRY_ON_ERROR': True,
    'REDIS_TIMEOUT': 5,  # seconds
    'REDIS_CONNECT_TIMEOUT': 5,  # seconds
    'REDIS_BUSY_WAIT_TIMEOUT': 5,  # seconds
    'REDIS_IDLE_CHECK_INTERVAL': 60  # seconds
}

# Bot required permissions
BOT_REQUIRED_PERMISSIONS = [
    'manage_channels',
    'manage_roles',
    'read_messages',
    'send_messages',
    'manage_messages',
    'embed_links',
    'read_message_history',
    'add_reactions'
]

# Channel settings
CHANNEL_SETTINGS = {
    'CATEGORY_NAME': 'DraXon OCULUS',
    'UPDATE_INTERVAL': 60,  # seconds
    'INCIDENT_CHECK_INTERVAL': 60  # seconds
}

# Channel configurations
CHANNELS_CONFIG = [
    {'name': '👥 All Staff: 0', 'type': 'count'},
    {'name': '🤖 Automated Systems: 0', 'type': 'count'},
    {'name': '✅ RSI Platform', 'type': 'status'},
    {'name': '✅ Star Citizen (PU)', 'type': 'status'},
    {'name': '✅ Arena Commander', 'type': 'status'}
]

# Channel permissions
CHANNEL_PERMISSIONS = {
    'display_only': {
        'everyone': {
            'view_channel': True,
            'connect': False,
            'speak': False
        },
        'bot': {
            'view_channel': True,
            'connect': True,
            'speak': True,
            'manage_channels': True
        }
    }
}

# Role settings
ROLE_SETTINGS = {
    'PROMOTION_COOLDOWN': 604800,  # 7 days in seconds
    'DEMOTION_COOLDOWN': 604800,   # 7 days in seconds
    'MIN_VOTES_REQUIRED': {
        'PROMOTION': 2,
        'DEMOTION': 3
    },
    'VOTE_TIMEOUT': 86400,  # 24 hours in seconds
    'ROLE_COLORS': {
        'Magnate': 0xFF0000,       # Red
        'Chairman': 0xFFA500,      # Orange
        'Executive': 0xFFFF00,     # Yellow
        'Team Leader': 0x00FF00,   # Green
        'Employee': 0x0000FF,      # Blue
        'Applicant': 0x808080      # Gray
    },
    'ROLE_PERMISSIONS': {
        'Magnate': ['administrator'],
        'Chairman': ['manage_guild', 'manage_roles', 'manage_channels'],
        'Executive': ['manage_messages', 'mention_everyone'],
        'Team Leader': ['manage_messages'],
        'Employee': ['send_messages', 'read_messages'],
        'Applicant': ['read_messages']
    }
}

# Status emojis
STATUS_EMOJIS = {
    'operational': '✅',
    'partial_outage': '⚠️',
    'major_outage': '❌',
    'maintenance': '🔧',
    'investigating': '🔍'
}

# Role hierarchy
ROLE_HIERARCHY = {
    'leadership': ['Magnate', 'Chairman', 'Executive'],
    'management': ['Team Leader'],
    'staff': ['Employee'],
    'applicants': ['Applicant']
}

# DraXon roles
DraXon_ROLES = {
    'leadership': ['Magnate', 'Chairman', 'Executive'],
    'management': ['Team Leader'],
    'staff': ['Employee'],
    'applicants': ['Applicant']
}

# V3 Additions Below
# These are new configurations that don't affect existing functionality

# Division configurations
DIVISIONS = {
    'Logistics': 'Transportation and supply management',
    'Resources': 'Mining, salvaging, and production',
    'Tactical': 'Legal mercenary operations',
    'HR': 'Recruitment and personnel',
    'SpecOps': 'Covert operations'
}

# Rank codes
RANK_CODES = {
    'Magnate': 'MG',
    'Chairman': 'CR',
    'Executive': 'EXE',
    'Team Leader': 'TL',
    'Employee': 'EMP',
    'Applicant': 'AP'
}

# Application settings
APPLICATION_SETTINGS = {
    'VOTE_TIMEOUT': 86400,  # 24 hours
    'MIN_VOTES_REQUIRED': {
        'EXE': 2,  # All CR + MG
        'TL': 2,   # Division EXE + CR
        'EMP': 2   # Division TL + EXE
    }
}

# System messages
SYSTEM_MESSAGES = {
    'APPLICATION': {
        'THREAD_CREATED': """
📋 Application for {position}
Applicant: {applicant}
Current Rank: {rank}
Division: {division}

📝 Application Details:
{details}

📊 Voting Status ({current}/{required})
Required Voters:
{voters}
""",
        'APPROVED': "✅ Application for {position} has been approved!",
        'REJECTED': "❌ Application for {position} has been rejected.",
        'EXPIRED': "⏰ Application for {position} has expired due to timeout."
    }
}
