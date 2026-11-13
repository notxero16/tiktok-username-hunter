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

HTML = r'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#09090f"><title>TikTok Username Hunter</title>\n<style>\n*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at top,#241744,#09090f 55%);color:#f7f4ff;font:15px system-ui,sans-serif;min-height:100vh}main{max-width:720px;margin:auto;padding:25px 15px 50px}.brand{font-weight:800;letter-spacing:1px;color:#c6b5ff;margin-bottom:24px}h1{font-size:36px;line-height:1.05;margin:0 0 8px}.muted{color:#aaa6bd;line-height:1.5}.panel{background:#151520;border:1px solid #302d40;border-radius:18px;padding:17px;margin-top:20px}.tabs{display:flex;gap:8px;margin-bottom:18px}.tab,button{border:0;border-radius:11px;padding:12px 15px;color:white;background:#30264c;font-weight:700;cursor:pointer}.tab{background:#222131}.tab.active{background:#6247a6}.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}label{display:block;font-weight:650;margin:12px 0 7px}select,input{width:100%;padding:12px;border:1px solid #39364c;border-radius:10px;background:#0e0e17;color:white;font:inherit}.checks{display:flex;flex-wrap:wrap;gap:12px;margin-top:14px}.checks label{display:flex;align-items:center;gap:6px;margin:0;font-weight:500}.checks input{width:auto;accent-color:#9b7bff}button.primary{width:100%;margin-top:17px;background:linear-gradient(100deg,#9c7aff,#704bd3)}button:disabled{opacity:.5}.small{font-size:12px;color:#aaa6bd;line-height:1.5}.bar{height:7px;background:#2c293b;border-radius:10px;margin-top:8px;overflow:hidden}.bar i{display:block;height:100%;width:0;background:#8d70ff}.stat{display:flex;justify-content:space-between;color:#aaa6bd;font-size:13px;margin-top:14px}.result{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:12px;background:#101019;border:1px solid #302d40;border-radius:12px;margin-top:9px}.name{font-weight:800}.result a{display:block;color:#c8baff;font-size:12px;margin-top:4px;text-decoration:none}.pill{font-size:11px;font-weight:800;padding:5px 8px;border-radius:20px}.available{background:#16392d;color:#55dfa6}.taken{background:#401e29;color:#ff8290}.unknown{background:#40371c;color:#f5d078}.notice{padding:12px;border:1px solid #4b3e70;background:#211a34;border-radius:12px;margin-top:18px;font-size:12px;color:#d7cff1;line-height:1.5}@media(max-width:440px){h1{font-size:31px}.panel{padding:14px}}\n</style></head><body><main><div class="brand">＠ USERNAME HUNTER</div><h1>Find your next username.</h1><p class="muted">Choose your filters and let the hunter check TikTok profile data for possible available handles.</p>\n<div class="panel"><div class="tabs"><button class="tab active" id="tabAuto" onclick="tab(\'auto\')">Automatic hunter</button><button class="tab" id="tabManual" onclick="tab(\'manual\')">Check a name</button></div>\n<section id="auto"><div class="grid"><div><label>Minimum length</label><select id="min"><option>2</option><option selected>3</option><option>4</option><option>5</option></select></div><div><label>Maximum length</label><select id="max"><option>2</option><option>3</option><option selected>4</option><option>5</option><option>6</option></select></div><div><label>Names per search</label><select id="count"><option>10</option><option selected>20</option><option>30</option><option>40</option></select></div><div><label>Style</label><select id="style"><option value="mixed">Mixed / pronounceable</option><option value="random">Random letters</option></select></div></div>\n<div class="checks"><label><input id="numbers" type="checkbox"> Numbers</label><label><input id="underscores" type="checkbox"> Underscores</label><label><input id="periods" type="checkbox"> Periods</label><label><input id="repeats" type="checkbox" checked> Avoid repeated letters</label></div>\n<button class="primary" id="start" onclick="hunt()">Find available usernames</button><div class="stat"><span id="status">Ready</span><span id="counter">0 / 0</span></div><div class="bar"><i id="bar"></i></div><div id="results"></div></section>\n<section id="manual" style="display:none"><label>Username to check</label><input id="manualName" placeholder="e.g. jghe" maxlength="25"><button class="primary" onclick="manualCheck()">Check username</button><div id="manualResult"></div></section>\n<div class="notice">Unofficial checker: reads TikTok\'s public profile page, not a private availability API. TikTok may block requests or reserve usernames. Only trying the username inside TikTok confirms whether you can claim it. Checks are deliberately paced. No login or password is needed.</div></div><p class="small">A name appears in the automatic results only after two clear not-found responses. Inconclusive checks are never marked available.</p></main>\n<script>\nlet busy=false;\nfunction tab(which){document.getElementById(\'auto\').style.display=which===\'auto\'?\'block\':\'none\';document.getElementById(\'manual\').style.display=which===\'manual\'?\'block\':\'none\';document.getElementById(\'tabAuto\').classList.toggle(\'active\',which===\'auto\');document.getElementById(\'tabManual\').classList.toggle(\'active\',which===\'manual\')}\nasync function post(path,obj){let r=await fetch(path,{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify(obj)});if(!r.ok)throw Error(\'Server error \'+r.status);return r.json()}\nfunction addResult(el,r){let row=document.createElement(\'div\');row.className=\'result\';let left=document.createElement(\'div\'),name=document.createElement(\'div\'),a=document.createElement(\'a\'),pill=document.createElement(\'span\');name.className=\'name\';name.textContent=\'@\'+r.username;a.href=r.url||\'https://www.tiktok.com/@\'+r.username;a.target=\'_blank\';a.rel=\'noopener\';a.textContent=\'Open TikTok profile ↗\';left.append(name,a);pill.className=\'pill \'+(r.status===\'available\'?\'available\':r.status===\'taken\'?\'taken\':\'unknown\');pill.textContent=r.status.toUpperCase();row.append(left,pill);el.append(row)}\nasync function hunt(){if(busy)return;let min=+document.getElementById(\'min\').value,max=+document.getElementById(\'max\').value;if(min>max){alert(\'Minimum length must not exceed maximum.\');return}busy=true;let btn=document.getElementById(\'start\'),out=document.getElementById(\'results\'),status=document.getElementById(\'status\'),counter=document.getElementById(\'counter\'),bar=document.getElementById(\'bar\');btn.disabled=true;btn.textContent=\'Searching…\';out.innerHTML=\'\';bar.style.width=\'0%\';\ntry{let x=await post(\'/api/candidates\',{min,max,count:+document.getElementById(\'count\').value,numbers:document.getElementById(\'numbers\').checked,underscores:document.getElementById(\'underscores\').checked,periods:document.getElementById(\'periods\').checked,repeats:document.getElementById(\'repeats\').checked,style:document.getElementById(\'style\').value});counter.textContent=\'0 / \'+x.names.length;\nfor(let i=0;i<x.names.length;i++){let r=await post(\'/api/check\',{username:x.names[i]});counter.textContent=(i+1)+\' / \'+x.names.length;bar.style.width=((i+1)/x.names.length*100)+\'%\';status.textContent=\'Checking @\'+x.names[i];if(r.status===\'available\')addResult(out,r)}\nif(!out.children.length){out.innerHTML=\'<p class="small">No confirmed available names in this batch. Try another search later.</p>\'}status.textContent=\'Finished — only double-checked names are shown.\'}\ncatch(e){status.textContent=\'Could not check: \'+e.message;out.innerHTML=\'<p class="small">The backend may be offline or TikTok may be blocking requests.</p>\'}\nfinally{busy=false;btn.disabled=false;btn.textContent=\'Find available usernames\'}}\nasync function manualCheck(){let out=document.getElementById(\'manualResult\');out.innerHTML=\'<p class="small">Checking…</p>\';try{let r=await post(\'/api/check\',{username:document.getElementById(\'manualName\').value});out.innerHTML=\'\';addResult(out,r)}catch(e){out.innerHTML=\'<p class="small">Check failed: \'+e.message+\'</p>\'}}\n</script></body></html>'

if __name__=="__main__":
    print("TikTok Username Hunter listening on",PORT)
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
