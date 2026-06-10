%global claude_version 1.11847.5
%global claude_hash    9692f0b44ffa0158a501a91309e361c0d48ed8e4
%global electron_ver   41.6.1
%global nodepty_ver    1.1.0-beta34

Name:           claude-desktop
Version:        %{claude_version}
Release:        1%{?dist}
Summary:        Claude Desktop for Linux
License:        Proprietary
URL:            https://claude.com/download/

Source0:        https://downloads.claude.ai/releases/win32/arm64/%{claude_version}/Claude-%{claude_hash}.exe

ExclusiveArch:  aarch64 x86_64
AutoReqProv:    no

BuildRequires:  p7zip-plugins
BuildRequires:  icoutils
BuildRequires:  nodejs >= 22
BuildRequires:  npm
BuildRequires:  desktop-file-utils
# toolchain to compile node-pty from source (Claude Code "run in terminal")
BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  python3

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

# --- build node-pty from source for Linux ----------------------------------
# The Windows installer only ships Windows node-pty binaries, so Claude Code's
# "run in terminal" can't load the module on Linux. Build the same version the
# app bundles (in its own dir with a package.json, so npm doesn't prune the
# electron/asar install above and electron-rebuild can resolve the module tree)
# and rebuild it against the electron ABI we ship.
mkdir -p %{_builddir}/_pty
cd %{_builddir}/_pty
cat > package.json << 'PKG'
{
  "name": "claude-desktop-pty-build",
  "version": "0.0.0",
  "private": true,
  "dependencies": {
    "node-pty": "%{nodepty_ver}",
    "@electron/rebuild": "^4"
  }
}
PKG
npm install
%{_builddir}/_pty/node_modules/.bin/electron-rebuild --force \
    --version %{electron_ver} --module-dir %{_builddir}/_pty --only node-pty
cd %{_builddir}/_tools

# --- extract installer -----------------------------------------------------
cd %{_builddir}
cp %{SOURCE0} Claude-installer.exe
7z x -y Claude-installer.exe
7z x -y AnthropicClaude-%{claude_version}-full.nupkg

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
# ion-dist renderer bundle (served via custom protocol from the resources dir)
cp -r lib/net45/resources/ion-dist app.asar.contents/resources/ 2>/dev/null || :

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
  writeRegistryDword: () => {},
  closeOfficeDocument: () => {},
  focusOfficeDocument: () => false,
  getWindowAbove: () => null,
  isHardwareVirtEnabled: () => true,
  isProcessRunning: () => Promise.resolve(false),
  moveWindowBehind: () => {},
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
sed -i 's/if(process\.platform==="darwin")return e==="arm64"?"darwin-arm64":"darwin-x64";if(process\.platform==="win32")return e==="arm64"?"win32-arm64":"win32-x64";throw new Error/if(process.platform==="darwin")return e==="arm64"?"darwin-arm64":"darwin-x64";if(process.platform==="win32")return e==="arm64"?"win32-arm64":"win32-x64";if(process.platform==="linux")return e==="arm64"?"linux-arm64":"linux-x64";throw new Error/g' "$_idx"

# file:// origin validation
sed -i 's/e\.protocol==="file:"&&[a-zA-Z]*\.app\.isPackaged===!0/e.protocol==="file:"/g' "$_idx"

# quit on window close when tray is disabled (upstream only checks win32)
sed -i 's/if(Eo&&!ci("menuBarEnabled"))/if((Eo||process.platform==="linux")\&\&!ci("menuBarEnabled"))/' "$_idx"

# disable the system tray entirely (the tray icon is unreliable across Linux DEs,
# e.g. not clickable on KDE Plasma). Force the menuBarEnabled getter to read false so
# no tray is ever created and the window-close handler above quits the app. Anchored on
# the stable "menuBarEnabled" key (not the minified getter) so it survives version bumps;
# the trailing ")" avoids matching the setter/listener which take a second argument.
# Must run AFTER the quit-on-close patch (which matches the literal Ci("menuBarEnabled")).
sed -i 's/[A-Za-z0-9_$]\+("menuBarEnabled")/!1/g' "$_idx"

# repack
# --unpack "*.node" keeps native addons (node-pty's pty.node, claude-native)
# out of the archive and marked unpacked, so they load from app.asar.unpacked
# on disk instead of being extracted to /tmp. Without this the Windows pty.node
# extracted from the installer gets packed in and shadows the Linux build we
# overlay in %install, breaking Claude Code's "run in terminal".
asar pack app.asar.contents app.asar --unpack "*.node"

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

# --- node-pty Linux binary (Claude Code "run in terminal") ------------------
# Only pty.node is needed on Linux; spawn-helper is a macOS-only build target
# and node-pty's native code uses forkpty() directly on Linux.
_ptyrel="$_dest"/app.asar.unpacked/node_modules/node-pty/build/Release
install -Dm755 %{_builddir}/_pty/node_modules/node-pty/build/Release/pty.node "$_ptyrel"/pty.node
# drop the unusable Windows-only binaries shipped in the installer
rm -f "$_ptyrel"/conpty.node "$_ptyrel"/conpty_console_list.node \
      "$_ptyrel"/winpty-agent.exe "$_ptyrel"/winpty.dll

# --- claude-ssh binaries ----------------------------------------------------
# No longer bundled: as of 1.11187.4 the Windows installer ships no claude-ssh
# directory. The app fetches the platform binary at runtime from
# https://downloads.claude.ai/claude-ssh-releases (claude-ssh.zst), so the SSH
# remote feature self-bootstraps and nothing needs to be installed here.

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
* Tue Jun 10 2026 Claude Desktop Linux Maintainers - 1.11847.5-1
- update to Claude Desktop 1.11847.5

* Tue Jun 09 2026 Claude Desktop Linux Maintainers - 1.11187.4-1
- update to Claude Desktop 1.11187.4
- update Electron from 40.4.1 to 41.6.1
- drop bundled claude-ssh binaries (now downloaded at runtime by the app)
- copy new ion-dist resource bundle into the app
- build node-pty for Linux so Claude Code "run in terminal" works
- disable the system tray on Linux (unreliable across desktops; app now quits on window close)

* Sat Feb 21 2026 Claude Desktop Linux Maintainers - 1.1.3918-1
- update to Claude Desktop 1.1.3918

* Fri Feb 20 2026 Claude Desktop Linux Maintainers - 1.1.3770-1
- update to Claude Desktop 1.1.3770
- claude-ssh binaries now included in Windows installer, macOS DMG no longer needed

* Sun Feb 15 2026 Claude Desktop Linux Maintainers - 1.1.3189-1
- update to Claude Desktop 1.1.3189
- update Electron from 39.5.0 to 40.4.1
- add claude-ssh binaries from macOS DMG for SSH remote feature

* Thu Feb 12 2026 Claude Desktop Linux Maintainers - 1.1.2685-1
- update to Claude Desktop 1.1.2685

* Sun Feb 08 2026 Claude Desktop Linux Maintainers - 1.1.2321-1
- update to Claude Desktop 1.1.2321
