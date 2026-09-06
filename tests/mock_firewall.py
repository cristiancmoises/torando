#!/usr/bin/env python3
"""A stateful command double. It never invokes a real firewall command."""

import copy
import json
import os
from pathlib import Path
import shlex
import sys


def main():
    name = Path(sys.argv[0]).name
    args = sys.argv[1:]
    if name == "uname":
        print(os.environ.get("MOCK_OS", "Linux"))
        return 0
    if name == "id":
        if args == ["-u"]:
            print(os.environ.get("MOCK_EUID", "0"))
            return 0
        users = {"alice": "1000", "bob": "1001", "tor": "43", "root": "0"}
        users.update({value: value for value in list(users.values())})
        if len(args) == 3 and args[:2] == ["-u", "--"] and args[2] in users:
            print(users[args[2]])
            return 0
        return 1
    if name == "pgrep":
        return int(os.environ.get("MOCK_PGREP_EXIT", "1"))
    if name not in {"iptables", "ip6tables"}:
        raise RuntimeError(f"unexpected mock command: {name}")

    path = Path(os.environ["TORANDO_TEST_STATE"])
    state = json.loads(path.read_text())
    if args[:3] != ["-w", "5", "-t"]:
        raise RuntimeError(f"missing bounded xtables lock wait: {args}")
    table, operation, chain, *rule = args[3:]
    state["calls"].append([name, table, operation, chain, *rule])

    def finish(code):
        path.write_text(json.dumps(state))
        return code

    failure = state.get("failure")
    if failure and [name, table, operation, chain] == failure["command"]:
        failure["remaining"] -= 1
        if failure["remaining"] == 0:
            state.pop("failure")
            print("mock: injected firewall failure", file=sys.stderr)
            return finish(4)

    chains = state["tables"][name][table]
    if operation == "-N":
        if chain in chains:
            return finish(1)
        chains[chain] = []
    elif chain not in chains:
        return finish(1)
    elif operation == "-S":
        print(f"-P {chain} ACCEPT" if chain == "OUTPUT" else f"-N {chain}")
        for entry in chains[chain]:
            normalized = list(entry)
            if "--dport" in entry:
                proto = entry[entry.index("-p") + 1]
                index = normalized.index("-p") + 2
                normalized[index:index] = ["-m", proto]
            if entry[-2:] == ["-j", "REJECT"]:
                normalized += ["--reject-with", "icmp6-port-unreachable" if name == "ip6tables" else "icmp-port-unreachable"]
            print(shlex.join(["-A", chain, *normalized]))
        return finish(0)
    elif operation == "-C":
        return finish(0 if rule in chains[chain] else 1)
    elif operation in {"-A", "-I"}:
        if operation == "-I":
            position = int(rule.pop(0)) - 1
        else:
            position = len(chains[chain])
        target = rule[rule.index("-j") + 1]
        if target not in {"ACCEPT", "DROP", "REJECT", "RETURN", "REDIRECT"} and target not in chains:
            return finish(1)
        chains[chain].insert(position, rule)
    elif operation == "-D":
        if rule not in chains[chain]:
            return finish(1)
        chains[chain].remove(rule)
    elif operation == "-F":
        chains[chain] = []
    elif operation == "-X":
        referenced = any(
            "-j" in entry and entry[entry.index("-j") + 1] == chain
            for entries in chains.values()
            for entry in entries
        )
        if chains[chain] or referenced or chain == "OUTPUT":
            return finish(1)
        del chains[chain]
    else:
        raise RuntimeError(f"unsupported operation: {operation}")
    state["history"].append(copy.deepcopy(state["tables"]))
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
