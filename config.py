"""
Configuration for Riven.

Copy this file to config_local.py and update with your settings.
config_local.py is gitignored.
"""

# Memory API endpoint
MEMORY_API_URL = "http://192.168.1.11:8030"

# LLM API endpoint (for summarization)
LLM_URL = "http://127.0.0.1:8000/v1/"
LLM_API_KEY = "sk-dummy"
LLM_MODEL = "nvidia/MiniMax-M2.5-NVFP4"

# Default database name
DEFAULT_DB = "riven"

# Context settings
CONTEXT_MAX_MESSAGES = 50
CONTEXT_KEEP_RECENT = 10
CONTEXT_CLUSTER_GAP_MINUTES = 30
CONTEXT_CLUSTER_EXCLUDE_MINUTES = 30
