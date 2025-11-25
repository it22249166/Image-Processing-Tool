import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps
import numpy as np
import sys
from pathlib import Path

# --- Global Variables and Constants ---
original_image_pil = None
processed_image_pil = None
img_history = []
HISTORY_LIMIT = 10 
C_LOG = 255 / np.log(1 + 255) # Constant for log transformation to map 255 to 255

# --- Robust File Picker (For stability) ---

def pick_file_with_pyside():
    """Return a selected file path using PySide6's QFileDialog, or None if PySide6 isn't available or canceled."""
    try:
        # Import PySide6 here in case it's not installed
        from PySide6.QtWidgets import QApplication, QFileDialog
    except Exception:
        return None

    app = QApplication.instance()
    created_app = False
    if app is None:
        try:
            app = QApplication(sys.argv)
            created_app = True
        except Exception:
            return None

    try:
        dialog_filter = "Images (*.png *.jpg *.jpeg);;All Files (*)"
        # Use a temporary parent widget (None) or ensure QApplication is fully initialized
        file_path, _ = QFileDialog.getOpenFileName(None, "Open Image", "", dialog_filter)
    except Exception:
        file_path = None

    if created_app:
        try:
            # Quit the application instance we created
            app.quit()
        except Exception:
            pass

    return file_path if file_path else None

# --- History and Undo Logic ---

def save_state():
    """Saves the current processed image state to the history stack."""
    global processed_image_pil, img_history
    if processed_image_pil:
        # Only save if the new state is different from the last one (simple check)
        if not img_history or not np.array_equal(np.array(processed_image_pil), np.array(img_history[-1])):
            if len(img_history) >= HISTORY_LIMIT:
                img_history.pop(0) # Remove the oldest state
            img_history.append(processed_image_pil.copy())

def undo():
    """Restores the previous image state from the history stack."""
    global processed_image_pil, img_history, original_image_pil
    if len(img_history) > 1:
        # Pop the current state, and restore the state before it
        img_history.pop()
        processed_image_pil = img_history[-1].copy()
        update_images()
        # messagebox.showinfo("Undo", "Undo successful.")
    elif len(img_history) == 1 and original_image_pil:
        # Restore to the very first loaded image
        processed_image_pil = original_image_pil.copy()
        img_history = [processed_image_pil.copy()]
        update_images()
        messagebox.showwarning("Reset", "Reverted to original loaded image.")
    else:
        messagebox.showwarning("Warning", "Cannot undo further.")

# --- Image Display and Utilities ---

def update_images():
    """Updates the displayed images, resizing them to fit the canvas."""
    global processed_image_pil, original_image_pil
    
    if original_image_pil is None or processed_image_pil is None:
        return

    try:
        tonal_window.update_idletasks()
        
        frame_width = right_frame.winfo_width()
        frame_height = right_frame.winfo_height()

        if frame_width < 100 or frame_height < 100:
            return

        # Allocate space for both images side-by-side
        max_w = int((frame_width / 2) - 20)
        max_h = int(frame_height - 20)
        
        # Helper to resize and display
        def display_image(image_pil, label_widget):
            img_w, img_h = image_pil.size
            
            # Calculate ratio to fit inside max_w x max_h
            ratio = min(max_w / img_w, max_h / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
            
            display_pil = image_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            display_tk = ImageTk.PhotoImage(display_pil)
            label_widget.config(image=display_tk, text="")
            label_widget.image = display_tk # Keep a reference
            
        display_image(original_image_pil, original_image_label)
        display_image(processed_image_pil, processed_image_label)
        
    except Exception as e:
        print(f"FATAL ERROR in update_images: {e}")
        # messagebox.showerror("Display Error", "Could not display image properly.")


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
        
            # Load and convert to RGB for consistent processing
            new_image = Image.open(file_path).convert("RGB")
            
            original_image_pil = new_image.copy()
            processed_image_pil = new_image.copy()
            
            # Initialize history stack with the current image
            img_history = [processed_image_pil.copy()]
            
            # Reset sliders/entries to default state
            brightness_slider.set(1.0)
            gamma_entry.delete(0, tk.END)
            gamma_entry.insert(0, "1.0")
            
            update_images()
            messagebox.showinfo("Success", "Image loaded successfully.")
        
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

# --- Tonal Transformation Functions ---

def adjust_brightness(value):
    """Adjusts brightness using PIL ImageEnhance."""
    global processed_image_pil
    if original_image_pil is None:
        # messagebox.showwarning("Warning", "No image loaded")
        return

    try:
        # We always enhance the current image in the history stack
        enhancer = ImageEnhance.Brightness(img_history[-1])
        bright_img = enhancer.enhance(float(value))
        processed_image_pil = bright_img
        update_images()
    except Exception as e:
        print(f"Brightness error: {e}")

def commit_brightness_change():
    """Saves the current brightness-adjusted image to history when the slider is released."""
    if processed_image_pil and original_image_pil:
        save_state()

def apply_negative():
    """Applies the image negative transformation (inversion)."""
    global processed_image_pil
    if processed_image_pil is None:
        messagebox.showwarning("Warning", "No image loaded to process.")
        return

    try:
        save_state()
        # Use ImageOps.invert for a fast, built-in negative operation
        processed_image_pil = ImageOps.invert(processed_image_pil)
        
        update_images()
        messagebox.showinfo("Success", "Applied Negative (Invert).")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply negative: {e}")
        if len(img_history) > 0: img_history.pop() # Remove failed state

def apply_log_transformation():
    """Applies the log transformation: s = c * log(1 + r)."""
    global processed_image_pil
    if processed_image_pil is None:
        messagebox.showwarning("Warning", "No image loaded to process.")
        return

    try:
        save_state()
        
        # 1. Convert PIL image to NumPy array (float for math)
        img_np = np.array(processed_image_pil, dtype=float)
        
        # 2. Normalize intensity (0-1) for log calculation
        normalized_img = img_np / 255.0
        
        # 3. Apply log transformation: s = c * log(1 + r)
        log_transformed = C_LOG * np.log(1 + normalized_img * 255) / 255
        
        # 4. Scale back to 0-255 and ensure type is uint8
        output_img_np = np.clip(log_transformed * 255, 0, 255).astype(np.uint8)

        # 5. Convert back to PIL Image
        processed_image_pil = Image.fromarray(output_img_np)
        
        update_images()
        messagebox.showinfo("Success", "Applied Log Transformation.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply log transformation: {e}")
        if len(img_history) > 0: img_history.pop()

def apply_power_law_transformation():
    """Applies the power-law (gamma) transformation: s = r^gamma."""
    global processed_image_pil
    if processed_image_pil is None:
        messagebox.showwarning("Warning", "No image loaded to process.")
        return

    try:
        gamma = float(gamma_entry.get())
        if gamma <= 0:
            messagebox.showwarning("Input Error", "Gamma must be greater than 0.")
            return

        save_state()
        
        # 1. Convert PIL image to NumPy array (float for math)
        img_np = np.array(processed_image_pil, dtype=float)
        
        # 2. Normalize intensity (0-1)
        normalized_img = img_np / 255.0
        
        # 3. Apply Power Law (Gamma) transformation
        gamma_transformed = normalized_img ** gamma
        
        # 4. Scale back to 0-255 and ensure type is uint8
        output_img_np = np.clip(gamma_transformed * 255, 0, 255).astype(np.uint8)

        # 5. Convert back to PIL Image
        processed_image_pil = Image.fromarray(output_img_np)
        
        update_images()
        messagebox.showinfo("Success", f"Applied Power Law (Gamma={gamma}).")

    except ValueError:
        messagebox.showerror("Input Error", "Gamma value must be a number.")
        if len(img_history) > 0: img_history.pop()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to apply power law: {e}")
        if len(img_history) > 0: img_history.pop()


# --- Main Window Setup ---

tonal_window = tk.Tk()
tonal_window.title("Tonal Transformations")
tonal_window.geometry("1000x700")

# Configure grid weights
tonal_window.grid_columnconfigure(0, weight=0) 
tonal_window.grid_columnconfigure(1, weight=1) 
tonal_window.grid_rowconfigure(0, weight=1)

# Left Panel (Controls)
left_frame = tk.Frame(tonal_window, width=250, bg='#E0F7FA', relief='raised')
left_frame.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
left_frame.grid_propagate(False) 
left_frame.config(width=250)

# Right Panel (Image Display)
right_frame = tk.Frame(tonal_window, bg='white')
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

tk.Label(left_frame, text="Tonal Controls", font=('Helvetica', 16, 'bold'), bg='#E0F7FA').pack(pady=10)

# File Management Buttons
upload_btn = ttk.Button(left_frame, text="Load Image", command=upload_image)
upload_btn.pack(pady=10, padx=10, fill='x')

save_btn = ttk.Button(left_frame, text="Save Processed Image", command=save_image)
save_btn.pack(pady=10, padx=10, fill='x')

undo_btn = ttk.Button(left_frame, text="Undo Last Operation", command=undo)
undo_btn.pack(pady=10, padx=10, fill='x')

ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)

# Brightness Control
tk.Label(left_frame, text="Brightness Multiplier", font=('Helvetica', 12, 'underline'), bg='#E0F7FA').pack(pady=5)
brightness_slider = ttk.Scale(
    left_frame, 
    from_=0.1, to=2.0, 
    orient="horizontal", 
    command=adjust_brightness
)
brightness_slider.set(1.0)
brightness_slider.bind('<ButtonRelease-1>', lambda e: commit_brightness_change())
brightness_slider.pack(pady=5, padx=10, fill='x')
tk.Label(left_frame, text="0.1 (Dark) to 2.0 (Bright)", font=('Helvetica', 10), bg='#E0F7FA').pack()


ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)

# Direct Transformations
tk.Label(left_frame, text="Direct Transformations", font=('Helvetica', 14, 'underline'), bg='#E0F7FA').pack(pady=5)

negative_button = ttk.Button(left_frame, text="Apply Negative (Invert)", command=apply_negative)
negative_button.pack(pady=10, padx=10, fill='x')

log_button = ttk.Button(left_frame, text="Apply Log Transformation", command=apply_log_transformation)
log_button.pack(pady=10, padx=10, fill='x')

ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)

# Gamma/Power Law Control
tk.Label(left_frame, text="Gamma (Power Law) Transformation", font=('Helvetica', 12, 'underline'), bg='#E0F7FA').pack(pady=5)
tk.Label(left_frame, text="Gamma (γ):", font=('Helvetica', 12), bg='#E0F7FA').pack()
gamma_entry = tk.Entry(left_frame, width=10)
gamma_entry.insert(0, "1.0") # 1.0 is no change
gamma_entry.pack(pady=5)

power_law_button = ttk.Button(left_frame, text="Apply Gamma", command=apply_power_law_transformation)
power_law_button.pack(pady=10, padx=10, fill='x')


# Bind resizing event to update images
tonal_window.bind('<Configure>', lambda e: tonal_window.after_idle(update_images))

# If an image path was supplied as the first CLI argument, preload it so the UI shows it immediately.
if len(sys.argv) > 1:
    try:
        p = Path(sys.argv[1])
        if p.exists():
            new_image = Image.open(p).convert("RGB")
            original_image_pil = new_image.copy()
            processed_image_pil = new_image.copy()
            img_history = [processed_image_pil.copy()]
            try:
                brightness_slider.set(1.0)
                gamma_entry.delete(0, tk.END)
                gamma_entry.insert(0, "1.0")
            except Exception:
                pass
            update_images()
    except Exception as e:
        messagebox.showwarning("Preload Warning", f"Failed to preload image: {e}")

tonal_window.mainloop()