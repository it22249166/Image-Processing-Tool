import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFilter, ImageEnhance, ImageFont
import os
import numpy as np
import subprocess
import sys
from pathlib import Path
import io
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import zipfile
import json
import base64
import webbrowser
import time
import datetime

# Optional OpenCV import (fall back gracefully if not present)
try:
    import cv2
except Exception:
    cv2 = None
import threading
import traceback
import uuid


# --- PySide6 Fallback for File Picking (Optional) ---

def pick_file_with_pyside():
    """Return a selected file path using PySide6's QFileDialog, or None if PySide6 isn't available or canceled."""
    try:
        # Prevent runtime errors if PySide6 is not installed/working
        from PySide6.QtWidgets import QApplication, QFileDialog
    except Exception:
        return None

    app = QApplication.instance()
    created_app = False
    if app is None:
        app = QApplication([])
        created_app = True

    try:
        dialog_filter = "Images (*.png *.jpg *.jpeg *.gif);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(None, "Open Image", "", dialog_filter)
    except Exception:
        file_path = None

    if created_app:
        try:
            # Quit the temporary application instance
            app.quit()
        except Exception:
            pass

    return file_path


class PhotoEditorApp(tk.Tk):
    """
    Advanced Image Editor combining a professional dark UI (Tkinter) 
    with image processing (Pillow) and local analysis (NumPy, Matplotlib).
    """
    def __init__(self):
        super().__init__()
        self.title("VisionX Learner - Advanced Image Editor with Local Analysis")
        self.geometry("1400x900")
        
        # --- THEME PALETTES ---
        # Dark Mode Palette (Using existing user colors)
        self.dark_palette = {
            'bg': "#08211D",        
            'panel_bg': '#000000',       
            'accent_primary': '#1C7367', 
            'accent_hover': '#124A42',   
            'fg_color': '#c3cfd5',       
            'separator_color': '#269C8B',
            'error_color': '#E74C3C',
            'success_color': '#2ECC71'
        }
        
        # Light Mode Palette (New bright theme)
        self.light_palette = {
            'bg': "#F1F9F9",
            'panel_bg': '#CEE9E9',
            'accent_primary': '#88C9C9',
            'accent_hover': '#64BABA',
            'fg_color': "#000000",
            'separator_color': '#BBBBBB',
            'error_color': '#DC3545',
            'success_color': '#28A745'
        }
        self.current_mode = 'dark' # Initial mode
        # Font must be defined before configuring styles
        self.font_main = 'Inter'
        # Set initial theme and configuration
        self.set_theme('dark', initial=True)
        self.configure(bg=self.dark_bg)
        
        self._configure_styles()
        
        # --- Image and History State ---
        self.img = None
        self.original_img = None 
        self.img_history = [] 
        # Path to the currently loaded image (if loaded via file dialog)
        self.current_image_path = None

        # --- Cropping State ---
        self.cropping = False
        self.crop_rectangle = None 
        self.start_x, self.start_y = 0, 0 

        # --- Drag-Resize State ---
        self.resizing = False
        self.resize_mode = None 
        self.resize_handles = {} 
        self.resize_handle_size = 10
        self.img_display_box = None # (x1, y1, x2, y2) on canvas
        self.original_img_size_on_canvas = None
        self.original_canvas_mouse_pos = None
        self.current_temp_img = None # Holds the temporary image during slider/resize preview
        self.tk_img_temp = None # Keep a reference for temporary display

        # --- Adjustment Variables (New Interactive Sliders) ---
        self.flip_var = tk.StringVar(value="Horizontal")
        self.brightness_var = tk.DoubleVar(value=1.0)
        self.contrast_var = tk.DoubleVar(value=1.0)
        self.blur_var = tk.DoubleVar(value=0.0)

        # --- Initialize UI Layout ---
        self._create_menu_bar()
        self._create_main_layout()
        # Populate recent menu at startup (in-memory recent list)
        try:
            self._update_recent_menu()
        except Exception:
            pass
    
    def set_theme(self, mode, initial=False):
        """Switches the application between dark and light modes."""
        if mode == 'dark':
            palette = self.dark_palette
        elif mode == 'light':
            palette = self.light_palette
        else:
            return

        # 1. Update active color variables
        self.dark_bg = palette['bg']
        self.panel_bg = palette['panel_bg']
        self.accent_primary = palette['accent_primary']
        self.accent_hover = palette['accent_hover']
        self.fg_color = palette['fg_color']
        self.separator_color = palette['separator_color']
        self.error_color = palette['error_color']
        self.success_color = palette['success_color']

        # 2. Update root window background
        self.configure(bg=self.dark_bg)
        self.current_mode = mode

        # 3. Reconfigure styles (ttk widgets)
        self._configure_styles()
        
        # 4. Recursively update all tk widgets (manual update needed for tk widgets)
        if not initial:
            self._update_all_widgets(self)

    def _update_all_widgets(self, widget):
        """Recursively updates the colors of all TK widgets (Label, Frame, Canvas, etc.)."""
        # Set background and foreground for standard tk widgets
        try:
            widget.config(bg=self.panel_bg, fg=self.fg_color)
        except tk.TclError:
            # Some widgets (like Toplevel/Tk root) don't have fg
            try:
                widget.config(bg=self.panel_bg)
            except tk.TclError:
                pass
        
        # Handle specialized widgets like the main canvas background
        if widget is self.canvas:
            widget.config(bg=self.dark_bg)

        # Continue recursion for children
        for child in widget.winfo_children():
            self._update_all_widgets(child)    

    def _configure_styles(self):
        """Sets up the dark theme for Tkinter and ttk widgets with a smoother look."""
        style = ttk.Style(self)
        style.theme_use('clam')
        
        # General styles
        style.configure("TFrame", background=self.panel_bg)
        style.configure("TLabel", background=self.panel_bg, foreground=self.fg_color, font=(self.font_main, 10))
        style.configure("TCheckbutton", background=self.panel_bg, foreground=self.fg_color, focuscolor=self.accent_primary)
        style.configure("TSeparator", background=self.separator_color) # Use separator color

        # --- Primary Button (Main Actions: Open, Apply, Commit) ---
        style.configure("Primary.TButton", 
                        font=(self.font_main, 10, 'bold'), 
                        padding=[12, 10], 
                        relief="flat",
                        background=self.accent_primary, 
                        foreground=self.dark_bg, # Dark text on bright button
                        borderwidth=0) 
        style.map("Primary.TButton", 
                  background=[('active', self.accent_hover), ('disabled', self.separator_color)],
                  foreground=[('active', 'white'), ('disabled', self.fg_color)])

        # --- Secondary Button (Tool/Sidebar Buttons & Menu Bar Tools) ---
        style.configure("Secondary.TButton", 
                        font=(self.font_main, 10),
                        background=self.panel_bg, # Match panel BG for integrated look
                        foreground=self.fg_color,
                        padding=[10, 8],
                        relief="flat",
                        borderwidth=1,
                        bordercolor=self.panel_bg) # Border matches panel for smooth effect
        style.map("Secondary.TButton", 
                  background=[('active', self.separator_color)], # Subtle hover 
                  foreground=[('active', 'white')])
                  
        # Slider/Scale Style
        style.configure("TScale", 
                        background=self.panel_bg, 
                        foreground=self.fg_color, 
                        sliderrelief='flat',
                        troughcolor=self.separator_color,
                        sliderthickness=15) # Make slider handle slightly larger
        style.map("TScale",
                  background=[('active', self.accent_primary)])

        # Combobox Style (Making it dark mode friendly)
        style.configure("TCombobox", 
                        fieldbackground=self.panel_bg,
                        background=self.panel_bg,
                        foreground=self.fg_color,
                        selectbackground=self.accent_hover,
                        selectforeground='white',
                        arrowcolor=self.accent_primary,
                        borderwidth=1,
                        relief='flat')
        style.map("TCombobox", 
                 fieldbackground=[('readonly', self.panel_bg)], 
                 selectbackground=[('readonly', self.accent_primary)])


    # --- UI Component Creation ---

    def _create_menu_bar(self):
        """Creates a mock menu bar at the top."""
        # Keep a visual toolbar bar, but also create a real menubar for File operations
        menu_bar = tk.Frame(self, bg=self.panel_bg, height=35)
        menu_bar.pack(fill='x', side='top')

        # Title
        tk.Label(menu_bar, text="VisionX Learner",
                 bg=self.panel_bg, fg=self.accent_primary, padx=15,
                 font=(self.font_main, 12, 'bold')).pack(side='left')

        # Visual mock menu labels for spacing/visuals (these are not the actual OS menu)
        menu_frame = tk.Frame(menu_bar, bg=self.panel_bg)
        menu_frame.pack(side='left', padx=10)
        for item in [" ", " ", " "]:
            tk.Label(menu_frame, text=item, bg=self.panel_bg, fg=self.fg_color, padx=8, pady=5, font=(self.font_main, 10)) \
                .pack(side='left', padx=2)

        # Theme Toggle Button
        def toggle_theme():
            if self.current_mode == 'dark':
                self.set_theme('light')
            else:
                self.set_theme('dark')

        ttk.Button(menu_bar, text="Toggle Theme", command=toggle_theme,
                   style="Secondary.TButton").pack(side='right', padx=15, pady=5)

        # Main Action Buttons - Use Primary for Open, Secondary for others
        ttk.Button(menu_bar, text="Open Image", command=self.upload_image,
                   style="Primary.TButton").pack(side='right', padx=5, pady=5)
        ttk.Button(menu_bar, text="Whiteboard", command=self.open_whiteboard,
           style="Secondary.TButton").pack(side='right', padx=5, pady=5)
        ttk.Button(menu_bar, text="View Properties", command=self.view_image_properties,
                   style="Secondary.TButton").pack(side='right', padx=5, pady=5)
        ttk.Button(menu_bar, text="Undo", command=self.undo_last_action,
                   style="Secondary.TButton").pack(side='right', padx=5, pady=5)

        # --- Native menubar for File operations (good for keyboard shortcuts & macOS menu) ---
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='Open...', command=self.upload_image, accelerator='Ctrl+O')
        # file_menu.add_command(label='Save', command=self.file_save, accelerator='Ctrl+S')
        file_menu.add_command(label='Save', command=self.file_save_as, accelerator='Ctrl+Shift+S')
        file_menu.add_separator()
        file_menu.add_command(label='Export...', command=self.file_export)
        # file_menu.add_command(label='Upload to Drive...', command=self.file_export_to_drive)
        file_menu.add_separator()

        # Recent submenu
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label='Recent', menu=self.recent_menu)
        file_menu.add_separator()
        file_menu.add_command(label='Close Image', command=self.file_close_image)
        file_menu.add_command(label='Exit', command=self.file_exit)
        menubar.add_cascade(label='File', menu=file_menu)

        # Attach menubar to the root window (native menu on macOS)
        try:
            self.config(menu=menubar)
        except Exception:
            pass

        # Keyboard shortcuts
        # Ctrl/Command depends on platform; bind both common variants
        self.bind_all('<Control-s>', lambda e: self.file_save())
        self.bind_all('<Control-S>', lambda e: self.file_save_as())
        self.bind_all('<Command-s>', lambda e: self.file_save())
        self.bind_all('<Command-S>', lambda e: self.file_save_as())
        self.bind_all('<Control-o>', lambda e: self.upload_image())


    def _create_main_layout(self):
        """Creates the three-panel layout (Controls, Canvas, Status)."""
        main_frame = tk.Frame(self, bg=self.dark_bg)
        main_frame.pack(fill='both', expand=True)

        # 1. Left Control Panel (Combines Tools and Adjustments)
        self._create_control_panel(main_frame)
        
        # 2. Center Canvas
        self._create_canvas(main_frame)

        # 3. Status Bar (Bottom)
        status_bar = tk.Frame(self, bg=self.panel_bg, height=25)
        status_bar.pack(fill='x', side='bottom')
        self.status_label = tk.Label(status_bar, text="Ready.", bg=self.panel_bg, fg=self.fg_color, anchor='w', font=(self.font_main, 10))
        self.status_label.pack(side='left', padx=10)
        # Recent files storage (in-memory for this session)
        self.recent_files = []

    # --- File menu handlers (ensure these exist for menu callbacks) ---
    def _update_recent_menu(self):
        try:
            self.recent_menu.delete(0, 'end')
        except Exception:
            return
        if not self.recent_files:
            self.recent_menu.add_command(label='(No recent files)', state='disabled')
            return
        for p in list(self.recent_files)[-5:][::-1]:
            self.recent_menu.add_command(label=os.path.basename(p), command=lambda p=p: self._open_recent(p))

    def _add_to_recent(self, path):
        try:
            if path in self.recent_files:
                self.recent_files.remove(path)
            self.recent_files.append(path)
            self.recent_files = self.recent_files[-20:]
            self._update_recent_menu()
        except Exception:
            pass

    def _open_recent(self, path):
        try:
            if Path(path).exists():
                new_img = Image.open(path).convert('RGB')
                self.original_img = new_img.copy()
                self.img = new_img.copy()
                self.current_image_path = path
                self.img_history = [self.img.copy()]
                self.update_canvas()
                self.status_label.config(text=f"Image loaded: {os.path.basename(path)}", foreground=self.success_color)
            else:
                messagebox.showwarning('Recent File', f'File not found: {path}')
                try:
                    self.recent_files.remove(path)
                except Exception:
                    pass
                self._update_recent_menu()
        except Exception as e:
            messagebox.showerror('Open Recent', f'Failed to open recent file: {e}')

    def file_save(self):
        if not self.img:
            messagebox.showwarning('Save', 'No image loaded to save.')
            return
        if getattr(self, 'current_image_path', None):
            try:
                self.img.save(self.current_image_path)
                self.status_label.config(text=f'Saved: {os.path.basename(self.current_image_path)}', foreground=self.success_color)
                self._add_to_recent(self.current_image_path)
            except Exception as e:
                messagebox.showerror('Save Error', f'Failed to save image: {e}')
        else:
            self.file_save_as()

    def file_save_as(self):
        if not self.img:
            messagebox.showwarning('Save As', 'No image loaded to save.')
            return
        filetypes = [('PNG Image', '*.png'), ('JPEG Image', '*.jpg;*.jpeg'), ('All files', '*.*')]
        try:
            path = filedialog.asksaveasfilename(defaultextension='.png', filetypes=filetypes)
        except Exception:
            path = None
        if path:
            try:
                ext = Path(path).suffix.lower()
                if ext in ['.jpg', '.jpeg']:
                    self.img.save(path, quality=95, subsampling=0)
                else:
                    self.img.save(path)
                self.current_image_path = path
                self.status_label.config(text=f'Saved as: {os.path.basename(path)}', foreground=self.success_color)
                self._add_to_recent(path)
            except Exception as e:
                messagebox.showerror('Save As Error', f'Failed to save image: {e}')

    def file_export(self):
        if not self.img:
            messagebox.showwarning('Export', 'No image loaded to export.')
            return
        filetypes = [('JPEG Image', '*.jpg;*.jpeg'), ('PNG Image', '*.png')]
        path = filedialog.asksaveasfilename(defaultextension='.jpg', filetypes=filetypes)
        if not path:
            return
        try:
            ext = Path(path).suffix.lower()

            # Ensure JPEGs are in RGB mode (JPEG does not support alpha)
            save_img = self.img
            if ext in ['.jpg', '.jpeg']:
                if save_img.mode in ('RGBA', 'LA') or (hasattr(save_img, 'getchannel') and 'A' in save_img.getbands()):
                    save_img = save_img.convert('RGB')

            # Try the preferred save options for JPEG, but be defensive: some Pillow versions may not accept 'subsampling'
            if ext in ['.jpg', '.jpeg']:
                try:
                    save_img.save(path, quality=92, subsampling=0)
                except TypeError:
                    # Older/newer Pillow may not accept subsampling kwarg — try without it
                    save_img.save(path, quality=92)
            else:
                # PNG, etc.
                save_img.save(path)

            messagebox.showinfo('Export', f'Exported: {path}')
            self._add_to_recent(path)
            self.status_label.config(text=f'Exported: {os.path.basename(path)}', foreground=self.success_color)
        except PermissionError:
            messagebox.showerror('Export Error', f'Permission denied writing to: {path}')
            self.status_label.config(text='Export failed (permission).', foreground=self.error_color)
        except Exception as e:
            # Write full traceback to a log file to help debugging on the user's machine
            try:
                log_path = Path(__file__).resolve().parent / 'export_error.log'
                with open(log_path, 'a', encoding='utf-8') as fh:
                    fh.write('\n--- Export Error ---\n')
                    fh.write(str(Path(path)) + '\n')
                    fh.write(traceback.format_exc())
            except Exception:
                pass
            # Provide a concise message to the user and point to the log
            messagebox.showerror('Export Error', f'Failed to export image: {e}\n\nDetails written to export_error.log in the project folder.')
            self.status_label.config(text='Export failed.', foreground=self.error_color)

    def file_export_to_drive(self):
        """Upload the current image to Google Drive using OAuth.

        Requires a `client_secrets.json` file in the project root with OAuth 2.0
        client credentials. Tokens will be stored in `token_drive.json`.

        If the google API libraries are missing the user will be prompted to
        install them:
          pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
        """
        if not self.img:
            messagebox.showwarning('Upload to Drive', 'No image loaded to upload.')
            return

        # Ask for the filename to use on Drive
        try:
            from tkinter import simpledialog
            filename = simpledialog.askstring('Upload to Drive', 'Enter the filename to use on Drive (e.g. image.jpg):')
        except Exception:
            filename = None

        if not filename:
            return

        # Determine format from extension
        ext = Path(filename).suffix.lower()
        if ext in ['.jpg', '.jpeg']:
            fmt = 'JPEG'
            mime = 'image/jpeg'
        else:
            fmt = 'PNG'
            mime = 'image/png'

        # Prepare image bytes
        try:
            buf = io.BytesIO()
            save_img = self.img
            if fmt == 'JPEG' and save_img.mode in ('RGBA', 'LA'):
                save_img = save_img.convert('RGB')
            save_img.save(buf, format=fmt)
            buf.seek(0)
        except Exception as e:
            messagebox.showerror('Upload Error', f'Failed to prepare image bytes for upload: {e}')
            return

        # Try to import Google API libraries
        try:
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseUpload
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            import google.auth
        except Exception:
            messagebox.showerror('Missing Packages',
                                 'Google API client libraries are not installed.\n'
                                 'Install with:\n'
                                 'pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib')
            return

        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        token_path = Path(__file__).resolve().parent / 'token_drive.json'
        secrets_path = Path(__file__).resolve().parent / 'client_secrets.json'

        if not secrets_path.exists():
            messagebox.showerror('Missing client_secrets.json',
                                 f'Place your OAuth client_secrets.json in the project folder:\n{secrets_path}')
            return

        try:
            # Load or refresh credentials
            if token_path.exists():
                import json
                with open(token_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # attempt to create credentials from token file
                from google.oauth2.credentials import Credentials
                creds = Credentials.from_authorized_user_info(data, SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
                    try:
                        creds = flow.run_local_server(port=0)
                    except Exception:
                        # Fallback for environments where opening a browser fails (headless macOS, blocked browser)
                        # run_console prints a URL — user can paste into a browser manually.
                        creds = flow.run_console()

                # Save the credentials for the next run
                try:
                    import json
                    with open(token_path, 'w', encoding='utf-8') as f:
                        f.write(creds.to_json())
                except Exception:
                    pass

            service = build('drive', 'v3', credentials=creds)

            media = MediaIoBaseUpload(buf, mimetype=mime, resumable=False)
            file_metadata = {'name': filename}
            uploaded = service.files().create(body=file_metadata, media_body=media, fields='id,name').execute()
            file_id = uploaded.get('id')
            messagebox.showinfo('Upload Complete', f'File uploaded to Drive with ID: {file_id}')
            self.status_label.config(text=f'Uploaded to Drive: {filename}', foreground=self.success_color)

        except Exception as e:
            # Log full traceback and show concise error
            try:
                logp = Path(__file__).resolve().parent / 'export_error.log'
                with open(logp, 'a', encoding='utf-8') as fh:
                    fh.write('\n--- Drive Upload Error ---\n')
                    fh.write(traceback.format_exc())
            except Exception:
                pass
            messagebox.showerror('Drive Upload Failed', f'Failed to upload to Drive: {e}\n\nSee export_error.log for details')
            self.status_label.config(text='Drive upload failed.', foreground=self.error_color)

    def file_close_image(self):
        if not self.img:
            return
        try:
            confirm = messagebox.askyesno('Close Image', 'Close current image? Unsaved changes will be lost.')
            if confirm:
                self.img = None
                self.original_img = None
                self.current_image_path = None
                self.img_history = []
                self.canvas.delete('all')
                self.status_label.config(text='Image closed.', foreground=self.fg_color)
        except Exception as e:
            messagebox.showerror('Close Error', f'Failed to close image: {e}')

    def file_exit(self):
        try:
            if self.img is not None:
                resp = messagebox.askyesnocancel('Exit', 'Save changes before exiting?')
                if resp is None:
                    return
                if resp is True:
                    self.file_save()
            self.quit()
        except Exception:
            self.quit()
    
    def open_advanced_options(self):
        """
        Launches the advanced_options.py script in a new process to open 
        the secondary advanced manipulation window.
        """
        script_name = 'advanced_options.py'
        # Construct the absolute path to the script
        # Using pathlib.Path(__file__).resolve().parent ensures we get the directory 
        # of the currently executing script, even if run from elsewhere.
        script_path = Path(__file__).resolve().parent / script_name
        
        if not script_path.exists():
            messagebox.showerror('Error', 
                                 f"Advanced Options script not found!\n\n"
                                 f"Attempted path: {script_path.resolve()}\n\n"
                                 f"Please ensure '{script_name}' exists in the same directory as photo_editor_app.py.")
            return

        try:
            # Launch the script using the current Python interpreter
            # If an image is currently loaded, pass its path as an argument so the advanced tool can load it
            cmd = [sys.executable, str(script_path)]
            if getattr(self, 'current_image_path', None):
                cmd.append(str(self.current_image_path))
            subprocess.Popen(cmd)
        except Exception as e:
            messagebox.showerror('Error', f'Failed to launch Advanced Options:\n{e}')

    def open_whiteboard(self):
        """Open a simple drawing whiteboard that can save or insert the drawing into the editor."""
        wb = tk.Toplevel(self)
        wb.title('Whiteboard')
        wb.geometry('900x700')
        wb.transient(self)

        # Scrollable toolbar so buttons remain accessible on small screens
        toolbar_container = ttk.Frame(wb)
        toolbar_container.pack(fill='x', side='top', padx=6, pady=6)
        toolbar_canvas = tk.Canvas(toolbar_container, height=44, highlightthickness=0)
        toolbar_canvas.pack(side='top', fill='x', expand=True)
        toolbar_hscroll = ttk.Scrollbar(toolbar_container, orient='horizontal', command=toolbar_canvas.xview)
        toolbar_hscroll.pack(side='top', fill='x')
        toolbar_canvas.configure(xscrollcommand=toolbar_hscroll.set)
        toolbar = ttk.Frame(toolbar_canvas)
        toolbar_canvas.create_window((0, 0), window=toolbar, anchor='nw')
        def _toolbar_configure(e):
            toolbar_canvas.configure(scrollregion=toolbar_canvas.bbox('all'))
        toolbar.bind('<Configure>', _toolbar_configure)

        # Default canvas size
        CANVAS_W, CANVAS_H = 800, 600

        # PIL backing image to store drawing (RGBA)
        wb_img = Image.new('RGBA', (CANVAS_W, CANVAS_H), (255, 255, 255, 0))
        wb_draw = ImageDraw.Draw(wb_img)

    # Separate objects: attachments (images) and text objects
        attachments = []  # each: {'img': PIL.Image, 'x':int, 'y':int, 'w':int, 'h':int}
    # collaboration server base url (if connected)
        collab_server_url = None
        text_objects = []  # each: {'text':str, 'x':int, 'y':int, 'fill':str, 'font':None}

        # Drawing state
        draw_color = tk.StringVar(value='#000000')
        pen_width = tk.IntVar(value=4)
        mode_var = tk.StringVar(value='Pen')
        drawing = {'active': False, 'last': (None, None), 'start': (None, None), 'selected': None, 'offset': (0, 0), 'resize': None}

        # History for undo/redo -- store snapshots containing image + attachments + texts
        wb_history = [{'img': wb_img.copy(), 'attachments': [], 'texts': []}]
        history_index = 0

        def push_history():
            nonlocal wb_history, history_index, wb_img, attachments, text_objects
            # truncate forward history
            wb_history = wb_history[:history_index+1]
            # deep-copy attachments (images copied) and texts
            at_copy = []
            for a in attachments:
                at_copy.append({'img': a['img'].copy(), 'x': a['x'], 'y': a['y'], 'w': a['w'], 'h': a['h']})
            txt_copy = [t.copy() for t in text_objects]
            wb_history.append({'img': wb_img.copy(), 'attachments': at_copy, 'texts': txt_copy})
            history_index = len(wb_history) - 1
            # limit
            if len(wb_history) > 30:
                wb_history = wb_history[-30:]
                history_index = len(wb_history) - 1

        def undo():
            nonlocal history_index, wb_img, wb_draw, attachments, text_objects
            if history_index > 0:
                history_index -= 1
                snap = wb_history[history_index]
                wb_img = snap['img'].copy()
                attachments = [ {'img':a['img'].copy(), 'x':a['x'], 'y':a['y'], 'w':a['w'], 'h':a['h']} for a in snap['attachments'] ]
                text_objects = [t.copy() for t in snap['texts']]
                wb_draw = ImageDraw.Draw(wb_img)
                update_preview()

        def redo():
            nonlocal history_index, wb_img, wb_draw, attachments, text_objects
            if history_index < len(wb_history) - 1:
                history_index += 1
                snap = wb_history[history_index]
                wb_img = snap['img'].copy()
                attachments = [ {'img':a['img'].copy(), 'x':a['x'], 'y':a['y'], 'w':a['w'], 'h':a['h']} for a in snap['attachments'] ]
                text_objects = [t.copy() for t in snap['texts']]
                wb_draw = ImageDraw.Draw(wb_img)
                update_preview()

        def choose_color():
            c = colorchooser.askcolor(title='Choose pen color', color=draw_color.get())
            if c and c[1]:
                draw_color.set(c[1])

        def attach_file():
            # Ask the user to pick an image file and add it as an attachment
            p = filedialog.askopenfilename(title='Choose attachment', filetypes=[('Image files', ('*.png','*.jpg','*.jpeg','*.bmp','*.gif')), ('All files','*.*')])
            if not p:
                return
            try:
                aimg = Image.open(p).convert('RGBA')
                # scale down if larger than canvas
                aw, ah = aimg.size
                maxw, maxh = CANVAS_W//2, CANVAS_H//2
                if aw > maxw or ah > maxh:
                    aimg.thumbnail((maxw, maxh), Image.Resampling.LANCZOS)
                    aw, ah = aimg.size
                ax = (CANVAS_W - aw)//2
                ay = (CANVAS_H - ah)//2
                # keep an original copy for high-quality resizes
                attach = {'id': str(uuid.uuid4()), 'img': aimg, 'orig_img': aimg.copy(), 'x': ax, 'y': ay, 'w': aw, 'h': ah}
                attachments.append(attach)
                push_history()
                update_preview()
                # if connected to collab server, upload the attachment and broadcast its URL
                try:
                    if collab_server_url and collab_connected:
                        import requests
                        upload_url = collab_server_url.rstrip('/') + '/upload'
                        with open(p, 'rb') as fh:
                            resp = requests.post(upload_url, files={'file': fh}, timeout=10)
                        if resp.status_code in (200, 201):
                            data = resp.json()
                            print('Attachment uploaded to server:', data)
                            # emit attach operation with id and remote url so other clients can fetch
                            emit_collab_operation('attach', {'id': attach['id'], 'url': data.get('url'), 'name': data.get('name'), 'x': attach['x'], 'y': attach['y'], 'w': attach['w'], 'h': attach['h']})
                except Exception as e:
                    print('collab attachment upload failed:', e)
            except Exception as e:
                messagebox.showerror('Attach Error', f'Failed to attach file: {e}')

        def export_collab():
            """Export a collaboration pack (zip) containing base image, attachments and manifest."""
            p = filedialog.asksaveasfilename(defaultextension='.zip', filetypes=[('Collaboration Pack', '*.zip')], title='Export Collaboration Pack')
            if not p:
                return
            try:
                # compose base image (wb_img only, without attachments/texts)
                base = wb_img.copy()
                manifest = {'attachments': [], 'texts': []}
                # create zip
                with zipfile.ZipFile(p, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                    # save base image
                    bio = io.BytesIO()
                    base.save(bio, format='PNG')
                    z.writestr('base.png', bio.getvalue())
                    # attachments
                    for i, a in enumerate(attachments):
                        aname = f'attachment_{i}.png'
                        abio = io.BytesIO()
                        # write original image when possible
                        try:
                            a.get('orig_img', a['img']).save(abio, format='PNG')
                        except Exception:
                            a['img'].save(abio, format='PNG')
                        z.writestr(aname, abio.getvalue())
                        manifest['attachments'].append({'name': aname, 'x': a['x'], 'y': a['y'], 'w': a['w'], 'h': a['h']})
                    # texts
                    for t in text_objects:
                        manifest['texts'].append({'text': t['text'], 'x': t['x'], 'y': t['y'], 'fill': t.get('fill', '#000000'), 'font_size': t.get('font_size', 20)})
                    z.writestr('manifest.json', json.dumps(manifest))
                messagebox.showinfo('Exported', f'Collaboration pack saved: {p}')
            except Exception as e:
                messagebox.showerror('Export Error', f'Failed to export collaboration pack: {e}')

        def import_collab():
            """Import a collaboration pack (zip) and restore whiteboard state."""
            p = filedialog.askopenfilename(title='Import Collaboration Pack', filetypes=[('Collaboration Pack', '*.zip')])
            if not p:
                return
            try:
                with zipfile.ZipFile(p, 'r') as z:
                    # manifest
                    if 'manifest.json' not in z.namelist():
                        messagebox.showerror('Import Error', 'Invalid collaboration pack (no manifest).')
                        return
                    manifest = json.loads(z.read('manifest.json').decode('utf-8'))
                    # load base
                    if 'base.png' in z.namelist():
                        base = Image.open(io.BytesIO(z.read('base.png'))).convert('RGBA')
                        nonlocal wb_img, wb_draw
                        wb_img = base.copy()
                        wb_draw = ImageDraw.Draw(wb_img)
                    # load attachments
                    attachments.clear()
                    for a in manifest.get('attachments', []):
                        name = a.get('name')
                        if name and name in z.namelist():
                            img = Image.open(io.BytesIO(z.read(name))).convert('RGBA')
                            attachments.append({'img': img, 'orig_img': img.copy(), 'x': a.get('x', 0), 'y': a.get('y', 0), 'w': a.get('w', img.width), 'h': a.get('h', img.height)})
                    # load texts
                    text_objects.clear()
                    for t in manifest.get('texts', []):
                        text_objects.append({'text': t.get('text', ''), 'x': t.get('x', 0), 'y': t.get('y', 0), 'fill': t.get('fill', '#000000'), 'font_size': t.get('font_size', 20)})
                    push_history()
                    update_preview()
                messagebox.showinfo('Imported', 'Collaboration pack loaded.')
            except Exception as e:
                messagebox.showerror('Import Error', f'Failed to import collaboration pack: {e}')

        def publish_to_community():
            """Save a collaboration pack to ./community and open the folder for the user to share.

            This prompts the user for optional metadata (title, author, description),
            generates a thumbnail, includes metadata in the manifest, and creates a
            human-readable timestamped filename.
            """
            try:
                # Ask user for optional metadata (keep it simple)
                title = simpledialog.askstring('Publish', 'Title (optional):')
                author = simpledialog.askstring('Publish', 'Author (optional):')
                description = simpledialog.askstring('Publish', 'Description (optional):')

                os.makedirs('community', exist_ok=True)

                # readable timestamp
                ts = datetime.datetime.now()
                ts_str = ts.strftime('%Y%m%d_%H%M%S')

                # sanitize title for filename
                safe_title = None
                if title:
                    safe_title = ''.join(c if (c.isalnum() or c in (' ', '-', '_')) else '_' for c in title).strip().replace(' ', '_')
                    if len(safe_title) > 40:
                        safe_title = safe_title[:40]

                if safe_title:
                    fname = Path(f'community/whiteboard_{safe_title}_{ts_str}.zip')
                else:
                    fname = Path(f'community/whiteboard_pack_{ts_str}.zip')

                # Compose final image and create a thumbnail
                full_img = compose_full_image()
                thumb = full_img.copy()
                # create a reasonable thumbnail (max 512x512, preserve aspect)
                thumb.thumbnail((512, 512))

                # Build manifest with metadata
                manifest = {
                    'title': title or '',
                    'author': author or '',
                    'description': description or '',
                    'timestamp': ts.isoformat(),
                    'attachments': [],
                    'texts': []
                }

                # write zip
                with zipfile.ZipFile(fname, 'w', compression=zipfile.ZIP_DEFLATED) as z:
                    # base image
                    base = full_img.convert('RGBA')
                    bio = io.BytesIO()
                    base.save(bio, format='PNG')
                    z.writestr('base.png', bio.getvalue())

                    # thumbnail
                    tbio = io.BytesIO()
                    try:
                        thumb.save(tbio, format='PNG')
                        z.writestr('thumbnail.png', tbio.getvalue())
                        manifest['thumbnail'] = 'thumbnail.png'
                    except Exception:
                        # ignore thumbnail generation issues
                        manifest['thumbnail'] = ''

                    # attachments
                    for i, a in enumerate(attachments):
                        aname = f'attachment_{i}.png'
                        abio = io.BytesIO()
                        try:
                            a.get('orig_img', a['img']).save(abio, format='PNG')
                        except Exception:
                            try:
                                a['img'].save(abio, format='PNG')
                            except Exception:
                                abio = None
                        if abio is not None:
                            z.writestr(aname, abio.getvalue())
                            manifest['attachments'].append({'name': aname, 'x': a.get('x', 0), 'y': a.get('y', 0), 'w': a.get('w', a.get('img').width if a.get('img') is not None else 0), 'h': a.get('h', a.get('img').height if a.get('img') is not None else 0)})

                    # texts
                    for t in text_objects:
                        manifest['texts'].append({'text': t.get('text', ''), 'x': t.get('x', 0), 'y': t.get('y', 0), 'fill': t.get('fill', '#000000'), 'font_size': t.get('font_size', 20)})

                    # write manifest
                    z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))

                # open community folder for user convenience
                try:
                    folder = str(Path('community').resolve())
                    if sys.platform == 'darwin':
                        subprocess.Popen(['open', folder])
                    elif sys.platform == 'win32':
                        subprocess.Popen(['explorer', folder])
                    else:
                        subprocess.Popen(['xdg-open', folder])
                except Exception:
                    pass

                messagebox.showinfo('Published', f'Whiteboard pack saved to: {fname}')
            except Exception as e:
                messagebox.showerror('Publish Error', f'Failed to publish: {e}')

        # Toolbar controls
        # --- Collaboration (LAN) client state and helpers ---
        collab_sio = None
        collab_thread = None
        collab_connected = False
        collab_status_var = tk.StringVar(value='Collab: Disconnected')

        def emit_collab_operation(op_type, payload):
            nonlocal collab_sio, collab_connected
            try:
                if collab_sio and collab_connected:
                    collab_sio.emit('operation', {'type': op_type, 'payload': payload})
            except Exception:
                pass

        def connect_collab():
            """Prompt for server URL and start a Socket.IO client in background."""
            nonlocal collab_sio, collab_thread, collab_connected, collab_server_url
            server = simpledialog.askstring('Connect', 'Collab server URL (e.g. http://127.0.0.1:5001):', initialvalue='http://127.0.0.1:5001')
            if not server:
                return
            try:
                import socketio as _sio
            except Exception:
                messagebox.showerror('Dependency Error', 'python-socketio is required. Install with: pip install python-socketio[client]')
                return

            sio = _sio.Client()
            # remember the server base URL for uploads
            try:
                collab_server_url = server
            except Exception:
                pass

            @sio.event
            def connect():
                nonlocal collab_connected
                collab_connected = True
                try:
                    wb.after(0, lambda: collab_status_var.set('Collab: Connected'))
                    wb.after(0, lambda: messagebox.showinfo('Collab', f'Connected to: {server}'))
                except Exception:
                    pass

            @sio.event
            def disconnect():
                nonlocal collab_connected
                collab_connected = False
                try:
                    wb.after(0, lambda: collab_status_var.set('Collab: Disconnected'))
                    wb.after(0, lambda: messagebox.showinfo('Collab', 'Disconnected from server'))
                except Exception:
                    pass

            @sio.on('init_state')
            def on_init_state(state):
                # apply canonical state (strokes, attachments, texts)
                def _apply():
                    try:
                        for s in state.get('strokes', []):
                            pts = s.get('points', [])
                            if pts:
                                try:
                                    wb_draw.line([tuple(p) for p in pts], fill=s.get('color', '#000000'), width=int(s.get('width', 4)))
                                except Exception:
                                    pass
                        # attachments: if remote URL provided, fetch it from server and attach
                        for a in state.get('attachments', []):
                            try:
                                if isinstance(a, dict) and a.get('url'):
                                    # construct full url
                                    url = a.get('url')
                                    if url.startswith('/'):
                                        base = server.rstrip('/')
                                        url = base + url
                                    import requests
                                    r = requests.get(url, timeout=8)
                                    if r.status_code == 200:
                                        from io import BytesIO
                                        img = Image.open(BytesIO(r.content)).convert('RGBA')
                                        aw, ah = img.size
                                        attachments.append({'img': img, 'orig_img': img.copy(), 'x': a.get('x', 50), 'y': a.get('y', 50), 'w': a.get('w', aw), 'h': a.get('h', ah)})
                                        print('Fetched attachment from server (init_state):', url)
                                        continue
                                # fallback: append raw metadata (may be reconstructed later)
                                attachments.append(a)
                            except Exception:
                                attachments.append(a)
                        for t in state.get('texts', []):
                            text_objects.append(t)
                        push_history()
                        update_preview()
                    except Exception:
                        pass
                wb.after(0, _apply)

            @sio.on('operation')
            def on_operation(data):
                def _apply():
                    try:
                        t = data.get('type')
                        p = data.get('payload', {})
                        if t == 'stroke':
                            pts = p.get('points', [])
                            if pts:
                                try:
                                    wb_draw.line([tuple(x) for x in pts], fill=p.get('color', '#000000'), width=int(p.get('width', 4)))
                                except Exception:
                                    pass
                        elif t == 'attach':
                            # if operation provides a URL, fetch and append image
                            try:
                                if isinstance(p, dict) and p.get('url'):
                                    url = p.get('url')
                                    if url.startswith('/'):
                                        base = server.rstrip('/')
                                        url = base + url
                                    import requests
                                    from io import BytesIO
                                    r = requests.get(url, timeout=8)
                                    if r.status_code == 200:
                                        img = Image.open(BytesIO(r.content)).convert('RGBA')
                                        aw, ah = img.size
                                        attachments.append({'id': p.get('id'), 'img': img, 'orig_img': img.copy(), 'x': p.get('x', 50), 'y': p.get('y', 50), 'w': p.get('w', aw), 'h': p.get('h', ah)})
                                        print('Fetched attachment from server (operation):', url)
                                        # done
                                        pass
                                    else:
                                        attachments.append(p)
                                else:
                                    attachments.append(p)
                            except Exception:
                                attachments.append(p)
                        elif t == 'text':
                            text_objects.append(p)
                        push_history()
                        update_preview()
                    except Exception:
                        pass
                wb.after(0, _apply)

            def _run():
                try:
                    sio.connect(server)
                    sio.wait()
                except Exception as e:
                    try:
                        wb.after(0, lambda: collab_status_var.set('Collab: Connection failed'))
                        wb.after(0, lambda: messagebox.showerror('Collab Error', f'Connection failed: {e}'))
                    except Exception:
                        pass

            collab_sio = sio
            collab_thread = threading.Thread(target=_run, daemon=True)
            collab_thread.start()

        # Collab Connect button
        ttk.Button(toolbar, text='Collab Connect', command=connect_collab).pack(side='left', padx=6)
        ttk.Label(toolbar, textvariable=collab_status_var).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Color', command=choose_color).pack(side='left', padx=4)
        ttk.Label(toolbar, text='Pen:').pack(side='left')
        ttk.Scale(toolbar, from_=1, to=40, variable=pen_width, orient='horizontal').pack(side='left', padx=6)
        ttk.Separator(toolbar, orient='vertical').pack(side='left', padx=6, fill='y')

        # Mode selector
        modes = ['Pen', 'Eraser', 'Line', 'Rect', 'Ellipse', 'Text', 'Eyedropper', 'Move']
        ttk.Label(toolbar, text='Mode:').pack(side='left')
        mode_combo = ttk.Combobox(toolbar, values=modes, textvariable=mode_var, state='readonly', width=10)
        mode_combo.pack(side='left', padx=4)
        ttk.Button(toolbar, text='Attach', command=attach_file).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Undo', command=undo).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Redo', command=redo).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Clear', command=lambda: clear_board()).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Save', command=lambda: save_board()).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Insert to Editor', command=lambda: insert_to_editor()).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Export...', command=lambda: save_board()).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Export Pack', command=export_collab).pack(side='left', padx=6)
        ttk.Button(toolbar, text='Import Pack', command=import_collab).pack(side='left', padx=6)
        # ttk.Button(toolbar, text='Publish', command=publish_to_community).pack(side='left', padx=6)

        canvas_frame = ttk.Frame(wb)
        canvas_frame.pack(fill='both', expand=True, padx=8, pady=6)

        wb_canvas = tk.Canvas(canvas_frame, width=CANVAS_W, height=CANVAS_H, bg='white', bd=2, relief='sunken')
        wb_canvas.pack(fill='both', expand=True)

        def clear_board():
            wb_canvas.delete('all')
            nonlocal wb_img, wb_draw, wb_history, history_index, attachments, text_objects
            wb_img = Image.new('RGBA', (CANVAS_W, CANVAS_H), (255, 255, 255, 0))
            wb_draw = ImageDraw.Draw(wb_img)
            attachments = []
            text_objects = []
            wb_history = [{'img': wb_img.copy(), 'attachments': [], 'texts': []}]
            history_index = 0
            update_preview()

        def save_board():
            p = filedialog.asksaveasfilename(defaultextension='.png', filetypes=[('PNG Image', '*.png')])
            if not p:
                return
            try:
                # Ensure RGB if user wants JPEG; default is PNG
                ext = Path(p).suffix.lower()
                out = compose_full_image()
                if ext in ('.jpg', '.jpeg'):
                    out = out.convert('RGB')
                out.save(p)
                messagebox.showinfo('Saved', f'Saved whiteboard to: {p}')
            except Exception as e:
                messagebox.showerror('Save Error', f'Failed to save whiteboard: {e}')

        def compose_full_image(src=None):
            """Return a new PIL RGBA image that composites wb_img + attachments + texts."""
            _src = src if src is not None else wb_img
            out = _src.copy().convert('RGBA')
            # draw attachments
            for a in attachments:
                try:
                    out.paste(a['img'], (int(a['x']), int(a['y'])), a['img'])
                except Exception:
                    try:
                        out.paste(a['img'], (int(a['x']), int(a['y'])))
                    except Exception:
                        pass
            # draw texts
            draw_tmp = ImageDraw.Draw(out)
            for t in text_objects:
                try:
                    fsize = int(t.get('font_size', 20))
                    try:
                        font = ImageFont.truetype('DejaVuSans.ttf', fsize)
                    except Exception:
                        try:
                            font = ImageFont.load_default()
                        except Exception:
                            font = None
                    if font is not None:
                        draw_tmp.text((t['x'], t['y']), t['text'], fill=t.get('fill', '#000000'), font=font)
                    else:
                        draw_tmp.text((t['x'], t['y']), t['text'], fill=t.get('fill', '#000000'))
                except Exception:
                    pass
            return out

        def update_preview(img=None):
            """Update the canvas display from the backing PIL image (or provided image)."""
            nonlocal wb_canvas
            _src = img if img is not None else wb_img
            try:
                disp = compose_full_image(_src)
                # Convert to a PhotoImage and display at top-left
                tkimg = ImageTk.PhotoImage(disp)
                wb_canvas.delete('all')
                wb_canvas.create_image(0, 0, image=tkimg, anchor='nw', tags=('wb_image',))
                wb_canvas.image = tkimg
                # draw selection overlay (rectangle + handles) on top using canvas primitives
                try:
                    wb_canvas.delete('wb_sel')
                except Exception:
                    pass
                sel = drawing.get('selected') if isinstance(drawing, dict) else None
                resize_sel = drawing.get('resize') if isinstance(drawing, dict) else None
                handle_size = 6
                target = sel or (resize_sel and (resize_sel[0], resize_sel[1]))
                if target:
                    typ, idx = target
                    if typ == 'attach' and 0 <= idx < len(attachments):
                        a = attachments[idx]
                        x0, y0 = int(a['x']), int(a['y'])
                        x1, y1 = int(a['x'] + a['w']), int(a['y'] + a['h'])
                    elif typ == 'text' and 0 <= idx < len(text_objects):
                        t = text_objects[idx]
                        try:
                            fsize = int(t.get('font_size', 20))
                            try:
                                font = ImageFont.truetype('DejaVuSans.ttf', fsize)
                            except Exception:
                                font = ImageFont.load_default()
                            bbox = ImageDraw.Draw(wb_img).textbbox((t['x'], t['y']), t['text'], font=font)
                            x0, y0, x1, y1 = bbox
                        except Exception:
                            x0, y0 = int(t['x']) - 4, int(t['y']) - 4
                            x1, y1 = int(t['x']) + 4, int(t['y']) + 4
                    else:
                        x0 = y0 = x1 = y1 = None

                    if x0 is not None:
                        # selection rectangle
                        wb_canvas.create_rectangle(x0, y0, x1, y1, outline='#2b8cff', width=2, tags=('wb_sel',))
                        # handles
                        for hx, hy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                            wb_canvas.create_rectangle(hx-handle_size, hy-handle_size, hx+handle_size, hy+handle_size, fill='white', outline='#2b8cff', tags=('wb_sel',))
            except Exception:
                pass

        def insert_to_editor():
            # Insert the whiteboard drawing into the main editor.
            try:
                # If no image in editor, use drawing as the new image (convert to RGB)
                if self.img is None:
                    self.push_history()
                    self.img = wb_img.convert('RGB')
                    self.original_img = self.img.copy()
                    self.img_history = [self.img.copy()]
                    self.update_canvas()
                    self.status_label.config(text='Whiteboard inserted as new image.', foreground=self.success_color)
                    wb.destroy()
                    return

                # Otherwise, composite the drawing over the current image, centered
                base = self.img.copy().convert('RGBA')
                # Compose full whiteboard (wb_img + attachments + texts)
                full = compose_full_image()
                # Resize drawing to fit base if sizes differ
                if full.size != base.size:
                    overlay = full.resize(base.size, Image.Resampling.LANCZOS)
                else:
                    overlay = full

                composed = Image.alpha_composite(base, overlay)
                self.push_history()
                self.img = composed.convert('RGB')
                self.update_canvas()
                self.status_label.config(text='Whiteboard inserted into current image.', foreground=self.success_color)
                wb.destroy()
            except Exception as e:
                messagebox.showerror('Insert Error', f'Failed to insert whiteboard: {e}')

        # Drawing handlers
        def on_down(ev):
            drawing['start'] = (ev.x, ev.y)
            drawing['last'] = (ev.x, ev.y)
            drawing['active'] = True
            m = mode_var.get()
            if m == 'Eyedropper':
                # sample color from image
                try:
                    px = wb_img.getpixel((int(ev.x), int(ev.y)))
                    if isinstance(px, tuple):
                        # convert to hex
                        r, g, b = px[:3]
                        draw_color.set('#%02x%02x%02x' % (r, g, b))
                except Exception:
                    pass
                drawing['active'] = False
            elif m == 'Text':
                # prompt for text and draw at location
                txt = simpledialog.askstring('Text', 'Enter text:')
                if txt:
                    try:
                        # create a movable text object instead of drawing directly
                        # default font size
                        text_objects.append({'text': txt, 'x': ev.x, 'y': ev.y, 'fill': draw_color.get(), 'font': None, 'font_size': 20})
                        push_history()
                        update_preview()
                    except Exception as e:
                        messagebox.showerror('Text Error', str(e))
                drawing['active'] = False
            elif m == 'Move':
                # select topmost attachment or text under cursor
                sel = None
                # attachments: check from topmost (last) to bottom
                for i in range(len(attachments)-1, -1, -1):
                    a = attachments[i]
                    if ev.x >= a['x'] and ev.x <= a['x'] + a['w'] and ev.y >= a['y'] and ev.y <= a['y'] + a['h']:
                        sel = ('attach', i)
                        break
                if sel is None:
                    # check text objects using the same font metrics used for rendering
                    for i in range(len(text_objects)-1, -1, -1):
                        t = text_objects[i]
                        try:
                            fsize = int(t.get('font_size', 20))
                            try:
                                font = ImageFont.truetype('DejaVuSans.ttf', fsize)
                            except Exception:
                                font = ImageFont.load_default()
                            bbox = ImageDraw.Draw(wb_img).textbbox((t['x'], t['y']), t['text'], font=font)
                            x0, y0, x1, y1 = bbox
                            if ev.x >= x0 and ev.x <= x1 and ev.y >= y0 and ev.y <= y1:
                                sel = ('text', i)
                                break
                        except Exception:
                            # fallback: simple point check near text origin
                            if abs(ev.x - t['x']) < 10 and abs(ev.y - t['y']) < 10:
                                sel = ('text', i)
                                break
                if sel:
                    # determine if click landed on a resize handle (corners)
                    handle_hit = None
                    handle_size = 8
                    if sel[0] == 'attach':
                        obj = attachments[sel[1]]
                        cx, cy = obj['x'], obj['y']
                        w, h = obj['w'], obj['h']
                        corners = {'nw': (cx, cy), 'ne': (cx + w, cy), 'sw': (cx, cy + h), 'se': (cx + w, cy + h)}
                        for name, (hx, hy) in corners.items():
                            if abs(ev.x - hx) <= handle_size and abs(ev.y - hy) <= handle_size:
                                handle_hit = ('attach', sel[1], name)
                                break
                    else:
                        obj = text_objects[sel[1]]
                        # approximate bbox for text selection
                        try:
                            bbox = ImageDraw.Draw(wb_img).textbbox((obj['x'], obj['y']), obj['text'])
                            x0, y0, x1, y1 = bbox
                            corners = {'nw': (x0, y0), 'ne': (x1, y0), 'sw': (x0, y1), 'se': (x1, y1)}
                            for name, (hx, hy) in corners.items():
                                if abs(ev.x - hx) <= handle_size and abs(ev.y - hy) <= handle_size:
                                    handle_hit = ('text', sel[1], name)
                                    break
                        except Exception:
                            # fallback: small area around origin
                            if abs(ev.x - obj['x']) <= handle_size and abs(ev.y - obj['y']) <= handle_size:
                                handle_hit = ('text', sel[1], 'se')
                    if handle_hit:
                        drawing['resize'] = handle_hit
                        drawing['active'] = True
                        # store start offsets for resize
                        drawing['resize_start'] = (ev.x, ev.y)
                        drawing['resize_orig'] = obj.copy() if isinstance(obj, dict) else None
                    else:
                        drawing['selected'] = sel
                        if sel[0] == 'attach':
                            obj = attachments[sel[1]]
                            drawing['offset'] = (ev.x - obj['x'], ev.y - obj['y'])
                        else:
                            obj = text_objects[sel[1]]
                            drawing['offset'] = (ev.x - obj['x'], ev.y - obj['y'])
                        drawing['active'] = True

                # start collecting stroke points for Pen/Eraser
                if m in ('Pen', 'Eraser'):
                    drawing['stroke_pts'] = [(ev.x, ev.y)]

        def on_move(ev):
            if not drawing['active']:
                return
            m = mode_var.get()
            x, y = ev.x, ev.y
            sx, sy = drawing['start']
            lx, ly = drawing['last']
            w = pen_width.get()
            c = draw_color.get()

            if m in ('Pen', 'Eraser'):
                # immediate drawing
                color = c
                if m == 'Eraser':
                    # simple eraser: draw transparent if possible, otherwise white
                    try:
                        color = (255, 255, 255, 0)
                    except Exception:
                        color = '#ffffff'
                try:
                    wb_draw.line([lx, ly, x, y], fill=color, width=w)
                except Exception:
                    wb_draw.line([lx, ly, x, y], fill=c, width=w)
                drawing['last'] = (x, y)
                # append to stroke points for collaborative sync
                try:
                    if 'stroke_pts' in drawing:
                        drawing['stroke_pts'].append((x, y))
                    else:
                        drawing['stroke_pts'] = [(lx, ly), (x, y)]
                except Exception:
                    pass
                update_preview()
            else:
                # If moving a selected object (translation)
                if m == 'Move' and drawing.get('selected') is not None and drawing.get('resize') is None:
                    sel = drawing['selected']
                    offx, offy = drawing.get('offset', (0, 0))
                    if sel[0] == 'attach':
                        a = attachments[sel[1]]
                        a['x'] = int(x - offx)
                        a['y'] = int(y - offy)
                    else:
                        t = text_objects[sel[1]]
                        t['x'] = int(x - offx)
                        t['y'] = int(y - offy)
                    update_preview()
                    drawing['last'] = (x, y)
                    return
                # If resizing an object
                if m == 'Move' and drawing.get('resize') is not None:
                    typ, idx, handle_name = drawing['resize']
                    if typ == 'attach':
                        a = attachments[idx]
                        orig = a.get('orig_img', a['img'])
                        ox, oy = drawing.get('resize_start', (0, 0))
                        # compute new bbox dependent on handle
                        if handle_name == 'se':
                            new_w = max(8, x - a['x'])
                            new_h = max(8, y - a['y'])
                            a['w'], a['h'] = int(new_w), int(new_h)
                        elif handle_name == 'ne':
                            new_w = max(8, x - a['x'])
                            new_h = max(8, a['y'] + a['h'] - y)
                            a['y'] = int(y)
                            a['w'], a['h'] = int(new_w), int(new_h)
                        elif handle_name == 'sw':
                            new_w = max(8, a['x'] + a['w'] - x)
                            new_h = max(8, y - a['y'])
                            a['x'] = int(x)
                            a['w'], a['h'] = int(new_w), int(new_h)
                        elif handle_name == 'nw':
                            new_w = max(8, a['x'] + a['w'] - x)
                            new_h = max(8, a['y'] + a['h'] - y)
                            a['x'], a['y'] = int(x), int(y)
                            a['w'], a['h'] = int(new_w), int(new_h)
                        # resize image from original for quality
                        try:
                            a['img'] = a.get('orig_img', a['img']).resize((max(1, a['w']), max(1, a['h'])), Image.Resampling.LANCZOS)
                        except Exception:
                            try:
                                a['img'] = a.get('orig_img', a['img']).resize((max(1, a['w']), max(1, a['h'])))
                            except Exception:
                                pass
                    else:
                        t = text_objects[idx]
                        # use vertical drag to change font size
                        start_x, start_y = drawing.get('resize_start', (0, 0))
                        delta = y - start_y
                        new_size = max(6, int(t.get('font_size', 20) + delta // 6))
                        t['font_size'] = new_size
                    update_preview()
                    drawing['last'] = (x, y)
                    return
                # shape preview: draw on a temporary copy
                tmp = wb_img.copy()
                draw_tmp = ImageDraw.Draw(tmp)
                # normalize coordinates so PIL doesn't raise when x1<x0 or y1<y0
                x0, x1 = (sx, x) if sx <= x else (x, sx)
                y0, y1 = (sy, y) if sy <= y else (y, sy)
                if m == 'Line':
                    draw_tmp.line([sx, sy, x, y], fill=c, width=w)
                elif m == 'Rect':
                    draw_tmp.rectangle([x0, y0, x1, y1], outline=c, width=w)
                elif m == 'Ellipse':
                    draw_tmp.ellipse([x0, y0, x1, y1], outline=c, width=w)
                update_preview(tmp)

        def on_up(ev):
            m = mode_var.get()
            drawing['active'] = False
            sx, sy = drawing['start']
            x, y = ev.x, ev.y
            w = pen_width.get()
            c = draw_color.get()
            if m in ('Pen', 'Eraser'):
                # finish stroke
                push_history()
                # emit stroke to collaborators if connected
                try:
                    pts = drawing.pop('stroke_pts', None)
                    if pts:
                        payload = {'points': pts, 'color': c, 'width': w, 'mode': m, 'id': str(uuid.uuid4())}
                        emit_collab_operation('stroke', payload)
                except Exception:
                    pass
            elif m == 'Line':
                wb_draw.line([sx, sy, x, y], fill=c, width=w)
                push_history()
                update_preview()
            elif m == 'Rect':
                # normalize coordinates before drawing final shape
                x0, x1 = (sx, x) if sx <= x else (x, sx)
                y0, y1 = (sy, y) if sy <= y else (y, sy)
                wb_draw.rectangle([x0, y0, x1, y1], outline=c, width=w)
                push_history()
                update_preview()
            elif m == 'Ellipse':
                x0, x1 = (sx, x) if sx <= x else (x, sx)
                y0, y1 = (sy, y) if sy <= y else (y, sy)
                wb_draw.ellipse([x0, y0, x1, y1], outline=c, width=w)
                push_history()
                update_preview()
            elif m == 'Move':
                # finalize moving selection
                if drawing.get('selected') is not None or drawing.get('resize') is not None:
                    push_history()
                drawing['selected'] = None
                drawing['offset'] = (0, 0)
                drawing['resize'] = None
                drawing.pop('resize_start', None)
                drawing.pop('resize_orig', None)
            drawing['last'] = (None, None)

        wb_canvas.bind('<ButtonPress-1>', on_down)
        wb_canvas.bind('<B1-Motion>', on_move)
        wb_canvas.bind('<ButtonRelease-1>', on_up)
        def on_double_click(ev):
            # Edit text object if double-clicked
            for i in range(len(text_objects)-1, -1, -1):
                t = text_objects[i]
                try:
                    fsize = int(t.get('font_size', 20))
                    try:
                        font = ImageFont.truetype('DejaVuSans.ttf', fsize)
                    except Exception:
                        font = ImageFont.load_default()
                    bbox = ImageDraw.Draw(wb_img).textbbox((t['x'], t['y']), t['text'], font=font)
                    x0, y0, x1, y1 = bbox
                    if ev.x >= x0 and ev.x <= x1 and ev.y >= y0 and ev.y <= y1:
                        newtxt = simpledialog.askstring('Edit Text', 'Edit text:', initialvalue=t['text'])
                        if newtxt is not None:
                            t['text'] = newtxt
                            push_history()
                            update_preview()
                        return
                except Exception:
                    if abs(ev.x - t['x']) < 10 and abs(ev.y - t['y']) < 10:
                        newtxt = simpledialog.askstring('Edit Text', 'Edit text:', initialvalue=t['text'])
                        if newtxt is not None:
                            t['text'] = newtxt
                            push_history()
                            update_preview()
                        return

        wb_canvas.bind('<Double-1>', on_double_click)

        # Keep references so GC doesn't remove objects
        wb._wb_img = wb_img
        wb._wb_draw = wb_draw
        wb._wb_canvas = wb_canvas
        wb._pen_width = pen_width
        wb._draw_color = draw_color


    def _create_control_panel(self, parent):
        """Creates the professional-looking control panel on the left."""
        control_frame = ttk.Frame(parent, width=280)
        control_frame.pack(side='left', fill='y')
        control_frame.pack_propagate(False)

        # Scrollable area setup
        y_scrollbar = ttk.Scrollbar(control_frame, orient=tk.VERTICAL)
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        canvas_left = tk.Canvas(control_frame, bg=self.panel_bg, bd=0, highlightthickness=0, yscrollcommand=y_scrollbar.set)
        canvas_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scrollbar.config(command=canvas_left.yview)

        inner_frame = ttk.Frame(canvas_left, padding="15 10") # Increased padding
        canvas_left.create_window((0, 0), window=inner_frame, anchor="nw")

        # Update scroll region when inner_frame content changes size
        inner_frame.bind("<Configure>", lambda e: canvas_left.configure(scrollregion = canvas_left.bbox("all")))
        
        # --- Section Helpers ---
        def create_section(title):
            # Use accent_primary for bold headings
            ttk.Label(inner_frame, text=title, font=(self.font_main, 12, 'bold'), 
                      foreground=self.accent_primary, background=self.panel_bg).pack(fill='x', pady=(15, 5))
            ttk.Separator(inner_frame, orient='horizontal').pack(fill='x', pady=5)

        def create_tool_button(text, command):
            # Use Secondary.TButton for all small tool buttons
            ttk.Button(inner_frame, text=text, command=command, style="Secondary.TButton").pack(fill='x', pady=3, ipady=3)
            
        def create_slider_control(title, var, from_, to, default, command_type):
            """
            Creates a slider control with a label, the slider, and commit/reset buttons.
            `command_type` is the type of enhancement ('brightness', 'contrast', 'blur').
            """
            # Label with textvariable to show current value
            value_label = ttk.Label(inner_frame, text=f"{title}: {default:.1f}", 
                                    textvariable=var, compound='right')
            value_label.pack(fill='x', pady=(5, 0))
            
            # Use a callback to format the value display
            def update_label(v):
                value = float(v)
                var.set(value)
                # Apply preview on every motion
                self.apply_enhancement_preview(command_type, value)
                
            slider = ttk.Scale(inner_frame, 
                               from_=from_, 
                               to=to, 
                               variable=var, 
                               command=update_label, # Use the formatted callback for instant preview
                               orient=tk.HORIZONTAL)
            slider.set(default)
            slider.pack(fill='x', pady=0)
            
            # Control Buttons
            btn_frame = ttk.Frame(inner_frame)
            btn_frame.pack(fill='x', pady=(5, 10))
            
            # Apply button uses Primary.TButton
            ttk.Button(btn_frame, text=f"Apply {title}", 
                       command=lambda: self.commit_enhancement(title.lower(), var, default, title), 
                       style="Primary.TButton").pack(side='left', fill='x', expand=True, padx=(0, 2))
            
            # Reset button uses Secondary.TButton
            ttk.Button(btn_frame, text="Reset", 
                       command=lambda: self.reset_adjustment_preview(var, default), 
                       style="Secondary.TButton").pack(side='left', fill='x', expand=True, padx=(2, 0))

        # --- 1. Core Tools ---
        create_section("CORE TOOLS")
        create_tool_button("Apply Crop (Drag Area)", lambda: self.set_tool_mode('crop'))
        create_tool_button("Toggle Resize Mode (Handles)", lambda: self.set_tool_mode('resize'))
        create_tool_button("Reset to Original Image", self.reset_image)
        
        # --- 2. Interactive Adjustments (NEW INTERACTIVITY) ---
        create_section("INTERACTIVE ADJUSTMENTS")
        
        # Brightness (Range 0.1 to 3.0, default 1.0)
        create_slider_control("Brightness", self.brightness_var, 0.1, 3.0, 1.0, 'brightness')
        
        # Contrast (Range 0.1 to 3.0, default 1.0)
        create_slider_control("Contrast", self.contrast_var, 0.1, 3.0, 1.0, 'contrast')

        # Blur (Radius 0 to 10.0, default 0.0)
        create_slider_control("Blur Radius", self.blur_var, 0.0, 10.0, 0.0, 'blur')


        # --- 3. Color/Mode Adjustments ---
        create_section("COLOR / MODE")
        create_tool_button("Convert to Grayscale", self.convert_grayscale)
        create_tool_button("Convert to HSV", self.convert_hsv)
        create_tool_button("Convert to Binary (Threshold)", self.convert_binary)
        create_tool_button("Invert Colors", self.invert_image)

        # --- 4. Geometric Transforms ---
        create_section("GEOMETRIC TRANSFORMS")
        create_tool_button("Rotate 90° Clockwise", self.rotate_image)
        create_tool_button("Advanced Options", self.open_advanced_options)
        
        flip_frame = ttk.Frame(inner_frame)
        flip_frame.pack(fill='x', pady=3)
        ttk.Label(flip_frame, text="Flip Direction:").pack(side='left', padx=(0, 5))
        flip_combo = ttk.Combobox(flip_frame, textvariable=self.flip_var, values=["Horizontal", "Vertical"], state="readonly")
        flip_combo.pack(side='left', expand=True, fill='x')
        ttk.Button(inner_frame, text="Apply Flip", command=self.flip_image, style="Secondary.TButton").pack(fill='x', pady=3, ipady=3)

        # --- 5. Analysis ---
        create_section("ANALYSIS & VISUALIZATION")
        create_tool_button("View Histogram (R/G/B)", self.view_histogram)
        create_tool_button("Run Local CV Analysis", self.analyze_image_with_open_source_model)
        create_tool_button("Advanced Image Enhancer", self.ai_image_enhancer_advanced)
        create_tool_button("AI Image Enhancer", self.ai_image_enhancer)
        

    def _create_canvas(self, parent):
        """Creates the central area for image display and binding events."""
        self.canvas = tk.Canvas(parent, bg=self.dark_bg, highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True, padx=5, pady=5)
        
        # Initial instructional text
        self.canvas.create_text(
            self.winfo_width() / 2, self.winfo_height() / 2, 
             
            fill=self.fg_color, font=(self.font_main, 14), tags="placeholder_text"
        )
        
        # Bind resize event to update canvas layout
        self.canvas.bind('<Configure>', self.on_canvas_resize)
        
        # Bind unified mouse handlers
        self.canvas.bind("<ButtonPress-1>", self.handle_press)
        self.canvas.bind("<B1-Motion>", self.handle_drag)
        self.canvas.bind("<ButtonRelease-1>", self.handle_release)

    # --- Tool Mode Switcher ---

    def set_tool_mode(self, mode):
        """Toggles between cropping and resizing modes."""
        if self.img is None:
            messagebox.showwarning("Warning", "Load an image first.")
            return

        self.cropping = False
        self.resizing = False
        self.canvas.delete("crop_rect") # Clear crop selection
        self.canvas.delete("resize_handles") # Clear resize handles
        
        # Clear any active enhancement preview
        self.current_temp_img = None
        self.update_canvas() # Redraw to show committed state

        if mode == 'crop':
            self.cropping = True
            # Use accent_primary for active tool status
            self.status_label.config(text="Mode: Cropping. Click and drag to select area.", foreground=self.accent_primary)
            self.canvas.config(cursor="crosshair")
        elif mode == 'resize':
            self.resizing = True # True indicates the handles are visible and clickable
            self.draw_resize_handles()
            self.status_label.config(text="Mode: Resize. Drag handles to change size.", foreground=self.accent_primary)
            self.canvas.config(cursor="")
            
    
    # --- History Management ---

    def push_history(self):
        """Saves the current image state to the history stack."""
        if self.img:
            self.img_history.append(self.img.copy())
            # Keep history size reasonable (e.g., last 10 steps)
            if len(self.img_history) > 10:
                self.img_history.pop(0)

    def undo_last_action(self):
        """Reverts the image to the previous state in history."""
        if len(self.img_history) > 1:
            self.img_history.pop() # Remove current state (the one we are currently on)
            self.img = self.img_history[-1].copy() # Revert to the last saved state
            self.update_canvas()
            # Distinct color for feedback/warning (Carrot Orange)
            self.status_label.config(text="Undo successful. Reverted to previous state.", foreground='#F39C12')
        elif self.original_img:
            # If only the original image is left in history, revert to it.
            self.img = self.original_img.copy()
            self.img_history = [self.img.copy()]
            self.update_canvas()
            messagebox.showinfo("Info", "Reverted to the original image. Cannot undo further.")
        else:
            messagebox.showwarning("Warning", "No image actions to undo.")
            self.status_label.config(text="Ready.", foreground=self.fg_color)
            

    # --- Image Loading and UI Redraw ---

    def upload_image(self):
        """Opens dialog, loads image, and initializes history."""
        # Prefer the built-in Tkinter file dialog (safer while the Tk mainloop is running).
        # Only use the PySide6 picker as a fallback when Tk's dialog didn't return a path.
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif")])
        if not file_path:
            try:
                file_path = pick_file_with_pyside()
            except Exception:
                file_path = None

        if file_path:
            try:
                # Open image and ensure it's in RGB mode for consistent manipulation
                new_img = Image.open(file_path).convert("RGB")
                self.original_img = new_img.copy()
                self.img = new_img.copy()
                # Remember the file path so we can pass it to auxiliary tools
                self.current_image_path = file_path
                self.img_history = [self.img.copy()] # Initialize history with the original image
                self.update_canvas()
                # Distinct color for success (Emerald Green)
                self.status_label.config(text=f"Image loaded: {os.path.basename(file_path)}", foreground='#2ECC71')
                # Add opened image to recent list for quick access
                try:
                    self._add_to_recent(file_path)
                except Exception:
                    pass
                self.canvas.delete("placeholder_text")
                # Ensure tools are disabled visually
                self.cropping = False
                self.resizing = False
                self.canvas.delete("crop_rect") 
                self.canvas.delete("resize_handles")
                self.canvas.config(cursor="")
                
                # Reset all enhancement variables
                self.brightness_var.set(1.0)
                self.contrast_var.set(1.0)
                self.blur_var.set(0.0)
                self.current_temp_img = None
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load image: {e}")
                self.status_label.config(text="Ready.", foreground=self.fg_color)
                
    def reset_image(self):
        """Resets the image to the original loaded state."""
        if self.original_img:
            self.img = self.original_img.copy()
            self.img_history = [self.img.copy()] # Reset history
            self.update_canvas()
            # Distinct color for feedback/warning (Carrot Orange)
            self.status_label.config(text="Image reset to original.", foreground='#F39C12')
            # Reset visual state
            self.cropping = False
            self.resizing = False
            self.canvas.delete("crop_rect") 
            self.canvas.delete("resize_handles")
            self.canvas.config(cursor="")
            
            # Reset all enhancement variables
            self.brightness_var.set(1.0)
            self.contrast_var.set(1.0)
            self.blur_var.set(0.0)
            self.current_temp_img = None
        else:
            messagebox.showwarning("Warning", "No original image saved to reset to.")
            self.status_label.config(text="Ready.", foreground=self.fg_color)
            
    def update_canvas(self):
        """Handles image resizing, display, and redrawing of UI elements (handles/crop) based on self.img."""
        if not self.img:
            return

        # Ensure no temporary image is active
        self.current_temp_img = None
        
        canvas_width = self.canvas.winfo_width() - 40 
        canvas_height = self.canvas.winfo_height() - 40 
        
        if canvas_width <= 0 or canvas_height <= 0: return

        img_width, img_height = self.img.size
        
        # Calculate scaling ratio to fit image inside canvas bounds
        ratio_w = canvas_width / img_width
        ratio_h = canvas_height / img_height
        ratio = min(ratio_w, ratio_h)
        
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        if new_width > 0 and new_height > 0:
            # Prepare image for display (ensure RGB mode)
            display_img = self.img.convert('RGB').resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            self.tk_img = ImageTk.PhotoImage(display_img)
            
            self.canvas.delete("all")
            
            center_x = self.canvas.winfo_width() / 2
            center_y = self.canvas.winfo_height() / 2
            
            self.canvas.create_image(center_x, center_y, image=self.tk_img, anchor='center', tags="current_image")
            self.canvas.image = self.tk_img # Keep a reference

            # Store image display bounds
            self.img_display_box = (
                center_x - new_width // 2,
                center_y - new_height // 2,
                center_x + new_width // 2,
                center_y + new_height // 2
            )
            
            # If in resize mode, redraw handles
            if self.resizing == True: # Check specifically for True (handles visible) not 'active' (drag in progress)
                 self.draw_resize_handles()
        
    def on_canvas_resize(self, event):
        """Called when the main canvas is resized."""
        # This will redraw either self.img or self.current_temp_img if it exists
        if self.current_temp_img:
            # If a preview is active, redraw the preview image
            self.update_canvas_preview(self.current_temp_img)
        else:
            # Otherwise, redraw the committed image
            self.update_canvas()

    # --- Cropping Functions ---

    def start_crop(self, event):
        """Initializes cropping rectangle."""
        if self.img and self.cropping:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            
            if not self.img_display_box: return False

            # Check if click is within the displayed image bounds
            x_min, y_min, x_max, y_max = self.img_display_box
            if x_min <= canvas_x <= x_max and y_min <= canvas_y <= y_max:
                self.start_x, self.start_y = canvas_x, canvas_y
                self.canvas.delete("crop_rect")
                self.crop_rectangle = self.canvas.create_rectangle(
                    self.start_x, self.start_y, self.start_x, self.start_y, 
                    outline='#E74C3C', width=2, dash=(5, 2), tags="crop_rect" # Keep red for crop selection
                )
                return True
        return False

    def draw_crop(self, event):
        """Updates the cropping rectangle during drag."""
        if self.cropping and self.crop_rectangle and self.img_display_box:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            
            # Clamp x and y to image bounds
            img_start_x, img_start_y, img_end_x, img_end_y = self.img_display_box
            current_x = max(img_start_x, min(canvas_x, img_end_x))
            current_y = max(img_start_y, min(canvas_y, img_end_y))
            
            self.canvas.coords(self.crop_rectangle, self.start_x, self.start_y, current_x, current_y)

    def apply_crop(self, event):
        """Applies the crop based on the final rectangle coordinates."""
        if self.cropping and self.crop_rectangle and self.img:
            self.cropping = False
            self.canvas.config(cursor="")
            
            x1, y1, x2, y2 = self.canvas.coords(self.crop_rectangle)
            
            if not self.img_display_box: return

            img_start_x, img_start_y, _, _ = self.img_display_box
            disp_w = self.tk_img.width()
            disp_h = self.tk_img.height()
            
            scale_x = self.img.size[0] / disp_w
            scale_y = self.img.size[1] / disp_h
            
            # Map canvas crop box to original image coordinates
            original_x1 = int((min(x1, x2) - img_start_x) * scale_x)
            original_y1 = int((min(y1, y2) - img_start_y) * scale_y)
            original_x2 = int((max(x1, x2) - img_start_x) * scale_x)
            original_y2 = int((max(y1, y2) - img_start_y) * scale_y)

            if original_x2 > original_x1 and original_y2 > original_y1:
                self.push_history()
                self.img = self.img.crop((original_x1, original_y1, original_x2, original_y2))
                self.update_canvas()
                self.status_label.config(text="Image successfully cropped.", foreground='#2ECC71')
            else:
                messagebox.showwarning("Crop Error", "Invalid crop area selected.")
            
            self.canvas.delete("crop_rect")
            self.crop_rectangle = None

    # --- Drag-Resize Functions (Simplified for class scope) ---
    
    def _get_cursor(self, mode):
        """Maps the resize mode (e.g., 'se') to a Tkinter cursor name."""
        cursor_map = {
            'nw': 'top_left_corner', 'n': 'top_side', 'ne': 'top_right_corner',
            'w': 'left_side', 'e': 'right_side',
            'sw': 'bottom_left_corner', 's': 'bottom_side', 'se': 'bottom_right_corner',
        }
        return cursor_map.get(mode, "")

    def draw_resize_handles(self):
        """Draws 8 small interactive handles around the displayed image."""
        if not self.img_display_box or not self.img: return
            
        x1, y1, x2, y2 = self.img_display_box
        s = self.resize_handle_size // 2

        handle_positions = {
            'nw': (x1 - s, y1 - s), 'n': ((x1 + x2) / 2 - s, y1 - s), 'ne': (x2 - s, y1 - s),
            'w': (x1 - s, (y1 + y2) / 2 - s),                          'e': (x2 - s, (y1 + y2) / 2 - s),
            'sw': (x1 - s, y2 - s), 's': ((x1 + x2) / 2 - s, y2 - s), 'se': (x2 - s, y2 - s),
        }

        self.canvas.delete("resize_handles")
        self.resize_handles = {}
        
        for mode, (hx, hy) in handle_positions.items():
            handle_id = self.canvas.create_oval(
                hx, hy, hx + self.resize_handle_size, hy + self.resize_handle_size,
                fill=self.accent_primary, outline='white', width=1, tags=("resize_handles", mode)
            )
            self.resize_handles[mode] = handle_id
            
            # Bind events for cursor change
            self.canvas.tag_bind(handle_id, "<Enter>", lambda e, m=mode: self.canvas.config(cursor=self._get_cursor(m)))
            self.canvas.tag_bind(handle_id, "<Leave>", lambda e: self.canvas.config(cursor=""))

    def get_handle_at_event(self, event):
        """Checks if the mouse event is over a resize handle."""
        if self.resizing != True: return None # Only check if handles are displayed
        ids = self.canvas.find_overlapping(event.x, event.y, event.x, event.y)
        for id in ids:
            tags = self.canvas.gettags(id)
            if "resize_handles" in tags:
                return tags[1]
        return None

    def start_drag_resize(self, event):
        """Initializes the resize state if a handle is clicked."""
        self.resize_mode = self.get_handle_at_event(event)

        if self.resize_mode and self.img_display_box and self.img:
            # We set 'resizing' to 'active' to indicate drag is in progress
            self.resizing = 'active' 
            
            tk_img_ref = self.canvas.image
            self.original_img_size_on_canvas = (tk_img_ref.width(), tk_img_ref.height())
            self.original_canvas_mouse_pos = (event.x, event.y)
            
            self.canvas.delete("resize_handles") # Hide handles during drag
            # Use accent_primary for the active outline
            self.canvas.itemconfig("current_image", outline=self.accent_primary, width=2, dash=(5, 2)) 
            
            return True 
        return False 

    def drag_resize(self, event):
        """Calculates the new size and updates the canvas image during a drag."""
        if self.resizing != 'active' or not self.img_display_box: return
        
        initial_w, initial_h = self.original_img_size_on_canvas
        dx = event.x - self.original_canvas_mouse_pos[0]
        dy = event.y - self.original_canvas_mouse_pos[1]
        
        new_w = initial_w
        new_h = initial_h
        
        # Calculate new width/height based on drag direction
        if 'e' in self.resize_mode: new_w += dx
        if 'w' in self.resize_mode: new_w -= dx
        if 's' in self.resize_mode: new_h += dy
        if 'n' in self.resize_mode: new_h -= dy
            
        new_w = max(10, int(new_w))
        new_h = max(10, int(new_h))

        # Scale back to original image size
        ratio_x = self.img.size[0] / initial_w
        ratio_y = self.img.size[1] / initial_h

        target_img_w = int(new_w * ratio_x)
        target_img_h = int(new_h * ratio_y)
        
        # Create and display temporary image
        try:
            # Resize the actual PIL image (in memory)
            # Use NEAREST for speed during interactive drag
            self.current_temp_img = self.img.resize((target_img_w, target_img_h), Image.Resampling.NEAREST)
            # Resize the display version for the canvas
            temp_disp_img = self.current_temp_img.resize((new_w, new_h), Image.Resampling.NEAREST).convert('RGB')

            self.tk_img_temp = ImageTk.PhotoImage(temp_disp_img)
            
            image_id = self.canvas.find_withtag("current_image")
            if image_id:
                # Update image content and size visually
                self.canvas.coords(image_id[0], self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)
                self.canvas.itemconfig(image_id[0], image=self.tk_img_temp)
                self.canvas.image = self.tk_img_temp # Important: update reference
                
        except Exception as e:
            print(f"Error during drag resize: {e}")

    def end_drag_resize(self, event):
        """Applies the final resize, pushes to history, and cleans up state."""
        if self.resizing == 'active':
            self.resizing = True # Back to handle-visible mode
            self.canvas.itemconfig("current_image", outline="", dash="")
            
            if self.current_temp_img:
                self.push_history()
                self.img = self.current_temp_img.copy()
                self.current_temp_img = None
                self.update_canvas() # Redraw the canvas, which includes the handles
                self.status_label.config(text="Image successfully resized.", foreground='#2ECC71')
            
            return True 
        return False 
    
    # --- Enhancement/Preview Functions (Placeholder - Implement these in full app) ---
    def apply_enhancement_preview(self, command_type, value):
        """
        Applies a non-committing enhancement (brightness, contrast, blur) 
        to the image for real-time preview.
        """
        if not self.img: return
        
        base_img = self.img
        
        # Only apply a single adjustment at a time for simplicity in this example
        if command_type == 'brightness':
            enhancer = ImageEnhance.Brightness(base_img)
            temp_img = enhancer.enhance(value)
        elif command_type == 'contrast':
            enhancer = ImageEnhance.Contrast(base_img)
            temp_img = enhancer.enhance(value)
        elif command_type == 'blur':
            if value > 0:
                temp_img = base_img.filter(ImageFilter.GaussianBlur(radius=value))
            else:
                temp_img = base_img

        self.current_temp_img = temp_img
        self.update_canvas_preview(temp_img)

    def update_canvas_preview(self, temp_img):
        """Redraws the canvas using a temporary image."""
        if not temp_img: return

        canvas_width = self.canvas.winfo_width() - 40 
        canvas_height = self.canvas.winfo_height() - 40 
        
        if canvas_width <= 0 or canvas_height <= 0: return

        img_width, img_height = temp_img.size
        
        ratio_w = canvas_width / img_width
        ratio_h = canvas_height / img_height
        ratio = min(ratio_w, ratio_h)
        
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        if new_width > 0 and new_height > 0:
            display_img = temp_img.convert('RGB').resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            self.tk_img_temp = ImageTk.PhotoImage(display_img)
            
            # Find the existing image and update it, or create a new one
            image_id = self.canvas.find_withtag("current_image")
            center_x = self.canvas.winfo_width() / 2
            center_y = self.canvas.winfo_height() / 2
            
            if image_id:
                self.canvas.itemconfig(image_id[0], image=self.tk_img_temp)
                self.canvas.coords(image_id[0], center_x, center_y)
            else:
                self.canvas.create_image(center_x, center_y, image=self.tk_img_temp, anchor='center', tags="current_image")
            
            self.canvas.image = self.tk_img_temp
            # No need to update self.img_display_box as it is not used for sizing temp image
            
    def commit_enhancement(self, command_type, var, default_value, title):
        """Commits the current previewed enhancement to the main image history."""
        if self.current_temp_img:
            self.push_history()
            self.img = self.current_temp_img.copy()
            self.current_temp_img = None
            self.update_canvas() # Redraw committed state
            self.status_label.config(text=f"{title} applied and committed.", foreground='#2ECC71')
        else:
            self.status_label.config(text=f"No {title} changes to commit. Value is {var.get():.1f}.", foreground=self.fg_color)

    def reset_adjustment_preview(self, var, default_value):
        """Resets the slider variable and reverts the display image."""
        if self.img:
            var.set(default_value)
            self.current_temp_img = None
            self.update_canvas()
            self.status_label.config(text="Adjustment preview reset.", foreground='#F39C12')

    # --- Other Operations (Stubs for PIL) ---
    def convert_grayscale(self):
        if not self.img: return
        self.push_history()
        self.img = self.img.convert('L').convert('RGB')
        self.update_canvas()
        self.status_label.config(text="Converted to Grayscale.", foreground='#2ECC71')

    def convert_hsv(self):
        if not self.img: return
        self.push_history()
        # Convert to HSV, then back to RGB for display compatibility
        self.img = self.img.convert('HSV').convert('RGB') 
        self.update_canvas()
        self.status_label.config(text="Converted to HSV (displaying RGB interpretation).", foreground='#2ECC71')

    def convert_binary(self):
        if not self.img: return
        self.push_history()
        # Convert to grayscale, then threshold (e.g., 128)
        gray_img = self.img.convert('L')
        # Simple binary conversion: 0 if < 128, 255 if >= 128
        self.img = gray_img.point(lambda x: 255 if x > 128 else 0, '1').convert('RGB')
        self.update_canvas()
        self.status_label.config(text="Converted to Binary (Threshold 128).", foreground='#2ECC71')
        
    def invert_image(self):
        if not self.img: return
        self.push_history()
        self.img = ImageOps.invert(self.img)
        self.update_canvas()
        self.status_label.config(text="Colors inverted.", foreground='#2ECC71')

    def rotate_image(self):
        if not self.img: return
        self.push_history()
        self.img = self.img.rotate(-90, expand=True) # Rotate 90 degrees clockwise
        self.update_canvas()
        self.status_label.config(text="Rotated 90° Clockwise.", foreground='#2ECC71')

    def flip_image(self):
        if not self.img: return
        direction = self.flip_var.get()
        self.push_history()
        if direction == "Horizontal":
            self.img = self.img.transpose(Image.FLIP_LEFT_RIGHT)
        elif direction == "Vertical":
            self.img = self.img.transpose(Image.FLIP_TOP_BOTTOM)
        self.update_canvas()
        self.status_label.config(text=f"Flipped {direction}ly.", foreground='#2ECC71')
        
    def view_image_properties(self):
        if not self.img:
            messagebox.showwarning("Warning", "Load an image first.")
            return

        w, h = self.img.size
        mode = self.img.mode
        info = (
            f"Image Size: {w}x{h} pixels\n"
            f"Color Mode: {mode}\n"
            f"Format: {self.img.format if self.img.format else 'N/A'}"
        )
        messagebox.showinfo("Image Properties", info)

    def view_histogram(self):
        if not self.img:
            messagebox.showwarning("Warning", "Load an image first.")
            return
        
        # Calculate histograms for R, G, B channels
        r, g, b = self.img.split()
        
        # Matplotlib Figure setup
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor(self.panel_bg)
        ax.set_facecolor(self.dark_bg)
        ax.tick_params(colors=self.fg_color)
        ax.xaxis.label.set_color(self.fg_color)
        ax.yaxis.label.set_color(self.fg_color)
        ax.title.set_color(self.fg_color)

        ax.hist(np.array(r).flatten(), bins=256, color='red', alpha=0.6, label='Red')
        ax.hist(np.array(g).flatten(), bins=256, color='green', alpha=0.6, label='Green')
        ax.hist(np.array(b).flatten(), bins=256, color='blue', alpha=0.6, label='Blue')
        ax.set_title('RGB Histogram')
        ax.set_xlabel('Pixel Value')
        ax.set_ylabel('Frequency')
        ax.legend(facecolor=self.panel_bg, edgecolor=self.separator_color, labelcolor=self.fg_color)
        
        # Create a new Tkinter Toplevel window for the plot
        plot_window = tk.Toplevel(self)
        plot_window.title("Image Histogram")
        plot_window.configure(bg=self.dark_bg)
        
        # Embed Matplotlib figure into Tkinter window
        canvas_plot = FigureCanvasTkAgg(fig, master=plot_window)
        canvas_widget = canvas_plot.get_tk_widget()
        canvas_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas_plot.draw()
        
        self.status_label.config(text="Displaying image histogram.", foreground=self.accent_primary)

    def analyze_image_with_open_source_model(self):
        """
        Perform a local, open-source analysis on the currently loaded image.

        Metrics produced:
        - Average RGB color
        - Dominant colors (k-means, top 3)
        - Edge count and edge density (Canny)
        - Sharpness estimate (Laplacian variance)
        - Approximate object/contour count (contours from edges)

        This runs entirely locally using Pillow / NumPy / OpenCV (if available).
        Results are shown in a scrollable Toplevel window.
        """
        if not self.img:
            messagebox.showwarning("Warning", "Please load an image first before running local analysis.")
            return

        # Small status update and UI refresh
        self.status_label.config(text="Performing local Computer Vision analysis...", foreground=self.accent_primary)
        try:
            self.update_idletasks()

            # Convert to RGB numpy array
            np_img = np.array(self.img.convert('RGB'))
            h, w = np_img.shape[:2]

            # Downsample large images for speed (keep aspect ratio)
            max_dim = 800
            scale = 1.0
            if max(h, w) > max_dim:
                scale = max_dim / float(max(h, w))
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))
                try:
                    # Prefer OpenCV resize if available for speed/quality
                    if cv2 is not None:
                        small = cv2.resize(np_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    else:
                        small = np.array(self.img.resize((new_w, new_h), Image.Resampling.LANCZOS).convert('RGB'))
                except Exception:
                    small = np.array(self.img.resize((new_w, new_h), Image.Resampling.LANCZOS).convert('RGB'))
            else:
                small = np_img.copy()

            total_pixels = small.shape[0] * small.shape[1]

            # 1) Average color
            avg_color = np.mean(small.reshape(-1, 3), axis=0).astype(int)

            # 2) Convert to grayscale for structure analysis
            try:
                if cv2 is not None:
                    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
                else:
                    gray = (0.2989 * small[..., 0] + 0.5870 * small[..., 1] + 0.1140 * small[..., 2]).astype('uint8')
            except Exception:
                gray = (0.2989 * small[..., 0] + 0.5870 * small[..., 1] + 0.1140 * small[..., 2]).astype('uint8')

            # 3) Sharpness (Laplacian variance) and edges (Canny)
            try:
                if cv2 is not None:
                    lap = cv2.Laplacian(gray, cv2.CV_64F)
                    sharpness = float(lap.var())
                    # Use auto thresholds based on median
                    med = np.median(gray)
                    lower = int(max(0, 0.66 * med))
                    upper = int(min(255, 1.33 * med))
                    edges = cv2.Canny(gray, lower, upper)
                    edge_count = int((edges > 0).sum())
                    # find contours for an approximate object count
                    contours_info = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    contours = contours_info[0] if len(contours_info) == 2 else contours_info[1]
                    object_count = sum(1 for c in contours if cv2.contourArea(c) > 100)  # ignore tiny contours
                else:
                    # Fallback simple gradient magnitude
                    gx = np.gradient(gray.astype(float), axis=1)
                    gy = np.gradient(gray.astype(float), axis=0)
                    grad = np.hypot(gx, gy)
                    sharpness = float(np.var(grad))
                    edge_count = int((grad > 50).sum())
                    object_count = 0
            except Exception:
                # Fallback values
                sharpness = 0.0
                edge_count = 0
                object_count = 0

            edge_density = (edge_count / float(total_pixels)) * 100.0 if total_pixels > 0 else 0.0

            # 4) Dominant colors - kmeans (cv2.kmeans if available, otherwise simple histogram fallback)
            dominant_colors = []
            try:
                Z = small.reshape((-1, 3)).astype(np.float32)
                K = 3
                if cv2 is not None:
                    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
                    _, labels, centers = cv2.kmeans(Z, K, None, criteria, 10, cv2.KMEANS_PP_CENTERS)
                    centers = centers.astype(int)
                    counts = np.bincount(labels.flatten(), minlength=K)
                    # Sort by count
                    order = np.argsort(-counts)
                    for i in order:
                        c = centers[i]
                        dominant_colors.append((int(c[0]), int(c[1]), int(c[2]), int(counts[i])))
                else:
                    # simple fallback: use average as single dominant
                    dominant_colors.append((int(avg_color[0]), int(avg_color[1]), int(avg_color[2]), total_pixels))
            except Exception:
                dominant_colors.append((int(avg_color[0]), int(avg_color[1]), int(avg_color[2]), total_pixels))

            # Build human-friendly report
            report_lines = []
            report_lines.append("--- Local Open-Source CV Analysis Report ---\n")
            report_lines.append(f"Image (analyzed at): {small.shape[1]} x {small.shape[0]} pixels (downsampled from {w} x {h})")
            report_lines.append("")
            report_lines.append("1) Average Color (RGB):")
            report_lines.append(f"   R: {avg_color[0]}, G: {avg_color[1]}, B: {avg_color[2]}")
            report_lines.append("")
            report_lines.append("2) Dominant Colors (top entries - RGB + pixel count):")
            for idx, (r, g, b, cnt) in enumerate(dominant_colors[:3], start=1):
                percent = (cnt / float(total_pixels)) * 100.0 if total_pixels > 0 else 0.0
                report_lines.append(f"   {idx}. RGB({r}, {g}, {b}) — {cnt} px ({percent:.2f}%)")
            report_lines.append("")
            report_lines.append("3) Structural / Edge Analysis:")
            report_lines.append(f"   Edge pixels detected: {edge_count}")
            report_lines.append(f"   Edge density: {edge_density:.3f}%")
            report_lines.append("")
            report_lines.append("4) Sharpness (Laplacian variance):")
            report_lines.append(f"   Sharpness score: {sharpness:.2f}  (higher = sharper)")
            report_lines.append("")
            report_lines.append("5) Object / Contour Estimate:")
            report_lines.append(f"   Approx. number of contours (area > 100 px): {object_count}")
            report_lines.append("")

            # Interpretation heuristics
            report_lines.append("Interpretation:")
            if edge_density > 10.0:
                report_lines.append("  - High edge density: image likely contains fine detail, textures, or many small features.")
            elif edge_density > 2.0:
                report_lines.append("  - Moderate edge density: balanced detail and smooth regions.")
            else:
                report_lines.append("  - Low edge density: large uniform areas or blurred content.")

            if sharpness < 50:
                report_lines.append("  - Low sharpness: image may be out of focus or heavily blurred.")
            elif sharpness < 300:
                report_lines.append("  - Moderate sharpness.")
            else:
                report_lines.append("  - High sharpness: image contains many high-frequency details.")

            final_report = "\n".join(report_lines)

            # Show results in a scrollable window
            self._display_analysis_result(final_report, title="Local CV Analysis Report")
            # Update status
            self.status_label.config(text="Local CV Analysis completed.", foreground=self.success_color)

        except Exception as e:
            # Ensure status is reset and an error is visible
            self.status_label.config(text="Ready.", foreground=self.fg_color)
            messagebox.showerror("Analysis Error", f"An error occurred during local image analysis:\n{e}")

    def ai_image_enhancer(self):
        """Automatically enhance the currently loaded image using a small local pipeline.

        Uses OpenCV when available for denoising and CLAHE; otherwise uses Pillow's UnsharpMask
        and small contrast/color/brightness boosts. Runs in a background thread to avoid
        blocking the UI and pushes to history on success.
        """
        if not self.img:
            messagebox.showwarning("Warning", "Load an image first before running AI Image Enhancer.")
            return

        # Ask user to continue (optional) — run immediately
        proceed = messagebox.askyesno("AI Enhancer", "Run automatic enhancement on the current image? This will create a new history entry.")
        if not proceed:
            return

        # Background worker
        def _worker(img_copy):
            try:
                # Convert to NumPy RGB array
                arr = np.array(img_copy.convert('RGB'))

                # 1) Denoise (OpenCV preferred)
                if cv2 is not None:
                    try:
                        denoised = cv2.fastNlMeansDenoisingColored(arr, None, 10, 10, 7, 21)
                    except Exception:
                        denoised = arr

                    # 2) CLAHE on L channel
                    try:
                        lab = cv2.cvtColor(denoised, cv2.COLOR_RGB2LAB)
                        l, a, b = cv2.split(lab)
                        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
                        cl = clahe.apply(l)
                        limg = cv2.merge((cl, a, b))
                        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2RGB)
                    except Exception:
                        enhanced = denoised

                    # 3) Unsharp mask (manual)
                    try:
                        gaussian = cv2.GaussianBlur(enhanced, (0, 0), sigmaX=1.0)
                        unsharp = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
                    except Exception:
                        unsharp = enhanced

                    result_pil = Image.fromarray(np.clip(unsharp, 0, 255).astype('uint8'))
                else:
                    # Pillow fallback
                    try:
                        tmp = img_copy.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
                    except Exception:
                        tmp = img_copy.copy()

                    try:
                        # Slight boosts for contrast/color/brightness
                        tmp = ImageEnhance.Contrast(tmp).enhance(1.12)
                        tmp = ImageEnhance.Color(tmp).enhance(1.06)
                        tmp = ImageEnhance.Brightness(tmp).enhance(1.03)
                        tmp = ImageOps.autocontrast(tmp, cutoff=1)
                    except Exception:
                        pass
                    result_pil = tmp

                # Completed, schedule UI update
                def _finish():
                    try:
                        self.push_history()
                        self.img = result_pil.copy()
                        self.current_temp_img = None
                        self.update_canvas()
                        self.status_label.config(text="AI enhancement applied.", foreground=self.success_color)
                    except Exception as e:
                        messagebox.showerror("Enhancer Error", f"Failed to apply enhancement: {e}")
                        self.status_label.config(text="Ready.", foreground=self.fg_color)

                self.after(1, _finish)

            except Exception as e:
                self.after(1, lambda: (messagebox.showerror("Enhancer Error", f"Error during enhancement: {e}"), self.status_label.config(text="Ready.", foreground=self.fg_color)))

        # Start background thread
        self.status_label.config(text="Running AI Image Enhancer...", foreground=self.accent_primary)
        worker_thread = threading.Thread(target=_worker, args=(self.img.copy(),), daemon=True)
        worker_thread.start()

    def _enhancement_pipeline(self, pil_img, params: dict, cancel_event: 'threading.Event' = None):
        """Apply an enhancement pipeline to a PIL image according to params.

        params keys:
        - denoise: int (0-30)
        - clahe: float (1.0-5.0)
        - sharpen: float (0-2)
        - contrast: float
        - color: float
        - gamma: float

        cancel_event (optional): a threading.Event that, if set, should cause the pipeline to abort early.
        """
        img = pil_img.convert('RGB')
        arr = np.array(img)

        def _check_cancel():
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError('Enhancement cancelled')

        # OpenCV path (preferred for quality & speed)
        if cv2 is not None:
            try:
                denoise = int(params.get('denoise', 10))
                if denoise > 0:
                    _check_cancel()
                    arr = cv2.fastNlMeansDenoisingColored(arr, None, h=denoise, hColor=denoise, templateWindowSize=7, searchWindowSize=21)

                _check_cancel()
                # CLAHE
                clahe_clip = float(params.get('clahe', 2.0))
                lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=clahe_clip, tileGridSize=(8,8))
                cl = clahe.apply(l)
                lab = cv2.merge((cl, a, b))
                arr = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

                _check_cancel()
                # Unsharp (adaptive)
                sharpen = float(params.get('sharpen', 1.0))
                if sharpen > 0:
                    gaussian = cv2.GaussianBlur(arr, (0,0), sigmaX=1.0)
                    arr = cv2.addWeighted(arr, 1.0 + sharpen*0.5, gaussian, -0.5*sharpen, 0)

                _check_cancel()
                # Color/Contrast/Gamma adjustments using a lightweight approach (convert to LAB for contrast if needed)
                result = Image.fromarray(np.clip(arr,0,255).astype('uint8'))
                result = result.convert('RGB')
                _check_cancel()
                # Use Pillow for the final color/contrast/gamma steps for simplicity
                result = ImageEnhance.Contrast(result).enhance(float(params.get('contrast', 1.0)))
                _check_cancel()
                result = ImageEnhance.Color(result).enhance(float(params.get('color', 1.0)))
                _check_cancel()
                g = float(params.get('gamma', 1.0))
                if g != 1.0:
                    lut = [pow(x/255.0, 1.0/g)*255 for x in range(256)]
                    result = result.point(lut*3)

            except RuntimeError:
                # bubbled up cancellation
                raise
            except Exception:
                result = img
        else:
            # Pillow fallback
            result = img
            try:
                denoise = int(params.get('denoise', 0))
                if denoise > 0:
                    _check_cancel()
                    # Pillow has no built-in denoise; apply a mild filter sequence
                    result = result.filter(ImageFilter.MedianFilter(size=3))

                _check_cancel()
                clahe_clip = float(params.get('clahe', 1.0))
                # approximate by autocontrast for local contrast
                if clahe_clip > 1.0:
                    result = ImageOps.autocontrast(result, cutoff=0)

                _check_cancel()
                sharpen = float(params.get('sharpen', 1.0))
                if sharpen > 0:
                    result = result.filter(ImageFilter.UnsharpMask(radius=2, percent=int(100*sharpen), threshold=3))

                _check_cancel()
                # Color / Contrast / Gamma
                result = ImageEnhance.Contrast(result).enhance(float(params.get('contrast', 1.0)))
                _check_cancel()
                result = ImageEnhance.Color(result).enhance(float(params.get('color', 1.0)))
                _check_cancel()
                g = float(params.get('gamma', 1.0))
                if g != 1.0:
                    lut = [pow(x/255.0, 1.0/g)*255 for x in range(256)]
                    result = result.point(lut*3)
            except RuntimeError:
                raise
            except Exception:
                pass

        return result

    def ai_image_enhancer_advanced(self):
        """Open a dialog with parameters for the enhancement pipeline and allow preview/apply."""
        if not self.img:
            messagebox.showwarning("Warning", "Load an image first before opening the Advanced Enhancer.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("AI Enhancer — Advanced")
        dlg.geometry('520x520')
        dlg.transient(self)

        params = {
            'denoise': tk.IntVar(value=8),
            'clahe': tk.DoubleVar(value=2.0),
            'sharpen': tk.DoubleVar(value=1.0),
            'contrast': tk.DoubleVar(value=1.08),
            'color': tk.DoubleVar(value=1.05),
            'gamma': tk.DoubleVar(value=1.0),
        }

        # Presets
        presets = {
            'Auto': None,  # computed dynamically
            'Portrait': {'denoise': 6, 'clahe': 1.6, 'sharpen': 0.8, 'contrast': 1.05, 'color': 1.08, 'gamma': 1.0},
            'Landscape': {'denoise': 4, 'clahe': 2.4, 'sharpen': 1.0, 'contrast': 1.12, 'color': 1.04, 'gamma': 1.0},
            'Night': {'denoise': 14, 'clahe': 3.0, 'sharpen': 0.6, 'contrast': 1.15, 'color': 1.02, 'gamma': 1.15},
            'HDR-like': {'denoise': 5, 'clahe': 3.5, 'sharpen': 1.2, 'contrast': 1.2, 'color': 1.1, 'gamma': 1.0},
        }

        def compute_auto_params():
            """Estimate reasonable parameters from the current image content."""
            # downsample for speed
            try:
                np_img = np.array(self.img.convert('RGB'))
                h, w = np_img.shape[:2]
                max_dim = 600
                if max(h, w) > max_dim:
                    scale = max_dim / float(max(h, w))
                    new_w = max(1, int(w * scale))
                    new_h = max(1, int(h * scale))
                    small = np.array(self.img.resize((new_w, new_h), Image.Resampling.LANCZOS).convert('RGB'))
                else:
                    small = np_img

                # grayscale
                gray = (0.2989 * small[..., 0] + 0.5870 * small[..., 1] + 0.1140 * small[..., 2]).astype('uint8')

                # sharpness via laplacian variance if cv2 available
                if cv2 is not None:
                    lap = cv2.Laplacian(gray, cv2.CV_64F)
                    sharpness = float(lap.var())
                    med = np.median(gray)
                    lower = int(max(0, 0.66 * med))
                    upper = int(min(255, 1.33 * med))
                    edges = cv2.Canny(gray, lower, upper)
                    edge_count = int((edges > 0).sum())
                else:
                    gx = np.gradient(gray.astype(float), axis=1)
                    gy = np.gradient(gray.astype(float), axis=0)
                    grad = np.hypot(gx, gy)
                    sharpness = float(np.var(grad))
                    edge_count = int((grad > 50).sum())

                total = float(small.shape[0] * small.shape[1])
                edge_density = (edge_count / total) * 100.0 if total > 0 else 0.0

                # Heuristics: low sharpness -> stronger denoise; high edge density -> preserve detail (less denoise)
                if sharpness < 80:
                    denoise = 14
                    sharpen = 1.0
                elif sharpness < 300:
                    denoise = 8
                    sharpen = 1.0
                else:
                    denoise = 3
                    sharpen = 1.2

                # Night scenes: low median brightness
                median_brightness = float(np.median(small))
                if median_brightness < 60:
                    clahe = 3.0
                    contrast = 1.15
                    gamma = 1.15
                    denoise = max(denoise, 12)
                else:
                    clahe = 2.0
                    contrast = 1.08
                    gamma = 1.0

                color = 1.05

                return {'denoise': int(denoise), 'clahe': float(clahe), 'sharpen': float(sharpen),
                        'contrast': float(contrast), 'color': float(color), 'gamma': float(gamma)}
            except Exception:
                return presets['Landscape'].copy()

        def apply_preset(name):
            if name == 'Auto':
                p = compute_auto_params()
            else:
                p = presets.get(name, presets['Landscape']).copy()

            # Apply to vars
            try:
                self_binds = params
                params['denoise'].set(int(p.get('denoise', params['denoise'].get())))
                params['clahe'].set(float(p.get('clahe', params['clahe'].get())))
                params['sharpen'].set(float(p.get('sharpen', params['sharpen'].get())))
                params['contrast'].set(float(p.get('contrast', params['contrast'].get())))
                params['color'].set(float(p.get('color', params['color'].get())))
                params['gamma'].set(float(p.get('gamma', params['gamma'].get())))
            except Exception:
                pass

        # Layout: presets combobox + sliders in a scrollable frame
        top_frame = ttk.Frame(dlg)
        top_frame.pack(fill='x', padx=8, pady=8)

        ttk.Label(top_frame, text='Preset:').pack(side='left')
        preset_var = tk.StringVar(value='Auto')
        preset_combo = ttk.Combobox(top_frame, textvariable=preset_var, values=list(presets.keys()), state='readonly')
        preset_combo.pack(side='left', padx=6)
        ttk.Button(top_frame, text='Apply Preset', command=lambda: apply_preset(preset_var.get())).pack(side='left', padx=6)

        # Sliders area
        body = ttk.Frame(dlg)
        body.pack(fill='both', expand=True, padx=8, pady=6)

        def add_slider(label_text, var, frm, to, resolution=None):
            f = ttk.Frame(body)
            f.pack(fill='x', pady=4)
            ttk.Label(f, text=label_text).pack(anchor='w')
            s = ttk.Scale(f, from_=frm, to=to, variable=var, orient='horizontal')
            s.pack(fill='x')

        add_slider('Denoise Strength (0-30)', params['denoise'], 0, 30)
        add_slider('CLAHE Clip (1.0-5.0)', params['clahe'], 1.0, 5.0)
        add_slider('Sharpen Strength (0-2)', params['sharpen'], 0.0, 2.0)
        add_slider('Contrast (0.5-1.5)', params['contrast'], 0.5, 1.5)
        add_slider('Color Boost (0.5-1.5)', params['color'], 0.5, 1.5)
        add_slider('Gamma (0.5-2.0)', params['gamma'], 0.5, 2.0)

        btn_frame = ttk.Frame(dlg)
        btn_frame.pack(fill='x', pady=8)

        def _preview():
            p = {k: v.get() for k, v in params.items()}
            try:
                preview_img = self._enhancement_pipeline(self.img.copy(), p)
                self.update_canvas_preview(preview_img)
                self.status_label.config(text="Previewing enhancement...", foreground=self.accent_primary)
            except Exception as e:
                messagebox.showerror('Preview Error', f'Failed to generate preview: {e}')

        def _apply_with_progress():
            p = {k: v.get() for k, v in params.items()}

            # Progress dialog
            prog = tk.Toplevel(dlg)
            prog.title('Applying...')
            prog.geometry('360x120')
            prog.transient(dlg)
            ttk.Label(prog, text='Applying advanced enhancement — please wait').pack(pady=8)
            progress_label = ttk.Label(prog, text='Starting...')
            progress_label.pack(pady=4)
            cancel_event = threading.Event()

            def _cancel():
                cancel_event.set()
                progress_label.config(text='Cancelling...')

            ttk.Button(prog, text='Cancel', command=_cancel).pack(pady=6)

            def _bg():
                try:
                    # pass cancel_event into pipeline
                    out = self._enhancement_pipeline(self.img.copy(), p, cancel_event=cancel_event)
                    def _finish():
                        try:
                            self.push_history()
                            self.img = out.copy()
                            self.update_canvas()
                            self.status_label.config(text='Advanced enhancement applied.', foreground=self.success_color)
                        finally:
                            try:
                                prog.destroy()
                            except Exception:
                                pass
                            try:
                                dlg.destroy()
                            except Exception:
                                pass

                    self.after(1, _finish)
                except RuntimeError:
                    # cancellation
                    self.after(1, lambda: (progress_label.config(text='Cancelled.'), self.status_label.config(text='Enhancement cancelled.', foreground=self.fg_color), prog.destroy()))
                except Exception as e:
                    self.after(1, lambda: (messagebox.showerror('Error', f'Enhancement failed: {e}'), self.status_label.config(text='Ready.', foreground=self.fg_color), prog.destroy()))

            self.status_label.config(text='Applying advanced enhancement...', foreground=self.accent_primary)
            threading.Thread(target=_bg, daemon=True).start()

        ttk.Button(btn_frame, text='Preview', command=_preview).pack(side='left', padx=10)
        ttk.Button(btn_frame, text='Apply (with progress)', command=_apply_with_progress).pack(side='left', padx=10)
        ttk.Button(btn_frame, text='Cancel', command=lambda: (dlg.destroy(), self.update_canvas())).pack(side='right', padx=10)

        # Apply Auto preset initially for convenience
        try:
            apply_preset('Auto')
        except Exception:
            pass

    def _display_analysis_result(self, text, title="Analysis Result"):
        """Helper: show analysis text in a read-only scrollable Toplevel window."""
        try:
            result_window = tk.Toplevel(self)
            result_window.title(title)
            result_window.configure(bg=self.panel_bg)
            result_window.geometry("640x480")

            # Text area
            text_area = tk.Text(result_window, wrap=tk.WORD, font=(self.font_main, 10), padx=12, pady=12,
                                bg=self.panel_bg, fg=self.fg_color, bd=0)
            text_area.insert(tk.END, text)
            text_area.config(state=tk.DISABLED)

            # Scrollbar
            scrollbar = ttk.Scrollbar(result_window, command=text_area.yview)
            text_area.config(yscrollcommand=scrollbar.set)

            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        except Exception as e:
            messagebox.showerror("Display Error", f"Failed to display analysis result: {e}")


    # --- Unified Event Handlers ---

    def handle_press(self, event):
        """Handles the start of a drag, checking for resize handle first, then crop area."""
        # 1. Check for Resize Handle Click
        if self.get_handle_at_event(event):
            self.start_drag_resize(event)
            return
            
        # 2. Check for Crop Start (only if in crop mode)
        if self.cropping and self.start_crop(event):
            return

    def handle_drag(self, event):
        """Handles the drag motion for either resizing or cropping."""
        if self.resizing == 'active':
            self.drag_resize(event)
        elif self.cropping and self.crop_rectangle:
            self.draw_crop(event)

    def handle_release(self, event):
        """Handles the end of a drag, applying c        python /Users/malith_bandara/Desktop/DIP-test/main.pyrop or resize."""
        if self.resizing == 'active':
            self.end_drag_resize(event)
        elif self.cropping and self.crop_rectangle:
            self.apply_crop(event)
        
        # Reset mouse pointer if not in a tool mode
        if not self.cropping and self.resizing != True:
             self.canvas.config(cursor="")
             
# --- Main Execution ---

if __name__ == "__main__":
    try:
        app = PhotoEditorApp()
        app.mainloop()
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Please ensure you have all required dependencies installed: Pillow, numpy, and matplotlib.")