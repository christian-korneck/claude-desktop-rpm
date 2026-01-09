#!/bin/bash
set -e

# Update this URL when a new version of Claude Desktop is released
CLAUDE_DOWNLOAD_URL="https://downloads.claude.ai/releases/win32/arm64/1.0.2768/Claude-21341c944a9d74880b52a77c4f1522f47f52d0da.exe"

# Check for Fedora-based system
if [ ! -f "/etc/fedora-release" ]; then
    echo "❌ This script requires a Fedora-based Linux distribution"
    exit 1
fi

# Check for root/sudo
if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo to install dependencies"
    exit 1
fi

# Print system information
echo "System Information:"
echo "Distribution: $(cat /etc/os-release | grep "PRETTY_NAME" | cut -d'"' -f2)"
echo "Fedora version: $(cat /etc/fedora-release)"

# Function to check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo "❌ $1 not found"
        return 1
    else
        echo "✓ $1 found"
        return 0
    fi
}

# Check and install dependencies
echo "Checking dependencies..."
DEPS_TO_INSTALL=""

# Check system package dependencies
for cmd in 7z wget wrestool icotool convert npx rpm rpmbuild; do
    if ! check_command "$cmd"; then
        case "$cmd" in
            "7z")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL p7zip-plugins"
                ;;
            "wget")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL wget"
                ;;
            "wrestool"|"icotool")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL icoutils"
                ;;
            "convert")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL ImageMagick"
                ;;
            "npx")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL nodejs npm"
                ;;
            "rpm")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL rpm"
                ;;
            "rpmbuild")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL rpmbuild"
                ;;
            "curl")
                DEPS_TO_INSTALL="$DEPS_TO_INSTALL curl"
        esac
    fi
done

# Install system dependencies if any
if [ ! -z "$DEPS_TO_INSTALL" ]; then
    echo "Installing system dependencies: $DEPS_TO_INSTALL"
    dnf install -y $DEPS_TO_INSTALL
    echo "System dependencies installed successfully"
fi

# Install electron globally via npm if not present
if ! check_command "electron"; then
    echo "Installing electron via npm..."
    npm install -g electron
    if ! check_command "electron"; then
        echo "Failed to install electron. Please install it manually:"
        echo "sudo npm install -g electron"
        exit 1
    fi
    echo "Electron installed successfully"
fi

# Extract version from the URL path (version is in the URL: .../arm64/VERSION/...)
VERSION=$(echo "$CLAUDE_DOWNLOAD_URL" | grep -oP '(?<=arm64/)[^/]+')
PACKAGE_NAME="claude-desktop"
# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    aarch64)
        LIB_DIR="lib64"
        RPM_ARCH="aarch64"
        ;;
    x86_64)
        LIB_DIR="lib64"
        RPM_ARCH="x86_64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac
MAINTAINER="Claude Desktop Linux Maintainers"
DESCRIPTION="Claude Desktop for Linux"

# Create working directories
WORK_DIR="$(pwd)/build"
FEDORA_ROOT="$WORK_DIR/fedora-package"
INSTALL_DIR="$FEDORA_ROOT/usr"

# Clean previous build
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
mkdir -p "$FEDORA_ROOT/FEDORA"
mkdir -p "$INSTALL_DIR/lib/$PACKAGE_NAME"
mkdir -p "$INSTALL_DIR/share/applications"
mkdir -p "$INSTALL_DIR/share/icons"
mkdir -p "$INSTALL_DIR/bin"

# Install asar if needed
if ! command -v asar > /dev/null 2>&1; then
    echo "Installing asar package globally..."
    npm install -g asar
fi

# Download Claude Windows installer
echo "📥 Downloading Claude Desktop installer..."
CLAUDE_EXE="$WORK_DIR/Claude-installer.exe"
if ! curl -o "$CLAUDE_EXE" "$CLAUDE_DOWNLOAD_URL"; then
    echo "❌ Failed to download Claude Desktop installer"
    exit 1
fi
echo "✓ Download complete"

# Extract resources
echo "📦 Extracting resources..."
cd "$WORK_DIR"
if ! 7z x -y "$CLAUDE_EXE"; then
    echo "❌ Failed to extract installer"
    exit 1
fi

if ! 7z x -y "AnthropicClaude-$VERSION-full.nupkg"; then
    echo "❌ Failed to extract nupkg"
    exit 1
fi
echo "✓ Resources extracted"

# Extract and convert icons
echo "🎨 Processing icons..."
if ! wrestool -x -t 14 "lib/net45/claude.exe" -o claude.ico; then
    echo "❌ Failed to extract icons from exe"
    exit 1
fi

if ! icotool -x claude.ico; then
    echo "❌ Failed to convert icons"
    exit 1
fi
echo "✓ Icons processed"

# Map icon sizes to their corresponding extracted files
declare -A icon_files=(
    ["16"]="claude_13_16x16x32.png"
    ["24"]="claude_11_24x24x32.png"
    ["32"]="claude_10_32x32x32.png"
    ["48"]="claude_8_48x48x32.png"
    ["64"]="claude_7_64x64x32.png"
    ["256"]="claude_6_256x256x32.png"
)

# Install icons
for size in 16 24 32 48 64 256; do
    icon_dir="$INSTALL_DIR/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$icon_dir"
    if [ -f "${icon_files[$size]}" ]; then
        echo "Installing ${size}x${size} icon..."
        install -Dm 644 "${icon_files[$size]}" "$icon_dir/claude-desktop.png"
    else
        echo "Warning: Missing ${size}x${size} icon"
    fi
done

# Process app.asar
mkdir -p electron-app
cp "lib/net45/resources/app.asar" electron-app/
cp -r "lib/net45/resources/app.asar.unpacked" electron-app/

cd electron-app
npx asar extract app.asar app.asar.contents

# Replace native module with stub implementation
echo "Creating stub native module..."
mkdir -p app.asar.contents/node_modules/@ant/claude-native
cat > app.asar.contents/node_modules/@ant/claude-native/index.js << EOF
// Stub implementation of claude-native using KeyboardKey enum values
const KeyboardKey = {
  Backspace: 43,
  Tab: 280,
  Enter: 261,
  Shift: 272,
  Control: 61,
  Alt: 40,
  CapsLock: 56,
  Escape: 85,
  Space: 276,
  PageUp: 251,
  PageDown: 250,
  End: 83,
  Home: 154,
  LeftArrow: 175,
  UpArrow: 282,
  RightArrow: 262,
  DownArrow: 81,
  Delete: 79,
  Meta: 187
};

Object.freeze(KeyboardKey);

module.exports = {
  getWindowsVersion: () => "10.0.0",
  setWindowEffect: () => {},
  removeWindowEffect: () => {},
  getIsMaximized: () => false,
  flashFrame: () => {},
  clearFlashFrame: () => {},
  showNotification: () => {},
  setProgressBar: () => {},
  clearProgressBar: () => {},
  setOverlayIcon: () => {},
  clearOverlayIcon: () => {},
  KeyboardKey
};
EOF

# Copy Tray icons and other resources
mkdir -p app.asar.contents/resources
cp ../lib/net45/resources/Tray* app.asar.contents/resources/

# Copy i18n resources
mkdir -p app.asar.contents/resources/i18n
cp ../lib/net45/resources/*.json app.asar.contents/resources/i18n/

# Copy other resources (fonts, images, etc.)
cp -r ../lib/net45/resources/fonts app.asar.contents/resources/ 2>/dev/null || true
cp ../lib/net45/resources/*.png app.asar.contents/resources/ 2>/dev/null || true
cp ../lib/net45/resources/*.clod app.asar.contents/resources/ 2>/dev/null || true

# Patch for Linux: Fix window frame/titlebar
# The app uses titleBarStyle:"hidden" which doesn't work properly on Linux
# Change it to show native window decorations
echo "Patching for Linux window decorations..."
sed -i 's/titleBarStyle:"hidden"/titleBarStyle:"default"/g' app.asar.contents/.vite/build/index.js
sed -i 's/titleBarStyle:"hiddenInset"/titleBarStyle:"default"/g' app.asar.contents/.vite/build/index.js

# Patch for Linux: Fix Claude Code platform detection
# The getPlatform() function only handles darwin and win32, but linux-arm64 binaries exist
echo "Patching Claude Code platform detection for Linux..."
sed -i 's/if(process\.platform==="darwin")return e==="arm64"?"darwin-arm64":"darwin-x64";if(process\.platform==="win32")return"win32-x64";throw new Error/if(process.platform==="darwin")return e==="arm64"?"darwin-arm64":"darwin-x64";if(process.platform==="win32")return"win32-x64";if(process.platform==="linux")return e==="arm64"?"linux-arm64":"linux-x64";throw new Error/g' app.asar.contents/.vite/build/index.js

# Patch for Linux: Fix origin validation for local file:// URLs
# The app validates IPC origins and requires isPackaged===true for file: protocol
# Since we run via electron command, isPackaged is false, so we need to allow file: regardless
echo "Patching origin validation for file:// URLs..."
sed -i 's/e\.protocol==="file:"&&oe\.app\.isPackaged===!0/e.protocol==="file:"/g' app.asar.contents/.vite/build/index.js

# Patch for Linux: Add stub handlers for ClaudeVM
# These handlers are not registered on Linux but the renderer keeps calling them
echo "Patching ClaudeVM handlers..."
sed -i 's/t\.ipc\.handle("\$eipc_message\$_6a039d75-594a-4e0d-aad1-af47761a02ae_\$_claude\.web_\$_ClaudeCode_\$_getStatus"/t.ipc.handle("\$eipc_message\$_6a039d75-594a-4e0d-aad1-af47761a02ae_\$_claude.web_\$_ClaudeVM_\$_getDownloadStatus",async()=>null),t.ipc.handle("\$eipc_message\$_6a039d75-594a-4e0d-aad1-af47761a02ae_\$_claude.web_\$_ClaudeVM_\$_getRunningStatus",async()=>null),t.ipc.handle("\$eipc_message\$_6a039d75-594a-4e0d-aad1-af47761a02ae_\$_claude.web_\$_ClaudeCode_\$_getStatus"/g' app.asar.contents/.vite/build/index.js

# Repackage app.asar
npx asar pack app.asar.contents app.asar

# Create native module with keyboard constants
mkdir -p "$INSTALL_DIR/lib/$PACKAGE_NAME/app.asar.unpacked/node_modules/@ant/claude-native"
cat > "$INSTALL_DIR/lib/$PACKAGE_NAME/app.asar.unpacked/node_modules/@ant/claude-native/index.js" << EOF
// Stub implementation of claude-native using KeyboardKey enum values
const KeyboardKey = {
  Backspace: 43,
  Tab: 280,
  Enter: 261,
  Shift: 272,
  Control: 61,
  Alt: 40,
  CapsLock: 56,
  Escape: 85,
  Space: 276,
  PageUp: 251,
  PageDown: 250,
  End: 83,
  Home: 154,
  LeftArrow: 175,
  UpArrow: 282,
  RightArrow: 262,
  DownArrow: 81,
  Delete: 79,
  Meta: 187
};

Object.freeze(KeyboardKey);

module.exports = {
  getWindowsVersion: () => "10.0.0",
  setWindowEffect: () => {},
  removeWindowEffect: () => {},
  getIsMaximized: () => false,
  flashFrame: () => {},
  clearFlashFrame: () => {},
  showNotification: () => {},
  setProgressBar: () => {},
  clearProgressBar: () => {},
  setOverlayIcon: () => {},
  clearOverlayIcon: () => {},
  KeyboardKey
};
EOF

# Copy app files
cp app.asar "$INSTALL_DIR/lib/$PACKAGE_NAME/"
cp -r app.asar.unpacked "$INSTALL_DIR/lib/$PACKAGE_NAME/"

# Create desktop entry
cat > "$INSTALL_DIR/share/applications/claude-desktop.desktop" << EOF
[Desktop Entry]
Name=Claude
Exec=claude-desktop %u
Icon=claude-desktop
Type=Application
Terminal=false
Categories=Office;Utility;
MimeType=x-scheme-handler/claude;
StartupWMClass=claude
EOF

# Create launcher script
cat > "$INSTALL_DIR/bin/claude-desktop" << EOF
#!/bin/bash
electron /usr/${LIB_DIR}/claude-desktop/app.asar "\$@"
EOF
chmod +x "$INSTALL_DIR/bin/claude-desktop"

# Create RPM spec file
cat > "$WORK_DIR/claude-desktop.spec" << EOF
Name:           claude-desktop
Version:        ${VERSION}
Release:        1%{?dist}
Summary:        Claude Desktop for Linux
License:        Proprietary
URL:            https://www.anthropic.com
BuildArch:      ${RPM_ARCH}
Requires:       nodejs >= 12.0.0, npm, p7zip

%description
Claude is an AI assistant from Anthropic.
This package provides the desktop interface for Claude.

%install
mkdir -p %{buildroot}/usr/lib64/%{name}
mkdir -p %{buildroot}/usr/bin
mkdir -p %{buildroot}/usr/share/applications
mkdir -p %{buildroot}/usr/share/icons

# Copy files from the INSTALL_DIR
cp -r ${INSTALL_DIR}/lib/%{name}/* %{buildroot}/usr/lib64/%{name}/
cp -r ${INSTALL_DIR}/bin/* %{buildroot}/usr/bin/
cp -r ${INSTALL_DIR}/share/applications/* %{buildroot}/usr/share/applications/
cp -r ${INSTALL_DIR}/share/icons/* %{buildroot}/usr/share/icons/

%files
%{_bindir}/claude-desktop
%{_libdir}/%{name}
%{_datadir}/applications/claude-desktop.desktop
%{_datadir}/icons/hicolor/*/apps/claude-desktop.png

%post
# Update icon caches
gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor || :
# Force icon theme cache rebuild
touch -h %{_datadir}/icons/hicolor >/dev/null 2>&1 || :
update-desktop-database %{_datadir}/applications || :

%changelog
* $(LC_ALL=C date '+%a %b %d %Y') ${MAINTAINER} ${VERSION}-1
- Initial package
EOF

# Build RPM package
echo "📦 Building RPM package..."
mkdir -p "${WORK_DIR}"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

RPM_FILE="$(pwd)/claude-desktop-${VERSION}-1.$(uname -m).rpm"
if ! rpmbuild -bb \
    --define "_topdir ${WORK_DIR}" \
    --define "_rpmdir $(pwd)" \
    "${WORK_DIR}/claude-desktop.spec"; then
    echo "❌ Failed to build RPM package"
    exit 1
fi
