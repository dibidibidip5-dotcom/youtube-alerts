#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""유튜브 애널리틱스용 OAuth 토큰 발급 헬퍼 (로컬에서 1회 실행).

채널 수만큼 브라우저 인증을 반복한다. 매번 다른 채널(브랜드 계정)을
선택해 승인하면, 토큰이 어느 채널 것인지 자동으로 판별해 저장한다.
결과: oauth_tokens.json (git에 올라가지 않음)

사용법: python get_tokens.py
        (config.json의 oauth_client_id / oauth_client_secret을 읽는다.
         인자로 직접 줄 수도 있지만, 비밀값이 화면에 남으므로 권장하지 않는다.)
"""
import json
import sys
import webbrowser
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# 윈도우 기본 콘솔 인코딩(cp949)에서 한글·기호 출력이 죽지 않도록
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).resolve().parent
PORT = 8400
REDIRECT = f"http://localhost:{PORT}/"
SCOPES = " ".join([
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",  # 채널·영상 읽기 전용
])


def wait_for_code():
    """localhost 콜백으로 돌아오는 인증 코드를 기다린다."""
    result = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result["code"] = q.get("code", [None])[0]
            result["error"] = q.get("error", [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            msg = "인증 완료! 터미널로 돌아가세요." if result.get("code") else f"실패: {result.get('error')}"
            self.wfile.write(f"<h2>{msg}</h2>".encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("localhost", PORT), H)
    while "code" not in result and "error" not in result:
        srv.handle_request()
    srv.server_close()
    if not result.get("code"):
        raise SystemExit(f"인증 거부됨: {result.get('error')}")
    return result["code"]


def post_json(url, data):
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def get_json(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def load_client():
    """인자로 주면 그걸, 아니면 config.json에서 읽는다."""
    if len(sys.argv) == 3:
        return sys.argv[1], sys.argv[2]
    cfg_file = BASE / "config.json"
    if cfg_file.exists():
        cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
        cid, sec = cfg.get("oauth_client_id"), cfg.get("oauth_client_secret")
        if cid and sec:
            return cid, sec
    raise SystemExit("MISSING: config.json에 oauth_client_id / oauth_client_secret 이 없습니다.")


def main():
    client_id, client_secret = load_client()
    channels = json.loads((BASE / "channels.json").read_text(encoding="utf-8"))
    out_file = BASE / "oauth_tokens.json"
    tokens = json.loads(out_file.read_text(encoding="utf-8")) if out_file.exists() else {}

    remaining = [c for c in channels if c["id"] not in tokens]
    print(f"TODO {len(remaining)}: {', '.join(c['name'] for c in remaining)}")

    while remaining:
        names = ", ".join(c["name"] for c in remaining)
        print(f"\n브라우저가 열립니다. [{names}] 중 하나의 채널 계정을 선택해 승인하세요.")
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": SCOPES,
            "access_type": "offline",
            "prompt": "consent select_account",
        })
        webbrowser.open(auth_url)
        code = wait_for_code()

        tok = post_json("https://oauth2.googleapis.com/token", {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        })
        me = get_json(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            tok["access_token"],
        )
        items = me.get("items", [])
        if not items:
            print("RETRY: 이 계정엔 채널이 없습니다. 다시 시도하세요.")
            continue
        cid, title = items[0]["id"], items[0]["snippet"]["title"]
        match = next((c for c in channels if c["id"] == cid), None)
        if not match:
            print(f"RETRY: 선택한 채널({title})은 대상 목록에 없습니다. 다른 채널로 다시 승인하세요.")
            continue
        if cid in tokens:
            print(f"RETRY: {match['name']}은(는) 이미 발급됨. 남은 채널로 승인하세요.")
            continue
        tokens[cid] = {"refresh_token": tok["refresh_token"], "name": match["name"]}
        out_file.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
        remaining = [c for c in channels if c["id"] not in tokens]
        print(f"OK {match['name']} 토큰 저장. 남은 채널 {len(remaining)}")

    print(f"DONE {len(channels)} 채널 모두 완료")


if __name__ == "__main__":
    main()
