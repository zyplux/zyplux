#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

VARIANT_CONFIG_DIRS = {"code": "Code", "insiders": "Code - Insiders"}
SESSION_DIR_PATTERN = re.compile(r"\d{8}T\d{6}")
WINDOW_DIR_PATTERN = re.compile(r"window\d+")
EXTHOST_PID_PATTERN = re.compile(r"Started local extension host with pid (\d+)\.")
WATCHDOG_BLAME_PATTERN = re.compile(r"UNRESPONSIVE extension host: '([^']+)' took ([0-9.]+)% of ([0-9.]+)ms")
EXTENSION_DIR_PATTERN = re.compile(r"/extensions/([^/]+)/")
BUILTIN_EXTENSIONS_PATH = "/resources/app/extensions/"
PROFILE_GLOB = "exthost-*.cpuprofile"
CLOCK_TICKS_PER_SECOND = os.sysconf("SC_CLK_TCK")


def list_session_dirs(logs_dir, session_count):
    sessions = sorted(
        (d for d in logs_dir.iterdir() if d.is_dir() and SESSION_DIR_PATTERN.fullmatch(d.name)),
        key=lambda d: d.name,
        reverse=True,
    )
    return sessions[:session_count]


def list_window_dirs(session_dir):
    return sorted(d for d in session_dir.iterdir() if d.is_dir() and WINDOW_DIR_PATTERN.fullmatch(d.name))


def parse_renderer_log(renderer_log_path):
    text = renderer_log_path.read_text(errors="replace")
    exthost_pids = [int(m.group(1)) for m in EXTHOST_PID_PATTERN.finditer(text)]
    blames = [(m.group(1), float(m.group(2)), float(m.group(3))) for m in WATCHDOG_BLAME_PATTERN.finditer(text)]
    return exthost_pids, blames


def is_live_exthost(pid):
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    return b"code" in cmdline and b"node.mojom.NodeService" in cmdline


def read_cpu_ticks(pid):
    stat = Path(f"/proc/{pid}/stat").read_text()
    fields = stat[stat.rindex(")") + 2 :].split()
    return int(fields[11]) + int(fields[12])


def read_rss_bytes(pid):
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    return 0


def sample_cpu_percents(pids, sample_seconds):
    ticks_before = {}
    for pid in pids:
        try:
            ticks_before[pid] = read_cpu_ticks(pid)
        except OSError:
            continue
    time.sleep(sample_seconds)
    percents = {}
    for pid, before in ticks_before.items():
        try:
            delta = read_cpu_ticks(pid) - before
        except OSError:
            continue
        percents[pid] = 100.0 * delta / CLOCK_TICKS_PER_SECOND / sample_seconds
    return percents


def classify_frame(url, function_name):
    if function_name == "(idle)":
        return None
    if function_name == "(garbage collector)":
        return "(garbage collector)"
    match = EXTENSION_DIR_PATTERN.search(url)
    if match:
        prefix = "builtin:" if BUILTIN_EXTENSIONS_PATH in url else ""
        return prefix + match.group(1)
    return "(vscode core / runtime)"


def attribute_profile_hits(profile_path):
    try:
        profile = json.loads(profile_path.read_text())
    except OSError, json.JSONDecodeError:
        return {}
    hits_per_bucket = defaultdict(int)
    for node in profile.get("nodes", []):
        hit_count = node.get("hitCount", 0)
        if not hit_count:
            continue
        frame = node.get("callFrame", {})
        bucket = classify_frame(frame.get("url", ""), frame.get("functionName", ""))
        if bucket:
            hits_per_bucket[bucket] += hit_count
    return hits_per_bucket


def collect_variant_diagnostics(config_dir_name, session_count):
    logs_dir = Path.home() / ".config" / config_dir_name / "logs"
    if not logs_dir.is_dir():
        return None
    exthost_pids = set()
    blame_stats = defaultdict(lambda: [0, 0.0])
    for session_dir in list_session_dirs(logs_dir, session_count):
        for window_dir in list_window_dirs(session_dir):
            renderer_log = window_dir / "renderer.log"
            if not renderer_log.is_file():
                continue
            pids, blames = parse_renderer_log(renderer_log)
            exthost_pids.update(pids)
            for extension_id, pct, _window_ms in blames:
                blame_stats[extension_id][0] += 1
                blame_stats[extension_id][1] += pct
    live_pids = {pid for pid in exthost_pids if is_live_exthost(pid)}
    return {"name": config_dir_name, "live_pids": live_pids, "blame_stats": blame_stats}


def format_size(byte_count):
    if byte_count >= 1 << 30:
        return f"{byte_count / (1 << 30):.1f} GiB"
    return f"{byte_count / (1 << 20):.0f} MiB"


def print_variant_report(diagnostics, cpu_percents):
    print(f"== {diagnostics['name']} ==")
    if not diagnostics["live_pids"]:
        print("  no running extension host")
    for pid in sorted(diagnostics["live_pids"]):
        cpu = cpu_percents.get(pid)
        cpu_label = f"{cpu:.0f}% cpu" if cpu is not None else "cpu n/a"
        print(f"  extension host pid {pid}: {cpu_label}, rss {format_size(read_rss_bytes(pid))}")
    if diagnostics["blame_stats"]:
        print("  watchdog blames (renderer.log):")
        ranked = sorted(diagnostics["blame_stats"].items(), key=lambda item: item[1][0], reverse=True)
        for extension_id, (count, pct_sum) in ranked:
            print(f"    {count}x {extension_id}  avg {pct_sum / count:.0f}% of blocked window")
    else:
        print("  no watchdog blames found")
    print()


def print_profiles_report(top_count):
    profile_paths = sorted(Path("/tmp").glob(PROFILE_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    if not profile_paths:
        print("no saved profiles in /tmp (watchdog only saves them when the host blocks >~3s)")
        return False
    print(f"== saved profiles ({len(profile_paths)} files in /tmp) ==")
    combined_hits = defaultdict(int)
    for path in profile_paths:
        hits = attribute_profile_hits(path)
        for bucket, count in hits.items():
            combined_hits[bucket] += count
        if hits:
            top_bucket = max(hits, key=lambda bucket: hits[bucket])
            top_pct = 100.0 * hits[top_bucket] / sum(hits.values())
            saved_at = datetime.fromtimestamp(path.stat().st_mtime).strftime("%m-%d %H:%M")
            print(f"  {path}  [{saved_at}]  {top_pct:.0f}% {top_bucket}")
    total_hits = sum(combined_hits.values())
    print("  combined attribution (idle excluded):")
    ranked = sorted(combined_hits.items(), key=lambda item: item[1], reverse=True)
    for bucket, count in ranked[:top_count]:
        print(f"    {100.0 * count / total_hits:5.1f}%  {bucket}")
    print()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Identify CPU-hungry VS Code extensions via watchdog logs, saved exthost profiles, and live /proc sampling.",
        epilog="For spinners that yield (never block the host), the watchdog stays silent: "
        'use "Developer: Show Running Extensions" > "Start Extension Host Profile" in VS Code, '
        "then re-run this script to analyze the saved profile.",
    )
    parser.add_argument("--variant", choices=["code", "insiders", "all"], default="all")
    parser.add_argument("--sessions", type=int, default=2, help="recent log sessions to scan (default 2)")
    parser.add_argument("--sample-seconds", type=float, default=3.0, help="live CPU sampling window (default 3)")
    parser.add_argument("--top", type=int, default=8, help="rows in combined attribution (default 8)")
    args = parser.parse_args()

    variant_keys = list(VARIANT_CONFIG_DIRS) if args.variant == "all" else [args.variant]
    all_diagnostics = []
    for key in variant_keys:
        diagnostics = collect_variant_diagnostics(VARIANT_CONFIG_DIRS[key], args.sessions)
        if diagnostics:
            all_diagnostics.append(diagnostics)
    if not all_diagnostics:
        parser.exit(1, "no VS Code config directories found\n")

    pids_to_sample = set().union(*(d["live_pids"] for d in all_diagnostics))
    cpu_percents = sample_cpu_percents(pids_to_sample, args.sample_seconds) if pids_to_sample else {}

    for diagnostics in all_diagnostics:
        print_variant_report(diagnostics, cpu_percents)
    has_profiles = print_profiles_report(args.top)

    has_blames = any(d["blame_stats"] for d in all_diagnostics)
    is_burning = any(pct > 50 for pct in cpu_percents.values())
    if is_burning and not (has_blames or has_profiles):
        print("extension host is busy but nothing is blamed: the offender yields between iterations.")
        print('profile it manually: "Developer: Show Running Extensions" > "Start Extension Host Profile",')
        print("stop after ~10s, then re-run this script.")


if __name__ == "__main__":
    main()
