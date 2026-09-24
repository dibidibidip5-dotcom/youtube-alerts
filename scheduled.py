#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예약(공개 예정) 영상 현황 → 텔레그램 전송.

매일 08:30(KST) 실행. 채널별 OAuth로 업로드 목록의 비공개 영상 중
publishAt이 설정된 것을 공개 예정 시각순으로 보여준다.
"""
import html
import re
import sys
from datetime import datetime, timedelta, timezone

from common import CONFIG, api_get, api_get_auth, send_telegram
from weekly import access_token, load_oauth

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
LONGFORM_SECS = 180  # 180초 초과를 롱폼으로 본다


def esc(s):
    return html.escape(str(s or ""))


def parse_duration(iso):
    """ISO8601 재생시간(PT#H#M#S) → 초."""
    h = re.search(r"(\d+)H", iso)
    m = re.search(r"(\d+)M", iso)
    s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) if h else 0) * 3600 + \
           (int(m.group(1)) if m else 0) * 60 + (int(s.group(1)) if s else 0)


def upcoming_videos(uploads_playlist_id, token, now):
    """예약(공개 예정) 영상의 (영상ID, 제목, 공개예정 KST 시각, 재생초) 목록.

    소유자 OAuth 필요. 공개 시각 오름차순."""
    items = api_get_auth(
        token,
        "playlistItems",
        part="snippet,status",
        playlistId=uploads_playlist_id,
        maxResults=25,
    ).get("items", [])
    private_ids = [
        i["snippet"]["resourceId"]["videoId"]
        for i in items
        if i.get("status", {}).get("privacyStatus") == "private"
    ]
    if not private_ids:
        return []
    resp = api_get_auth(token, "videos", part="snippet,status,contentDetails",
                        id=",".join(private_ids))
    out = []
    for v in resp.get("items", []):
        publish_at = v["status"].get("publishAt")
        if not publish_at:
            continue  # 예약 없이 그냥 비공개인 영상
        t = datetime.fromisoformat(publish_at.replace("Z", "+00:00")).astimezone(KST)
        if t >= now:
            out.append((v["id"], v["snippet"]["title"], t,
                        parse_duration(v["contentDetails"].get("duration", ""))))
    out.sort(key=lambda x: x[2])
    return out


def main():
    now = datetime.now(KST)
    client_id, client_secret, tokens = load_oauth()

    ids = [c["id"] for c in CONFIG["channels"]]
    resp = api_get("channels", part="contentDetails", id=",".join(ids))
    uploads_map = {
        i["id"]: i["contentDetails"]["relatedPlaylists"].get("uploads")
        for i in resp.get("items", [])
    }

    lines = [f"📅 <b>예약 영상 현황</b> ({now.month}/{now.day} {WEEKDAYS[now.weekday()]})"]
    for c in CONFIG["channels"]:
        cid = c["id"]
        lines.append("")
        lines.append(f"{c['emoji']} <b>{esc(c['name'])}</b>")
        tk = tokens.get(cid)
        uploads = uploads_map.get(cid)
        if not (tk and uploads):
            lines.append("· 조회 불가 (토큰/채널 확인 필요)")
            continue
        try:
            token = access_token(client_id, client_secret, tk["refresh_token"])
            vids = upcoming_videos(uploads, token, now)
        except Exception:
            lines.append("· 조회 실패")
            continue
        if not vids:
            lines.append("· 예약된 영상 없음 ⚠️")
        for _vid, title, t, secs in vids:
            wd = WEEKDAYS[t.weekday()]
            tag = "🎬 " if secs > LONGFORM_SECS else ""
            lines.append(f"· {t.month}/{t.day}({wd}) {t:%H:%M} — {tag}\"{esc(title)}\"")

    send_telegram("\n".join(lines))
    print(f"[{now.isoformat()}] 전송 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_telegram(f"⚠️ 예약 영상 리포트 실행 실패: {esc(e)}")
        except Exception:
            pass
        print(f"실패: {e}", file=sys.stderr)
        raise
