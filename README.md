# 👁️ Vision ERP — Face Recognition Attendance System

A desktop-based AI-powered ERP system that automates student attendance using live webcam and deep learning face recognition. Built with Python, OpenCV, and dlib.

---

## 📋 Prerequisites

Before setting up, make sure you have the following installed on your Windows PC:

- **Python 3.11** → [Download here](https://www.python.org/downloads/release/python-3110/)
- **CMake** (required for dlib) → [Download here](https://cmake.org/download/)
- **Visual C++ Build Tools** → [Download here](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- **Git** → [Download here](https://git-scm.com/)

> ⚠️ During Python installation, check **"Add Python to PATH"**.

---

## 🚀 Setup & Installation

### Step 1 — Clone the Repository

```bash
git clone https://github.com/your-username/vision-erp.git
cd vision-erp
```

---

### Step 2 — Verify Python 3.11

```bash
py -3.11 --version
```

Expected output: `Python 3.11.x`

---

### Step 3 — Create Virtual Environment

```bash
py -3.11 -m venv venv311
```

---

### Step 4 — Activate Virtual Environment

```bash
venv311\Scripts\activate
```

You should see `(venv311)` at the start of your terminal line.

---

### Step 5 — Install Dependencies

Run these commands **in order** (dlib must be installed before face_recognition):

```bash
pip install cmake
pip install dlib
pip install face_recognition
pip install git+https://github.com/ageitgey/face_recognition_models
pip install opencv-python pandas requests PyJWT cryptography Pillow
```

> ⏳ `dlib` installation takes a few minutes — this is normal.

---

### Step 6 — Prepare Logo Assets (First Time Only)

```bash
python convert_logo.py
python prepare_installer_logos.py
```

---

### Step 7 — Run the Application

```bash
venv311\Scripts\activate
python erp_main.py
```

---

## 📁 Project Structure

```
vision-erp/
│
├── erp_main.py                        # Main application entry point
├── capture_and_train.py               # Face enrollment & encoding
├── take_attendance.py                 # Live attendance engine
├── oauth_manager.py                   # OAuth 2.0 (Google/Microsoft) auth
├── convert_logo.py                    # One-time logo converter
├── prepare_installer_logos.py         # One-time installer asset prep
│
├── haarcascade_frontalface_default.xml  # Face detection model
├── haarcascade_frontalface_alt.xml      # Alternate face detection model
│
├── requirements.txt                   # Core dependencies
├── oauth_config.json                  # OAuth credentials (fill before use)
└── README.md
```

---

## ⚙️ OAuth Setup (Optional)

To enable Google/Microsoft login, edit `oauth_config.json`:

```json
{
  "google": {
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "enabled": true
  },
  "microsoft": {
    "client_id": "YOUR_MICROSOFT_CLIENT_ID",
    "client_secret": "YOUR_MICROSOFT_CLIENT_SECRET",
    "tenant_id": "common",
    "enabled": false
  }
}
```

> 🔐 Never push real credentials to GitHub. Add `oauth_config.json` to `.gitignore` after filling it.

---

## 🧪 First Run Checklist

- [ ] Python 3.11 installed and verified
- [ ] Virtual environment created and activated
- [ ] All dependencies installed successfully
- [ ] `logo.png` present in project root
- [ ] `erp_main.py` runs without errors

---

## 🛠️ Common Issues

| Problem | Fix |
|---|---|
| `dlib` fails to install | Make sure CMake and Visual C++ Build Tools are installed |
| `face_recognition` not found | Install dlib first, then face_recognition |
| Camera not opening | Check webcam connection; try changing `cv2.VideoCapture(0)` to `(1)` |
| `face_encodings.pkl` not found | Register at least one student first via the enrollment screen |
| `venv311\Scripts\activate` not working | Run in **Command Prompt**, not PowerShell |

---

## 👥 Authors

- **Dhrubajyoti Nath** — CS24MCAGN005
- **Violina Saikia** — CS24MCAGN013

*MCA Semester IV Project — The Assam Kaziranga University, Jorhat, Assam | June 2026*

*Supervisor: Prof. Ratan Kumar Saha, HOD*
