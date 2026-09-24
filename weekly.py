#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유튜브 애널리틱스 주간 리포트 (OAuth) → 텔레그램 전송.

매주 월요일 실행. 지난주(월~일)와 그 전주를 비교한다.
채널별 refresh token은 YT_OAUTH_TOKENS(JSON) 또는 로컬 oauth_tokens.json.
"""
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from common import BASE, CONFIG, api_get, fmt, send_telegram

KST = timezone(timedelta(hours=9))
COMP_FILE = BASE / "competitors.json"
COMP_STATE = BASE / "competitor_state.json"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"

TRAFFIC_LABELS = {
    "SUBSCRIBER": "구독피드", "RELATED_VIDEO": "추천영상", "YT_SEARCH": "검색",
    "EXT_URL": "외부링크", "NO_LINK_OTHER": "직접/기타", "PLAYLIST": "재생목록",
    "NOTIFICATION": "알림", "YT_CHANNEL": "채널페이지", "YT_OTHER_PAGE": "탐색/기타",
    "SHORTS": "쇼츠피드", "HASHTAGS": "해시태그", "SOUND_PAGE": "사운드",
    "ADVERTISING": "광고", "END_SCREEN": "최종화면", "ANNOTATION": "카드",
    "CAMPAIGN_CARD": "캠페인", "PROMOTED": "홍보", "LIVE_REDIRECT": "라이브",
    "VIDEO_REMIXES": "리믹스", "IMMERSIVE_LIVE": "라이브탭",
}


def esc(s):
    return html.escape(str(s or ""))


def load_oauth():
    client_id = os.environ.get("OAUTH_CLIENT_ID") or CONFIG.get("oauth_client_id")
    client_secret = os.environ.get("OAUTH_CLIENT_SECRET") or CONFIG.get("oauth_client_secret")
    raw = os.environ.get("YT_OAUTH_TOKENS")
    token_file = BASE / "oauth_tokens.json"
    if raw:
        tokens = json.loads(raw)
    elif token_file.exists():
        tokens = json.loads(token_file.read_text(encoding="utf-8"))
    else:
        tokens = {}
    if not (client_id and client_secret and tokens):
        # 구글 승인(선택 단계)을 아직 안 한 상태. 실패가 아니라 "할 일 없음"이다.
        # 여기서 오류로 끝내면 매일 아침 텔레그램에 실패 알림이 날아간다.
        print("SKIP 구글 승인 전이라 건너뜁니다. (예약 현황·주간·월간은 승인 후에 옵니다)")
        raise SystemExit(0)
    return client_id, client_secret, tokens


def access_token(client_id, client_secret, refresh_token):
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def query(token, cid, start, end, metrics, **extra):
    params = {
        "ids": f"channel=={cid}",
        "startDate": start,
        "endDate": end,
        "metrics": metrics,
        **extra,
    }
    url = ANALYTICS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def totals(resp):
    """단일 행 응답을 {지표명: 값} 으로 변환."""
    cols = [c["name"] for c in resp.get("columnHeaders", [])]
    rows = resp.get("rows") or [[0] * len(cols)]
    return dict(zip(cols, rows[0]))


def pct_change(cur, prev):
    if not prev:
        return " (전주 0)"
    ch = (cur - prev) / prev * 100
    return f" (전주 {fmt(prev)}, {'+' if ch >= 0 else ''}{ch:.0f}%)"


def mmss(seconds):
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}"


def video_title(vid):
    """공개 Data API로 영상 제목 조회 (API 키 사용)."""
    try:
        items = api_get("videos", part="snippet", id=vid).get("items", [])
        return items[0]["snippet"]["title"] if items else vid
    except Exception:
        return vid


def competitor_section(now):
    """벤치마크 채널: 구독자/조회수 주간 증감 + 이번 주 히트 영상."""
    if not COMP_FILE.exists():
        return None
    comps = json.loads(COMP_FILE.read_text(encoding="utf-8"))
    if not comps:
        return None
    prev = json.loads(COMP_STATE.read_text(encoding="utf-8")) if COMP_STATE.exists() else {}
    resp = api_get("channels", part="statistics,contentDetails",
                   id=",".join(c["id"] for c in comps))
    info = {i["id"]: i for i in resp.get("items", [])}

    week_ago = now - timedelta(days=7)
    lines, new_state = ["👀 <b>벤치마크 채널</b> (주간)"], {}
    for c in comps:
        cid = c["id"]
        it = info.get(cid)
        if not it:
            continue
        subs = int(it["statistics"].get("subscriberCount", 0))
        views = int(it["statistics"].get("viewCount", 0))
        p = prev.get(cid, {})
        d_subs = subs - int(p["subs"]) if p.get("subs") is not None else None
        d_views = views - int(p["views"]) if p.get("views") is not None else None
        line = f"· {esc(c['name'])}: 구독 {fmt(subs)}"
        if d_subs is not None:
            line += f" ({'+' if d_subs >= 0 else ''}{fmt(d_subs)})"
        if d_views is not None:
            line += f" · 주간조회 {'+' if d_views >= 0 else ''}{fmt(d_views)}"
        lines.append(line)

        # 최근 7일 내 업로드 중 최고 조회 영상
        try:
            uploads = it["contentDetails"]["relatedPlaylists"].get("uploads")
            items = api_get("playlistItems", part="snippet",
                            playlistId=uploads, maxResults=5).get("items", [])
            fresh = [
                (i["snippet"]["resourceId"]["videoId"], i["snippet"]["title"])
                for i in items
                if datetime.fromisoformat(
                    i["snippet"]["publishedAt"].replace("Z", "+00:00")) >= week_ago
            ]
            if fresh:
                vr = api_get("videos", part="statistics",
                             id=",".join(v for v, _ in fresh))
                vs = {v["id"]: int(v["statistics"].get("viewCount", 0))
                      for v in vr.get("items", [])}
                top_v, top_t = max(fresh, key=lambda x: vs.get(x[0], 0))
                if vs.get(top_v, 0) > 0:
                    lines.append(f"   └ 이번주: 《{esc(top_t[:35])}》 {fmt(vs[top_v])}회")
        except Exception:
            pass

        new_state[cid] = {"subs": subs, "views": views}

    COMP_STATE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2), encoding="utf-8")
    return "\n".join(lines)


def main():
    now = datetime.now(KST)
    client_id, client_secret, tokens = load_oauth()

    # 지난주 월~일, 그 전주 월~일
    last_sun = (now - timedelta(days=now.weekday() + 1)).date()
    last_mon = last_sun - timedelta(days=6)
    prev_sun = last_mon - timedelta(days=1)
    prev_mon = prev_sun - timedelta(days=6)

    header = (f"📈 <b>주간 리포트</b> ({last_mon.month}/{last_mon.day}"
              f"~{last_sun.month}/{last_sun.day})")
    sections = []

    base_metrics = ("views,estimatedMinutesWatched,averageViewDuration,"
                    "averageViewPercentage,subscribersGained,subscribersLost,"
                    "likes,comments,shares")

    for c in CONFIG["channels"]:
        cid = c["id"]
        tk = tokens.get(cid)
        if not tk:
            sections.append(f"{c['emoji']} <b>{esc(c['name'])}</b>: 토큰 없음")
            continue
        try:
            at = access_token(client_id, client_secret, tk["refresh_token"])
            cur = totals(query(at, cid, str(last_mon), str(last_sun), base_metrics))
            prev = totals(query(at, cid, str(prev_mon), str(prev_sun), base_metrics))
        except Exception as e:
            sections.append(f"{c['emoji']} <b>{esc(c['name'])}</b>: 조회 실패 ({esc(e)})")
            continue

        lines = [f"{c['emoji']} <b>{esc(c['name'])}</b>"]
        lines.append(f"조회수 {fmt(cur.get('views', 0))}{pct_change(cur.get('views', 0), prev.get('views', 0))}")
        lines.append(
            f"시청 {fmt(cur.get('estimatedMinutesWatched', 0))}분"
            f"{pct_change(cur.get('estimatedMinutesWatched', 0), prev.get('estimatedMinutesWatched', 0))}"
        )
        lines.append(
            f"평균 지속 {mmss(cur.get('averageViewDuration', 0))}"
            f" ({cur.get('averageViewPercentage', 0):.0f}% 시청)"
        )
        gained, lost = int(cur.get("subscribersGained", 0)), int(cur.get("subscribersLost", 0))
        lines.append(f"구독 +{fmt(gained)} / -{fmt(lost)} (순증 {'+' if gained - lost >= 0 else ''}{fmt(gained - lost)})")
        lines.append(
            f"좋아요 {fmt(cur.get('likes', 0))} · 댓글 {fmt(cur.get('comments', 0))} · 공유 {fmt(cur.get('shares', 0))}"
        )

        # 트래픽 소스 상위 3
        try:
            tr = query(at, cid, str(last_mon), str(last_sun), "views",
                       dimensions="insightTrafficSourceType", sort="-views", maxResults="3")
            total_views = int(cur.get("views", 0)) or 1
            parts = [
                f"{TRAFFIC_LABELS.get(r[0], r[0])} {int(r[1]) * 100 // total_views}%"
                for r in tr.get("rows", []) if int(r[1]) > 0
            ]
            if parts:
                lines.append("유입: " + " · ".join(parts))
        except Exception:
            pass

        # 지난주 인기 영상 1위
        try:
            top = query(at, cid, str(last_mon), str(last_sun), "views",
                        dimensions="video", sort="-views", maxResults="1")
            rows = top.get("rows", [])
            if rows and int(rows[0][1]) > 0:
                title = video_title(rows[0][0])
                lines.append(f"주간 1위: 《{esc(title[:40])}》 {fmt(rows[0][1])}회")
        except Exception:
            pass

        # 수익 (수익창출 채널만 값이 옴)
        try:
            rev = totals(query(at, cid, str(last_mon), str(last_sun), "estimatedRevenue"))
            if rev.get("estimatedRevenue"):
                lines.append(f"수익 ${rev['estimatedRevenue']:.2f}")
        except Exception:
            pass

        sections.append("\n".join(lines))

    try:
        comp = competitor_section(now)
        if comp:
            sections.append(comp)
    except Exception as e:
        sections.append(f"👀 벤치마크 조회 실패 ({esc(e)})")

    send_telegram(header + "\n\n" + "\n\n".join(sections))
    print(f"[{now.isoformat()}] 주간 리포트 전송 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_telegram(f"⚠️ 주간 리포트 실행 실패: {esc(e)}")
        except Exception:
            pass
        print(f"실패: {e}", file=sys.stderr)
        raise
