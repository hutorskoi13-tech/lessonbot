# minimal backport for Python 3.13+ (stdlib imghdr was removed)
def what(file, h=None):
    if h is None:
        try:
            with open(file, "rb") as f:
                h = f.read(64)
        except Exception:
            return None
    if h.startswith(b"\xFF\xD8"): return "jpeg"
    if h.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if h.startswith(b"GIF87a") or h.startswith(b"GIF89a"): return "gif"
    if h[:4] == b"RIFF" and h[8:12] == b"WEBP": return "webp"
    if h.startswith(b"BM"): return "bmp"
    if h.startswith(b"II*\x00") or h.startswith(b"MM\x00*"): return "tiff"
    return None
