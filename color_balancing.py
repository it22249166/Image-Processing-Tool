import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    from PIL import Image, ImageTk, ImageEnhance
except Exception as e:
    import sys
    messagebox.showerror(
        "Missing Dependency",
        f"Pillow (PIL) is not installed or failed to import:\n{e}\nPlease install it with: pip install pillow"
    )
    sys.exit(1)

import numpy as np
import io
import base64
import sys
from pathlib import Path

# --- Global Variables and Constants ---
original_image_pil = None
processed_image_pil = None
img_history = []
HISTORY_LIMIT = 10 

# Flag set when a preload from CLI/Advanced Options supplied an image path
PRELOADED_IMAGE = False

# Global variable provided by the environment for file transfer (MANDATORY)
if 'uploaded_files_data' not in globals():
    uploaded_files_data = {} 

# Variables to store the current, live non-destructive filter settings (multipliers)
color_balance_settings = {'R': 1.0, 'G': 1.0, 'B': 1.0}
brightness_setting = 1.0


# --- Helper Functions ---
def pick_file_with_pyside():
    """Return a selected file path using PySide6's QFileDialog, or None if PySide6 isn't available or canceled."""
    try:
        # Import PySide6 here in case it's not installed, allowing the script to still run without it
        from PySide6.QtWidgets import QApplication, QFileDialog
    except Exception:
        return None

    app = QApplication.instance()
    created_app = False
    if app is None:
        try:
            app = QApplication([])
            created_app = True
        except Exception:
            return None

    try:
        dialog_filter = "Images (*.png *.jpg *.jpeg);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(None, "Open Image", "", dialog_filter)
    except Exception:
        file_path = None

    if created_app:
        try:
            app.quit()
        except Exception:
            pass

    return file_path if file_path else None

def reset_sliders():
    """Resets all control widgets to their default neutral state (1.0)."""
    global color_balance_settings, brightness_setting
    
    # Reset Tonal
    brightness_setting = 1.0
    brightness_slider.set(1.0)
    update_brightness_label(1.0, preview=False)

    # Reset Color Balance
    color_balance_settings = {'R': 1.0, 'G': 1.0, 'B': 1.0}
    red_slider.set(1.0)
    update_color_label('R', 1.0, preview=False)
    green_slider.set(1.0)
    update_color_label('G', 1.0, preview=False)
    blue_slider.set(1.0)
    update_color_label('B', 1.0, preview=False)
    

def load_initial_state():
    """Sets the initial state with no image loaded."""
    global original_image_pil, processed_image_pil, img_history
    # If an image was preloaded via CLI, keep it and do not reset state
    if PRELOADED_IMAGE:
        try:
            update_images()
        except Exception:
            pass
        return

    original_image_pil = None
    processed_image_pil = None
    img_history = []
    
    reset_sliders()
    update_images()


# --- History and Undo Logic ---

def save_state(is_major_change=True):
    """Saves the current processed image state to the history stack."""
    global processed_image_pil, img_history
    if processed_image_pil and is_major_change:
        current_state = processed_image_pil.copy()
        
        # Check if the last state is different before appending
        if not img_history or not np.array_equal(np.array(current_state), np.array(img_history[-1])):
            if len(img_history) >= HISTORY_LIMIT:
                img_history.pop(0) # Remove the oldest state
            img_history.append(current_state)

def undo():
    """Restores the previous image state from the history stack."""
    global processed_image_pil, img_history, original_image_pil
    if len(img_history) > 1:
        img_history.pop()
        processed_image_pil = img_history[-1].copy()
        update_images()
        reset_sliders() # Reset sliders since we are reverting to a committed state
        # messagebox.showinfo("Undo", "Undo successful. Sliders reset to neutral.")
    elif len(img_history) == 1 and original_image_pil:
        # If only one state remains, reset to the initial original state
        processed_image_pil = original_image_pil.copy()
        img_history = [processed_image_pil.copy()]
        reset_sliders()
        update_images()
        messagebox.showwarning("Reset", "Reverted to original loaded image.")
    else:
        messagebox.showwarning("Warning", "Cannot undo further.")


# --- File Management (Using Environment Globals) ---

def upload_image():
    """Handles file dialog and loads the selected image, prioritizing a robust file picker."""
    global original_image_pil, processed_image_pil, img_history
    
    # 1. Try PySide6 file picker first (more stable on some systems)
    file_path = pick_file_with_pyside()
    
    if not file_path:
        # 2. Fallback to standard Tkinter dialog
        try:
            file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        except Exception as e:
            messagebox.showerror("File Dialog Error", f"The image selection dialog crashed: {e}")
            return
            
    if file_path:
        try:
            # Load and convert to RGB for consistent processing
            new_image = Image.open(file_path).convert("RGB")
            
            original_image_pil = new_image.copy()
            processed_image_pil = new_image.copy()
            
            # Initialize history stack with the current image
            img_history = [processed_image_pil.copy()]
            
            # Reset sliders/entries to default state
            reset_sliders()
            
            update_images()
            messagebox.showinfo("Success", "Image loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")

def save_image():
    """Saves the current processed image to a user-specified file."""
    global processed_image_pil
    if processed_image_pil:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")],
            title="Save Processed Image As"
        )
        if file_path:
            try:
                processed_image_pil.save(file_path)
                messagebox.showinfo("Success", f"Image successfully saved to:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")
    else:
        messagebox.showwarning("Warning", "No processed image to save.")



# --- Image Display and Utilities ---

def update_images(event=None):
    """Updates the displayed images, resizing them to fit the canvas."""
    global processed_image_pil, original_image_pil
    
    right_frame.update_idletasks()
    frame_width = right_frame.winfo_width()
    frame_height = right_frame.winfo_height()

    if frame_width < 100 or frame_height < 100:
        return

    max_w = int((frame_width / 2) - 20)
    max_h = int(frame_height - 20)
        
    def display_image(image_pil, label_widget, default_text):
        if image_pil is None:
            label_widget.config(
                image='', 
                text=default_text, 
                fg='gray', 
                bg='#F0F0F0', 
                compound='center', 
                font=('Helvetica', 14)
            )
            label_widget.image = None
            return

        img_w, img_h = image_pil.size
        
        if img_w > max_w or img_h > max_h:
            ratio = min(max_w / img_w, max_h / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        else:
            new_w, new_h = img_w, img_h
        
        display_pil = image_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
        display_tk = ImageTk.PhotoImage(display_pil)
        label_widget.config(image=display_tk, text="", compound='center')
        label_widget.image = display_tk 
        
    display_image(original_image_pil, original_image_label, "Original Image Preview")
    display_image(processed_image_pil, processed_image_label, "Processed Image Preview")
        

# --- Core Image Processing Pipeline ---

def apply_color_balance_core(image_pil, r_mult, g_mult, b_mult):
    """Core function to adjust the RGB channels of an image using multipliers."""
    try:
        if image_pil.mode != 'RGB':
            image_pil = image_pil.convert('RGB')
            
        img_np = np.array(image_pil, dtype=float)
        
        # Apply scaling to each channel
        img_np[:, :, 0] *= r_mult # Red
        img_np[:, :, 1] *= g_mult # Green
        img_np[:, :, 2] *= b_mult # Blue

        # Clip and convert back
        output_img_np = np.clip(img_np, 0, 255).astype(np.uint8)
        return Image.fromarray(output_img_np)
    except Exception as e:
        print(f"Error during color balance calculation: {e}")
        return image_pil

def apply_all_transforms(base_img_pil):
    """
    Applies all non-destructive filters in a defined order 
    (Color Balance -> Brightness) to the image state committed in history.
    """
    if base_img_pil is None:
        return None
        
    current_img = base_img_pil.copy()

    # 1. Non-destructive Color Balance (Applied first)
    r_mult = color_balance_settings['R']
    g_mult = color_balance_settings['G']
    b_mult = color_balance_settings['B']
    
    if r_mult != 1.0 or g_mult != 1.0 or b_mult != 1.0:
        current_img = apply_color_balance_core(current_img, r_mult, g_mult, b_mult)

    # 2. Non-destructive Brightness Adjustment
    brightness = brightness_setting
    if brightness != 1.0:
        enhancer = ImageEnhance.Brightness(current_img)
        current_img = enhancer.enhance(brightness)
        
    return current_img


# --- Live Adjustments (Triggers Preview Update) ---

def update_color_label(channel, value, preview=True):
    """Updates the label next to the color slider and refreshes the preview."""
    global processed_image_pil
    
    value_f = float(value)
    color_balance_settings[channel] = value_f
    
    # Update Label
    if channel == 'R': red_label.config(text=f"Red Multiplier: {value_f:.2f}")
    elif channel == 'G': green_label.config(text=f"Green Multiplier: {value_f:.2f}")
    elif channel == 'B': blue_label.config(text=f"Blue Multiplier: {value_f:.2f}")
    
    # Update Preview
    if preview and img_history:
        processed_image_pil = apply_all_transforms(img_history[-1])
        update_images()

def update_brightness_label(value, preview=True):
    """Updates the label next to the brightness slider and refreshes the preview."""
    global processed_image_pil, brightness_setting
    value_f = float(value)
    brightness_setting = value_f
    brightness_label.config(text=f"Multiplier: {value_f:.2f}")
    
    # Apply all transforms to the last committed state for live preview
    if preview and img_history:
        processed_image_pil = apply_all_transforms(img_history[-1])
        update_images()

# --- Commit Function ---

def commit_adjustments(event=None):
    """Applies the current live color balance and brightness settings permanently and resets the sliders."""
    global processed_image_pil
    
    if not processed_image_pil or not img_history:
        messagebox.showwarning("Warning", "No image loaded to commit changes.")
        return

    # Check if any change has been made (using a small tolerance for floats)
    r_mult = color_balance_settings['R']
    g_mult = color_balance_settings['G']
    b_mult = color_balance_settings['B']
    brightness = brightness_setting
    
    if (abs(r_mult - 1.0) < 0.01 and 
        abs(g_mult - 1.0) < 0.01 and 
        abs(b_mult - 1.0) < 0.01 and 
        abs(brightness - 1.0) < 0.01):
        messagebox.showinfo("No Change", "All adjustments are neutral (1.0). No commit needed.")
        return

    # Apply the committed changes to the image from the last history state
    current_committed_img = apply_all_transforms(img_history[-1])
    
    # Add the new state to history
    processed_image_pil = current_committed_img.copy()
    save_state(is_major_change=True)
    
    # Reset multipliers and sliders to 1.0 so the next adjustment starts from the new state
    reset_sliders()
    
    # Re-run the transform pipeline just in case
    processed_image_pil = apply_all_transforms(img_history[-1])
    update_images()

    messagebox.showinfo("Committed", "Adjustments saved to history as a single, undoable step.")


# --- Main Window Setup ---

editor_window = tk.Tk()
editor_window.title("Non-Destructive Color Balancer")
editor_window.geometry("1000x700")

# Configure grid weights
editor_window.grid_columnconfigure(0, weight=0) 
editor_window.grid_columnconfigure(1, weight=1) 
editor_window.grid_rowconfigure(0, weight=1)

# Left Panel (Controls)
left_frame = tk.Frame(editor_window, width=280, bg='#E0F7FA', relief='raised')
left_frame.grid(row=0, column=0, sticky='nswe', padx=8, pady=8)
left_frame.grid_propagate(False) 
left_frame.config(width=280)

# Right Panel (Image Display)
right_frame = tk.Frame(editor_window, bg='white')
right_frame.grid(row=0, column=1, sticky='nswe', padx=8, pady=8)
right_frame.grid_columnconfigure(0, weight=1)
right_frame.grid_columnconfigure(1, weight=1)
right_frame.grid_rowconfigure(0, weight=1)

# Image Display Widgets
original_image_label = tk.Label(right_frame, text="Original Image", bg='#F0F0F0', font=('Helvetica', 12, 'bold'))
original_image_label.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

processed_image_label = tk.Label(right_frame, text="Processed Image", bg='#F0F0F0', font=('Helvetica', 12, 'bold'))
processed_image_label.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

# --- Populate Controls ---

tk.Label(left_frame, text="Color Control Tools", font=('Helvetica', 16, 'bold'), bg='#E0F7FA', fg='#0056b3').pack(pady=10)

# --- 1. File Management Section ---
ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=5, padx=10)

load_file_btn = ttk.Button(left_frame, text="Load Image from Files", command=upload_image)
load_file_btn.pack(pady=5, padx=10, fill='x')

# STATUS LABEL 


undo_btn = ttk.Button(left_frame, text="Undo Last Operation", command=undo)
undo_btn.pack(pady=5, padx=10, fill='x')

save_btn = ttk.Button(left_frame, text="Save Processed Image", command=save_image)
save_btn.pack(pady=10, padx=10, fill='x')

ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)


# --- 2. Live RGB Color Balance ---
tk.Label(left_frame, text="Live RGB Color Balance", font=('Helvetica', 14, 'bold'), bg='#E0F7FA', fg='#333').pack(pady=5)
tk.Label(left_frame, text="Adjust channel intensity (0.5 to 2.0)", font=('Helvetica', 10), bg='#E0F7FA').pack()

# Red Channel
tk.Label(left_frame, text="Red Channel", font=('Helvetica', 10, 'bold'), bg='#E0F7FA').pack(pady=(5, 0))
red_slider = ttk.Scale(
    left_frame, 
    from_=0.5, to=2.0, 
    orient="horizontal", 
    command=lambda v: update_color_label('R', v)
)
red_slider.set(1.0)
red_slider.pack(pady=2, padx=10, fill='x')
red_label = tk.Label(left_frame, text="Red Multiplier: 1.00", font=('Helvetica', 9), bg='#E0F7FA', foreground='#C00000') 
red_label.pack()

# Green Channel
tk.Label(left_frame, text="Green Channel", font=('Helvetica', 10, 'bold'), bg='#E0F7FA').pack(pady=(5, 0))
green_slider = ttk.Scale(
    left_frame, 
    from_=0.5, to=2.0, 
    orient="horizontal", 
    command=lambda v: update_color_label('G', v)
)
green_slider.set(1.0)
green_slider.pack(pady=2, padx=10, fill='x')
green_label = tk.Label(left_frame, text="Green Multiplier: 1.00", font=('Helvetica', 9), bg='#E0F7FA', foreground='#008000')
green_label.pack()

# Blue Channel
tk.Label(left_frame, text="Blue Channel", font=('Helvetica', 10, 'bold'), bg='#E0F7FA').pack(pady=(5, 0))
blue_slider = ttk.Scale(
    left_frame, 
    from_=0.5, to=2.0, 
    orient="horizontal", 
    command=lambda v: update_color_label('B', v)
)
blue_slider.set(1.0)
blue_slider.pack(pady=2, padx=10, fill='x')
blue_label = tk.Label(left_frame, text="Blue Multiplier: 1.00", font=('Helvetica', 9), bg='#E0F7FA', foreground='#0000C0')
blue_label.pack()


# --- 3. Live Brightness Adjustment ---
ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)
tk.Label(left_frame, text="Live Brightness", font=('Helvetica', 14, 'bold'), bg='#E0F7FA', fg='#333').pack(pady=5)

# Brightness Control
brightness_slider = ttk.Scale(
    left_frame, 
    from_=0.1, to=2.0, 
    orient="horizontal", 
    command=update_brightness_label
)
brightness_slider.set(1.0)
brightness_slider.pack(pady=2, padx=10, fill='x')

brightness_label = tk.Label(left_frame, text="Multiplier: 1.00", font=('Helvetica', 10), bg='#E0F7FA')
brightness_label.pack()

# Commit Button
commit_btn = ttk.Button(left_frame, text="COMMIT ALL ADJUSTMENTS to History", command=commit_adjustments)
commit_btn.pack(pady=15, padx=10, fill='x')


# Bind resizing event to update images
editor_window.bind('<Configure>', update_images)

# Set initial state without image
editor_window.after(100, load_initial_state)

# Preload image if a path was supplied on the command line (forwarded by advanced_options.py)
if len(sys.argv) > 1:
    try:
        p = Path(sys.argv[1])
        if p.exists():
            new_image = Image.open(p).convert('RGB')
            original_image_pil = new_image.copy()
            processed_image_pil = new_image.copy()
            img_history = [processed_image_pil.copy()]
            PRELOADED_IMAGE = True
            reset_sliders()
            update_images()
    except Exception as e:
        messagebox.showwarning('Preload Warning', f'Failed to preload image: {e}')

editor_window.mainloop()