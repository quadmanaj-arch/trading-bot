import os, json, base64, urllib.request, urllib.parse, urllib.error

KEY   = os.environ['ALPACA_KEY']
SEC   = os.environ['ALPACA_SECRET']
PTOK  = os.environ['PUSHOVER_TOKEN']
PUSER = os.environ['PUSHOVER_USER']
GTOK  = os.environ['GH_TOKEN']

TRADE = 'https://paper-api.alpaca.markets/v2'
DATA  = 'https://data.alpaca.markets/v2'
JOURNAL_URL = 'https://api.github.com/repos/quadmanaj-arch/journal-/contents/journal.md'

ALP_HDR = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SEC}
GH_HDR  = {'Authorization': f'Bearer {GTOK}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}

def alp_get(path, base=None):
    base = base or TRADE
    r = urllib.request.urlopen(urllib.request.Request(base + path, headers=ALP_HDR))
    return json.loads(r.read())

def alp_post(path, body, method='POST'):
    req = urllib.request.Request(
        TRADE + path,
        data=json.dumps(body).encode(),
        headers={**ALP_HDR, 'Content-Type': 'application/json'},
        method=method
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'msg': e.read().decode()}

def alp_delete(path):
    try:
        req = urllib.request.Request(TRADE + path, headers=ALP_HDR, method='DELETE')
        urllib.request.urlopen(req)
    except Exception as e:
        print(f'DELETE {path} failed: {e}')

def pushover(title, msg, priority=0):
    data = urllib.parse.urlencode({
        'token': PTOK, 'user': PUSER,
        'title': title[:250], 'message': str(msg)[:1000],
        'priority': str(priority)
    }).encode()
    r = urllib.request.urlopen(urllib.request.Request('https://api.pushover.net/1/messages.json', data=data))
    result = json.loads(r.read())
    print(f'Pushover [{title}]: status={result.get("status")}')
    return result

def journal_append(entry, commit_msg='Bot update'):
    req = urllib.request.Request(JOURNAL_URL, headers=GH_HDR)
    with urllib.request.urlopen(req) as r:
        d = json.loads(r.read())
    sha = d['sha']
    content = base64.b64decode(d['content']).decode() + entry
    payload = json.dumps({
        'message': commit_msg,
        'content': base64.b64encode(content.encode()).decode(),
        'sha': sha,
        'committer': {'name': 'Trading Bot', 'email': 'quadmanaj@gmail.com'}
    }).encode()
    req2 = urllib.request.Request(JOURNAL_URL, data=payload, headers={**GH_HDR, 'Content-Type': 'application/json'}, method='PUT')
    with urllib.request.urlopen(req2) as r:
        return json.loads(r.read())
