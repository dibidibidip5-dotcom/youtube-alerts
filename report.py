#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유튜브 채널 일일 리포트 → 텔레그램 전송.

매일 09:00(KST) 실행. state.json에 전일 수치를 저장해 두고 증감을 계산한다.
"""
import html
import json
import sys
from datetime import datetime, timedelta, timezone

from common import BASE, CONFIG, api_get, fmt, send_telegram

STATE_FILE = BASE / "state.json"
KST = timezone(timedelta(hours=9))


def esc(s):
    return html.escape(str(s or ""))


def delta_str(cur, prev):
    if prev is None:
        return ""
    d = int(cur) - int(prev)
    return f" ({'+' if d >= 0 else ''}{fmt(d)})"


def recent_videos(uploads_playlist_id):
    """업로드 재생목록에서 최근 영상 3개의 (id, 제목, 게시시각)을 가져온다."""
    try:
        items = api_get(
            "playlistItems",
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=3,
        ).get("items", [])
    except Exception:
        return []
    return [
        (
            i["snippet"]["resourceId"]["videoId"],
            i["snippet"]["title"],
            i["snippet"]["publishedAt"],
        )
        for i in items
    ]


def main():
    now = datetime.now(KST)
    prev_state = {}
    if STATE_FILE.exists():
        prev_state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    prev_channels = prev_state.get("channels", {})

    ids = [c["id"] for c in CONFIG["channels"]]
    resp = api_get(
        "channels",
        part="snippet,statistics,contentDetails",
        id=",".join(ids),
    )
    info = {i["id"]: i for i in resp.get("items", [])}

    # 채널별 최근 영상 수집 후 영상 통계는 한 번에 조회
    channel_videos = {}
    all_video_ids = []
    for cid, item in info.items():
        uploads = item["contentDetails"]["relatedPlaylists"].get("uploads")
        vids = recent_videos(uploads) if uploads else []
        channel_videos[cid] = vids
        all_video_ids += [v[0] for v in vids]

    video_stats = {}
    if all_video_ids:
        vresp = api_get("videos", part="statistics", id=",".join(all_video_ids))
        video_stats = {v["id"]: v["statistics"] for v in vresp.get("items", [])}

    weekday = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()]
    lines = [f"📊 <b>유튜브 일일 리포트</b> ({now.month}/{now.day} {weekday})"]
    new_state = {"updated_at": now.isoformat(), "channels": {}}

    for c in CONFIG["channels"]:
        cid = c["id"]
        item = info.get(cid)
        lines.append("")
        if not item:
            lines.append(f"{c['emoji']} <b>{esc(c['name'])}</b>: 채널 조회 실패")
            continue
        stats = item["statistics"]
        subs = int(stats.get("subscriberCount", 0))
        views = int(stats.get("viewCount", 0))
        prev = prev_channels.get(cid, {})

        lines.append(f"{c['emoji']} <b>{esc(c['name'])}</b>")
        lines.append(f"구독자 {fmt(subs)}{delta_str(subs, prev.get('subs'))}")
        if prev.get("views") is not None:
            lines.append(f"어제 조회수 {fmt(views - int(prev['views']))} (누적 {fmt(views)})")
        else:
            lines.append(f"누적 조회수 {fmt(views)}")

        vids = channel_videos.get(cid, [])
        # 최근 26시간 내 업로드 = 새 영상
        cutoff = now - timedelta(hours=26)
        for vid, title, published in vids:
            pub = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if pub >= cutoff:
                vs = video_stats.get(vid, {})
                lines.append(f"🆕 새 영상: \"{esc(title)}\" ({fmt(vs.get('viewCount', 0))}회)")
        # 최근 영상 중 조회수 1위
        if vids:
            top = max(vids, key=lambda v: int(video_stats.get(v[0], {}).get("viewCount", 0)))
            vs = video_stats.get(top[0], {})
            lines.append(
                f"최근 인기: \"{esc(top[1])}\" {fmt(vs.get('viewCount', 0))}회 · "
                f"👍{fmt(vs.get('likeCount', 0))} · 💬{fmt(vs.get('commentCount', 0))}"
            )

        new_state["channels"][cid] = {"subs": subs, "views": views}

    send_telegram("\n".join(lines))
    STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{now.isoformat()}] 전송 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_telegram(f"⚠️ 유튜브 리포트 실행 실패: {esc(e)}")
        except Exception:
            pass
        print(f"실패: {e}", file=sys.stderr)
        raise
