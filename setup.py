#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""세팅 도우미 — 열쇠가 맞는지 확인하고, 채널을 찾아 넣고, 시험 메시지를 보낸다.

에이전트가 사람 대신 실행한다. 사람은 결과만 본다.

  python setup.py 점검              열쇠 세 개가 살아 있는지 확인
  python setup.py 채팅방            텔레그램에서 내 채팅방 번호를 찾아 저장
  python setup.py 채널 @핸들 [...]   채널을 찾아 channels.json에 넣는다
  python setup.py 시험              텔레그램으로 시험 메시지를 보낸다
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# 윈도우 기본 콘솔 인코딩(cp949)에서 한글·기호 출력이 죽지 않도록
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).resolve().parent
CONFIG_FILE = BASE / "config.json"
CHANNELS_FILE = BASE / "channels.json"
YT = "https://www.googleapis.com/youtube/v3"

EMOJIS = ["🎬", "🎙", "🎵", "🎤", "📺", "🎞", "🎥", "📻", "🎧", "🍿"]


def load():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def save(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


def get_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def yt(cfg, endpoint, **params):
    params["key"] = cfg["youtube_api_key"]
    return get_json(f"{YT}/{endpoint}?" + urllib.parse.urlencode(params))


def tg(cfg, method, **params):
    url = f"https://api.telegram.org/bot{cfg['telegram_bot_token']}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return get_json(url)


def need(cfg, *keys):
    missing = [k for k in keys if not cfg.get(k)]
    if missing:
        names = {"youtube_api_key": "유튜브 열쇠",
                 "telegram_bot_token": "텔레그램 봇 열쇠",
                 "telegram_chat_id": "텔레그램 채팅방 번호"}
        print("아직 없는 것: " + ", ".join(names.get(k, k) for k in missing))
        sys.exit(1)


# ── 점검 ──────────────────────────────────────────────────────────────
def cmd_check():
    cfg = load()
    ok = True

    if not cfg.get("youtube_api_key"):
        print("MISSING 유튜브 열쇠")
        ok = False
    else:
        try:
            yt(cfg, "channels", part="id", forHandle="@YouTube")
            print("OK 유튜브 열쇠")
        except Exception as e:
            print(f"FAIL 유튜브 열쇠 ({e})")
            print("  → 열쇠가 틀렸거나, 구글 클라우드에서 'YouTube Data API v3'를 안 켰습니다.")
            ok = False

    if not cfg.get("telegram_bot_token"):
        print("MISSING 텔레그램 봇 열쇠")
        ok = False
    else:
        try:
            me = tg(cfg, "getMe")
            print(f"OK 텔레그램 봇 열쇠 (@{me['result']['username']})")
        except Exception as e:
            print(f"FAIL 텔레그램 봇 열쇠 ({e})")
            ok = False

    if not cfg.get("telegram_chat_id"):
        print("MISSING 텔레그램 채팅방 번호")
        ok = False
    else:
        print(f"OK 텔레그램 채팅방 번호 {cfg['telegram_chat_id']}")

    if CHANNELS_FILE.exists():
        chs = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
        real = [c for c in chs if not str(c.get("id", "")).startswith("여기에")]
        if real:
            print(f"OK 채널 {len(real)}개: {', '.join(c['name'] for c in real)}")
        else:
            print("MISSING 채널")
            ok = False

    print("\n" + ("READY 모두 준비됐습니다." if ok else "NOT_READY 위에 MISSING/FAIL 로 나온 것을 채워야 합니다."))
    sys.exit(0 if ok else 1)


# ── 채팅방 번호 찾기 ──────────────────────────────────────────────────
def cmd_chat():
    cfg = load()
    need(cfg, "telegram_bot_token")
    try:
        ups = tg(cfg, "getUpdates").get("result", [])
    except Exception as e:
        print(f"FAIL 텔레그램 조회 실패: {e}")
        sys.exit(1)
    ids = []
    for u in ups:
        msg = u.get("message") or u.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") and chat["id"] not in [i for i, _ in ids]:
            ids.append((chat["id"], chat.get("first_name") or chat.get("title") or ""))
    if not ids:
        print("MISSING 아직 대화 기록이 없습니다.")
        print("→ 텔레그램에서 그 봇을 찾아 '시작'을 누르고 아무 말이나 보낸 뒤, 다시 실행하세요.")
        sys.exit(1)
    chat_id, who = ids[-1]
    cfg["telegram_chat_id"] = str(chat_id)
    save(cfg)
    print(f"OK 채팅방 저장 {chat_id} ({who})")


# ── 채널 넣기 ─────────────────────────────────────────────────────────
def cmd_channels(args):
    cfg = load()
    need(cfg, "youtube_api_key")
    if not args:
        print("채널 주소나 @핸들을 하나 이상 적어주세요.")
        sys.exit(1)

    found = []
    for raw in args:
        h = raw.strip().split("?")[0].rstrip("/")
        mode, key = "handle", h
        if "youtube.com" in h:
            tail = h.split("youtube.com/", 1)[1]
            part = tail.split("/")
            if part[0] == "channel" and len(part) > 1:
                mode, key = "id", part[1]
            elif part[0] in ("c", "user") and len(part) > 1:
                mode, key = "user", part[1]
            else:
                mode, key = "handle", part[0]
        elif h.startswith("UC") and len(h) == 24:
            mode, key = "id", h
        if mode == "handle" and not key.startswith("@"):
            key = "@" + key
        try:
            if mode == "id":
                items = yt(cfg, "channels", part="snippet", id=key).get("items", [])
            elif mode == "user":
                items = yt(cfg, "channels", part="snippet", forUsername=key).get("items", [])
                if not items:  # 옛 사용자 이름이 아니면 핸들로 한 번 더
                    items = yt(cfg, "channels", part="snippet",
                               forHandle="@" + key).get("items", [])
            else:
                items = yt(cfg, "channels", part="snippet", forHandle=key).get("items", [])
        except Exception as e:
            print(f"FAIL {raw} 조회 실패 ({e})")
            continue
        if not items:
            print(f"FAIL {raw} 그런 채널을 못 찾았습니다.")
            continue
        it = items[0]
        found.append({"id": it["id"], "name": it["snippet"]["title"]})
        print(f"OK {raw} -> {it['snippet']['title']}")

    if not found:
        sys.exit(1)

    # 기존 채널은 남기고, 새 것만 뒤에 붙인다 (덮어쓰지 않는다)
    out = []
    if CHANNELS_FILE.exists():
        try:
            out = [c for c in json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
                   if not str(c.get("id", "")).startswith("여기에")]
        except Exception:
            out = []
    have = {c["id"] for c in out}
    added = 0
    for c in found:
        if c["id"] in have:
            print(f"SKIP {c['name']} 이미 들어 있음")
            continue
        out.append({"id": c["id"], "emoji": EMOJIS[len(out) % len(EMOJIS)], "name": c["name"]})
        have.add(c["id"])
        added += 1

    CHANNELS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print(f"\nDONE 새로 {added}개 추가, 지금 모두 {len(out)}개")


# ── 시험 메시지 ───────────────────────────────────────────────────────
def cmd_test():
    cfg = load()
    need(cfg, "telegram_bot_token", "telegram_chat_id")
    text = "연결됐습니다. 이제 여기로 채널 소식이 옵니다."
    url = f"https://api.telegram.org/bot{cfg['telegram_bot_token']}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": cfg["telegram_chat_id"], "text": text}).encode()
    try:
        with urllib.request.urlopen(url, data=data, timeout=20) as r:
            json.load(r)
        print("OK 보냈습니다. 텔레그램을 확인하세요.")
    except Exception as e:
        print(f"FAIL 전송 실패: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd in ("점검", "check"):
        cmd_check()
    elif cmd in ("채팅방", "chat"):
        cmd_chat()
    elif cmd in ("채널", "channels"):
        cmd_channels(args)
    elif cmd in ("시험", "test"):
        cmd_test()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
