from __future__ import annotations

import re
import shutil
import tarfile
import time
import zipfile
from pathlib import Path
from typing import Optional

import requests

CHUNK_SIZE = 1024 * 1024


def ensure_vosk_model(model_path: str, download_url: str, archive_name: str) -> None:
    model_dir = Path(model_path)
    if _is_valid_model_dir(model_dir):
        print(f"[VoiceAssistant] Vosk model found at {model_dir}. Using existing model.")
        return

    if not download_url:
        raise RuntimeError(
            "Vosk model not found and VOSK_MODEL_URL is not set. "
            "Set VOSK_MODEL_URL in config.py or as an environment variable."
        )

    print(f"[VoiceAssistant] Vosk model not found at {model_dir}.")
    print(f"[VoiceAssistant] Downloading model from Google Drive...")

    downloads_dir = Path("models") / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    archive_path = downloads_dir / archive_name

    if archive_path.exists():
        print(f"[VoiceAssistant] Removing existing archive at {archive_path}")
        archive_path.unlink()

    if "drive.google.com" in download_url:
        _download_google_drive(download_url, archive_path, archive_name)
    else:
        _download_file(download_url, archive_path)

    print(f"[VoiceAssistant] Extracting model archive to {model_dir}...")
    extract_dir = downloads_dir / "extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir()

    _extract_archive(archive_path, extract_dir)

    extracted_root = _select_extracted_root(extract_dir)
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    if model_dir.exists():
        shutil.rmtree(model_dir)
    shutil.move(str(extracted_root), str(model_dir))

    print(f"[VoiceAssistant] Extraction complete. Model installed at {model_dir}")
    print(f"[VoiceAssistant] Cleaning up temporary files...")

    try:
        archive_path.unlink()
    except FileNotFoundError:
        pass
    shutil.rmtree(extract_dir, ignore_errors=True)

    print(f"[VoiceAssistant] Cleanup complete.")

    if not _is_valid_model_dir(model_dir):
        raise RuntimeError("Downloaded model does not look like a valid Vosk model directory.")

    print(f"[VoiceAssistant] Model validation successful. Ready to use.")


def _is_valid_model_dir(model_dir: Path) -> bool:
    if not model_dir.is_dir():
        return False
    if not any(model_dir.iterdir()):
        return False
    expected = ("conf", "am", "graph")
    return any((model_dir / entry).exists() for entry in expected)


def _select_extracted_root(extract_dir: Path) -> Path:
    dirs = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(dirs) == 1:
        return dirs[0]
    return extract_dir


def _download_google_drive(url: str, dest_path: Path, archive_name: str) -> None:
    file_id = _extract_gdrive_file_id(url)
    if not file_id:
        folder_id = _extract_gdrive_folder_id(url)
        if folder_id:
            file_id = _resolve_gdrive_folder_file_id(folder_id, archive_name)
        else:
            raise RuntimeError("Could not extract Google Drive file id from URL.")

    session = requests.Session()
    
    # Try direct download first
    base = "https://drive.google.com/uc?export=download&id=" + file_id
    response = session.get(base, stream=True)
    
    # Check if we got the virus scan warning page for large files
    if response.status_code == 200:
        # Check first chunk to see if it's HTML
        first_chunk = next(response.iter_content(chunk_size=512), None)
        if first_chunk and first_chunk[:15].lower() == b'<!doctype html>':
            response.close()
            # It's the warning page, extract UUID and download with confirm
            response = session.get(base)
            html = response.text
            response.close()
            
            # Extract UUID from the HTML form
            uuid_match = re.search(r'name="uuid" value="([^"]+)"', html)
            if uuid_match:
                uuid = uuid_match.group(1)
                # Use the new download URL with confirm
                download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t&uuid={uuid}"
                response = session.get(download_url, stream=True)
            else:
                # Try the old token method as fallback
                token = _get_confirm_token_from_html(html)
                if token:
                    url_with_confirm = base + f"&confirm={token}"
                    response = session.get(url_with_confirm, stream=True)
                else:
                    raise RuntimeError("Could not extract download confirmation from Google Drive.")
        else:
            # It's the actual file, rewind by creating new response with first chunk
            # We need to re-download since we already consumed a chunk
            response.close()
            response = session.get(base, stream=True)
    
    _download_stream(response, dest_path)


def _extract_gdrive_file_id(url: str) -> Optional[str]:
    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


def _extract_gdrive_folder_id(url: str) -> Optional[str]:
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


def _resolve_gdrive_folder_file_id(folder_id: str, archive_name: str) -> str:
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    response = requests.get(url)
    try:
        response.raise_for_status()
        html = response.text

        if "accounts.google.com" in response.url or "ServiceLogin" in html:
            raise RuntimeError(
                "Google Drive folder is not publicly accessible. "
                "Make it public or provide a direct file link."
            )

        candidates = _extract_folder_candidates(html)
        if not candidates:
            raise RuntimeError(
                "Could not find archive files in the Google Drive folder. "
                "Make sure it contains a .zip or .tar.gz model archive."
            )

        archive_name_lower = (archive_name or "").lower()
        for file_id, name in candidates:
            if archive_name_lower and name.lower() == archive_name_lower:
                return file_id

        if len(candidates) == 1:
            return candidates[0][0]

        names = ", ".join(name for _, name in candidates)
        raise RuntimeError(
            "Multiple archive files found in Google Drive folder. "
            f"Set VOSK_MODEL_ARCHIVE_NAME to one of: {names}"
        )
    finally:
        response.close()


def _extract_folder_candidates(html: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    patterns = [
        re.compile(r'\["([a-zA-Z0-9_-]{10,})","([^"]+\\.(?:zip|tar\\.gz|tgz))"', re.IGNORECASE),
        re.compile(
            r'"id":"([a-zA-Z0-9_-]{10,})".{0,200}?"name":"([^"]+\\.(?:zip|tar\\.gz|tgz))"',
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r'"name":"([^"]+\\.(?:zip|tar\\.gz|tgz))".{0,200}?"id":"([a-zA-Z0-9_-]{10,})"',
            re.IGNORECASE | re.DOTALL,
        ),
    ]

    for pattern in patterns:
        for match in pattern.findall(html):
            if isinstance(match, tuple) and len(match) == 2:
                if match[0].lower().endswith((".zip", ".tar.gz", ".tgz")):
                    name, file_id = match
                else:
                    file_id, name = match
                candidates.append((file_id, name))

    seen = set()
    unique: list[tuple[str, str]] = []
    for file_id, name in candidates:
        key = (file_id, name)
        if key in seen:
            continue
        seen.add(key)
        unique.append((file_id, name))
    return unique


def _get_confirm_token(response: requests.Response) -> Optional[str]:
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value
    try:
        text = response.text
    except Exception:
        return None
    match = re.search(r"confirm=([0-9A-Za-z_]+)", text)
    if match:
        return match.group(1)
    return None


def _get_confirm_token_from_html(html: str) -> Optional[str]:
    match = re.search(r"confirm=([0-9A-Za-z_]+)", html)
    if match:
        return match.group(1)
    return None


def _download_file(url: str, dest_path: Path) -> None:
    response = requests.get(url, stream=True)
    _download_stream(response, dest_path)


def _download_stream(response: requests.Response, dest_path: Path) -> None:
    try:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        start = time.time()

        with open(dest_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                handle.write(chunk)
                downloaded += len(chunk)
                _print_progress(downloaded, total, start)

        print()
        print("[VoiceAssistant] Download complete.")
    finally:
        response.close()


def _print_progress(downloaded: int, total: int, start: float) -> None:
    elapsed = max(0.001, time.time() - start)
    speed_mb = downloaded / (1024 * 1024) / elapsed
    downloaded_mb = downloaded / (1024 * 1024)
    if total > 0:
        total_mb = total / (1024 * 1024)
        percent = downloaded / total * 100
        msg = (
            f"\r[VoiceAssistant] Downloading Vosk model: "
            f"{percent:6.2f}% ({downloaded_mb:,.1f}/{total_mb:,.1f} MB) "
            f"{speed_mb:,.1f} MB/s"
        )
    else:
        msg = (
            f"\r[VoiceAssistant] Downloading Vosk model: "
            f"{downloaded_mb:,.1f} MB downloaded "
            f"{speed_mb:,.1f} MB/s"
        )
    print(msg, end="", flush=True)


def _extract_archive(archive_path: Path, extract_dir: Path) -> None:
    suffixes = "".join(archive_path.suffixes).lower()
    if suffixes.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)
        return
    if suffixes.endswith(".tar.gz") or suffixes.endswith(".tgz"):
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(extract_dir)
        return
    if suffixes.endswith(".tar"):
        with tarfile.open(archive_path, "r:") as tf:
            tf.extractall(extract_dir)
        return
    raise RuntimeError(f"Unsupported archive format: {archive_path}")
