# ⚡ OptiFile Desktop

OptiFile Desktop is a modern, high-performance, cross-platform utility designed to compress PDFs and images, convert PDF pages to images, standardize document margins, and bulk-rename files. It runs natively on both **macOS** and **Windows** with two custom UX modes optimized for productivity.

---

## 🚀 Key Features

* **🗜️ High-Efficiency Compression:**
  - **PDFs:** Compressed using Ghostscript with custom DPI presets (High Quality: 300 DPI, Balanced: 150 DPI, Low Quality: 72 DPI).
  - **Images (JPEG, PNG, HEIC, TIFF, BMP):** Optimized using Pillow with EXIF rotation correction and aspect-ratio preserving scaling.
* **📐 Smart Page Size Standardization (Preflight):**
  - Scans PDF files using `pypdf`, identifies the majority page dimensions, and scales outlier pages to make the document uniform.
* **🖼️ PDF to Image Converter:**
  - Extracts PDF pages as sequentially numbered images (`(1).jpg`, `(2).jpg`...) in PNG or JPEG formats.
* **🏷️ Bulk File Renamer:**
  - Sequentially renames lists of files as `(1).ext`, `(2).ext`... while preventing local file collisions.
* **🌓 Live Theme Sync:**
  - Synchronizes with system settings on startup and listens to live theme transitions to toggle between Charcoal Dark Mode (`#121214`) and Crisp Light Mode (`#F3F4F6`).
* **🔒 Zero Temp Cache & Privacy:**
  - Does not write files to system temporary paths. All operations execute inside the files' parent directory under private transient filenames (`_temp_compressed`), which are instantly moved or deleted on completion.

---

## 🎭 Dual UX Modes

### 1. Full GUI Mode (macOS & Windows)
Launched by opening the application directly. Provides a full desktop workspace with:
- Selected file lists showing icons (📕 for PDF, 🖼️ for images) and sizes.
- Drag-and-drop zone to import files.
- Single-letter shortcuts (`C` to convert, `U` to preflight, `R` to rename).

### 2. macOS Quick Action Mode (macOS Finder Service)
Triggered by right-clicking files in Finder and choosing **Quick Actions > OptiFile**.
- **No GUI Window:** Runs completely hidden in the background.
- **Native OS Prompt Dialogs:** Uses focused macOS popup menus (`System Events`) to select options natively using arrow keys and `Enter`.
- Extremely fast and completely keyboard-navigable.

---

## ⌨️ Keyboard Navigation Map

### Main App Panel
* **`Up` / `Down` Arrow Keys:** Cycle focus and highlight between operations (Compress, Convert, Preflight, Rename) indicated by a `▶ ` cursor.
* **`Left` / `Right` Arrow Keys:** Change compression preset quality (High, Balanced, Low).
* **`Return` (Enter):** Run the currently highlighted operation.
* **`Escape`:** Close the application.

### Completion Panel / Native Dialogs
* **`Left` / `Right` Arrow Keys:** Cycle selection between `[Replace Originals]`, `[Keep Copies]`, and `[Discard]`.
* **`Return` (Enter):** Confirm and execute the selected action.
* **`Escape`:** Discard temporary outputs and close the program.

---

## 🛠️ Installation & Compilation

### macOS Installation (Quick Action Setup)
1. Ensure **Ghostscript** is installed via Homebrew:
   ```bash
   brew install ghostscript
   ```
2. Run the build script to compile the python files:
   ```bash
   ./build_app.sh
   ```
3. Run the installer script to register the Finder Quick Action:
   ```bash
   ./install.sh
   ```
4. Now, right-click any PDF or image in Finder, go to **Quick Actions**, and select **OptiFile**!

### Windows Compilation
1. Ensure Python 3.9+ is installed and **"Add Python to PATH"** is checked during installation.
2. Unzip `OptiFile_Windows_Compiler.zip`.
3. Double-click `build_app.bat`.
4. It will install Pillow, pypdf, and compile a standalone executable file in `dist\OptiFile.exe`.

---

## 📦 Dependencies
- Python 3.9+
- Pillow (Image compression)
- pypdf (PDF parsing)
- PyInstaller (Stand-alone packaging)
- Ghostscript (PDF rendering & resizing)
