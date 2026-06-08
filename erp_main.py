"""
Default login:  admin / admin123
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import json, os, subprocess, hashlib, glob, sys, threading
import pandas as pd
from datetime import datetime, timedelta

# ── OAuth 2.0 (optional — graceful fallback if module/deps missing) ──
try:
    from oauth_manager import (
        OAuthFlow, find_user_by_oauth,
        load_oauth_config, save_oauth_config, PROVIDERS
    )
    _OAUTH_OK = True
except ImportError:
    _OAUTH_OK = False

# ── optional PIL (avatar generation) ──────────────────────────────
try:
    from PIL import Image, ImageTk, ImageDraw
    _PIL = True
except ImportError:
    _PIL = False

# ═══════════════════════════════════════════════════════════════════
#  PATHS
# ═══════════════════════════════════════════════════════════════════
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DB_FILE        = os.path.join(BASE_DIR, "db.json")
USERS_FILE     = os.path.join(BASE_DIR, "users.json")
NOTICES_FILE     = os.path.join(BASE_DIR, "notices.json")
LEAVE_FILE       = os.path.join(BASE_DIR, "leaves.json")
TIMETABLE_FILE   = os.path.join(BASE_DIR, "timetable.json")
ASSIGNMENTS_FILE = os.path.join(BASE_DIR, "assignments.json")

# ═══════════════════════════════════════════════════════════════════
#  THEME  — supports "dark" and "light" modes
# ═══════════════════════════════════════════════════════════════════
THEMES = {
    "dark": {
        "bg":      "#161b27",
        "sidebar": "#1e2535",
        "card":    "#252e42",
        "card2":   "#2e3a52",
        "border":  "#3a4460",
        "accent":  "#f5c518",
        "accent2": "#d4a800",
        "text":    "#e8eaf0",
        "muted":   "#8892a4",
        "green":   "#3fb950",
        "red":     "#e53935",
        "blue":    "#58a6ff",
        "purple":  "#bc8cff",
        "orange":  "#ff9800",
        "hdr":     "#0f1420",
    },
    "light": {
        "bg":      "#f0f2f7",
        "sidebar": "#ffffff",
        "card":    "#ffffff",
        "card2":   "#f5f7fa",
        "border":  "#d8dce8",
        "accent":  "#c49a00",
        "accent2": "#a07800",
        "text":    "#1a1f2e",
        "muted":   "#5a6478",
        "green":   "#2e8b57",
        "red":     "#c0392b",
        "blue":    "#1a6bc0",
        "purple":  "#7b3fa0",
        "orange":  "#d4700a",
        "hdr":     "#ffffff",
    },
}

_current_theme = "dark"
C = dict(THEMES["dark"])

def set_theme(mode):
    global _current_theme, C
    _current_theme = mode
    C.update(THEMES[mode])

def toggle_theme():
    set_theme("light" if _current_theme == "dark" else "dark")

FT  = ("Segoe UI", 26, "bold")
FH  = ("Segoe UI", 16, "bold")
FSH = ("Segoe UI", 13, "bold")
FB  = ("Segoe UI", 11)
FS  = ("Segoe UI", 9)

# ═══════════════════════════════════════════════════════════════════
#  DATA HELPERS
# ═══════════════════════════════════════════════════════════════════
def _hash(pw):  return hashlib.sha256(pw.encode()).hexdigest()

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f:
            db = json.load(f)
    else:
        db = {"streams": {}, "students": {}}
    for sd in db.get("streams", {}).values():
        cd = sd.get("classes", {})
        if isinstance(cd, list):
            sd["classes"] = {c: {"subjects": []} for c in cd}
        else:
            for cv in sd["classes"].values():
                if "subjects" not in cv:
                    cv["subjects"] = []
    return db

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    users = {"admin": {"password": _hash("admin123"), "role": "admin",
                        "name": "System Admin", "email": "admin@dhvino.edu",
                        "phone": "", "assigned": [],
                        "created_at": datetime.now().isoformat()}}
    save_users(users)
    return users

def save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def _load(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []

def _save(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def load_notices():   return _load(NOTICES_FILE)
def save_notices(d):  _save(NOTICES_FILE, d)
def load_leaves():    return _load(LEAVE_FILE)
def save_leaves(d):   _save(LEAVE_FILE, d)

def load_timetable():
    if os.path.exists(TIMETABLE_FILE):
        with open(TIMETABLE_FILE) as f:
            return json.load(f)
    return {}

def save_timetable(d):  _save(TIMETABLE_FILE, d)

def load_assignments():   return _load(ASSIGNMENTS_FILE)
def save_assignments(d):  _save(ASSIGNMENTS_FILE, d)

# ═══════════════════════════════════════════════════════════════════
#  WIDGET HELPERS
# ═══════════════════════════════════════════════════════════════════
AVATAR_COLORS = ["#f0a500","#58a6ff","#3fb950","#bc8cff","#ffa657","#f85149","#79c0ff"]

def make_avatar_photo(name, size=60):
    if not _PIL:
        return None
    initials = "".join(p[0].upper() for p in name.split()[:2]) or "?"
    col = AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]
    img = Image.new("RGB", (size, size), col)
    d = ImageDraw.Draw(img)
    try:
        from PIL import ImageFont
        fnt = ImageFont.truetype("arial.ttf", size // 3)
    except:
        fnt = None
    if fnt:
        bb = d.textbbox((0,0), initials, font=fnt)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
    else:
        tw, th = len(initials)*size//5, size//3
    d.text(((size-tw)//2, (size-th)//2), initials, fill="white", font=fnt)
    return ImageTk.PhotoImage(img)

def _lighten(h):
    h = h.lstrip("#")
    r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return "#{:02x}{:02x}{:02x}".format(min(255,r+30), min(255,g+30), min(255,b+30))

def mkbtn(parent, text, cmd=None, bg=None, fg=None, w=None, **kw):
    bg = bg or C["accent"]
    fg = fg or C["bg"]
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  cursor="hand2", padx=14, pady=7, **kw)
    if w:
        b.config(width=w)
    b.bind("<Enter>", lambda e: b.config(bg=_lighten(bg)))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b

def sep(parent, bg=None):
    return tk.Frame(parent, bg=bg or C["border"], height=1)

def mkcb(parent, values=None, w=22):
    s = ttk.Style()
    s.configure("D.TCombobox", fieldbackground=C["card2"], background=C["card2"],
                foreground=C["text"], arrowcolor=C["accent"])
    cb = ttk.Combobox(parent, values=values or [],
                      style="D.TCombobox", state="readonly")
    return cb

def mkentry(parent, ph="", w=28, show=None):
    e = tk.Entry(parent, font=FB, bg=C["card2"], fg=C["text"],
                 insertbackground=C["accent"], relief="flat", bd=0,
                 highlightbackground=C["border"], highlightthickness=1,
                 highlightcolor=C["accent"])
    if show:
        e.config(show=show)
    if ph:
        e.insert(0, ph)
        e.config(fg=C["muted"])
        def fi(ev):
            if e.get() == ph:
                e.delete(0, tk.END); e.config(fg=C["text"])
        def fo(ev):
            if not e.get():
                e.insert(0, ph); e.config(fg=C["muted"])
        e.bind("<FocusIn>", fi); e.bind("<FocusOut>", fo)
    return e

def mkcard(parent, px=18, py=14):
    return tk.Frame(parent, bg=C["card"],
                    highlightbackground=C["border"], highlightthickness=1,
                    padx=px, pady=py)

def mktree(parent, cols, h=14):
    s = ttk.Style()
    s.configure("D.Treeview", background=C["card"], foreground=C["text"],
                fieldbackground=C["card"], rowheight=28, font=FB)
    s.configure("D.Treeview.Heading", background=C["card2"],
                foreground=C["accent"], font=("Segoe UI",10,"bold"))
    s.map("D.Treeview", background=[("selected",C["accent"])],
          foreground=[("selected",C["bg"])])
    tv = ttk.Treeview(parent, columns=cols, show="headings",
                      height=h, style="D.Treeview")
    for c in cols:
        tv.heading(c, text=c)
        tv.column(c, width=120, anchor="center")
    sb = ttk.Scrollbar(parent, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=sb.set)
    return tv, sb

def scroll_frame(parent):
    outer = tk.Frame(parent, bg=C["bg"])
    c = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=c.yview)
    inner = tk.Frame(c, bg=C["bg"])
    inner.bind("<Configure>",
               lambda e: c.configure(scrollregion=c.bbox("all")))
    c.create_window((0,0), window=inner, anchor="nw")
    c.configure(yscrollcommand=sb.set)
    c.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _scroll(e):
        try:
            c.yview_scroll(int(-1*(e.delta/120)), "units")
        except:
            pass
    outer.bind_all("<MouseWheel>", _scroll)
    return outer, inner

def stat_card(parent, val, lbl, col, ico):
    f = tk.Frame(parent, bg=C["card"],
                 highlightbackground=col, highlightthickness=2,
                 padx=18, pady=14)
    tk.Label(f, text=ico, bg=C["card"], fg=col, font=("Segoe UI",20)).pack()
    tk.Label(f, text=str(val), bg=C["card"], fg=col,
             font=("Segoe UI",28,"bold")).pack()
    tk.Label(f, text=lbl, bg=C["card"], fg=C["muted"], font=FS).pack()
    return f

# ═══════════════════════════════════════════════════════════════════
#  APPLICATION
# ═══════════════════════════════════════════════════════════════════
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Vision ERP")
        self.root.state("zoomed")
        self.root.configure(bg=C["bg"])

        self.cur_user      = None
        self.cur_role      = None
        self.cur_data      = {}
        self.pages         = {}
        self.active_nb     = None
        self._nav_btns     = {}
        self._clock_job    = None
        self._theme_btn    = None   # reference to toggle button in header
        # OAuth — always initialised so _rebuild_oauth_buttons is safe to call
        self._oauth_btn_frame = None
        self._lerr_oauth      = None

        self._style()
        os.makedirs(os.path.join(BASE_DIR,"attendance"),    exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR,"dataset"),       exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR,"StudentDetails"),exist_ok=True)

        if not os.path.exists(DB_FILE):
            save_db({"streams":{},"students":{}})

        self._show_login()
        self.root.mainloop()

    # ── ttk style ─────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TScrollbar", background=C["card2"],
                    troughcolor=C["bg"], arrowcolor=C["muted"])

    def _apply_theme(self):
        """Rebuild the entire UI with the new theme colours."""
        if self.cur_role == "admin":
            self._build_admin()
        elif self.cur_role == "teacher":
            self._build_teacher()
        elif self.cur_role == "student":
            self._build_student()
        else:
            self._show_login()

    def _do_toggle_theme(self):
        toggle_theme()
        self.root.configure(bg=C["bg"])
        self._style()
        self._apply_theme()

    # ─────────────────────────────────────────────────────────────
    #  CLOCK (cancel previous before starting new)
    # ─────────────────────────────────────────────────────────────
    def _stop_clock(self):
        if self._clock_job is not None:
            try:
                self.root.after_cancel(self._clock_job)
            except:
                pass
            self._clock_job = None

    def _start_clock(self, lbl):
        self._stop_clock()
        def tick():
            try:
                lbl.config(text=datetime.now().strftime("%A  %d %b %Y   %H:%M:%S"))
                self._clock_job = self.root.after(1000, tick)
            except tk.TclError:
                pass
        tick()

    # ─────────────────────────────────────────────────────────────
    #  CLEAR
    # ─────────────────────────────────────────────────────────────
    def _clear(self):
        self._stop_clock()
        for w in self.root.winfo_children():
            w.destroy()
        self.pages            = {}
        self.active_nb        = None
        self._nav_btns        = {}
        # Nullify OAuth widget refs — they were just destroyed above
        self._oauth_btn_frame = None
        self._lerr_oauth      = None

    # ═══════════════════════════════════════════════════════════
    #  LOGIN
    # ═══════════════════════════════════════════════════════════
    def _show_login(self):
        self._clear()
        self.cur_user = None
        self.cur_role = None
        self.root.configure(bg=C["bg"])

        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill=tk.BOTH, expand=True)

        # LEFT branding panel
        left = tk.Frame(main, bg=C["hdr"], width=480)
        left.pack(side=tk.LEFT, fill=tk.Y)
        left.pack_propagate(False)

        for col in [C["accent"],C["accent2"],"#a07010","#705010"]:
            tk.Frame(left, bg=col, height=4).pack(fill=tk.X)

        bf = tk.Frame(left, bg=C["hdr"])
        bf.place(relx=0.5, rely=0.44, anchor="center")
        tk.Label(bf, text="⬡", bg=C["hdr"], fg=C["accent"],
                 font=("Segoe UI",52)).pack()
        tk.Label(bf, text="Vision", bg=C["hdr"], fg=C["accent"],
                 font=("Segoe UI",34,"bold")).pack()
        tk.Label(bf, text="Academic ERP System", bg=C["hdr"], fg=C["muted"],
                 font=("Segoe UI",13)).pack(pady=(2,18))
        sep(bf).pack(fill=tk.X, pady=10)
        for feat in ["🎓  Smart Face Attendance",
                     "📊  Analytics Dashboard",
                     "👥  Teacher & Student Portal",
                     "📋  Timetable & Notices",
                     "✉️   Leave Management"]:
            tk.Label(bf, text=feat, bg=C["hdr"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(pady=2, anchor="w")
        tk.Label(left, text=f"© {datetime.now().year} DHVINO Education Technology",
                 bg=C["hdr"], fg=C["border"], font=FS).pack(side=tk.BOTTOM, pady=14)

        # RIGHT form panel
        right = tk.Frame(main, bg=C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # theme toggle top-right of login screen
        ttf = tk.Frame(right, bg=C["bg"])
        ttf.pack(fill=tk.X)
        icon  = "☀️" if _current_theme == "dark" else "🌙"
        label = " Light mode" if _current_theme == "dark" else " Dark mode"
        tb = tk.Button(ttf, text=f"{icon}{label}",
                       command=lambda: [toggle_theme(),
                                        self.root.configure(bg=C["bg"]),
                                        self._style(),
                                        self._show_login()],
                       bg=C["card2"], fg=C["text"],
                       font=("Segoe UI", 9), relief="flat",
                       cursor="hand2", padx=10, pady=5,
                       activebackground=C["accent"], activeforeground=C["bg"])
        tb.pack(side=tk.RIGHT, padx=16, pady=12)

        form = tk.Frame(right, bg=C["bg"])
        form.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(form, text="Welcome Back", bg=C["bg"], fg=C["text"],
                 font=("Segoe UI",22,"bold")).pack(pady=(0,4))
        tk.Label(form, text="Sign in to your account", bg=C["bg"],
                 fg=C["muted"], font=("Segoe UI",11)).pack(pady=(0,26))

        # Role buttons
        self._role_var = tk.StringVar(value="admin")
        rbf = tk.Frame(form, bg=C["bg"])
        rbf.pack(pady=(0,20))

        self._role_frames = {}
        for txt, val, ico in [("Admin","admin","⚙️"), ("Teacher","teacher","👨\u200d🏫"), ("Student","student","🎓")]:
            rf = tk.Frame(rbf, bg=C["card"],
                          highlightbackground=C["border"], highlightthickness=2,
                          padx=22, pady=12, cursor="hand2")
            rf.pack(side=tk.LEFT, padx=8)
            tk.Label(rf, text=ico, bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",18)).pack()
            tk.Label(rf, text=txt, bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10,"bold")).pack()
            self._role_frames[val] = rf

            def sel(v=val):
                self._role_var.set(v)
                for vv, ff in self._role_frames.items():
                    is_sel = vv == v
                    ff.configure(highlightbackground=C["accent"] if is_sel else C["border"])
                    for w in ff.winfo_children():
                        w.configure(fg=C["accent"] if is_sel else C["muted"])

            rf.bind("<Button-1>", lambda e, v=val: sel(v))
            for w in rf.winfo_children():
                w.bind("<Button-1>", lambda e, v=val: sel(v))

        # Pre-select admin styling
        self._role_frames["admin"].configure(highlightbackground=C["accent"])
        for w in self._role_frames["admin"].winfo_children():
            w.configure(fg=C["accent"])

        # Username
        tk.Label(form, text="Username", bg=C["bg"], fg=C["muted"],
                 font=("Segoe UI",10)).pack(anchor="w")
        self._lu = tk.Entry(form, font=FB, bg=C["card"], fg=C["text"],
                            insertbackground=C["accent"], relief="flat", bd=0,
                            width=30, highlightbackground=C["border"],
                            highlightthickness=1, highlightcolor=C["accent"])
        self._lu.pack(pady=(3,12), ipady=8, padx=2, fill=tk.X)
        self._lu.insert(0, "admin")

        # Password
        tk.Label(form, text="Password", bg=C["bg"], fg=C["muted"],
                 font=("Segoe UI",10)).pack(anchor="w")
        self._lp = tk.Entry(form, font=FB, bg=C["card"], fg=C["text"],
                            insertbackground=C["accent"], relief="flat", bd=0,
                            width=30, show="●", highlightbackground=C["border"],
                            highlightthickness=1, highlightcolor=C["accent"])
        self._lp.pack(pady=(3,6), ipady=8, padx=2, fill=tk.X)
        self._lp.insert(0, "admin123")

        self._lerr = tk.Label(form, text="", bg=C["bg"], fg=C["red"], font=FS)
        self._lerr.pack(pady=(0,10))

        sb2 = tk.Button(form, text="Sign In  →", command=self._do_login,
                        bg=C["accent"], fg=C["bg"],
                        font=("Segoe UI",12,"bold"),
                        relief="flat", cursor="hand2", width=26, pady=10)
        sb2.pack()
        sb2.bind("<Enter>", lambda e: sb2.config(bg=C["accent2"]))
        sb2.bind("<Leave>", lambda e: sb2.config(bg=C["accent"]))
        self.root.bind("<Return>", lambda e: self._do_login())

        tk.Label(form, text="Default: admin / admin123",
                 bg=C["bg"], fg=C["border"], font=FS).pack(pady=(14,0))

        # ── OAuth "Sign in with …" buttons ───────────────────────
        # Built entirely inline on every _show_login call.
        # Reads config fresh — no stale widget references possible.
        if _OAUTH_OK:
            try:
                cfg = load_oauth_config()
                active_providers = [
                    (pk, pi) for pk, pi in PROVIDERS.items()
                    if cfg.get(pk, {}).get("enabled")
                    and cfg.get(pk, {}).get("client_id", "").strip()
                ]
            except Exception:
                active_providers = []

            if active_providers:
                tk.Frame(form, bg=C["border"],
                         height=1).pack(fill=tk.X, pady=(16, 8))
                tk.Label(form, text="— or sign in with —",
                         bg=C["bg"], fg=C["muted"],
                         font=("Segoe UI", 9)).pack()

                # Status label for OAuth feedback (stored on self for _do_oauth_login)
                self._lerr_oauth = tk.Label(form, text="",
                                            bg=C["bg"], fg=C["blue"], font=FS)

                for pkey, pinfo in active_providers:
                    b = tk.Button(
                        form,
                        text=f"{pinfo['icon']}  Continue with {pinfo['label']}",
                        command=lambda p=pkey: self._do_oauth_login(p),
                        bg=C["card"], fg=C["text"],
                        font=("Segoe UI", 10, "bold"),
                        relief="flat", cursor="hand2",
                        width=26, pady=8,
                        activebackground=C["card2"],
                        activeforeground=C["text"],
                    )
                    b.pack(pady=3, fill=tk.X)

                self._lerr_oauth.pack(pady=(6, 0))

    # ─── OAuth login flow ────────────────────────────────────────
    def _do_oauth_login(self, provider: str):
        """Run OAuth browser flow in background thread, then log in."""
        lbl = self._lerr_oauth
        if lbl is None:
            return
        lbl.config(
            text=f"🔄  Opening {PROVIDERS[provider]['label']} in browser…",
            fg=C["blue"])
        self.root.update()

        def _run():
            try:
                result = OAuthFlow(provider).run(timeout=120)
            except RuntimeError as exc:
                self.root.after(0, lambda: _safe_lbl(f"❌  {exc}", C["red"]))
                return
            except Exception as exc:
                self.root.after(0, lambda: _safe_lbl(f"❌  Error: {exc}", C["red"]))
                return

            if result is None:
                self.root.after(0,
                    lambda: _safe_lbl("❌  Cancelled or timed out.", C["red"]))
                return

            users = load_users()
            match = find_user_by_oauth(result["email"], users)
            if match is None:
                self.root.after(0,
                    lambda: _safe_lbl(
                        f"❌  No account linked to {result['email']}", C["red"]))
                return

            uname, ud = match

            def _finish():
                self.cur_user = uname
                self.cur_role = ud["role"]
                self.cur_data = ud
                self.root.unbind("<Return>")
                if self.cur_role == "admin":     self._build_admin()
                elif self.cur_role == "teacher": self._build_teacher()
                else:                            self._build_student()

            self.root.after(0, _finish)

        # Safe label update — widget may be gone if user navigated away
        def _safe_lbl(msg, fg):
            try:
                if self._lerr_oauth and self._lerr_oauth.winfo_exists():
                    self._lerr_oauth.config(text=msg, fg=fg)
            except tk.TclError:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def _do_login(self):
        uname = self._lu.get().strip()
        pw    = self._lp.get()
        role  = self._role_var.get()
        users = load_users()

        if uname not in users:
            self._lerr.config(text="❌  Invalid username or password")
            return
        ud = users[uname]
        if ud["password"] != _hash(pw):
            self._lerr.config(text="❌  Invalid username or password")
            return
        if ud["role"] != role:
            self._lerr.config(text=f"❌  This account is not a {role}")
            return

        self.cur_user = uname
        self.cur_role = ud["role"]
        self.cur_data = ud
        self.root.unbind("<Return>")

        if self.cur_role == "admin":
            self._build_admin()
        elif self.cur_role == "teacher":
            self._build_teacher()
        else:
            self._build_student()

    # ─────────────────────────────────────────────────────────────
    #  SHELL (header + scrollable sidebar + content)
    # ─────────────────────────────────────────────────────────────
    def _build_shell(self, nav_items):
        self._clear()

        # ── Header ──────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C["hdr"], height=60)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        tk.Label(hdr, text="⬡  DHVINO ERP", bg=C["hdr"], fg=C["accent"],
                 font=("Segoe UI",17,"bold")).pack(side=tk.LEFT, padx=22)
        lb = tk.Button(hdr, text="⏻  Logout", command=self._show_login,
                       bg=C["hdr"], fg=C["muted"], font=("Segoe UI",10),
                       relief="flat", cursor="hand2", padx=12, pady=6,
                       activebackground=C["red"], activeforeground="white")
        lb.pack(side=tk.RIGHT, padx=10)
        rcol = (C["accent"] if self.cur_role=="admin"
                else C["blue"] if self.cur_role=="teacher" else C["green"])
        tk.Label(hdr, text=f"  {self.cur_data['name']}  |  {self.cur_role.upper()}  ",
                 bg=rcol, fg=C["bg"],
                 font=("Segoe UI",10,"bold")).pack(side=tk.RIGHT, padx=4, pady=14)
        tk.Frame(hdr, bg=C["border"], width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=8)

        # ── Theme toggle ──────────────────────────────────────
        icon  = "☀️" if _current_theme == "dark" else "🌙"
        label = " Light" if _current_theme == "dark" else " Dark"
        self._theme_btn = tk.Button(
            hdr, text=f"{icon}{label}",
            command=self._do_toggle_theme,
            bg=C["card2"], fg=C["text"],
            font=("Segoe UI", 9), relief="flat",
            cursor="hand2", padx=10, pady=4,
            activebackground=C["accent"], activeforeground=C["bg"])
        self._theme_btn.pack(side=tk.RIGHT, padx=6, pady=8)
        tk.Frame(hdr, bg=C["border"], width=1).pack(side=tk.RIGHT, fill=tk.Y, pady=8)

        clk = tk.Label(hdr, text="", bg=C["hdr"], fg=C["muted"], font=("Segoe UI",10))
        clk.pack(side=tk.RIGHT, padx=16)
        self._start_clock(clk)

        # ── Body ────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # ── Scrollable sidebar ───────────────────────────────────
        SB_W = 230
        sb_outer = tk.Frame(body, bg=C["sidebar"], width=SB_W)
        sb_outer.pack(side=tk.LEFT, fill=tk.Y)
        sb_outer.pack_propagate(False)

        sb_canvas = tk.Canvas(sb_outer, bg=C["sidebar"],
                              highlightthickness=0, width=SB_W)
        sb_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb_scroll = ttk.Scrollbar(sb_outer, orient="vertical",
                                  command=sb_canvas.yview)
        sb_canvas.configure(yscrollcommand=sb_scroll.set)

        sb = tk.Frame(sb_canvas, bg=C["sidebar"])
        sb_win = sb_canvas.create_window((0, 0), window=sb, anchor="nw", width=SB_W)

        def _on_sb_configure(e):
            sb_canvas.configure(scrollregion=sb_canvas.bbox("all"))
            total = sb_canvas.bbox("all")
            if total and total[3] > sb_canvas.winfo_height():
                sb_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                sb_scroll.pack_forget()

        def _on_canvas_resize(e):
            sb_canvas.itemconfig(sb_win, width=e.width)

        sb.bind("<Configure>", _on_sb_configure)
        sb_canvas.bind("<Configure>", _on_canvas_resize)

        def _sw(e):
            try: sb_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
            except Exception: pass
        def _su(e): sb_canvas.yview_scroll(-1, "units")
        def _sd(e): sb_canvas.yview_scroll( 1, "units")
        for w in (sb_canvas, sb):
            w.bind("<MouseWheel>", _sw)
            w.bind("<Button-4>",   _su)
            w.bind("<Button-5>",   _sd)

        # ── Avatar ───────────────────────────────────────────────
        avf = tk.Frame(sb, bg=C["sidebar"], pady=14); avf.pack(fill=tk.X)
        if _PIL:
            try:
                av = make_avatar_photo(self.cur_data["name"], 52)
                if av:
                    al = tk.Label(avf, image=av, bg=C["sidebar"])
                    al.image = av; al.pack()
            except Exception: pass
        tk.Label(avf, text=self.cur_data["name"], bg=C["sidebar"],
                 fg=C["text"], font=("Segoe UI",11,"bold")).pack(pady=(5,1))
        tk.Label(avf, text=self.cur_role.upper(), bg=C["sidebar"],
                 fg=C["accent"], font=("Segoe UI",9)).pack()
        sep(sb).pack(fill=tk.X, padx=12, pady=6)

        # ── Content ─────────────────────────────────────────────
        content = tk.Frame(body, bg=C["bg"])
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Nav buttons ─────────────────────────────────────────
        self._nav_btns = {}
        for item in nav_items:
            if item == "---":
                sep(sb).pack(fill=tk.X, padx=12, pady=4); continue
            ico, lbl_text, pkey = item
            bf = tk.Frame(sb, bg=C["sidebar"]); bf.pack(fill=tk.X, padx=6, pady=1)
            b = tk.Button(bf, text=f"  {ico}  {lbl_text}", anchor="w",
                          command=lambda k=pkey: self._nav(k),
                          bg=C["sidebar"], fg=C["muted"],
                          font=("Segoe UI",10,"bold"), relief="flat",
                          height=2, padx=10,
                          activebackground=C["accent"], activeforeground=C["bg"],
                          cursor="hand2")
            b.pack(fill=tk.X)
            for w in (b, bf):
                w.bind("<MouseWheel>", _sw)
                w.bind("<Button-4>",   _su)
                w.bind("<Button-5>",   _sd)
            b.bind("<Enter>", lambda e, bb=b: bb.config(bg=C["card"], fg=C["text"])
                   if bb is not self.active_nb else None)
            b.bind("<Leave>", lambda e, bb=b: bb.config(
                bg=C["sidebar"] if bb is not self.active_nb else C["accent"],
                fg=C["muted"]   if bb is not self.active_nb else C["bg"]))
            self._nav_btns[pkey] = b

        tk.Frame(sb, bg=C["sidebar"], height=16).pack()
        return content

    def _nav(self, key):
        for p in self.pages.values():
            p.pack_forget()
        if key in self.pages:
            self.pages[key].pack(fill=tk.BOTH, expand=True)
            if hasattr(self.pages[key], "on_show"):
                self.pages[key].on_show()
        if self.active_nb:
            self.active_nb.config(bg=C["sidebar"], fg=C["muted"])
        nb = self._nav_btns.get(key)
        if nb:
            nb.config(bg=C["accent"], fg=C["bg"])
            self.active_nb = nb

    # ═══════════════════════════════════════════════════════════
    #  ADMIN UI
    # ═══════════════════════════════════════════════════════════
    def _build_admin(self):
        nav = [
            ("🏠", "Dashboard",      "dashboard"),
            ("📋", "Manage Classes",  "classes"),
            ("👥", "Students",        "students"),
            ("📸", "Attendance",      "attendance"),
            ("📊", "View Records",    "records"),
            "---",
            ("👨‍🏫", "Teachers",       "teachers"),
            ("📝", "Assignments",     "assignments"),
            ("📣", "Notices",         "notices"),
            ("📅", "Timetable",       "timetable"),
            ("✉️",  "Leave Requests", "leaves"),
            "---",
            ("✏️",  "Edit / Delete",  "edit"),
            ("⚙️",  "Settings",       "settings"),
        ]
        ct = self._build_shell(nav)
        self.pages["dashboard"]   = self._pg_a_dashboard(ct)
        self.pages["classes"]     = self._pg_classes(ct)
        self.pages["students"]    = self._pg_students(ct)
        self.pages["attendance"]  = self._pg_attendance(ct)
        self.pages["records"]     = self._pg_records(ct)
        self.pages["teachers"]    = self._pg_teachers(ct)
        self.pages["assignments"] = self._pg_assignments(ct)
        self.pages["notices"]     = self._pg_notices(ct)
        self.pages["timetable"]   = self._pg_timetable(ct)
        self.pages["leaves"]      = self._pg_leaves(ct)
        self.pages["edit"]        = self._pg_edit(ct)
        self.pages["settings"]    = self._pg_settings(ct)
        self._nav("dashboard")

    # ─── ADMIN DASHBOARD ────────────────────────────────────────
    def _pg_a_dashboard(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            db    = load_db()
            users = load_users()
            streams  = db.get("streams", {})
            students = db.get("students", {})
            teachers = {u: d for u,d in users.items() if d.get("role")=="teacher"}

            total_cls = sum(len(d.get("classes",{})) for d in streams.values())
            today     = datetime.now().strftime("%Y-%m-%d")
            att_today = 0
            for fp in glob.glob(os.path.join(BASE_DIR,"attendance","**",f"{today}.csv"),
                                recursive=True):
                try: att_today += len(pd.read_csv(fp))
                except: pass

            tr = tk.Frame(inner, bg=C["bg"])
            tr.pack(fill=tk.X, padx=20, pady=(20, 10))
            greet = "Morning" if datetime.now().hour < 12 else \
                    ("Afternoon" if datetime.now().hour < 17 else "Evening")
            tk.Label(tr, text=f"Good {greet}, {self.cur_data['name'].split()[0]} 👋",
                     bg=C["bg"], fg=C["text"],
                     font=("Segoe UI",20,"bold")).pack(side=tk.LEFT)
            tk.Label(tr, text=datetime.now().strftime("%A, %d %B %Y"),
                     bg=C["bg"], fg=C["muted"], font=FB).pack(side=tk.RIGHT)

            # ── stat cards — grid so they share all available width ──
            sg = tk.Frame(inner, bg=C["bg"])
            sg.pack(fill=tk.X, padx=35, pady=(8, 22))
            stat_data = [
                (len(streams),   "Streams",         C["accent"], "🎓"),
                (total_cls,      "Classes",          C["blue"],   "📚"),
                (len(students),  "Students",         C["green"],  "👥"),
                (len(teachers),  "Teachers",         C["purple"], "👨‍🏫"),
                (att_today,      "Attendance Today", C["orange"], "✅"),
            ]
            for i in range(len(stat_data)):
                sg.columnconfigure(i, weight=1)
            for col_idx, (val, lbl, col, ico) in enumerate(stat_data):
                sc = stat_card(sg, val, lbl, col, ico)
                sc.grid(row=0, column=col_idx, sticky="nsew", padx=14, pady=10)

            # ── lower section — grid 3 columns, all expanding ────────
            lower = tk.Frame(inner, bg=C["bg"])
            lower.pack(fill=tk.BOTH, padx=35, pady=(5, 25), expand=True)
            lower.columnconfigure(0, weight=2)
            lower.columnconfigure(1, weight=1)
            lower.columnconfigure(2, weight=1)
            lower.rowconfigure(0, weight=1)

            # ── streams overview ─────────────────────────────────────
            lc = mkcard(lower, 20, 16)
            lc.grid(row=0, column=0, sticky="nsew", padx=(0, 16), pady=8)
            tk.Label(lc, text="📋  Streams Overview", bg=C["card"],
                     fg=C["text"], font=FSH).pack(anchor="w", pady=(0, 8))
            sep(lc).pack(fill=tk.X, pady=(0, 8))
            if not streams:
                tk.Label(lc, text="No streams yet. Go to Manage Classes →",
                         bg=C["card"], fg=C["muted"], font=FB).pack(pady=20)
            for sn, sd in streams.items():
                rf = tk.Frame(lc, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1)
                rf.pack(fill=tk.X, pady=5, padx=2)
                cls_cnt = len(sd.get("classes", {}))
                enr = sum(1 for s in students.values() if s.get("stream") == sn)
                tk.Label(rf, text=f"  🎓 {sn}", bg=C["card2"],
                         fg=C["accent"], font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=10, pady=8)
                tk.Label(rf, text=f"{cls_cnt} classes  •  {enr} students",
                         bg=C["card2"], fg=C["muted"], font=FS).pack(side=tk.RIGHT, padx=14)

            # ── quick actions ────────────────────────────────────────
            qa = mkcard(lower, 20, 16)
            qa.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
            tk.Label(qa, text="⚡  Quick Actions", bg=C["card"],
                     fg=C["text"], font=FSH).pack(anchor="w", pady=(0, 8))
            sep(qa).pack(fill=tk.X, pady=(0, 8))
            for btxt, bpg in [("➕  Register Student", "students"),
                               ("📸  Take Attendance",  "attendance"),
                               ("📣  Post Notice",      "notices")]:
                b = tk.Button(qa, text=btxt,
                              command=lambda p=bpg: self._nav(p),
                              bg=C["card2"], fg=C["text"], font=("Segoe UI", 10),
                              relief="flat", cursor="hand2", anchor="w",
                              padx=12, pady=8)
                b.pack(fill=tk.X, pady=4)
                b.bind("<Enter>", lambda e, bb=b: bb.config(bg=C["accent"], fg=C["bg"]))
                b.bind("<Leave>", lambda e, bb=b: bb.config(bg=C["card2"], fg=C["text"]))

            # ── recent notices ───────────────────────────────────────
            nc = mkcard(lower, 20, 16)
            nc.grid(row=0, column=2, sticky="nsew", padx=(16, 0), pady=8)
            tk.Label(nc, text="📣  Recent Notices", bg=C["card"],
                     fg=C["text"], font=FSH).pack(anchor="w", pady=(0, 8))
            sep(nc).pack(fill=tk.X, pady=(0, 8))
            notices = load_notices()[-4:][::-1]
            if not notices:
                tk.Label(nc, text="No notices yet.", bg=C["card"],
                         fg=C["muted"], font=FB).pack(pady=20)
            for n in notices:
                nf = tk.Frame(nc, bg=C["card2"], padx=10, pady=7)
                nf.pack(fill=tk.X, pady=4)
                tk.Label(nf, text=n.get("title", "")[:34], bg=C["card2"],
                         fg=C["text"], font=("Segoe UI", 10, "bold")).pack(anchor="w")
                tk.Label(nf, text=n.get("date", ""), bg=C["card2"],
                         fg=C["muted"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── MANAGE CLASSES ─────────────────────────────────────────
    def _pg_classes(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📋  Manage Streams & Classes",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1, minsize=380)
            row.columnconfigure(1, weight=1, minsize=380)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            # add panel
            ap = mkcard(row, 16, 18)
            ap.grid(row=0, column=0, sticky="nsew", padx=(0,7))

            def sec(title):
                tk.Label(ap, text=title, bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))

            sec("Add Stream")
            se = mkentry(ap, "Stream name e.g. MCA", w=24)
            se.pack(pady=(0,8), ipady=6, fill=tk.X)
            def add_stream():
                n = se.get().strip()
                if not n or n == "Stream name e.g. MCA": return
                db = load_db()
                if n in db["streams"]:
                    messagebox.showwarning("Exists", f"Stream '{n}' exists"); return
                db["streams"][n] = {"classes": {}}
                save_db(db); se.delete(0,tk.END); refresh()
            mkbtn(ap,"Add Stream", add_stream).pack(pady=(0,16), fill=tk.X)
            sep(ap).pack(fill=tk.X, pady=(0,14))

            db = load_db()
            sec("Add Class to Stream")
            s_cb = mkcb(ap, list(db["streams"].keys()), 22)
            s_cb.pack(pady=(0,6), fill=tk.X)
            ce = mkentry(ap, "Class e.g. 2nd Year", w=24)
            ce.pack(pady=(0,8), ipady=6, fill=tk.X)
            def add_class():
                s = s_cb.get(); n = ce.get().strip()
                if not s or not n or n=="Class e.g. 2nd Year": return
                db = load_db()
                if n in db["streams"].get(s,{}).get("classes",{}):
                    messagebox.showwarning("Exists","Class exists"); return
                db["streams"][s]["classes"][n] = {"subjects":[]}
                save_db(db); ce.delete(0,tk.END); refresh()
            mkbtn(ap,"Add Class", add_class).pack(pady=(0,16), fill=tk.X)
            sep(ap).pack(fill=tk.X, pady=(0,14))

            sec("Add Subject")
            s2 = mkcb(ap, list(db["streams"].keys()), 22)
            s2.pack(pady=(0,6), fill=tk.X)
            c2 = mkcb(ap, [], 22)
            c2.pack(pady=(0,6), fill=tk.X)
            def on_s2(e):
                db = load_db()
                c2["values"] = list(db["streams"].get(s2.get(),{}).get("classes",{}).keys())
            s2.bind("<<ComboboxSelected>>", on_s2)
            sube = mkentry(ap, "Subject e.g. DBMS", w=24)
            sube.pack(pady=(0,8), ipady=6, fill=tk.X)
            def add_sub():
                s = s2.get(); c = c2.get(); sub = sube.get().strip()
                if not all([s,c,sub]) or sub=="Subject e.g. DBMS": return
                db = load_db()
                subs = db["streams"][s]["classes"][c].get("subjects",[])
                if sub in subs: messagebox.showwarning("Exists","Subject exists"); return
                subs.append(sub)
                db["streams"][s]["classes"][c]["subjects"] = subs
                save_db(db); sube.delete(0,tk.END); refresh()
            mkbtn(ap,"Add Subject", add_sub).pack(fill=tk.X)

            # existing config
            rp = mkcard(row, 24, 22)
            rp.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(rp, text="Existing Configuration", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            db = load_db()
            if not db["streams"]:
                tk.Label(rp, text="No streams yet.", bg=C["card"],
                         fg=C["muted"], font=FB).pack(pady=20)
            for sn, sd in db["streams"].items():
                sf = tk.Frame(rp, bg=C["card2"],
                              highlightbackground=C["accent"], highlightthickness=1,
                              padx=14, pady=10)
                sf.pack(fill=tk.X, pady=5)
                sr = tk.Frame(sf, bg=C["card2"])
                sr.pack(fill=tk.X)
                tk.Label(sr, text=f"🎓  {sn}", bg=C["card2"], fg=C["accent"],
                         font=FSH).pack(side=tk.LEFT)
                def del_s(s=sn):
                    if messagebox.askyesno("Delete", f"Delete stream '{s}' and ALL data?"):
                        db = load_db()
                        db["streams"].pop(s,None)
                        db["students"] = {k:v for k,v in db["students"].items()
                                          if v.get("stream")!=s}
                        save_db(db); refresh()
                mkbtn(sr,"🗑", del_s, C["red"], w=3).pack(side=tk.RIGHT)
                for cn, cd in sd.get("classes",{}).items():
                    cf = tk.Frame(sf, bg=C["card"],
                                  highlightbackground=C["border"], highlightthickness=1,
                                  padx=12, pady=7)
                    cf.pack(fill=tk.X, pady=2)
                    cr = tk.Frame(cf, bg=C["card"])
                    cr.pack(fill=tk.X)
                    tk.Label(cr, text=f"📚  {cn}", bg=C["card"], fg=C["text"],
                             font=("Segoe UI",11,"bold")).pack(side=tk.LEFT)
                    subs = cd.get("subjects",[])
                    tk.Label(cr, text=f"{len(subs)} subjects", bg=C["card"],
                             fg=C["muted"], font=FS).pack(side=tk.LEFT, padx=8)
                    def del_c(s=sn, c=cn):
                        if messagebox.askyesno("Delete", f"Delete class '{c}'?"):
                            db = load_db()
                            db["streams"][s]["classes"].pop(c,None)
                            db["students"] = {k:v for k,v in db["students"].items()
                                              if not (v.get("stream")==s and v.get("class")==c)}
                            save_db(db); refresh()
                    mkbtn(cr,"🗑", del_c, C["red"], w=3).pack(side=tk.RIGHT)
                    if subs:
                        tk.Label(cf, text="  Subjects: "+", ".join(subs),
                                 bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── STUDENTS ───────────────────────────────────────────────
    def _pg_students(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        tk.Label(page, text="👥  Student Management",
                 bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")

        nb = ttk.Notebook(page)
        nb.pack(fill=tk.BOTH, expand=True, padx=28, pady=6)

        # ── Tab 1: All students ──
        t1 = tk.Frame(nb, bg=C["bg"])
        nb.add(t1, text="  All Students  ")
        sr = tk.Frame(t1, bg=C["bg"])
        sr.pack(fill=tk.X, pady=8)
        se = mkentry(sr, "🔍  Search name or ID...", w=36)
        se.pack(side=tk.LEFT, ipady=7, padx=4)
        tvf = tk.Frame(t1, bg=C["bg"])
        tvf.pack(fill=tk.BOTH, expand=True)

        # Added "Face" column to show whether face data exists in model
        cols = ["ID","Name","Stream","Class","Face","Registered"]
        tv, tsb = mktree(tvf, cols, h=16)
        tv.column("ID",         width=155)
        tv.column("Name",       width=190)
        tv.column("Stream",     width=110)
        tv.column("Class",      width=110)
        tv.column("Face",       width=70)
        tv.column("Registered", width=110)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)

        def _face_trained(sid, name):
            """Return ✅ if student has encodings in face_encodings.pkl, else ➕"""
            enc_p = os.path.join(BASE_DIR, "face_encodings.pkl")
            if not os.path.exists(enc_p):
                return "➕"
            try:
                import pickle
                with open(enc_p, "rb") as f:
                    store = pickle.load(f)
                key = f"{sid}|{name}"
                return "✅" if key in store else "➕"
            except Exception:
                return "?"

        def load_stu(q=""):
            tv.delete(*tv.get_children())
            db = load_db()
            for sid, d in db.get("students", {}).items():
                nm = d.get("name", "")
                if q and q.lower() not in sid.lower() and q.lower() not in nm.lower():
                    continue
                face_icon = _face_trained(sid, nm)
                tv.insert("", "end", iid=sid,
                          values=(sid, nm,
                                  d.get("stream",""), d.get("class",""),
                                  face_icon,
                                  d.get("registered_at","")[:10]))

        se.bind("<KeyRelease>",
                lambda e: load_stu("" if se.get() == "🔍  Search name or ID..." else se.get()))

        # ── button row ──────────────────────────────────────────────────
        br = tk.Frame(t1, bg=C["bg"])
        br.pack(fill=tk.X, pady=4)

        def _selected_sid():
            sel = tv.selection()
            if not sel:
                messagebox.showinfo("Select", "Please select a student row first.")
                return None
            # Use the iid directly — it is always the exact string key from db.json
            # Never use values[0] because Treeview silently converts numeric-looking
            # strings to int, which breaks dict.pop() on string-keyed dicts.
            return str(sel[0])

        def del_stu():
            sid = _selected_sid()
            if sid is None: return
            nm  = str(tv.item(sid)["values"][1])
            if messagebox.askyesno("Delete", f"Delete student '{nm}' ({sid})?\nThis cannot be undone."):
                db = load_db()
                db["students"].pop(sid, None)
                save_db(db)
                load_stu()

        def capture_later():
            """Open face-capture for an already-registered student."""
            sid = _selected_sid()
            if sid is None: return
            row  = tv.item(sid)["values"]
            nm   = str(row[1])
            strm = str(row[2])
            cls  = str(row[3])
            if not messagebox.askyesno("Capture Face",
                                       f"Open camera to capture face data for\n{nm} ({sid})?"):
                return
            try:
                import importlib, sys as _sys
                # Force reload so we always get the latest file
                if "capture_and_train" in _sys.modules:
                    importlib.reload(_sys.modules["capture_and_train"])
                from capture_and_train import capture_and_train as _cap
                save = messagebox.askyesno("Save Images?",
                                           "Save captured face images to dataset/ folder?\n"
                                           "YES = keep  |  NO = discard after training")
                ok, msg = _cap(sid, nm, strm, cls,
                               save_images=save,
                               tk_root=self.root)
                if ok:
                    messagebox.showinfo("Done", msg)
                    load_stu()   # refresh Face column
                else:
                    messagebox.showerror("Failed", msg)
            except Exception as ex:
                messagebox.showerror("Error", str(ex))

        mkbtn(br, "🗑  Delete",            del_stu,       C["red"]).pack(side=tk.LEFT, padx=4)
        mkbtn(br, "📸  Capture Face Later", capture_later, C["blue"]).pack(side=tk.LEFT, padx=4)
        mkbtn(br, "🔄  Refresh",           lambda: load_stu(), C["card2"]).pack(side=tk.LEFT, padx=4)

        # ── Tab 2: Register ──
        t2 = tk.Frame(nb, bg=C["bg"])
        nb.add(t2, text="  Register New  ")

        # scrollable inner area so the form never gets clipped
        t2_so, t2_inner = scroll_frame(t2)
        t2_so.pack(fill=tk.BOTH, expand=True)

        rc2 = mkcard(t2_inner, 36, 28)
        rc2.pack(pady=20, padx=20, fill=tk.X)

        tk.Label(rc2, text="Register New Student", bg=C["card"],
                 fg=C["accent"], font=FSH).pack(pady=(0,18))
        tk.Label(rc2,
                 text="The camera will open automatically after you click Register.\n"
                      "150 face images will be captured and trained with LBPH.\n"
                      "You will be asked whether to save the images to disk.",
                 bg=C["card"], fg=C["muted"], font=("Segoe UI",9),
                 wraplength=380, justify="left").pack(pady=(0,14))

        flds = {}
        for lbl, key, ph in [("Full Name","name","e.g. Violina Saikia"),
                               ("Student ID","id","e.g. CS24MCA013")]:
            tk.Label(rc2, text=lbl, bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(anchor="w")
            e = mkentry(rc2, ph, w=30)
            e.pack(pady=(3,12), ipady=7, fill=tk.X)
            flds[key] = e

        tk.Label(rc2, text="Stream", bg=C["card"], fg=C["muted"],
                 font=("Segoe UI",10)).pack(anchor="w")
        db0 = load_db()
        reg_s = mkcb(rc2, list(db0["streams"].keys()), 28)
        reg_s.pack(pady=(3,10), fill=tk.X)
        tk.Label(rc2, text="Class", bg=C["card"], fg=C["muted"],
                 font=("Segoe UI",10)).pack(anchor="w")
        reg_c = mkcb(rc2, [], 28)
        reg_c.pack(pady=(3,14), fill=tk.X)

        def on_rs(e):
            db = load_db()
            reg_c["values"] = list(db["streams"].get(reg_s.get(),{}).get("classes",{}).keys())
        reg_s.bind("<<ComboboxSelected>>", on_rs)

        # save-images checkbox
        save_var = tk.BooleanVar(value=True)
        cb_fr = tk.Frame(rc2, bg=C["card"]); cb_fr.pack(anchor="w", pady=(0,6))
        tk.Checkbutton(cb_fr, text="Save captured face images to disk",
                       variable=save_var, bg=C["card"], fg=C["muted"],
                       selectcolor=C["card2"], activebackground=C["card"],
                       font=("Segoe UI",10), cursor="hand2").pack(side=tk.LEFT)
        tk.Label(cb_fr, text="  (dataset/<ID>/)",
                 bg=C["card"], fg=C["border"], font=("Segoe UI",9)).pack(side=tk.LEFT)

        # progress bar
        reg_prog_var = tk.IntVar(value=0)
        reg_prog = ttk.Progressbar(rc2, variable=reg_prog_var, maximum=100, length=360)
        reg_prog.pack(pady=(4,8), fill=tk.X)

        rstat = tk.Label(rc2, text="", bg=C["card"], fg=C["green"],
                         font=("Segoe UI",9), wraplength=380, justify="left")
        rstat.pack(pady=(0,6))

        reg_btn = [None]  # mutable reference so do_reg can disable/enable

        def do_reg():
            name = flds["name"].get().strip()
            sid  = flds["id"].get().strip()
            s    = reg_s.get()
            c    = reg_c.get()
            if not all([name, sid, s, c]) or name == "e.g. Violina Saikia":
                rstat.config(text="❌  Fill all fields", fg=C["red"]); return
            db = load_db()
            if sid in db["students"]:
                rstat.config(text="❌  ID already exists", fg=C["red"]); return

            # save to db first
            db["students"][sid] = {
                "name": name, "class_key": f"{s}|{c}",
                "stream": s, "class": c,
                "registered_at": datetime.now().isoformat()
            }
            save_db(db)

            if not messagebox.askyesno("Capture Faces",
                                       f"Student '{name}' saved.\n\n"
                                       "Open camera now to capture 150 face images?\n"
                                       "• Only ONE face must be visible at a time\n"
                                       "• A 3-second countdown starts when face is detected\n\n"
                                       "(Click NO to capture later from All Students tab)"):
                rstat.config(text=f"✅  {name} registered. Use 📸 Capture Face Later to add face data.", fg=C["green"])
                for e in flds.values(): e.delete(0, tk.END)
                reg_prog_var.set(0)
                return

            if reg_btn[0]:
                reg_btn[0].config(state="disabled")
            rstat.config(text="📸  Camera opening…", fg=C["blue"])
            self.root.update_idletasks()

            try:
                import importlib, sys as _sys
                if "capture_and_train" in _sys.modules:
                    importlib.reload(_sys.modules["capture_and_train"])
                from capture_and_train import capture_and_train as _cap_train
                ok, msg = _cap_train(
                    sid, name, s, c,
                    save_images=save_var.get(),
                    progress_var=reg_prog_var,
                    status_label=rstat,
                    tk_root=self.root
                )
                if ok:
                    rstat.config(text="✅  Done! See below for file locations.", fg=C["green"])
                    messagebox.showinfo("Training Complete", msg)
                else:
                    rstat.config(text=f"❌  {msg}", fg=C["red"])
            except Exception as ex:
                import traceback
                rstat.config(text=f"❌  Error: {ex}", fg=C["red"])
                print(traceback.format_exc())
            finally:
                if reg_btn[0]:
                    reg_btn[0].config(state="normal")
                reg_prog_var.set(0)

            for e in flds.values(): e.delete(0, tk.END)

        btn = mkbtn(rc2, "📸  Register + Capture Faces", do_reg, w=30)
        btn.pack(pady=(8, 0))
        reg_btn[0] = btn

        # # Storage info card
        # info_card = mkcard(t2_inner, 28, 18)
        # info_card.pack(pady=(6, 20), padx=20, fill=tk.X)
        # tk.Label(info_card, text="📦  Where trained data is stored",
        #          bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
        # sep(info_card).pack(fill=tk.X, pady=(0,10))
        # for label_txt, val in [
        #     ("Model file",  os.path.join(BASE_DIR, "trainer.yml")),
        #     ("Label map",   os.path.join(BASE_DIR, "trainer_meta.json")),
        #     ("Face images", os.path.join(BASE_DIR, "dataset", "<StudentID>", "")),
        #     ("Attendance",  os.path.join(BASE_DIR, "attendance", "")),
        # ]:
        #     row_f = tk.Frame(info_card, bg=C["card"]); row_f.pack(fill=tk.X, pady=2)
        #     tk.Label(row_f, text=f"{label_txt}:", bg=C["card"], fg=C["muted"],
        #              font=("Segoe UI",10,"bold"), width=14, anchor="w").pack(side=tk.LEFT)
        #     tk.Label(row_f, text=val, bg=C["card"], fg=C["blue"],
        #              font=("Segoe UI",9), anchor="w").pack(side=tk.LEFT)

        # ── Tab 3: Import / Export ──
        t3 = tk.Frame(nb, bg=C["bg"])
        nb.add(t3, text="  Import / Export  ")
        t3_so, t3_inner = scroll_frame(t3)
        t3_so.pack(fill=tk.BOTH, expand=True)

        def _refresh_t3():
            for w in t3_inner.winfo_children(): w.destroy()

            tk.Label(t3_inner, text="📦  Import / Export",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(18,2), anchor="w")
            tk.Label(t3_inner,
                     text="Transfer student data and face encodings between machines.",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,10), anchor="w")
            sep(t3_inner).pack(fill=tk.X, padx=28, pady=(0,14))

            row3 = tk.Frame(t3_inner, bg=C["bg"])
            row3.pack(fill=tk.BOTH, padx=28, expand=True)
            row3.columnconfigure(0, weight=1)
            row3.columnconfigure(1, weight=1)

            # ── LEFT: Student CSV ──────────────────────────────────────
            csv_card = mkcard(row3, 22, 20)
            csv_card.grid(row=0, column=0, sticky="nsew", padx=(0,8), pady=4)
            tk.Label(csv_card, text="👥  Student List (CSV)",
                     bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
            tk.Label(csv_card,
                     text="Export/import the student registry (names, IDs, streams, classes).\n"
                          "Does NOT include face data — use the Face Encodings section for that.",
                     bg=C["card"], fg=C["muted"], font=FS, wraplength=340, justify="left").pack(anchor="w", pady=(0,12))
            sep(csv_card).pack(fill=tk.X, pady=(0,12))

            csv_st = tk.Label(csv_card, text="", bg=C["card"], fg=C["green"], font=FS)

            def exp_csv():
                db = load_db()
                rows = [{"ID":k,"Name":v.get("name"),"Stream":v.get("stream"),
                         "Class":v.get("class"),"Registered":v.get("registered_at","")[:10]}
                        for k,v in db.get("students",{}).items()]
                if not rows:
                    csv_st.config(text="❌  No students to export.", fg=C["red"]); return
                p = filedialog.asksaveasfilename(defaultextension=".csv",
                                                 filetypes=[("CSV","*.csv")],
                                                 title="Save Student List")
                if p:
                    pd.DataFrame(rows).to_csv(p, index=False)
                    csv_st.config(text=f"✅  Exported {len(rows)} students.", fg=C["green"])

            def imp_csv():
                p = filedialog.askopenfilename(filetypes=[("CSV","*.csv")],
                                               title="Open Student CSV")
                if not p: return
                try:
                    df = pd.read_csv(p)
                    db = load_db(); cnt = 0
                    for _, r in df.iterrows():
                        sid=str(r.get("ID","")).strip(); nm=str(r.get("Name","")).strip()
                        s=str(r.get("Stream","")).strip(); c=str(r.get("Class","")).strip()
                        if sid and nm and s and c:
                            db["students"][sid] = {"name":nm,"stream":s,"class":c,
                                                    "class_key":f"{s}|{c}",
                                                    "registered_at":datetime.now().isoformat()}
                            cnt += 1
                    save_db(db)
                    csv_st.config(text=f"✅  Imported {cnt} students.", fg=C["green"])
                    load_stu()
                except Exception as ex:
                    csv_st.config(text=f"❌  {ex}", fg=C["red"])

            mkbtn(csv_card, "⬇️  Export Student List", exp_csv, w=30).pack(pady=4, fill=tk.X)
            mkbtn(csv_card, "⬆️  Import Student List", imp_csv, w=30).pack(pady=4, fill=tk.X)
            csv_st.pack(pady=(6,0))

            # ── RIGHT: Face Encodings ──────────────────────────────────
            enc_card = mkcard(row3, 22, 20)
            enc_card.grid(row=0, column=1, sticky="nsew", padx=(8,0), pady=4)
            tk.Label(enc_card, text="🧠  Face Encodings (.pkl)",
                     bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
            tk.Label(enc_card,
                     text="Export face encodings from this machine and import them on another.\n"
                          "MERGE mode: adds new students without deleting existing ones.\n"
                          "REPLACE mode: overwrites all encodings with the imported file.",
                     bg=C["card"], fg=C["muted"], font=FS, wraplength=340, justify="left").pack(anchor="w", pady=(0,12))
            sep(enc_card).pack(fill=tk.X, pady=(0,12))

            enc_p = os.path.join(BASE_DIR, "face_encodings.pkl")
            enc_exists = os.path.exists(enc_p)

            # status line
            if enc_exists:
                try:
                    import pickle as _pk
                    with open(enc_p,"rb") as _f:
                        _d = _pk.load(_f)
                    tk.Label(enc_card,
                             text=f"📊  This machine: {len(_d)} student(s) trained",
                             bg=C["card"], fg=C["green"],
                             font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(0,10))
                except Exception:
                    pass
            else:
                tk.Label(enc_card, text="⚠️  No face_encodings.pkl on this machine yet.",
                         bg=C["card"], fg=C["orange"], font=FS).pack(anchor="w", pady=(0,10))

            enc_st = tk.Label(enc_card, text="", bg=C["card"], fg=C["green"], font=FS)

            def exp_enc():
                if not os.path.exists(enc_p):
                    enc_st.config(text="❌  No face_encodings.pkl found — train students first.", fg=C["red"]); return
                p = filedialog.asksaveasfilename(
                    defaultextension=".pkl",
                    filetypes=[("Pickle","*.pkl"),("All","*.*")],
                    initialfile="face_encodings_export.pkl",
                    title="Export Face Encodings")
                if p:
                    import shutil
                    shutil.copy2(enc_p, p)
                    try:
                        import pickle as _pk
                        with open(p,"rb") as _f: _d2 = _pk.load(_f)
                        enc_st.config(text=f"✅  Exported {len(_d2)} student(s) → {os.path.basename(p)}", fg=C["green"])
                    except Exception:
                        enc_st.config(text=f"✅  Exported → {os.path.basename(p)}", fg=C["green"])

            def imp_enc_merge():
                _imp_enc(merge=True)

            def imp_enc_replace():
                if not messagebox.askyesno("Replace?",
                    "REPLACE will delete ALL existing face encodings on this machine\n"
                    "and replace with the imported file.\n\nAre you sure?"):
                    return
                _imp_enc(merge=False)

            def _imp_enc(merge=True):
                p = filedialog.askopenfilename(
                    filetypes=[("Pickle","*.pkl"),("All","*.*")],
                    title="Import Face Encodings")
                if not p: return
                try:
                    import pickle as _pk
                    with open(p,"rb") as _f:
                        incoming = _pk.load(_f)
                    if not isinstance(incoming, dict):
                        enc_st.config(text="❌  Invalid file — not a valid encodings dict.", fg=C["red"]); return

                    if merge and os.path.exists(enc_p):
                        with open(enc_p,"rb") as _f:
                            existing = _pk.load(_f)
                        added = skipped = 0
                        for key, val in incoming.items():
                            if key in existing:
                                # Merge encodings lists (avoid duplicates by extending)
                                existing[key]["encodings"].extend(val["encodings"])
                                skipped += 1
                            else:
                                existing[key] = val
                                added += 1
                        with open(enc_p,"wb") as _f:
                            _pk.dump(existing, _f)
                        enc_st.config(
                            text=f"✅  Merged: {added} new + {skipped} updated student(s).",
                            fg=C["green"])
                    else:
                        import shutil
                        shutil.copy2(p, enc_p)
                        enc_st.config(
                            text=f"✅  Replaced with {len(incoming)} student(s) from file.",
                            fg=C["green"])

                    load_stu()   # refresh face tick marks
                    _refresh_t3()
                except Exception as ex:
                    enc_st.config(text=f"❌  {ex}", fg=C["red"])

            mkbtn(enc_card, "⬇️  Export Encodings",       exp_enc,      w=30).pack(pady=4, fill=tk.X)
            mkbtn(enc_card, "⬆️  Import & MERGE",          imp_enc_merge,   C["green"], w=30).pack(pady=4, fill=tk.X)
            mkbtn(enc_card, "⚠️  Import & REPLACE ALL",    imp_enc_replace, C["red"],   w=30).pack(pady=4, fill=tk.X)
            enc_st.pack(pady=(6,0))

            # ── BOTTOM: How-to guide ───────────────────────────────────
            guide = mkcard(t3_inner, 28, 18)
            guide.pack(fill=tk.X, padx=28, pady=(14,8))
            tk.Label(guide, text="📖  How to share face data between machines",
                     bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
            steps = [
                ("Step 1", "On Machine A (where faces are captured): click  ⬇️ Export Encodings  and save the .pkl file to a USB drive or shared folder."),
                ("Step 2", "On Machine B: click  ⬆️ Import & MERGE  and select the .pkl file. Existing students on Machine B are kept; new ones are added."),
                ("Step 3", "If both machines have different students captured, export from each and import on the other using MERGE — no data is lost."),
                ("Step 4", "Use REPLACE only when you want Machine B to use exactly what Machine A has, discarding anything captured on B."),
            ]
            for title, desc in steps:
                sf = tk.Frame(guide, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1,
                              padx=12, pady=8)
                sf.pack(fill=tk.X, pady=3)
                tk.Label(sf, text=title, bg=C["card2"], fg=C["accent"],
                         font=("Segoe UI",10,"bold"), width=8, anchor="w").pack(side=tk.LEFT)
                tk.Label(sf, text=desc, bg=C["card2"], fg=C["muted"],
                         font=FS, wraplength=660, justify="left").pack(side=tk.LEFT, padx=8)

        _refresh_t3()

        # ── Tab 4: Student Logins ──
        t4 = tk.Frame(nb, bg=C["bg"])
        nb.add(t4, text="  Student Logins  ")
        t4_so, t4_inner = scroll_frame(t4)
        t4_so.pack(fill=tk.BOTH, expand=True)

        def load_stu_logins():
            for w in t4_inner.winfo_children(): w.destroy()
            tk.Label(t4_inner, text="🔐  Student Login Accounts",
                     bg=C["bg"], fg=C["text"], font=FSH).pack(padx=20, pady=(16,4), anchor="w")
            tk.Label(t4_inner,
                     text="Create a login for registered students so they can access the Student portal.\n"
                          "Username = Student ID.  Set an initial password below.",
                     bg=C["bg"], fg=C["muted"], font=FS, wraplength=700, justify="left").pack(
                         padx=20, pady=(0,12), anchor="w")

            row4 = tk.Frame(t4_inner, bg=C["bg"]); row4.pack(fill=tk.BOTH, padx=20, expand=True)

            # add panel
            ap4 = mkcard(row4, 22, 20)
            ap4.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(ap4, text="Create Student Login", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            tk.Label(ap4, text="Select Student", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            db_now = load_db()
            us_now = load_users()
            all_stus = {sid: d for sid,d in db_now.get("students",{}).items()}
            no_login = [f"{sid} — {d['name']}" for sid,d in all_stus.items() if sid not in us_now]
            sl_pick = mkcb(ap4, no_login, 28); sl_pick.pack(pady=(3,12), fill=tk.X)
            tk.Label(ap4, text="Initial Password", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            sl_pw = mkentry(ap4, "min 6 chars", w=28, show="●"); sl_pw.pack(pady=(3,12), ipady=6, fill=tk.X)
            sl_st = tk.Label(ap4, text="", bg=C["card"], fg=C["green"], font=FS); sl_st.pack()
            def create_login():
                sel = sl_pick.get()
                if not sel: sl_st.config(text="❌  Select a student", fg=C["red"]); return
                sid2 = sel.split(" — ")[0]
                pw2  = sl_pw.get()
                if len(pw2)<6: sl_st.config(text="❌  Min 6 chars", fg=C["red"]); return
                us2 = load_users()
                if sid2 in us2: sl_st.config(text="❌  Login already exists", fg=C["red"]); return
                db2 = load_db(); sd2 = db2["students"].get(sid2,{})
                us2[sid2] = {
                    "password": _hash(pw2), "role": "student",
                    "name": sd2.get("name", sid2),
                    "email": "", "phone": "",
                    "created_at": datetime.now().isoformat()
                }
                save_users(us2)
                sl_st.config(text=f"✅  Login created for {sid2}", fg=C["green"])
                load_stu_logins()
            mkbtn(ap4, "➕  Create Login", create_login, w=26).pack(pady=(8,0))

            # list panel
            lp4 = mkcard(row4, 22, 20)
            lp4.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(lp4, text="Existing Student Logins", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            us_check = load_users()
            db_check = load_db()
            stu_logins = {u:d for u,d in us_check.items() if d.get("role")=="student"}
            if not stu_logins:
                tk.Label(lp4, text="No student logins yet.", bg=C["card"],
                         fg=C["muted"], font=FB).pack(pady=20)
            for uid, ud2 in stu_logins.items():
                sf = tk.Frame(lp4, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1,
                              padx=12, pady=8)
                sf.pack(fill=tk.X, pady=3)
                sd3 = db_check.get("students",{}).get(uid,{})
                tk.Label(sf, text=ud2.get("name",uid), bg=C["card2"],
                         fg=C["text"], font=("Segoe UI",11,"bold")).pack(side=tk.LEFT, anchor="w")
                tk.Label(sf, text=f"  @{uid}  •  {sd3.get('stream','?')}/{sd3.get('class','?')}",
                         bg=C["card2"], fg=C["muted"], font=FS).pack(side=tk.LEFT, anchor="w")
                def del_sl(u=uid):
                    if messagebox.askyesno("Remove","Remove login for student "+u+"?"):
                        us3=load_users(); us3.pop(u,None); save_users(us3); load_stu_logins()
                def reset_sl(u=uid):
                    pw3=simpledialog.askstring("Reset Password",f"New password for {u}:",show="*")
                    if pw3 and len(pw3)>=6:
                        us3=load_users(); us3[u]["password"]=_hash(pw3); save_users(us3)
                        messagebox.showinfo("Done",f"Password reset for {u}")
                    elif pw3:
                        messagebox.showerror("Error","Min 6 characters")
                act4 = tk.Frame(sf, bg=C["card2"]); act4.pack(side=tk.RIGHT)
                mkbtn(act4,"🔑 Reset PW", reset_sl, C["blue"]).pack(side=tk.LEFT, padx=2)
                mkbtn(act4,"🗑", del_sl, C["red"], w=3).pack(side=tk.LEFT, padx=2)

        def on_tab_change(e=None):
            idx = nb.index(nb.select())
            if idx == 0: load_stu()
            elif idx == 3: load_stu_logins()
        nb.bind("<<NotebookTabChanged>>", on_tab_change)
        page.on_show = lambda: load_stu()
        return page

    # ─── ATTENDANCE ─────────────────────────────────────────────
    def _pg_attendance(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📸  Take Attendance",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            tk.Label(inner,
                     text="Two windows open when attendance starts:\n"
                          "  1.Camera feed with live face recognition boxes\n"
                          "  2.Live attendance panel showing Present / Absent in real-time",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,10), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, weight=2)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            # ── left: controls ────────────────────────────────────────
            cf = mkcard(row, 32, 28)
            cf.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            db = load_db()
            tk.Label(cf, text="Stream", bg=C["card"], fg=C["muted"], font=FB).pack(anchor="w")
            a_s = mkcb(cf, list(db["streams"].keys()), 28)
            a_s.pack(pady=(3,12), fill=tk.X)
            tk.Label(cf, text="Class", bg=C["card"], fg=C["muted"], font=FB).pack(anchor="w")
            a_c = mkcb(cf, [], 28)
            a_c.pack(pady=(3,12), fill=tk.X)
            tk.Label(cf, text="Subject", bg=C["card"], fg=C["muted"], font=FB).pack(anchor="w")
            a_sub = mkcb(cf, [], 28)
            a_sub.pack(pady=(3,16), fill=tk.X)

            def on_as(e):
                db = load_db()
                a_c["values"] = list(db["streams"].get(a_s.get(),{}).get("classes",{}).keys())
                a_c.set("")
            def on_ac(e):
                db = load_db()
                a_sub["values"] = db["streams"].get(a_s.get(),{}) \
                                              .get("classes",{}) \
                                              .get(a_c.get(),{}) \
                                              .get("subjects",[])
                a_sub.set("")
            a_s.bind("<<ComboboxSelected>>", on_as)
            a_c.bind("<<ComboboxSelected>>", on_ac)

            st = tk.Label(cf, text="", bg=C["card"], fg=C["green"], font=FS)
            st.pack(pady=(0,8), fill=tk.X)

            def start():
                s = a_s.get(); c = a_c.get(); sub = a_sub.get()
                if not all([s, c, sub]):
                    st.config(text="❌  Select all fields", fg=C["red"]); return
                enc_path = os.path.join(BASE_DIR, "face_encodings.pkl")
                if not os.path.exists(enc_path):
                    st.config(text="❌  Model not trained yet — register students first",
                              fg=C["red"]); return
                st.config(text="📸  Opening camera…", fg=C["green"])
                subprocess.Popen([sys.executable,
                                  os.path.join(BASE_DIR, "take_attendance.py"),
                                  s, c, sub])

            mkbtn(cf, "▶  Start Attendance", start, w=28).pack(pady=4)
            mkbtn(cf, "🔄  Retrain Model (standalone GUI)",
                  lambda: subprocess.Popen([sys.executable,
                                            os.path.join(BASE_DIR, "capture_and_train.py")]),
                  C["purple"], w=28).pack(pady=4)

            # ── right: storage info card ──────────────────────────────
            # ic = mkcard(row, 28, 24)
            # ic.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            # tk.Label(ic, text="📦  Trained Data Storage",
            #          bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
            # sep(ic).pack(fill=tk.X, pady=(0,10))

            # model_exists = os.path.exists(os.path.join(BASE_DIR, "trainer.yml"))
            # meta_exists  = os.path.exists(os.path.join(BASE_DIR, "trainer_meta.json"))

            # # model status
            # for lbl_txt, path, exists in [
            #     ("LBPH Model",  os.path.join(BASE_DIR, "trainer.yml"),        model_exists),
            #     ("Label Map",   os.path.join(BASE_DIR, "trainer_meta.json"),  meta_exists),
            #     ("Face Images", os.path.join(BASE_DIR, "dataset", ""),        True),
            #     ("Attendance",  os.path.join(BASE_DIR, "attendance", ""),     True),
            # ]:
            #     rf = tk.Frame(ic, bg=C["card2"],
            #                   highlightbackground=C["border"], highlightthickness=1,
            #                   padx=10, pady=6)
            #     rf.pack(fill=tk.X, pady=3)
            #     dot_col = C["green"] if exists else C["red"]
            #     dot_txt = "●  " + ("EXISTS" if exists else "NOT FOUND")
            #     tk.Label(rf, text=lbl_txt, bg=C["card2"], fg=C["text"],
            #              font=("Segoe UI",10,"bold"), width=14, anchor="w").pack(side=tk.LEFT)
            #     tk.Label(rf, text=dot_txt, bg=C["card2"], fg=dot_col,
            #              font=("Segoe UI",9), width=12).pack(side=tk.LEFT)
            #     tk.Label(rf, text=path, bg=C["card2"], fg=C["blue"],
            #              font=("Segoe UI",8), anchor="w", wraplength=300).pack(side=tk.LEFT)

            # students in model
            enc_path = os.path.join(BASE_DIR, "face_encodings.pkl")
            enc_exists = os.path.exists(enc_path)
            if enc_exists:
                try:
                    import pickle
                    with open(enc_path, "rb") as f:
                        enc_data = pickle.load(f)
                    n_stu = len(enc_data)
                    tk.Label(ic, text=f"\n  👥  {n_stu} student(s) trained in model",
                             bg=C["card"], fg=C["green"],
                             font=("Segoe UI",11,"bold")).pack(anchor="w")
                except Exception:
                    pass
            else:
                tk.Label(ic, text="\n  ⚠️  No model found — please register students first.",
                         bg=C["card"], fg=C["orange"],
                         font=("Segoe UI",10)).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── VIEW RECORDS ───────────────────────────────────────────
    def _pg_records(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        tk.Label(page, text="📊  Attendance Records",
                 bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,6), anchor="w")
        fr = tk.Frame(page, bg=C["bg"])
        fr.pack(fill=tk.X, padx=28, pady=4)
        db = load_db()
        f_s = mkcb(fr, list(db["streams"].keys()), 17)
        f_s.pack(side=tk.LEFT, padx=3)
        f_c = mkcb(fr, [], 17); f_c.pack(side=tk.LEFT, padx=3)
        f_sub = mkcb(fr, [], 17); f_sub.pack(side=tk.LEFT, padx=3)
        f_d = mkcb(fr, [], 15); f_d.pack(side=tk.LEFT, padx=3)
        mkbtn(fr,"🔄 Load", None, w=8).pack(side=tk.LEFT, padx=3)

        tvf = tk.Frame(page, bg=C["bg"])
        tvf.pack(fill=tk.BOTH, expand=True, padx=28, pady=6)
        cols = ["StudentID","Name","Stream","Class","Subject","Time","Confidence"]
        tv, tsb = mktree(tvf, cols, h=18)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)
        summ = tk.Label(page, text="", bg=C["bg"], fg=C["muted"], font=FS)
        summ.pack(padx=28, anchor="w")

        def on_fs(e):
            db = load_db()
            f_c["values"] = list(db["streams"].get(f_s.get(),{}).get("classes",{}).keys())
            f_c.set(""); f_sub.set(""); f_d.set("")
        def on_fc(e):
            p = os.path.join(BASE_DIR,"attendance", f_s.get(), f_c.get())
            f_sub["values"] = sorted(os.listdir(p)) if os.path.exists(p) else []
            f_sub.set(""); f_d.set("")
        def on_fsub(e):
            p = os.path.join(BASE_DIR,"attendance", f_s.get(), f_c.get(), f_sub.get())
            f_d["values"] = sorted([x[:-4] for x in os.listdir(p) if x.endswith(".csv")],
                                    reverse=True) if os.path.exists(p) else []
            f_d.set("")
        def load_rec(e=None):
            tv.delete(*tv.get_children())
            s=f_s.get(); c=f_c.get(); sub=f_sub.get(); d=f_d.get()
            if not all([s,c,sub,d]): return
            fp = os.path.join(BASE_DIR,"attendance",s,c,sub,f"{d}.csv")
            if not os.path.exists(fp): return
            try:
                df = pd.read_csv(fp)
                for _, r in df.iterrows():
                    tv.insert("","end", values=[str(r.get(col,"")) for col in cols])
                summ.config(text=f"  {len(df)} records  •  {fp}")
            except: pass
        def exp_rec():
            s=f_s.get(); c=f_c.get(); sub=f_sub.get(); d=f_d.get()
            if not all([s,c,sub,d]): messagebox.showinfo("Select","Select all filters"); return
            fp = os.path.join(BASE_DIR,"attendance",s,c,sub,f"{d}.csv")
            dest = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
            if dest and os.path.exists(fp):
                import shutil; shutil.copy(fp,dest); messagebox.showinfo("Exported",f"Saved: {dest}")

        f_s.bind("<<ComboboxSelected>>", on_fs)
        f_c.bind("<<ComboboxSelected>>", on_fc)
        f_sub.bind("<<ComboboxSelected>>", on_fsub)
        f_d.bind("<<ComboboxSelected>>", load_rec)

        # wire the Load button properly
        for w in fr.winfo_children():
            if isinstance(w, tk.Button): w.config(command=load_rec)

        br = tk.Frame(page, bg=C["bg"])
        br.pack(fill=tk.X, padx=28, pady=4)
        mkbtn(br,"⬇️  Export CSV", exp_rec, C["blue"]).pack(side=tk.LEFT, padx=4)

        def on_show():
            db = load_db()
            f_s["values"] = list(db["streams"].keys())
        page.on_show = on_show
        return page

    # ─── TEACHERS ───────────────────────────────────────────────
    def _pg_teachers(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="👨‍🏫  Teacher Management",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1, minsize=400)
            row.columnconfigure(1, weight=1, minsize=400)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            # ── LEFT PANEL: Add New Teacher ──────────────────────────
            ap = mkcard(row, 16, 18)
            ap.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(ap, text="Add New Teacher", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            flds = {}
            for lbl,key,ph,sh in [("Full Name","name","Dr. Smith",None),
                                    ("Username","uname","login username",None),
                                    ("Password","pass","initial password","●"),
                                    ("Email","email","teacher@edu",""),
                                    ("Phone","phone","10 digits","")]:
                tk.Label(ap, text=lbl, bg=C["card"], fg=C["muted"],
                         font=("Segoe UI",10)).pack(anchor="w")
                e = mkentry(ap, ph, w=26, show=sh)
                e.pack(pady=(3,10), ipady=6, fill=tk.X)
                flds[key] = e

            # ── subject list being built for the new teacher ──
            sep(ap).pack(fill=tk.X, pady=(4,10))
            tk.Label(ap, text="📚  Subject Assignments  (add one or more)",
                     bg=C["card"], fg=C["accent"], font=("Segoe UI",10,"bold")).pack(anchor="w", pady=(0,8))

            pending_assigns = []

            pill_frame = tk.Frame(ap, bg=C["card"]); pill_frame.pack(fill=tk.X, pady=(0,6))

            def redraw_pills():
                for w in pill_frame.winfo_children(): w.destroy()
                if not pending_assigns:
                    tk.Label(pill_frame, text="No subjects added yet.",
                             bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
                    return
                for idx, a in enumerate(pending_assigns):
                    pf = tk.Frame(pill_frame, bg=C["card2"],
                                  highlightbackground=C["accent"], highlightthickness=1,
                                  padx=8, pady=4)
                    pf.pack(fill=tk.X, pady=2)
                    tk.Label(pf, text=f"📘 {a['stream']} / {a['class']} / {a['subject']}",
                             bg=C["card2"], fg=C["text"], font=FS).pack(side=tk.LEFT)
                    def rm(i=idx):
                        pending_assigns.pop(i); redraw_pills()
                    tk.Button(pf, text="✕", command=rm, bg=C["card2"], fg=C["red"],
                              font=("Segoe UI",8,"bold"), relief="flat",
                              cursor="hand2", padx=4).pack(side=tk.RIGHT)

            redraw_pills()

            db_now = load_db()
            tk.Label(ap, text="Stream", bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(anchor="w", pady=(6,0))
            ts = mkcb(ap, list(db_now["streams"].keys()), 24); ts.pack(pady=(3,6), fill=tk.X)
            tk.Label(ap, text="Class", bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(anchor="w")
            tc = mkcb(ap, [], 24); tc.pack(pady=(3,6), fill=tk.X)
            tk.Label(ap, text="Subject", bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(anchor="w")
            tsub = mkcb(ap, [], 24); tsub.pack(pady=(3,8), fill=tk.X)

            def on_ts(e):
                db = load_db()
                tc["values"] = list(db["streams"].get(ts.get(),{}).get("classes",{}).keys())
                tc.set(""); tsub.set(""); tsub["values"] = []
            def on_tc(e):
                db = load_db()
                tsub["values"] = db["streams"].get(ts.get(),{}).get("classes",{}).get(tc.get(),{}).get("subjects",[])
                tsub.set("")
            ts.bind("<<ComboboxSelected>>", on_ts)
            tc.bind("<<ComboboxSelected>>", on_tc)

            add_sub_st = tk.Label(ap, text="", bg=C["card"], fg=C["orange"], font=FS)
            add_sub_st.pack()

            def add_subject_to_list():
                s=ts.get(); c=tc.get(); sub=tsub.get()
                if not (s and c and sub):
                    add_sub_st.config(text="⚠️  Select stream, class & subject", fg=C["orange"]); return
                entry = {"stream":s,"class":c,"subject":sub}
                if entry in pending_assigns:
                    add_sub_st.config(text="⚠️  Already added", fg=C["orange"]); return
                pending_assigns.append(entry)
                redraw_pills()
                ts.set(""); tc.set(""); tsub.set("")
                tc["values"] = []; tsub["values"] = []
                add_sub_st.config(text=f"✅  {sub} added to list", fg=C["green"])

            mkbtn(ap, "➕  Add This Subject", add_subject_to_list,
                  bg=C["card2"], fg=C["text"]).pack(fill=tk.X, pady=(0,8))
            sep(ap).pack(fill=tk.X, pady=(0,10))

            st = tk.Label(ap, text="", bg=C["card"], fg=C["green"], font=FS); st.pack()

            def add_t():
                nm=flds["name"].get().strip(); un=flds["uname"].get().strip()
                pw=flds["pass"].get(); em=flds["email"].get().strip()
                ph=flds["phone"].get().strip()
                if not all([nm, un, pw]):
                    st.config(text="❌  Fill Name, Username & Password", fg=C["red"]); return
                us = load_users()
                if un in us:
                    st.config(text="❌  Username taken", fg=C["red"]); return
                us[un] = {"password":_hash(pw),"role":"teacher","name":nm,
                           "email":em,"phone":ph,"assigned":list(pending_assigns),
                           "created_at":datetime.now().isoformat()}
                save_users(us)
                st.config(text=f"✅  {nm} added with {len(pending_assigns)} subject(s)!", fg=C["green"])
                for e in flds.values(): e.delete(0,tk.END)
                pending_assigns.clear(); redraw_pills()
                refresh()

            mkbtn(ap, "✔  Save Teacher", add_t).pack(fill=tk.X)

            # ── RIGHT PANEL: Current Teachers ───────────────────────
            tp = mkcard(row, 16, 18)
            tp.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(tp, text="Current Teachers", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            users = load_users()
            teachers = {u:d for u,d in users.items() if d.get("role")=="teacher"}
            if not teachers:
                tk.Label(tp, text="No teachers added yet.", bg=C["card"],
                         fg=C["muted"], font=FB).pack(pady=20)

            for un, ud in teachers.items():
                tf = tk.Frame(tp, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1,
                              padx=14, pady=10)
                tf.pack(fill=tk.X, pady=4)

                top_row = tk.Frame(tf, bg=C["card2"]); top_row.pack(fill=tk.X)
                if _PIL:
                    try:
                        av = make_avatar_photo(ud["name"], 38)
                        if av:
                            al = tk.Label(top_row, image=av, bg=C["card2"])
                            al.image = av; al.pack(side=tk.LEFT, padx=(0,10))
                    except: pass
                info = tk.Frame(top_row, bg=C["card2"])
                info.pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Label(info, text=ud["name"], bg=C["card2"], fg=C["text"],
                         font=("Segoe UI",12,"bold")).pack(anchor="w")
                tk.Label(info, text=f"@{un}  •  {ud.get('email','')}",
                         bg=C["card2"], fg=C["muted"], font=FS).pack(anchor="w")

                act = tk.Frame(top_row, bg=C["card2"])
                act.pack(side=tk.RIGHT, anchor="n")

                def del_t(u=un):
                    if messagebox.askyesno("Delete", f"Remove teacher '{u}'?"):
                        us=load_users(); us.pop(u,None); save_users(us); refresh()

                mkbtn(act, "🗑", del_t, C["red"], w=3).pack(pady=(0,4))

                assigns = ud.get("assigned", [])
                sub_hdr = tk.Frame(tf, bg=C["card2"]); sub_hdr.pack(fill=tk.X, pady=(6,2))
                tk.Label(sub_hdr, text=f"📚  {len(assigns)} Subject(s):",
                         bg=C["card2"], fg=C["muted"], font=FS).pack(side=tk.LEFT)

                for idx, a in enumerate(assigns):
                    af = tk.Frame(tf, bg=C["card"],
                                  highlightbackground=C["accent"], highlightthickness=1,
                                  padx=8, pady=3)
                    af.pack(fill=tk.X, pady=1)
                    tk.Label(af,
                             text=f"📘 {a.get('stream','?')} / {a.get('class','?')} / {a.get('subject','?')}",
                             bg=C["card"], fg=C["blue"], font=FS).pack(side=tk.LEFT)
                    def rm_assign(u=un, i=idx):
                        us2 = load_users()
                        if u in us2:
                            lst = us2[u].get("assigned", [])
                            if 0 <= i < len(lst):
                                lst.pop(i)
                                us2[u]["assigned"] = lst
                                save_users(us2)
                        refresh()
                    tk.Button(af, text="✕", command=rm_assign,
                              bg=C["card"], fg=C["red"],
                              font=("Segoe UI",8,"bold"), relief="flat",
                              cursor="hand2", padx=4).pack(side=tk.RIGHT)

                # ── inline "Add Subject" row for existing teacher ──
                add_row = tk.Frame(tf, bg=C["card2"]); add_row.pack(fill=tk.X, pady=(6,0))
                db2 = load_db()
                et_s   = mkcb(add_row, list(db2["streams"].keys()), 12)
                et_s.pack(side=tk.LEFT, padx=(0,3))
                et_c   = mkcb(add_row, [], 12)
                et_c.pack(side=tk.LEFT, padx=(0,3))
                et_sub = mkcb(add_row, [], 12)
                et_sub.pack(side=tk.LEFT, padx=(0,4))
                add_st = tk.Label(add_row, text="", bg=C["card2"], fg=C["green"], font=FS)
                add_st.pack(side=tk.LEFT, padx=4)

                def on_ets(e, s_cb=et_s, c_cb=et_c, sub_cb=et_sub):
                    db3 = load_db()
                    c_cb["values"] = list(db3["streams"].get(s_cb.get(),{}).get("classes",{}).keys())
                    c_cb.set(""); sub_cb.set(""); sub_cb["values"] = []
                def on_etc(e, s_cb=et_s, c_cb=et_c, sub_cb=et_sub):
                    db3 = load_db()
                    sub_cb["values"] = db3["streams"].get(s_cb.get(),{}).get("classes",{}).get(c_cb.get(),{}).get("subjects",[])
                    sub_cb.set("")
                et_s.bind("<<ComboboxSelected>>", on_ets)
                et_c.bind("<<ComboboxSelected>>", on_etc)

                def do_add_sub(u=un, s_cb=et_s, c_cb=et_c, sub_cb=et_sub, lbl=add_st):
                    s2=s_cb.get(); c2=c_cb.get(); sub2=sub_cb.get()
                    if not (s2 and c2 and sub2):
                        lbl.config(text="⚠️ Select all", fg=C["orange"]); return
                    us2=load_users()
                    if u not in us2: return
                    cur = us2[u].get("assigned",[])
                    entry2 = {"stream":s2,"class":c2,"subject":sub2}
                    if entry2 in cur:
                        lbl.config(text="Already assigned", fg=C["orange"]); return
                    cur.append(entry2)
                    us2[u]["assigned"] = cur
                    save_users(us2)
                    refresh()

                mkbtn(add_row, "➕", do_add_sub, bg=C["green"], fg=C["bg"], w=3).pack(side=tk.LEFT)

        page.on_show = refresh
        return page

    # ─── NOTICES ────────────────────────────────────────────────
    def _pg_notices(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📣  Announcements & Notices",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1, minsize=380)
            row.columnconfigure(1, weight=1, minsize=380)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            pp = mkcard(row, 16, 18)
            pp.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(pp, text="Post Notice", bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            tk.Label(pp, text="Title", bg=C["card"], fg=C["muted"], font=("Segoe UI",10)).pack(anchor="w")
            te = mkentry(pp, "Notice title…", w=28)
            te.pack(pady=(3,10), ipady=6, fill=tk.X)
            tk.Label(pp, text="Category", bg=C["card"], fg=C["muted"], font=("Segoe UI",10)).pack(anchor="w")
            cat = mkcb(pp, ["General","Academic","Holiday","Exam","Event","Urgent"], 26)
            cat.current(0); cat.pack(pady=(3,10), fill=tk.X)
            tk.Label(pp, text="Audience", bg=C["card"], fg=C["muted"], font=("Segoe UI",10)).pack(anchor="w")
            aud = mkcb(pp, ["All","Teachers Only","Students Only"], 26)
            aud.current(0); aud.pack(pady=(3,10), fill=tk.X)
            tk.Label(pp, text="Message", bg=C["card"], fg=C["muted"], font=("Segoe UI",10)).pack(anchor="w")
            mt = tk.Text(pp, bg=C["card2"], fg=C["text"], font=FB,
                         width=28, height=5, relief="flat", insertbackground=C["accent"])
            mt.pack(pady=(3,14), fill=tk.X)
            st = tk.Label(pp, text="", bg=C["card"], fg=C["green"], font=FS); st.pack()
            def post():
                t=te.get().strip(); msg=mt.get("1.0",tk.END).strip()
                if not t or t=="Notice title…": st.config(text="❌  Enter title",fg=C["red"]); return
                ns = load_notices()
                ns.append({"title":t,"message":msg,"category":cat.get(),
                            "audience": aud.get(),
                            "author":self.cur_data["name"],
                            "date":datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "id":int(datetime.now().timestamp())})
                save_notices(ns)
                te.delete(0,tk.END); mt.delete("1.0",tk.END)
                st.config(text="✅  Posted!", fg=C["green"]); refresh()
            mkbtn(pp,"📣  Post Notice", post).pack(fill=tk.X)

            nl = mkcard(row, 16, 18)
            nl.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(nl, text="Posted Notices", bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            cat_col = {"General":C["muted"],"Academic":C["blue"],"Holiday":C["green"],
                       "Exam":C["red"],"Event":C["purple"],"Urgent":C["orange"]}
            aud_col = {"All":C["green"],"Teachers Only":C["blue"],"Students Only":C["purple"]}
            for n in load_notices()[::-1]:
                nf = tk.Frame(nl, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1,
                              padx=14, pady=10)
                nf.pack(fill=tk.X, pady=3)
                hr = tk.Frame(nf, bg=C["card2"]); hr.pack(fill=tk.X)
                col = cat_col.get(n.get("category","General"), C["muted"])
                tk.Label(hr, text=f"  {n.get('category','')}  ", bg=col,
                         fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, pady=2)
                aud_txt = n.get("audience","All")
                ac = aud_col.get(aud_txt, C["muted"])
                tk.Label(hr, text=f"  👁 {aud_txt}  ", bg=ac,
                         fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, padx=4, pady=2)
                tk.Label(hr, text=n.get("title",""), bg=C["card2"], fg=C["text"],
                         font=("Segoe UI",12,"bold")).pack(side=tk.LEFT, padx=8)
                def del_n(nid=n.get("id")):
                    ns=[x for x in load_notices() if x.get("id")!=nid]
                    save_notices(ns); refresh()
                mkbtn(hr,"🗑", del_n, C["red"], w=3).pack(side=tk.RIGHT)
                tk.Label(nf, text=n.get("message","")[:120], bg=C["card2"],
                         fg=C["muted"], font=FS, wraplength=380, justify="left").pack(anchor="w", pady=(4,0))
                tk.Label(nf, text=f"By {n.get('author','')}  •  {n.get('date','')}",
                         bg=C["card2"], fg=C["border"], font=FS).pack(anchor="w", pady=(2,0))

        page.on_show = refresh
        return page

    # ─── TIMETABLE ──────────────────────────────────────────────
    def _pg_timetable(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)
        DAYS  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
        SLOTS = ["9:00-10:00","10:00-11:00","11:00-12:00",
                 "12:00-1:00","1:00-2:00","2:00-3:00","3:00-4:00"]

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📅  Timetable Management",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            ctrl = tk.Frame(inner, bg=C["bg"])
            ctrl.pack(fill=tk.X, padx=28, pady=(0,10))
            tk.Label(ctrl, text="Stream:", bg=C["bg"], fg=C["muted"], font=FB).pack(side=tk.LEFT)
            db = load_db()
            tt_s = mkcb(ctrl, list(db["streams"].keys()), 18); tt_s.pack(side=tk.LEFT, padx=8)
            tk.Label(ctrl, text="Class:", bg=C["bg"], fg=C["muted"], font=FB).pack(side=tk.LEFT)
            tt_c = mkcb(ctrl, [], 18); tt_c.pack(side=tk.LEFT, padx=8)
            gf_ref = [None]

            def on_ts(e):
                db = load_db()
                tt_c["values"] = list(db["streams"].get(tt_s.get(),{}).get("classes",{}).keys())
                tt_c.set("")
            def show_grid(e=None):
                if gf_ref[0]: gf_ref[0].destroy()
                s=tt_s.get(); c=tt_c.get()
                if not s or not c: return
                key = f"{s}|{c}"
                data = load_timetable().get(key,{})
                gf = tk.Frame(inner, bg=C["bg"])
                gf.pack(fill=tk.BOTH, padx=28, pady=4)
                gf_ref[0] = gf
                tk.Label(gf, text="", bg=C["card2"], width=12, pady=6).grid(row=0,column=0)
                for ci, day in enumerate(DAYS):
                    tk.Label(gf, text=day, bg=C["accent"], fg=C["bg"],
                             font=("Segoe UI",9,"bold"), width=14, pady=6).grid(row=0,column=ci+1,padx=1,pady=1)
                cells = {}
                for ri, slot in enumerate(SLOTS):
                    tk.Label(gf, text=slot, bg=C["card2"], fg=C["muted"],
                             font=("Segoe UI",8), width=12, pady=6).grid(row=ri+1,column=0,padx=1,pady=1)
                    for ci, day in enumerate(DAYS):
                        val = data.get(day,{}).get(slot,"")
                        e = tk.Entry(gf, font=("Segoe UI",9), bg=C["card"],
                                     fg=C["text"], relief="flat", width=14,
                                     insertbackground=C["accent"])
                        e.insert(0,val)
                        e.grid(row=ri+1,column=ci+1,padx=1,pady=1,ipady=5)
                        cells[(day,slot)] = e
                def save_tt():
                    tt = load_timetable()
                    tt[key] = {}
                    for (day,slot),e in cells.items():
                        v = e.get().strip()
                        if v: tt[key].setdefault(day,{})[slot] = v
                    save_timetable(tt)
                    messagebox.showinfo("Saved","Timetable saved!")
                mkbtn(gf,"💾  Save Timetable", save_tt, w=20).grid(
                    row=len(SLOTS)+1, columnspan=len(DAYS)+1, pady=10)

            tt_s.bind("<<ComboboxSelected>>", on_ts)
            tt_c.bind("<<ComboboxSelected>>", show_grid)

        page.on_show = refresh
        return page

    # ─── LEAVE REQUESTS ─────────────────────────────────────────
    def _pg_leaves(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="✉️  Leave Requests",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            leaves = load_leaves()[::-1]
            if not leaves:
                tk.Label(inner, text="No leave requests yet.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=40)
                return
            sc = {"Pending":C["orange"],"Approved":C["green"],"Rejected":C["red"]}
            for lv in leaves:
                lf = mkcard(inner, 20, 14)
                lf.pack(fill=tk.X, padx=28, pady=4)
                hr = tk.Frame(lf, bg=C["card"]); hr.pack(fill=tk.X)
                col = sc.get(lv.get("status","Pending"), C["orange"])
                tk.Label(hr, text=f"  {lv.get('status','Pending')}  ",
                         bg=col, fg=C["bg"], font=("Segoe UI",9,"bold")).pack(side=tk.LEFT)
                tk.Label(hr, text=f"{lv.get('teacher_name','')} — {lv.get('subject','')}",
                         bg=C["card"], fg=C["text"],
                         font=("Segoe UI",12,"bold")).pack(side=tk.LEFT, padx=10)
                tk.Label(hr, text=lv.get("date",""), bg=C["card"],
                         fg=C["muted"], font=FS).pack(side=tk.RIGHT)
                tk.Label(lf, text=f"📅 {lv.get('from_date','')} → {lv.get('to_date','')}",
                         bg=C["card"], fg=C["blue"], font=FB).pack(anchor="w", pady=(6,2))
                tk.Label(lf, text=lv.get("reason",""), bg=C["card"],
                         fg=C["muted"], font=FB, wraplength=580, justify="left").pack(anchor="w")
                if lv.get("status","Pending") == "Pending":
                    ar = tk.Frame(lf, bg=C["card"]); ar.pack(anchor="w", pady=(8,0))
                    def app(lid=lv.get("id")):
                        ls=load_leaves()
                        for l in ls:
                            if l.get("id")==lid: l["status"]="Approved"
                        save_leaves(ls); refresh()
                    def rej(lid=lv.get("id")):
                        ls=load_leaves()
                        for l in ls:
                            if l.get("id")==lid: l["status"]="Rejected"
                        save_leaves(ls); refresh()
                    mkbtn(ar,"✅  Approve", app, C["green"]).pack(side=tk.LEFT, padx=4)
                    mkbtn(ar,"❌  Reject",  rej, C["red"]).pack(side=tk.LEFT, padx=4)

        page.on_show = refresh
        return page

    # ─── EDIT / DELETE ──────────────────────────────────────────
    def _pg_edit(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="✏️  Edit & Delete Records",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, weight=2)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            ep = mkcard(row, 24, 22)
            ep.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(ep, text="Edit Attendance Record", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            db = load_db()
            for lbl, ref_name in [("Stream","e_s"),("Class","e_c"),("Subject","e_sub"),("Date","e_d")]:
                tk.Label(ep, text=lbl, bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            e_s = mkcb(ep, list(db["streams"].keys()), 24); e_s.pack(pady=(2,8), fill=tk.X)
            e_c = mkcb(ep, [], 24); e_c.pack(pady=(2,8), fill=tk.X)
            e_sub = mkcb(ep, [], 24); e_sub.pack(pady=(2,8), fill=tk.X)
            e_d = mkcb(ep, [], 24); e_d.pack(pady=(2,8), fill=tk.X)

            def es(ev):
                db=load_db()
                e_c["values"]=list(db["streams"].get(e_s.get(),{}).get("classes",{}).keys())
            def ec(ev):
                p=os.path.join(BASE_DIR,"attendance",e_s.get(),e_c.get())
                e_sub["values"]=sorted(os.listdir(p)) if os.path.exists(p) else []
            def esub(ev):
                p=os.path.join(BASE_DIR,"attendance",e_s.get(),e_c.get(),e_sub.get())
                e_d["values"]=sorted([x[:-4] for x in os.listdir(p) if x.endswith(".csv")],
                                      reverse=True) if os.path.exists(p) else []
            e_s.bind("<<ComboboxSelected>>", es)
            e_c.bind("<<ComboboxSelected>>", ec)
            e_sub.bind("<<ComboboxSelected>>", esub)

            tvf = tk.Frame(ep, bg=C["card"])
            tvf.pack(fill=tk.BOTH, expand=True, pady=6)
            ecols = ["StudentID","Name","Time","Confidence"]
            etv, esb2 = mktree(tvf, ecols, h=9)
            etv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            esb2.pack(side=tk.RIGHT, fill=tk.Y)
            _ef = [None]

            def load_e(ev=None):
                etv.delete(*etv.get_children())
                s=e_s.get();c=e_c.get();sub=e_sub.get();d=e_d.get()
                if not all([s,c,sub,d]): return
                fp=os.path.join(BASE_DIR,"attendance",s,c,sub,f"{d}.csv")
                _ef[0]=fp
                if os.path.exists(fp):
                    df=pd.read_csv(fp)
                    for _,r in df.iterrows():
                        etv.insert("","end",values=(r.get("StudentID",""),r.get("Name",""),
                                                     r.get("Time",""),r.get("Confidence","")))
            e_d.bind("<<ComboboxSelected>>", load_e)

            def del_r():
                sel=etv.selection()
                if not sel or not _ef[0]: return
                sid=etv.item(sel[0])["values"][0]
                if messagebox.askyesno("Delete",f"Remove attendance for {sid}?"):
                    df=pd.read_csv(_ef[0])
                    df=df[df["StudentID"].astype(str)!=str(sid)]
                    df.to_csv(_ef[0],index=False); load_e()
            def add_m():
                if not _ef[0]: return
                sid=simpledialog.askstring("Student ID","Enter Student ID:")
                if not sid: return
                db=load_db(); stu=db["students"].get(sid)
                nm=stu["name"] if stu else "Manual"
                df=pd.read_csv(_ef[0])
                df.loc[len(df)]={"StudentID":sid,"Name":nm,
                                  "Time":datetime.now().strftime("%H:%M:%S"),"Confidence":100.0}
                df.to_csv(_ef[0],index=False); load_e()

            mkbtn(ep,"🗑  Remove Selected", del_r, C["red"]).pack(fill=tk.X, pady=2)
            mkbtn(ep,"➕  Add Manual Entry", add_m, C["green"]).pack(fill=tk.X, pady=2)

            # bulk delete
            dp = mkcard(row, 24, 22)
            dp.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(dp, text="Bulk Delete", bg=C["card"], fg=C["red"], font=FSH).pack(anchor="w", pady=(0,12))
            db = load_db()
            tk.Label(dp, text="Stream", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            d_s = mkcb(dp, list(db["streams"].keys()), 22); d_s.pack(pady=(2,8), fill=tk.X)
            tk.Label(dp, text="Class", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            d_c = mkcb(dp, [], 22); d_c.pack(pady=(2,8), fill=tk.X)
            d_info = tk.Label(dp, text="", bg=C["card"], fg=C["muted"], font=FS)
            d_info.pack(anchor="w", pady=4)
            def dbs(ev):
                db=load_db()
                d_c["values"]=list(db["streams"].get(d_s.get(),{}).get("classes",{}).keys())
                d_c.set("")
            def dbc(ev):
                p=os.path.join(BASE_DIR,"attendance",d_s.get(),d_c.get())
                n=sum(1 for f in glob.glob(os.path.join(p,"**","*.csv"),recursive=True))
                d_info.config(text=f"{n} CSV file(s)")
            d_s.bind("<<ComboboxSelected>>", dbs)
            d_c.bind("<<ComboboxSelected>>", dbc)
            def del_all():
                s=d_s.get(); c=d_c.get()
                if not s or not c: return
                path=os.path.join(BASE_DIR,"attendance",s,c)
                if not os.path.exists(path): messagebox.showinfo("Info","No records"); return
                if messagebox.askyesno("Confirm",f"Delete ALL attendance for {s} > {c}?"):
                    import shutil; shutil.rmtree(path)
                    d_info.config(text="✅  Deleted"); refresh()
            mkbtn(dp,"🗑  Delete Class Attendance", del_all, C["red"], w=22).pack(pady=(4,0))

        page.on_show = refresh
        return page

    # ─── SETTINGS ───────────────────────────────────────────────
    def _pg_settings(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="⚙️  Settings",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            # ── Row 1: Password + System Info ─────────────────────
            row1 = tk.Frame(inner, bg=C["bg"])
            row1.columnconfigure(0, weight=1); row1.columnconfigure(1, weight=2)
            row1.pack(fill=tk.BOTH, padx=28)

            pp = mkcard(row1, 24, 22)
            pp.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(pp, text="Change Password", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            cur_e = mkentry(pp, "Current password", w=26, show="●")
            cur_e.pack(pady=(0,8), ipady=6, fill=tk.X)
            new_e = mkentry(pp, "New password", w=26, show="●")
            new_e.pack(pady=(0,8), ipady=6, fill=tk.X)
            con_e = mkentry(pp, "Confirm new password", w=26, show="●")
            con_e.pack(pady=(0,14), ipady=6, fill=tk.X)
            pw_st = tk.Label(pp, text="", bg=C["card"], fg=C["green"], font=FS); pw_st.pack()
            def chpw():
                cur=cur_e.get(); nw=new_e.get(); co=con_e.get(); us=load_users()
                if us[self.cur_user]["password"]!=_hash(cur):
                    pw_st.config(text="❌  Wrong password",fg=C["red"]); return
                if nw!=co: pw_st.config(text="❌  Mismatch",fg=C["red"]); return
                if len(nw)<6: pw_st.config(text="❌  Min 6 chars",fg=C["red"]); return
                us[self.cur_user]["password"]=_hash(nw); save_users(us)
                pw_st.config(text="✅  Password changed!", fg=C["green"])
            mkbtn(pp,"🔒  Update Password", chpw, w=24).pack()

            ip = mkcard(row1, 24, 22)
            ip.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(ip, text="System Information", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            _db=load_db(); _us=load_users()
            for lbl, val in [
                ("Students", str(len(_db.get("students",{})))),
                ("Teachers", str(sum(1 for u in _us.values() if u.get("role")=="teacher"))),
                ("Admins",   str(sum(1 for u in _us.values() if u.get("role")=="admin"))),
                ("Streams",  str(len(_db.get("streams",{})))),
                # ("Python",   sys.version[:6]),
                # ("Data dir", BASE_DIR[:40]),
            ]:
                r=tk.Frame(ip,bg=C["card2"],padx=12,pady=7); r.pack(fill=tk.X,pady=2)
                tk.Label(r,text=lbl,bg=C["card2"],fg=C["muted"],font=FS).pack(side=tk.LEFT)
                tk.Label(r,text=val,bg=C["card2"],fg=C["text"],
                         font=("Segoe UI",9,"bold")).pack(side=tk.RIGHT)

            # ── Admin accounts ─────────────────────────────────────
            sep(inner).pack(fill=tk.X, padx=28, pady=(22,0))
            tk.Label(inner, text="🛡️  Admin Accounts",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(12,2), anchor="w")
            tk.Label(inner,
                     text="Add, edit or remove admin accounts. At least one must always exist.",
                     bg=C["bg"], fg=C["muted"], font=FS).pack(padx=28, pady=(0,10), anchor="w")

            row2 = tk.Frame(inner, bg=C["bg"])
            row2.columnconfigure(0, weight=1); row2.columnconfigure(1, weight=1)
            row2.pack(fill=tk.BOTH, padx=28, pady=(0,4))

            ac = mkcard(row2, 24, 22)
            ac.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(ac, text="➕  Add New Admin", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            an_fields = {}
            for lbl_t, fkey in [("Full Name","name"),("Username","username"),
                                 ("Email (optional)","email")]:
                tk.Label(ac, text=lbl_t, bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
                e = mkentry(ac, lbl_t, w=28); e.pack(pady=(2,10), ipady=6, fill=tk.X)
                an_fields[fkey] = e
            tk.Label(ac, text="Password", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            an_pw = mkentry(ac, "min 6 chars", w=28, show="●")
            an_pw.pack(pady=(2,10), ipady=6, fill=tk.X)
            tk.Label(ac, text="Confirm Password", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            an_pw2 = mkentry(ac, "repeat password", w=28, show="●")
            an_pw2.pack(pady=(2,14), ipady=6, fill=tk.X)
            an_st = tk.Label(ac, text="", bg=C["card"], fg=C["green"], font=FS); an_st.pack()
            def add_admin():
                nm=an_fields["name"].get().strip(); un=an_fields["username"].get().strip()
                em=an_fields["email"].get().strip(); pw=an_pw.get(); pw2=an_pw2.get()
                if not nm or nm=="Full Name":
                    an_st.config(text="❌  Name required",fg=C["red"]); return
                if not un or un=="Username":
                    an_st.config(text="❌  Username required",fg=C["red"]); return
                if len(pw)<6:
                    an_st.config(text="❌  Min 6 char password",fg=C["red"]); return
                if pw!=pw2:
                    an_st.config(text="❌  Passwords don't match",fg=C["red"]); return
                us5=load_users()
                if un in us5:
                    an_st.config(text=f"❌  '{un}' already exists",fg=C["red"]); return
                us5[un]={"password":_hash(pw),"role":"admin","name":nm,
                          "email":em,"phone":"","assigned":[],
                          "created_at":datetime.now().isoformat()}
                save_users(us5)
                an_st.config(text=f"✅  Admin '{un}' created!",fg=C["green"])
                for e in an_fields.values(): e.delete(0,tk.END)
                an_pw.delete(0,tk.END); an_pw2.delete(0,tk.END)
                refresh()
            mkbtn(ac,"➕  Create Admin",add_admin,w=26).pack(pady=(8,0))

            lc = mkcard(row2, 24, 22)
            lc.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(lc, text="Existing Admins", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            admins={u:d for u,d in load_users().items() if d.get("role")=="admin"}
            if not admins:
                tk.Label(lc,text="No admins found.",bg=C["card"],fg=C["muted"],font=FB).pack(pady=20)
            for aun, aud in admins.items():
                af=tk.Frame(lc,bg=C["card2"],highlightbackground=C["border"],
                            highlightthickness=1,padx=14,pady=10); af.pack(fill=tk.X,pady=4)
                ir=tk.Frame(af,bg=C["card2"]); ir.pack(fill=tk.X)
                you="  ← you" if aun==self.cur_user else ""
                tk.Label(ir,text=f"⚙️  {aud.get('name',aun)}",bg=C["card2"],
                         fg=C["accent"],font=("Segoe UI",11,"bold")).pack(side=tk.LEFT)
                tk.Label(ir,text=f"@{aun}{you}",bg=C["card2"],
                         fg=C["muted"],font=FS).pack(side=tk.LEFT,padx=8)
                if aud.get("email"):
                    tk.Label(af,text=f"📧  {aud['email']}",bg=C["card2"],
                             fg=C["muted"],font=FS).pack(anchor="w")
                tk.Label(af,text=f"🗓️  {aud.get('created_at','')[:10]}",
                         bg=C["card2"],fg=C["muted"],font=FS).pack(anchor="w",pady=(2,6))
                actf=tk.Frame(af,bg=C["card2"]); actf.pack(anchor="w")
                def reset_adm(un=aun):
                    npw=simpledialog.askstring("Reset PW",f"New password for '{un}':",show="*")
                    if npw is None: return
                    if len(npw)<6: messagebox.showerror("Error","Min 6 chars"); return
                    u6=load_users(); u6[un]["password"]=_hash(npw); save_users(u6)
                    messagebox.showinfo("Done",f"Password reset for '{un}'")
                def del_adm(un=aun):
                    if un==self.cur_user:
                        messagebox.showerror("Error","Can't delete your own account."); return
                    if len([u for u,d in load_users().items() if d.get("role")=="admin"])<=1:
                        messagebox.showerror("Error","Cannot delete the only admin."); return
                    if messagebox.askyesno("Delete",f"Delete admin '{un}'?"):
                        u7=load_users(); u7.pop(un,None); save_users(u7); refresh()
                mkbtn(actf,"🔑  Reset PW",reset_adm,bg=C["blue"],fg="white").pack(side=tk.LEFT,padx=(0,6))
                if aun!=self.cur_user:
                    mkbtn(actf,"🗑  Delete",del_adm,bg=C["red"],fg="white").pack(side=tk.LEFT)

            # ── OAuth section ──────────────────────────────────────
            sep(inner).pack(fill=tk.X, padx=28, pady=(22,0))
            tk.Label(inner, text="🔐  OAuth 2.0 / Single Sign-On",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(12,2), anchor="w")

            if not _OAUTH_OK:
                tk.Label(inner,
                         text="⚠️  oauth_manager.py not found or deps missing.  "
                              "Run:  pip install requests PyJWT cryptography",
                         bg=C["bg"],fg=C["orange"],font=FS,
                         wraplength=700).pack(padx=28,pady=(0,14),anchor="w")
                return

            tk.Label(inner,
                     text="Configure providers then control which users can sign in via OAuth. "
                          "Changes take effect immediately on the login screen after next logout.",
                     bg=C["bg"],fg=C["muted"],font=FS,
                     wraplength=740).pack(padx=28,pady=(0,12),anchor="w")

            cfg=load_oauth_config()
            prow=tk.Frame(inner,bg=C["bg"]); prow.pack(fill=tk.X,padx=28,pady=(0,4))

            for col_idx,(pkey,pinfo) in enumerate(PROVIDERS.items()):
                prow.columnconfigure(col_idx, weight=1)
                pc=cfg.setdefault(pkey,{"client_id":"","client_secret":"","enabled":False})
                if pkey=="microsoft": pc.setdefault("tenant_id","common")
                pcard=mkcard(prow,22,18)
                pcard.grid(row=0,column=col_idx,sticky="nsew",
                           padx=(0,8) if col_idx==0 else (8,0))
                hdr2=tk.Frame(pcard,bg=C["card"]); hdr2.pack(fill=tk.X,pady=(0,10))
                tk.Label(hdr2,text=f"{pinfo['icon']}  {pinfo['label']}",
                         bg=C["card"],fg=C["accent"],font=FSH).pack(side=tk.LEFT)
                ena_var=tk.BooleanVar(value=bool(pc.get("enabled")))
                tk.Checkbutton(hdr2,text="Enabled",variable=ena_var,
                               bg=C["card"],fg=C["text"],selectcolor=C["card2"],
                               activebackground=C["card"],
                               font=FS,cursor="hand2").pack(side=tk.RIGHT)
                fields={}
                fd=[("Client ID","client_id",False),("Client Secret","client_secret",True)]
                if pkey=="microsoft": fd.append(("Tenant ID","tenant_id",False))
                for flbl,fkey,is_sec in fd:
                    tk.Label(pcard,text=flbl,bg=C["card"],fg=C["muted"],font=FS).pack(anchor="w")
                    e=mkentry(pcard,flbl,w=32,show="●" if is_sec else None)
                    e.delete(0,tk.END)
                    v=pc.get(fkey,"")
                    if v: e.insert(0,v); e.config(fg=C["text"])
                    e.pack(pady=(2,8),ipady=5,fill=tk.X); fields[fkey]=e
                sl=tk.Label(pcard,text="",bg=C["card"],fg=C["green"],font=FS); sl.pack(anchor="w")
                def _save_p(pk=pkey,flds=fields,ev=ena_var,s=sl):
                    c2=load_oauth_config(); pc2=c2.setdefault(pk,{})
                    pc2["enabled"]=ev.get()
                    for fk,ew in flds.items(): pc2[fk]=ew.get().strip()
                    save_oauth_config(c2)
                    s.config(text="✅  Saved! Log out and back in to see login button.")
                    s.after(4000,lambda:s.config(text=""))
                mkbtn(pcard,f"💾  Save {pinfo['label']} Settings",
                      _save_p).pack(fill=tk.X,pady=(8,0))

            # ── Bulk enable ────────────────────────────────────────
            sep(inner).pack(fill=tk.X, padx=28, pady=(18,0))
            tk.Label(inner, text="⚡  Quick Bulk Access",
                     bg=C["bg"],fg=C["text"],font=FSH).pack(padx=28,pady=(10,2),anchor="w")
            tk.Label(inner,
                     text="Enable or revoke OAuth for everyone or a specific role. "
                          "Users without an OAuth e-mail are skipped when enabling.",
                     bg=C["bg"],fg=C["muted"],font=FS,
                     wraplength=740).pack(padx=28,pady=(0,10),anchor="w")
            bkf=mkcard(inner,24,18); bkf.pack(fill=tk.X,padx=28,pady=(0,6))
            scope_var=tk.StringVar(value="all")
            rb_row=tk.Frame(bkf,bg=C["card"]); rb_row.pack(fill=tk.X)
            for txt,val in [("Everyone","all"),("Admins","admin"),
                            ("Teachers","teacher"),("Students","student")]:
                tk.Radiobutton(rb_row,text=txt,variable=scope_var,value=val,
                               bg=C["card"],fg=C["text"],selectcolor=C["card2"],
                               activebackground=C["card"],
                               font=FS,cursor="hand2").pack(side=tk.LEFT,padx=12,pady=6)
            bk_st=tk.Label(bkf,text="",bg=C["card"],fg=C["green"],font=FS)
            bk_st.pack(anchor="w",pady=(6,0))
            def _bulk(enable):
                scope=scope_var.get(); usb=load_users(); cnt=0
                for un_b,ud_b in usb.items():
                    if scope!="all" and ud_b.get("role")!=scope: continue
                    if enable and not ud_b.get("oauth_email","").strip(): continue
                    ud_b["oauth_enabled"]=enable; cnt+=1
                save_users(usb)
                word="enabled" if enable else "revoked"
                bk_st.config(text=f"✅  OAuth {word} for {cnt} user(s).",
                             fg=C["green"] if enable else C["orange"])
                bk_st.after(3000,lambda:bk_st.config(text="")); refresh()
            bb=tk.Frame(bkf,bg=C["card"]); bb.pack(fill=tk.X,pady=(8,0))
            mkbtn(bb,"✅  Enable for selected",lambda:_bulk(True),
                  bg=C["green"],fg="white").pack(side=tk.LEFT,padx=(0,8))
            mkbtn(bb,"❌  Revoke for selected",lambda:_bulk(False),
                  bg=C["red"],fg="white").pack(side=tk.LEFT)

            # ── Per-user table ─────────────────────────────────────
            sep(inner).pack(fill=tk.X, padx=28, pady=(18,0))
            tk.Label(inner, text="👤  Per-User OAuth Access",
                     bg=C["bg"],fg=C["text"],font=FSH).pack(padx=28,pady=(10,2),anchor="w")
            tk.Label(inner,
                     text="Set each user's OAuth e-mail then enable or revoke individually.",
                     bg=C["bg"],fg=C["muted"],font=FS,
                     wraplength=740).pack(padx=28,pady=(0,10),anchor="w")
            tbl=tk.Frame(inner,bg=C["bg"]); tbl.pack(fill=tk.X,padx=28,pady=(0,30))
            HDR=[("Username",130),("Role",80),("Name",150),
                 ("OAuth Email",220),("Status",72),("Action",90)]
            for ci,(ht,hw) in enumerate(HDR):
                tk.Label(tbl,text=ht,bg=C["card2"],fg=C["accent"],
                         font=("Segoe UI",9,"bold"),width=hw//8,anchor="w",
                         padx=8,pady=6,highlightbackground=C["border"],
                         highlightthickness=1).grid(row=0,column=ci,
                                                    sticky="ew",padx=1,pady=1)
            role_order={"admin":0,"teacher":1,"student":2}
            for ri,(un_t,ud_t) in enumerate(
                    sorted(load_users().items(),
                           key=lambda x:(role_order.get(x[1].get("role",""),9),x[0])),
                    start=1):
                rc=(C["accent"] if ud_t["role"]=="admin"
                    else C["blue"] if ud_t["role"]=="teacher" else C["green"])
                bg_r=C["card"] if ri%2==0 else C["card2"]
                def _lbl(txt,fg=None):
                    return tk.Label(tbl,text=txt,bg=bg_r,fg=fg or C["text"],
                                    font=FS,anchor="w",padx=8,pady=6)
                _lbl(un_t).grid(row=ri,column=0,sticky="ew",padx=1,pady=1)
                _lbl(ud_t["role"],fg=rc).grid(row=ri,column=1,sticky="ew",padx=1,pady=1)
                _lbl(ud_t.get("name","")[:22]).grid(row=ri,column=2,sticky="ew",padx=1,pady=1)
                ee=tk.Entry(tbl,font=FS,bg=bg_r,fg=C["text"],
                            insertbackground=C["accent"],relief="flat",
                            highlightbackground=C["border"],highlightthickness=1)
                ee.insert(0,ud_t.get("oauth_email",""))
                ee.grid(row=ri,column=3,sticky="ew",padx=1,pady=1,ipady=5)
                is_on=bool(ud_t.get("oauth_enabled"))
                al=tk.Label(tbl,text="✅ ON" if is_on else "❌ OFF",bg=bg_r,
                            fg=C["green"] if is_on else C["red"],
                            font=("Segoe UI",9,"bold"),padx=8,pady=6)
                al.grid(row=ri,column=4,sticky="ew",padx=1,pady=1)
                def _tog(un=un_t,el=ee,a=al):
                    ut=load_users(); cur=bool(ut[un].get("oauth_enabled"))
                    em=el.get().strip()
                    if not cur and not em:
                        messagebox.showwarning("Email Required",
                            f"Enter {un}'s OAuth e-mail first."); return
                    ut[un]["oauth_enabled"]=not cur; ut[un]["oauth_email"]=em
                    save_users(ut); ns=not cur
                    a.config(text="✅ ON" if ns else "❌ OFF",
                             fg=C["green"] if ns else C["red"])
                mkbtn(tbl,"Revoke" if is_on else "Enable",_tog,
                      bg=C["red"] if is_on else C["green"],
                      fg="white").grid(row=ri,column=5,sticky="ew",padx=1,pady=1)

        page.on_show = refresh
        refresh()
        return page

    # ═══════════════════════════════════════════════════════════
    #  TEACHER UI
    # ═══════════════════════════════════════════════════════════
    def _build_teacher(self):
        nav = [
            ("🏠", "My Dashboard",   "t_dash"),
            ("👤", "My Profile",      "t_profile"),
            ("📸", "Take Attendance", "t_att"),
            ("📊", "My Records",      "t_records"),
            ("📅", "My Timetable",    "t_tt"),
            "---",
            ("📝", "My Assignments",  "t_assign"),
            ("📣", "Notices",         "t_notices"),
            ("✉️",  "Leave Request",  "t_leave"),
        ]
        ct = self._build_shell(nav)
        self.pages["t_dash"]    = self._pg_t_dashboard(ct)
        self.pages["t_profile"] = self._pg_t_profile(ct)
        self.pages["t_att"]     = self._pg_t_attendance(ct)
        self.pages["t_records"] = self._pg_t_records(ct)
        self.pages["t_tt"]      = self._pg_t_timetable(ct)
        self.pages["t_assign"]  = self._pg_t_assignments(ct)
        self.pages["t_notices"] = self._pg_t_notices(ct)
        self.pages["t_leave"]   = self._pg_t_leave(ct)
        self._nav("t_dash")

    # ─── TEACHER DASHBOARD ──────────────────────────────────────
    def _pg_t_dashboard(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            ud = load_users().get(self.cur_user, self.cur_data)
            assigns = ud.get("assigned",[])

            tr = tk.Frame(inner, bg=C["bg"])
            tr.pack(fill=tk.X, padx=28, pady=(22,8))
            if _PIL:
                try:
                    av = make_avatar_photo(ud["name"],60)
                    if av:
                        al = tk.Label(tr, image=av, bg=C["bg"])
                        al.image=av; al.pack(side=tk.LEFT, padx=(0,14))
                except: pass
            tc = tk.Frame(tr, bg=C["bg"]); tc.pack(side=tk.LEFT)
            greet = "Morning" if datetime.now().hour<12 else ("Afternoon" if datetime.now().hour<17 else "Evening")
            tk.Label(tc, text=f"Good {greet}, {ud['name'].split()[0]} 👋",
                     bg=C["bg"], fg=C["text"], font=("Segoe UI",20,"bold")).pack(anchor="w")
            tk.Label(tc, text=datetime.now().strftime("%A, %d %B %Y"),
                     bg=C["bg"], fg=C["muted"], font=FB).pack(anchor="w")

            today = datetime.now().strftime("%Y-%m-%d")
            att_today = 0
            for a in assigns:
                fp=os.path.join(BASE_DIR,"attendance",a.get("stream",""),
                                a.get("class",""),a.get("subject",""),f"{today}.csv")
                if os.path.exists(fp):
                    try: att_today += len(pd.read_csv(fp))
                    except: pass

            my_leaves = [l for l in load_leaves() if l.get("username")==self.cur_user]

            sr = tk.Frame(inner, bg=C["bg"])
            sr.pack(fill=tk.X, padx=24, pady=8)
            for val,lbl,col,ico in [
                (len(assigns),"Assigned Classes",C["accent"],"📚"),
                (att_today,"Marked Today",C["green"],"✅"),
                (len(load_notices()),"Notices",C["blue"],"📣"),
                (len(my_leaves),"My Leaves",C["purple"],"✉️"),
            ]:
                sc = stat_card(sr, val, lbl, col, ico)
                sc.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

            lower = tk.Frame(inner, bg=C["bg"])
            lower.pack(fill=tk.BOTH, padx=24, pady=10, expand=True)
            ac = mkcard(lower, 24, 20)
            ac.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,8))
            tk.Label(ac, text="📚  My Assigned Classes", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
            if not assigns:
                tk.Label(ac, text="No classes assigned. Contact admin.",
                         bg=C["card"], fg=C["muted"], font=FB).pack(pady=20)
            for a in assigns:
                af = tk.Frame(ac, bg=C["card2"],
                              highlightbackground=C["accent"], highlightthickness=1,
                              padx=14, pady=12)
                af.pack(fill=tk.X, pady=4)
                tk.Label(af, text=f"🎓 {a.get('stream','?')}  /  {a.get('class','?')}",
                         bg=C["card2"], fg=C["text"],
                         font=("Segoe UI",12,"bold")).pack(anchor="w")
                tk.Label(af, text=f"📘 Subject: {a.get('subject','?')}",
                         bg=C["card2"], fg=C["blue"], font=FB).pack(anchor="w")
                fp=os.path.join(BASE_DIR,"attendance",a.get("stream",""),
                                a.get("class",""),a.get("subject",""),f"{today}.csv")
                cnt=0
                if os.path.exists(fp):
                    try: cnt=len(pd.read_csv(fp))
                    except: pass
                tk.Label(af, text=f"✅ Today: {cnt} marked",
                         bg=C["card2"], fg=C["green"], font=FS).pack(anchor="w", pady=(4,0))

            rn = mkcard(lower, 20, 20)
            rn.pack(side=tk.LEFT, fill=tk.BOTH)
            tk.Label(rn, text="📣  Recent Notices", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,8))
            for n in load_notices()[-5:][::-1]:
                nf = tk.Frame(rn, bg=C["card2"], padx=10, pady=7)
                nf.pack(fill=tk.X, pady=2)
                tk.Label(nf, text=n.get("title","")[:35], bg=C["card2"],
                         fg=C["text"], font=("Segoe UI",10,"bold")).pack(anchor="w")
                tk.Label(nf, text=n.get("date",""), bg=C["card2"],
                         fg=C["muted"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── TEACHER PROFILE ────────────────────────────────────────
    def _pg_t_profile(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            ud = load_users().get(self.cur_user, self.cur_data)
            tk.Label(inner, text="👤  My Profile",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"]); row.pack(fill=tk.BOTH, padx=28, expand=True)

            avp = mkcard(row, 32, 30)
            avp.pack(side=tk.LEFT, fill=tk.Y, padx=(0,18))
            if _PIL:
                try:
                    av = make_avatar_photo(ud["name"],96)
                    if av:
                        al = tk.Label(avp, image=av, bg=C["card"])
                        al.image=av; al.pack(pady=(0,12))
                except: pass
            tk.Label(avp, text=ud["name"], bg=C["card"], fg=C["text"],
                     font=("Segoe UI",16,"bold")).pack()
            tk.Label(avp, text="TEACHER", bg=C["card"], fg=C["accent"],
                     font=("Segoe UI",9,"bold")).pack(pady=(2,8))
            sep(avp).pack(fill=tk.X, pady=8)
            for ico, key in [("📧","email"),("📞","phone")]:
                tk.Label(avp, text=f"{ico}  {ud.get(key,'—')}",
                         bg=C["card"], fg=C["muted"], font=FB).pack(pady=3)
            tk.Label(avp, text=f"🗓️  Since {ud.get('created_at','')[:10]}",
                     bg=C["card"], fg=C["muted"], font=FS).pack(pady=3)

            ep = mkcard(row, 28, 28)
            ep.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(ep, text="Edit Profile", bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            flds = {}
            for lbl, key in [("Full Name","name"),("Email","email"),("Phone","phone")]:
                tk.Label(ep, text=lbl, bg=C["card"], fg=C["muted"],
                         font=("Segoe UI",10)).pack(anchor="w")
                e = mkentry(ep, "", w=30); e.pack(pady=(3,12), ipady=7, fill=tk.X)
                e.insert(0, ud.get(key,"")); e.config(fg=C["text"])
                flds[key] = e
            st = tk.Label(ep, text="", bg=C["card"], fg=C["green"], font=FS); st.pack()
            def save():
                us = load_users()
                for key, e in flds.items():
                    us[self.cur_user][key] = e.get().strip()
                save_users(us)
                self.cur_data = us[self.cur_user]
                st.config(text="✅  Profile updated!", fg=C["green"])
                refresh()
            mkbtn(ep,"💾  Save Changes", save, w=28).pack(pady=(8,0))

            sep(inner).pack(fill=tk.X, padx=28, pady=14)
            ap = mkcard(inner, 28, 22)
            ap.pack(fill=tk.X, padx=28)
            tk.Label(ap, text="📚  My Assignments", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,10))
            for a in ud.get("assigned",[]):
                af = tk.Frame(ap, bg=C["card2"], padx=14, pady=8)
                af.pack(fill=tk.X, pady=3)
                tk.Label(af, text=f"🎓 {a.get('stream')} / {a.get('class')} / 📘 {a.get('subject')}",
                         bg=C["card2"], fg=C["text"], font=FB).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── TEACHER ATTENDANCE ─────────────────────────────────────
    def _pg_t_attendance(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📸  Take Attendance",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            tk.Label(inner, text="Only your assigned classes are shown.",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,14), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            ud = load_users().get(self.cur_user, self.cur_data)
            assigns = ud.get("assigned",[])
            if not assigns:
                tk.Label(inner, text="No classes assigned yet.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=40); return
            today = datetime.now().strftime("%Y-%m-%d")
            for a in assigns:
                af = mkcard(inner, 24, 20)
                af.pack(fill=tk.X, padx=28, pady=6)
                tk.Label(af, text=f"🎓 {a.get('stream')} / {a.get('class')} / 📘 {a.get('subject')}",
                         bg=C["card"], fg=C["accent"], font=FSH).pack(anchor="w")
                sep(af).pack(fill=tk.X, pady=8)
                fp=os.path.join(BASE_DIR,"attendance",a.get("stream",""),
                                a.get("class",""),a.get("subject",""),f"{today}.csv")
                if os.path.exists(fp):
                    try: cnt=len(pd.read_csv(fp)); status=f"✅  {cnt} students marked today"; sc=C["green"]
                    except: status="⚠️  File error"; sc=C["orange"]
                else:
                    status="Not taken today"; sc=C["orange"]
                tk.Label(af, text=status, bg=C["card"], fg=sc, font=FB).pack(anchor="w", pady=(0,8))
                def start(s=a.get("stream",""), c=a.get("class",""), sub=a.get("subject","")):
                    enc_path = os.path.join(BASE_DIR, "face_encodings.pkl")
                    if not os.path.exists(enc_path):
                        messagebox.showwarning("Missing", "Model not trained. Contact admin.")
                        return
                    subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "take_attendance.py"), s, c, sub])
                mkbtn(af, f"▶  Start Attendance", start).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── TEACHER RECORDS ────────────────────────────────────────
    def _pg_t_records(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        tk.Label(page, text="📊  My Attendance Records",
                 bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,6), anchor="w")

        assigns = self.cur_data.get("assigned",[])
        labels  = [f"{a.get('stream')}/{a.get('class')}/{a.get('subject')}" for a in assigns]

        fr = tk.Frame(page, bg=C["bg"])
        fr.pack(fill=tk.X, padx=28, pady=4)
        f_a = mkcb(fr, labels, 30); f_a.pack(side=tk.LEFT, padx=3)
        f_d = mkcb(fr, [], 16);     f_d.pack(side=tk.LEFT, padx=3)

        def on_fa(e):
            idx = labels.index(f_a.get()) if f_a.get() in labels else -1
            if idx<0: return
            a = assigns[idx]
            p = os.path.join(BASE_DIR,"attendance",a.get("stream",""),a.get("class",""),a.get("subject",""))
            f_d["values"] = sorted([x[:-4] for x in os.listdir(p) if x.endswith(".csv")],
                                    reverse=True) if os.path.exists(p) else []
            f_d.set("")
        f_a.bind("<<ComboboxSelected>>", on_fa)

        tvf = tk.Frame(page, bg=C["bg"])
        tvf.pack(fill=tk.BOTH, expand=True, padx=28, pady=6)
        cols = ["StudentID","Name","Stream","Class","Subject","Time","Confidence"]
        tv, tsb = mktree(tvf, cols, h=16)
        tv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)
        summ = tk.Label(page, text="", bg=C["bg"], fg=C["muted"], font=FS)
        summ.pack(padx=28, anchor="w")
        _cf = [None]

        def load_r(e=None):
            tv.delete(*tv.get_children())
            idx = labels.index(f_a.get()) if f_a.get() in labels else -1
            if idx<0: return
            a=assigns[idx]; d=f_d.get()
            if not d: return
            fp=os.path.join(BASE_DIR,"attendance",a.get("stream",""),a.get("class",""),
                            a.get("subject",""),f"{d}.csv")
            _cf[0]=fp
            if os.path.exists(fp):
                df=pd.read_csv(fp)
                for _,r in df.iterrows():
                    tv.insert("","end", values=[str(r.get(c,"")) for c in cols])
                summ.config(text=f"  {len(df)} records  •  {fp}")
        f_d.bind("<<ComboboxSelected>>", load_r)

        br = tk.Frame(page, bg=C["bg"]); br.pack(fill=tk.X, padx=28, pady=4)
        def del_r():
            sel=tv.selection()
            if not sel or not _cf[0]: return
            sid=tv.item(sel[0])["values"][0]
            if messagebox.askyesno("Delete",f"Remove record for {sid}?"):
                df=pd.read_csv(_cf[0])
                df=df[df["StudentID"].astype(str)!=str(sid)]
                df.to_csv(_cf[0],index=False); load_r()
        def add_m():
            if not _cf[0]: return
            sid=simpledialog.askstring("Student ID","Enter Student ID:")
            if not sid: return
            db=load_db(); stu=db["students"].get(sid); nm=stu["name"] if stu else "Manual"
            df=pd.read_csv(_cf[0])
            df.loc[len(df)]={"StudentID":sid,"Name":nm,
                              "Time":datetime.now().strftime("%H:%M:%S"),"Confidence":100.0}
            df.to_csv(_cf[0],index=False); load_r()

        mkbtn(br,"🗑  Remove Record", del_r, C["red"]).pack(side=tk.LEFT, padx=4)
        mkbtn(br,"➕  Add Manual", add_m, C["green"]).pack(side=tk.LEFT, padx=4)
        mkbtn(br,"🔄  Refresh", load_r, C["card2"]).pack(side=tk.LEFT, padx=4)

        def on_show():
            ud = load_users().get(self.cur_user, self.cur_data)
            new_assigns = ud.get("assigned",[])
            new_labels  = [f"{a.get('stream')}/{a.get('class')}/{a.get('subject')}" for a in new_assigns]
            f_a["values"] = new_labels
        page.on_show = on_show
        return page

    # ─── TEACHER TIMETABLE ──────────────────────────────────────
    def _pg_t_timetable(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)
        DAYS  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
        SLOTS = ["9:00-10:00","10:00-11:00","11:00-12:00",
                 "12:00-1:00","1:00-2:00","2:00-3:00","3:00-4:00"]

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📅  My Timetable",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            ud = load_users().get(self.cur_user, self.cur_data)
            assigns = ud.get("assigned",[])
            labels  = list(dict.fromkeys([f"{a.get('stream')}/{a.get('class')}" for a in assigns]))
            ctrl = tk.Frame(inner, bg=C["bg"])
            ctrl.pack(fill=tk.X, padx=28, pady=(0,10))
            tk.Label(ctrl, text="Class:", bg=C["bg"], fg=C["muted"], font=FB).pack(side=tk.LEFT)
            tc = mkcb(ctrl, labels, 26); tc.pack(side=tk.LEFT, padx=8)
            gfr = [None]
            def show(e=None):
                if gfr[0]: gfr[0].destroy()
                if not tc.get(): return
                parts = tc.get().split("/",1)
                if len(parts)<2: return
                s, c = parts[0], parts[1]
                key = f"{s}|{c}"
                data = load_timetable().get(key,{})
                my_subjects = [a.get("subject","") for a in assigns
                               if a.get("stream")==s and a.get("class")==c]
                gf = tk.Frame(inner, bg=C["bg"])
                gf.pack(fill=tk.BOTH, padx=28, pady=4); gfr[0]=gf
                today_day = datetime.now().strftime("%A")
                tk.Label(gf, text="", bg=C["card2"], width=12, pady=6).grid(row=0,column=0)
                for ci, day in enumerate(DAYS):
                    is_today = day == today_day
                    bg = C["accent"] if is_today else C["card2"]
                    fg = C["bg"] if is_today else C["text"]
                    tk.Label(gf, text=day+((" ◀" if is_today else "")), bg=bg, fg=fg,
                             font=("Segoe UI",9,"bold"), width=14, pady=6).grid(
                                 row=0,column=ci+1,padx=1,pady=1)
                for ri, slot in enumerate(SLOTS):
                    tk.Label(gf, text=slot, bg=C["card2"], fg=C["muted"],
                             font=("Segoe UI",8), width=12, pady=6).grid(
                                 row=ri+1,column=0,padx=1,pady=1)
                    for ci, day in enumerate(DAYS):
                        val = data.get(day,{}).get(slot,"")
                        is_mine = val in my_subjects
                        bg = C["accent"] if is_mine else C["card"]
                        fg = C["bg"] if is_mine else (C["text"] if val else C["muted"])
                        tk.Label(gf, text=val or "—", bg=bg, fg=fg,
                                 font=("Segoe UI",9), width=14, pady=6,
                                 relief="flat").grid(row=ri+1,column=ci+1,padx=1,pady=1)
            tc.bind("<<ComboboxSelected>>", show)

        page.on_show = refresh
        return page

    # ─── TEACHER ASSIGNMENTS ────────────────────────────────────
    def _pg_t_assignments(self, parent):
        """Teacher page: post assignments for their own assigned classes only."""
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            ud = load_users().get(self.cur_user, self.cur_data)
            assigns = ud.get("assigned", [])

            tk.Label(inner, text="📝  My Assignments",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            tk.Label(inner, text="Post and manage assignments for your assigned classes.",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            if not assigns:
                tk.Label(inner,
                         text="⚠️  You have no assigned classes yet.\nAsk the admin to assign you to a stream/class/subject.",
                         bg=C["bg"], fg=C["orange"], font=FB,
                         justify="left").pack(padx=28, pady=40, anchor="w")
                return

            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1, minsize=380)
            row.columnconfigure(1, weight=1, minsize=380)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            # ── Post form ──────────────────────────────────────────
            pp = mkcard(row, 16, 18)
            pp.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(pp, text="Post New Assignment", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))

            class_options = [
                f"{a['stream']} / {a['class']} / {a['subject']}"
                for a in assigns if a.get("stream") and a.get("class") and a.get("subject")
            ]

            tk.Label(pp, text="Class / Subject", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            ta_cls = mkcb(pp, class_options, 28)
            if class_options:
                ta_cls.current(0)
            ta_cls.pack(pady=(3,10), fill=tk.X)

            tk.Label(pp, text="Title", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            ta_title = mkentry(pp, "Assignment title…", w=26)
            ta_title.pack(pady=(3,10), ipady=6, fill=tk.X)

            tk.Label(pp, text="Due Date (YYYY-MM-DD)", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            ta_due = mkentry(pp, datetime.now().strftime("%Y-%m-%d"), w=26)
            ta_due.config(fg=C["text"])
            ta_due.pack(pady=(3,10), ipady=6, fill=tk.X)

            tk.Label(pp, text="Description", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            ta_desc = tk.Text(pp, bg=C["card2"], fg=C["text"], font=FB,
                              width=26, height=5, relief="flat", insertbackground=C["accent"])
            ta_desc.pack(pady=(3,14), fill=tk.X)

            ta_st = tk.Label(pp, text="", bg=C["card"], fg=C["green"], font=FS)
            ta_st.pack()

            def post_assign():
                sel = ta_cls.get()
                if not sel:
                    ta_st.config(text="❌  Select a class/subject", fg=C["red"]); return
                parts = [p.strip() for p in sel.split("/")]
                if len(parts) != 3:
                    ta_st.config(text="❌  Invalid selection", fg=C["red"]); return
                s, c, sub = parts
                title = ta_title.get().strip()
                due   = ta_due.get().strip()
                desc  = ta_desc.get("1.0", tk.END).strip()
                if not title or title == "Assignment title…":
                    ta_st.config(text="❌  Enter a title", fg=C["red"]); return
                al = load_assignments()
                al.append({
                    "id":                  int(datetime.now().timestamp()),
                    "stream":              s,
                    "class":               c,
                    "subject":             sub,
                    "class_key":           f"{s}|{c}",
                    "title":               title,
                    "due":                 due,
                    "description":         desc,
                    "posted_by":           ud["name"],
                    "posted_by_username":  self.cur_user,
                    "posted_at":           datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                save_assignments(al)
                ta_title.delete(0, tk.END)
                ta_desc.delete("1.0", tk.END)
                ta_st.config(text="✅  Assignment posted!", fg=C["green"])
                refresh()

            mkbtn(pp, "📝  Post Assignment", post_assign).pack(fill=tk.X)

            # ── My posted assignments ──────────────────────────────
            lp = mkcard(row, 16, 18)
            lp.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(lp, text="My Posted Assignments", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))

            my_assigns = [a for a in load_assignments()[::-1]
                          if a.get("posted_by_username") == self.cur_user]

            if not my_assigns:
                tk.Label(lp, text="No assignments posted yet.",
                         bg=C["card"], fg=C["muted"], font=FB).pack(pady=20)
            else:
                for a in my_assigns:
                    af = tk.Frame(lp, bg=C["card2"],
                                  highlightbackground=C["border"], highlightthickness=1,
                                  padx=14, pady=10)
                    af.pack(fill=tk.X, pady=4)
                    hr2 = tk.Frame(af, bg=C["card2"]); hr2.pack(fill=tk.X)
                    tk.Label(hr2, text=f"  {a.get('subject','')}  ", bg=C["blue"],
                             fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, pady=2)
                    tk.Label(hr2, text=f"{a.get('stream','')}/{a.get('class','')}",
                             bg=C["card2"], fg=C["muted"], font=FS).pack(side=tk.LEFT, padx=6)
                    def del_a(aid=a.get("id")):
                        if messagebox.askyesno("Delete", "Delete this assignment?"):
                            al2 = [x for x in load_assignments() if x.get("id") != aid]
                            save_assignments(al2); refresh()
                    mkbtn(hr2, "🗑", del_a, C["red"], w=3).pack(side=tk.RIGHT)
                    tk.Label(af, text=a.get("title",""), bg=C["card2"], fg=C["text"],
                             font=("Segoe UI",12,"bold")).pack(anchor="w", pady=(4,2))
                    tk.Label(af, text=f"📅 Due: {a.get('due','')}  •  {a.get('posted_at','')}",
                             bg=C["card2"], fg=C["accent"], font=FS).pack(anchor="w")
                    if a.get("description"):
                        tk.Label(af, text=a.get("description","")[:120], bg=C["card2"],
                                 fg=C["muted"], font=FS, wraplength=360, justify="left").pack(anchor="w", pady=(2,0))

        page.on_show = refresh
        return page

    # ─── TEACHER NOTICES ────────────────────────────────────────
    def _pg_t_notices(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📣  Notices & Announcements",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            cat_col = {"General":C["muted"],"Academic":C["blue"],"Holiday":C["green"],
                       "Exam":C["red"],"Event":C["purple"],"Urgent":C["orange"]}
            # Teachers see "All" and "Teachers Only" notices
            notices = [n for n in load_notices()[::-1]
                       if n.get("audience","All") in ("All","Teachers Only")]
            if not notices:
                tk.Label(inner, text="No notices for you yet.", bg=C["bg"],
                         fg=C["muted"], font=FB).pack(pady=40)
            for n in notices:
                nf = mkcard(inner, 20, 16)
                nf.pack(fill=tk.X, padx=28, pady=5)
                hr = tk.Frame(nf, bg=C["card"]); hr.pack(fill=tk.X)
                col = cat_col.get(n.get("category","General"), C["muted"])
                tk.Label(hr, text=f"  {n.get('category','')}  ",
                         bg=col, fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, pady=2)
                tk.Label(hr, text=n.get("title",""), bg=C["card"], fg=C["text"],
                         font=("Segoe UI",14,"bold")).pack(side=tk.LEFT, padx=10)
                tk.Label(nf, text=n.get("message",""), bg=C["card"], fg=C["muted"],
                         font=FB, wraplength=640, justify="left").pack(anchor="w", pady=(8,4))
                tk.Label(nf, text=f"Posted by {n.get('author','')}  •  {n.get('date','')}",
                         bg=C["card"], fg=C["border"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── TEACHER LEAVE ──────────────────────────────────────────
    def _pg_t_leave(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="✉️  Leave Request",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"]); row.pack(fill=tk.BOTH, padx=28, expand=True)

            fp = mkcard(row, 28, 26)
            fp.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(fp, text="Submit Leave Request", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            ud = load_users().get(self.cur_user, self.cur_data)
            assigns = ud.get("assigned",[])
            subjs = [a.get("subject","") for a in assigns]
            tk.Label(fp, text="Subject", bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(anchor="w")
            lv_sub = mkcb(fp, subjs, 28); lv_sub.pack(pady=(3,12), fill=tk.X)
            tk.Label(fp, text="From Date (YYYY-MM-DD)", bg=C["card"],
                     fg=C["muted"], font=("Segoe UI",10)).pack(anchor="w")
            lv_from = mkentry(fp, datetime.now().strftime("%Y-%m-%d"), w=28)
            lv_from.config(fg=C["text"]); lv_from.pack(pady=(3,12), ipady=6, fill=tk.X)
            tk.Label(fp, text="To Date (YYYY-MM-DD)", bg=C["card"],
                     fg=C["muted"], font=("Segoe UI",10)).pack(anchor="w")
            lv_to = mkentry(fp, (datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d"), w=28)
            lv_to.config(fg=C["text"]); lv_to.pack(pady=(3,12), ipady=6, fill=tk.X)
            tk.Label(fp, text="Reason", bg=C["card"], fg=C["muted"],
                     font=("Segoe UI",10)).pack(anchor="w")
            lv_reason = tk.Text(fp, bg=C["card2"], fg=C["text"], font=FB,
                                 width=28, height=4, relief="flat",
                                 insertbackground=C["accent"])
            lv_reason.pack(pady=(3,14), fill=tk.X)
            st = tk.Label(fp, text="", bg=C["card"], fg=C["green"], font=FS); st.pack()
            def submit():
                sub=lv_sub.get(); reason=lv_reason.get("1.0",tk.END).strip()
                frm=lv_from.get().strip(); to=lv_to.get().strip()
                if not all([sub,reason,frm,to]):
                    st.config(text="❌  Fill all fields",fg=C["red"]); return
                ls=load_leaves()
                ls.append({"id":int(datetime.now().timestamp()),
                            "teacher_name":ud["name"],"username":self.cur_user,
                            "subject":sub,"from_date":frm,"to_date":to,
                            "reason":reason,"status":"Pending",
                            "date":datetime.now().strftime("%Y-%m-%d %H:%M")})
                save_leaves(ls)
                lv_reason.delete("1.0",tk.END)
                st.config(text="✅  Submitted!", fg=C["green"]); refresh()
            mkbtn(fp,"📨  Submit Request", submit).pack(fill=tk.X)

            # history
            hp = mkcard(row, 24, 26)
            hp.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(hp, text="My Leave History", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            sc2 = {"Pending":C["orange"],"Approved":C["green"],"Rejected":C["red"]}
            my_leaves = [l for l in load_leaves()[::-1] if l.get("username")==self.cur_user]
            if not my_leaves:
                tk.Label(hp, text="No requests yet.", bg=C["card"],
                         fg=C["muted"], font=FB).pack(pady=20)
            for lv in my_leaves:
                lf = tk.Frame(hp, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1,
                              padx=14, pady=10)
                lf.pack(fill=tk.X, pady=4)
                hr = tk.Frame(lf, bg=C["card2"]); hr.pack(fill=tk.X)
                col = sc2.get(lv.get("status","Pending"), C["orange"])
                tk.Label(hr, text=f"  {lv.get('status','Pending')}  ",
                         bg=col, fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT)
                tk.Label(hr, text=f"{lv.get('subject','')}  •  {lv.get('from_date','')} → {lv.get('to_date','')}",
                         bg=C["card2"], fg=C["text"],
                         font=("Segoe UI",11,"bold")).pack(side=tk.LEFT, padx=8)
                tk.Label(lf, text=lv.get("reason",""), bg=C["card2"], fg=C["muted"],
                         font=FS, wraplength=380).pack(anchor="w", pady=(4,0))

        page.on_show = refresh
        return page


    # ─── ADMIN: ASSIGNMENTS ─────────────────────────────────────
    def _pg_assignments(self, parent):
        """Admin page: post assignments per class, view/delete them."""
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📝  Assignment Management",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"])
            row.columnconfigure(0, weight=1, minsize=380)
            row.columnconfigure(1, weight=1, minsize=380)
            row.pack(fill=tk.BOTH, padx=28, expand=True)

            pp = mkcard(row, 16, 18)
            pp.grid(row=0, column=0, sticky="nsew", padx=(0,7))
            tk.Label(pp, text="Post Assignment", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            db = load_db()
            tk.Label(pp, text="Stream", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            as_s = mkcb(pp, list(db["streams"].keys()), 26); as_s.pack(pady=(3,10), fill=tk.X)
            tk.Label(pp, text="Class", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            as_c = mkcb(pp, [], 26); as_c.pack(pady=(3,10), fill=tk.X)
            tk.Label(pp, text="Subject", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            as_sub = mkcb(pp, [], 26); as_sub.pack(pady=(3,10), fill=tk.X)
            tk.Label(pp, text="Title", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            as_title = mkentry(pp, "Assignment title…", w=26); as_title.pack(pady=(3,10), ipady=6, fill=tk.X)
            tk.Label(pp, text="Due Date (YYYY-MM-DD)", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            as_due = mkentry(pp, datetime.now().strftime("%Y-%m-%d"), w=26)
            as_due.config(fg=C["text"]); as_due.pack(pady=(3,10), ipady=6, fill=tk.X)
            tk.Label(pp, text="Description", bg=C["card"], fg=C["muted"], font=FS).pack(anchor="w")
            as_desc = tk.Text(pp, bg=C["card2"], fg=C["text"], font=FB,
                              width=26, height=5, relief="flat", insertbackground=C["accent"])
            as_desc.pack(pady=(3,14), fill=tk.X)
            as_st = tk.Label(pp, text="", bg=C["card"], fg=C["green"], font=FS); as_st.pack()

            def on_as_s(e):
                db2=load_db(); as_c["values"]=list(db2["streams"].get(as_s.get(),{}).get("classes",{}).keys()); as_c.set("")
            def on_as_c(e):
                db2=load_db(); as_sub["values"]=db2["streams"].get(as_s.get(),{}).get("classes",{}).get(as_c.get(),{}).get("subjects",[]); as_sub.set("")
            as_s.bind("<<ComboboxSelected>>", on_as_s)
            as_c.bind("<<ComboboxSelected>>", on_as_c)

            def post_assign():
                s=as_s.get(); c=as_c.get(); sub=as_sub.get()
                title=as_title.get().strip(); due=as_due.get().strip()
                desc=as_desc.get("1.0",tk.END).strip()
                if not all([s,c,sub,title]):
                    as_st.config(text="❌  Fill all required fields", fg=C["red"]); return
                al2 = load_assignments()
                al2.append({
                    "id": int(datetime.now().timestamp()),
                    "stream": s, "class": c, "subject": sub,
                    "class_key": f"{s}|{c}",
                    "title": title, "due": due, "description": desc,
                    "posted_by": self.cur_data["name"],
                    "posted_at": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
                save_assignments(al2)
                as_title.delete(0,tk.END); as_desc.delete("1.0",tk.END)
                as_st.config(text="✅  Posted!", fg=C["green"]); refresh()
            mkbtn(pp,"📝  Post Assignment", post_assign).pack(fill=tk.X)

            lp = mkcard(row, 24, 22)
            lp.grid(row=0, column=1, sticky="nsew", padx=(7,0))
            tk.Label(lp, text="All Assignments", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,12))
            for a in load_assignments()[::-1]:
                af = tk.Frame(lp, bg=C["card2"],
                              highlightbackground=C["border"], highlightthickness=1,
                              padx=14, pady=10)
                af.pack(fill=tk.X, pady=4)
                hr2 = tk.Frame(af, bg=C["card2"]); hr2.pack(fill=tk.X)
                tk.Label(hr2, text=f"  {a.get('subject','')}  ", bg=C["blue"],
                         fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, pady=2)
                tk.Label(hr2, text=f"{a.get('stream','')}/{a.get('class','')}",
                         bg=C["card2"], fg=C["muted"], font=FS).pack(side=tk.LEFT, padx=6)
                def del_a(aid=a.get("id")):
                    al3=[x for x in load_assignments() if x.get("id")!=aid]
                    save_assignments(al3); refresh()
                mkbtn(hr2,"🗑", del_a, C["red"], w=3).pack(side=tk.RIGHT)
                tk.Label(af, text=a.get("title",""), bg=C["card2"], fg=C["text"],
                         font=("Segoe UI",12,"bold")).pack(anchor="w", pady=(4,2))
                tk.Label(af, text=f"📅 Due: {a.get('due','')}  •  By {a.get('posted_by','')}",
                         bg=C["card2"], fg=C["accent"], font=FS).pack(anchor="w")
                if a.get("description"):
                    tk.Label(af, text=a.get("description","")[:120], bg=C["card2"],
                             fg=C["muted"], font=FS, wraplength=380, justify="left").pack(anchor="w", pady=(2,0))

        page.on_show = refresh
        return page

    # ═══════════════════════════════════════════════════════════
    #  STUDENT UI
    # ═══════════════════════════════════════════════════════════
    def _build_student(self):
        nav = [
            ("🏠", "My Dashboard",    "s_dash"),
            ("📊", "My Attendance",   "s_att"),
            ("📅", "My Timetable",    "s_tt"),
            ("📝", "Assignments",     "s_assign"),
            ("📣", "Notices",         "s_notices"),
            "---",
            ("👤", "My Profile",      "s_profile"),
        ]
        ct = self._build_shell(nav)
        self.pages["s_dash"]    = self._pg_s_dashboard(ct)
        self.pages["s_att"]     = self._pg_s_attendance(ct)
        self.pages["s_tt"]      = self._pg_s_timetable(ct)
        self.pages["s_assign"]  = self._pg_s_assignments(ct)
        self.pages["s_notices"] = self._pg_s_notices(ct)
        self.pages["s_profile"] = self._pg_s_profile(ct)
        self._nav("s_dash")

    def _get_student_data(self):
        """Return (student_id, student_dict) for the logged-in student."""
        db = load_db()
        return self.cur_user, db.get("students", {}).get(self.cur_user, {})

    # ─── STUDENT DASHBOARD ──────────────────────────────────────
    def _pg_s_dashboard(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            sid, sd = self._get_student_data()
            nm = sd.get("name", self.cur_data.get("name", sid))
            stream = sd.get("stream",""); cls = sd.get("class","")

            tr = tk.Frame(inner, bg=C["bg"])
            tr.pack(fill=tk.X, padx=28, pady=(22,8))
            if _PIL:
                try:
                    av = make_avatar_photo(nm, 60)
                    if av:
                        al = tk.Label(tr, image=av, bg=C["bg"])
                        al.image=av; al.pack(side=tk.LEFT, padx=(0,14))
                except: pass
            tc = tk.Frame(tr, bg=C["bg"]); tc.pack(side=tk.LEFT)
            greet = "Morning" if datetime.now().hour<12 else ("Afternoon" if datetime.now().hour<17 else "Evening")
            tk.Label(tc, text=f"Good {greet}, {nm.split()[0]} 👋",
                     bg=C["bg"], fg=C["text"], font=("Segoe UI",20,"bold")).pack(anchor="w")
            tk.Label(tc, text=f"🎓 {stream}  /  {cls}   •   {datetime.now().strftime('%A, %d %B %Y')}",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(anchor="w")

            today = datetime.now().strftime("%Y-%m-%d")
            my_notices = [n for n in load_notices()
                          if n.get("audience","All") in ("All","Students Only")]
            my_assigns = [a for a in load_assignments()
                          if a.get("class_key") == f"{stream}|{cls}"]
            att_today = 0
            att_dir = os.path.join(BASE_DIR,"attendance",stream,cls)
            if os.path.exists(att_dir):
                for subj in os.listdir(att_dir):
                    fp=os.path.join(att_dir,subj,f"{today}.csv")
                    if os.path.exists(fp):
                        try:
                            df=pd.read_csv(fp)
                            if str(sid) in df["StudentID"].astype(str).values:
                                att_today+=1
                        except: pass

            sr = tk.Frame(inner, bg=C["bg"])
            sr.pack(fill=tk.X, padx=24, pady=8)
            for val,lbl,col,ico in [
                (att_today,         "Present Today",   C["green"],  "✅"),
                (len(my_assigns),   "Assignments",     C["blue"],   "📝"),
                (len(my_notices),   "Notices",         C["purple"], "📣"),
            ]:
                sc = stat_card(sr, val, lbl, col, ico)
                sc.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

            lower = tk.Frame(inner, bg=C["bg"])
            lower.pack(fill=tk.BOTH, padx=24, pady=10, expand=True)
            nc = mkcard(lower, 22, 18)
            nc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,8))
            tk.Label(nc, text="📣  Recent Notices", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,8))
            for n in my_notices[-5:][::-1]:
                nf2 = tk.Frame(nc, bg=C["card2"], padx=10, pady=7)
                nf2.pack(fill=tk.X, pady=2)
                tk.Label(nf2, text=n.get("title","")[:40], bg=C["card2"],
                         fg=C["text"], font=("Segoe UI",10,"bold")).pack(anchor="w")
                tk.Label(nf2, text=n.get("date",""), bg=C["card2"],
                         fg=C["muted"], font=FS).pack(anchor="w")

            ac2 = mkcard(lower, 22, 18)
            ac2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(ac2, text="📝  Upcoming Assignments", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,8))
            if not my_assigns:
                tk.Label(ac2, text="No assignments yet.", bg=C["card"],
                         fg=C["muted"], font=FB).pack(pady=10)
            for a in sorted(my_assigns, key=lambda x: x.get("due",""))[:5]:
                af2 = tk.Frame(ac2, bg=C["card2"], padx=10, pady=7)
                af2.pack(fill=tk.X, pady=2)
                tk.Label(af2, text=a.get("title","")[:35], bg=C["card2"],
                         fg=C["text"], font=("Segoe UI",10,"bold")).pack(anchor="w")
                tk.Label(af2, text=f"{a.get('subject','')}  •  Due: {a.get('due','')}",
                         bg=C["card2"], fg=C["accent"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── STUDENT ATTENDANCE ─────────────────────────────────────
    def _pg_s_attendance(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            sid, sd = self._get_student_data()
            stream = sd.get("stream",""); cls = sd.get("class","")

            tk.Label(inner, text="📊  My Attendance",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            tk.Label(inner, text=f"Class: {stream} / {cls}",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,14), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            att_base = os.path.join(BASE_DIR,"attendance",stream,cls)
            if not os.path.exists(att_base):
                tk.Label(inner, text="No attendance records yet.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=40); return

            subjects = sorted(os.listdir(att_base))
            if not subjects:
                tk.Label(inner, text="No subjects found.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=40); return

            for subj in subjects:
                subj_dir = os.path.join(att_base, subj)
                if not os.path.isdir(subj_dir): continue
                csv_files = sorted([f for f in os.listdir(subj_dir) if f.endswith(".csv")], reverse=True)
                sc = mkcard(inner, 22, 18)
                sc.pack(fill=tk.X, padx=28, pady=8)
                tk.Label(sc, text=f"📘  {subj}", bg=C["card"],
                         fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,8))

                present=0; total=0; records=[]
                for fname in csv_files:
                    fp=os.path.join(subj_dir,fname)
                    try:
                        df=pd.read_csv(fp); total+=1
                        row=df[df["StudentID"].astype(str)==str(sid)]
                        if not row.empty:
                            present+=1
                            records.append({"Date":fname[:-4],"Status":"✅ Present",
                                            "Time":str(row.iloc[0].get("Time","—")),
                                            "Conf":str(row.iloc[0].get("Confidence","—"))})
                        else:
                            records.append({"Date":fname[:-4],"Status":"❌ Absent","Time":"—","Conf":"—"})
                    except: pass

                pct = round(present/total*100,1) if total>0 else 0
                bar_col = C["green"] if pct>=75 else (C["orange"] if pct>=50 else C["red"])
                sumf = tk.Frame(sc, bg=C["card"]); sumf.pack(fill=tk.X, pady=(0,8))
                tk.Label(sumf, text=f"Present: {present}/{total}   Attendance: {pct}%",
                         bg=C["card"], fg=bar_col, font=("Segoe UI",11,"bold")).pack(side=tk.LEFT)
                if pct < 75:
                    tk.Label(sumf, text="  ⚠️ Below 75% — at risk!", bg=C["card"],
                             fg=C["red"], font=FS).pack(side=tk.LEFT, padx=8)

                tvf2 = tk.Frame(sc, bg=C["card"]); tvf2.pack(fill=tk.X)
                rcols = ["Date","Status","Time","Confidence"]
                rtv, rsb = mktree(tvf2, rcols, h=min(len(records),8))
                rtv.column("Date",width=120); rtv.column("Status",width=120)
                rtv.column("Time",width=90); rtv.column("Confidence",width=100)
                rtv.pack(side=tk.LEFT, fill=tk.X, expand=True)
                rsb.pack(side=tk.RIGHT, fill=tk.Y)
                for r in records:
                    rtv.insert("","end", values=(r["Date"],r["Status"],r["Time"],r["Conf"]))

        page.on_show = refresh
        return page

    # ─── STUDENT TIMETABLE ──────────────────────────────────────
    def _pg_s_timetable(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)
        DAYS  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]
        SLOTS = ["9:00-10:00","10:00-11:00","11:00-12:00",
                 "12:00-1:00","1:00-2:00","2:00-3:00","3:00-4:00"]

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            sid, sd = self._get_student_data()
            stream = sd.get("stream", "")
            cls    = sd.get("class",  "")

            tk.Label(inner, text="📅  My Timetable",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            tk.Label(inner, text=f"Class: {stream} / {cls}",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,14), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            if not stream or not cls:
                tk.Label(inner, text="No class information found. Contact admin.",
                         bg=C["bg"], fg=C["orange"], font=FB).pack(pady=40)
                return

            key  = f"{stream}|{cls}"
            data = load_timetable().get(key, {})
            today_day = datetime.now().strftime("%A")

            gf = tk.Frame(inner, bg=C["bg"])
            gf.pack(fill=tk.BOTH, padx=28, pady=4)

            # header row
            tk.Label(gf, text="", bg=C["card2"], width=12, pady=8).grid(row=0, column=0, padx=1, pady=1)
            for ci, day in enumerate(DAYS):
                is_today = (day == today_day)
                bg_ = C["accent"] if is_today else C["card2"]
                fg_ = C["bg"]    if is_today else C["text"]
                tk.Label(gf, text=day + (" ◀" if is_today else ""),
                         bg=bg_, fg=fg_,
                         font=("Segoe UI",9,"bold"),
                         width=14, pady=8).grid(row=0, column=ci+1, padx=1, pady=1)

            for ri, slot in enumerate(SLOTS):
                tk.Label(gf, text=slot, bg=C["card2"], fg=C["muted"],
                         font=("Segoe UI",8), width=12, pady=8).grid(
                             row=ri+1, column=0, padx=1, pady=1)
                for ci, day in enumerate(DAYS):
                    val = data.get(day, {}).get(slot, "")
                    bg_ = C["card"]
                    fg_ = C["text"] if val else C["muted"]
                    tk.Label(gf, text=val or "—",
                             bg=bg_, fg=fg_,
                             font=("Segoe UI",9),
                             width=14, pady=8,
                             relief="flat").grid(row=ri+1, column=ci+1, padx=1, pady=1)

            if not any(data.get(d) for d in DAYS):
                tk.Label(inner,
                         text="No timetable set for your class yet. Check back later.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=20, padx=28, anchor="w")

        page.on_show = refresh
        return page

    # ─── STUDENT ASSIGNMENTS ────────────────────────────────────
    def _pg_s_assignments(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            sid, sd = self._get_student_data()
            stream = sd.get("stream",""); cls = sd.get("class","")
            class_key = f"{stream}|{cls}"

            tk.Label(inner, text="📝  My Assignments",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            tk.Label(inner, text=f"Class: {stream} / {cls}",
                     bg=C["bg"], fg=C["muted"], font=FB).pack(padx=28, pady=(0,14), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))

            assigns = [a for a in load_assignments() if a.get("class_key")==class_key]
            if not assigns:
                tk.Label(inner, text="No assignments posted for your class yet.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=40); return

            for a in sorted(assigns, key=lambda x: x.get("posted_at",""), reverse=True):
                af = mkcard(inner, 22, 18)
                af.pack(fill=tk.X, padx=28, pady=6)
                hr2 = tk.Frame(af, bg=C["card"]); hr2.pack(fill=tk.X)
                tk.Label(hr2, text=f"  {a.get('subject','')}  ", bg=C["blue"],
                         fg=C["bg"], font=("Segoe UI",9,"bold")).pack(side=tk.LEFT, pady=2)
                due = a.get("due","")
                try:
                    overdue = datetime.strptime(due,"%Y-%m-%d") < datetime.now()
                except: overdue=False
                due_col = C["red"] if overdue else C["green"]
                tk.Label(hr2, text=f"  📅 Due: {due}{'  ⚠️ OVERDUE' if overdue else ''}  ",
                         bg=due_col, fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, padx=4)
                tk.Label(af, text=a.get("title",""), bg=C["card"], fg=C["text"],
                         font=("Segoe UI",13,"bold")).pack(anchor="w", pady=(8,4))
                if a.get("description"):
                    tk.Label(af, text=a.get("description",""), bg=C["card"],
                             fg=C["muted"], font=FB, wraplength=680, justify="left").pack(anchor="w", pady=(0,4))
                tk.Label(af, text=f"Posted by {a.get('posted_by','')}  •  {a.get('posted_at','')}",
                         bg=C["card"], fg=C["border"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── STUDENT NOTICES ────────────────────────────────────────
    def _pg_s_notices(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            tk.Label(inner, text="📣  Notices & Announcements",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            cat_col = {"General":C["muted"],"Academic":C["blue"],"Holiday":C["green"],
                       "Exam":C["red"],"Event":C["purple"],"Urgent":C["orange"]}
            notices = [n for n in load_notices()[::-1]
                       if n.get("audience","All") in ("All","Students Only")]
            if not notices:
                tk.Label(inner, text="No notices for you yet.",
                         bg=C["bg"], fg=C["muted"], font=FB).pack(pady=40); return
            for n in notices:
                nf = mkcard(inner, 20, 16)
                nf.pack(fill=tk.X, padx=28, pady=5)
                hr2 = tk.Frame(nf, bg=C["card"]); hr2.pack(fill=tk.X)
                col = cat_col.get(n.get("category","General"), C["muted"])
                tk.Label(hr2, text=f"  {n.get('category','')}  ",
                         bg=col, fg=C["bg"], font=("Segoe UI",8,"bold")).pack(side=tk.LEFT, pady=2)
                tk.Label(hr2, text=n.get("title",""), bg=C["card"], fg=C["text"],
                         font=("Segoe UI",14,"bold")).pack(side=tk.LEFT, padx=10)
                tk.Label(nf, text=n.get("message",""), bg=C["card"], fg=C["muted"],
                         font=FB, wraplength=660, justify="left").pack(anchor="w", pady=(8,4))
                tk.Label(nf, text=f"Posted by {n.get('author','')}  •  {n.get('date','')}",
                         bg=C["card"], fg=C["border"], font=FS).pack(anchor="w")

        page.on_show = refresh
        return page

    # ─── STUDENT PROFILE ────────────────────────────────────────
    def _pg_s_profile(self, parent):
        page = tk.Frame(parent, bg=C["bg"])
        so, inner = scroll_frame(page)
        so.pack(fill=tk.BOTH, expand=True)

        def refresh():
            for w in inner.winfo_children(): w.destroy()
            sid, sd = self._get_student_data()
            nm = sd.get("name", sid)

            tk.Label(inner, text="👤  My Profile",
                     bg=C["bg"], fg=C["text"], font=FH).pack(padx=28, pady=(22,4), anchor="w")
            sep(inner).pack(fill=tk.X, padx=28, pady=(0,14))
            row = tk.Frame(inner, bg=C["bg"]); row.pack(fill=tk.BOTH, padx=28, expand=True)

            avp = mkcard(row, 32, 30)
            avp.pack(side=tk.LEFT, fill=tk.Y, padx=(0,18))
            if _PIL:
                try:
                    av = make_avatar_photo(nm, 96)
                    if av:
                        al = tk.Label(avp, image=av, bg=C["card"])
                        al.image=av; al.pack(pady=(0,12))
                except: pass
            tk.Label(avp, text=nm, bg=C["card"], fg=C["text"],
                     font=("Segoe UI",16,"bold")).pack()
            tk.Label(avp, text="STUDENT", bg=C["card"], fg=C["green"],
                     font=("Segoe UI",9,"bold")).pack(pady=(2,8))
            sep(avp).pack(fill=tk.X, pady=8)
            for ico, lbl, val in [("🆔","Student ID",sid),("🎓","Stream",sd.get("stream","—")),
                                   ("📚","Class",sd.get("class","—")),("🗓️","Registered",sd.get("registered_at","—")[:10])]:
                tk.Label(avp, text=f"{ico}  {lbl}: {val}",
                         bg=C["card"], fg=C["muted"], font=FB).pack(pady=3, anchor="w")

            ep = mkcard(row, 28, 28)
            ep.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(ep, text="Change Password", bg=C["card"],
                     fg=C["accent"], font=FSH).pack(anchor="w", pady=(0,14))
            cur_e = mkentry(ep, "Current password", w=28, show="●"); cur_e.pack(pady=(0,8), ipady=6, fill=tk.X)
            new_e = mkentry(ep, "New password", w=28, show="●"); new_e.pack(pady=(0,8), ipady=6, fill=tk.X)
            con_e = mkentry(ep, "Confirm new password", w=28, show="●"); con_e.pack(pady=(0,14), ipady=6, fill=tk.X)
            pw_st = tk.Label(ep, text="", bg=C["card"], fg=C["green"], font=FS); pw_st.pack()
            def chpw():
                cur=cur_e.get(); nw=new_e.get(); co=con_e.get()
                us=load_users()
                if us.get(self.cur_user,{}).get("password")!=_hash(cur):
                    pw_st.config(text="❌  Wrong current password",fg=C["red"]); return
                if nw!=co: pw_st.config(text="❌  Passwords don't match",fg=C["red"]); return
                if len(nw)<6: pw_st.config(text="❌  Min 6 characters",fg=C["red"]); return
                us[self.cur_user]["password"]=_hash(nw); save_users(us)
                pw_st.config(text="✅  Password changed!", fg=C["green"])
            mkbtn(ep,"🔒  Update Password", chpw, w=26).pack()

        page.on_show = refresh
        return page


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    App()
