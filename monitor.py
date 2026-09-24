#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유튜브 채널 시간별 감시 → 변화가 있을 때만 텔레그램 알림.

감지 항목: 새 댓글, 구독자 변동, 구독자/조회수 마일스톤, 조회수 급상승, 새 영상.
monitor_state.json에 직전 상태를 저장하고 실행마다 비교한다.
첫 실행은 알림 없이 상태만 만든다(시딩).
"""
import html
import json
import re
import statistics
import sys
from datetime import datetime, timedelta, timezone

from common import BASE, CONFIG, api_get, fmt, send_telegram

STATE_FILE = BASE / "monitor_state.json"
KST = timezone(timedelta(hours=9))

SUB_MILESTONES = [100, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 5000,
                  7000, 10000, 20000, 50000, 100000, 500000, 1000000]
VIEW_MILESTONES = [1000, 5000, 10000, 50000, 100000, 500000, 1000000, 5000000]
RECENT_VIDEOS = 5        # 채널당 감시할 최근 영상 수
MAX_COMMENT_ALERTS = 5   # 채널당 한 번에 알리는 댓글 수 상한
SURGE_MIN_DELTA = 30     # 급상승 최소 증가량 (1회 간격 기준)
SURGE_RATIO = 3          # 평소 증가 속도의 몇 배면 급상승으로 볼지
SEEN_COMMENTS_CAP = 300  # 상태 파일에 기억해둘 댓글 ID 수


def esc(s):
    return html.escape(str(s or ""))


def clip(s, n=80):
    s = str(s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def parse_duration(iso):
    """ISO8601 재생시간(PT#H#M#S) → 초."""
    h = re.search(r"(\d+)H", iso)
    m = re.search(r"(\d+)M", iso)
    s = re.search(r"(\d+)S", iso)
    return (int(h.group(1)) if h else 0) * 3600 + \
           (int(m.group(1)) if m else 0) * 60 + (int(s.group(1)) if s else 0)


def crossed(prev, cur, milestones):
    """prev→cur 사이에 넘은 마일스톤 중 가장 큰 것 (없으면 None)."""
    hit = [m for m in milestones if prev < m <= cur]
    return hit[-1] if hit else None


def fetch_comments(cid):
    """채널 전체의 최신 댓글 스레드. 댓글 기능이 꺼져 있으면 빈 목록."""
    try:
        items = api_get(
            "commentThreads",
            part="snippet",
            allThreadsRelatedToChannelId=cid,
            order="time",
            maxResults=20,
        ).get("items", [])
    except Exception:
        return []
    out = []
    for t in items:
        top = t["snippet"]["topLevelComment"]["snippet"]
        out.append({
            "id": t["id"],
            "author": top.get("authorDisplayName", ""),
            "author_cid": (top.get("authorChannelId") or {}).get("value", ""),
            "text": top.get("textOriginal", ""),
            "video_id": top.get("videoId", ""),
        })
    return out


def main():
    now = datetime.now(KST)
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
    first_run = not state.get("seeded")
    st_channels = state.setdefault("channels", {})

    ids = [c["id"] for c in CONFIG["channels"]]
    resp = api_get("channels", part="statistics,contentDetails", id=",".join(ids))
    info = {i["id"]: i for i in resp.get("items", [])}

    # 채널별 최근 업로드 목록 → 영상 통계는 전 채널 합쳐서 한 번에 조회
    recent = {}
    for cid, item in info.items():
        uploads = item["contentDetails"]["relatedPlaylists"].get("uploads")
        vids = []
        if uploads:
            try:
                vids = [
                    (i["snippet"]["resourceId"]["videoId"], i["snippet"]["title"],
                     i["snippet"]["publishedAt"])
                    for i in api_get(
                        "playlistItems", part="snippet",
                        playlistId=uploads, maxResults=RECENT_VIDEOS,
                    ).get("items", [])
                ]
            except Exception:
                pass
        recent[cid] = vids

    comments = {cid: fetch_comments(cid) for cid in info}

    # 제목 조회용: 최근 영상 + 댓글이 달린 영상
    title_map = {vid: t for vids in recent.values() for vid, t, _ in vids}
    need_ids = {v for vids in recent.values() for v, _, _ in vids}
    need_ids |= {c["video_id"] for cs in comments.values() for c in cs if c["video_id"]}
    video_stats, extra_titles, video_secs = {}, {}, {}
    if need_ids:
        vresp = api_get("videos", part="snippet,statistics,contentDetails",
                        id=",".join(sorted(need_ids)))
        for v in vresp.get("items", []):
            video_stats[v["id"]] = v["statistics"]
            extra_titles[v["id"]] = v["snippet"]["title"]
            video_secs[v["id"]] = parse_duration(v["contentDetails"].get("duration", ""))
    title_map = {**extra_titles, **title_map}

    sections = []
    for c in CONFIG["channels"]:
        cid = c["id"]
        item = info.get(cid)
        if not item:
            continue
        # 나중에 추가된 채널은 처음 한 번은 조용히 기록만 (기존 영상·댓글을 새것으로 오인 방지)
        ch_first = first_run or cid not in st_channels
        st = st_channels.setdefault(cid, {})
        events = []

        subs = int(item["statistics"].get("subscriberCount", 0))
        prev_subs = st.get("subs")

        # 구독자 변동 + 마일스톤
        if prev_subs is not None and subs != prev_subs:
            d = subs - prev_subs
            events.append(f"👥 구독자 {'+' if d > 0 else ''}{fmt(d)} ({fmt(prev_subs)} → {fmt(subs)})")
            ms = crossed(prev_subs, subs, SUB_MILESTONES)
            if ms and ms > st.get("sub_milestone", 0):
                events.append(f"🎉 구독자 <b>{fmt(ms)}명 돌파!</b>")
                st["sub_milestone"] = ms
        st["subs"] = subs

        # 새 영상 / 조회수 급상승 / 조회수 마일스톤 / 24시간 성적표
        known = set(st.get("known_videos", []))
        vv = st.setdefault("video_views", {})
        cards = st.setdefault("report_cards", {})
        for vid, title, published in recent[cid]:
            views = int(video_stats.get(vid, {}).get("viewCount", 0))
            pub = datetime.fromisoformat(published.replace("Z", "+00:00"))
            age_h = (now - pub).total_seconds() / 3600
            if vid not in known and not ch_first:
                events.append(f"🆕 새 영상 업로드: 《{esc(clip(title, 40))}》")
            # 업로드 24시간 안 된 영상은 성적표 대상으로 추적
            if age_h < 24 and vid not in cards:
                cards[vid] = {"pub": published, "done": False}
            card = cards.get(vid)
            if card and not card["done"] and age_h >= 24:
                card["done"] = True
                hist = st.setdefault("h24_history", [])
                norm = views * 24 / min(max(age_h, 24), 36)  # 밤사이 지연 보정
                if len(hist) >= 3:
                    base = statistics.median(hist)
                    ratio = norm / base if base else 0
                    if ratio >= 2:
                        verdict = f"평소({fmt(base)}회)의 {ratio:.1f}배 🚀 터졌습니다!"
                    elif ratio >= 1.2:
                        verdict = f"평소({fmt(base)}회)의 {ratio:.1f}배 😊 순항 중"
                    elif ratio >= 0.8:
                        verdict = f"평소({fmt(base)}회) 수준 😐"
                    else:
                        verdict = (f"평소({fmt(base)}회)의 {ratio * 100:.0f}% 🐢 "
                                   "제목·썸네일 점검 고려")
                else:
                    verdict = f"(비교 데이터 {len(hist)}/3개 수집 중)"
                events.append(
                    f"📋 24시간 성적표: 《{esc(clip(title, 40))}》 "
                    f"{fmt(views)}회 ({age_h:.0f}시간 경과) — {verdict}"
                )
                hist.append(round(norm))
                st["h24_history"] = hist[-20:]
            prev = vv.get(vid)
            if prev is not None:
                delta = views - int(prev["views"])
                ema = float(prev.get("ema", 0))
                if delta >= SURGE_MIN_DELTA and ema > 0 and delta >= SURGE_RATIO * ema:
                    events.append(
                        f"📈 급상승: 《{esc(clip(title, 40))}》 +{fmt(delta)}회 (평소의 {delta / ema:.0f}배)"
                    )
                ms = crossed(int(prev["views"]), views, VIEW_MILESTONES)
                if ms:
                    events.append(f"🎉 《{esc(clip(title, 40))}》 조회수 <b>{fmt(ms)}회 돌파!</b>")
                new_ema = delta if ema == 0 else 0.7 * ema + 0.3 * delta
            else:
                new_ema = 0
            vv[vid] = {"views": views, "ema": round(max(new_ema, 0), 2)}
        st["known_videos"] = sorted(known | {v for v, _, _ in recent[cid]})[-50:]
        # 더는 감시하지 않는 영상은 상태에서 정리
        tracked = {v for v, _, _ in recent[cid]}
        for gone in [v for v in vv if v not in tracked]:
            del vv[gone]
        for gone in [v for v in cards if v not in tracked and cards[v]["done"]]:
            del cards[gone]

        # 새 댓글 → 내용을 그대로 알림 (본인 채널이 단 댓글은 제외)
        own_ids = {ch["id"] for ch in CONFIG["channels"]}
        seen = set(st.get("seen_comments", []))
        fresh = [cm for cm in comments[cid]
                 if cm["id"] not in seen and cm["author_cid"] not in own_ids]
        if fresh and not ch_first:
            events.append(f"💬 새 댓글 {len(fresh)}개")
            for cm in fresh[:MAX_COMMENT_ALERTS]:
                vt = clip(title_map.get(cm["video_id"], ""), 30)
                link = f"https://youtu.be/{cm['video_id']}" if cm.get("video_id") else ""
                events.append(
                    f"  · {esc(cm['author'])}: \"{esc(clip(cm['text'], 120))}\"\n"
                    f"    《{esc(vt)}》 {link}")
        st["seen_comments"] = ([cm["id"] for cm in comments[cid]] +
                               list(seen))[:SEEN_COMMENTS_CAP]

        if events:
            sections.append(f"{c['emoji']} <b>{esc(c['name'])}</b>\n" + "\n".join(events))

    # 감시(경쟁) 채널 새 영상 → 개별 알림
    watch_file = BASE / "watch_channels.json"
    if watch_file.exists():
        watch = json.loads(watch_file.read_text(encoding="utf-8"))
        wst = state.setdefault("watch", {})
        wids = [w["id"] for w in watch]
        w_uploads = {}
        if wids:
            try:
                w_uploads = {
                    i["id"]: i["contentDetails"]["relatedPlaylists"].get("uploads")
                    for i in api_get("channels", part="contentDetails",
                                     id=",".join(wids)).get("items", [])
                }
            except Exception:
                pass
        for w in watch:
            uploads = w_uploads.get(w["id"])
            if not uploads:
                continue
            try:
                items = api_get("playlistItems", part="snippet",
                                playlistId=uploads, maxResults=5).get("items", [])
            except Exception:
                continue
            seeding = w["id"] not in wst  # 감시 첫 회는 알림 없이 상태만 기록
            known = set(wst.get(w["id"], []))
            cur = set()
            for i2 in items:
                vid = i2["snippet"]["resourceId"]["videoId"]
                cur.add(vid)
                if seeding or vid in known:
                    continue
                title = i2["snippet"]["title"]
                msg = (f"👀 <b>경쟁 채널 새 영상</b> — {esc(w['name'])}\n"
                       f"《{esc(clip(title, 70))}》\n"
                       f"https://youtu.be/{vid}")
                send_telegram(msg)
            wst[w["id"]] = sorted(known | cur)[-30:]

    state["seeded"] = True
    state["updated_at"] = now.isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    if first_run:
        send_telegram("🟢 실시간 감시 시작! 이제 새 댓글·구독자 변동·급상승·마일스톤이 "
                      "생기면 바로 알려드립니다. (매시 30분 확인, 08:30~23:30)")
        print(f"[{now.isoformat()}] 시딩 완료")
    elif sections:
        # 채널마다 따로 보낸다. 한 통에 몰면 텔레그램 4096자 제한에 걸려
        # 그 회차 알림이 통째로 사라진다(상태는 이미 저장된 뒤라 다시 안 온다).
        head = f"🔔 <b>채널 알림</b> ({now:%H:%M})"
        for sec in sections:
            body = sec if len(sec) < 3800 else sec[:3800] + "\n…(줄임)"
            send_telegram(f"{head}\n\n{body}")
        print(f"[{now.isoformat()}] 알림 {len(sections)}개 채널 전송")
    else:
        print(f"[{now.isoformat()}] 변화 없음")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_telegram(f"⚠️ 채널 감시 실행 실패: {esc(e)}")
        except Exception:
            pass
        print(f"실패: {e}", file=sys.stderr)
        raise
