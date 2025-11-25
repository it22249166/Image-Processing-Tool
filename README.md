 # DIP-test — Digital Image Processing GUI

This repository contains a Tkinter-based desktop image editor with a whiteboard and an experimental LAN real-time collaboration prototype.

This README explains how to set up a Python environment, install dependencies, run the app, test whiteboard collaboration on a single machine (LAN), and troubleshoot common issues. The goal is that another user can follow these steps and have the app + collaboration working in one try.

Supported OS: macOS (tested). The instructions use zsh but should work in bash too.

---

1) Create and activate a Python environment (recommended)

Prefer using a virtualenv or conda environment so dependencies are isolated.

venv (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

conda example:

```bash
conda create -n dip-test python=3.11 -y
conda activate dip-test
```

Important: always use the same `python` executable for installing packages and running the app. Verify with:

```bash
python -c "import sys; print(sys.executable)"
```

2) Install dependencies

The repo includes a `requirements.txt` with core and optional real-time libs. Install everything with:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If you only want the non-real-time features, remove the socketio/flask/eventlet lines from `requirements.txt` before installing.

Notes for macOS:
- `tkinter` is usually provided by system Python. If you get Tk errors, install Python from python.org or use Homebrew/Tcl-Tk where recommended.

3) Run the app (editor + whiteboard)

From the project root:

```bash
python main.py
```

This opens the main GUI. Use the left control panel to Upload an image, apply filters, or open the Whiteboard.

4) Whiteboard features (quick)

- Open the Whiteboard from the app (File / Tools or the Whiteboard button). The whiteboard supports:
  - Pen/Eraser, Line, Rectangle, Ellipse
  - Text objects (double-click to edit)
  - Attachments (image stickers) which can be moved/resized
  - Undo/Redo
  - Save / Insert to editor / Export Pack / Import Pack / Publish to `./community`

5) LAN real-time collaboration (one-machine test)

The project includes `collab_server.py` (a minimal Socket.IO server) and client integration in the Whiteboard. This is intended for LAN/local testing. Follow these steps to test locally on one machine:

- Start the collaboration server (defaults to port 5000). If you see "Address already in use" you can change the port in the server file or free the port — see troubleshooting below.

```bash
python collab_server.py
```

- Confirm the server is healthy (in another terminal):

```bash
curl http://127.0.0.1:5000/health
# expected output: OK
```

- Start two or more instances of the app (each in its own terminal):

```bash
python main.py
python main.py
```

- In each Whiteboard window click the "Collab Connect" button and enter the server URL (for same-machine testing):

```
http://127.0.0.1:5000
```

- What to expect on success:
  - The whiteboard toolbar shows a small status label: "Collab: Connected".
  - A messagebox "Connected to: <server>" appears.
  - The server terminal prints "Client connected: <sid>" for each client.
  - When you draw a stroke and finish it (mouse up), that stroke is emitted to the server and broadcast to other clients; other windows render the stroke.

6) Export / Import / Publish packs (asynchronous collaboration)

- Export Pack: creates a zip containing `base.png`, attachments, and `manifest.json`. Use the Whiteboard → Export Pack.
- Import Pack: load a zip exported by another user. Use Whiteboard → Import Pack.
- Publish: creates a prettier pack in `./community` with metadata and thumbnail.

These allow people to share state without a running server.

7) Troubleshooting & common fixes

- "python-socketio is required" message when clicking Collab Connect:
  - Make sure you installed `python-socketio` in the same Python environment you use to run `main.py`.
  - Install explicitly with the `python` executable you printed earlier:

```bash
python -m pip install "python-socketio[client]" flask eventlet
```

- Address already in use when starting `collab_server.py`:
  - Find the process using the port and stop it:

```bash
lsof -nP -iTCP:5000 -sTCP:LISTEN
kill <PID>
```

  - Or change port by editing `collab_server.py` (the call to `eventlet.wsgi.server(..., ('0.0.0.0', 5000) ...)`) and restart.

- Client cannot connect / Connection failed:
  - Verify server is running and reachable (use curl health endpoint above).
  - If using a different machine, use the host machine LAN IP (find it with `ipconfig getifaddr en0` on macOS or `ifconfig`). The server binds to `0.0.0.0` so remote machines on the same LAN can connect via `http://<host-ip>:5000`.
  - Ensure no firewall blocks the port.

- Tkinter GUI or font errors on macOS:
  - Use a Python installation that bundles a working Tcl/Tk (python.org installer) or ensure Homebrew Tcl/Tk and set appropriate environment variables. The app will fall back to default fonts where possible.

8) Advanced notes and next steps

- The real-time server is intentionally minimal and keeps state in memory. For persistence, attachment uploads, or multi-machine public hosting, I can:
  - Add an HTTP upload endpoint and store attachments on disk or S3.
  - Persist `CANV_STATE` to disk and add session save/load endpoints.
  - Add authentication and TLS (Let's Encrypt + nginx) and provide a deploy guide for a small VPS.

9) Repro checklist for another user (one-try run)

From a fresh macOS system with Python 3.11+ installed:

```bash
# create & activate environment
python3 -m venv .venv
source .venv/bin/activate

# upgrade pip and install deps
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# start server (open a terminal)
python collab_server.py

# open two terminals and start the GUI twice
python main.py
python main.py

# In each GUI: Whiteboard -> Collab Connect -> enter http://127.0.0.1:5000
# Draw and verify strokes sync across windows
```

If that fails, check `python -c "import sys; print(sys.executable)"` and that `python -m pip list` includes `python-socketio` and `eventlet`.

10) Getting help

If something doesn't work, paste these into an issue or message:
- Output of `python -c "import sys; print(sys.executable)"`
- Output of `python -m pip list --format=columns | egrep "socketio|eventlet|flask|Pillow"`
- Server terminal logs and client messagebox text.

---

Happy testing — tell me which extra feature you want next (attachment uploads, persistence, public deploy guide, or improved selection UX) and I will implement it.
# DIP-test — Digital Image Processing GUI

This repository contains a simple Tkinter-based GUI for image processing tasks (grayscale, flip, rotate, invert, crop, etc.).

Quick start (macOS, zsh):

1. Create and activate a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

Note: On macOS the `tkinter` package is usually provided by the system Python. If you see errors about Tk, install the `python-tk` equivalent via Homebrew or use the official python.org installer which includes Tcl/Tk support.

3. Run the application:

```bash
python main.py
```

4. Use the GUI to upload an image and try the tools.

If anything fails, paste the terminal output here and I'll help fix it.
Digital Image Processing Final Project# DIP-test

---

LAN Real-time Collaboration (optional)
=====================================

This project includes a minimal Socket.IO-based collaboration prototype for LAN testing.

Quick steps to try it on a single machine:

1. Install extra dependencies:

```bash
pip install -r requirements.txt
```

2. Start the collaboration server (from the project root):

```bash
python collab_server.py
```

3. Start two or more instances of the app (each in its own terminal):

```bash
python main.py
python main.py
```

4. In the Whiteboard window, click the "Collab Connect" button and enter:

```
http://127.0.0.1:5000
```

5. Draw in one window and verify strokes/text appear in the other windows.

Notes:
- This is a proof-of-concept intended for LAN/local testing. For production or public use you should secure the server (TLS, auth) and consider a hosted deployment.
- If you want me to wire attachment HTTP uploads or persist session history on disk, I can add that next.
