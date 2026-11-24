"""AI Tools Usage Among College Students - live dashboard fed by Google Forms.
Respondents fill the Google Form -> answers land in the linked Google Sheet -> this app reads the
Sheet (published as CSV) and shows live charts.

Run:  python -m pip install -r requirements.txt && python dashboard.py
Env:  SHEET_CSV_URL (required), FORM_URL, ADMIN_PASSWORD, SECRET_KEY, PORT
"""
import csv, hmac, io, os, secrets, time, urllib.request
from functools import wraps
from flask import Flask, jsonify, redirect, render_template_string, request, session, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SHEET_CSV_URL = os.environ.get("SHEET_CSV_URL", "")
FORM_URL = os.environ.get("FORM_URL", "#")

SECTIONS = ["Background", "Usage habits", "Attitudes & experience", "Policy & concerns"]
LIKERT = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
# k: s = single choice, m = multiple choice, l = 1-5 scale, t = free text
QS = [
    {"s": 0, "k": "s", "t": "What is your current year of study?", "o": ["1st year", "2nd year", "3rd year", "4th year", "Postgraduate"]},
    {"s": 0, "k": "s", "t": "Which field best describes your course?", "o": ["Engineering / IT", "Science", "Commerce / Management", "Arts / Humanities", "Medical / Health", "Other"]},
    {"s": 1, "k": "s", "t": "How often do you use AI tools for college work?", "o": ["Daily", "A few times a week", "About once a week", "Rarely", "Never"]},
    {"s": 1, "k": "m", "t": "Which AI tools have you used? (select all)", "o": ["ChatGPT", "Google Gemini", "Claude", "Microsoft Copilot", "Perplexity", "Grammarly / QuillBot", "Canva / image AI", "Other"]},
    {"s": 1, "k": "m", "t": "What do you mainly use AI for? (select all)", "o": ["Assignments & writing", "Coding & debugging", "Research & reading", "Summarising notes", "Exam preparation", "Language help", "Creative projects", "Career & resumes"]},
    {"s": 1, "k": "s", "t": "Roughly how many hours per week do you spend on AI tools?", "o": ["Under 1", "1–3", "3–7", "7–14", "More than 14"]},
    {"s": 1, "k": "s", "t": "Which plan do you use?", "o": ["Free plans only", "I pay for a subscription", "Provided by my institution"]},
    {"s": 1, "k": "s", "t": "How did you first learn about AI tools?", "o": ["Friends / classmates", "Social media", "College / faculty", "Own searching", "Other"]},
    {"s": 1, "k": "s", "t": "How often do you fact-check AI outputs?", "o": ["Always", "Often", "Sometimes", "Never"]},
    {"s": 2, "k": "l", "t": "AI tools have improved my academic performance."},
    {"s": 2, "k": "l", "t": "AI tools save me significant time."},
    {"s": 2, "k": "l", "t": "I trust the accuracy of AI-generated answers."},
    {"s": 2, "k": "l", "t": "I worry I rely on AI too much."},
    {"s": 2, "k": "l", "t": "Colleges should officially allow AI tools in coursework."},
    {"s": 3, "k": "s", "t": "Does your college have an AI-use policy?", "o": ["Yes, and it is clear", "Yes, but it is unclear", "No policy", "I don’t know"]},
    {"s": 3, "k": "s", "t": "What is your biggest concern about AI in education?", "o": ["Inaccurate information", "Plagiarism / cheating", "Loss of critical thinking", "Data privacy", "Cost / access inequality", "No major concern"]},
    {"s": 3, "k": "t", "t": "How could your college better support responsible AI use? (optional)"},
]

CSS = """*{box-sizing:border-box}body{margin:0;background:#f5f6f8;color:#14213d;font:15px/1.5 Inter,system-ui,Arial,sans-serif}
.w{max-width:820px;margin:0 auto;padding:18px 14px 60px}.wd{max-width:1100px}
header{background:#fff;border:1px solid #e1e5ec;border-top:4px solid #2f5bea;border-radius:12px;padding:20px;margin-bottom:14px}
h1{font-size:22px;margin:4px 0 6px}h2{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#2f5bea;margin:24px 0 8px}h3{font-size:15px;margin:0 0 10px}
.mu{color:#5b6578;font-size:13px}.card{background:#fff;border:1px solid #e1e5ec;border-radius:12px;padding:16px;margin-bottom:12px}.card.err{border-color:#d33}
.opt{display:flex;gap:10px;align-items:center;padding:8px 10px;border:1px solid #e1e5ec;border-radius:8px;margin:6px 0;cursor:pointer}.opt:has(input:checked){background:#e8eeff;border-color:#2f5bea}
.lk{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}.lk label{text-align:center;border:1px solid #e1e5ec;border-radius:8px;padding:8px 2px;font-size:12px;cursor:pointer}
.lk label:has(input:checked){background:#2f5bea;color:#fff}.lk input{position:absolute;opacity:0}
textarea,input[type=password]{width:100%;border:1px solid #e1e5ec;border-radius:8px;padding:10px;font:inherit}textarea{min-height:90px}
button,.btn{background:#2f5bea;color:#fff;border:0;border-radius:8px;padding:11px 22px;font:600 14px Arial;cursor:pointer;text-decoration:none;display:inline-block}.btn.g{background:#fff;color:#14213d;border:1px solid #e1e5ec}
.pb{position:sticky;top:0;height:6px;background:#e1e5ec;border-radius:3px;margin-bottom:14px;z-index:5}.pb i{display:block;height:100%;background:#2f5bea;border-radius:3px;width:0;transition:width .3s}
.top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px}
.kp{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.kp .card{margin:0}.kp b{display:block;font-size:30px}
.gr{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:12px}@media(max-width:520px){.gr{grid-template-columns:1fr}}
.br{display:grid;grid-template-columns:minmax(90px,38%) 1fr 62px;gap:8px;align-items:center;margin:5px 0;font-size:13px}
.br .t{height:14px;background:#e1e5ec;border-radius:7px;overflow:hidden}.br .t i{display:block;height:100%;background:#2f5bea}.br span:last-child{text-align:right;color:#5b6578}
.sk{display:flex;height:22px;border-radius:6px;overflow:hidden;margin:8px 0}.sk i{display:block;font:11px/22px Arial;color:#fff;text-align:center;overflow:hidden}
.tx{border-left:3px solid #2f5bea;padding:6px 10px;margin:8px 0;background:#f5f6f8;font-size:13px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#12805c;margin-right:6px}"""

DASH_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Survey Dashboard</title><style>__CSS__</style></head>
<body><div class="w wd"><div class="top"><div><div class="mu"><span class="dot"></span>Live · refreshes every 10 seconds · <span id="upd"></span></div>
<h1 style="margin:2px 0">AI Tools Usage Among College Students</h1></div>
<div><a class="btn" href="__FORM__" target="_blank">Open survey form</a> <a class="btn g" href="/logout">Log out</a></div></div>
<div class="kp" id="kp" style="margin-top:14px"></div><h2>Question breakdown</h2><div class="gr" id="gr"></div></div>
<script>
var LB=['Strongly disagree','Disagree','Neutral','Agree','Strongly agree'],COL=['#c0392b','#e67e22','#8a93a6','#4a90d9','#2f5bea'];
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}
function body(q,n){var h='',t;
 if(q.k==='l'){t=q.counts.reduce(function(a,b){return a+b;},0)||1;
  q.counts.forEach(function(c,j){h+='<i style="width:'+(c/t*100)+'%;background:'+COL[j]+'" title="'+LB[j]+': '+c+'">'+(c?Math.round(c/t*100)+'%':'')+'</i>';});
  return '<div class="sk">'+h+'</div><div class="mu">Mean <b style="color:#14213d">'+(q.mean===null?'–':q.mean)+'</b> / 5 · 1 = strongly disagree, 5 = strongly agree</div>';}
 if(q.k==='t')return q.texts.length?q.texts.map(function(x){return '<div class="tx">'+esc(x)+'</div>';}).join(''):'<div class="mu">No comments yet.</div>';
 q.labels.forEach(function(l,j){var c=q.counts[j];h+='<div class="br"><span>'+esc(l)+'</span><div class="t"><i style="width:'+(n?c/n*100:0)+'%"></i></div><span>'+c+' · '+(n?Math.round(c/n*100):0)+'%</span></div>';});
 return h;}
function draw(d){var k=d.kpis,p=function(v){return v===null?'–':v+'%';};
 document.getElementById('kp').innerHTML=[['Total responses',d.n],['Use AI weekly or more',p(k.weekly)],['Fact-check always / often',p(k.factcheck)],['Avg. time-saving rating',(k.timesaving===null?'–':k.timesaving+' / 5')]].map(function(x){return '<div class="card"><span class="mu">'+x[0]+'</span><b>'+x[1]+'</b></div>';}).join('');
 document.getElementById('gr').innerHTML=d.questions.map(function(q,i){return '<div class="card"><div class="mu">Q'+(i+1)+' · '+esc(q.sec)+'</div><h3>'+esc(q.t)+'</h3>'+body(q,d.n)+'</div>';}).join('');
 document.getElementById('upd').textContent='updated '+new Date().toLocaleTimeString();}
function load(){fetch('/api/stats').then(function(r){if(r.status===401){location='/login';throw 0;}return r.json();}).then(function(d){if(d.error){document.getElementById('upd').textContent='Error: '+d.error;return;}draw(d);}).catch(function(){});}
load();setInterval(load,10000);
</script></body></html>""".replace("__CSS__", CSS)


# ---------- read the Google Sheet ----------
_cache = {"t": 0.0, "rows": []}

def fetch_rows():
    if time.time() - _cache["t"] < 10:          # cache 10s so refreshes don't hammer Google
        return _cache["rows"]
    if not SHEET_CSV_URL:
        raise RuntimeError("SHEET_CSV_URL is not set")
    req = urllib.request.Request(SHEET_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=20).read().decode("utf-8-sig")
    rows = [r for r in list(csv.reader(io.StringIO(text)))[1:] if r and r[0].strip()]
    _cache.update(t=time.time(), rows=rows)
    return rows

def parse(r):
    """Sheet row -> (timestamp, answers). Column 0 = Timestamp, columns 1..17 = Q1..Q17."""
    r = r + [""] * (len(QS) + 1 - len(r))
    out = []
    for i, q in enumerate(QS):
        v = r[i + 1].strip()
        if q["k"] == "m":
            out.append([x.strip() for x in v.split(",") if x.strip()])
        elif q["k"] == "l":
            out.append(int(v) if v.isdigit() and 1 <= int(v) <= 5 else None)
        else:
            out.append(v)
    return r[0], out

def stats():
    rows = [parse(r) for r in fetch_rows()]
    n = len(rows)
    out = []
    for i, q in enumerate(QS):
        vals = [a[i] for _, a in rows]
        item = {"t": q["t"], "k": q["k"], "sec": SECTIONS[q["s"]]}
        if q["k"] in ("s", "m"):
            item["labels"] = q["o"]
            item["counts"] = [sum(1 for v in vals if (o in v if q["k"] == "m" else v == o)) for o in q["o"]]
        elif q["k"] == "l":
            v = [x for x in vals if x]
            item["counts"] = [v.count(j) for j in range(1, 6)]
            item["mean"] = round(sum(v) / len(v), 2) if v else None
        else:
            item["texts"] = [x for x in vals if x][::-1][:15]
        out.append(item)
    pct = lambda f: round(100 * sum(1 for _, a in rows if f(a)) / n) if n else None
    ts = [a[10] for _, a in rows if a[10]]
    return {"n": n, "kpis": {
        "weekly": pct(lambda a: a[2] in ("Daily", "A few times a week", "About once a week")),
        "factcheck": pct(lambda a: a[8] in ("Always", "Often")),
        "timesaving": round(sum(ts) / len(ts), 1) if ts else None,
        "last": rows[-1][0] if rows else None}, "questions": out}

# ---------- pages ----------
LOGIN = """<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin login</title><style>{{css|safe}}</style></head>
<body><div class="w" style="max-width:420px"><header><h1>Dashboard login</h1>{% if err %}<p style="color:#d33">Incorrect password.</p>{% endif %}
<form method="post"><p><input type="password" name="password" placeholder="Admin password" autofocus></p><button>Sign in</button></form></header></div></body></html>"""

def admin_only(f):
    @wraps(f)
    def wrap(*a, **kw):
        if not session.get("admin"):
            if request.path.startswith("/api"):
                return jsonify(error="unauthorized"), 401
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrap

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("password", ""), ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(url_for("home"))
        return render_template_string(LOGIN, css=CSS, err=True), 401
    return render_template_string(LOGIN, css=CSS, err=False)

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/")
@admin_only
def home():
    return DASH_PAGE.replace("__FORM__", FORM_URL)

@app.get("/api/stats")
@admin_only
def api_stats():
    try:
        return jsonify(stats())
    except Exception as e:
        return jsonify(error=str(e)), 502

if __name__ == "__main__":
    if ADMIN_PASSWORD == "admin123":
        print("WARNING: using the default admin password. Set ADMIN_PASSWORD before sharing the link.")
    if not SHEET_CSV_URL:
        print("WARNING: SHEET_CSV_URL is not set - the dashboard will show an error until you set it.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
