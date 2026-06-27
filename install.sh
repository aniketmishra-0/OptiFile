#!/bin/bash

# Define paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="$HOME/Library/Services"
APP_DESTINATION="/Applications/OptiFile.app"
WORKFLOW_NAME="OptiFile.workflow"
TARGET_WORKFLOW_DIR="$SERVICES_DIR/$WORKFLOW_NAME"

echo "Installing OptiFile macOS Finder Integration (Smart GUI Edition)..."

# Stop any running instances
echo "Stopping any running instances of OptiFile..."
killall OptiFile 2>/dev/null || true
pkill -f "OptiFile" 2>/dev/null || true

# 1. Verify and Install OptiFile.app to /Applications
if [ -d "$SCRIPT_DIR/dist/OptiFile.app" ]; then
    echo "✓ Found compiled OptiFile.app. Installing to /Applications..."
    rm -rf "$APP_DESTINATION"
    cp -R "$SCRIPT_DIR/dist/OptiFile.app" "$APP_DESTINATION"
    xattr -cr "$APP_DESTINATION" 2>/dev/null || true
    echo "✓ Successfully installed OptiFile.app to /Applications"
elif [ -d "$APP_DESTINATION" ]; then
    echo "✓ OptiFile.app is already installed in /Applications"
else
    echo "❌ Error: Could not find compiled OptiFile.app in '$SCRIPT_DIR/dist/OptiFile.app'"
    echo "Please run './build_app.sh' first to compile the app before running the installer."
    exit 1
fi

# 2. Clean up any existing separate workflows
rm -rf "$SERVICES_DIR/OptiFile - Compress.workflow"
rm -rf "$SERVICES_DIR/OptiFile - Convert PDF to Images.workflow"
rm -rf "$SERVICES_DIR/OptiFile - Bulk Rename.workflow"
rm -rf "$SERVICES_DIR/OptiFile - Merge PDFs.workflow"
rm -rf "$SERVICES_DIR/OptiFile - Merge Images to PDF.workflow"
rm -rf "$TARGET_WORKFLOW_DIR"
echo "✓ Cleaned up separate workflows"

# 3. Create the unified workflow bundle structure
mkdir -p "$TARGET_WORKFLOW_DIR/Contents"

# 4. Write Info.plist (correctly configured for Finder, PDFs, and common image formats)
cat << 'EOF' > "$TARGET_WORKFLOW_DIR/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>NSServices</key>
	<array>
		<dict>
			<key>NSMenuItem</key>
			<dict>
				<key>default</key>
				<string>OptiFile</string>
			</dict>
			<key>NSMessage</key>
			<string>runWorkflowAsService</string>
			<key>NSRequiredContext</key>
			<dict>
				<key>NSApplicationIdentifier</key>
				<string>com.apple.finder</string>
			</dict>
			<key>NSSendFileTypes</key>
			<array>
				<string>com.adobe.pdf</string>
				<string>public.jpeg</string>
				<string>public.png</string>
				<string>public.heic</string>
				<string>public.tiff</string>
				<string>com.microsoft.bmp</string>
			</array>
		</dict>
	</array>
</dict>
</plist>
EOF
echo "✓ Generated Info.plist"

# 5. Write document.wflow
cat << 'EOF' > "$TARGET_WORKFLOW_DIR/Contents/document.wflow"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>AMApplicationBuild</key>
	<string>512</string>
	<key>AMApplicationVersion</key>
	<string>2.10</string>
	<key>AMDocumentVersion</key>
	<string>2</string>
	<key>actions</key>
	<array>
		<dict>
			<key>action</key>
			<dict>
				<key>AMAccepts</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Optional</key>
					<true/>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>AMActionVersion</key>
				<string>2.0.3</string>
				<key>AMApplication</key>
				<array>
					<string>Automator</string>
				</array>
				<key>AMParameterProperties</key>
				<dict>
					<key>COMMAND_STRING</key>
					<dict/>
					<key>CheckedForUserDefaultShell</key>
					<dict/>
					<key>inputMethod</key>
					<dict/>
					<key>shell</key>
					<dict/>
					<key>source</key>
					<dict/>
				</dict>
				<key>AMProvides</key>
				<dict>
					<key>Container</key>
					<string>List</string>
					<key>Types</key>
					<array>
						<string>com.apple.cocoa.string</string>
					</array>
				</dict>
				<key>ActionBundlePath</key>
				<string>/System/Library/Automator/Run Shell Script.action</string>
				<key>ActionName</key>
				<string>Run Shell Script</string>
				<key>ActionParameters</key>
				<dict>
					<key>COMMAND_STRING</key>
					<string>open -a "/Applications/OptiFile.app" "$@"</string>
					<key>CheckedForUserDefaultShell</key>
					<true/>
					<key>inputMethod</key>
					<integer>1</integer>
					<key>shell</key>
					<string>/bin/bash</string>
					<key>source</key>
					<string></string>
				</dict>
				<key>BundleIdentifier</key>
				<string>com.apple.RunShellScript</string>
				<key>CFBundleVersion</key>
				<string>2.0.3</string>
				<key>CanShowSelectedItemsWhenRun</key>
				<false/>
				<key>CanShowWhenRun</key>
				<true/>
				<key>Category</key>
				<array>
					<string>AMCategoryUtilities</string>
				</array>
				<key>Class Name</key>
				<string>RunShellScriptAction</string>
				<key>InputUUID</key>
				<string>5EEA3E62-AFE5-4276-A778-C091942C6B78</string>
				<key>Keywords</key>
				<array>
					<string>Shell</string>
					<string>Script</string>
					<string>Command</string>
					<string>Run</string>
					<string>Unix</string>
				</array>
				<key>OutputUUID</key>
				<string>4B3FD597-9C55-4133-A905-DFA4C811F6B1</string>
				<key>UUID</key>
				<string>CFB0951C-1076-4028-92A0-490967D87A87</string>
				<key>UnlocalizedApplications</key>
				<array>
					<string>Automator</string>
				</array>
				<key>arguments</key>
				<dict>
					<key>0</key>
					<dict>
						<key>default value</key>
						<integer>0</integer>
						<key>name</key>
						<string>inputMethod</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>0</string>
					</dict>
					<key>1</key>
					<dict>
						<key>default value</key>
						<string></string>
						<key>name</key>
						<string>source</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>1</string>
					</dict>
					<key>2</key>
					<dict>
						<key>default value</key>
						<false/>
						<key>name</key>
						<string>CheckedForUserDefaultShell</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>2</string>
					</dict>
					<key>3</key>
					<dict>
						<key>default value</key>
						<string></string>
						<key>name</key>
						<string>COMMAND_STRING</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>3</string>
					</dict>
					<key>4</key>
					<dict>
						<key>default value</key>
						<string>/bin/sh</string>
						<key>name</key>
						<string>shell</string>
						<key>required</key>
						<string>0</string>
						<key>type</key>
						<string>0</string>
						<key>uuid</key>
						<string>4</string>
					</dict>
				</dict>
			</dict>
		</dict>
	</array>
	<key>connectors</key>
	<dict/>
	<key>variables</key>
	<array/>
	<key>workflowMetaData</key>
	<dict>
		<key>serviceApplicationBundleID</key>
		<string>com.apple.finder</string>
		<key>serviceApplicationPath</key>
		<string>/System/Library/CoreServices/Finder.app</string>
		<key>serviceInputTypeIdentifier</key>
		<string>com.apple.Automator.fileSystemObject</string>
		<key>serviceOutputTypeIdentifier</key>
		<string>com.apple.Automator.nothing</string>
		<key>serviceProcessesInput</key>
		<integer>0</integer>
		<key>workflowTypeIdentifier</key>
		<string>com.apple.Automator.servicesMenu</string>
	</dict>
</dict>
</plist>
EOF
echo "✓ Generated document.wflow"

# 6. Refresh Services registration
echo "Refreshing macOS services database..."
/System/Library/CoreServices/pbs -update

echo "🎉 OptiFile successfully installed!"
echo "Right-click any PDF or Image in Finder to see 'OptiFile'!"
