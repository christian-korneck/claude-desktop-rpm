# Claude Desktop - rpm for Fedora Linux (amd64, arm64)& Asahi Fedora Linux (arm64)

An RPM spec file that downloads and repackages the Claude Desktop Windows Electron app to run natively on Fedora Linux.

Status: Works well for me on Fedora Asahi 42 aarch64 (as of 1.1.2321 / 08-Feb-2026). Claude Code and MCPs are working. Other Fedora and EL versions and x86_64 are likely working, too but are only lightly tested as I work on a Macbook (feedback appreciated).

I aim to update this repo at least once per month for new Claude Desktop versions.

## Build requirements

prereqs for building:

```
sudo dnf install rpmdevtools p7zip-plugins icoutils nodejs npm desktop-file-utils
```

build the RPM:
```
spectool -g -R claude-desktop.spec
rpmbuild -bb claude-desktop.spec
```
The resulting RPM will be in `~/rpmbuild/RPMS/$ARCH/` and can get installed with:

```
ARCH=$(uname -m)
sudo dnf install ~/rpmbuild/RPMS/$ARCH/claude-desktop-*.rpm
```

## Alternative: Use `mock`

The `mock` tool provides a sandbox that allows building rpms in a clean chroot without polluting the host. It also allows to target different distro versions.

prereqs for building:

```
sudo dnf install mock rpmdevtools
```
build the RPM:

```
. /etc/os-release
OS=$ID OS_VERSION=${VERSION_ID%%.*} ARCH=$(uname -m)

spectool -g -R claude-desktop.spec

mock -r $OS-$OS_VERSION-$ARCH --enable-network --spec claude-desktop.spec --sources ~/rpmbuild/SOURCES/
```

The `--enable-network` flag is required because `%prep` runs `npm install` to fetch electron and asar.

The resulting RPM will be in `/var/lib/mock/$OS-$OS_VERSION-$ARCH/result/` and can get installed with:

```
sudo dnf install /var/lib/mock/$OS-$OS_VERSION-$ARCH/result/claude-desktop-*.rpm
```

## Disclaimer

This is an educational project. Use at your own risk. The closed-source Claude Desktop binaries are not part of this repo and if you want to use them be aware of the terms and licenses that apply.
