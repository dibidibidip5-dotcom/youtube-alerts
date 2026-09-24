# -*- coding: utf-8 -*-
"""report.py / monitor.py 공용: 설정 로딩, 유튜브 API, 텔레그램 전송."""
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
YT = "https://www.googleapis.com/youtube/v3"


def load_config():
    """비밀정보는 환경변수 우선(깃허브 액션), 없으면 config.json(로컬 실행)."""
    cfg = {}
    local = BASE / "config.json"
    if local.exists():
        cfg = json.loads(local.read_text(encoding="utf-8"))
    cfg["youtube_api_key"] = os.environ.get("YT_API_KEY") or cfg.get("youtube_api_key")
    cfg["telegram_bot_token"] = os.environ.get("TG_BOT_TOKEN") or cfg.get("telegram_bot_token")
    cfg["telegram_chat_id"] = os.environ.get("TG_CHAT_ID") or cfg.get("telegram_chat_id")
    if "channels" not in cfg:
        cfg["channels"] = json.loads((BASE / "channels.json").read_text(encoding="utf-8"))
    missing = [k for k in ("youtube_api_key", "telegram_bot_token", "telegram_chat_id") if not cfg.get(k)]
    if missing:
        raise SystemExit(f"설정 누락: {', '.join(missing)}")
    return cfg


CONFIG = load_config()


def api_get(endpoint, **params):
    params["key"] = CONFIG["youtube_api_key"]
    url = f"{YT}/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def api_get_auth(token, endpoint, **params):
    """소유자 OAuth로 조회 — 비공개·예약 영상까지 보인다."""
    url = f"{YT}/{endpoint}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def send_telegram(text, reply_markup=None):
    url = f"https://api.telegram.org/bot{CONFIG['telegram_bot_token']}/sendMessage"
    payload = {
        "chat_id": CONFIG["telegram_chat_id"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    data = urllib.parse.urlencode(payload).encode()
    with urllib.request.urlopen(url, data=data, timeout=30) as r:
        return json.load(r)


def fmt(n):
    return f"{int(n):,}"
