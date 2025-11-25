import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import cv2 # Required for segmentation techniques

# --- Global Variables ---
original_image_pil = None
processed_image_pil = None
img_history = []
HISTORY_LIMIT = 10 

# --- Robust File Picker (For stability) ---

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

# --- History and Undo Logic ---

def save_state():
    """Saves the current processed image state to the history stack."""
    global processed_image_pil, img_history
    if processed_image_pil:
        if len(img_history) >= HISTORY_LIMIT:
            img_history.pop(0) # Remove the oldest state
        img_history.append(processed_image_pil.copy())

def undo():
    """Restores the previous image state from the history stack."""
    global processed_image_pil, img_history
    if len(img_history) > 1:
        img_history.pop()
        processed_image_pil = img_history[-1].copy()
        update_images()
        # messagebox.showinfo("Undo", "Undo successful.")
    else:
        messagebox.showwarning("Warning", "Cannot undo further.")

# --- Image Display and Utilities ---

def update_images():
    """Updates the displayed images, resizing them to fit the canvas."""
    global processed_image_pil, original_image_pil
    
    if original_image_pil is None or processed_image_pil is None:
        return

    try:
        segment_window.update_idletasks()
        
        frame_width = right_frame.winfo_width()
        frame_height = right_frame.winfo_height()

        if frame_width < 100 or frame_height < 100:
            return # Wait for geometry

        canvas_w = frame_width // 2
        canvas_h = frame_height

        max_w = int(canvas_w - 20)
        max_h = int(canvas_h - 20)
        
        # Helper to resize and display
        def display_image(image_pil, label_widget):
            img_w, img_h = image_pil.size
            ratio = min(max_w / img_w, max_h / img_h)
            new_w, new_h = int(img_w * ratio), int(img_h * ratio)
            
            # Use Image.Resampling.LANCZOS for quality
            display_pil = image_pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
            display_tk = ImageTk.PhotoImage(display_pil)
            label_widget.config(image=display_tk, text="")
            label_widget.image = display_tk # Keep a reference
            
        display_image(original_image_pil, original_image_label)
        display_image(processed_image_pil, processed_image_label)
        
    except Exception as e:
        print(f"FATAL ERROR in update_images: {e}")
        messagebox.showerror("Display Error", "Could not display image properly.")


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
            
            update_images()
            messagebox.showinfo("Success", "Image loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")

# --- Segmentation Functions ---

def apply_kmeans_segmentation():
    """Applies K-Means clustering for color-based segmentation."""
    global processed_image_pil
    if processed_image_pil is None:
        messagebox.showwarning("Warning", "No image loaded to segment.")
        return
    
    try:
        # 1. Get k value from entry
        k_val = int(k_clusters_entry.get())
        if k_val < 2 or k_val > 16:
            messagebox.showwarning("Input Error", "K must be between 2 and 16.")
            return

        save_state()
        
        # 2. Convert PIL image to OpenCV BGR format (NumPy array)
        img_np = np.array(processed_image_pil)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 3. Reshape image to a list of pixels for clustering
        Z = img_cv.reshape((-1, 3))
        Z = np.float32(Z)

        # 4. Define criteria and apply kmeans()
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        ret, label, center = cv2.kmeans(Z, k_val, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

        # 5. Convert back to 8 bit and reshape the segmented image
        center = np.uint8(center)
        res = center[label.flatten()]
        segmented_img_cv = res.reshape((img_np.shape))
        
        # 6. Convert segmented OpenCV image back to PIL RGB
        segmented_img_rgb = cv2.cvtColor(segmented_img_cv, cv2.COLOR_BGR2RGB)
        processed_image_pil = Image.fromarray(segmented_img_rgb)
        
        update_images()
        
    except ValueError:
        messagebox.showerror("Input Error", "K value must be an integer.")
        if len(img_history) > 0: img_history.pop() 
    except Exception as e:
        messagebox.showerror("Processing Error", f"K-Means failed: {e}")
        if len(img_history) > 0: img_history.pop() 


def apply_thresholding():
    """Applies simple binary thresholding to create a mask."""
    global processed_image_pil
    if processed_image_pil is None:
        messagebox.showwarning("Warning", "No image loaded to threshold.")
        return
    
    try:
        # 1. Get threshold value from entry
        thresh_val = float(threshold_entry.get())
        if thresh_val < 0 or thresh_val > 255:
            messagebox.showwarning("Input Error", "Threshold value must be between 0 and 255.")
            return

        save_state()
        
        # 2. Convert PIL image to OpenCV BGR format (NumPy array)
        img_np = np.array(processed_image_pil)
        img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 3. Convert to Grayscale
        gray_cv = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # 4. Apply Binary Thresholding: Pixels > thresh_val become 0 (black), others 255 (white)
        _, thresholded_cv = cv2.threshold(gray_cv, thresh_val, 255, cv2.THRESH_BINARY)
        
        # 5. Convert back to PIL image (need to make it RGB for display)
        thresholded_pil = Image.fromarray(thresholded_cv).convert("RGB")
        processed_image_pil = thresholded_pil
        
        update_images()
        
    except ValueError:
        messagebox.showerror("Input Error", "Threshold value must be a number.")
        if len(img_history) > 0: img_history.pop() 
    except Exception as e:
        messagebox.showerror("Processing Error", f"Thresholding failed: {e}")
        if len(img_history) > 0: img_history.pop() 


def save_image():
    """Saves the current processed image."""
    global processed_image_pil
    if processed_image_pil:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")]
        )
        if file_path:
            try:
                processed_image_pil.save(file_path)
                messagebox.showinfo("Success", f"Image saved successfully to {file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {e}")
    else:
        messagebox.showwarning("Warning", "No processed image to save.")


# --- Main Window Setup ---

segment_window = tk.Tk()
segment_window.title("Image Segmentation")
segment_window.geometry("1000x700")

# Configure grid weights
segment_window.grid_columnconfigure(0, weight=0) 
segment_window.grid_columnconfigure(1, weight=1) 
segment_window.grid_rowconfigure(0, weight=1)

# Left Panel (Controls)
left_frame = tk.Frame(segment_window, width=250, bg='#E8F5E9', relief='raised')
left_frame.grid(row=0, column=0, sticky='nswe', padx=5, pady=5)
left_frame.grid_propagate(False) 
left_frame.config(width=250)

# Right Panel (Image Display)
right_frame = tk.Frame(segment_window, bg='white')
right_frame.grid(row=0, column=1, sticky='nswe', padx=5, pady=5)
right_frame.grid_columnconfigure(0, weight=1)
right_frame.grid_columnconfigure(1, weight=1)
right_frame.grid_rowconfigure(0, weight=1)

# Image Display Widgets
original_image_label = tk.Label(right_frame, text="Original Image", bg='#F0F0F0', font=('Helvetica', 12, 'bold'))
original_image_label.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

processed_image_label = tk.Label(right_frame, text="Segmented Image", bg='#F0F0F0', font=('Helvetica', 12, 'bold'))
processed_image_label.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

# --- Populate Controls ---

tk.Label(left_frame, text="Segmentation Controls", font=('Helvetica', 16, 'bold'), bg='#E8F5E9').pack(pady=10)

upload_btn = ttk.Button(left_frame, text="Load Image", command=upload_image)
upload_btn.pack(pady=10, padx=10, fill='x')

save_btn = ttk.Button(left_frame, text="Save Segmented Image", command=save_image)
save_btn.pack(pady=10, padx=10, fill='x')

undo_btn = ttk.Button(left_frame, text="Undo Last Operation", command=undo)
undo_btn.pack(pady=10, padx=10, fill='x')

ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)

# K-Means Segmentation Controls
tk.Label(left_frame, text="K-Means Clustering", font=('Helvetica', 14, 'underline'), bg='#E8F5E9').pack(pady=5)
tk.Label(left_frame, text="Number of Clusters (K):", font=('Helvetica', 12), bg='#E8F5E9').pack()
k_clusters_entry = tk.Entry(left_frame, width=10)
k_clusters_entry.insert(0, "4")
k_clusters_entry.pack(pady=5)
kmeans_btn = ttk.Button(left_frame, text="Apply K-Means", command=apply_kmeans_segmentation)
kmeans_btn.pack(pady=10, padx=10, fill='x')

ttk.Separator(left_frame, orient='horizontal').pack(fill='x', pady=10, padx=10)

# Thresholding Controls
tk.Label(left_frame, text="Binary Thresholding", font=('Helvetica', 14, 'underline'), bg='#E8F5E9').pack(pady=5)
tk.Label(left_frame, text="Threshold Value (0-255):", font=('Helvetica', 12), bg='#E8F5E9').pack()
threshold_entry = tk.Entry(left_frame, width=10)
threshold_entry.insert(0, "127")
threshold_entry.pack(pady=5)
threshold_btn = ttk.Button(left_frame, text="Apply Threshold", command=apply_thresholding)
threshold_btn.pack(pady=10, padx=10, fill='x')


# Bind resizing event to update images
segment_window.bind('<Configure>', lambda e: segment_window.after_idle(update_images))

# Preload image if path provided on the command line (forwarded from advanced_options)
import sys
from pathlib import Path
if len(sys.argv) > 1:
    try:
        p = Path(sys.argv[1])
        if p.exists():
            new_image = Image.open(p).convert('RGB')
            original_image_pil = new_image.copy()
            processed_image_pil = new_image.copy()
            img_history = [processed_image_pil.copy()]
            update_images()
    except Exception as e:
        messagebox.showwarning('Preload Warning', f'Failed to preload image: {e}')

segment_window.mainloop()