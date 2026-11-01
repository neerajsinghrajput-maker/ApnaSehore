"""Telegram alerts (optional). .env mein TELEGRAM_BOT_TOKEN aur TELEGRAM_CHAT_ID daalo.

Token: Telegram par @BotFather se naya bot banao.
Chat ID: apne bot ko message bhejo, phir https://api.telegram.org/bot<TOKEN>/getUpdates kholo.
"""
import os

import requests


def notify(text: str) -> None:
    print(text)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=10)
    except requests.RequestException as e:
        print(f"[telegram] message nahi gaya: {e}")
