import os
import sys
import shutil
import glob
import subprocess
import threading
import uuid
import time
from collections import Counter
import tempfile
import io

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk, ImageOps

# Import pypdf for page size calculations
try:
    import pypdf
except ImportError:
    pypdf = None

# Colors for modern theme (will be updated dynamically based on system preference)
BG_COLOR = "#121214"
CARD_BG = "#1A1A1E"
DROP_ZONE_BG = "#222228"
BORDER_COLOR = "#2D2D35"
ACCENT_COLOR = "#6366F1"  # Indigo
ACCENT_HOVER = "#4F46E5"
TEXT_MAIN = "#F3F4F6"
TEXT_MUTED = "#9CA3AF"
SUCCESS_GREEN = "#10B981"
DANGER_RED = "#EF4444"
SEC_BTN_BG = "#4B5563"
SEC_BTN_HOVER = "#374151"
DROP_ZONE_HOVER = "#2A2A32"

class ScrollableFrame(tk.Frame):
    """A scrollable frame containing selected file cards."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, bg=kwargs.get("bg", BG_COLOR), highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg=kwargs.get("bg", BG_COLOR))

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mouse scroll when mouse enters
        self.canvas.bind('<Enter>', lambda _: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind('<Leave>', lambda _: self.canvas.unbind_all("<MouseWheel>"))
        
    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if sys.platform == "darwin":
            self.canvas.yview_scroll(-1 * int(event.delta), "units")
        else:
            self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

# App Version
APP_VERSION = "2.0.6"

class OptiFileApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"OptiFile Desktop v{APP_VERSION}")
        self.quality_var = tk.StringVar(value="Balanced")
        
        # Register macOS OpenDocument handler ASAP
        if sys.platform == "darwin":
            self.root.createcommand("::tk::mac::OpenDocument", self.handle_mac_open_document)
            
        # Initialize files pending queue and debouncing timer
        self.pending_files = []
        self.process_files_timer = None
        self.native_flow_active = False
        self.files_passed = False
        self.selected_files = []
        self.gs_bin = self.find_ghostscript()
        
        # Filter out macOS process serial number argument if present
        args = [arg for arg in sys.argv[1:] if not arg.startswith("-psn")]
        if args:
            self.add_files_to_queue(args)
            
        # We withdraw the window initially on macOS to avoid flash of wrong mode
        self.init_shown = False
        if sys.platform == "darwin":
            self.root.withdraw()
            # If no files passed in argv, set a default timer just in case no Apple Event arrives
            if not args:
                self.show_timer = self.root.after(150, self.show_initial_window)
        else:
            if args:
                self.process_queued_files()
            else:
                self.show_initial_window()
            
    def add_files_to_queue(self, files):
        for f in files:
            if f not in self.pending_files:
                self.pending_files.append(f)
        
        # Reset the debounce timer (50ms of inactivity required to process)
        if self.process_files_timer:
            self.root.after_cancel(self.process_files_timer)
        self.process_files_timer = self.root.after(50, self.process_queued_files)
        
    def process_queued_files(self):
        self.process_files_timer = None
        if not self.pending_files:
            return
            
        self.files_passed = True
        self.selected_files = []
        for path in self.pending_files:
            if os.path.exists(path):
                name = os.path.basename(path)
                size = os.path.getsize(path)
                ext = os.path.splitext(name)[1].lower()
                self.selected_files.append({
                    "path": path,
                    "name": name,
                    "size": size,
                    "type": "pdf" if ext == ".pdf" else "image"
                })
        self.pending_files = [] # Clear the queue
        
        if self.init_shown:
            # If we are already running the native headless flow, rerun it to process new files
            if self.native_flow_active or sys.platform == "darwin":
                self.root.after(10, self.run_macos_native_flow)
            else:
                self.root.geometry("340x480")
                self.center_window(340, 480)
                self.rebuild_ui()
        else:
            self.show_initial_window()
            
    def handle_mac_open_document(self, *args):
        # Gather all opened files
        files = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                files.extend(arg)
            else:
                files.append(arg)
        self.add_files_to_queue(files)
            
    def show_initial_window(self):
        if self.init_shown:
            return
        self.init_shown = True
        
        if hasattr(self, "show_timer") and self.show_timer:
            self.root.after_cancel(self.show_timer)
            self.show_timer = None
            
        # Check if we should run the native macOS flow
        if sys.platform == "darwin" and self.files_passed:
            self.root.after(10, self.run_macos_native_flow)
            return
            
        if self.files_passed:
            self.root.geometry("340x480")
            self.center_window(340, 480)
        else:
            self.root.geometry("850x680")
            self.center_window(850, 680)
            
        # Detect and apply theme based on system preference
        self.dark_mode_active = self.is_dark_mode()
        self.apply_theme()
        
        self.root.configure(bg=BG_COLOR)
        self.root.resizable(True, True)
        
        self.setup_styles()
        self.create_widgets()
        
        # Update UI initially
        self.update_file_list_ui()
        self.check_ghostscript_status()
        
        # Start periodic theme checker
        self.check_theme_periodically()
        
        # Setup keyboard shortcuts
        self.setup_keyboard_shortcuts()
        
        # Show window
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if sys.platform == "darwin":
            try:
                pid = os.getpid()
                subprocess.Popen([
                    "osascript", "-e",
                    f'tell application "System Events" to set frontmost of first process whose unix id is {pid} to true'
                ])
            except Exception:
                pass

    def setup_keyboard_shortcuts(self):
        self.root.bind("<Up>", self.navigate_buttons_up)
        self.root.bind("<Down>", self.navigate_buttons_down)
        self.root.bind("<Left>", self.navigate_presets_left)
        self.root.bind("<Right>", self.navigate_presets_right)
        self.root.bind("<Escape>", self.on_escape_pressed)
        self.bind_main_screen_keys()
        
        # Set active button index to 0 initially
        self.active_button_index = 0
        self.update_button_focus()

    def bind_main_screen_keys(self):
        self.root.bind("<Return>", lambda e: self.execute_active_button())
        self.root.bind("<Key-c>", lambda e: self.start_pdf_to_images())
        self.root.bind("<Key-C>", lambda e: self.start_pdf_to_images())
        self.root.bind("<Key-u>", lambda e: self.start_preflight())
        self.root.bind("<Key-U>", lambda e: self.start_preflight())
        self.root.bind("<Key-r>", lambda e: self.run_bulk_rename())
        self.root.bind("<Key-R>", lambda e: self.run_bulk_rename())

    def unbind_main_screen_keys(self):
        self.root.unbind("<Return>")
        self.root.unbind("<Key-c>")
        self.root.unbind("<Key-C>")
        self.root.unbind("<Key-u>")
        self.root.unbind("<Key-U>")
        self.root.unbind("<Key-r>")
        self.root.unbind("<Key-R>")

    def navigate_presets_left(self, event):
        if not hasattr(self, "quality_var"): return
        current = self.quality_var.get()
        if current == "Balanced":
            self.quality_var.set("High")
        elif current == "Low":
            self.quality_var.set("Balanced")

    def navigate_presets_right(self, event):
        if not hasattr(self, "quality_var"): return
        current = self.quality_var.get()
        if current == "High":
            self.quality_var.set("Balanced")
        elif current == "Balanced":
            self.quality_var.set("Low")

    def get_enabled_buttons(self):
        buttons = []
        for name in ["btn_compress", "btn_pdf_images", "btn_uniform", "btn_rename"]:
            if hasattr(self, name):
                btn = getattr(self, name)
                if btn and btn.winfo_exists() and btn.cget("state") != "disabled":
                    buttons.append(btn)
        return buttons

    def update_button_focus(self):
        enabled_btns = self.get_enabled_buttons()
        if not enabled_btns:
            return
            
        if not hasattr(self, "active_button_index"):
            self.active_button_index = 0
            
        if self.active_button_index >= len(enabled_btns):
            self.active_button_index = len(enabled_btns) - 1
        if self.active_button_index < 0:
            self.active_button_index = 0
            
        for idx, btn in enumerate(enabled_btns):
            orig_text = getattr(btn, "original_text", btn.cget("text"))
            clean_text = orig_text.lstrip("▶ ").lstrip("  ")
            
            if idx == self.active_button_index:
                btn.configure(text=f"▶ {clean_text}", bg=ACCENT_COLOR, fg="#FFFFFF")
            else:
                btn.configure(text=f"  {clean_text}", bg=SEC_BTN_BG, fg=TEXT_MAIN)

    def navigate_buttons_up(self, event):
        enabled_btns = self.get_enabled_buttons()
        if not enabled_btns: return
        self.active_button_index = (self.active_button_index - 1) % len(enabled_btns)
        self.update_button_focus()

    def navigate_buttons_down(self, event):
        enabled_btns = self.get_enabled_buttons()
        if not enabled_btns: return
        self.active_button_index = (self.active_button_index + 1) % len(enabled_btns)
        self.update_button_focus()

    def execute_active_button(self):
        enabled_btns = self.get_enabled_buttons()
        if not enabled_btns: return
        
        if self.active_button_index >= len(enabled_btns):
            self.active_button_index = 0
            
        active_btn = enabled_btns[self.active_button_index]
        active_btn.invoke()

    def on_escape_pressed(self, event):
        if hasattr(self, "results_frame") and self.results_frame.winfo_ismapped():
            if hasattr(self, "current_results") and self.current_results:
                self.discard_temps(self.current_results)
            else:
                self.close_results_panel()
        else:
            self.root.destroy()

    def run_applescript_list(self, title, prompt, items, default_item=None, ok_button="Select", cancel_button="Cancel"):
        items_str = ", ".join(f'"{item}"' for item in items)
        default_str = f' default items {{"{default_item}"}}' if default_item else ''
        script = f'''
        tell application "System Events"
            activate
            choose from list {{{items_str}}} with title "{title}" with prompt "{prompt}"{default_str} OK button name "{ok_button}" Cancel button name "{cancel_button}"
        end tell
        '''
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            out = proc.stdout.strip()
            if out == "false" or not out:
                return None
            return out
        except Exception:
            return None

    def run_applescript_dialog(self, text, title="OptiFile", buttons=["OK"], default_button="OK", icon="note"):
        buttons_str = ", ".join(f'"{b}"' for b in buttons)
        
        # Try to dynamically resolve custom icon from bundled app resources
        icon_str = icon
        if getattr(sys, 'frozen', False):
            try:
                # sys.executable is at /Applications/OptiFile.app/Contents/MacOS/OptiFile
                contents_dir = os.path.dirname(os.path.dirname(sys.executable))
                resources_dir = os.path.join(contents_dir, "Resources")
                if os.path.exists(resources_dir):
                    for f in os.listdir(resources_dir):
                        if f.endswith(".icns"):
                            icon_str = f'file (POSIX file "{os.path.join(resources_dir, f)}")'
                            break
            except Exception:
                pass
                
        script = f'''
        tell application "System Events"
            activate
            display dialog "{text}" with title "{title}" buttons {{{buttons_str}}} default button "{default_button}" with icon {icon_str}
        end tell
        '''
        try:
            proc = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
            out = proc.stdout.strip()
            if "button returned:" in out:
                return out.split("button returned:")[1].strip()
            return None
        except Exception:
            return None

    def run_macos_native_flow(self):
        self.native_flow_active = True
        if not self.selected_files:
            self.root.destroy()
            return
            
        has_pdf = any(f["type"] == "pdf" for f in self.selected_files)
        has_image = any(f["type"] == "image" for f in self.selected_files)
        
        title = "OptiFile"
        if has_pdf and not has_image:
            options = ["Compress PDF", "Convert PDF to Images", "Make Page Sizes Uniform (Preflight)"]
            default_opt = "Compress PDF"
            prompt = "Choose action for selected PDF(s):"
        elif not has_pdf and has_image:
            options = ["Compress Images", "Bulk Rename - (1) (2) (3)"]
            default_opt = "Compress Images"
            prompt = "Choose action for selected Image(s):"
        else:
            options = ["Compress All Files", "Bulk Rename - (1) (2) (3)"]
            default_opt = "Compress All Files"
            prompt = "Choose action for selected file(s):"
            
        choice = self.run_applescript_list(title, prompt, options, default_item=default_opt)
        if not choice:
            self.root.destroy()
            return
            
        if choice in ["Compress PDF", "Compress Images", "Compress All Files"]:
            quality_options = [
                "High Quality (300 DPI / 1080p)",
                "Balanced (Recommended - 150 DPI / 720p)",
                "Low Quality (72 DPI / 480p)"
            ]
            q_choice = self.run_applescript_list(title, "Choose PDF & Image compression quality:", quality_options, default_item="Balanced (Recommended - 150 DPI / 720p)")
            if not q_choice:
                self.root.destroy()
                return
                
            if q_choice.startswith("High"):
                self.quality_var.set("High")
            elif q_choice.startswith("Low"):
                self.quality_var.set("Low")
            else:
                self.quality_var.set("Balanced")
                
            self.run_macos_native_compress()
            
        elif choice == "Convert PDF to Images":
            fmt_options = ["JPG (Joint Photographic Group)", "PNG (Portable Network Graphics)"]
            fmt_choice = self.run_applescript_list(title, "Choose output image format:", fmt_options, default_item="JPG (Joint Photographic Group)")
            if not fmt_choice:
                self.root.destroy()
                return
                
            fmt = "png" if "PNG" in fmt_choice else "jpg"
            self.run_macos_native_convert(fmt)
            
        elif choice == "Make Page Sizes Uniform (Preflight)":
            self.run_macos_native_preflight()
            
        elif choice == "Bulk Rename - (1) (2) (3)":
            self.run_macos_native_rename()

    def run_macos_native_compress(self):
        subprocess.run(["osascript", "-e", 'display notification "Compressing files..." with title "OptiFile"'])
        
        preset = self.quality_var.get()
        if preset == "High":
            gs_resol = "300"
            gs_qfactor = "0.3"
            img_max_dim = 1600
            img_quality = 85
        elif preset == "Low":
            gs_resol = "72"
            gs_qfactor = "1.1"
            img_max_dim = 800
            img_quality = 55
        else:  # Balanced (Recommended)
            gs_resol = "150"
            gs_qfactor = "0.7"
            img_max_dim = 1280
            img_quality = 78
            
        results = []
        skipped_optimized = 0
        failed_count = 0
        
        for file_info in self.selected_files:
            try:
                path = file_info["path"]
                name = file_info["name"]
                orig_size = file_info["size"]
                ext = os.path.splitext(name)[1].lower()
                base = os.path.splitext(name)[0]
                
                temp_out = os.path.join(tempfile.gettempdir(), f"{base}_temp_compressed{ext}")
                
                success = False
                if file_info["type"] == "pdf":
                    # Scan PDF to see if it is image-heavy
                    is_image_heavy = False
                    if pypdf is not None:
                        try:
                            reader = pypdf.PdfReader(path)
                            total_pages = len(reader.pages)
                            has_images = sum(1 for p in reader.pages if len(p.images) > 0)
                            if total_pages > 0 and (has_images / total_pages) >= 0.7:
                                is_image_heavy = True
                        except Exception:
                            pass
                            
                    # Method 1: Try Ghostscript (only if not image-heavy)
                    gs_worked = False
                    if self.gs_bin and not is_image_heavy:
                        cmd = [
                            self.gs_bin, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                            "-dNOPAUSE", "-dQUIET", "-dBATCH",
                            "-dDownsampleColorImages=true", f"-dColorImageResolution={gs_resol}",
                            "-dColorImageDownsampleThreshold=1.0", "-dColorImageDownsampleType=/Bicubic",
                            "-dAutoFilterColorImages=false", "-dColorImageFilter=/DCTEncode",
                            f"-sOutputFile={temp_out}",
                            "-c", f"<< /PassThroughJPEGImages false /ColorImageDict << /QFactor {gs_qfactor} /Blend 1 >> >> setdistillerparams",
                            "-f", path
                        ]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                            if os.path.getsize(temp_out) < orig_size:
                                gs_worked = True
                                success = True
                            else:
                                os.remove(temp_out)
                                
                    # Method 2: If Ghostscript failed, bloated, or skipped (image-heavy), try pypdf+Pillow image resizing
                    if not gs_worked and pypdf is not None:
                        try:
                            reader = pypdf.PdfReader(path)
                            writer = pypdf.PdfWriter()
                            for page in reader.pages:
                                writer.add_page(page)
                            
                            img_compressed = False
                            for page in writer.pages:
                                for img_obj in page.images:
                                    try:
                                        # Pre-check dimensions without decoding to save CPU & memory
                                        obj = img_obj.indirect_reference.get_object()
                                        w = obj.get("/Width", 0)
                                        h = obj.get("/Height", 0)
                                        
                                        if w > img_max_dim or h > img_max_dim:
                                            pil_img = img_obj.image
                                            ratio = min(img_max_dim / w, img_max_dim / h)
                                            new_w, new_h = int(w * ratio), int(h * ratio)
                                            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                                            
                                            # Replace directly without duplicate pre-compression checks
                                            img_obj.replace(pil_img, quality=img_quality)
                                            img_compressed = True
                                    except Exception:
                                        pass
                            
                            if img_compressed:
                                with open(temp_out, "wb") as f:
                                    writer.write(f)
                                if os.path.exists(temp_out) and os.path.getsize(temp_out) < orig_size:
                                    success = True
                                elif os.path.exists(temp_out):
                                    os.remove(temp_out)
                        except Exception as e:
                            print(f"pypdf fallback failed: {e}")
                            if os.path.exists(temp_out):
                                os.remove(temp_out)
                else:
                    img = Image.open(path)
                    img = ImageOps.exif_transpose(img)
                    img.thumbnail((img_max_dim, img_max_dim), Image.Resampling.LANCZOS)
                    
                    if ext in [".jpg", ".jpeg"]:
                        img.convert("RGB").save(temp_out, "JPEG", quality=img_quality, optimize=True)
                        success = True
                    elif ext == ".png":
                        img.save(temp_out, "PNG", optimize=True)
                        success = True
                    elif ext == ".heic":
                        img.convert("RGB").save(temp_out, "JPEG", quality=img_quality, optimize=True)
                        success = True
                    else:
                        img.save(temp_out, optimize=True)
                        success = True
                        
                if success:
                    new_size = os.path.getsize(temp_out)
                    if new_size >= orig_size:
                        if os.path.exists(temp_out):
                            os.remove(temp_out)
                        skipped_optimized += 1
                    else:
                        results.append({
                            "name": name,
                            "original": path,
                            "temp_out": temp_out,
                            "final_out": path,
                            "orig_size": orig_size,
                            "new_size": new_size
                        })
                else:
                    skipped_optimized += 1
            except Exception as e:
                print(f"Error compressing: {e}")
                failed_count += 1
                
        if not results:
            if skipped_optimized > 0 and failed_count == 0:
                self.run_applescript_dialog("All selected files are already fully optimized!", buttons=["OK"], icon="note")
            elif skipped_optimized > 0 and failed_count > 0:
                self.run_applescript_dialog("Some files were already optimized, and others failed to compress.", buttons=["OK"], icon="warning")
            else:
                self.run_applescript_dialog("Compression failed. Please ensure Ghostscript is installed and files are valid.", buttons=["OK"], icon="stop")
            self.root.destroy()
            return
            
        total_orig = sum(r["orig_size"] for r in results)
        total_new = sum(r["new_size"] for r in results)
        saved_bytes = total_orig - total_new
        saved_percent = (saved_bytes / total_orig) * 100 if total_orig > 0 else 0
        
        saved_label = f"Saved {saved_percent:.1f}% ({self.format_size(saved_bytes)}) of disk space!"
        action = self.run_applescript_dialog(
            f"OptiFile Compression Complete!\n\n{saved_label}\n\nOriginal: {self.format_size(total_orig)}  |  New: {self.format_size(total_new)}",
            buttons=["Done", "Keep Copies", "Replace Originals"],
            default_button="Replace Originals"
        )
        
        if action == "Replace Originals":
            self.apply_replacements(results)
        elif action == "Keep Copies":
            self.keep_copies(results)
        else:
            self.discard_temps(results)
            
        self.root.destroy()

    def run_macos_native_convert(self, format_ext):
        subprocess.run(["osascript", "-e", 'display notification "Converting PDF to images..." with title "OptiFile"'])
        
        out_dirs = []
        for file_info in self.selected_files:
            if file_info["type"] != "pdf": continue
            path = file_info["path"]
            name = file_info["name"]
            dir_name = os.path.dirname(path)
            base_name = os.path.splitext(name)[0]
            
            out_dir = os.path.join(dir_name, f"{base_name}_images")
            counter = 1
            while os.path.exists(out_dir):
                out_dir = os.path.join(dir_name, f"{base_name}_images_{counter}")
                counter += 1
            os.makedirs(out_dir, exist_ok=True)
            out_dirs.append(out_dir)
            
            if self.gs_bin:
                device = "png16m" if format_ext == "png" else "jpeg"
                cmd = [
                    self.gs_bin, f"-sDEVICE={device}", "-r150", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                    f"-sOutputFile={out_dir}/(%d).{format_ext}", path
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
        subprocess.run(["osascript", "-e", 'display notification "Successfully converted PDF pages to images!" with title "OptiFile"'])
        if out_dirs:
            self.open_path_in_file_manager(os.path.dirname(out_dirs[0]))
            
        self.root.destroy()

    def run_macos_native_preflight(self):
        subprocess.run(["osascript", "-e", 'display notification "Standardizing page sizes..." with title "OptiFile"'])
        
        pdf_files = [f for f in self.selected_files if f["type"] == "pdf"]
        if not pdf_files:
            self.root.destroy()
            return
            
        if not pypdf:
            self.run_applescript_dialog("The 'pypdf' package is required for page size analysis but was not found.", buttons=["OK"], icon="stop")
            self.root.destroy()
            return
            
        results = []
        for file_info in pdf_files:
            try:
                path = file_info["path"]
                name = file_info["name"]
                
                reader = pypdf.PdfReader(path)
                sizes = [(round(float(p.mediabox.width), 2), round(float(p.mediabox.height), 2)) for p in reader.pages]
                if not sizes:
                    continue
                    
                most_common = Counter(sizes).most_common(1)[0][0]
                width, height = most_common
                label = f"{width}x{height} pt"
                
                base = os.path.splitext(name)[0]
                temp_out = os.path.join(tempfile.gettempdir(), f"{base}_temp_uniform.pdf")
                
                if self.gs_bin:
                    cmd = [
                        self.gs_bin, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                        f"-dDEVICEWIDTHPOINTS={width}", f"-dDEVICEHEIGHTPOINTS={height}", "-dFIXEDMEDIA", "-dPDFFitPage",
                        f"-sOutputFile={temp_out}", path
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    if os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                        results.append({
                            "original": path,
                            "temp_out": temp_out,
                            "final_out": path,
                            "label": label
                        })
            except Exception as e:
                print(f"Error in preflight: {e}")
                
        if not results:
            self.run_applescript_dialog("Standardization failed or could not be completed.", buttons=["OK"], icon="stop")
            self.root.destroy()
            return
            
        action = self.run_applescript_dialog(
            f"OptiFile Preflight Complete!\n\nStandardized page dimensions for {len(results)} PDF(s).",
            buttons=["Done", "Keep Copies", "Replace Originals"],
            default_button="Replace Originals"
        )
        
        if action == "Replace Originals":
            self.apply_replacements(results)
        elif action == "Keep Copies":
            for item in results:
                try:
                    temp = item["temp_out"]
                    dest = os.path.join(os.path.dirname(item["original"]), f"uniform_{os.path.basename(item['original'])}")
                    if os.path.exists(dest):
                        os.remove(dest)
                    shutil.move(temp, dest)
                except Exception:
                    pass
            if results:
                self.open_path_in_file_manager(os.path.dirname(results[0]["original"]))
        else:
            self.discard_temps(results)
            
        self.root.destroy()

    def run_macos_native_rename(self):
        file_paths = [f["path"] for f in self.selected_files]
        
        folders = set(os.path.dirname(p) for p in file_paths)
        if len(folders) > 1:
            action = self.run_applescript_dialog(
                "Selected files are in different folders. Sequentially renaming them will name files as (1), (2), etc. inside each folder independently. Do you want to proceed?",
                buttons=["Cancel", "Proceed"],
                default_button="Proceed"
            )
            if action != "Proceed":
                self.root.destroy()
                return
                
        from collections import defaultdict
        dir_groups = defaultdict(list)
        for path in file_paths:
            dir_groups[os.path.dirname(path)].append(path)
            
        new_paths = []
        for dir_path, paths in dir_groups.items():
            temp_files = []
            for idx, orig_path in enumerate(paths):
                ext = os.path.splitext(orig_path)[1].lower()
                temp_path = os.path.join(dir_path, f"temp_optifile_{uuid.uuid4().hex}_{idx}{ext}")
                try:
                    os.rename(orig_path, temp_path)
                    temp_files.append((temp_path, ext))
                except Exception:
                    pass
            pad_width = len(str(len(temp_files)))
            for idx, (temp_path, ext) in enumerate(temp_files):
                num_str = str(idx + 1).zfill(pad_width)
                final_path = os.path.join(dir_path, f"({num_str}){ext}")
                try:
                    if os.path.exists(final_path):
                        os.remove(final_path)
                    os.rename(temp_path, final_path)
                    new_paths.append(final_path)
                except Exception:
                    pass
                    
        subprocess.run(["osascript", "-e", f'display notification "Successfully renamed {len(new_paths)} files sequentially." with title "OptiFile"'])
        if new_paths:
            dir_to_open = os.path.dirname(new_paths[0])
            self.refresh_macos_finder(dir_to_open)
            self.open_path_in_file_manager(dir_to_open)
            
        self.root.destroy()

    def is_dark_mode(self):
        if sys.platform == "darwin":
            try:
                proc = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True, text=True
                )
                return "Dark" in proc.stdout
            except Exception:
                return False
        elif sys.platform == "win32":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
            except Exception:
                return False
        return False

    def apply_theme(self):
        global BG_COLOR, CARD_BG, DROP_ZONE_BG, BORDER_COLOR, ACCENT_COLOR, ACCENT_HOVER, TEXT_MAIN, TEXT_MUTED, SUCCESS_GREEN, DANGER_RED, SEC_BTN_BG, SEC_BTN_HOVER, DROP_ZONE_HOVER
        if self.is_dark_mode():
            BG_COLOR = "#121214"
            CARD_BG = "#1A1A1E"
            DROP_ZONE_BG = "#222228"
            BORDER_COLOR = "#2D2D35"
            ACCENT_COLOR = "#6366F1"
            ACCENT_HOVER = "#4F46E5"
            TEXT_MAIN = "#F3F4F6"
            TEXT_MUTED = "#9CA3AF"
            SUCCESS_GREEN = "#10B981"
            DANGER_RED = "#EF4444"
            SEC_BTN_BG = "#4B5563"
            SEC_BTN_HOVER = "#374151"
            DROP_ZONE_HOVER = "#2A2A32"
        else:
            BG_COLOR = "#F3F4F6"
            CARD_BG = "#FFFFFF"
            DROP_ZONE_BG = "#E5E7EB"
            BORDER_COLOR = "#D1D5DB"
            ACCENT_COLOR = "#4F46E5"
            ACCENT_HOVER = "#3730A3"
            TEXT_MAIN = "#111827"
            TEXT_MUTED = "#4B5563"
            SUCCESS_GREEN = "#059669"
            DANGER_RED = "#DC2626"
            SEC_BTN_BG = "#E5E7EB"
            SEC_BTN_HOVER = "#D1D5DB"
            DROP_ZONE_HOVER = "#DCDFE4"

    def check_theme_periodically(self):
        # Only change theme if no background task is running
        if not getattr(self, "task_running", False):
            current_mode = self.is_dark_mode()
            if current_mode != self.dark_mode_active:
                self.dark_mode_active = current_mode
                self.apply_theme()
                self.rebuild_ui()
        self.root.after(2000, self.check_theme_periodically)

    def rebuild_ui(self):
        # Preserve selected files list and quality preset value
        preset = self.quality_var.get() if hasattr(self, "quality_var") else "Balanced"
        files_backup = list(self.selected_files)
        
        # Destroy all widgets in root
        for widget in self.root.winfo_children():
            widget.destroy()
            
        # Re-initialize styles and widgets
        self.setup_styles()
        self.create_widgets()
        
        # Restore state
        self.selected_files = files_backup
        self.quality_var.set(preset)
        
        # Re-bind keys and update focus
        self.setup_keyboard_shortcuts()
        
        # Bring window to front
        self.root.lift()
        self.root.focus_force()
        if sys.platform == "darwin":
            try:
                pid = os.getpid()
                subprocess.Popen([
                    "osascript", "-e",
                    f'tell application "System Events" to set frontmost of first process whose unix id is {pid} to true'
                ])
            except Exception:
                pass
        self.root.configure(bg=BG_COLOR)
        if self.files_passed:
            self.root.geometry("340x480")
        else:
            self.root.geometry("850x680")
            
        # Refresh widgets
        self.update_file_list_ui()
        self.check_ghostscript_status()

    def center_window(self, width, height):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('default')
        
        # Configure vertical scrollbar colors
        style.configure("Vertical.TScrollbar", 
                        gripcount=0,
                        background=BORDER_COLOR, 
                        troughcolor=BG_COLOR, 
                        bordercolor=BG_COLOR, 
                        lightcolor=BG_COLOR, 
                        darkcolor=BG_COLOR)
        
        # Progressbar styling
        style.configure("Custom.Horizontal.TProgressbar",
                        thickness=8,
                        troughcolor=CARD_BG,
                        background=ACCENT_COLOR,
                        bordercolor=CARD_BG,
                        lightcolor=ACCENT_COLOR,
                        darkcolor=ACCENT_COLOR)

    def find_ghostscript(self):
        # Check system path
        gs_bin = shutil.which("gs")
        if gs_bin:
            return gs_bin
        
        gs_win = shutil.which("gswin64c")
        if gs_win:
            return gs_win
            
        # Check common Windows paths
        if sys.platform == "win32":
            paths = [
                r"C:\Program Files\gs\gs*\bin\gswin64c.exe",
                r"C:\Program Files (x86)\gs\gs*\bin\gswin32c.exe"
            ]
            for path_pattern in paths:
                matches = glob.glob(path_pattern)
                if matches:
                    return sorted(matches)[-1]
                    
        # Check macOS standard brew paths
        if sys.platform == "darwin":
            brew_paths = [
                "/opt/homebrew/bin/gs",
                "/usr/local/bin/gs"
            ]
            for p in brew_paths:
                if os.path.exists(p):
                    return p
                    
        return None

    def check_ghostscript_status(self):
        if not self.gs_bin:
            if hasattr(self, "gs_warning_label") and self.gs_warning_label.winfo_exists():
                self.gs_warning_label.pack(side="right", padx=10)
            self.btn_uniform.configure(state="disabled")
            self.btn_pdf_images.configure(state="disabled")
            # We still allow image compression, but warn PDF compression will fail/fallback
        else:
            if hasattr(self, "gs_warning_label") and self.gs_warning_label.winfo_exists():
                self.gs_warning_label.pack_forget()

    def create_widgets(self):
        # --- Main Layout Frames ---
        if not self.files_passed:
            self.header_frame = tk.Frame(self.root, bg=CARD_BG, height=60)
            self.header_frame.pack(side="top", fill="x")
            self.header_frame.pack_propagate(False)
            
            # --- Header Widgets ---
            self.lbl_logo = tk.Label(self.header_frame, text="⚡ OptiFile Desktop", font=("Helvetica Neue", 16, "bold"), fg=TEXT_MAIN, bg=CARD_BG)
            self.lbl_logo.pack(side="left", padx=20, pady=15)
            
            self.gs_warning_label = tk.Label(self.header_frame, text="⚠️ Ghostscript Missing (PDF features disabled)", font=("Helvetica Neue", 10, "bold"), fg="#F59E0B", bg=CARD_BG, cursor="hand2")
            self.gs_warning_label.bind("<Button-1>", lambda e: self.open_ghostscript_download())
        
        # Content body
        self.main_container = tk.Frame(self.root, bg=BG_COLOR)
        self.main_container.pack(side="top", fill="both", expand=True, padx=15 if self.files_passed else 20, pady=8 if self.files_passed else 15)
        
        # Right Panel & Left Panel depending on compact mode
        if self.files_passed:
            self.right_panel = tk.Frame(self.main_container, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
            self.right_panel.pack(side="left", fill="both", expand=True)
            
            # File count summary at top of right panel
            file_summary_lbl = tk.Label(self.right_panel, text=f"📄 Selected: {len(self.selected_files)} file(s)", 
                                         font=("Helvetica Neue", 11, "bold"), fg=TEXT_MAIN, bg=CARD_BG)
            file_summary_lbl.pack(anchor="w", padx=15, pady=(10, 0))
        else:
            # Left Panel: File list and Selection
            self.left_panel = tk.Frame(self.main_container, bg=BG_COLOR)
            self.left_panel.pack(side="left", fill="both", expand=True)
            
            # Right Panel: Actions and Options
            self.right_panel = tk.Frame(self.main_container, bg=CARD_BG, width=280, highlightbackground=BORDER_COLOR, highlightthickness=1)
            self.right_panel.pack(side="right", fill="both", expand=False, padx=(20, 0))
            self.right_panel.pack_propagate(False)
        
        # Bottom status bar
        self.status_frame = tk.Frame(self.root, bg=CARD_BG, height=30 if self.files_passed else 35)
        self.status_frame.pack(side="bottom", fill="x")
        self.status_frame.pack_propagate(False)

        # --- Left Panel Widgets ---
        if not self.files_passed:
            # 1. Selection drop-zone styling
            self.selection_canvas = tk.Canvas(self.left_panel, bg=DROP_ZONE_BG, height=130, highlightthickness=0)
            self.selection_canvas.pack(side="top", fill="x", pady=(0, 15))
            self.selection_canvas.bind("<Button-1>", lambda e: self.browse_files())
            self.selection_canvas.bind("<Enter>", lambda e: self.selection_canvas.configure(bg=DROP_ZONE_HOVER))
            self.selection_canvas.bind("<Leave>", lambda e: self.selection_canvas.configure(bg=DROP_ZONE_BG))
            
            self.draw_dashed_border()
            
            # Add labels inside drop zone
            self.selection_canvas.create_text(400, 50, text="📄 Select Files to Optimize", font=("Helvetica Neue", 13, "bold"), fill=TEXT_MAIN, tags="txt")
            self.selection_canvas.create_text(400, 80, text="Supports PDFs and Images (JPG, PNG, HEIC, TIFF, BMP)", font=("Helvetica Neue", 10), fill=TEXT_MUTED, tags="txt")
            self.selection_canvas.bind("<Configure>", self.on_canvas_resize)
            
            # 2. Selected Files Header
            self.list_header = tk.Frame(self.left_panel, bg=BG_COLOR)
            self.list_header.pack(side="top", fill="x")
            
            self.lbl_selected_title = tk.Label(self.list_header, text="Selected Files", font=("Helvetica Neue", 12, "bold"), fg=TEXT_MAIN, bg=BG_COLOR)
            self.lbl_selected_title.pack(side="left", pady=(5, 5))
            
            self.btn_clear_all = tk.Button(self.list_header, text="Clear All", font=("Helvetica Neue", 10), bg=BG_COLOR, fg=DANGER_RED, activebackground=BG_COLOR, activeforeground=DANGER_RED, bd=0, cursor="hand2", command=self.clear_files)
            self.btn_clear_all.pack(side="right", pady=(5, 5))
            
            # 3. Selected Files list (Scrollable Frame)
            self.files_scroll_frame = ScrollableFrame(self.left_panel, bg=BG_COLOR)
            self.files_scroll_frame.pack(side="top", fill="both", expand=True)

        # --- Right Panel (Actions) Widgets ---
        # Title
        tk.Label(self.right_panel, text="COMPRESSION PRESET", font=("Helvetica Neue", 10, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(anchor="w", padx=15, pady=(10 if self.files_passed else 20, 3 if self.files_passed else 5))
        
        # Quality presets variables
        if not hasattr(self, "quality_var"):
            self.quality_var = tk.StringVar(value="Balanced")
        
        presets = [
            ("High Quality", "High", "300 DPI / 1080p"),
            ("Balanced", "Balanced", "150 DPI / 720p (Recommended)"),
            ("Low Quality", "Low", "72 DPI / 480p")
        ]
        
        for text, val, desc in presets:
            frame = tk.Frame(self.right_panel, bg=CARD_BG)
            frame.pack(fill="x", padx=15, pady=2 if self.files_passed else 5)
            
            rb = tk.Radiobutton(frame, text=text, variable=self.quality_var, value=val, 
                                font=("Helvetica Neue", 11, "bold"), fg=TEXT_MAIN, bg=CARD_BG,
                                selectcolor=CARD_BG, activebackground=CARD_BG, activeforeground=TEXT_MAIN,
                                highlightthickness=0, cursor="hand2")
            rb.pack(anchor="w")
            
            lbl_desc = tk.Label(frame, text=desc, font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=CARD_BG)
            lbl_desc.pack(anchor="w", padx=24)
            
        # Divider line
        div = tk.Frame(self.right_panel, bg=BORDER_COLOR, height=1)
        div.pack(fill="x", padx=15, pady=10 if self.files_passed else 20)
        
        tk.Label(self.right_panel, text="OPERATIONS", font=("Helvetica Neue", 10, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(anchor="w", padx=15, pady=(0, 5 if self.files_passed else 10))
        
        # Actions Buttons
        self.btn_compress = self.create_styled_button("🗜️ Compress Selected", ACCENT_COLOR, self.start_compression, fg_color="#FFFFFF")
        self.btn_compress.pack(fill="x", padx=15, pady=3 if self.files_passed else 6)
        
        self.btn_pdf_images = self.create_styled_button("🖼️ Convert PDF to Images", SEC_BTN_BG, self.start_pdf_to_images)
        self.btn_pdf_images.pack(fill="x", padx=15, pady=3 if self.files_passed else 6)
        
        self.btn_uniform = self.create_styled_button("📐 Make Page Sizes Uniform", SEC_BTN_BG, self.start_preflight)
        self.btn_uniform.pack(fill="x", padx=15, pady=3 if self.files_passed else 6)
        
        self.btn_rename = self.create_styled_button("🏷️ Bulk Rename (1), (2), (3)...", SEC_BTN_BG, self.run_bulk_rename)
        self.btn_rename.pack(fill="x", padx=15, pady=3 if self.files_passed else 6)

        # --- Status Bar Widgets ---
        self.lbl_status = tk.Label(self.status_frame, text="Ready", font=("Helvetica Neue", 10), fg=TEXT_MUTED, bg=CARD_BG)
        self.lbl_status.pack(side="left", padx=15, pady=5 if self.files_passed else 8)
        
        self.progress_bar = ttk.Progressbar(self.status_frame, style="Custom.Horizontal.TProgressbar", orient="horizontal", mode="determinate")
        self.progress_bar.pack(side="right", padx=15, pady=8 if self.files_passed else 12, fill="x", expand=False)
        self.progress_bar.pack_forget() # Hide initially

        # --- Dynamic Results Overlay Frame ---
        self.results_frame = tk.Frame(self.root, bg=BG_COLOR)
        # It will be placed on top of main_container when showing results

    def create_styled_button(self, text, color, command, fg_color=None):
        fg = fg_color if fg_color else TEXT_MAIN
        clean_text = text.lstrip("▶ ").lstrip("  ")
        display_text = f"  {clean_text}"
        
        btn = tk.Button(self.right_panel, text=display_text, font=("Helvetica Neue", 11, "bold"),
                        bg=color, fg=fg, activebackground=color, activeforeground=fg,
                        bd=0, relief="flat", padx=15, pady=6 if self.files_passed else 10, cursor="hand2", command=command)
        
        btn.original_text = display_text
        btn.default_bg = color
        
        # Subtle hover animations
        def on_enter(e):
            if btn['state'] != 'disabled':
                enabled_btns = self.get_enabled_buttons()
                is_active = btn in enabled_btns and enabled_btns.index(btn) == self.active_button_index
                current_color = ACCENT_COLOR if is_active else color
                
                if current_color == SEC_BTN_BG:
                    btn.configure(bg=SEC_BTN_HOVER)
                elif current_color == ACCENT_COLOR:
                    btn.configure(bg=ACCENT_HOVER)
                else:
                    btn.configure(bg=self.darken_color(current_color, 15))
                    
        def on_leave(e):
            if btn['state'] != 'disabled':
                enabled_btns = self.get_enabled_buttons()
                is_active = btn in enabled_btns and enabled_btns.index(btn) == self.active_button_index
                if is_active:
                    btn.configure(bg=ACCENT_COLOR)
                else:
                    btn.configure(bg=color)
                
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def create_completion_button(self, parent, text, color, command, is_primary=False):
        fg = "#FFFFFF" if (is_primary or color in [SUCCESS_GREEN, DANGER_RED, ACCENT_COLOR]) else TEXT_MAIN
        clean_text = text.lstrip("▶ ").lstrip("  ")
        display_text = f"  {clean_text}"
        
        btn = tk.Button(parent, text=display_text, font=("Helvetica Neue", 10 if self.files_passed else 11, "bold" if is_primary else "normal"),
                        bg=color, fg=fg, activebackground=color, activeforeground=fg,
                        bd=0, relief="flat", padx=15 if self.files_passed else 25, pady=7 if self.files_passed else 10, cursor="hand2", command=command)
        
        btn.original_text = display_text
        btn.default_bg = color
        
        # Subtle hover animations
        def on_enter(e):
            if btn['state'] != 'disabled':
                enabled_completion_btns = getattr(self, "active_completion_buttons", [])
                is_active = btn in enabled_completion_btns and enabled_completion_btns.index(btn) == self.active_completion_index
                current_color = ACCENT_COLOR if is_active and color == ACCENT_COLOR else color
                
                if current_color == SEC_BTN_BG:
                    btn.configure(bg=SEC_BTN_HOVER)
                elif current_color == ACCENT_COLOR:
                    btn.configure(bg=ACCENT_HOVER)
                else:
                    btn.configure(bg=self.darken_color(current_color, 15))
                    
        def on_leave(e):
            if btn['state'] != 'disabled':
                enabled_completion_btns = getattr(self, "active_completion_buttons", [])
                is_active = btn in enabled_completion_btns and enabled_completion_btns.index(btn) == self.active_completion_index
                if is_active:
                    btn.configure(bg=self.darken_color(color, 15) if color not in [SEC_BTN_BG, ACCENT_COLOR] else (ACCENT_HOVER if color == ACCENT_COLOR else SEC_BTN_HOVER))
                else:
                    btn.configure(bg=color)
                    
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def update_completion_button_focus(self):
        enabled_btns = getattr(self, "active_completion_buttons", [])
        if not enabled_btns:
            return
            
        if not hasattr(self, "active_completion_index"):
            self.active_completion_index = 0
            
        if self.active_completion_index >= len(enabled_btns):
            self.active_completion_index = len(enabled_btns) - 1
        if self.active_completion_index < 0:
            self.active_completion_index = 0
            
        for idx, btn in enumerate(enabled_btns):
            orig_text = getattr(btn, "original_text", btn.cget("text"))
            clean_text = orig_text.lstrip("▶ ").lstrip("  ")
            
            if idx == self.active_completion_index:
                hover_bg = self.darken_color(btn.default_bg, 15) if btn.default_bg not in [SEC_BTN_BG, ACCENT_COLOR] else (ACCENT_HOVER if btn.default_bg == ACCENT_COLOR else SEC_BTN_HOVER)
                btn.configure(text=f"▶ {clean_text}", bg=hover_bg, fg="#FFFFFF")
            else:
                btn.configure(text=f"  {clean_text}", bg=btn.default_bg)

    def navigate_completion_left(self, event):
        enabled_btns = getattr(self, "active_completion_buttons", [])
        if not enabled_btns: return
        self.active_completion_index = (self.active_completion_index - 1) % len(enabled_btns)
        self.update_completion_button_focus()

    def navigate_completion_right(self, event):
        enabled_btns = getattr(self, "active_completion_buttons", [])
        if not enabled_btns: return
        self.active_completion_index = (self.active_completion_index + 1) % len(enabled_btns)
        self.update_completion_button_focus()

    def execute_active_completion_button(self):
        enabled_btns = getattr(self, "active_completion_buttons", [])
        if not enabled_btns: return
        if self.active_completion_index >= len(enabled_btns):
            self.active_completion_index = 0
        active_btn = enabled_btns[self.active_completion_index]
        active_btn.invoke()

    def handle_completion_escape(self, results, folders, mode):
        if mode in ["preflight", "compress"] and results:
            self.discard_temps(results)
        else:
            self.close_results_panel()

    def bind_completion_screen_keys(self, results, folders, mode):
        self.unbind_main_screen_keys()
        self.root.unbind("<Left>")
        self.root.unbind("<Right>")
        
        self.root.bind("<Left>", self.navigate_completion_left)
        self.root.bind("<Right>", self.navigate_completion_right)
        self.root.bind("<Up>", self.navigate_completion_left)
        self.root.bind("<Down>", self.navigate_completion_right)
        self.root.bind("<Return>", lambda e: self.execute_active_completion_button())
        self.root.bind("<Escape>", lambda e: self.handle_completion_escape(results, folders, mode))

    def restore_main_screen_keys(self):
        self.root.unbind("<Left>")
        self.root.unbind("<Right>")
        
        self.root.bind("<Up>", self.navigate_buttons_up)
        self.root.bind("<Down>", self.navigate_buttons_down)
        self.root.bind("<Left>", self.navigate_presets_left)
        self.root.bind("<Right>", self.navigate_presets_right)
        self.root.bind("<Escape>", self.on_escape_pressed)
        self.bind_main_screen_keys()
        self.update_button_focus()

    def darken_color(self, hex_color, percent):
        """Generates a darker version of a hex color for hover effect."""
        try:
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            darkened = tuple(max(0, int(c * (100 - percent) / 100)) for c in rgb)
            return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"
        except Exception:
            return hex_color

    def draw_dashed_border(self):
        self.selection_canvas.delete("border")
        w = self.selection_canvas.winfo_width()
        h = self.selection_canvas.winfo_height()
        if w < 10: w = 550 # fallback width before packing renders
        
        self.selection_canvas.create_rectangle(10, 10, w - 10, h - 10,
                                               outline=BORDER_COLOR, dash=(6, 4), width=1.5, tags=("border",))

    def on_canvas_resize(self, event):
        self.draw_dashed_border()
        self.selection_canvas.coords("txt", event.width / 2, 50)
        # Move the second text label
        items = self.selection_canvas.find_withtag("txt")
        if len(items) > 1:
            self.selection_canvas.coords(items[1], event.width / 2, 80)

    def open_ghostscript_download(self):
        import webbrowser
        webbrowser.open("https://www.ghostscript.com/releases/gsdnld.html")

    # --- File Management Logic ---
    def browse_files(self):
        filetypes = [
            ("All Supported Files", "*.pdf *.jpg *.jpeg *.png *.heic *.tiff *.tif *.bmp"),
            ("PDF Documents", "*.pdf"),
            ("Images", "*.jpg *.jpeg *.png *.heic *.tiff *.tif *.bmp")
        ]
        
        paths = filedialog.askopenfilenames(title="Select Files", filetypes=filetypes)
        if not paths:
            return
            
        for path in paths:
            # Check for duplicates
            if any(f["path"] == path for f in self.selected_files):
                continue
                
            name = os.path.basename(path)
            size = os.path.getsize(path)
            ext = os.path.splitext(name)[1].lower()
            
            file_type = "pdf" if ext == ".pdf" else "image"
            
            self.selected_files.append({
                "path": path,
                "name": name,
                "size": size,
                "type": file_type
            })
            
        self.update_file_list_ui()

    def remove_file(self, file_idx):
        if 0 <= file_idx < len(self.selected_files):
            self.selected_files.pop(file_idx)
            self.update_file_list_ui()

    def clear_files(self):
        self.selected_files.clear()
        self.update_file_list_ui()

    def update_file_list_ui(self):
        if self.files_passed:
            self.disable_actions(len(self.selected_files) == 0)
            return
            
        # Clear existing cards
        for widget in self.files_scroll_frame.scrollable_frame.winfo_children():
            widget.destroy()
            
        if not self.selected_files:
            lbl_empty = tk.Label(self.files_scroll_frame.scrollable_frame, 
                                 text="No files selected.\nClick the box above to add files.", 
                                 font=("Helvetica Neue", 11), fg=TEXT_MUTED, bg=BG_COLOR, pady=60)
            lbl_empty.pack(fill="x", expand=True)
            self.btn_clear_all.pack_forget()
            self.disable_actions(True)
            return
            
        self.btn_clear_all.pack(side="right", pady=(5, 5))
        self.disable_actions(False)
        
        # Display list of selected files
        for i, file_info in enumerate(self.selected_files):
            card = tk.Frame(self.files_scroll_frame.scrollable_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(fill="x", pady=4, padx=5)
            
            # File Type Icon
            icon = "📕" if file_info["type"] == "pdf" else "🖼️"
            lbl_icon = tk.Label(card, text=icon, font=("Helvetica Neue", 14), bg=CARD_BG)
            lbl_icon.pack(side="left", padx=(10, 5), pady=10)
            
            # Name and Details Container
            details_frame = tk.Frame(card, bg=CARD_BG)
            details_frame.pack(side="left", fill="both", expand=True, padx=5)
            
            # Shorten name if too long
            display_name = file_info["name"]
            if len(display_name) > 40:
                display_name = display_name[:25] + "..." + display_name[-12:]
                
            lbl_name = tk.Label(details_frame, text=display_name, font=("Helvetica Neue", 11, "bold"), fg=TEXT_MAIN, bg=CARD_BG, anchor="w")
            lbl_name.pack(side="top", fill="x", pady=(8, 2))
            
            size_formatted = self.format_size(file_info["size"])
            lbl_size = tk.Label(details_frame, text=size_formatted, font=("Helvetica Neue", 9), fg=TEXT_MUTED, bg=CARD_BG, anchor="w")
            lbl_size.pack(side="top", fill="x", pady=(0, 8))
            
            # Remove button
            # Capture index in lambda closure
            btn_remove = tk.Button(card, text="✕", font=("Helvetica Neue", 11), bg=CARD_BG, fg=TEXT_MUTED, activebackground=CARD_BG, activeforeground=DANGER_RED, bd=0, cursor="hand2", command=lambda idx=i: self.remove_file(idx))
            btn_remove.pack(side="right", padx=15)
            
            # Hover highlight
            def on_enter_remove(e, b=btn_remove):
                b.configure(fg=DANGER_RED)
            def on_leave_remove(e, b=btn_remove):
                b.configure(fg=TEXT_MUTED)
            btn_remove.bind("<Enter>", on_enter_remove)
            btn_remove.bind("<Leave>", on_leave_remove)

    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def disable_actions(self, disable):
        state = "disabled" if disable else "normal"
        self.btn_compress.configure(state=state)
        self.btn_rename.configure(state=state)
        
        # PDF specific actions require Ghostscript as well
        if not self.gs_bin or disable:
            self.btn_uniform.configure(state="disabled")
            self.btn_pdf_images.configure(state="disabled")
        else:
            self.btn_uniform.configure(state="normal")
            self.btn_pdf_images.configure(state="normal")

    # --- Threading & Progress Helpers ---
    def run_threaded_task(self, target_func, args=()):
        self.task_running = True
        self.disable_actions(True)
        self.progress_bar.pack(side="right", padx=15, pady=12, fill="x", expand=False)
        self.progress_bar.configure(mode="determinate", value=0)
        
        # Start background processing thread
        thread = threading.Thread(target=target_func, args=args, daemon=True)
        thread.start()

    def update_progress(self, current, total, status_text):
        self.root.after(0, self._update_progress_ui, current, total, status_text)

    def _update_progress_ui(self, current, total, status_text):
        percent = (current / total) * 100
        self.progress_bar.configure(value=percent)
        self.lbl_status.configure(text=f"{status_text} ({current}/{total})")

    # --- ACTION 1: BULK RENAME ---
    def run_bulk_rename(self):
        if getattr(self, "task_running", False):
            return
        if not self.selected_files:
            return
            
        file_paths = [f["path"] for f in self.selected_files]
        
        # Check if they are in the same folder
        folders = set(os.path.dirname(p) for p in file_paths)
        if len(folders) > 1:
            confirm = messagebox.askyesno("OptiFile Renamer", "Selected files are in different folders. Sequentially renaming them will name files as (1), (2), etc. inside each folder independently. Do you want to proceed?")
            if not confirm:
                return
                
        def rename_task():
            self.update_progress(0, len(file_paths), "Renaming files...")
            try:
                # Group files by directory
                from collections import defaultdict
                dir_groups = defaultdict(list)
                for path in file_paths:
                    dir_groups[os.path.dirname(path)].append(path)
                
                total_processed = 0
                new_files = []
                
                for directory, paths in dir_groups.items():
                    # 1st pass: rename to temp names to avoid collisions
                    temp_names = []
                    for idx, path in enumerate(paths):
                        ext = os.path.splitext(path)[1]
                        temp_path = os.path.join(directory, f"temp_optifile_{uuid.uuid4().hex}_{idx}{ext}")
                        os.rename(path, temp_path)
                        temp_names.append((temp_path, ext))
                    
                    # 2nd pass: rename to final sequential names
                    pad_width = len(str(len(temp_names)))
                    for idx, (temp_path, ext) in enumerate(temp_names):
                        num_str = str(idx + 1).zfill(pad_width)
                        final_path = os.path.join(directory, f"({num_str}){ext}")
                        os.rename(temp_path, final_path)
                        new_files.append(final_path)
                        
                        total_processed += 1
                        self.update_progress(total_processed, len(file_paths), "Renaming files...")
                
                self.root.after(0, self.finish_bulk_rename, new_files)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Rename Error", f"An error occurred while renaming:\n{str(e)}"))
                self.root.after(0, self.reset_ui_after_task)
                
        self.run_threaded_task(rename_task)

    def finish_bulk_rename(self, new_paths):
        self.reset_ui_after_task()
        self.play_sound()
        
        # Load the newly renamed files into the selector automatically
        self.selected_files.clear()
        for path in new_paths:
            if os.path.exists(path):
                name = os.path.basename(path)
                size = os.path.getsize(path)
                ext = os.path.splitext(name)[1].lower()
                self.selected_files.append({
                    "path": path,
                    "name": name,
                    "size": size,
                    "type": "pdf" if ext == ".pdf" else "image"
                })
        self.update_file_list_ui()
        
        # Refresh Finder
        if new_paths:
            folders = set(os.path.dirname(p) for p in new_paths)
            for folder in folders:
                self.refresh_macos_finder(folder)
                
        # Show elegant toast notification
        self.show_completion_panel(mode="rename", file_count=len(new_paths))

    # --- ACTION 2: PDF TO IMAGES ---
    def start_pdf_to_images(self):
        if getattr(self, "task_running", False):
            return
        pdf_files = [f for f in self.selected_files if f["type"] == "pdf"]
        if not pdf_files:
            messagebox.showwarning("Convert PDF", "Please select at least one PDF file.")
            return
            
        # Ask output format
        format_window = tk.Toplevel(self.root)
        format_window.title("Choose Format")
        format_window.geometry("300x180")
        format_window.configure(bg=CARD_BG)
        format_window.resizable(False, False)
        format_window.transient(self.root)
        format_window.grab_set()
        
        # Center format window over main app
        x = self.root.winfo_x() + (self.root.winfo_width() - 300) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2
        format_window.geometry(f"+{x}+{y}")
        
        tk.Label(format_window, text="Select Output Image Format", font=("Helvetica Neue", 12, "bold"), fg=TEXT_MAIN, bg=CARD_BG).pack(pady=(20, 15))
        
        fmt_var = tk.StringVar(value="jpg")
        
        r_frame = tk.Frame(format_window, bg=CARD_BG)
        r_frame.pack()
        tk.Radiobutton(r_frame, text="JPG (Joint Photographic Group)", variable=fmt_var, value="jpg", fg=TEXT_MAIN, bg=CARD_BG, selectcolor=CARD_BG, font=("Helvetica Neue", 10)).pack(anchor="w", pady=2)
        tk.Radiobutton(r_frame, text="PNG (Portable Network Graphics)", variable=fmt_var, value="png", fg=TEXT_MAIN, bg=CARD_BG, selectcolor=CARD_BG, font=("Helvetica Neue", 10)).pack(anchor="w", pady=2)
        
        btn_frame = tk.Frame(format_window, bg=CARD_BG)
        btn_frame.pack(side="bottom", fill="x", pady=15)
        
        def on_confirm():
            img_format = fmt_var.get()
            format_window.destroy()
            self.run_pdf_to_images_task(pdf_files, img_format)
        tk.Button(btn_frame, text="Convert", bg=ACCENT_COLOR, fg="#FFFFFF", activebackground=ACCENT_HOVER, activeforeground="#FFFFFF", bd=0, padx=15, pady=6, font=("Helvetica Neue", 10, "bold"), command=on_confirm).pack(side="right", padx=20)
        tk.Button(btn_frame, text="Cancel", bg=SEC_BTN_BG, fg=TEXT_MAIN, activebackground=SEC_BTN_HOVER, activeforeground=TEXT_MAIN, bd=0, padx=15, pady=6, font=("Helvetica Neue", 10), command=format_window.destroy).pack(side="right")

    def run_pdf_to_images_task(self, pdf_files, img_format):
        def convert_task():
            total = len(pdf_files)
            device = "jpeg" if img_format == "jpg" else "png16m"
            
            output_directories = []
            
            for idx, file_info in enumerate(pdf_files):
                self.update_progress(idx, total, f"Converting {file_info['name']}...")
                
                pdf_path = file_info["path"]
                dir_name = os.path.dirname(pdf_path)
                base_name = os.path.splitext(file_info["name"])[0]
                
                out_dir = os.path.join(dir_name, f"{base_name}_images")
                counter = 1
                while os.path.exists(out_dir):
                    out_dir = os.path.join(dir_name, f"{base_name}_images_{counter}")
                    counter += 1
                os.makedirs(out_dir, exist_ok=True)
                output_directories.append(out_dir)
                
                output_pattern = os.path.join(out_dir, f"(%d).{img_format}")
                
                cmd = [
                    self.gs_bin,
                    f"-sDEVICE={device}",
                    "-r150",
                    "-dNOPAUSE", "-dQUIET", "-dBATCH",
                    f"-sOutputFile={output_pattern}",
                    pdf_path
                ]
                
                subprocess.run(cmd, capture_output=True)
                self.update_progress(idx + 1, total, f"Converting {file_info['name']}...")
                
            self.root.after(0, self.finish_pdf_to_images, output_directories)
            
        self.run_threaded_task(convert_task)

    def finish_pdf_to_images(self, out_dirs):
        self.reset_ui_after_task()
        self.play_sound()
        
        self.show_completion_panel(mode="convert", folders=out_dirs)

    # --- ACTION 3: MAKE PAGE SIZES UNIFORM (PREFLIGHT) ---
    def start_preflight(self):
        if getattr(self, "task_running", False):
            return
        pdf_files = [f for f in self.selected_files if f["type"] == "pdf"]
        if not pdf_files:
            messagebox.showwarning("Preflight", "Please select at least one PDF file.")
            return
            
        if not pypdf:
            messagebox.showerror("Preflight Error", "The 'pypdf' package is required for page size analysis but was not found.")
            return
            
        def preflight_task():
            total = len(pdf_files)
            results = []
            
            for idx, file_info in enumerate(pdf_files):
                self.update_progress(idx, total, f"Standardizing {file_info['name']}...")
                
                pdf_path = file_info["path"]
                dir_name = os.path.dirname(pdf_path)
                base_name = os.path.splitext(file_info["name"])[0]
                
                # Determine majority size
                try:
                    reader = pypdf.PdfReader(pdf_path)
                    sizes = []
                    for page in reader.pages:
                        w = round(float(page.mediabox.width), 2)
                        h = round(float(page.mediabox.height), 2)
                        sizes.append((w, h))
                    
                    if sizes:
                        width, height = Counter(sizes).most_common(1)[0][0]
                    else:
                        width, height = 595.2, 842.16 # Default A4
                except Exception:
                    width, height = 595.2, 842.16
                    
                out_path = os.path.join(dir_name, f"{base_name}_uniform.pdf")
                
                # Rescale pages via GS
                cmd = [
                    self.gs_bin,
                    "-sDEVICE=pdfwrite",
                    "-dCompatibilityLevel=1.4",
                    "-dNOPAUSE", "-dQUIET", "-dBATCH",
                    f"-dDEVICEWIDTHPOINTS={width}",
                    f"-dDEVICEHEIGHTPOINTS={height}",
                    "-dFIXEDMEDIA",
                    "-dPDFFitPage",
                    f"-sOutputFile={out_path}",
                    pdf_path
                ]
                
                proc = subprocess.run(cmd, capture_output=True)
                success = (proc.returncode == 0 and os.path.exists(out_path))
                
                if success:
                    results.append({
                        "original": pdf_path,
                        "temp_out": out_path,
                        "final_out": pdf_path,
                        "label": f"{width}x{height} pt"
                    })
                
                self.update_progress(idx + 1, total, f"Standardizing {file_info['name']}...")
                
            self.root.after(0, self.finish_preflight, results)
            
        self.run_threaded_task(preflight_task)

    def finish_preflight(self, results):
        self.reset_ui_after_task()
        if not results:
            messagebox.showerror("Preflight", "Failed to standardize pages for the selected PDFs.")
            return
            
        self.play_sound()
        self.show_completion_panel(mode="preflight", results=results)

    # --- ACTION 4: COMPRESSION ---
    def start_compression(self):
        if getattr(self, "task_running", False):
            return
        if not self.selected_files:
            return
            
        preset = self.quality_var.get()
        
        def compression_task():
            total = len(self.selected_files)
            results = []
            
            # Preset values mapping
            if preset == "High":
                gs_resol = "300"
                gs_qfactor = "0.3"
                img_max_dim = 1600
                img_quality = 85
            elif preset == "Low":
                gs_resol = "72"
                gs_qfactor = "1.1"
                img_max_dim = 800
                img_quality = 55
            else: # Balanced
                gs_resol = "150"
                gs_qfactor = "0.7"
                img_max_dim = 1280
                img_quality = 78
                
            for idx, file_info in enumerate(self.selected_files):
                self.update_progress(idx, total, f"Compressing {file_info['name']}...")
                
                path = file_info["path"]
                name = file_info["name"]
                dir_name = os.path.dirname(path)
                base, ext = os.path.splitext(name)
                ext_lowercase = ext.lower()
                
                orig_size = file_info["size"]
                success = False
                
                if file_info["type"] == "pdf":
                    # Scan PDF to see if it is image-heavy
                    is_image_heavy = False
                    if pypdf is not None:
                        try:
                            reader = pypdf.PdfReader(path)
                            total_pages = len(reader.pages)
                            has_images = sum(1 for p in reader.pages if len(p.images) > 0)
                            if total_pages > 0 and (has_images / total_pages) >= 0.7:
                                is_image_heavy = True
                        except Exception:
                            pass
                            
                    # Ghostscript compression (only if not image-heavy)
                    temp_out = os.path.join(tempfile.gettempdir(), f"{base}_temp_compressed.pdf")
                    final_replace = path
                    
                    cmd = [
                        self.gs_bin,
                        "-sDEVICE=pdfwrite",
                        "-dCompatibilityLevel=1.4",
                        "-dNOPAUSE", "-dQUIET", "-dBATCH",
                        "-dDownsampleColorImages=true",
                        f"-dColorImageResolution={gs_resol}",
                        "-dColorImageDownsampleThreshold=1.0",
                        "-dColorImageDownsampleType=/Bicubic",
                        "-dAutoFilterColorImages=false",
                        "-dColorImageFilter=/DCTEncode",
                        f"-sOutputFile={temp_out}",
                        "-c", f"<< /PassThroughJPEGImages false /ColorImageDict << /QFactor {gs_qfactor} /Blend 1 >> >> setdistillerparams",
                        "-f", path
                    ]
                    
                    gs_worked = False
                    if self.gs_bin and not is_image_heavy:
                        proc = subprocess.run(cmd, capture_output=True)
                        if proc.returncode == 0 and os.path.exists(temp_out) and os.path.getsize(temp_out) > 0:
                            if os.path.getsize(temp_out) < orig_size:
                                gs_worked = True
                                success = True
                            else:
                                os.remove(temp_out)
                                
                    if not gs_worked and pypdf is not None:
                        try:
                            reader = pypdf.PdfReader(path)
                            writer = pypdf.PdfWriter()
                            for page in reader.pages:
                                writer.add_page(page)
                            
                            img_compressed = False
                            for page in writer.pages:
                                for img_obj in page.images:
                                    try:
                                        # Pre-check dimensions without decoding to save CPU & memory
                                        obj = img_obj.indirect_reference.get_object()
                                        w = obj.get("/Width", 0)
                                        h = obj.get("/Height", 0)
                                        
                                        if w > img_max_dim or h > img_max_dim:
                                            pil_img = img_obj.image
                                            ratio = min(img_max_dim / w, img_max_dim / h)
                                            new_w, new_h = int(w * ratio), int(h * ratio)
                                            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                                            
                                            # Replace directly without duplicate pre-compression checks
                                            img_obj.replace(pil_img, quality=img_quality)
                                            img_compressed = True
                                    except Exception:
                                        pass
                            
                            if img_compressed:
                                with open(temp_out, "wb") as f:
                                    writer.write(f)
                                if os.path.exists(temp_out) and os.path.getsize(temp_out) < orig_size:
                                    success = True
                                elif os.path.exists(temp_out):
                                    os.remove(temp_out)
                        except Exception as e:
                            print(f"GUI pypdf fallback failed: {e}")
                            if os.path.exists(temp_out):
                                os.remove(temp_out)
                        
                else: # Images (JPG, PNG, HEIC, TIFF, BMP)
                    temp_out = os.path.join(tempfile.gettempdir(), f"{base}_temp_compressed{ext_lowercase}")
                    final_replace = path
                    
                    # Handle HEIC natively on macOS via sips
                    if ext_lowercase in ('.heic', '.heif') and sys.platform == "darwin":
                        cmd = [
                            "sips",
                            "-Z", str(img_max_dim),
                            "-s", "format", "heic",
                            "-s", "formatOptions", str(img_quality),
                            path,
                            "--out", temp_out
                        ]
                        proc = subprocess.run(cmd, capture_output=True)
                        success = (proc.returncode == 0 and os.path.exists(temp_out))
                    else:
                        # Pillow image resize & compression
                        try:
                            # Load pillow-heif for Windows if HEIC is processed
                            if ext_lowercase in ('.heic', '.heif'):
                                try:
                                    from pillow_heif import register_heif_opener
                                    register_heif_opener()
                                except ImportError:
                                    # Fallback
                                    raise RuntimeError("pillow-heif package missing on Windows for HEIC images.")
                                    
                            img = Image.open(path)
                            img = ImageOps.exif_transpose(img) # Prevent rotation
                            
                            # Scale maintaining aspect ratio
                            w, h = img.size
                            if max(w, h) > img_max_dim:
                                img.thumbnail((img_max_dim, img_max_dim), Image.Resampling.LANCZOS)
                                
                            save_args = {}
                            if ext_lowercase in ('.jpg', '.jpeg'):
                                if img.mode in ('RGBA', 'LA'):
                                    img = img.convert('RGB')
                                save_args['quality'] = img_quality
                                save_args['optimize'] = True
                            elif ext_lowercase == '.png':
                                # PNG is lossless, so we just run standard size optimization
                                save_args['optimize'] = True
                            elif ext_lowercase in ('.tiff', '.tif'):
                                save_args['compression'] = 'tiff_lzw'
                            elif ext_lowercase in ('.heic', '.heif'):
                                save_args['quality'] = img_quality
                                
                            img.save(temp_out, **save_args)
                            success = os.path.exists(temp_out)
                        except Exception as e:
                            print(f"PIL error for {name}: {e}")
                            success = False
                            
                # Check results and sizes
                if success:
                    new_size = os.path.getsize(temp_out)
                    # If compression actually expanded the size, we discard it to prevent bloat
                    if new_size >= orig_size:
                        if os.path.exists(temp_out):
                            os.remove(temp_out)
                        print(f"Skipping {name}: Original ({orig_size}) was smaller than compressed ({new_size})")
                    else:
                        results.append({
                            "original": path,
                            "name": name,
                            "temp_out": temp_out,
                            "final_out": final_replace,
                            "orig_size": orig_size,
                            "new_size": new_size
                        })
                        
                self.update_progress(idx + 1, total, f"Compressing {file_info['name']}...")
                
            self.root.after(0, self.finish_compression, results)
            
        self.run_threaded_task(compression_task)

    def finish_compression(self, results):
        self.reset_ui_after_task()
        if not results:
            messagebox.showinfo("Optimization Complete", "All selected files are already fully optimized!")
            return
            
        self.play_sound()
        self.show_completion_panel(mode="compress", results=results)

    # --- UI Cleanups & Overlay Managers ---
    def reset_ui_after_task(self):
        self.task_running = False
        self.disable_actions(False)
        self.progress_bar.pack_forget()
        self.lbl_status.configure(text="Ready")

    def play_sound(self):
        # Play notification sound based on platform
        try:
            if sys.platform == "darwin":
                # Background play of macOS system sounds
                subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif sys.platform == "win32":
                import winsound
                # Play standard Asterisk sound asynchronously
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    def show_completion_panel(self, mode, file_count=0, folders=None, results=None):
        # Hide main app containers
        self.main_container.pack_forget()
        if hasattr(self, "header_frame") and self.header_frame:
            self.header_frame.pack_forget()
        self.status_frame.pack_forget()
        
        # Build Results view
        self.results_frame.pack(fill="both", expand=True)
        for w in self.results_frame.winfo_children():
            w.destroy()
            
        # Title Card
        title_lbl = tk.Label(self.results_frame, text="🎉 Optimization Successful!", font=("Helvetica Neue", 16 if self.files_passed else 20, "bold"), fg=SUCCESS_GREEN, bg=BG_COLOR)
        title_lbl.pack(pady=(20, 10) if self.files_passed else (50, 20))
        
        # Data Info Container
        info_frame = tk.Frame(self.results_frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        info_frame.pack(fill="x", padx=15 if self.files_passed else 100, pady=10 if self.files_passed else 20)
        
        btn_frame = tk.Frame(self.results_frame, bg=BG_COLOR)
        btn_frame.pack(pady=15 if self.files_passed else 30)
        
        self.active_completion_buttons = []
        
        if mode == "rename":
            tk.Label(info_frame, text=f"Successfully renamed {file_count} files sequentially.", font=("Helvetica Neue", 12), fg=TEXT_MAIN, bg=CARD_BG, pady=30).pack()
            
            btn1 = self.create_completion_button(btn_frame, "Open Folder", ACCENT_COLOR, lambda: self.open_file_folder(results=None), is_primary=True)
            btn1.pack(side="left", padx=10)
            btn2 = self.create_completion_button(btn_frame, "Done", SEC_BTN_BG, self.close_results_panel)
            btn2.pack(side="left", padx=10)
            self.active_completion_buttons = [btn1, btn2]
            
        elif mode == "convert":
            tk.Label(info_frame, text=f"Successfully extracted PDF pages into separate folder(s):", font=("Helvetica Neue", 12), fg=TEXT_MAIN, bg=CARD_BG, pady=10).pack()
            for out_dir in folders:
                tk.Label(info_frame, text=os.path.basename(out_dir), font=("Helvetica Neue", 11, "italic"), fg=TEXT_MUTED, bg=CARD_BG, pady=5).pack()
                
            btn1 = self.create_completion_button(btn_frame, "Open Folder(s)", ACCENT_COLOR, lambda: self.open_folders(folders), is_primary=True)
            btn1.pack(side="left", padx=10)
            btn2 = self.create_completion_button(btn_frame, "Done", SEC_BTN_BG, self.close_results_panel)
            btn2.pack(side="left", padx=10)
            self.active_completion_buttons = [btn1, btn2]
            
        elif mode == "preflight":
            tk.Label(info_frame, text=f"Standardized page dimensions for {len(results)} PDF(s).", font=("Helvetica Neue", 12), fg=TEXT_MAIN, bg=CARD_BG, pady=15).pack()
            
            for res in results:
                name = os.path.basename(res["original"])
                tk.Label(info_frame, text=f"• {name} ➜ {res['label']}", font=("Helvetica Neue", 10), fg=TEXT_MUTED, bg=CARD_BG, anchor="w", padx=20).pack(fill="x", pady=2)
                
            # Spacer
            tk.Label(info_frame, text="", bg=CARD_BG, height=1).pack()
            
            btn1 = self.create_completion_button(btn_frame, "Replace Originals", SUCCESS_GREEN, lambda: self.apply_replacements(results), is_primary=True)
            btn1.pack(side="left", padx=10)
            btn2 = self.create_completion_button(btn_frame, "Keep Standardized Copies", ACCENT_COLOR, lambda: self.keep_copies(results))
            btn2.pack(side="left", padx=10)
            btn3 = self.create_completion_button(btn_frame, "Cancel & Discard", DANGER_RED, lambda: self.discard_temps(results))
            btn3.pack(side="left", padx=10)
            self.active_completion_buttons = [btn1, btn2, btn3]
            
        elif mode == "compress":
            total_orig = sum(r["orig_size"] for r in results)
            total_new = sum(r["new_size"] for r in results)
            saved_bytes = total_orig - total_new
            saved_percent = (saved_bytes / total_orig) * 100 if total_orig > 0 else 0
            
            # Giant percentage display
            lbl_percentage = tk.Label(info_frame, text=f"{saved_percent:.1f}% Saved", font=("Helvetica Neue", 22 if self.files_passed else 28, "bold"), fg=SUCCESS_GREEN, bg=CARD_BG, pady=10 if self.files_passed else 15)
            lbl_percentage.pack()
            
            lbl_saving_info = tk.Label(info_frame, text=f"Original: {self.format_size(total_orig)}  |  New: {self.format_size(total_new)}", font=("Helvetica Neue", 10 if self.files_passed else 11), fg=TEXT_MAIN, bg=CARD_BG, pady=5 if self.files_passed else 10)
            lbl_saving_info.pack()
            
            # File list details inside ScrollableFrame overlay
            list_frame = tk.Frame(info_frame, bg=CARD_BG, height=80 if self.files_passed else 150)
            list_frame.pack(fill="x", padx=10 if self.files_passed else 20, pady=5 if self.files_passed else 10)
            
            # List details
            for res in results:
                reduction = ((res["orig_size"] - res["new_size"]) / res["orig_size"]) * 100
                tk.Label(list_frame, text=f"• {res['name']} ({self.format_size(res['orig_size'])} ➔ {self.format_size(res['new_size'])} | -{reduction:.0f}%)", font=("Helvetica Neue", 9 if self.files_passed else 10), fg=TEXT_MUTED, bg=CARD_BG, anchor="w").pack(fill="x", pady=1)
                
            btn1 = self.create_completion_button(btn_frame, "Replace Originals", SUCCESS_GREEN, lambda: self.apply_replacements(results), is_primary=True)
            btn1.pack(side="left", padx=5 if self.files_passed else 10)
            btn2 = self.create_completion_button(btn_frame, "Keep Copies" if self.files_passed else "Keep Compressed Copies", ACCENT_COLOR, lambda: self.keep_copies(results))
            btn2.pack(side="left", padx=5 if self.files_passed else 10)
            btn3 = self.create_completion_button(btn_frame, "Discard" if self.files_passed else "Cancel & Discard", DANGER_RED, lambda: self.discard_temps(results))
            btn3.pack(side="left", padx=5 if self.files_passed else 10)
            self.active_completion_buttons = [btn1, btn2, btn3]

        # Initialize completion button navigation
        self.active_completion_index = 0
        self.bind_completion_screen_keys(results, folders, mode)
        self.update_completion_button_focus()

    def close_results_panel(self):
        if self.files_passed:
            # In compact mode, we exit the application completely on completion
            self.root.destroy()
            return
            
        self.results_frame.pack_forget()
        
        # Restore main views
        if hasattr(self, "header_frame") and self.header_frame:
            self.header_frame.pack(side="top", fill="x")
        self.main_container.pack(side="top", fill="both", expand=True, padx=20, pady=15)
        self.status_frame.pack(side="bottom", fill="x")
        
        # Clear selection on success and refresh UI
        self.clear_files()
        
        # Restore main screen key bindings
        self.restore_main_screen_keys()

    def open_folders(self, paths):
        for path in paths:
            self.open_path_in_file_manager(path)

    def open_file_folder(self, results=None):
        if results:
            # Open the containing folder of the first result
            folder = os.path.dirname(results[0]["temp_out"])
            self.open_path_in_file_manager(folder)
        elif self.selected_files:
            folder = os.path.dirname(self.selected_files[0]["path"])
            self.open_path_in_file_manager(folder)

    def refresh_macos_finder(self, path):
        if sys.platform == "darwin":
            try:
                script = f'tell application "Finder" to update folder (POSIX file "{path}")'
                subprocess.run(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    def open_path_in_file_manager(self, path):
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open directory:\n{str(e)}")

    def apply_replacements(self, results):
        """Overwrites original files with the optimized temporary files."""
        for item in results:
            try:
                temp = item["temp_out"]
                final = item["final_out"]
                
                # Delete original file safely (moves to Trash on Mac, standard delete on Win)
                if os.path.exists(final):
                    if sys.platform == "darwin":
                        # AppleScript to send file to Trash (lossless delete)
                        applescript = f'tell application "Finder" to delete POSIX file "{final}"'
                        subprocess.run(["osascript", "-e", applescript], capture_output=True)
                    else:
                        # Direct delete on Windows
                        os.remove(final)
                        
                # Rename/move temp file to final location
                shutil.move(temp, final)
            except Exception as e:
                print(f"Error replacing original file: {e}")
                
        if results:
            self.refresh_macos_finder(os.path.dirname(results[0]["original"]))
        self.close_results_panel()

    def keep_copies(self, results):
        """Preserves the temporary file naming and location but opens folder."""
        for item in results:
            try:
                temp = item["temp_out"]
                orig = item["original"]
                dir_name = os.path.dirname(orig)
                base, ext = os.path.splitext(os.path.basename(orig))
                
                # Check for temp naming pattern
                if "_temp_uniform" in temp:
                    clean_path = os.path.join(dir_name, f"{base}_uniform{ext}")
                else:
                    clean_path = os.path.join(dir_name, f"{base}_compressed{ext}")
                    
                if os.path.exists(clean_path):
                    os.remove(clean_path)
                shutil.move(temp, clean_path)
            except Exception as e:
                print(f"Error keeping copies: {e}")
                
        # Open parent folder of first copy
        if results:
            orig = results[0]["original"]
            dir_to_open = os.path.dirname(orig)
            self.refresh_macos_finder(dir_to_open)
            self.open_path_in_file_manager(dir_to_open)
            
        self.close_results_panel()

    def discard_temps(self, results):
        """Discards all optimization temporary outputs and goes back."""
        for item in results:
            try:
                if os.path.exists(item["temp_out"]):
                    os.remove(item["temp_out"])
            except Exception as e:
                print(f"Error discarding temp file: {e}")
        self.close_results_panel()

if __name__ == "__main__":
    root = tk.Tk()
    app = OptiFileApp(root)
    root.mainloop()
