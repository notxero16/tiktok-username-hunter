import json,re,time,random,threading,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlparse

PORT=int(os.environ.get("PORT","8000"))
HOME="https://www.tiktok.com"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
RE=re.compile(r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',re.S)
NOT_FOUND={10202,10221,10222,10223,10224}
LOCK=threading.Lock()
LAST=0.0
DELAY=1.5

def valid(s):
    if not isinstance(s,str): return "Enter a username."
    s=s.strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9._]{2,24}",s): return "Use 2–24 letters, numbers, periods or underscores."
    if s.endswith("."): return "A username can't end with a period."
    return None

def fetch(name):
    global LAST
    with LOCK:
        wait=DELAY-(time.monotonic()-LAST)
        if wait>0: time.sleep(wait)
        LAST=time.monotonic()
        req=Request(f"{HOME}/@{name}",headers={"User-Agent":UA,"Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"})
        try:
            with urlopen(req,timeout=12) as r: page=r.read(3000000).decode("utf-8","replace")
        except HTTPError as e:
            return "unknown",f"TikTok HTTP {e.code}; not proof of availability."
        except Exception as e:
            return "unknown","Request failed: "+type(e).__name__
    m=RE.search(page)
    if not m: return "unknown","TikTok did not return the expected profile data."
    try:
        data=json.loads(m.group(1)); detail=data.get("__DEFAULT_SCOPE__",{}).get("webapp.user-detail",{})
        info=detail.get("userInfo")
        if isinstance(info,dict) and isinstance(info.get("user"),dict):
            return "taken",info["user"].get("nickname") or "Account found"
        if detail.get("statusCode") in NOT_FOUND: return "not_found","TikTok profile says not found."
        return "unknown","Unclear TikTok response."
    except Exception: return "unknown","TikTok profile data could not be read."

def check(name):
    problem=valid(name)
    if problem:return {"username":str(name),"status":"invalid","detail":problem}
    name=name.strip().lstrip("@")
    a,detail=fetch(name)
    url=f"{HOME}/@{name}"
    if a=="taken":return {"username":name,"status":"taken","detail":detail,"url":url}
    if a!="not_found":return {"username":name,"status":"unknown","detail":detail,"url":url}
    b,detail2=fetch(name)
    if b=="not_found":return {"username":name,"status":"available","detail":"Two separate not-found responses. TikTok may still reserve the handle.","double_checked":True,"url":url}
    if b=="taken":return {"username":name,"status":"taken","detail":detail2,"url":url}
    return {"username":name,"status":"unknown","detail":"First check looked free, but confirmation was inconclusive.","url":url}

def candidates(d):
    mn=max(2,min(24,int(d.get("min",3)))); mx=max(mn,min(24,int(d.get("max",4))))
    count=max(1,min(40,int(d.get("count",20))))
    letters="abcdefghijklmnopqrstuvwxyz"; cons="bcdfghjklmnpqrstvwxyz"; vows="aeiou"
    seeds=["vex","hdy","qio","zay","kio","nvy","jex","ryo","vyn","kye","zyo","luz","nyx","avi","eko","ixo","qev","jio"]
    rng=random.SystemRandom(); out=[]; seen=set()
    def okay(s):
        if not mn<=len(s)<=mx:return False
        if not d.get("numbers") and any(c.isdigit() for c in s):return False
        if not d.get("underscores") and "_" in s:return False
        if not d.get("periods") and "." in s:return False
        if d.get("repeats",True) and any(s[i]==s[i-1] for i in range(1,len(s))):return False
        return True
    if d.get("style")!="random":
        for s in seeds:
            if okay(s) and s not in seen:seen.add(s);out.append(s)
    tries=0
    while len(out)<count and tries<count*150:
        tries+=1;n=rng.randint(mn,mx);chars=[]
        for i in range(n):
            if d.get("numbers") and rng.random()<.025:chars.append(rng.choice("0123456789"))
            else:chars.append(rng.choice(vows if i%2 else cons))
        s="".join(chars)
        if d.get("underscores") and rng.random()<.015 and len(s)>2:
            p=rng.randrange(1,len(s));s=s[:p]+"_"+s[p:]
        elif d.get("periods") and rng.random()<.015 and len(s)>2:
            p=rng.randrange(1,len(s));s=s[:p]+"."+s[p:]
        if okay(s) and s not in seen:seen.add(s);out.append(s)
    rng.shuffle(out)
    return out[:count]

class Handler(BaseHTTPRequestHandler):
    def send_json(self,code,obj,ctype="application/json; charset=utf-8"):
        raw=obj.encode() if isinstance(obj,str) else json.dumps(obj).encode()
        self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/":self.send_json(200,HTML,"text/html; charset=utf-8")
        elif path=="/health":self.send_json(200,{"ok":True})
        else:self.send_json(404,{"error":"not found"})
    def do_POST(self):
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n>10000:return self.send_json(413,{"error":"too large"})
            d=json.loads(self.rfile.read(n) or b"{}")
        except Exception:return self.send_json(400,{"error":"invalid JSON"})
        p=urlparse(self.path).path
        if p=="/api/check":return self.send_json(200,check(d.get("username","")))
        if p=="/api/candidates":
            try:return self.send_json(200,{"names":candidates(d)})
            except Exception:return self.send_json(400,{"error":"invalid filters"})
        self.send_json(404,{"error":"not found"})
    def log_message(self,fmt,*args):
        return

HTML = open(os.path.join(os.path.dirname(__file__), "index.html"), encoding="utf-8").read()

if __name__=="__main__":
    print("TikTok Username Hunter listening on",PORT)
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
