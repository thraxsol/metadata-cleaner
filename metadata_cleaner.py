from pathlib import Path
from PIL import Image, ExifTags
import pikepdf
import subprocess
import json

from logger import log

EXIFTOOL_PATH = "exiftool"  # Change to full path if needed


def get_file_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in [".jpg", ".jpeg", ".png", ".tiff", ".tif"]:
        return "image"
    elif ext in [".mp4", ".mov", ".avi", ".mkv", ".mp3", ".wav", ".flac"]:
        return "media"
    elif ext == ".pdf":
        return "pdf"
    return "other"


def extract_image_metadata(path: str) -> dict:
    metadata = {}
    try:
        img = Image.open(path)
        exif = img.getexif()
        for tag_id, value in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            metadata[str(tag)] = value
    except Exception as e:
        log(f"Error extracting image metadata from {path}: {e}")
    return metadata


def extract_pdf_metadata(path: str) -> dict:
    try:
        with pikepdf.open(path) as pdf:
            return {str(k): str(v) for k, v in pdf.docinfo.items()}
    except Exception as e:
        log(f"Error extracting PDF metadata from {path}: {e}")
        return {}


def extract_media_metadata(path: str) -> dict:
    try:
        cmd = [EXIFTOOL_PATH, "-json", path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)[0]
        return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        log(f"Error extracting media metadata from {path}: {e}")
        return {}


def extract_metadata(path: str, file_type: str) -> dict:
    if file_type == "image":
        return extract_image_metadata(path)
    elif file_type == "pdf":
        return extract_pdf_metadata(path)
    elif file_type == "media":
        return extract_media_metadata(path)
    return {}


# -----------------------------
# RULES ENGINE HELPERS
# -----------------------------
DEFAULT_RULES = {
    "remove_gps": True,
    "remove_timestamps": True,
    "remove_camera": True,
    "remove_xmp": True,
    "remove_iptc": True,
    "keep_icc": True,
    "keep_orientation": True,
}

TIMESTAMP_TAGS = {
    "DateTime",
    "DateTimeOriginal",
    "CreateDate",
}

CAMERA_TAGS = {
    "Make",
    "Model",
    "LensModel",
    "LensMake",
}


def _normalize_rules(rules: dict | None) -> dict:
    if rules is None:
        return DEFAULT_RULES.copy()
    merged = DEFAULT_RULES.copy()
    merged.update(rules)
    return merged


# -----------------------------
# LOSSLESS CLEAN HELPERS
# -----------------------------
def clean_image_lossless(src: Path, dst: Path, rules: dict):
    try:
        rules = _normalize_rules(rules)
        img = Image.open(src)
        exif = img.getexif()

        keep_always = {"XResolution", "YResolution", "ResolutionUnit"}
        if rules.get("keep_orientation", True):
            keep_always.add("Orientation")
        if rules.get("keep_icc", True):
            keep_always.add("ICCProfile")

        keys_to_delete = []
        for tag_id, value in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, tag_id)

            if tag_name in keep_always:
                continue

            if rules.get("remove_gps", True) and str(tag_name).startswith("GPS"):
                keys_to_delete.append(tag_id)
                continue

            if rules.get("remove_timestamps", True) and tag_name in TIMESTAMP_TAGS:
                keys_to_delete.append(tag_id)
                continue

            if rules.get("remove_camera", True) and tag_name in CAMERA_TAGS:
                keys_to_delete.append(tag_id)
                continue

            if rules.get("remove_xmp", True) and "XMP" in str(tag_name):
                keys_to_delete.append(tag_id)
                continue

            if rules.get("remove_iptc", True) and "IPTC" in str(tag_name):
                keys_to_delete.append(tag_id)
                continue

            # Any other metadata is removed in lossless mode
            keys_to_delete.append(tag_id)

        for k in keys_to_delete:
            del exif[k]

        data = list(img.getdata())
        new_img = Image.new(img.mode, img.size)
        new_img.putdata(data)

        exif_bytes = exif.tobytes()
        new_img.save(dst, exif=exif_bytes)
        return True, "Lossless image metadata removed"
    except Exception as e:
        return False, str(e)


def clean_pdf_lossless(src: Path, dst: Path, rules: dict):
    try:
        # For now, rules do not affect PDFs; we just clear docinfo.
        with pikepdf.open(src) as pdf:
            pdf.docinfo.clear()
            pdf.save(dst)
        return True, "Lossless PDF metadata removed"
    except Exception as e:
        return False, str(e)


def clean_media_lossless(src: Path, dst: Path, rules: dict):
    try:
        rules = _normalize_rules(rules)
        cmd = [EXIFTOOL_PATH, "-P"]

        if rules.get("remove_gps", True):
            cmd.append("-GPS*=")
        if rules.get("remove_timestamps", True):
            cmd.append("-AllDates=")
        if rules.get("remove_camera", True):
            cmd.extend(["-Make=", "-Model=", "-Lens*="])
        if rules.get("remove_xmp", True):
            cmd.append("-XMP:all=")
        if rules.get("remove_iptc", True):
            cmd.append("-IPTC:all=")

        cmd.extend(["-o", str(dst), str(src)])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, "Lossless media metadata removed"
        return False, result.stderr or "ExifTool error"
    except Exception as e:
        return False, str(e)


# -----------------------------
# FULL CLEAN
# -----------------------------
def clean_image_full(src: Path, dst: Path, rules: dict):
    try:
        # Full clean still nukes all metadata; rules are ignored here.
        with Image.open(src) as img:
            data = list(img.getdata())
            new_img = Image.new(img.mode, img.size)
            new_img.putdata(data)
            new_img.save(dst)
        return True, "Image metadata removed"
    except Exception as e:
        return False, str(e)


def clean_pdf_full(src: Path, dst: Path, rules: dict):
    try:
        with pikepdf.open(src) as pdf:
            pdf.docinfo.clear()
            pdf.save(dst)
        return True, "PDF metadata removed"
    except Exception as e:
        return False, str(e)


def clean_media_full(src: Path, dst: Path, rules: dict):
    try:
        # Full clean: remove everything via ExifTool.
        cmd = [EXIFTOOL_PATH, "-all=", "-o", str(dst), str(src)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True, "Media metadata removed"
        return False, result.stderr or "ExifTool error"
    except Exception as e:
        return False, str(e)


# -----------------------------
# MAIN CLEAN FUNCTION
# -----------------------------
def clean_file(path: str, overwrite: bool = False, lossless: bool = False, rules: dict | None = None):
    src = Path(path)
    if not src.exists():
        log(f"File not found: {path}")
        return False, "File not found", path

    rules = _normalize_rules(rules)
    file_type = get_file_type(src)
    log(f"Starting {'lossless' if lossless else 'full'} clean for {path} (type: {file_type}, rules={rules})")

    if overwrite:
        tmp_suffix = ".tmp_clean_lossless" if lossless else ".tmp_clean"
        dst = src.with_suffix(src.suffix + tmp_suffix)
    else:
        suffix = "_cleaned_lossless" if lossless else "_cleaned"
        dst = src.with_name(src.stem + suffix + src.suffix)

    if lossless:
        if file_type == "image":
            ok, msg = clean_image_lossless(src, dst, rules)
        elif file_type == "pdf":
            ok, msg = clean_pdf_lossless(src, dst, rules)
        elif file_type == "media":
            ok, msg = clean_media_lossless(src, dst, rules)
        else:
            log(f"Unsupported file type for lossless clean: {path}")
            return False, "Unsupported file type", str(src)
    else:
        if file_type == "image":
            ok, msg = clean_image_full(src, dst, rules)
        elif file_type == "pdf":
            ok, msg = clean_pdf_full(src, dst, rules)
        elif file_type == "media":
            ok, msg = clean_media_full(src, dst, rules)
        else:
            log(f"Unsupported file type for full clean: {path}")
            return False, "Unsupported file type", str(src)

    if ok and overwrite:
        dst.replace(src)
        log(f"Clean successful (overwritten): {path}")
        return True, msg, str(src)

    if ok:
        log(f"Clean successful: {dst}")
    else:
        log(f"Clean failed for {path}: {msg}")

    return ok, msg, str(dst)


def compare_metadata(before: dict, after: dict) -> dict:
    removed = {}
    for key, value in before.items():
        if key not in after:
            removed[key] = value
        elif after.get(key) != value:
            removed[key] = value
    return removed
