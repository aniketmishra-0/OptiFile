#!/bin/bash

# Ensure brew path is loaded in Automator context (non-interactive shell)
if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -f /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# Ensure Ghostscript is installed
if ! command -v gs &> /dev/null; then
    osascript -e 'display notification "Installing dependencies (Ghostscript)... Please wait." with title "OptiFile"'
    brew install ghostscript
    
    # Verify installation
    if ! command -v gs &> /dev/null; then
        osascript -e 'display dialog "Ghostscript is required but could not be installed automatically. Please install it manually by running:\n\nbrew install ghostscript\n\nin Terminal." with title "OptiFile Error" buttons {"OK"} default button "OK" with icon stop'
        exit 1
    fi
fi

GS_BIN=$(command -v gs)

# 1. Parse inputs and detect types
has_pdf=false
has_image=false
total_files=0
declare -a files

for f in "$@"; do
    if [ -f "$f" ]; then
        files+=("$f")
        total_files=$((total_files + 1))
        
        filename=$(basename "$f")
        ext="${filename##*.}"
        ext_lowercase=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
        
        if [ "$ext_lowercase" = "pdf" ]; then
            has_pdf=true
        elif [[ "$ext_lowercase" == "jpg" || "$ext_lowercase" == "jpeg" || "$ext_lowercase" == "png" || "$ext_lowercase" == "heic" || "$ext_lowercase" == "tiff" || "$ext_lowercase" == "bmp" ]]; then
            has_image=true
        fi
    fi
done

if [ "$total_files" -eq 0 ]; then
    exit 0
fi

# 2. Show context-aware menu based on selected file types
if [ "$has_pdf" = "true" ] && [ "$has_image" = "false" ]; then
    # PDFs only menu
    CHOICE=$(osascript -e 'choose from list {"Compress PDF", "Convert PDF to Images", "Make Page Sizes Uniform (Preflight)"} with title "OptiFile" with prompt "Choose action for selected PDF(s):" default items {"Compress PDF"} OK button name "Select" Cancel button name "Cancel"')
elif [ "$has_pdf" = "false" ] && [ "$has_image" = "true" ]; then
    # Images only menu
    CHOICE=$(osascript -e 'choose from list {"Compress Images", "Bulk Rename - (1) (2) (3)"} with title "OptiFile" with prompt "Choose action for selected Image(s):" default items {"Compress Images"} OK button name "Select" Cancel button name "Cancel"')
else
    # Mixed files menu
    CHOICE=$(osascript -e 'choose from list {"Compress All Files", "Bulk Rename - (1) (2) (3)"} with title "OptiFile" with prompt "Choose action for selected file(s):" default items {"Compress All Files"} OK button name "Select" Cancel button name "Cancel"')
fi

# Exit if cancelled
if [ "$CHOICE" = "false" ] || [ -z "$CHOICE" ]; then
    exit 0
fi

# --- ACTION 1: BULK RENAME ---
if [ "$CHOICE" = "Bulk Rename - (1) (2) (3)" ]; then
    if [ "$total_files" -lt 1 ]; then
        exit 0
    fi
    
    declare -a temp_files
    
    # First pass: Rename all selected files to temporary names to prevent collisions
    for ((i=0; i<total_files; i++)); do
        orig_f="${files[$i]}"
        dir=$(dirname "$orig_f")
        ext="${orig_f##*.}"
        temp_name="$dir/temp_optifile_${RANDOM}_${i}.${ext}"
        mv "$orig_f" "$temp_name"
        temp_files+=("$temp_name")
    done
    
    # Second pass: Rename to final sequential format (1).ext, (2).ext, etc.
    for ((i=0; i<total_files; i++)); do
        temp_f="${temp_files[$i]}"
        dir=$(dirname "$temp_f")
        ext="${temp_f##*.}"
        idx=$((i + 1))
        final_name="$dir/($idx).$ext"
        mv "$temp_f" "$final_name"
    done
    
    # Notify user
    afplay /System/Library/Sounds/Glass.aiff
    osascript -e "display notification \"Renamed $total_files files sequentially as (1), (2), (3)...\" with title \"OptiFile Renamer\""
    exit 0
fi

# --- ACTION 2: PDF TO IMAGES ---
if [ "$CHOICE" = "Convert PDF to Images" ]; then
    # Prompt for image format (PNG or JPG)
    FORMAT_CHOICE=$(osascript -e 'choose from list {"JPG (Joint Photographic Group)", "PNG (Portable Network Graphics)"} with title "OptiFile" with prompt "Choose output image format:" default items {"JPG (Joint Photographic Group)"} OK button name "Convert" Cancel button name "Cancel"')
    
    if [ "$FORMAT_CHOICE" = "false" ] || [ -z "$FORMAT_CHOICE" ]; then
        exit 0
    fi
    
    if [ "$FORMAT_CHOICE" = "PNG (Portable Network Graphics)" ]; then
        GS_DEVICE="png16m"
        IMG_EXT="png"
    else
        GS_DEVICE="jpeg"
        IMG_EXT="jpg"
    fi
    
    for f in "${files[@]}"; do
        filename=$(basename "$f")
        ext="${filename##*.}"
        dir=$(dirname "$f")
        base=$(basename "$f" ."$ext")
        
        # Create output folder
        out_dir="$dir/${base}_images"
        mkdir -p "$out_dir"
        
        # Extract pages as sequentially numbered images: (1).ext, (2).ext, etc.
        $GS_BIN -sDEVICE="$GS_DEVICE" -r150 -dNOPAUSE -dQUIET -dBATCH -sOutputFile="$out_dir/(%d).$IMG_EXT" "$f"
    done
    
    afplay /System/Library/Sounds/Glass.aiff
    osascript -e "display notification \"Successfully converted PDF pages to sequentially numbered $IMG_EXT images!\" with title \"OptiFile Converter\""
    exit 0
fi

# --- ACTION 3: MAKE PAGE SIZES UNIFORM (PREFLIGHT) ---
if [ "$CHOICE" = "Make Page Sizes Uniform (Preflight)" ]; then
    success_count=0
    declare -a compressed_files
    declare -a original_files
    declare -a target_replacements
    
    for f in "${files[@]}"; do
        filename=$(basename "$f")
        ext="${filename##*.}"
        dir=$(dirname "$f")
        base=$(basename "$f" ."$ext")
        
        # Determine the majority page size (most common dimensions in points)
        SIZES=$(python3 -c "
import sys, pypdf
from collections import Counter
try:
    reader = pypdf.PdfReader('$f')
    sizes = [(round(float(p.mediabox.width), 2), round(float(p.mediabox.height), 2)) for p in reader.pages]
    most_common = Counter(sizes).most_common(1)[0][0]
    print(f'{most_common[0]} {most_common[1]}')
except Exception as e:
    sys.exit(1)
" 2>/dev/null)

        if [ -z "$SIZES" ]; then
            # Fallback to standard A4 if majority detection fails
            width="595.2"
            height="842.16"
            label="Default A4"
        else
            read width height <<< "$SIZES"
            label="${width}x${height}pt"
        fi
        
        out_file="$dir/${base}_uniform.pdf"
        
        # Run Ghostscript to scale all pages to the detected majority size
        $GS_BIN -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dNOPAUSE -dQUIET -dBATCH \
            -dDEVICEWIDTHPOINTS="$width" -dDEVICEHEIGHTPOINTS="$height" -dFIXEDMEDIA -dPDFFitPage \
            -sOutputFile="$out_file" "$f"
            
        if [ $? -eq 0 ] && [ -f "$out_file" ]; then
            compressed_files+=("$out_file")
            original_files+=("$f")
            target_replacements+=("$f")
            success_count=$((success_count + 1))
        else
            osascript -e "display notification \"Failed to standardize pages for '$filename'\" with title \"OptiFile Preflight\""
        fi
    done
    
    if [ "$success_count" -gt 0 ]; then
        afplay /System/Library/Sounds/Glass.aiff
        
        if [ "$success_count" -eq 1 ]; then
            ACTION=$(osascript -e "display dialog \"OptiFile Preflight Complete!\n\nAll pages scaled uniformly to the majority size ($label).\" with title \"OptiFile\" buttons {\"Done\", \"Open PDF\", \"Replace Original\"} default button \"Done\" with icon note" 2>/dev/null)
            
            if [ "$ACTION" = "button returned:Replace Original" ]; then
                orig_file="${original_files[0]}"
                comp_file="${compressed_files[0]}"
                repl_file="${target_replacements[0]}"
                
                osascript -e "tell application \"Finder\" to delete POSIX file \"$orig_file\"" &>/dev/null
                mv "$comp_file" "$repl_file"
                osascript -e "display notification \"Original replaced with uniform version!\" with title \"OptiFile\""
            elif [ "$ACTION" = "button returned:Open PDF" ]; then
                open "${compressed_files[0]}"
            fi
        else
            ACTION=$(osascript -e "display dialog \"OptiFile Preflight Complete!\n\nStandardized page sizes for $success_count PDFs.\" with title \"OptiFile\" buttons {\"Done\", \"Replace All Originals\"} default button \"Done\" with icon note" 2>/dev/null)
            
            if [ "$ACTION" = "button returned:Replace All Originals" ]; then
                for ((i=0; i<success_count; i++)); do
                    orig_file="${original_files[$i]}"
                    comp_file="${compressed_files[$i]}"
                    repl_file="${target_replacements[$i]}"
                    
                    osascript -e "tell application \"Finder\" to delete POSIX file \"$orig_file\"" &>/dev/null
                    mv "$comp_file" "$repl_file"
                done
                osascript -e "display notification \"All originals replaced with uniform versions!\" with title \"OptiFile\""
            fi
        fi
    fi
    exit 0
fi

# --- ACTION 4: COMPRESSION (Default) ---
# Prompt for compression quality
QUALITY_CHOICE=$(osascript -e 'choose from list {"High Quality (300 DPI / 1080p)", "Balanced (Recommended - 150 DPI / 720p)", "Low Quality (72 DPI / 480p)"} with title "OptiFile" with prompt "Choose PDF & Image compression quality:" default items {"Balanced (Recommended - 150 DPI / 720p)"} OK button name "Compress" Cancel button name "Cancel"')

if [ "$QUALITY_CHOICE" = "false" ] || [ -z "$QUALITY_CHOICE" ]; then
    exit 0
fi

# Map settings
if [ "$QUALITY_CHOICE" = "High Quality (300 DPI / 1080p)" ]; then
    GS_RESOL="300"
    GS_QFACTOR="0.3"
    IMG_MAX_DIM="1920"
    IMG_QUALITY="85"
    QUALITY_LABEL="High"
elif [ "$QUALITY_CHOICE" = "Low Quality (72 DPI / 480p)" ]; then
    GS_RESOL="72"
    GS_QFACTOR="1.1"
    IMG_MAX_DIM="800"
    IMG_QUALITY="50"
    QUALITY_LABEL="Low"
else
    GS_RESOL="150"
    GS_QFACTOR="0.7"
    IMG_MAX_DIM="1280"
    IMG_QUALITY="70"
    QUALITY_LABEL="Balanced"
fi

success_count=0
total_orig_size=0
total_new_size=0

declare -a compressed_files
declare -a original_files
declare -a target_replacements

for f in "${files[@]}"; do
    filename=$(basename "$f")
    ext="${filename##*.}"
    ext_lowercase=$(echo "$ext" | tr '[:upper:]' '[:lower:]')
    dir=$(dirname "$f")
    base=$(basename "$f" ."$ext")
    orig_size=$(stat -f%z "$f")
    
    if [ "$ext_lowercase" = "pdf" ]; then
        out_file="$dir/${base}_compressed.pdf"
        $GS_BIN -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dNOPAUSE -dQUIET -dBATCH \
            -dDownsampleColorImages=true -dColorImageResolution="$GS_RESOL" -dColorImageDownsampleThreshold=1.0 \
            -dColorImageDownsampleType=/Bicubic -dAutoFilterColorImages=false -dColorImageFilter=/DCTEncode \
            -sOutputFile="$out_file" \
            -c "<< /PassThroughJPEGImages false /ColorImageDict << /QFactor $GS_QFACTOR /Blend 1 >> >> setdistillerparams" \
            -f "$f"
        final_out_file="$out_file"
        final_replace_path="$f"
        
    elif [[ "$ext_lowercase" == "jpg" || "$ext_lowercase" == "jpeg" || "$ext_lowercase" == "png" || "$ext_lowercase" == "heic" || "$ext_lowercase" == "tiff" || "$ext_lowercase" == "bmp" ]]; then
        if [ "$ext_lowercase" = "heic" ]; then
            out_file="$dir/${base}_compressed.heic"
            sips -Z "$IMG_MAX_DIM" -s format heic -s formatOptions "$IMG_QUALITY" "$f" --out "$out_file" &>/dev/null
            final_out_file="$out_file"
            final_replace_path="$f"
        else
            out_file="$dir/${base}_compressed.jpg"
            sips -Z "$IMG_MAX_DIM" -s format jpeg -s formatOptions "$IMG_QUALITY" "$f" --out "$out_file" &>/dev/null
            final_out_file="$out_file"
            final_replace_path="$dir/${base}.jpg"
        fi
    else
        continue
    fi
    
    if [ $? -eq 0 ] && [ -f "$final_out_file" ]; then
        new_size=$(stat -f%z "$final_out_file")
        
        if [ "$new_size" -ge "$orig_size" ]; then
            rm "$final_out_file"
            osascript -e "display notification \"'$filename' is already optimized!\" with title \"OptiFile ($QUALITY_LABEL)\""
        else
            compressed_files+=("$final_out_file")
            original_files+=("$f")
            target_replacements+=("$final_replace_path")
            
            success_count=$((success_count + 1))
            total_orig_size=$((total_orig_size + orig_size))
            total_new_size=$((total_new_size + new_size))
        fi
    else
        osascript -e "display notification \"Failed to compress '$filename'\" with title \"OptiFile ($QUALITY_LABEL)\""
    fi
done

if [ "$success_count" -gt 0 ]; then
    afplay /System/Library/Sounds/Glass.aiff
    
    orig_mb=$(( total_orig_size / 1048576 ))
    orig_frac=$(( (total_orig_size % 1048576) * 100 / 1048576 ))
    [ ${#orig_frac} -eq 1 ] && orig_frac="0$orig_frac"
    
    new_mb=$(( total_new_size / 1048576 ))
    new_frac=$(( (total_new_size % 1048576) * 100 / 1048576 ))
    [ ${#new_frac} -eq 1 ] && new_frac="0$new_frac"
    
    saved_percent=$(( 100 - (total_new_size * 100 / total_orig_size) ))
    
    if [ "$success_count" -eq 1 ]; then
        ACTION=$(osascript -e "display dialog \"OptiFile ($QUALITY_LABEL) Complete!\n\nOriginal: ${orig_mb}.${orig_frac} MB\nCompressed: ${new_mb}.${new_frac} MB\nSaved: ${saved_percent}%\" with title \"OptiFile\" buttons {\"Done\", \"Open File\", \"Replace Original\"} default button \"Done\" with icon note" 2>/dev/null)
        
        if [ "$ACTION" = "button returned:Replace Original" ]; then
            orig_file="${original_files[0]}"
            comp_file="${compressed_files[0]}"
            repl_file="${target_replacements[0]}"
            
            osascript -e "tell application \"Finder\" to delete POSIX file \"$orig_file\"" &>/dev/null
            mv "$comp_file" "$repl_file"
            osascript -e "display notification \"Original replaced with compressed version!\" with title \"OptiFile\""
        elif [ "$ACTION" = "button returned:Open File" ]; then
            open "${compressed_files[0]}"
        fi
    else
        ACTION=$(osascript -e "display dialog \"OptiFile ($QUALITY_LABEL) Batch Complete!\n\nCompressed: $success_count files\nTotal Original: ${orig_mb}.${orig_frac} MB\nTotal Compressed: ${new_mb}.${new_frac} MB\nSaved: ${saved_percent}%\" with title \"OptiFile\" buttons {\"Done\", \"Replace All Originals\"} default button \"Done\" with icon note" 2>/dev/null)
        
        if [ "$ACTION" = "button returned:Replace All Originals" ]; then
            for ((i=0; i<success_count; i++)); do
                orig_file="${original_files[$i]}"
                comp_file="${compressed_files[$i]}"
                repl_file="${target_replacements[$i]}"
                
                osascript -e "tell application \"Finder\" to delete POSIX file \"$orig_file\"" &>/dev/null
                mv "$comp_file" "$repl_file"
            done
            osascript -e "display notification \"All originals replaced with compressed versions!\" with title \"OptiFile\""
        fi
    fi
fi
