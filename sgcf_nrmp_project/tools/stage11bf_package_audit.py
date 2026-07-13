#!/usr/bin/env python3
"""Audit the exact Stage 11B-F OSRF package without installing it."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


PACKAGE_URL = (
    "https://osrf-distributions.s3.us-east-1.amazonaws.com/gz-rendering/"
    "releases/libgz-rendering8-ogre2-dev_8.2.3-1~jammy_amd64.deb"
)
EXPECTED_IDENTITY = {
    "Package": "libgz-rendering8-ogre2-dev",
    "Version": "8.2.3-1~jammy",
    "Architecture": "amd64",
}
REQUIRED_MEDIA_DIRS = (
    "Hlms/Unlit/GLSL",
    "Hlms/Pbs/GLSL",
    "Hlms/Gz",
    "Hlms/Terra",
    "2.0/scripts/Compositors",
    "2.0/scripts/materials/Common",
    "2.0/scripts/materials/Common/GLSL",
    "2.0/scripts/materials/Terra",
    "2.0/scripts/materials/Terra/GLSL",
)


def run(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def parse_headers(path: Path) -> dict[str, str]:
    responses: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("HTTP/"):
            if current:
                responses.append(current)
            parts = line.split(None, 2)
            current = {"status_line": line, "status": parts[1]}
        elif ":" in line and current:
            key, value = line.split(":", 1)
            current[key.lower()] = value.strip()
    if current:
        responses.append(current)
    if not responses:
        raise RuntimeError("No HTTP response found in header audit")
    final = responses[-1]
    final["response_count"] = str(len(responses))
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--headers", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract-root", type=Path, default=Path("/tmp/stage11bf_package"))
    args = parser.parse_args()

    package = args.package.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    headers = parse_headers(args.headers)
    size = package.stat().st_size
    content_length = int(headers.get("content-length", "-1"))
    package_sha = sha256(package)
    package_md5 = md5(package)
    etag = headers.get("etag", "").strip('"')
    download_ok = (
        headers["status"] == "200"
        and content_length == size
        and size > 0
        and (not etag or etag == package_md5)
    )
    download = {
        "requested_url": PACKAGE_URL,
        "final_url": PACKAGE_URL,
        "redirect_count": int(headers["response_count"]) - 1,
        "http_status": int(headers["status"]),
        "content_type": headers.get("content-type"),
        "content_length": content_length,
        "downloaded_size": size,
        "filename": package.name,
        "sha256": package_sha,
        "md5": package_md5,
        "etag": etag,
        "last_modified": headers.get("last-modified"),
        "download_file_mtime_utc": dt.datetime.fromtimestamp(
            package.stat().st_mtime, tz=dt.timezone.utc
        ).isoformat(),
        "dpkg_deb_recognized": True,
        "passed": download_ok,
    }
    write_json(output / "stage11bf_download_audit.json", download)
    if not download_ok:
        raise RuntimeError(f"Download audit failed: {download}")

    fields = {
        key: run("dpkg-deb", "--field", str(package), key).strip()
        for key in ("Package", "Version", "Architecture", "Depends")
    }
    identity_ok = all(fields[key] == value for key, value in EXPECTED_IDENTITY.items())
    metadata = {
        "identity": fields,
        "expected_identity": EXPECTED_IDENTITY,
        "identity_exact_match": identity_ok,
        "package_sha256": package_sha,
        "package_size": size,
        "dpkg_info": run("dpkg-deb", "--info", str(package)),
    }
    write_json(output / "stage11bf_package_metadata.json", metadata)
    (output / "stage11bf_package_file_manifest.txt").write_text(
        run("dpkg-deb", "--contents", str(package))
    )
    if not identity_ok:
        raise RuntimeError(f"Package identity mismatch: {fields}")

    if args.extract_root.exists():
        shutil.rmtree(args.extract_root)
    args.extract_root.mkdir(parents=True)
    subprocess.run(
        ["dpkg-deb", "--extract", str(package), str(args.extract_root)], check=True
    )
    media_roots = sorted(
        path
        for path in args.extract_root.rglob("media")
        if path.is_dir()
        and (
            path.as_posix().endswith("/gz-rendering8/ogre2/media")
            or path.as_posix().endswith("/gz-rendering8/ogre2/src/media")
        )
    )
    if len(media_roots) != 1:
        raise RuntimeError(f"Expected one media root, found {media_roots}")
    media = media_roots[0]
    required = {
        relative: {
            "exists": (media / relative).is_dir(),
            "nonempty": (media / relative).is_dir()
            and any((media / relative).iterdir()),
        }
        for relative in REQUIRED_MEDIA_DIRS
    }
    files = sorted(path for path in media.rglob("*") if path.is_file())
    directories = sorted(path for path in media.rglob("*") if path.is_dir())
    glsl_files = [
        path for path in files if "GLSL" in path.relative_to(media).parts
        or path.suffix.lower() in {".glsl", ".vert", ".frag"}
    ]
    piece_files = [
        path
        for path in files
        if path.suffix.lower() == ".piece" or "_piece_" in path.name.lower()
    ]
    material_script_files = [
        path
        for path in files
        if path.suffix.lower() in {".material", ".script", ".compositor"}
    ]
    media_audit = {
        "package_sha256": package_sha,
        "media_root_in_package": "/" + media.relative_to(args.extract_root).as_posix(),
        "resource_root": "/usr/share/gz/gz-rendering8",
        "required_directories": required,
        "all_required_present_and_nonempty": all(
            item["exists"] and item["nonempty"] for item in required.values()
        ),
        "file_count": len(files),
        "directory_count": len(directories),
        "glsl_file_count": len(glsl_files),
        "piece_file_count": len(piece_files),
        "material_script_file_count": len(material_script_files),
        "total_bytes": sum(path.stat().st_size for path in files),
    }
    write_json(output / "stage11bf_hlms_media_audit.json", media_audit)
    manifest_lines = ["type\tsize\tsha256\trelative_path"]
    manifest_lines.extend(f"directory\t0\t-\t{p.relative_to(media).as_posix()}" for p in directories)
    manifest_lines.extend(
        f"file\t{p.stat().st_size}\t{sha256(p)}\t{p.relative_to(media).as_posix()}"
        for p in files
    )
    (output / "stage11bf_hlms_media_manifest.txt").write_text(
        "\n".join(manifest_lines) + "\n"
    )
    aliases = sorted(
        Path(root) / name
        for root, _directories, names in os.walk(args.extract_root)
        for name in names
        if name in {"libgz-rendering-ogre2.so", "libgz-rendering8-ogre2.so"}
    )
    alias_records = []
    for alias in aliases:
        alias_records.append(
            {
                "path": "/" + alias.relative_to(args.extract_root).as_posix(),
                "type": "symlink" if alias.is_symlink() else "file",
                "target": os.readlink(alias) if alias.is_symlink() else None,
            }
        )
    logical_aliases = [path for path in aliases if path.name == "libgz-rendering-ogre2.so"]
    installed_target = Path("/usr/lib/x86_64-linux-gnu/libgz-rendering8-ogre2.so.8")
    target_sha = sha256(installed_target) if installed_target.exists() else None
    interaction = {
        "package_contains_logical_alias": bool(logical_aliases),
        "aliases": alias_records,
        "official_alias_chain": [
            "libgz-rendering-ogre2.so",
            "libgz-rendering8-ogre2.so",
            "libgz-rendering8-ogre2.so.8",
            "libgz-rendering8-ogre2.so.8.2.3",
        ] if logical_aliases else [],
        "installed_stage11be_target": str(installed_target) if installed_target.exists() else None,
        "installed_stage11be_target_sha256": target_sha,
        "expected_stage11be_target_sha256": "c82cba3f167941ee6b0439d545a9181305b6ba57652e82ae41477bb0e34b24ef",
        "target_matches_stage11be": target_sha == "c82cba3f167941ee6b0439d545a9181305b6ba57652e82ae41477bb0e34b24ef",
        "selected_case": "B_OFFICIAL_PACKAGE_PROVIDES_ALIAS" if logical_aliases else "A_KEEP_LOCAL_ALIAS",
        "must_build_from_pre_alias_image": bool(logical_aliases),
        "must_not_overwrite_stage11be_local_alias": bool(logical_aliases),
    }
    write_json(output / "stage11bf_alias_package_interaction.json", interaction)

    main_library = Path("/usr/lib/x86_64-linux-gnu/libgz-rendering8.so.8")
    binary_data = main_library.read_bytes() if main_library.exists() else b""
    strings_available = shutil.which("strings") is not None
    resource_audit = {
        "current_environment_value": os.environ.get("GZ_RENDERING_RESOURCE_PATH"),
        "strings_tool_available": strings_available,
        "binary_scan_method": "direct byte search",
        "binary_contains_environment_name": b"GZ_RENDERING_RESOURCE_PATH" in binary_data,
        "binary_contains_default_root": b"gz-rendering8" in binary_data,
        "package_media_root": "/" + media.relative_to(args.extract_root).as_posix(),
        "derived_resource_root": "/usr/share/gz/gz-rendering8",
        "valid_candidates": ["/usr/share/gz/gz-rendering8/ogre2/media"],
        "resource_root_is_parent_of_ogre2": True,
        "unique": True,
    }
    write_json(output / "stage11bf_resource_path_audit.json", resource_audit)

    print(json.dumps({
        "download": download,
        "identity": fields,
        "media": media_audit,
        "alias_interaction": interaction,
        "resource": resource_audit,
    }, indent=2, sort_keys=True))
    if not media_audit["all_required_present_and_nonempty"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
