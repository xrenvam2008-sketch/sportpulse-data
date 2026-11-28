#!/usr/bin/env python3
"""Check IPTV stream URLs without deleting or rewriting playlist entries.

The checker probes both maintained playlists, follows one HLS variant and one
media segment where possible, and writes a CSV report. 403/451 and transient
network failures are reported separately from confirmed 404/410 responses.
"""
import csv
import concurrent.futures
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PLAYLISTS = [
    Path("iptv/rus_RU.m3u"),
    Path("iptv/iptv-org.github.io_clean.m3u"),
]
REPORT = Path("iptv_stream_check.csv")
TIMEOUT = 12
MAX_BYTES = 65536
WORKERS = 16
UA_DEFAULT = "Mozilla/5.0 (compatible; sportpulse-iptv-check/1.0)"

def parse_playlist(path):
    rows = []
    if not path.exists():
        print(f"Missing playlist: {path}", file=sys.stderr)
        return rows
    current = None
    headers = {}
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            current = {
                "playlist": str(path),
                "channel": line.rsplit(",", 1)[-1].strip(),
                "url": "",
                "headers": {},
            }
            headers = {}
            m = re.search(r'tvg-id="([^"]*)"', line)
            current["tvg_id"] = m.group(1) if m else ""
            ua = re.search(r'http-user-agent="([^"]*)"', line, re.I)
            ref = re.search(r'http-referrer="([^"]*)"', line, re.I)
            if ua:
                headers["User-Agent"] = ua.group(1)
            if ref:
                headers["Referer"] = ref.group(1)
        elif line.startswith("#EXTVLCOPT:http-user-agent=") and current:
            headers["User-Agent"] = line.split("=", 1)[1]
        elif line.startswith("#EXTVLCOPT:http-referrer=") and current:
            headers["Referer"] = line.split("=", 1)[1]
        elif line and not line.startswith("#") and current:
            current["url"] = line
            current["headers"] = dict(headers)
            rows.append(current)
            current = None
    return rows

def fetch(url, headers=None):
    req_headers = {"User-Agent": UA_DEFAULT, "Range": f"bytes=0-{MAX_BYTES-1}"}
    req_headers.update(headers or {})
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        return response.status, response.read(MAX_BYTES), response.geturl()

def first_uri(manifest):
    for line in manifest.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None

def probe_hls(url, headers):
    status, body, final_url = fetch(url, headers)
    text = body.decode("utf-8-sig", "replace")
    if not text.lstrip().startswith("#EXTM3U"):
        return "INVALID_HLS", status, "Response is not an M3U8 manifest"
    child = first_uri(text)
    if not child:
        return "OK_HLS_MANIFEST", status, "Manifest has no media URI"
    child_url = urllib.parse.urljoin(final_url, child)
    child_path = urllib.parse.urlsplit(child_url).path.lower()
    # If this is a master playlist, fetch its first variant and then one segment.
    if child_path.endswith(".m3u8"):
        cstatus, cbody, cfinal = fetch(child_url, headers)
        ctext = cbody.decode("utf-8-sig", "replace")
        if not ctext.lstrip().startswith("#EXTM3U"):
            return "VARIANT_INVALID", cstatus, "First variant is not an M3U8 manifest"
        segment = first_uri(ctext)
        if segment:
            segment_url = urllib.parse.urljoin(cfinal, segment)
            sstatus, _, _ = fetch(segment_url, headers)
            if sstatus < 400:
                return "OK_HLS", sstatus, "Manifest and first segment reachable"
            return "SEGMENT_HTTP_ERROR", sstatus, "First media segment failed"
        return "OK_HLS_MANIFEST", cstatus, "Variant manifest has no media URI"
    # Media playlist: the first URI is usually a segment.
    sstatus, _, _ = fetch(child_url, headers)
    if sstatus < 400:
        return "OK_HLS", sstatus, "Manifest and first segment reachable"
    return "SEGMENT_HTTP_ERROR", sstatus, "First media segment failed"

def check(row):
    url = row["url"]
    scheme = urllib.parse.urlsplit(url).scheme.lower()
    if scheme not in ("http", "https"):
        return {**row, "status": "UNSUPPORTED_SCHEME", "http_status": "", "detail": f"{scheme or 'unknown'} cannot be probed as HTTP"}
    try:
        path = urllib.parse.urlsplit(url).path.lower()
        if path.endswith(".m3u8") or path.endswith(".m3u"):
            status, code, detail = probe_hls(url, row["headers"])
        else:
            code, body, final_url = fetch(url, row["headers"])
            sample = body.lstrip()
            if sample.startswith(b"#EXTM3U"):
                status, detail = "OK_HLS_MANIFEST", "Dynamic endpoint returned an M3U manifest"
            elif b"<MPD" in body[:4096] or b":MPD" in body[:4096]:
                status, detail = "OK_DASH", "DASH manifest returned"
            elif body and (body[0] == 0x47 or len(body) > 188):
                status, detail = "RESPONSE_RECEIVED", "HTTP response received; format needs player-side verification"
            else:
                status, detail = "UNVERIFIED_CONTENT", "HTTP response received but stream format was not identified"
        return {**row, "status": status, "http_status": code, "detail": detail}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 451):
            status, detail = "BLOCKED_OR_RESTRICTED", "Authentication, anti-bot or regional restriction; not treated as dead"
        elif e.code in (404, 410):
            status, detail = "DEAD_HTTP", "Endpoint returned a definitive 404/410"
        else:
            status, detail = "HTTP_ERROR", str(e.reason)
        return {**row, "status": status, "http_status": e.code, "detail": detail}
    except (TimeoutError, socket.timeout):
        return {**row, "status": "TIMEOUT", "http_status": "", "detail": "Connection timed out; not treated as confirmed dead"}
    except urllib.error.URLError as e:
        return {**row, "status": "NETWORK_ERROR", "http_status": "", "detail": str(e.reason)}
    except Exception as e:
        return {**row, "status": "CHECK_ERROR", "http_status": "", "detail": str(e)}

def main():
    rows = []
    for path in PLAYLISTS:
        rows.extend(parse_playlist(path))
    print(f"Checking {len(rows)} entries from {len(PLAYLISTS)} playlists...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(check, rows))
    fields = ["playlist", "tvg_id", "channel", "url", "status", "http_status", "detail"]
    with REPORT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    counts = {}
    for item in results:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("Results:", counts)
    print("Report:", REPORT)

if __name__ == "__main__":
    main()
