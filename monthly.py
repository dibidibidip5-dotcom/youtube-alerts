#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""월간 시청 패턴 리포트 (OAuth) → 텔레그램 전송.

최근 90일 데이터로 요일별 시청 분포, 시청자 연령/성별, 기기를 분석해
"무슨 요일에 올리는 게 좋은지"를 알려준다. 매월 1일 실행.
※ 시간대(몇 시)별 데이터는 유튜브 API가 제공하지 않아 요일 단위까지만 분석.
"""
import html
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from common import CONFIG, fmt, send_telegram
from weekly import access_token, load_oauth, query

KST = timezone(timedelta(hours=9))
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
AGE_LABELS = {
    "age13-17": "13-17", "age18-24": "18-24", "age25-34": "25-34",
    "age35-44": "35-44", "age45-54": "45-54", "age55-64": "55-64",
    "age65-": "65+",
}
DEVICE_LABELS = {
    "MOBILE": "모바일", "DESKTOP": "PC", "TV": "TV",
    "TABLET": "태블릿", "GAME_CONSOLE": "콘솔",
}


def esc(s):
    return html.escape(str(s or ""))


def bar(ratio, width=8):
    n = round(ratio * width)
    return "▰" * n + "▱" * (width - n)


def main():
    now = datetime.now(KST)
    client_id, client_secret, tokens = load_oauth()
    end = now.date() - timedelta(days=1)
    start = end - timedelta(days=89)

    sections = []
    for c in CONFIG["channels"]:
        tk = tokens.get(c["id"])
        if not tk:
            continue
        cid = c["id"]
        lines = [f"{c['emoji']} <b>{esc(c['name'])}</b>"]
        try:
            at = access_token(client_id, client_secret, tk["refresh_token"])

            # 요일별 조회 분포 (90일)
            daily = query(at, cid, str(start), str(end), "views", dimensions="day")
            by_wd = defaultdict(int)
            for d, v in daily.get("rows", []):
                by_wd[date.fromisoformat(d).weekday()] += int(v)
            total = sum(by_wd.values())
            if total:
                lines.append("요일별 시청 (90일)")
                for wd in range(7):
                    r = by_wd.get(wd, 0) / total
                    lines.append(f"{WEEKDAYS[wd]} {bar(r)} {r * 100:.0f}%")
                best = sorted(range(7), key=lambda w: -by_wd.get(w, 0))[:2]
                lines.append(
                    f"💡 시청 많은 요일: <b>{WEEKDAYS[best[0]]}·{WEEKDAYS[best[1]]}</b>"
                    " — 전날 저녁이나 당일 오전 업로드 추천"
                )
            else:
                lines.append("최근 90일 시청 데이터 없음")

            # 연령/성별 (조회 비율)
            try:
                demo = query(at, cid, str(start), str(end), "viewerPercentage",
                             dimensions="ageGroup,gender")
                by_age, by_gender = defaultdict(float), defaultdict(float)
                for age, gender, p in demo.get("rows", []):
                    by_age[age] += float(p)
                    by_gender[gender] += float(p)
                if by_age:
                    top_ages = sorted(by_age.items(), key=lambda x: -x[1])[:3]
                    lines.append("연령: " + " · ".join(
                        f"{AGE_LABELS.get(a, a)} {p:.0f}%" for a, p in top_ages))
                    m, f_ = by_gender.get("male", 0), by_gender.get("female", 0)
                    lines.append(f"성별: 남 {m:.0f}% · 여 {f_:.0f}%")
            except Exception:
                pass

            # 기기
            try:
                dev = query(at, cid, str(start), str(end), "views",
                            dimensions="deviceType", sort="-views")
                rows = dev.get("rows", [])
                dev_total = sum(int(r[1]) for r in rows) or 1
                if rows:
                    lines.append("기기: " + " · ".join(
                        f"{DEVICE_LABELS.get(r[0], r[0])} {int(r[1]) * 100 // dev_total}%"
                        for r in rows[:3]))
            except Exception:
                pass
        except Exception as e:
            lines.append(f"조회 실패 ({esc(e)})")
        sections.append("\n".join(lines))

    header = (f"🗓 <b>월간 시청 패턴</b> (최근 90일, "
              f"{start.month}/{start.day}~{end.month}/{end.day})")
    send_telegram(header + "\n\n" + "\n\n".join(sections))
    print(f"[{now.isoformat()}] 월간 패턴 리포트 전송 완료")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            send_telegram(f"⚠️ 월간 패턴 리포트 실행 실패: {esc(e)}")
        except Exception:
            pass
        print(f"실패: {e}", file=sys.stderr)
        raise
