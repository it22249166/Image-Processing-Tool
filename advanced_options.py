import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageTk

# If an image path is passed as the first argument, use it as the selected image
SELECTED_IMAGE_PATH = None
if len(sys.argv) > 1:
    try:
        p = Path(sys.argv[1])
        if p.exists():
            SELECTED_IMAGE_PATH = p
    except Exception:
        SELECTED_IMAGE_PATH = None

# --- Script Execution Helper (No Change to Logic) ---

def _run_script(script_name, image_path=None):
    """
    Launches an external script (like tonal_trans.py) in a new process 
    using the current Python interpreter.
    Checks if the script file exists and provides an error if not found.
    """
    
    # Construct the full path relative to where advanced_options.py is located
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        messagebox.showerror('Error', 
                             f"Script not found!\n\n"
                             f"Attempted path: {script_path.resolve()}\n\n"
                             f"Please ensure '{script_name}' exists in the same directory.")
        return
        
    try:
        cmd = [sys.executable, str(script_path)]
        if image_path:
            cmd.append(str(image_path))
        subprocess.Popen(cmd)
    except Exception as e:
        messagebox.showerror('Error', f'Failed to launch {script_name}:\n{e}')


# --- Functions to open each option (No Change to Logic) ---

def open_tonal_transformations():
    """Opens the Tonal Transformations tool."""
    _run_script('tonal_trans.py', image_path=SELECTED_IMAGE_PATH)

def open_color_balancing():
    """Opens the Color Balancing tool."""
    _run_script('color_balancing.py', image_path=SELECTED_IMAGE_PATH)

def open_filters():
    """Opens the Filters tool."""
    _run_script('filters.py', image_path=SELECTED_IMAGE_PATH)

def open_image_segmentation():
    """Opens the Image Segmentation tool."""
    _run_script('Image_segmentation.py', image_path=SELECTED_IMAGE_PATH)


# --- UI Setup (Aesthetic Changes Applied) ---

# Initialize the main window
advanced_window = tk.Tk()
advanced_window.title("Advanced Image Manipulation Tools")
advanced_window.geometry("550x400") # Slightly larger for better spacing
advanced_window.resizable(False, False) # Prevent resizing for fixed layout control

# 1. Styling using a modern theme and custom colors
style = ttk.Style()
# Try to use 'clam' or 'alt' as they are more customizable than default
style.theme_use('clam') 

# Define button style
style.configure('Custom.TButton', 
                font=('Helvetica', 12, 'bold'), 
                padding=[15, 10], 
                foreground='#ffffff', 
                background="#201E3E", # A nice green color
                relief='flat',
                borderradius=8) # Rounded corners

style.map('Custom.TButton', 
          background=[('active', "#1c1427")]) # Darker green on hover

# Define main title style
style.configure('Title.TLabel', 
                font=('Helvetica', 20, 'bold'), 
                foreground='#333333')

# Define description label style
style.configure('Description.TLabel', 
                font=('Helvetica', 10, 'italic'), 
                foreground="#666666")

# Set background color for the main window
advanced_window.configure(bg='#f0f2f5') 

# 2. Advanced options content (Title)
title_label = ttk.Label(advanced_window, 
                        text="Advanced Image Manipulation Suite", 
                        style='Title.TLabel',
                        background='#f0f2f5')
title_label.pack(pady=(30, 5))

# Description
desc_label = ttk.Label(advanced_window, 
                       text="Click any option below to launch the dedicated manipulation tool.", 
                       style='Description.TLabel',
                       background='#f0f2f5')
desc_label.pack(pady=(0, 20))

# If an image was provided on the command line, show a preview and filename
preview_frame = ttk.Frame(advanced_window, padding=(10, 5), style='')
preview_frame.pack(padx=20, pady=(0, 10), fill='x')

if SELECTED_IMAGE_PATH is not None:
    try:
        with Image.open(SELECTED_IMAGE_PATH) as _img:
            thumb = _img.copy()
            thumb.thumbnail((160, 160), Image.Resampling.LANCZOS)
            tk_thumb = ImageTk.PhotoImage(thumb)
            thumb_label = ttk.Label(preview_frame, image=tk_thumb)
            thumb_label.image = tk_thumb
            thumb_label.pack(side='left', padx=(0, 10))

        info_label = ttk.Label(preview_frame, text=f"Using image: {SELECTED_IMAGE_PATH.name}", style='Description.TLabel')
        info_label.pack(side='left', padx=5)
    except Exception as e:
        warn_label = ttk.Label(preview_frame, text=f"Failed to load preview: {e}", style='Description.TLabel')
        warn_label.pack(side='left')
else:
    # Keep the preview frame small when no image is provided
    preview_frame.pack_forget()

# 3. Scrollable container for buttons (so all options are visible on small screens)
container_outer = ttk.Frame(advanced_window)
container_outer.pack(padx=20, pady=(0,10), fill='both', expand=True)

# Create a canvas + scrollbar to host a vertically scrollable inner frame
btn_canvas = tk.Canvas(container_outer, borderwidth=0, highlightthickness=0, bg='#e9e7e2')
v_scroll = ttk.Scrollbar(container_outer, orient='vertical', command=btn_canvas.yview)
btn_canvas.configure(yscrollcommand=v_scroll.set)

v_scroll.pack(side='right', fill='y')
btn_canvas.pack(side='left', fill='both', expand=True)

inner_frame = ttk.Frame(btn_canvas, padding="10 10 10 10", style='')
btn_canvas.create_window((0, 0), window=inner_frame, anchor='nw')

def _on_inner_config(event):
    # Update scroll region to fit inner content
    btn_canvas.configure(scrollregion=btn_canvas.bbox('all'))

inner_frame.bind('<Configure>', _on_inner_config)

# Allow mousewheel scrolling on the canvas
def _on_mousewheel(event):
    btn_canvas.yview_scroll(int(-1*(event.delta/120)), 'units')

btn_canvas.bind_all('<MouseWheel>', _on_mousewheel)

# 4. Buttons (using the new style) placed inside inner_frame
tonal_btn = ttk.Button(inner_frame, 
                       text="Tonal Transformations", 
                       command=open_tonal_transformations, 
                       style='Custom.TButton')
tonal_btn.pack(pady=10, fill='x')

color_balancing_btn = ttk.Button(inner_frame, 
                                 text="Color Balancing", 
                                 command=open_color_balancing, 
                                 style='Custom.TButton')
color_balancing_btn.pack(pady=10, fill='x')

filters_btn = ttk.Button(inner_frame, 
                         text="Filters", 
                         command=open_filters, 
                         style='Custom.TButton')
filters_btn.pack(pady=10, fill='x')

image_segmentation_btn = ttk.Button(inner_frame, 
                                    text="Image Segmentation", 
                                    command=open_image_segmentation, 
                                    style='Custom.TButton')
image_segmentation_btn.pack(pady=10, fill='x')

# Add spacer to ensure last button isn't hidden under scrollbar
ttk.Label(inner_frame, text='').pack(pady=6)

# 5. Center the window on the screen
advanced_window.update_idletasks() # Ensure dimensions are calculated
width = advanced_window.winfo_width()
height = advanced_window.winfo_height()
screen_width = advanced_window.winfo_screenwidth()
screen_height = advanced_window.winfo_screenheight()
x = (screen_width // 2) - (width // 2)
y = (screen_height // 2) - (height // 2)
advanced_window.geometry(f'{width}x{height}+{x}+{y}')

advanced_window.mainloop()