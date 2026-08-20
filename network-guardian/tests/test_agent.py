import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ng_agent", ROOT / "agent.py")
agent = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agent
assert spec.loader
spec.loader.exec_module(agent)


class ClassificationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = agent.DEFAULT_CONFIG

    def test_healthy_auto(self):
        m = agent.Measurement(
            timestamp=agent.utc_now_iso(), site_id="s", node_id="n", location_label="x",
            gateway_rtt_ms=3, gateway_loss_pct=0, internet_rtt_ms=40, internet_loss_pct=0,
            dns_ms=30, http_ms=100,
        )
        self.assertEqual(agent.classify(m, self.cfg), ("good", "healthy"))

    def test_local_wifi_diagnosis(self):
        m = agent.Measurement(
            timestamp=agent.utc_now_iso(), site_id="s", node_id="n", location_label="far",
            gateway_rtt_ms=120, gateway_loss_pct=0, internet_rtt_ms=200, internet_loss_pct=0,
            dns_ms=30, http_ms=100,
        )
        self.assertEqual(agent.classify(m, self.cfg), ("bad", "local_wifi_or_lan"))

    def test_upstream_diagnosis(self):
        m = agent.Measurement(
            timestamp=agent.utc_now_iso(), site_id="s", node_id="n", location_label="near",
            gateway_rtt_ms=3, gateway_loss_pct=0, internet_rtt_ms=260, internet_loss_pct=0,
            dns_ms=30, http_ms=100,
        )
        self.assertEqual(agent.classify(m, self.cfg), ("bad", "upstream_or_wan"))

    def test_linux_ping_parse(self):
        text = "3 packets transmitted, 3 received, 0% packet loss\nrtt min/avg/max/mdev = 10.1/20.2/30.3/1.0 ms"
        self.assertEqual(agent.parse_ping_output(text), (20.2, 0.0))

    def test_macos_ping_parse(self):
        text = "3 packets transmitted, 3 packets received, 0.0% packet loss\nround-trip min/avg/max/stddev = 11.111/22.222/33.333/4.444 ms"
        self.assertEqual(agent.parse_ping_output(text), (22.222, 0.0))

    def test_icmp_only_failure_is_caution(self):
        m = agent.Measurement(
            timestamp=agent.utc_now_iso(), site_id="s", node_id="n", location_label="x",
            gateway_rtt_ms=None, gateway_loss_pct=100, internet_rtt_ms=None, internet_loss_pct=100,
            dns_ms=20, http_ms=100,
        )
        self.assertEqual(agent.classify(m, self.cfg), ("caution", "icmp_unavailable"))

    def test_manual_loaded_latency(self):
        m = agent.Measurement(
            timestamp=agent.utc_now_iso(), site_id="s", node_id="n", location_label="far",
            kind="manual", download_mbps=20, upload_mbps=10, idle_latency_ms=40,
            loaded_latency_ms=250,
        )
        self.assertEqual(agent.classify(m, self.cfg), ("bad", "congestion_or_bufferbloat"))


class StoreTests(unittest.TestCase):
    def test_append_only_insert(self):
        with tempfile.TemporaryDirectory() as td:
            store = agent.Store(Path(td) / "test.sqlite3")
            m = agent.Measurement(timestamp=agent.utc_now_iso(), site_id="s", node_id="n", location_label="x")
            m.severity, m.diagnosis = "good", "healthy"
            first = store.insert_measurement(m)
            second = store.insert_measurement(m)
            self.assertNotEqual(first, second)
            self.assertEqual(len(store.list_measurements()), 2)


if __name__ == "__main__":
    unittest.main()
