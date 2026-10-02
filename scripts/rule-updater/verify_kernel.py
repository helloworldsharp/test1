"""Exercise first-match decisions in an isolated Mihomo process, using only loopback."""
from __future__ import annotations

import argparse
import copy
import ipaddress
import json
import os
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

import yaml
from updater import UniqueLoader


class DNS(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        self.server.queries += 1
        end = 12
        while data[end]:
            end += data[end] + 1
        end += 5
        # Controlled foreign address; the selected outbound always rejects before dialing.
        answer = b"\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\x00\x00\x04" + socket.inet_aton("203.0.114.123")
        sock.sendto(data[:2] + b"\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00" + data[12:end] + answer, self.client_address)


def load(path):
    return yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def cases():
    direct, main = "🎯 全球直连", "🚀 节点选择"
    values = []
    for source, device in [("127.0.0.1", None), ("127.0.0.2", "📱 指定设备1"), ("127.0.0.3", "🖱️ 指定设备2")]:
        for host, group in [
            ("baidu.com", direct), ("1.2.4.8", direct), ("192.168.50.1", direct),
            ("speedtest.net", direct), ("ty1.chtm.hinet.net", direct),
            ("msftconnecttest.com", direct), ("push.apple.com", "🍎 苹果推送"),
            ("doubleclick.net", "🛡 广告拦截"), ("st.dl.bscstorage.net", direct),
            ("store.steampowered.com", device or "😄 Steam"),
            ("netflix.com", device or "🎥 奈飞视频"),
            ("chatgpt-async-webps-prod-eastus-1.webpubsub.azure.com", device or "🤖 AI"),
            ("epicgames-download1.akamaized.net", device or "🎮 其他游戏平台"),
            ("ampproject.org", device or main),
            ("bybit.com", device or "💶 Bybit"), ("bybit-exchange.github.io", device or "💶 Bybit"),
            ("binance.com", device or "🪙 BNQ"), ("tradingview.com", device or "🪙 BNQ"),
            ("chatgpt.com", device or "🤖 AI"), ("claudeusercontent.com", device or "🤖 AI"),
            ("github.com", device or main), ("objects.githubusercontent.com", device or main),
            ("t.me", device or main), ("91.105.192.1", device or main),
            ("xbox.com", device or "🎮 其他游戏平台"), ("ea.com", device or "🎮 其他游戏平台"),
            ("copilot.com", device or "Ⓜ 微软服务"), ("onedrive.live.com", device or "Ⓜ 微软服务"),
            ("grok.com", device or "🐦 XGORK"), ("www.gstatic.com", device or "🍀 Google相关"),
            ("google.cn", device or "🍀 Google相关"), ("ibkr.com.cn", device or "📈 海外券商"),
            ("schwab.com.cn", device or "📈 海外券商"), ("64.233.177.188", device or "🍀 Google相关"),
            ("not-in-any-list-6a03.invalid", device or "🐟 漏网之鱼"),
        ]:
            values.append((source, host, group))
    return values


def prepare(root, candidate, home, port, dns_port, mutate=None):
    config = {}
    for name in ("rules", "proxy-groups", "rule-providers"):
        config.update(load(root / "fragments" / (name + ".yaml")))
    for name, provider in config["rule-providers"].items():
        source = candidate / (name + ".yaml")
        if not source.is_file():
            suffix = provider["url"].split("/rules/", 1)[1]
            source = root / "rules" / suffix
        body = source.read_bytes()
        if name in {"src_alone1", "src_alone2"}:
            address = "127.0.0.2" if name == "src_alone1" else "127.0.0.3"
            body = yaml.safe_dump({"payload": ["SRC-IP-CIDR," + address + "/32"]}).encode()
        destination = home / (name + ".yaml")
        destination.write_bytes(body)
        config["rule-providers"][name] = {"type":"file", "behavior":provider["behavior"], "format":"yaml", "path":destination.name}
    for group in config["proxy-groups"]:
        name = group["name"]
        group.clear()
        group.update({"name":name, "type":"select", "proxies":["REJECT"]})
    config.update({"mixed-port":port, "bind-address":"127.0.0.1", "allow-lan":False,
                   "mode":"rule", "log-level":"info", "ipv6":False, "find-process-mode":"off",
                   "dns":{"enable":True, "nameserver":[f"udp://127.0.0.1:{dns_port}"], "ipv6":False}})
    if mutate == "bnq-shadow":
        config["rules"] = [("RULE-SET,crypto,🪙 BNQ" if rule.endswith(",🪙 BNQ") and rule.startswith("AND,") else rule)
                           for rule in config["rules"]]
    elif mutate == "devices-first":
        devices = [rule for rule in config["rules"] if rule.startswith(("RULE-SET,src_alone1,", "RULE-SET,src_alone2,"))]
        config["rules"] = devices + [rule for rule in config["rules"] if rule not in devices]
    return config


def run(root, candidate, binary, evidence, mutate=None, dns_contract=False):
    evidence.mkdir(parents=True, exist_ok=False)
    with socketserver.UDPServer(("127.0.0.1", 0), DNS) as dns:
        dns.queries = 0
        thread = threading.Thread(target=dns.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix="mihomo-test-", dir=evidence) as temporary:
                home = Path(temporary)
                port = free_port()
                config = prepare(root, candidate, home, port, dns.server_address[1], mutate)
                selected_cases = cases()
                if dns_contract:
                    config["rules"] = [
                        "AND,((DOMAIN,no-resolve-fixture.invalid),(IP-CIDR,203.0.114.123/32,no-resolve)),🎯 全球直连",
                        "DOMAIN,no-resolve-fixture.invalid,🐟 漏网之鱼",
                        "AND,((DOMAIN,resolve-fixture.invalid),(IP-CIDR,203.0.114.123/32)),🎯 全球直连",
                        "MATCH,🐟 漏网之鱼",
                    ]
                    selected_cases = [("127.0.0.1","no-resolve-fixture.invalid","🐟 漏网之鱼"),
                                      ("127.0.0.1","resolve-fixture.invalid","🎯 全球直连")]
                controller_port = free_port()
                config["external-controller"] = f"127.0.0.1:{controller_port}"
                path = home / "config.yaml"
                syntax_config = copy.deepcopy(config)
                syntax_config["proxy-groups"] = load(root / "fragments/proxy-groups.yaml")["proxy-groups"]
                labels = {"fixture-node"}
                labels.update(group.get("default-selected") for group in syntax_config["proxy-groups"]
                              if group.get("default-selected") not in {None, "DIRECT", "REJECT"})
                syntax_config["proxies"] = [{"name":label, "type":"http", "server":"127.0.0.1", "port":9} for label in sorted(labels)]
                path.write_text(yaml.safe_dump(syntax_config, allow_unicode=True, sort_keys=False), encoding="utf-8")
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                checked = subprocess.run([str(binary), "-d", str(home), "-f", str(path), "-t"],
                                         capture_output=True, timeout=60, creationflags=flags)
                (evidence / "syntax.log").write_bytes(checked.stdout + checked.stderr)
                if checked.returncode:
                    raise RuntimeError("Mihomo syntax check failed; see syntax.log")
                path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
                log_path = evidence / "kernel.log"
                results = []
                with log_path.open("wb") as log:
                    process = subprocess.Popen([str(binary), "-d", str(home), "-f", str(path)],
                                               stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
                    try:
                        deadline = time.monotonic() + 30
                        while True:
                            if process.poll() is not None:
                                raise RuntimeError("Mihomo exited during startup")
                            try:
                                with socket.create_connection(("127.0.0.1", port), timeout=.2):
                                    break
                            except OSError:
                                if time.monotonic() > deadline:
                                    raise TimeoutError("Mihomo startup timeout")
                                time.sleep(.1)
                        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                        expected_counts = {
                            name: len(load(home / provider["path"])["payload"])
                            for name, provider in config["rule-providers"].items()
                        }
                        deadline = time.monotonic() + 30
                        while True:
                            with opener.open(f"http://127.0.0.1:{controller_port}/providers/rules", timeout=2) as response:
                                ready = json.load(response)["providers"]
                            if all(ready.get(name, {}).get("ruleCount", 0) == count for name, count in expected_counts.items()):
                                break
                            if time.monotonic() > deadline:
                                mismatches = {name: {"expected":count, "loaded":ready.get(name, {}).get("ruleCount", 0)}
                                              for name, count in expected_counts.items() if ready.get(name, {}).get("ruleCount", 0) != count}
                                raise TimeoutError(f"rule providers incomplete or rules were rejected: {mismatches}")
                            time.sleep(.1)
                        for index, (source, host, expected) in enumerate(selected_cases):
                            queries_before = dns.queries
                            destination = f"{host}:{20000 + index}"
                            with socket.socket() as sock:
                                sock.settimeout(3)
                                sock.bind((source, 0))
                                sock.connect(("127.0.0.1", port))
                                sock.sendall(f"CONNECT {destination} HTTP/1.1\r\nHost: {destination}\r\n\r\n".encode())
                                try:
                                    sock.recv(4096)
                                except (OSError, TimeoutError):
                                    pass
                            deadline = time.monotonic() + 3
                            observed = ""
                            while time.monotonic() < deadline:
                                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                                observed = next((line for line in reversed(lines) if destination in line and ("match " in line)), "")
                                if observed:
                                    break
                                time.sleep(.05)
                            dns_queries = dns.queries - queries_before
                            passed = f"using {expected}[REJECT]" in observed
                            if dns_contract:
                                passed = passed and (dns_queries == 0 if host.startswith("no-resolve-") else dns_queries > 0)
                            results.append({"source":source, "host":host, "expected":expected, "passed":passed, "dns_queries":dns_queries, "log":observed})
                            if not passed:
                                print(json.dumps(results[-1], ensure_ascii=False), flush=True)
                    finally:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                report = {"kernel":subprocess.check_output([str(binary), "-v"]).decode(errors="replace").strip(),
                          "scope":"isolated loopback first-match; all outbounds REJECT; not real service connectivity",
                          "mutate":mutate, "dns_queries":dns.queries, "cases":results}
                (evidence / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                failures = sum(not case["passed"] for case in results)
                print(json.dumps({"cases":len(results), "failures":failures, "evidence":str(evidence)}))
                return failures == 0
        finally:
            dns.shutdown()
            thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--mihomo", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--mutate", choices=["bnq-shadow", "devices-first"])
    args = parser.parse_args()
    passed = run(args.root, args.candidate, args.mihomo.resolve(), args.evidence, args.mutate)
    if passed and not args.mutate:
        passed = run(args.root, args.candidate, args.mihomo.resolve(), args.evidence / "dns-contract", dns_contract=True)
    raise SystemExit(0 if passed else 1)
