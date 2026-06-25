"""GuardinoBot web-panel API (FastAPI, §9).

Separate service beside the bot, sharing the same DB/Redis and the §6 adapter
layer. Auth is Telegram one-time-code → JWT. See ``app/api/main.py``.
"""
