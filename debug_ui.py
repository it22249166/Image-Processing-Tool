# debug_ui.py
# Create the main UI step-by-step and print progress after each step.
import tkinter as tk
from tkinter import ttk
import sys

steps = []

def step(name):
    print('STEP:', name)
    steps.append(name)
    sys.stdout.flush()

try:
    step('create root')
    root = tk.Tk()
    root.title('Debug UI')

    step('create canvas_left')
    canvas_left = tk.Canvas(root, bg='#3498DB', width=300, height=700)
    canvas_left.pack(side='left', fill='both', expand=True)
    root.update()

    step('create scrollbar')
    scrollbar = ttk.Scrollbar(root, orient='vertical', command=canvas_left.yview)
    scrollbar.pack(side='left', fill='y')
    root.update()

    step('configure canvas')
    canvas_left.configure(yscrollcommand=scrollbar.set)
    canvas_left.bind('<Configure>', lambda e: canvas_left.configure(scrollregion=canvas_left.bbox('all')))
    root.update()

    step('create frame_left inside canvas')
    frame_left = tk.Frame(canvas_left, bg='#3498DB')
    canvas_left.create_window((0, 0), window=frame_left, anchor='nw')
    root.update()

    step('create frame_right')
    frame_right = tk.Frame(root, bg='white', width=900, height=700)
    frame_right.pack(side='right', fill='both', expand=True)
    root.update()

    step('create frame_original & frame_modified')
    frame_original = tk.Frame(frame_right, bg='white', width=450, height=700)
    frame_original.pack(side='left', fill='both', expand=True)
    frame_modified = tk.Frame(frame_right, bg='white', width=450, height=700)
    frame_modified.pack(side='right', fill='both', expand=True)
    root.update()

    step('create labels')
    original_label = tk.Label(frame_original, text='Original Image', bg='white')
    original_label.pack()
    modified_label = tk.Label(frame_modified, text='Modified Image', bg='white')
    modified_label.pack()
    root.update()

    step('create controls in frame_left')
    b = ttk.Button(frame_left, text='Upload')
    b.pack()
    root.update()

    step('create canvas_right')
    canvas_right = tk.Canvas(frame_modified, bg='white', width=450, height=700)
    canvas_right.pack(fill='both', expand=True)
    root.update()

    step('enter mainloop')
    root.mainloop()
    print('Exited mainloop')
except Exception as e:
    print('EXCEPTION:', type(e).__name__, e)
    raise
