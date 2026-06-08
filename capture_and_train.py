
import cv2
import numpy as np
import json
import os
import time
import threading
import pickle
import tkinter as tk
from tkinter import messagebox, ttk

# ── face_recognition (dlib) ────────────────────────────────────────────────
try:
    import face_recognition
except ImportError:
    raise ImportError(
        "face_recognition not installed.\n"
        "Run: pip install face_recognition\n"
        "(Also needs cmake + dlib — see README)"
    )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Haarcascade paths (still used for live preview bounding boxes only) ────
_CASCADE_DEFAULT_LOCAL = os.path.join(BASE_DIR, "haarcascade_frontalface_default.xml")
CASCADE = _CASCADE_DEFAULT_LOCAL if os.path.exists(_CASCADE_DEFAULT_LOCAL) \
          else cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

# ── New model file (replaces trainer.yml) ─────────────────────────────────
ENCODINGS_FILE = os.path.join(BASE_DIR, "face_encodings.pkl")   # pickle dict
DATASET        = os.path.join(BASE_DIR, "dataset")
TARGET         = 30          # captures needed (fewer needed vs LBPH)
STABLE_SECS    = 3           # seconds of stable single-face before capture


# ──────────────────────────────────────────────────────────────────────────
def load_db():
    p = os.path.join(BASE_DIR, "db.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"streams": {}, "students": {}}


def load_encodings() -> dict:
    """
    Returns dict:
      {
        "student_id|name": {
            "encodings": [np.array, ...],   # 128-d vectors
            "label": "student_id|name"
        },
        ...
      }
    """
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            return pickle.load(f)
    return {}


def save_encodings(data: dict):
    with open(ENCODINGS_FILE, "wb") as f:
        pickle.dump(data, f)


# ──────────────────────────────────────────────────────────────────────────
def _open_camera():
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS,          30)
    for _ in range(5):
        cap.read()
    return cap


# ──────────────────────────────────────────────────────────────────────────
def capture_and_train(student_id, name, stream="", cls="",
                      save_images=True,
                      progress_var=None,
                      status_label=None,
                      tk_root=None):
    """
    Open webcam, wait for a stable single face, capture TARGET frames,
    compute 128-d face_recognition encodings, and save to face_encodings.pkl.

    Returns (success: bool, message: str)
    """

    def _status(msg):
        if status_label:
            try:
                status_label.config(text=msg)
                if tk_root: tk_root.update_idletasks()
            except Exception:
                pass
        print(msg)

    def _prog(pct):
        if progress_var is not None:
            try:
                progress_var.set(int(pct))
                if tk_root: tk_root.update_idletasks()
            except Exception:
                pass

    key = f"{student_id}|{name}"

    # ── Haar cascade for quick preview boxes ──────────────────────────────
    face_det = cv2.CascadeClassifier(CASCADE)

    cap = _open_camera()
    if not cap.isOpened():
        return False, "Cannot open camera."

    raw_bgr_frames = []   # store full BGR frames for encoding later
    count          = 0
    win_title      = f"Registering: {name}  |  Press Q to cancel"

    # ── Phase 1: wait for stable single face ──────────────────────────────
    _status("🔍  Position your face in the frame…")
    stable_start = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        disp  = frame.copy()
        faces = face_det.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
        n     = len(faces)

        if n == 0:
            stable_start = None
            cv2.putText(disp, "No face detected — move closer",
                        (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 80, 220), 2)
        elif n > 1:
            stable_start = None
            cv2.putText(disp, f"Multiple faces ({n}) — ONE person only!",
                        (10, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 50, 255), 2)
            for (x, y, w, h) in faces:
                cv2.rectangle(disp, (x, y), (x+w, y+h), (0, 50, 255), 2)
        else:
            (x, y, w, h) = faces[0]
            if stable_start is None:
                stable_start = time.time()
            elapsed   = time.time() - stable_start
            remaining = max(0, STABLE_SECS - elapsed)
            cv2.rectangle(disp, (x, y), (x+w, y+h), (0, 220, 0), 2)
            if remaining > 0:
                cv2.putText(disp, f"Hold still… {remaining:.1f}s",
                            (x, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 0), 2)
            else:
                cv2.putText(disp, "Starting capture!",
                            (x, y - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (63, 185, 80), 2)
                cv2.imshow(win_title, disp)
                cv2.waitKey(1)
                break

        cv2.rectangle(disp, (0, 0), (disp.shape[1], 46), (15, 23, 42), -1)
        cv2.putText(disp, f"  PHASE 1/2 — Stabilising  |  {name}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 165, 0), 2)
        cv2.imshow(win_title, disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            cap.release(); cv2.destroyAllWindows()
            return False, "Cancelled by user."

    # ── Phase 2: capture frames ────────────────────────────────────────────
    _status(f"📸  Capturing frames (0/{TARGET})…")

    while count < TARGET:
        ret, frame = cap.read()
        if not ret:
            break

        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        disp  = frame.copy()
        faces = face_det.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))

        if len(faces) == 1:
            (x, y, w, h) = faces[0]
            cv2.rectangle(disp, (x, y), (x+w, y+h), (63, 185, 80), 2)
            raw_bgr_frames.append(frame.copy())
            count += 1
            _status(f"📸  Capturing frames ({count}/{TARGET})…")
            _prog(int(count / TARGET * 60))
        elif len(faces) == 0:
            cv2.putText(disp, "Face lost — reposition",
                        (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 80, 220), 2)
        else:
            cv2.putText(disp, "Multiple faces! Move others away.",
                        (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 50, 255), 2)

        bar_w = int(disp.shape[1] * count / TARGET)
        cv2.rectangle(disp, (0, 46), (bar_w, 52), (99, 102, 241), -1)
        cv2.rectangle(disp, (0, 0), (disp.shape[1], 46), (15, 23, 42), -1)
        cv2.putText(disp, f"PHASE 2/2 — Capturing  {count}/{TARGET}  |  {name}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 165, 0), 2)

        cv2.imshow(win_title, disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    if count < 10:
        return False, f"Only {count} frames captured (need ≥10). Try again in better light."

    # ── Optionally save raw images ─────────────────────────────────────────
    if save_images:
        img_dir = os.path.join(DATASET, student_id)
        os.makedirs(img_dir, exist_ok=True)
        for i, frm in enumerate(raw_bgr_frames):
            cv2.imwrite(os.path.join(img_dir, f"face_{i:04d}.png"), frm)

    # ── Compute 128-d encodings ────────────────────────────────────────────
    _status("🧠  Computing face encodings (this may take ~30 s)…")
    _prog(65)

    new_encodings = []
    for frm in raw_bgr_frames:
        rgb = cv2.cvtColor(frm, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb, model="hog")
        if not locs:
            continue
        # take the first (largest) face only
        encs = face_recognition.face_encodings(rgb, [locs[0]])
        if encs:
            new_encodings.append(encs[0])

    if not new_encodings:
        return False, "No valid face encodings found. Try better lighting / closer distance."

    _prog(85)

    # ── Merge into encodings store ────────────────────────────────────────
    _status("💾  Saving encodings…")
    store = load_encodings()
    if key in store:
        store[key]["encodings"].extend(new_encodings)
    else:
        store[key] = {"encodings": new_encodings, "label": key}
    save_encodings(store)

    _prog(100)
    total_students = len(store)
    img_info = (f"dataset/{student_id}/ ({count} images)"
                if save_images else "not saved")
    msg = (
        f"✅  {name} registered successfully!\n\n"
        f"  📦  Encodings   →  face_encodings.pkl\n"
        f"  📁  Images      →  {img_info}\n\n"
        f"  Students in model : {total_students}\n"
        f"  New encodings     : {len(new_encodings)}"
    )
    _status(f"✅  Done — {name}")
    print(msg)
    return True, msg


# ──────────────────────────────────────────────────────────────────────────
#  STANDALONE GUI  (python capture_and_train.py)
# ──────────────────────────────────────────────────────────────────────────
def _standalone_gui():
    root = tk.Tk()
    root.title("Face Capture — DHVINO ERP")
    root.configure(bg="#0d1117")
    root.resizable(False, False)

    BG   = "#0d1117"; CARD = "#1c2128"; CARD2 = "#22272e"
    BOR  = "#30363d"; ACC  = "#f0a500"; TXT   = "#e6edf3"
    MUT  = "#8b949e"; GRN  = "#3fb950"; RED   = "#f85149"

    fr = tk.Frame(root, bg=CARD, padx=30, pady=24,
                  highlightbackground=BOR, highlightthickness=1)
    fr.pack(padx=30, pady=30)

    tk.Label(fr, text="📸  Face Capture & Training",
             bg=CARD, fg=ACC, font=("Segoe UI", 16, "bold")).pack(pady=(0, 4))
    tk.Label(fr, text="Uses face_recognition (dlib) — great for classrooms.",
             bg=CARD, fg=MUT, font=("Segoe UI", 9)).pack(pady=(0, 14))

    db = load_db()
    students = db.get("students", {})
    stu_list = [f"{sid} — {d['name']}" for sid, d in students.items()]

    tk.Label(fr, text="Pick existing student (optional):",
             bg=CARD, fg=MUT, font=("Segoe UI", 10)).pack(anchor="w")
    pick_cb = ttk.Combobox(fr, values=stu_list, width=36, state="readonly")
    pick_cb.pack(pady=(3, 10), fill=tk.X)

    flds = {}
    for lbl, key, ph in [("Student ID", "id", "e.g. CS24MCA013"),
                          ("Full Name",  "name",   "e.g. Violina Saikia"),
                          ("Stream",     "stream", "e.g. MCA"),
                          ("Class",      "cls",    "e.g. 2nd year")]:
        tk.Label(fr, text=lbl, bg=CARD, fg=MUT, font=("Segoe UI", 10)).pack(anchor="w")
        e = tk.Entry(fr, font=("Segoe UI", 11), bg=CARD2, fg=TXT,
                     insertbackground=ACC, relief="flat", bd=0, width=34,
                     highlightbackground=BOR, highlightthickness=1)
        e.insert(0, ph); e.config(fg=MUT)
        def _fi(ev, _e=e, _p=ph):
            if _e.get() == _p: _e.delete(0, tk.END); _e.config(fg=TXT)
        def _fo(ev, _e=e, _p=ph):
            if not _e.get(): _e.insert(0, _p); _e.config(fg=MUT)
        e.bind("<FocusIn>", _fi); e.bind("<FocusOut>", _fo)
        e.pack(pady=(3, 10), ipady=6, fill=tk.X)
        flds[key] = e

    def on_pick(e=None):
        sel = pick_cb.get()
        if not sel: return
        sid = sel.split(" — ")[0]
        d   = students.get(sid, {})
        for key, val in [("id", sid), ("name", d.get("name", "")),
                         ("stream", d.get("stream", "")), ("cls", d.get("class", ""))]:
            flds[key].delete(0, tk.END)
            flds[key].insert(0, val)
            flds[key].config(fg=TXT)
    pick_cb.bind("<<ComboboxSelected>>", on_pick)

    save_var = tk.BooleanVar(value=True)
    tk.Checkbutton(fr, text="Save face images to dataset/",
                   variable=save_var, bg=CARD, fg=MUT,
                   selectcolor=CARD2, activebackground=CARD,
                   font=("Segoe UI", 10), cursor="hand2").pack(anchor="w", pady=(0, 8))

    prog_var = tk.IntVar()
    ttk.Progressbar(fr, variable=prog_var, maximum=100, length=340).pack(
        pady=(4, 8), fill=tk.X)
    stat = tk.Label(fr, text="Ready.", bg=CARD, fg=MUT,
                    font=("Segoe UI", 9), wraplength=360, justify="left")
    stat.pack()

    btn_ref = [None]

    def do_cap():
        sid  = flds["id"].get().strip()
        nm   = flds["name"].get().strip()
        strm = flds["stream"].get().strip()
        cls  = flds["cls"].get().strip()
        phs  = {"e.g. CS24MCA013", "e.g. Violina Saikia", "e.g. MCA", "e.g. 2nd year"}
        if not all([sid, nm, strm, cls]) or {sid, nm, strm, cls} & phs:
            stat.config(text="❌  Fill in all fields.", fg=RED)
            return
        btn_ref[0].config(state="disabled")
        prog_var.set(0)

        def run():
            ok, msg = capture_and_train(sid, nm, strm, cls,
                                        save_images=save_var.get(),
                                        progress_var=prog_var,
                                        status_label=stat,
                                        tk_root=root)
            stat.config(text=msg, fg=GRN if ok else RED)
            btn_ref[0].config(state="normal")
            if ok:
                root.after(0, lambda: messagebox.showinfo("Done", msg))

        threading.Thread(target=run, daemon=True).start()

    btn = tk.Button(fr, text="📸  Start Face Capture",
                    command=do_cap, bg=ACC, fg=BG,
                    font=("Segoe UI", 11, "bold"), relief="flat",
                    cursor="hand2", padx=14, pady=8)
    btn.pack(pady=(14, 0))
    btn_ref[0] = btn
    root.mainloop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        sid  = sys.argv[1]
        nm   = sys.argv[2]
        strm = sys.argv[3] if len(sys.argv) > 3 else ""
        cls  = sys.argv[4] if len(sys.argv) > 4 else ""
        save = sys.argv[5].lower() in ("true", "1", "yes") if len(sys.argv) > 5 else True
        ok, msg = capture_and_train(sid, nm, strm, cls, save_images=save)
        print(msg)
    else:
        _standalone_gui()
