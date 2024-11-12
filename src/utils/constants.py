"""Constants for DraXon OCULUS"""

import os
from pathlib import Path

# Version and description
APP_VERSION = "3.0.0"
BOT_DESCRIPTION = "DraXon Organizational Command & Unified Leadership Implementation System"

# Directory paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = os.path.join(ROOT_DIR, 'logs')
DATA_DIR = os.path.join(ROOT_DIR, 'data')

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

# Cache settings
CACHE_SETTINGS = {
    'STATUS_TTL': 300,  # 5 minutes
    'INCIDENT_TTL': 3600,  # 1 hour
    'MEMBER_TTL': 3600  # 1 hour
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
