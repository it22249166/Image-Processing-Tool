import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageFilter, Image
import numpy as np

# Global variables for this window
original_image = None
processed_image = None
display_original = None
display_processed = None
img_history = []
HISTORY_LIMIT = 10 # Maximum number of states to save

# --- Robust File Picker (Copied from main.py for stability) ---

def pick_file_with_pyside():
    """Return a selected file path using PySide6's QFileDialog, or None if PySide6 isn't available or canceled."""
    try:
        # We must import these here as PySide6 might not be installed
        from PySide6.QtWidgets import QApplication, QFileDialog
    except Exception:
        return None

    app = QApplication.instance()
    created_app = False
    if app is None:
        # Create a temporary QApplication instance if none exists
        try:
            app = QApplication([])
            created_app = True
        except Exception:
            return None # Cannot create app, return None

    try:
        # Use native dialog where possible; filter for common image types.
        dialog_filter = "Images (*.png *.jpg *.jpeg);;All Files (*)"
        file_path, _ = QFileDialog.getOpenFileName(None, "Open Image", "", dialog_filter)
    except Exception as e:
        print(f"PySide6 dialog error: {e}")
        file_path = None

    # Clean up the temporary QApplication
    if created_app:
        try:
            app.quit()
        except Exception:
            pass

    return file_path if file_path else None


# --- History and Undo Logic (Unchanged) ---

def save_state():
    """Saves the current processed image state to the history stack."""
    global processed_image, img_history
    if processed_image:
        if len(img_history) >= HISTORY_LIMIT:
            img_history.pop(0) # Remove the oldest state
        img_history.append(processed_image.copy())

def undo():
    """Restores the previous image state from the history stack."""
    global processed_image, img_history
    if len(img_history) > 1:
        img_history.pop()
        processed_image = img_history[-1].copy()
        update_images()
        # messagebox.showinfo("Undo", "Undo successful.")
    else:
        messagebox.showwarning("Warning", "Cannot undo further. This is the original image state or initial state.")

# --- Image Display and Utilities ---

def update_images():
    """Updates the displayed images, resizing them to fit the canvas."""
    global processed_image, original_image, display_original, display_processed
    
    if original_image is None or processed_image is None:
        return

    try:
        filter_window.update_idletasks()
        
        frame_width = right_frame.winfo_width()
        frame_height = right_frame.winfo_height()

        # Defensive geometry check
        if frame_width < 100 or frame_height < 100:
            print("Warning: Window geometry not ready for resizing.")
            return

        canvas_w = frame_width // 2
        canvas_h = frame_height

        max_w = int(canvas_w - 20)
        max_h = int(canvas_h - 20)

        # Update Original Image
        img_w, img_h = original_image.size
        ratio = min(max_w / img_w, max_h / img_h)
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        
        # Use Image.Resampling.LANCZOS for better quality and stability
        display_original_pil = original_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        display_original = ImageTk.PhotoImage(display_original_pil)
        original_image_label.config(image=display_original, text="")
        original_image_label.image = display_original
        
        # Update Processed Image
        img_w, img_h = processed_image.size
        ratio = min(max_w / img_w, max_h / img_h)
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        
        display_processed_pil = processed_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        display_processed = ImageTk.PhotoImage(display_processed_pil)
        processed_image_label.config(image=display_processed, text="")
        processed_image_label.image = display_processed
        
    except Exception as e:
        print(f"FATAL ERROR in update_images: {e}")
        messagebox.showerror("Display Error", "Could not display image properly. Try resizing the window slightly.")


def upload_image():
    """Handles file dialog and loads the selected image, prioritizing a robust file picker."""
    global original_image, processed_image, img_history
    
    # 1. Try PySide6 file picker first (more stable on some systems)
    file_path = pick_file_with_pyside()
    
    # 2. If PySide6 is not available or failed, fall back to Tkinter dialog
    if not file_path:
        # Wrap in a try-except in case the file dialog itself crashes/hangs
        try:
            file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg")])
        except Exception as e:
            messagebox.showerror("File Dialog Error", f"The image selection dialog crashed: {e}")
            return
            
    if file_path:
        try:
            # Load and convert to RGB for consistent processing
            new_image = Image.open(file_path).convert("RGB")
            
            original_image = new_image.copy()
            processed_image = new_image.copy()
            
            # Initialize history stack
            img_history = [processed_image.copy()]
            
            update_images()
            messagebox.showinfo("Success", "Image loaded successfully.")
        except Exception as e:
            # Catches exceptions during file read/PIL conversion
            messagebox.showerror("Error", f"Failed to load image: {e}")

# --- Filter Processing Functions (Unchanged) ---

def apply_filter(filter_name):
    """Applies the selected filter from PIL.ImageFilter."""
    global processed_image, img_history
    if processed_image:
        save_state()
        
        current_img = processed_image 
        
        if filter_name == "BLUR":
            filtered_img = current_img.filter(ImageFilter.BLUR)
        elif filter_name == "CONTOUR":
            filtered_img = current_img.filter(ImageFilter.CONTOUR)
        elif filter_name == "DETAIL":
            filtered_img = current_img.filter(ImageFilter.DETAIL)
        elif filter_name == "EDGE_ENHANCE":
            filtered_img = current_img.filter(ImageFilter.EDGE_ENHANCE)
        elif filter_name == "EMBOSS":
            filtered_img = current_img.filter(ImageFilter.EMBOSS)
        elif filter_name == "SHARPEN":
            filtered_img = current_img.filter(ImageFilter.SHARPEN)
        elif filter_name == "SMOOTH":
            filtered_img = current_img.filter(ImageFilter.SMOOTH)
        else:
            messagebox.showwarning("Filter Error", "Unknown filter selected.")
            if len(img_history) > 0: 
                img_history.pop() 
            return
            
        processed_image = filtered_img
        update_images()
    else:
        messagebox.showwarning("Warning", "No image loaded to apply filter.")

# --- Save Function (Unchanged) ---

def save_image():
    """Saves the current processed image."""
    global processed_image
    if processed_image:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )
        if file_path:
            try:
                processed_image.save(file_path)
                messagebox.showinfo("Success", f"Image saved successfully to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")
    else:
        messagebox.showwarning("Warning", "No processed image to save.")

# --- Main Window Setup (Unchanged) ---

filter_window = tk.Tk()
filter_window.title("Image Filters")
filter_window.geometry("1000x700")

# Configure grid weights
filter_window.grid_columnconfigure(0, weight=0) 
filter_window.grid_columnconfigure(1, weight=1) 
filter_window.grid_rowconfigure(0, weight=1)

# Left Panel (Controls)
left_frame = tk.Frame(filter_window, width=250, bg='#DDEEEE', relief='raised')
left_frame.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
left_frame.grid_propagate(False) 
left_frame.config(width=250)

# Right Panel (Image Display)
right_frame = tk.Frame(filter_window, bg='white')
right_frame.grid(row=0, column=1, sticky='nswe', padx=5, pady=5)
right_frame.grid_columnconfigure(0, weight=1)
right_frame.grid_columnconfigure(1, weight=1)
right_frame.grid_rowconfigure(0, weight=1)

# Image Display Widgets
original_image_label = tk.Label(right_frame, text="Original Image", bg='#F0F0F0', font=('Helvetica', 12, 'bold'))
original_image_label.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

processed_image_label = tk.Label(right_frame, text="Processed Image", bg='#F0F0F0', font=('Helvetica', 12, 'bold'))
processed_image_label.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

# --- Populate Controls ---

tk.Label(left_frame, text="Filter Controls", font=('Helvetica', 18, 'bold'), bg='#DDEEEE').pack(pady=10)

upload_btn = ttk.Button(left_frame, text="Load Image", command=upload_image)
upload_btn.pack(pady=10, padx=10, fill='x')

save_btn = ttk.Button(left_frame, text="Save Processed Image", command=save_image)
save_btn.pack(pady=10, padx=10, fill='x')

undo_btn = ttk.Button(left_frame, text="Undo", command=undo)
undo_btn.pack(pady=10, padx=10, fill='x')

ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=5, padx=10)

tk.Label(left_frame, text="Spatial Filters", font=('Helvetica', 14), bg='#DDEEEE').pack(pady=5)

filters = [
    ("Blur", "BLUR"), ("Sharpen", "SHARPEN"), ("Edge Enhance", "EDGE_ENHANCE"),
    ("Emboss", "EMBOSS"), ("Contour", "CONTOUR"), ("Detail", "DETAIL"),
    ("Smooth", "SMOOTH"),
]

for text, name in filters:
    btn = ttk.Button(left_frame, text=text, command=lambda n=name: apply_filter(n))
    btn.pack(pady=5, padx=10, fill='x')


# Bind resizing event to update images (using after_idle for safety)
filter_window.bind('<Configure>', lambda e: filter_window.after_idle(update_images))

# Preload image if launched with an image path argument
import sys
from pathlib import Path
if len(sys.argv) > 1:
    try:
        p = Path(sys.argv[1])
        if p.exists():
            new_image = Image.open(p).convert('RGB')
            original_image = new_image.copy()
            processed_image = new_image.copy()
            img_history = [processed_image.copy()]
            update_images()
    except Exception as e:
        messagebox.showwarning('Preload Warning', f'Failed to preload image: {e}')

filter_window.mainloop()