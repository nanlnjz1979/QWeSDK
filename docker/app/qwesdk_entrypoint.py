#!/usr/bin/env python3
"""Install the newest valid QWeSDK package before the worker starts.

The package directory can be mounted into the container with
QWESDK_PACKAGE_DIR. Wheels are preferred because the legacy source archive
currently contains a setup.py that refers to a directory outside the archive.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path
from pathlib import PurePosixPath


PACKAGE_NAME = "qwesdk"
DEFAULT_INSTALL_TARGET = Path("/var/lib/qwesdk/python")
VERSION_RE = re.compile(r"^qwesdk-(\d+(?:\.\d+){1,3})(?:-.*)?\.(whl|tar\.gz)$", re.I)


def parse_version(path: Path) -> tuple[int, ...] | None:
    match = VERSION_RE.match(path.name)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def package_kind(path: Path) -> str:
    return "wheel" if path.name.lower().endswith(".whl") else "sdist"


def sdist_contains_package(path: Path) -> bool:
    """Reject the known broken sdist format before invoking pip."""
    if package_kind(path) != "sdist":
        return True
    try:
        import tarfile

        with tarfile.open(path, "r:gz") as archive:
            for name in archive.getnames():
                parts = PurePosixPath(name).parts
                if len(parts) >= 2 and parts[1] == "m":
                    return True
            return False
    except (OSError, tarfile.TarError):
        return False


def get_installed_version(install_target: Path | None = None) -> str | None:
    """Read the SDK version from the writable overlay, not the read-only venv."""
    try:
        if install_target is None:
            return metadata.version(PACKAGE_NAME)
        distributions = metadata.distributions(path=[str(install_target)])
        for distribution in distributions:
            if distribution.metadata.get("Name", "").lower() == PACKAGE_NAME:
                return distribution.version
    except metadata.PackageNotFoundError:
        pass
    return None


def install_package(path: Path, install_target: Path) -> bool:
    print(f"安装 QWeSDK 包: {path}", flush=True)
    install_target.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".qwesdk-install-", dir=install_target))
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-cache-dir",
                "--upgrade",
                "--no-deps",
                "--target",
                str(staging),
                str(path),
            ],
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"安装失败，保留当前已安装版本。退出码: {result.returncode}", flush=True)
            return False

        # pip --target does not uninstall old distributions. Replace only the
        # SDK-owned files after a successful staged install, so a bad wheel
        # cannot leave the writable overlay half-updated.
        for existing in install_target.glob("qwesdk*"):
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
        for existing in (install_target / "m", install_target / "m.py"):
            if existing.is_dir():
                shutil.rmtree(existing)
            elif existing.exists():
                existing.unlink()
        for item in staging.iterdir():
            shutil.move(str(item), str(install_target / item.name))
        return True
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def find_candidates(package_dir: Path) -> list[tuple[tuple[int, ...], int, Path]]:
    candidates = []
    for path in package_dir.iterdir():
        if not path.is_file() or path.suffix not in {".whl", ".gz"}:
            continue
        version = parse_version(path)
        if version is None:
            print(f"跳过无法识别版本的文件: {path.name}", flush=True)
            continue
        if not sdist_contains_package(path):
            print(f"跳过无效源代码包（缺少 m/ 目录）: {path.name}", flush=True)
            continue
        # Lower kind values sort first, so wheel wins over sdist at the same
        # version. This keeps startup independent of filesystem iteration order.
        candidates.append((version, 0 if package_kind(path) == "wheel" else 1, path))
    candidates.sort(key=lambda item: (item[0], -item[1], item[2].name), reverse=True)
    return candidates


def main() -> int:
    package_dir = Path(
        os.environ.get("QWESDK_PACKAGE_DIR", "/app/packages")
    ).resolve()
    if not package_dir.exists():
        # Backward-compatible with the current layout where packages are in /app.
        package_dir = Path("/app")
    install_target = Path(
        os.environ.get("QWESDK_INSTALL_TARGET", str(DEFAULT_INSTALL_TARGET))
    ).resolve()

    candidates = find_candidates(package_dir)
    if not candidates:
        installed_version = get_installed_version(install_target)
        if installed_version:
            print(
                f"{package_dir} 中没有可安装的 QWeSDK 包，继续使用已安装版本 {installed_version}。",
                flush=True,
            )
            return 0
        print(f"{package_dir} 中没有可安装的 QWeSDK 包，且当前环境未安装 QWeSDK。", flush=True)
        return 1

    _, _, package_path = candidates[0]
    local_version = ".".join(str(part) for part in parse_version(package_path))
    installed_version = get_installed_version(install_target)
    print(f"候选包: {package_path.name} ({package_kind(package_path)})", flush=True)
    print(f"当前版本: {installed_version or '未安装'}，候选版本: {local_version}", flush=True)

    if installed_version == local_version:
        print("版本一致，跳过安装。", flush=True)
        return 0

    if not install_package(package_path, install_target):
        return 1 if installed_version is None else 0

    new_version = get_installed_version(install_target)
    if new_version != local_version:
        print(f"安装校验失败，实际版本: {new_version or '未安装'}", flush=True)
        return 1
    print(f"QWeSDK 更新完成: {new_version}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
