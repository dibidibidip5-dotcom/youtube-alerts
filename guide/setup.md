# 세팅 절차 (에이전트용)

이 순서대로 하세요. **건너뛰지 말고, 한 단계씩 확인하고 넘어갑니다.**

사람에게는 결과와 부탁할 일만 말하세요. 경로·파일명·명령어는 보여주지 않습니다.
예외는 **로그인처럼 사람이 직접 해야 하는 것** 하나뿐입니다.

## 시작 전에 먼저 읽을 것

- 수강생은 **윈도우**를 씁니다. 셸은 **파워셸**일 가능성이 높습니다.
  `&&`로 명령을 잇지 마세요(파워셸 5.1에서 문법 오류). **한 줄에 한 명령**입니다.
  `<` 리다이렉트도 쓰지 마세요. 파이프(`|`)는 됩니다.
- 파이썬 실행은 윈도우에서 `python`, 맥에서 `python3`입니다. 먼저 어느 쪽인지 확인하세요.
- **이어서 하는 경우**: 사람이 "이어서 세팅해줘"라고 하거나 대화가 끊겼다 다시 시작했으면,
  아래 **"어디까지 했는지 알아내기"**부터 보고 남은 단계만 하세요. 처음부터 다시 시키지 마세요.

## 어디까지 했는지 알아내기

| 확인 | 됐으면 |
|---|---|
| `python setup.py 점검` 출력 | `MISSING`으로 나온 것만 채우면 됩니다 |
| `gh auth status` | 깃허브 로그인 끝 (6단계 일부 완료) |
| `git remote -v` 에 origin 있음 | 저장소 만들기 끝 |
| `gh secret list` | 들어 있는 열쇠는 다시 안 넣어도 됩니다 |
| `oauth_tokens.json` 있음 | 구글 승인 끝 (10단계 완료) |

---

## 0단계 — 준비물 확인

에이전트가 직접 확인합니다. 없으면 설치합니다. **한 줄에 하나씩** 실행하세요.

```
winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
```
```
winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
```
```
winget install --id GitHub.cli -e --accept-source-agreements --accept-package-agreements
```

(맥이면 `brew install python git gh`)

> **설치한 게 있으면 새 PATH가 지금 창에 안 잡힙니다.** 두 가지 중 하나로 넘어가세요.
> - 전체 경로로 부른다. 파워셸은 경로 앞에 `&`가 있어야 실행합니다.
>   `& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" setup.py 점검`
>   (관리자 권한으로 설치됐으면 `& "C:\Program Files\Python312\python.exe" ...`,
>   Git Bash로 돌고 있으면 `"$LOCALAPPDATA/Programs/Python/Python312/python.exe" ...`)
> - 사람에게 이렇게 부탁한다: "프로그램을 깔았습니다. 클로드를 껐다가 다시 켠 뒤
>   **'이어서 세팅해줘'** 라고 말씀해 주세요." → 다시 시작하면 위 표로 진행 상태를 복원합니다.

---

## 1단계 — 텔레그램 봇 만들기

사람이 해야 합니다. 이렇게 부탁하세요.

> 텔레그램을 열고 검색창에 **BotFather** 를 치세요.
> 파란 체크가 붙은 계정에 들어가서 **시작**을 누르고, `/newbot` 이라고 보내세요.
> 봇 이름을 물어보면 아무거나(예: 내 채널 알림), 아이디를 물어보면 `bot`으로 끝나는
> 영어 이름을 지으세요. 다 하면 긴 글자열을 하나 줍니다. **그걸 저에게 붙여넣어 주세요.**

받은 열쇠를 `config.json`의 `telegram_bot_token`에 저장합니다.
파일이 없으면 새로 만듭니다. 생김새는 이렇습니다.

```json
{
  "youtube_api_key": "",
  "telegram_bot_token": "",
  "telegram_chat_id": ""
}
```

이 파일은 깃허브에 올라가지 않게 막혀 있습니다. **절대 커밋하지 마세요.**

---

## 2단계 — 내 채팅방 찾기

사람에게 부탁하세요.

> 방금 만든 봇을 텔레그램에서 찾아서 **시작**을 누르고, 아무 말이나 한마디 보내세요.

그다음 에이전트가 실행합니다.

```
python setup.py 채팅방
```

`OK 채팅방 저장`이 나오면 다음으로 갑니다.
`MISSING`이 나오면 사람이 아직 말을 안 보낸 것입니다. 한 번 더 부탁하세요.

---

## 3단계 — 유튜브 열쇠 받기

사람이 화면에서 눌러야 합니다. 한 번에 하나씩 부탁하세요.

1. **https://console.cloud.google.com/projectcreate** 를 열고 아무 이름이나 적고 **만들기**
2. **화면 맨 위에 방금 만든 프로젝트 이름이 보이는지 확인**하세요. 다른 이름이면 눌러서 바꿉니다.
   (제미나이 등으로 만든 프로젝트가 이미 있으면 엉뚱한 곳에 열쇠를 만들게 됩니다.)
3. **https://console.cloud.google.com/apis/library/youtube.googleapis.com** 를 열고 **사용** 누르기
4. **https://console.cloud.google.com/apis/credentials** 를 열고
   위쪽 **사용자 인증 정보 만들기** → **API 키**
5. 나온 열쇠를 **에이전트에게 붙여넣기**

> 구글 클라우드는 처음 들어가면 약관 동의와 나라 선택을 물어봅니다. 사람이 직접 누르게 하세요.
> 돈은 들지 않습니다. 카드 등록도 필요 없습니다.

받은 열쇠를 `config.json`의 `youtube_api_key`에 저장합니다.

---

## 4단계 — 내 채널 넣기

사람에게 부탁하세요.

> 알림을 받고 싶은 유튜브 채널 주소를 알려주세요. 여러 개면 다 알려주세요.
> (`youtube.com/@이름` 처럼 @가 붙은 주소가 제일 확실합니다.)

주소든 `@이름`이든 받아서 에이전트가 실행합니다.

```
python setup.py 채널 @핸들1 @핸들2
```

찾은 채널 이름을 사람에게 보여주고 **맞는지 확인**받으세요. 아니면 다시 물어봅니다.
이 명령은 기존 채널을 지우지 않고 **새 것만 덧붙입니다.** 나중에 채널을 더 넣을 때도 같습니다.

---

## 5단계 — 여기까지 확인

```
python setup.py 점검
```
```
python setup.py 시험
```

사람에게 "텔레그램에 메시지 왔나요?" 하고 물어보세요.
**왔다고 확인받기 전에는 다음으로 넘어가지 마세요.**

---

## 6단계 — 깃허브에 올리기

깃허브가 대신 실행해 주기 때문에, 올려야 알림이 자동으로 옵니다.

깃허브 계정이 없으면 사람에게 부탁하세요.

> **https://github.com/signup** 에서 계정을 만드세요. 무료입니다.
> 메일로 온 인증 번호까지 넣어야 끝납니다. 다 되면 알려주세요.

`gh auth status`로 로그인 여부를 확인하고, 안 돼 있으면 사람에게 부탁하세요.
**이것만 명령어를 보여줍니다.**

> 윈도우 검색창에 **PowerShell**을 치고 열어서, 아래 한 줄을 붙여넣고 엔터를 누르세요.
> 물어보는 것이 나오면 **엔터**, 브라우저가 열리면 로그인하고, 터미널에 나온
> 여덟 자리 코드를 브라우저에 넣으면 됩니다.
> `gh auth login -h github.com -p https -w`

로그인이 되면 에이전트가 이어서 합니다. **한 줄에 하나씩** 실행하세요.

```
git init
```
```
git branch -M main
```

커밋하는 사람 정보가 없으면 실패합니다. 깃허브 계정에서 두 값을 받아 에이전트가 조립합니다.

```
gh api user --jq .id
```
```
gh api user --jq .login
```

메일 주소는 `<번호>+<아이디>@users.noreply.github.com` 형태로 직접 만들어 넣습니다.
(깃허브가 주는 가짜 주소라 실제 메일이 공개되지 않습니다.)

```
git config user.email "<번호>+<아이디>@users.noreply.github.com"
```
```
git config user.name "<아이디>"
```
```
git add -A
```
```
git commit -m "유튜브 알림 세팅"
```

저장소는 **공개**로 만듭니다(무료 실행 시간이 넉넉하고, 8단계에서 필요합니다).
열쇠는 저장소에 들어가지 않으니 공개해도 안전합니다.

```
gh repo create youtube-alerts --public --source=. --push
```

그다음 열쇠 세 개를 깃허브에 넣습니다. **파일이 아니라 Secrets에 넣습니다.**
값을 화면에 찍지 마세요.

```
python -c "import json;print(json.load(open('config.json'))['youtube_api_key'],end='')" | gh secret set YT_API_KEY
```
```
python -c "import json;print(json.load(open('config.json'))['telegram_bot_token'],end='')" | gh secret set TG_BOT_TOKEN
```
```
python -c "import json;print(json.load(open('config.json'))['telegram_chat_id'],end='')" | gh secret set TG_CHAT_ID
```

---

## 7단계 — 진짜 오는지 확인

```
gh workflow run daily-report.yml
```

방금 올린 직후라 "not found"가 날 수 있습니다. 그러면 10초쯤 뒤 한 번 더 실행하세요.

```
gh run list --workflow=daily-report.yml --limit 1
```

실패면 위에서 나온 **실행 번호**로 로그를 읽어 고치세요. 번호 없이는 실행되지 않습니다.

```
gh run view <실행번호> --log-failed
```

사람에게 "텔레그램에 채널 현황 왔나요?" 하고 물어봅니다. 왔으면 **기본 세팅 끝입니다.**

사람에게 이렇게 알려주세요.

> 이제 매일 아침 9시에 구독자·조회수가 오고, 낮 동안 한 시간마다 새 댓글과
> 급상승을 알려줍니다. 컴퓨터를 꺼도 옵니다.

그리고 **구글 승인을 할지 물어보세요.**

> 여기에 더해 **예약해 둔 영상 현황과 주간·월간 시청 통계**도 받을 수 있습니다.
> 구글에 "내 채널이 맞다"를 증명하는 절차라 10분쯤 더 걸립니다. 지금 하시겠어요?

**안 한다고 하면 여기서 멈춥니다.** 그 세 가지는 조용히 건너뛰므로 그냥 두어도
실패 알림이 오지 않습니다. 나중에 "예약 영상도 알려줘"라고 하면 8단계부터 하면 됩니다.

---

# 여기부터는 선택입니다 (구글 승인)

## 8단계 — 안내 페이지 켜기

구글이 "이 앱의 개인정보처리방침 주소"를 요구합니다. 페이지는 이미 들어 있습니다.
깃허브 페이지로 켜기만 하면 됩니다. 셸마다 따옴표가 달라지므로 파일로 넘깁니다.

`pages.json`이라는 파일을 만들고 이렇게 적습니다.

```json
{ "source": { "branch": "main", "path": "/docs" } }
```

```
gh api -X POST "repos/{owner}/{repo}/pages" --input pages.json
```

주소는 추측하지 말고 확인해서 씁니다. 뜨는 데 1~2분 걸립니다.

```
gh api "repos/{owner}/{repo}/pages" --jq .html_url
```

그 주소를 실제로 열어 페이지가 보이는지 확인하고 넘어가세요.

---

## 9단계 — 구글 승인 설정

사람이 화면에서 눌러야 합니다. 한 번에 하나씩.

1. **https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com** 에서 **사용**
2. **https://console.cloud.google.com/auth/overview** 에서 **시작하기**
   - 앱 이름: 아무거나 (예: 내 채널 알림)
   - 사용자 지원 이메일: 본인 메일
   - 대상: **외부**
   - 연락처: 본인 메일
   - 마지막에 **동의 체크** — 이건 사람이 직접 누르게 하세요
3. **https://console.cloud.google.com/auth/branding** 에서 아래를 채우고 **저장**
   - 홈페이지 → 8단계 주소
   - 개인정보처리방침 → 8단계 주소 + `privacy.html`
   - 서비스 약관 → 8단계 주소 + `terms.html`
   - 승인된 도메인 → `<깃허브아이디>.github.io`
4. **https://console.cloud.google.com/auth/audience** 에서 **앱 게시** → **확인**
   - 이걸 안 하면 **7일마다 연결이 끊깁니다.** 반드시 하세요.
5. **https://console.cloud.google.com/auth/clients** 에서 **클라이언트 만들기**
   - 유형: **데스크톱 앱**
   - 나온 **클라이언트 ID**와 **보안 비밀번호**를 에이전트에게 붙여넣게 하세요
   - 받은 값을 `config.json`의 `oauth_client_id`·`oauth_client_secret`에 저장합니다

---

## 10단계 — 채널마다 허용 누르기

에이전트가 실행합니다. 채널 수만큼 브라우저가 열리고, 사람이 누르는 동안 계속 기다립니다.
**시간이 오래 걸리므로 백그라운드로 돌리고**, `oauth_tokens.json`에 채널이 다 찼는지로 완료를 확인하세요.

```
python get_tokens.py
```

사람에게 미리 알려주세요.

> 창이 뜨면 채널을 하나 고르고, **"확인하지 않은 앱"** 경고가 나오면
> **고급** → **(앱이름)으로 이동** 을 누른 뒤,
> **권한 체크박스가 보이면 전부 체크하고** **계속**을 누르세요.
> 채널 수만큼 반복됩니다. 경고는 정상입니다. 방금 만든 앱이라 구글 심사를 안 받아서 나옵니다.

`DONE`이 나오면 열쇠를 깃허브에 넣습니다. **한 줄에 하나씩.**

```
python -c "import json;print(json.load(open('config.json'))['oauth_client_id'],end='')" | gh secret set OAUTH_CLIENT_ID
```
```
python -c "import json;print(json.load(open('config.json'))['oauth_client_secret'],end='')" | gh secret set OAUTH_CLIENT_SECRET
```
```
python -c "print(open('oauth_tokens.json').read(),end='')" | gh secret set YT_OAUTH_TOKENS
```

마지막으로 한 번 돌려서 확인합니다.

```
gh workflow run scheduled-report.yml
```

---

## 막혔을 때

| 증상 | 까닭과 조치 |
|---|---|
| 유튜브 열쇠가 `FAIL` | 3단계에서 YouTube Data API v3를 안 켰거나, 다른 프로젝트에 켰습니다 |
| 채팅방이 `MISSING` | 사람이 봇에게 아직 말을 안 걸었습니다 |
| `python`을 못 찾음 | 방금 설치했다면 클로드를 껐다 켜야 합니다(0단계 참고) |
| `&&`에서 문법 오류 | 파워셸입니다. 한 줄에 하나씩 실행하세요 |
| 커밋이 `Author identity unknown` | 6단계의 이름·메일 설정을 건너뛰었습니다 |
| 깃허브 페이지가 422 | 브랜치가 `main`이 아닙니다. `git branch -M main` 후 다시 |
| 깃허브 실행이 실패 | `gh run list`로 실행 번호를 보고 `gh run view <번호> --log-failed` |
| 주간 통계만 "토큰 없음" | 그 채널은 10단계에서 허용을 안 눌렀습니다 |
| 주간 통계가 403 | 승인 화면의 권한 체크박스를 안 눌렀습니다. 10단계를 다시 |
| 7일 뒤 갑자기 끊김 | 9단계 4번(앱 게시)을 안 했습니다 |
