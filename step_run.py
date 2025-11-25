
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps
import sys
import numpy as np

# --- Configuration ---
# Define the fixed size for the image display canvases
DISPLAY_WIDTH = 430
DISPLAY_HEIGHT = 550
CANVAS_BG_COLOR = 'lightgray' # A neutral color for the display areas

# --- Utility Functions ---

def resize_image_to_fit(pil_img, target_width, target_height):
    """
    Resizes a PIL Image object to fit within target dimensions while 
    maintaining the aspect ratio. Returns the PIL Image object.
    """
    if pil_img is None:
        return None
        
    width, height = pil_img.size
    
    # Calculate scaling factor
    ratio_w = target_width / width
    ratio_h = target_height / height
    scale_factor = min(ratio_w, ratio_h)
    
    # Calculate new dimensions
    new_width = int(width * scale_factor)
    new_height = int(height * scale_factor)
    
    # Resize the image (Image.Resampling.LANCZOS is high quality)
    resized_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    return resized_img

# --- Main Application Class ---

class ImageProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Digital Image Processing GUI')
        
        # State variables to hold the original and current PIL images
        self.original_pil_img = None
        self.modified_pil_img = None
        self.img_history = []  # For undo functionality
        
        # State variables to hold the Tkinter PhotoImage objects 
        # (Must be stored to prevent garbage collection)
        self.tk_original_img = None
        self.tk_modified_img = None
        
        self._setup_ui()

    def _setup_ui(self):
        # 1. Left Control Panel (Scrollable)
        self.canvas_left = tk.Canvas(self.root, bg='#3498DB', width=300, height=700)
        self.canvas_left.pack(side='left', fill='y')

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.root, orient='vertical', command=self.canvas_left.yview)
        scrollbar.pack(side='left', fill='y')
        
        self.canvas_left.configure(yscrollcommand=scrollbar.set)
        
        # Frame inside the canvas to hold controls
        self.frame_left = tk.Frame(self.canvas_left, bg='#3498DB')
        self.canvas_left.create_window((0, 0), window=self.frame_left, anchor='nw')

        # Bind to update scroll region when frame_left size changes
        self.frame_left.bind('<Configure>', 
                             lambda e: self.canvas_left.configure(scrollregion=self.canvas_left.bbox('all')))

        # 2. Right Display Panel (Original and Modified)
        self.frame_right = tk.Frame(self.root, bg='white', width=900, height=700)
        self.frame_right.pack(side='right', fill='both', expand=True)

        # 2.1 Original Image Frame
        self.frame_original = tk.Frame(self.frame_right, bg='white', width=450, height=700)
        self.frame_original.pack(side='left', fill='both', expand=True)
        self.original_label = tk.Label(self.frame_original, text='Original Image', bg='white', font=('Helvetica', 16, 'bold'))
        self.original_label.pack(pady=(10, 5))
        
        # Canvas for Original Image Display (Fixed size constraint for image)
        self.canvas_original = tk.Canvas(self.frame_original, bg=CANVAS_BG_COLOR, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
        self.canvas_original.pack(pady=10, padx=10)

        # 2.2 Modified Image Frame
        self.frame_modified = tk.Frame(self.frame_right, bg='white', width=450, height=700)
        self.frame_modified.pack(side='right', fill='both', expand=True)
        self.modified_label = tk.Label(self.frame_modified, text='Modified Image', bg='white', font=('Helvetica', 16, 'bold'))
        self.modified_label.pack(pady=(10, 5))
        
        # Canvas for Modified Image Display (Fixed size constraint for image)
        self.canvas_modified = tk.Canvas(self.frame_modified, bg=CANVAS_BG_COLOR, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT)
        self.canvas_modified.pack(pady=10, padx=10)

        # Undo Button
        undo_btn_modified = ttk.Button(self.frame_modified, text='Undo', command=self.undo_last_action)
        undo_btn_modified.pack(pady=10, padx=20)
        
        # 3. Controls in Left Frame
        self.create_controls()


    def create_controls(self):
        # Upload Button
        upload_btn = ttk.Button(self.frame_left, text='Upload Image', command=self.upload_image)
        upload_btn.pack(pady=20, padx=20, fill='x')
        
        # --- Basic Transformations ---
        tk.Label(self.frame_left, text="Basic Tools", background='#3498DB', foreground='white', font=('Helvetica', 12, 'bold')).pack(pady=(10, 5), padx=20, fill='x')

        ttk.Button(self.frame_left, text="Flip Image (Horizontal)", command=self.flip_image).pack(pady=5, padx=20, fill='x')
        ttk.Button(self.frame_left, text="Invert Colors", command=self.invert_image).pack(pady=5, padx=20, fill='x')
        ttk.Button(self.frame_left, text="Grayscale", command=self.convert_to_grayscale).pack(pady=5, padx=20, fill='x')
        ttk.Button(self.frame_left, text="Reset Image", command=self.reset_image).pack(pady=20, padx=20, fill='x')

        # --- Advanced Options ---
        tk.Label(self.frame_left, text="Advanced Tools", background='#3498DB', foreground='white', font=('Helvetica', 12, 'bold')).pack(pady=(10, 5), padx=20, fill='x')

        ttk.Button(self.frame_left, text="Advanced Options", command=self.open_advanced_options).pack(pady=20, padx=20, fill='x')
        ttk.Button(self.frame_left, text="View Image Properties", command=self.view_image_properties).pack(pady=10, padx=20, fill='x')
        
        # Crop tool instructions
        crop_instruction = tk.Label(self.frame_left, text="[Crop Tool Instructions Here]", background='#3498DB', foreground='white', wraplength=260)
        crop_instruction.pack(pady=10, padx=20)


    # --- Image Handling Methods ---
    
    def upload_image(self):
        file_path = filedialog.askopenfilename(
            title="Select an Image",
            filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.bmp")]
        )
        
        if not file_path:
            return 
            
        try:
            # 1. Open and store the original PIL image
            self.original_pil_img = Image.open(file_path)
            self.modified_pil_img = self.original_pil_img.copy()
            self.img_history = [self.original_pil_img.copy()] # Start history

            # 2. Resize both and display
            self._display_image(self.canvas_original, self.original_pil_img, is_original=True)
            self._display_image(self.canvas_modified, self.modified_pil_img, is_original=False)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image: {e}")
            self.original_pil_img = None
            self.modified_pil_img = None


    def _display_image(self, canvas, pil_img, is_original):
        """
        Handles the resizing and displaying of a PIL image onto a canvas.
        """
        if pil_img is None:
            canvas.delete("all")
            return

        # Resize the image to fit the canvas dimensions
        resized_img = resize_image_to_fit(pil_img, canvas.winfo_width(), canvas.winfo_height())
        
        if resized_img is None:
            return

        # Convert the resized PIL image to a Tkinter PhotoImage
        tk_img = ImageTk.PhotoImage(resized_img)
        
        # Store the Tkinter object to prevent garbage collection
        if is_original:
            self.tk_original_img = tk_img
        else:
            self.tk_modified_img = tk_img
        
        # Clear the canvas and display the new image centered
        canvas.delete("all")
        canvas.create_image(
            canvas.winfo_width() / 2, 
            canvas.winfo_height() / 2, 
            image=tk_img, 
            anchor="center"
        )


    def update_modified_image(self, new_pil_img):
        """
        Applies a new processed image, updates history, and refreshes the display.
        """
        if new_pil_img is None:
            return # Safety check

        # Update history
        self.img_history.append(self.modified_pil_img.copy())
        
        # Update current image
        self.modified_pil_img = new_pil_img
        
        # Display the updated image
        self._display_image(self.canvas_modified, self.modified_pil_img, is_original=False)


    # --- Image Processing Stubs ---
    
    def flip_image(self):
        if self.modified_pil_img:
            flipped_img = ImageOps.mirror(self.modified_pil_img)
            self.update_modified_image(flipped_img)
        else:
            messagebox.showwarning("Warning", "No image loaded to flip.")

    def invert_image(self):
        if self.modified_pil_img:
            inverted_img = ImageOps.invert(self.modified_pil_img.convert('RGB'))
            self.update_modified_image(inverted_img)
        else:
            messagebox.showwarning("Warning", "No image loaded to invert.")

    def convert_to_grayscale(self):
        if self.modified_pil_img:
            gray_img = self.modified_pil_img.convert('L').convert('RGB')
            self.update_modified_image(gray_img)
        else:
            messagebox.showwarning("Warning", "No image loaded.")

    def reset_image(self):
        if self.original_pil_img:
            self.modified_pil_img = self.original_pil_img.copy()
            self.img_history = [self.original_pil_img.copy()] # Reset history
            self._display_image(self.canvas_modified, self.modified_pil_img, is_original=False)
        else:
            messagebox.showwarning("Warning", "No image to reset.")

    def undo_last_action(self):
        if len(self.img_history) > 1:
            # Pop the current state from history (which is the last one added)
            self.img_history.pop() 
            # Set the modified image to the previous state
            self.modified_pil_img = self.img_history[-1].copy()
            self._display_image(self.canvas_modified, self.modified_pil_img, is_original=False)
        elif len(self.img_history) == 1:
             # If only the original image is left, just reset to it without clearing history
            self.modified_pil_img = self.img_history[0].copy()
            self._display_image(self.canvas_modified, self.modified_pil_img, is_original=False)
        else:
            messagebox.showinfo("Undo", "Nothing left to undo.")
            
    # --- Advanced and Property Stubs ---

    def open_advanced_options(self):
        # This will eventually launch advanced_options.py
        messagebox.showinfo("Advanced Options", "Launching advanced tools (using 'advanced_options.py')...")

    def view_image_properties(self):
        if self.modified_pil_img:
            props = (
                f"Format: {self.modified_pil_img.format}\n"
                f"Size: {self.modified_pil_img.size[0]}x{self.modified_pil_img.size[1]} pixels\n"
                f"Mode: {self.modified_pil_img.mode}\n"
                f"Palette: {self.modified_pil_img.getpalette()}\n"
            )
            messagebox.showinfo("Image Properties", props)
        else:
            messagebox.showwarning("Warning", "No image loaded.")

# --- Run Application ---
if __name__ == '__main__':
    root = tk.Tk()
    app = ImageProcessorApp(root)
    # Ensure canvas sizes are correctly calculated after main window setup
    root.update_idletasks() 
    root.mainloop()