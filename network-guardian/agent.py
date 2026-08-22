#!/usr/bin/env python3
"""Network Guardian MVP

Local-first network quality monitor with SQLite storage, a tiny web dashboard,
manual Cloudflare result ingestion, and conservative degradation diagnosis.

Safety rule: this MVP never reboots routers, changes DNS, toggles interfaces,
or switches WANs automatically. The only automatic recovery step is a re-probe
used to confirm that a degradation is persistent.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import socket
import sqlite3
import statistics
import subprocess
import threading
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

APP_VERSION = "0.1.0"
BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
DEFAULT_CONFIG_PATH = BASE_DIR / "config.json"
DEFAULT_DB_PATH = BASE_DIR / "data" / "network_guardian.sqlite3"

DEFAULT_CONFIG: dict[str, Any] = {
    "site_id": "home-lab",
    "node_id": socket.gethostname(),
    "location_label": "router_near",
    "bind_host": "127.0.0.1",
    "port": 8765,
    "probe_interval_sec": 300,
    "confirm_after_sec": 15,
    "consecutive_bad_required": 3,
    "targets": ["1.1.1.1", "8.8.8.8"],
    "dns_host": "www.cloudflare.com",
    "http_url": "https://www.cloudflare.com/cdn-cgi/trace",
    "hub_url": "",
    "api_token": "",
    "thresholds": {
        "gateway_rtt_bad_ms": 80,
        "gateway_loss_bad_pct": 10,
        "internet_rtt_bad_ms": 200,
        "internet_loss_bad_pct": 10,
        "dns_bad_ms": 1000,
        "http_bad_ms": 2500,
        "idle_latency_caution_ms": 80,
        "idle_latency_bad_ms": 150,
        "loaded_latency_caution_ms": 100,
        "loaded_latency_bad_ms": 200,
        "download_caution_mbps": 10,
        "upload_caution_mbps": 2,
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path) -> dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            return merge_dict(DEFAULT_CONFIG, json.load(fh))
    return dict(DEFAULT_CONFIG)


def parse_ping_output(text: str) -> tuple[float | None, float | None]:
    """Return (avg_rtt_ms, packet_loss_pct) from Linux/macOS ping output."""
    loss = None
    avg = None
    loss_match = re.search(r"([0-9.]+)%\s*packet loss", text)
    if loss_match:
        loss = float(loss_match.group(1))
    rtt_match = re.search(r"(?:=)\s*[0-9.]+/([0-9.]+)/[0-9.]+/[0-9.]+\s*ms", text)
    if rtt_match:
        avg = float(rtt_match.group(1))
    return avg, loss


def ping_host(host: str, count: int = 3, timeout_sec: int = 8) -> tuple[float | None, float | None]:
    ping = shutil.which("ping")
    if not ping:
        return None, None
    try:
        proc = subprocess.run(
            [ping, "-n", "-c", str(count), host],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return parse_ping_output((proc.stdout or "") + "\n" + (proc.stderr or ""))
    except (subprocess.TimeoutExpired, OSError):
        return None, 100.0


def discover_default_gateway() -> str | None:
    system = platform.system().lower()
    try:
        if system == "darwin" and shutil.which("route"):
            proc = subprocess.run(
                ["route", "-n", "get", "default"], capture_output=True, text=True, timeout=3
            )
            match = re.search(r"gateway:\s*(\S+)", proc.stdout)
            return match.group(1) if match else None
        if system == "linux" and shutil.which("ip"):
            proc = subprocess.run(
                ["ip", "route", "show", "default"], capture_output=True, text=True, timeout=3
            )
            match = re.search(r"default via\s+(\S+)", proc.stdout)
            return match.group(1) if match else None
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def dns_probe(host: str, timeout_sec: float = 3.0) -> float | None:
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout_sec)
    start = time.perf_counter()
    try:
        socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        return round((time.perf_counter() - start) * 1000, 1)
    except OSError:
        return None
    finally:
        socket.setdefaulttimeout(previous_timeout)


def http_probe(url: str, timeout_sec: float = 5.0) -> float | None:
    req = urllib.request.Request(url, headers={"User-Agent": f"NetworkGuardian/{APP_VERSION}"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as response:
            response.read(256)
        return round((time.perf_counter() - start) * 1000, 1)
    except Exception:
        return None


def wifi_signal_dbm() -> float | None:
    """Best-effort RSSI discovery; failure is expected on some systems."""
    system = platform.system().lower()
    try:
        if system == "linux" and shutil.which("nmcli"):
            proc = subprocess.run(
                ["nmcli", "-t", "-f", "IN-USE,SIGNAL", "dev", "wifi"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            for line in proc.stdout.splitlines():
                if line.startswith("*:"):
                    pct = float(line.split(":", 1)[1])
                    return round((pct / 2.0) - 100.0, 1)
        if system == "darwin":
            airport = Path(
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            )
            if airport.exists():
                proc = subprocess.run([str(airport), "-I"], capture_output=True, text=True, timeout=3)
                match = re.search(r"agrCtlRSSI:\s*(-?\d+)", proc.stdout)
                if match:
                    return float(match.group(1))
    except (ValueError, OSError, subprocess.TimeoutExpired):
        pass
    return None


@dataclass
class Measurement:
    timestamp: str
    site_id: str
    node_id: str
    location_label: str
    kind: str = "auto"
    gateway_rtt_ms: float | None = None
    gateway_loss_pct: float | None = None
    internet_rtt_ms: float | None = None
    internet_loss_pct: float | None = None
    dns_ms: float | None = None
    http_ms: float | None = None
    wifi_signal_dbm: float | None = None
    download_mbps: float | None = None
    upload_mbps: float | None = None
    idle_latency_ms: float | None = None
    loaded_latency_ms: float | None = None
    severity: str = "unknown"
    diagnosis: str = "unknown"
    note: str = ""


def _is_bad(value: float | None, threshold: float) -> bool:
    return value is not None and value > threshold


def classify(m: Measurement, cfg: dict[str, Any]) -> tuple[str, str]:
    t = cfg["thresholds"]

    if m.kind == "manual":
        if _is_bad(m.loaded_latency_ms, t["loaded_latency_bad_ms"]):
            return "bad", "congestion_or_bufferbloat"
        if _is_bad(m.idle_latency_ms, t["idle_latency_bad_ms"]):
            return "bad", "upstream_or_wan"
        caution = any(
            [
                _is_bad(m.loaded_latency_ms, t["loaded_latency_caution_ms"]),
                _is_bad(m.idle_latency_ms, t["idle_latency_caution_ms"]),
                m.download_mbps is not None and m.download_mbps < t["download_caution_mbps"],
                m.upload_mbps is not None and m.upload_mbps < t["upload_caution_mbps"],
            ]
        )
        return ("caution", "capacity_or_congestion") if caution else ("good", "healthy")

    gateway_bad = _is_bad(m.gateway_rtt_ms, t["gateway_rtt_bad_ms"]) or _is_bad(
        m.gateway_loss_pct, t["gateway_loss_bad_pct"]
    )
    internet_bad = _is_bad(m.internet_rtt_ms, t["internet_rtt_bad_ms"]) or _is_bad(
        m.internet_loss_pct, t["internet_loss_bad_pct"]
    )
    dns_bad = m.dns_ms is None or _is_bad(m.dns_ms, t["dns_bad_ms"])
    http_bad = m.http_ms is None or _is_bad(m.http_ms, t["http_bad_ms"])

    if (gateway_bad or internet_bad) and not dns_bad and not http_bad:
        if m.gateway_loss_pct == 100.0 or m.internet_loss_pct == 100.0:
            return "caution", "icmp_unavailable"

    if gateway_bad:
        return "bad", "local_wifi_or_lan"
    if internet_bad and not gateway_bad:
        return "bad", "upstream_or_wan"
    if dns_bad and not internet_bad:
        return "bad", "dns"
    if http_bad and not internet_bad and not dns_bad:
        return "caution", "http_path_or_service"
    return "good", "healthy"


def recommendation_for(diagnosis: str) -> str:
    return {
        "healthy": "対処不要。通常監視を継続します。",
        "local_wifi_or_lan": "家のWi‑Fi/LAN側を優先確認。AP距離・5GHz/2.4GHz・中継経路を比較し、必要なら手動で再接続。",
        "upstream_or_wan": "上流回線/WAN側の可能性。ルーター直近も同時測定し、回線再接続や予備WAN切替は確認後に実施。",
        "dns": "DNS応答異常の可能性。IP疎通を再確認し、DNS変更は確認後に実施。",
        "http_path_or_service": "特定HTTP経路の遅延か一時障害の可能性。別URLでも再確認。",
        "icmp_unavailable": "pingだけ応答しない可能性。DNS/HTTPが正常なら障害扱いせず、別の軽量プローブで監視を継続。",
        "congestion_or_bufferbloat": "通信中遅延が高い可能性。SQM/CAKE等の帯域制御は別フェーズでA/B検証。",
        "capacity_or_congestion": "帯域または混雑の注意状態。同時刻のルーター直近値と比較して原因を分離。",
    }.get(diagnosis, "再測定して傾向を確認。")


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    location_label TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    gateway_rtt_ms REAL,
                    gateway_loss_pct REAL,
                    internet_rtt_ms REAL,
                    internet_loss_pct REAL,
                    dns_ms REAL,
                    http_ms REAL,
                    wifi_signal_dbm REAL,
                    download_mbps REAL,
                    upload_mbps REAL,
                    idle_latency_ms REAL,
                    loaded_latency_ms REAL,
                    severity TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    raw_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_measurements_ts ON measurements(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_measurements_node_ts ON measurements(node_id, timestamp DESC);

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    confirmed INTEGER NOT NULL DEFAULT 0,
                    detail_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(timestamp DESC);
                """
            )

    def insert_measurement(self, m: Measurement) -> int:
        payload = asdict(m)
        columns = list(payload.keys())
        values = [payload[c] for c in columns]
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                f"INSERT INTO measurements ({','.join(columns)},raw_json) VALUES ({','.join(['?'] * (len(columns)+1))})",
                values + [json.dumps(payload, ensure_ascii=False)],
            )
            return int(cur.lastrowid)

    def list_measurements(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM measurements ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def latest(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM measurements ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def recent_auto(self, node_id: str, limit: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM measurements WHERE node_id=? AND kind='auto' ORDER BY id DESC LIMIT ?",
                (node_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def insert_event(self, m: Measurement, confirmed: bool) -> int:
        recommendation = recommendation_for(m.diagnosis)
        detail = {"measurement": asdict(m), "recommendation": recommendation}
        with self._lock, self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO events
                (timestamp,node_id,severity,diagnosis,recommendation,confirmed,detail_json)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    utc_now_iso(),
                    m.node_id,
                    m.severity,
                    m.diagnosis,
                    recommendation,
                    1 if confirmed else 0,
                    json.dumps(detail, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def collect_auto(cfg: dict[str, Any]) -> Measurement:
    gateway = discover_default_gateway()
    gw_rtt, gw_loss = ping_host(gateway) if gateway else (None, None)

    rtts: list[float] = []
    losses: list[float] = []
    for target in cfg["targets"]:
        rtt, loss = ping_host(str(target))
        if rtt is not None:
            rtts.append(rtt)
        if loss is not None:
            losses.append(loss)

    m = Measurement(
        timestamp=utc_now_iso(),
        site_id=str(cfg["site_id"]),
        node_id=str(cfg["node_id"]),
        location_label=str(cfg["location_label"]),
        kind="auto",
        gateway_rtt_ms=gw_rtt,
        gateway_loss_pct=gw_loss,
        internet_rtt_ms=round(statistics.mean(rtts), 1) if rtts else None,
        internet_loss_pct=round(statistics.mean(losses), 1) if losses else 100.0,
        dns_ms=dns_probe(str(cfg["dns_host"])),
        http_ms=http_probe(str(cfg["http_url"])),
        wifi_signal_dbm=wifi_signal_dbm(),
    )
    m.severity, m.diagnosis = classify(m, cfg)
    return m


def post_to_hub(m: Measurement, cfg: dict[str, Any]) -> None:
    hub_url = str(cfg.get("hub_url") or "").rstrip("/")
    if not hub_url:
        return
    body = json.dumps(asdict(m), ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = str(cfg.get("api_token") or "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{hub_url}/api/ingest", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            response.read(64)
    except Exception as exc:
        print(f"[hub] upload failed: {exc}")


def maybe_confirm_event(store: Store, cfg: dict[str, Any], m: Measurement) -> None:
    required = int(cfg["consecutive_bad_required"])
    recent = store.recent_auto(m.node_id, required)
    if len(recent) < required or not all(row["severity"] == "bad" for row in recent):
        return

    time.sleep(max(0, int(cfg.get("confirm_after_sec", 15))))
    confirmation = collect_auto(cfg)
    store.insert_measurement(confirmation)
    post_to_hub(confirmation, cfg)
    if confirmation.severity == "bad":
        store.insert_event(confirmation, confirmed=True)
        print(f"[event] confirmed degradation: {confirmation.diagnosis}")


def run_probe(store: Store, cfg: dict[str, Any]) -> Measurement:
    m = collect_auto(cfg)
    store.insert_measurement(m)
    post_to_hub(m, cfg)
    print(json.dumps(asdict(m), ensure_ascii=False))
    if m.severity == "bad":
        maybe_confirm_event(store, cfg, m)
    return m


class DashboardHandler(BaseHTTPRequestHandler):
    store: Store
    cfg: dict[str, Any]

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[http] " + fmt % args)

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1_000_000:
            raise ValueError("invalid body length")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _authorized(self) -> bool:
        token = str(self.cfg.get("api_token") or "")
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/status":
            self._json(
                {
                    "version": APP_VERSION,
                    "site_id": self.cfg["site_id"],
                    "node_id": self.cfg["node_id"],
                    "location_label": self.cfg["location_label"],
                    "latest": self.store.latest(),
                    "safety": "observe_and_reprobe_only",
                }
            )
            return
        if path == "/api/measurements":
            self._json(self.store.list_measurements(200))
            return
        if path == "/api/events":
            self._json(self.store.list_events(100))
            return
        if path in ("/", "/index.html"):
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/api/manual", "/api/ingest") and not self._authorized():
            self._json({"error": "unauthorized"}, 401)
            return
        try:
            data = self._read_json()
        except Exception as exc:
            self._json({"error": str(exc)}, 400)
            return

        if path == "/api/manual":
            try:
                m = Measurement(
                    timestamp=str(data.get("timestamp") or utc_now_iso()),
                    site_id=str(data.get("site_id") or self.cfg["site_id"]),
                    node_id=str(data.get("node_id") or self.cfg["node_id"]),
                    location_label=str(data.get("location_label") or self.cfg["location_label"]),
                    kind="manual",
                    download_mbps=_float_or_none(data.get("download_mbps")),
                    upload_mbps=_float_or_none(data.get("upload_mbps")),
                    idle_latency_ms=_float_or_none(data.get("idle_latency_ms")),
                    loaded_latency_ms=_float_or_none(data.get("loaded_latency_ms")),
                    note=str(data.get("note") or "Cloudflare/manual"),
                )
                m.severity, m.diagnosis = classify(m, self.cfg)
                row_id = self.store.insert_measurement(m)
                self._json({"ok": True, "id": row_id, "measurement": asdict(m)}, 201)
            except Exception as exc:
                self._json({"error": str(exc)}, 400)
            return

        if path == "/api/ingest":
            try:
                allowed = {field.name for field in Measurement.__dataclass_fields__.values()}
                payload = {k: v for k, v in data.items() if k in allowed}
                m = Measurement(**payload)
                m.severity, m.diagnosis = classify(m, self.cfg)
                row_id = self.store.insert_measurement(m)
                self._json({"ok": True, "id": row_id}, 201)
            except Exception as exc:
                self._json({"error": str(exc)}, 400)
            return

        self.send_error(HTTPStatus.NOT_FOUND)


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def scheduler_loop(store: Store, cfg: dict[str, Any], stop: threading.Event) -> None:
    interval = max(30, int(cfg["probe_interval_sec"]))
    while not stop.is_set():
        start = time.monotonic()
        try:
            run_probe(store, cfg)
        except Exception as exc:
            print(f"[probe] failed: {exc}")
        elapsed = time.monotonic() - start
        stop.wait(max(1, interval - elapsed))


def serve(store: Store, cfg: dict[str, Any]) -> None:
    DashboardHandler.store = store
    DashboardHandler.cfg = cfg
    server = ThreadingHTTPServer((str(cfg["bind_host"]), int(cfg["port"])), DashboardHandler)
    stop = threading.Event()
    worker = threading.Thread(target=scheduler_loop, args=(store, cfg, stop), daemon=True)
    worker.start()
    print(f"Network Guardian {APP_VERSION}: http://{cfg['bind_host']}:{cfg['port']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Network Guardian MVP")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one probe and exit")
    mode.add_argument("--serve", action="store_true", help="run scheduler + local dashboard")
    args = parser.parse_args()

    cfg = load_config(args.config)
    store = Store(args.db)
    if args.once:
        run_probe(store, cfg)
    else:
        serve(store, cfg)


if __name__ == "__main__":
    main()
