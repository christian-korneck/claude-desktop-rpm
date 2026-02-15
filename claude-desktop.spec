%global claude_version 1.1.3189
%global claude_hash    1b7b58b8b5060b7d5d19c6863d8f0caef4f0fc97
%global electron_ver   40.4.1

Name:           claude-desktop
Version:        %{claude_version}
Release:        1%{?dist}
Summary:        Claude Desktop for Linux
License:        Proprietary
URL:            https://claude.com/download/

Source0:        https://downloads.claude.ai/releases/win32/arm64/%{claude_version}/Claude-%{claude_hash}.exe
Source1:        https://downloads.claude.ai/releases/darwin/universal/%{claude_version}/Claude-%{claude_hash}.dmg

ExclusiveArch:  aarch64 x86_64
AutoReqProv:    no

BuildRequires:  p7zip-plugins
BuildRequires:  icoutils
BuildRequires:  nodejs >= 22
BuildRequires:  npm
BuildRequires:  desktop-file-utils

Requires:       gtk3
Requires:       nss
Requires:       alsa-lib
Requires:       cups-libs
Requires:       dbus-libs
Requires:       mesa-libgbm

%description
Claude Desktop for Linux.

# ---------------------------------------------------------------------------
# %prep — download tools, extract installer, patch app
# ---------------------------------------------------------------------------
%prep
# --- npm install asar + electron locally -----------------------------------
mkdir -p %{_builddir}/_tools
cd %{_builddir}/_tools
npm install --no-save @electron/asar electron@%{electron_ver}
export PATH="%{_builddir}/_tools/node_modules/.bin:$PATH"

# --- extract installer -----------------------------------------------------
cd %{_builddir}
cp %{SOURCE0} Claude-installer.exe
7z x -y Claude-installer.exe
7z x -y AnthropicClaude-%{claude_version}-full.nupkg

# --- extract claude-ssh binaries from macOS DMG ----------------------------
# 7z returns exit code 2 on HFS+ "Headers Error" but extracts fine
7z x -y %{SOURCE1} -o_macos_dmg || true
test -f _macos_dmg/Claude/Claude.app/Contents/Resources/claude-ssh/version.txt
cp -r _macos_dmg/Claude/Claude.app/Contents/Resources/claude-ssh .

# --- extract icons ----------------------------------------------------------
wrestool -x -t 14 lib/net45/claude.exe -o claude.ico
icotool -x claude.ico

# --- extract and patch app.asar --------------------------------------------
asar extract lib/net45/resources/app.asar app.asar.contents
cp -r lib/net45/resources/app.asar.unpacked .

# copy resources into asar contents
mkdir -p app.asar.contents/resources/i18n
cp lib/net45/resources/Tray* app.asar.contents/resources/
cp lib/net45/resources/*.json app.asar.contents/resources/i18n/
cp -r lib/net45/resources/fonts app.asar.contents/resources/ 2>/dev/null || :
cp lib/net45/resources/*.png   app.asar.contents/resources/ 2>/dev/null || :
cp lib/net45/resources/*.clod  app.asar.contents/resources/ 2>/dev/null || :

# native module stub
mkdir -p app.asar.contents/node_modules/@ant/claude-native
cat > app.asar.contents/node_modules/@ant/claude-native/index.js << 'STUB'
const KeyboardKey = {
  Backspace: 43, Tab: 280, Enter: 261, Shift: 272, Control: 61,
  Alt: 40, CapsLock: 56, Escape: 85, Space: 276, PageUp: 251,
  PageDown: 250, End: 83, Home: 154, LeftArrow: 175, UpArrow: 282,
  RightArrow: 262, DownArrow: 81, Delete: 79, Meta: 187
};
Object.freeze(KeyboardKey);
class AuthRequest {
  static isAvailable() { return false; }
  start() { return Promise.reject(new Error("Not available")); }
  cancel() {}
}
module.exports = {
  getWindowsVersion: () => "10.0.0",
  getWindowsElevationType: () => "default",
  getCurrentPackageFamilyName: () => "",
  getActiveWindowHandle: () => null,
  getAppInfoForFile: () => null,
  focusWindow: () => {},
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
  readCfPrefValue: () => null,
  readPlistValue: () => null,
  readRegistryValues: () => [],
  writeRegistryValue: () => {},
  enableWindowsOptionalFeature: () => Promise.resolve({ success: false }),
  AuthRequest,
  KeyboardKey
};
STUB

# --- sed patches on index.js -----------------------------------------------
_idx=app.asar.contents/.vite/build/index.js

# native window decorations
sed -i 's/titleBarStyle:"hidden"/titleBarStyle:"default"/g'      "$_idx"
sed -i 's/titleBarStyle:"hiddenInset"/titleBarStyle:"default"/g' "$_idx"

# Linux platform detection for Claude Code
sed -i 's/if(process\.platform==="darwin")return e==="arm64"?"darwin-arm64":"darwin-x64";if(process\.platform==="win32")return"win32-x64";throw new Error/if(process.platform==="darwin")return e==="arm64"?"darwin-arm64":"darwin-x64";if(process.platform==="win32")return"win32-x64";if(process.platform==="linux")return e==="arm64"?"linux-arm64":"linux-x64";throw new Error/g' "$_idx"

# file:// origin validation
sed -i 's/e\.protocol==="file:"&&[a-zA-Z]*\.app\.isPackaged===!0/e.protocol==="file:"/g' "$_idx"

# quit on window close when tray is disabled (upstream only checks win32)
sed -i 's/if(Ci&&!mn("menuBarEnabled"))/if((Ci||process.platform==="linux")\&\&!mn("menuBarEnabled"))/' "$_idx"

# repack
asar pack app.asar.contents app.asar

# ---------------------------------------------------------------------------
# %build — nothing to compile
# ---------------------------------------------------------------------------
%build

# ---------------------------------------------------------------------------
# %install
# ---------------------------------------------------------------------------
%install
export PATH="%{_builddir}/_tools/node_modules/.bin:$PATH"

_elecdir=%{_builddir}/_tools/node_modules/electron/dist
_dest=%{buildroot}%{_libdir}/%{name}

# --- electron runtime -------------------------------------------------------
mkdir -p "$_dest"/electron
cp -r "$_elecdir"/* "$_dest"/electron/
# strip non-en-US locales (~41 MB)
find "$_dest"/electron/locales -type f ! -name 'en-US.pak' -delete
# remove chromium license blob (~15 MB)
rm -f "$_dest"/electron/LICENSES.chromium.html

# --- app.asar ---------------------------------------------------------------
install -Dm644 %{_builddir}/app.asar "$_dest"/app.asar

# --- app.asar.unpacked (from installer, with native stub overlay) -----------
cp -r %{_builddir}/app.asar.unpacked "$_dest"/
mkdir -p "$_dest"/app.asar.unpacked/node_modules/@ant/claude-native
cp %{_builddir}/app.asar.contents/node_modules/@ant/claude-native/index.js \
   "$_dest"/app.asar.unpacked/node_modules/@ant/claude-native/index.js
# remove Windows .node binary
rm -f "$_dest"/app.asar.unpacked/node_modules/@ant/claude-native/claude-native-binding.node

# --- claude-ssh binaries (from macOS DMG, for SSH remote feature) -----------
install -Dm755 %{_builddir}/claude-ssh/claude-ssh-linux-arm64 "$_dest"/electron/resources/claude-ssh/claude-ssh-linux-arm64
install -Dm755 %{_builddir}/claude-ssh/claude-ssh-linux-amd64 "$_dest"/electron/resources/claude-ssh/claude-ssh-linux-amd64
install -Dm644 %{_builddir}/claude-ssh/version.txt            "$_dest"/electron/resources/claude-ssh/version.txt

# --- launcher script --------------------------------------------------------
mkdir -p %{buildroot}%{_bindir}
cat > %{buildroot}%{_bindir}/claude-desktop << 'LAUNCHER'
#!/bin/bash
exec %{_libdir}/claude-desktop/electron/electron %{_libdir}/claude-desktop/app.asar "$@"
LAUNCHER
chmod 0755 %{buildroot}%{_bindir}/claude-desktop

# --- desktop file -----------------------------------------------------------
mkdir -p %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/claude-desktop.desktop << 'DESKTOP'
[Desktop Entry]
Name=Claude
Exec=claude-desktop %u
Icon=claude-desktop
Type=Application
Terminal=false
Categories=Office;Utility;
MimeType=x-scheme-handler/claude;
StartupWMClass=claude
DESKTOP
desktop-file-install \
    --dir=%{buildroot}%{_datadir}/applications \
    %{buildroot}%{_datadir}/applications/claude-desktop.desktop

# --- icons -------------------------------------------------------------------
for size in 16 24 32 48 64 256; do
    _icon=$(ls %{_builddir}/claude_*_${size}x${size}x32.png 2>/dev/null | head -1)
    if [ -n "$_icon" ]; then
        install -Dm644 "$_icon" \
            %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/claude-desktop.png
    fi
done

# ---------------------------------------------------------------------------
%files
%{_bindir}/claude-desktop
%{_libdir}/%{name}
%{_datadir}/applications/claude-desktop.desktop
%{_datadir}/icons/hicolor/*/apps/claude-desktop.png

%post
gtk-update-icon-cache -f -t %{_datadir}/icons/hicolor || :
touch -h %{_datadir}/icons/hicolor >/dev/null 2>&1 || :
update-desktop-database %{_datadir}/applications || :

%changelog
* Sun Feb 15 2026 Claude Desktop Linux Maintainers - 1.1.3189-1
- update to Claude Desktop 1.1.3189
- update Electron from 39.5.0 to 40.4.1
- add claude-ssh binaries from macOS DMG for SSH remote feature

* Thu Feb 12 2026 Claude Desktop Linux Maintainers - 1.1.2685-1
- update to Claude Desktop 1.1.2685

* Sun Feb 08 2026 Claude Desktop Linux Maintainers - 1.1.2321-1
- update to Claude Desktop 1.1.2321
