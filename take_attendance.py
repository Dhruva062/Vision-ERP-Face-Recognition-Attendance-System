import sys
import cv2
import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime

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

# ── Haarcascade for fast live preview bounding boxes ──────────────────────
_CASCADE_LOCAL = os.path.join(BASE_DIR, "haarcascade_frontalface_default.xml")
CASCADE = _CASCADE_LOCAL if os.path.exists(_CASCADE_LOCAL) \
          else cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

# ── New model file (replaces trainer.yml + trainer_meta.json) ─────────────
ENCODINGS_FILE = os.path.join(BASE_DIR, "face_encodings.pkl")

# Tolerance: lower = stricter. 0.5 is good for classrooms.
# Increase to 0.55 if too many "Unknown"; decrease to 0.45 if false positives.
TOLERANCE = 0.50


# ──────────────────────────────────────────────────────────────────────────
def load_db():
    p = os.path.join(BASE_DIR, "db.json")
    if os.path.exists(p):
        with open(p) as f:
            import json
            return json.load(f)
    return {"streams": {}, "students": {}}


def load_encodings() -> dict:
    """
    Returns the dict saved by capture_and_train.py:
      { "student_id|name": {"encodings": [...], "label": "..."}, ... }
    """
    if os.path.exists(ENCODINGS_FILE):
        with open(ENCODINGS_FILE, "rb") as f:
            return pickle.load(f)
    return {}


# ──────────────────────────────────────────────────────────────────────────
#  DASHBOARD  (unchanged from original — pure OpenCV drawing)
# ──────────────────────────────────────────────────────────────────────────
def make_dashboard(enrolled_ids, students, marked, stream, cls, subject):
    ROW_H  = 30
    W      = 440
    H      = max(500, 90 + ROW_H * (len(enrolled_ids) + 1) + 50)
    canvas = np.full((H, W, 3), (22, 27, 38), dtype=np.uint8)

    cv2.rectangle(canvas, (0, 0), (W, 56), (15, 23, 42), -1)
    cv2.putText(canvas, f"{stream} / {cls}",
                (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (240, 165, 0), 2)
    cv2.putText(canvas, f"Subject: {subject}",
                (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (139, 148, 158), 1)
    cv2.line(canvas, (0, 57), (W, 57), (48, 54, 61), 1)

    cv2.putText(canvas, "ID",     (8,   76), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (139, 148, 158), 1)
    cv2.putText(canvas, "Name",   (140, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (139, 148, 158), 1)
    cv2.putText(canvas, "Status", (340, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (139, 148, 158), 1)
    cv2.line(canvas, (0, 80), (W, 80), (48, 54, 61), 1)

    present = absent = 0
    y = 80 + ROW_H
    for sid in sorted(enrolled_ids):
        nm  = students.get(sid, {}).get("name", sid)[:22]
        ok  = sid in marked
        if ok: present += 1
        else:  absent  += 1
        bg  = (18, 48, 22) if ok else (22, 27, 38)
        col = (63, 185, 80) if ok else (100, 100, 100)
        cv2.rectangle(canvas, (0, y - ROW_H + 4), (W, y + 6), bg, -1)
        cv2.putText(canvas, sid[:18],   (8,   y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)
        cv2.putText(canvas, nm,         (140, y), cv2.FONT_HERSHEY_SIMPLEX, 0.38, col, 1)
        cv2.putText(canvas, "PRESENT" if ok else "absent",
                    (340, y), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (63, 185, 80) if ok else (80, 80, 80), 1)
        y += ROW_H

    cv2.rectangle(canvas, (0, H - 46), (W, H), (15, 23, 42), -1)
    cv2.putText(canvas,
                f"Present: {present}   Absent: {absent}   Total: {len(enrolled_ids)}",
                (10, H - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 165, 0), 1)
    return canvas


# ──────────────────────────────────────────────────────────────────────────
def main():
    args    = sys.argv[1:]
    stream  = args[0] if len(args) > 0 else "Unknown"
    cls     = args[1] if len(args) > 1 else "Unknown"
    subject = args[2] if len(args) > 2 else "General"

    # ── Load encodings ─────────────────────────────────────────────────────
    if not os.path.exists(ENCODINGS_FILE):
        print("❌  face_encodings.pkl not found. Register students first.")
        return

    store = load_encodings()
    if not store:
        print("❌  No encodings found. Register at least one student.")
        return

    # Build flat lists for face_recognition.compare_faces
    known_encodings = []   # list of np.array (128-d)
    known_labels    = []   # matching list of "student_id|name" strings
    for key, val in store.items():
        for enc in val["encodings"]:
            known_encodings.append(enc)
            known_labels.append(key)

    print(f"  Loaded {len(known_encodings)} encodings for {len(store)} student(s).")

    # ── Load DB ────────────────────────────────────────────────────────────
    db       = load_db()
    students = db.get("students", {})

    target_key   = f"{stream}|{cls}"
    enrolled_ids = {sid for sid, d in students.items()
                    if d.get("class_key") == target_key}
    print(f"  Enrolled: {enrolled_ids or '(none found)'}")

    # ── Attendance CSV ─────────────────────────────────────────────────────
    att_dir  = os.path.join(BASE_DIR, "attendance", stream, cls, subject)
    os.makedirs(att_dir, exist_ok=True)
    att_file = os.path.join(att_dir, datetime.now().strftime("%Y-%m-%d") + ".csv")
    cols_csv = ["StudentID", "Name", "Stream", "Class", "Subject", "Time", "Confidence"]
    if not os.path.exists(att_file):
        pd.DataFrame(columns=cols_csv).to_csv(att_file, index=False)

    existing = pd.read_csv(att_file)
    marked   = set(existing["StudentID"].astype(str).tolist())

    # ── Haar cascade for fast preview boxes ───────────────────────────────
    face_det = cv2.CascadeClassifier(CASCADE)

    # ── Open camera ───────────────────────────────────────────────────────
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    cam_win  = f"Attendance — {stream}/{cls}/{subject}  |  Q to stop"
    dash_win = "Live Attendance Panel"

    print("📸  Running attendance (face_recognition model). Press Q to stop.")

    # Process every Nth frame to keep UI responsive
    PROCESS_EVERY = 3
    frame_idx     = 0

    # Cache last recognition results so non-processed frames still show boxes
    last_results  = []   # list of (x, y, w, h, sid, sname, conf_pct, color, txt)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        disp = frame.copy()

        if frame_idx % PROCESS_EVERY == 0:
            # ── Downsample for faster face_recognition ────────────────────
            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

            # Use haar for location (fast), then dlib for encoding (accurate)
            gray   = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            bright = cv2.convertScaleAbs(gray, alpha=1.2, beta=15)
            haar_f = face_det.detectMultiScale(bright, 1.1, 5, minSize=(40, 40))

            if len(haar_f):
                # Convert haar boxes to face_recognition top-right-bottom-left format
                fr_locs = []
                for (x, y, w, h) in haar_f:
                    fr_locs.append((y, x + w, y + h, x))   # top, right, bottom, left

                encodings = face_recognition.face_encodings(rgb, fr_locs)
            else:
                fr_locs   = face_recognition.face_locations(rgb, model="hog")
                encodings = face_recognition.face_encodings(rgb, fr_locs)

            last_results = []

            for (top, right, bottom, left), face_enc in zip(fr_locs, encodings):
                # Scale coords back to full-res
                x = left   * 2
                y = top    * 2
                w = (right - left)  * 2
                h = (bottom - top)  * 2

                # Compare against all known encodings
                distances = face_recognition.face_distance(known_encodings, face_enc)
                best_idx  = int(np.argmin(distances))
                best_dist = distances[best_idx]

                conf_pct = round((1.0 - best_dist) * 100, 1)

                if best_dist <= TOLERANCE:
                    composite        = known_labels[best_idx]
                    sid, sname       = composite.split("|", 1)

                    if sid not in enrolled_ids:
                        color = (0, 80, 200)
                        txt   = "Not enrolled here"
                    else:
                        color = (34, 197, 94)
                        txt   = f"{sname}  {conf_pct}%"
                        if sid not in marked:
                            df = pd.read_csv(att_file)
                            new_row = pd.DataFrame([{
                                "StudentID": sid, "Name": sname,
                                "Stream": stream, "Class": cls,
                                "Subject": subject,
                                "Time": datetime.now().strftime("%H:%M:%S"),
                                "Confidence": conf_pct
                            }])
                            df = pd.concat([df, new_row], ignore_index=True)
                            df.to_csv(att_file, index=False)
                            marked.add(sid)
                            print(f"  ✅  {sname} ({sid})  conf={conf_pct}%")
                else:
                    sid   = ""
                    sname = ""
                    color = (0, 0, 200)
                    txt   = "Unknown"

                last_results.append((x, y, w, h, sid, sname, conf_pct, color, txt))

        # ── Draw boxes from last results ───────────────────────────────────
        for (x, y, w, h, sid, sname, conf_pct, color, txt) in last_results:
            cv2.rectangle(disp, (x, y), (x + w, y + h), color, 2)
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(disp, (x, y - th - 14), (x + tw + 8, y - 2), color, -1)
            cv2.putText(disp, txt, (x + 4, y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # ── HUD ───────────────────────────────────────────────────────────
        cv2.rectangle(disp, (0, 0), (disp.shape[1], 40), (15, 23, 42), -1)
        cv2.putText(disp,
                    f"  {len(marked)}/{len(enrolled_ids)} marked  |  {subject}  |  Q = stop",
                    (6, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (240, 165, 0), 2)

        cv2.imshow(cam_win, disp)
        cv2.imshow(dash_win, make_dashboard(
            enrolled_ids, students, marked, stream, cls, subject))

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\n  Saved → {att_file}")
    print(f"  Total: {len(marked)}/{len(enrolled_ids)} marked present")


if __name__ == "__main__":
    main()
