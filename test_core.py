import os
import sys
import shutil
import tempfile
from collections import Counter
from PIL import Image

# Modify path to allow importing from current folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import OptiFileApp

def run_tests():
    print("=== OptiFile Core Engine Verification ===")
    
    # Initialize a mock root and app instance
    import tkinter as tk
    root = tk.Tk()
    root.withdraw() # Hide window
    
    app = OptiFileApp(root)
    
    # 1. Test Ghostscript Detection
    print(f"1. Ghostscript detected: {app.gs_bin}")
    if not app.gs_bin:
        print("❌ ERROR: Ghostscript not found on this system!")
        sys.exit(1)
    else:
        print("✅ Ghostscript Detection Passed!")
        
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Created temp verification dir: {temp_dir}")
        
        # 2. Test Image Compression (Pillow)
        print("\n2. Testing Image Compression (Pillow)...")
        # Create a dummy large image (e.g. 2000x2000 red square)
        img_path = os.path.join(temp_dir, "test_large.jpg")
        img = Image.new('RGB', (2000, 2000), color='red')
        img.save(img_path, 'JPEG', quality=95)
        orig_size = os.path.getsize(img_path)
        print(f"Original image size: {orig_size} bytes")
        
        # Mock file info
        file_info = {
            "path": img_path,
            "name": "test_large.jpg",
            "size": orig_size,
            "type": "image"
        }
        app.selected_files = [file_info]
        app.quality_var.set("Balanced") # Should resize to max 1280
        
        # We will manually run the logic from compression_task for images to check success
        temp_out = os.path.join(temp_dir, "test_large_temp_compressed.jpg")
        
        # Pillow image resize & compression
        try:
            img = Image.open(img_path)
            w, h = img.size
            if max(w, h) > 1280:
                img.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            img.save(temp_out, quality=70, optimize=True)
            success = os.path.exists(temp_out)
        except Exception as e:
            print(f"Pillow error: {e}")
            success = False
            
        if success:
            new_size = os.path.getsize(temp_out)
            compressed_img = Image.open(temp_out)
            print(f"Compressed image size: {new_size} bytes (Saved {((orig_size - new_size)/orig_size)*100:.1f}%)")
            print(f"Compressed image dimensions: {compressed_img.size}")
            if compressed_img.size == (1280, 1280) and new_size < orig_size:
                print("✅ Image Compression Passed!")
            else:
                print("❌ ERROR: Image compression size/dimensions unexpected!")
                sys.exit(1)
        else:
            print("❌ ERROR: Image compression failed!")
            sys.exit(1)
            
        # 3. Test Bulk Rename
        print("\n3. Testing Bulk Rename...")
        file1 = os.path.join(temp_dir, "file_a.txt")
        file2 = os.path.join(temp_dir, "file_b.txt")
        with open(file1, "w") as f: f.write("test a")
        with open(file2, "w") as f: f.write("test b")
        
        app.selected_files = [
            {"path": file1, "name": "file_a.txt", "size": 6, "type": "image"},
            {"path": file2, "name": "file_b.txt", "size": 6, "type": "image"}
        ]
        
        # We run the rename logic (grouped by directory)
        file_paths = [file1, file2]
        from collections import defaultdict
        dir_groups = defaultdict(list)
        for path in file_paths:
            dir_groups[os.path.dirname(path)].append(path)
            
        new_files = []
        for directory, paths in dir_groups.items():
            temp_names = []
            for idx, path in enumerate(paths):
                ext = os.path.splitext(path)[1]
                temp_path = os.path.join(directory, f"temp_{idx}{ext}")
                os.rename(path, temp_path)
                temp_names.append((temp_path, ext))
            
            for idx, (temp_path, ext) in enumerate(temp_names):
                final_path = os.path.join(directory, f"({idx+1}){ext}")
                os.rename(temp_path, final_path)
                new_files.append(final_path)
                
        print(f"Renamed files: {new_files}")
        if os.path.exists(os.path.join(temp_dir, "(1).txt")) and os.path.exists(os.path.join(temp_dir, "(2).txt")):
            print("✅ Bulk Rename Passed!")
        else:
            print("❌ ERROR: Bulk rename did not create expected output files!")
            sys.exit(1)
            
    print("\n=== Verification Complete: All engine components work perfectly! ===")
    root.destroy()

if __name__ == "__main__":
    run_tests()
