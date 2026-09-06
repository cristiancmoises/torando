"""Exercise the shell implementation without root, Tor, or host firewall access."""

import copy
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "tests" / "mock_firewall.py"
RUNNER = '''
set -Eeuo pipefail
source "$1/lib/torando.sh"
TORANDO_LOCK="$TORANDO_TEST_LOCK"
torando_ipv6_required() { [[ ${MOCK_IPV6:-1} == 1 ]]; }
shift
torando_main "$@"
'''


def packet_result(tables, *, family="iptables", uid="1000", protocol="tcp", destination="93.184.216.34", port=443):
    """Interpret enough netfilter semantics to assert the intended packet policy."""
    packet = {"uid": uid, "proto": protocol, "dst": destination, "port": str(port)}

    def walk(table, chain):
        for rule in tables[family][table][chain]:
            def value(option):
                return rule[rule.index(option) + 1] if option in rule else None

            if value("--uid-owner") not in {None, packet["uid"]}:
                continue
            if value("-p") not in {None, packet["proto"]}:
                continue
            if value("--dport") not in {None, packet["port"]}:
                continue
            if value("-d") and ipaddress.ip_address(packet["dst"]) not in ipaddress.ip_network(value("-d")):
                continue
            interface = "lo" if ipaddress.ip_address(packet["dst"]).is_loopback else "eth0"
            if value("-o") not in {None, interface}:
                continue
            target = value("-j")
            if target == "REDIRECT":
                packet["dst"], packet["port"] = "127.0.0.1", value("--to-ports")
                return "ACCEPT"
            if target in {"ACCEPT", "REJECT", "DROP", "RETURN"}:
                return target
            result = walk(table, target)
            if result != "RETURN":
                return result
        return "RETURN"

    if family == "iptables":
        walk("nat", "OUTPUT")
    verdict = walk("filter", "OUTPUT")
    return ("ACCEPT" if verdict == "RETURN" else verdict, packet["dst"], packet["port"])


class FirewallTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.temp = Path(self.directory.name)
        self.bin = self.temp / "bin"
        self.bin.mkdir()
        # Only explicit test commands are reachable. A missing mock can never
        # fall through to an installed iptables binary on the host.
        for name in ("iptables", "ip6tables", "id", "pgrep", "uname"):
            (self.bin / name).symlink_to(MOCK)
        for name, target in (("python3", sys.executable), ("flock", shutil.which("flock")), ("cat", shutil.which("cat"))):
            (self.bin / name).symlink_to(target)
        self.bash = shutil.which("bash")
        self.path = self.temp / "state.json"
        self.lock = self.temp / "lock"
        self.env = {
            **os.environ,
            "PATH": str(self.bin),
            "TORANDO_TEST_STATE": str(self.path),
            "TORANDO_TEST_LOCK": str(self.lock),
            "SUDO_USER": "alice",
            "SUDO_UID": "1000",
            "MOCK_EUID": "0",
            "MOCK_IPV6": "1",
            "MOCK_PGREP_EXIT": "1",
            "MOCK_OS": "Linux",
        }
        self.original = {
            "iptables": {
                "nat": {"OUTPUT": [["-m", "comment", "--comment", "keep-nat", "-j", "RETURN"]]},
                "filter": {"OUTPUT": [["-m", "comment", "--comment", "keep-filter", "-j", "ACCEPT"]]},
            },
            "ip6tables": {"filter": {"OUTPUT": [["-m", "comment", "--comment", "keep-ipv6", "-j", "ACCEPT"]]}},
        }
        self.save({"tables": copy.deepcopy(self.original), "calls": [], "history": []})

    def state(self):
        return json.loads(self.path.read_text())

    def save(self, state):
        self.path.write_text(json.dumps(state))

    def run_cli(self, *args, expected=0, **env):
        result = subprocess.run(
            [self.bash, "-c", RUNNER, "test-runner", str(ROOT), *args],
            env={**self.env, **env}, text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def fail_at(self, binary, table, operation, chain):
        state = self.state()
        state["failure"] = {"command": [binary, table, operation, chain], "remaining": 1}
        self.save(state)

    def test_help_and_version_need_no_root_or_firewall(self):
        for action in ("enable", "disable"):
            result = self.run_cli(action, "--help", MOCK_EUID="1000")
            self.assertIn("--user", result.stdout)
            self.assertEqual(self.run_cli(action, "--version", MOCK_EUID="1000").stdout, "2.0.1\n")
        self.assertEqual(self.state()["calls"], [])

    def test_invalid_inputs_do_not_touch_firewall(self):
        cases = [
            (["--user", "root"], {}), (["--user", "tor"], {}),
            (["--user", "unknown"], {}), (["--user"], {}),
            (["--dns-port", "0"], {}), (["--dns-port", "65536"], {}),
            (["--trans-port", "1+1"], {}), (["--unknown"], {}),
            ([], {"SUDO_USER": "", "SUDO_UID": ""}),
            ([], {"MOCK_EUID": "1000"}), ([], {"MOCK_PGREP_EXIT": "0"}),
            ([], {"MOCK_PGREP_EXIT": "2"}),
            ([], {"MOCK_OS": "FreeBSD"}),
        ]
        for args, env in cases:
            with self.subTest(args=args, env=env):
                self.run_cli("enable", *args, expected=1, **env)
                self.assertEqual(self.state()["calls"], [])

    def test_enable_routes_tcp_and_dns_and_blocks_other_traffic(self):
        self.run_cli("enable")
        tables = self.state()["tables"]
        self.assertEqual(packet_result(tables), ("ACCEPT", "127.0.0.1", "9040"))
        for destination in ("8.8.8.8", "127.0.0.53"):
            self.assertEqual(packet_result(tables, protocol="udp", destination=destination, port=53), ("ACCEPT", "127.0.0.1", "5353"))
        self.assertEqual(packet_result(tables, protocol="udp")[0], "REJECT")
        self.assertEqual(packet_result(tables, protocol="icmp")[0], "REJECT")
        self.assertEqual(packet_result(tables, family="ip6tables", destination="2606:4700:4700::1111")[0], "REJECT")
        self.assertEqual(packet_result(tables, destination="127.0.0.1", port=8080), ("ACCEPT", "127.0.0.1", "8080"))
        self.assertEqual(packet_result(tables, family="ip6tables", destination="::1", port=8080)[0], "ACCEPT")
        self.assertEqual(packet_result(tables, uid="1001"), ("ACCEPT", "93.184.216.34", "443"))
        self.assertIn("enabled", self.run_cli("enable", "--status").stdout)

    def test_enable_and_disable_are_idempotent_and_preserve_other_rules(self):
        self.run_cli("enable")
        first = self.state()["tables"]
        self.run_cli("enable")
        self.assertEqual(self.state()["tables"], first)
        self.run_cli("disable")
        self.assertEqual(self.state()["tables"], self.original)
        self.run_cli("disable")
        self.assertEqual(self.state()["tables"], self.original)
        self.run_cli("enable", "--status", expected=3)

    def test_custom_ports_and_reconfiguration(self):
        self.run_cli("enable", "--trans-port", "19040", "--dns-port", "01535")
        result = self.run_cli("enable", "--status")
        self.assertIn("TCP port 19040, DNS port 1535", result.stdout)
        self.assertEqual(packet_result(self.state()["tables"])[2], "19040")
        self.run_cli("enable")
        self.assertEqual(packet_result(self.state()["tables"])[2], "9040")

    def test_multiple_users_remain_independent(self):
        self.run_cli("enable")
        self.run_cli("enable", "--user", "bob", "--trans-port", "19040")
        self.run_cli("enable", "--status")
        self.run_cli("enable", "--status", "--user", "1001")
        self.assertEqual(packet_result(self.state()["tables"], uid="1001")[2], "19040")
        self.run_cli("disable")
        self.run_cli("enable", "--status", "--user", "bob")
        self.run_cli("disable", "--user", "bob")
        self.assertEqual(self.state()["tables"], self.original)

    def test_reordered_nat_rules_are_detected_and_repaired(self):
        self.run_cli("enable")
        state = self.state()
        chain = state["tables"]["iptables"]["nat"]["TORANDO_N_1000"]
        chain.insert(0, chain.pop())
        self.save(state)
        self.run_cli("enable", "--status", expected=2)
        self.run_cli("enable")
        self.run_cli("enable", "--status")

    def test_an_earlier_accept_rule_is_reported_as_modified(self):
        self.run_cli("enable")
        state = self.state()
        state["tables"]["iptables"]["filter"]["OUTPUT"].insert(0, ["-j", "ACCEPT"])
        self.save(state)
        self.run_cli("enable", "--status", expected=2)

    def test_missing_ipv6_tool_fails_before_any_firewall_access(self):
        (self.bin / "ip6tables").unlink()
        self.assertIn("ip6tables is missing", self.run_cli("enable", expected=1).stderr)
        self.assertEqual(self.state()["calls"], [])

    def test_boot_disabled_ipv6_does_not_need_ip6tables(self):
        (self.bin / "ip6tables").unlink()
        self.run_cli("enable", MOCK_IPV6="0")
        self.run_cli("enable", "--status", MOCK_IPV6="0")
        self.run_cli("disable", MOCK_IPV6="0")
        self.assertEqual(self.state()["tables"], self.original)

    def test_firewall_preflight_failure_changes_nothing(self):
        self.fail_at("ip6tables", "filter", "-S", "OUTPUT")
        self.run_cli("enable", expected=4)
        self.assertEqual(self.state()["history"], [])

    def test_failed_enable_retains_blocks_and_disable_recovers(self):
        self.fail_at("iptables", "nat", "-A", "TORANDO_N_1000")
        result = self.run_cli("enable", expected=4)
        self.assertIn("Blocking guards may remain", result.stderr)
        self.assertEqual(packet_result(self.state()["tables"])[0], "REJECT")
        self.assertEqual(packet_result(self.state()["tables"], family="ip6tables", destination="2001:db8::1")[0], "REJECT")
        self.run_cli("enable", "--status", expected=2)
        self.run_cli("disable")
        self.assertEqual(self.state()["tables"], self.original)

    def test_failed_disable_retains_blocks_and_retry_recovers(self):
        self.run_cli("enable")
        self.fail_at("iptables", "nat", "-X", "TORANDO_N_1000")
        self.run_cli("disable", expected=4)
        self.assertEqual(packet_result(self.state()["tables"])[0], "REJECT")
        self.run_cli("disable")
        self.assertEqual(self.state()["tables"], self.original)

    def test_inspection_failure_during_update_reports_recovery(self):
        self.fail_at("iptables", "nat", "-S", "TORANDO_N_1000")
        result = self.run_cli("enable", expected=1)
        self.assertIn("cannot inspect firewall", result.stderr)
        self.assertIn("Recover with: sudo ./toroff.sh --user 1000", result.stderr)
        self.assertEqual(result.stderr.count("Blocking guards may remain"), 1)
        self.assertEqual(packet_result(self.state()["tables"])[0], "REJECT")
        self.run_cli("disable")
        self.assertEqual(self.state()["tables"], self.original)

    def test_interrupted_updates_retain_guards_and_report_recovery(self):
        for action in ("enable", "disable"):
            for signal_name, exit_code in (("SIGHUP", 129), ("SIGINT", 130), ("SIGTERM", 143)):
                with self.subTest(action=action, signal=signal_name):
                    if action == "disable":
                        self.run_cli("enable")
                    state = self.state()
                    state["interruption"] = {
                        "command": ["iptables", "nat", "-N" if action == "enable" else "-F", "TORANDO_N_1000"],
                        "signal": signal_name,
                    }
                    self.save(state)
                    result = self.run_cli(action, expected=exit_code)
                    self.assertNotIn("direct networking restored", result.stdout)
                    self.assertNotIn("Torando enabled", result.stdout)
                    self.assertIn(f"firewall update failed (exit {exit_code})", result.stderr)
                    self.assertIn("Recover with: sudo ./toroff.sh --user 1000", result.stderr)
                    self.assertEqual(result.stderr.count("Blocking guards may remain"), 1)
                    tables = self.state()["tables"]
                    self.assertEqual(packet_result(tables)[0], "REJECT")
                    self.assertEqual(packet_result(tables, family="ip6tables", destination="2001:db8::1")[0], "REJECT")
                    self.run_cli("enable", "--status", expected=2)
                    self.run_cli("disable")
                    self.assertEqual(self.state()["tables"], self.original)

    def test_reconfiguration_never_allows_direct_traffic_between_mutations(self):
        self.run_cli("enable")
        state = self.state()
        state["history"] = []
        self.save(state)
        self.run_cli("enable", "--trans-port", "19040")
        for snapshot in self.state()["history"]:
            verdict, destination, _ = packet_result(snapshot)
            self.assertTrue(verdict == "REJECT" or destination == "127.0.0.1")
            self.assertEqual(packet_result(snapshot, protocol="udp")[0], "REJECT")
            self.assertEqual(packet_result(snapshot, family="ip6tables", destination="2001:db8::1")[0], "REJECT")

    def test_lock_contention_changes_nothing(self):
        with self.lock.open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIn("another Torando command", self.run_cli("enable", expected=1).stderr)
        self.assertEqual(self.state()["calls"], [])


if __name__ == "__main__":
    unittest.main()
