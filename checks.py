"""Deterministic consistency / completeness checks on the extracted knowledge base."""
import difflib

BITS = {"uint8": 8, "uint16": 16, "uint32": 32, "sint8": 8, "sint16": 16, "sint32": 32, "boolean": 1, "float32": 32}


def run_checks(kb):
    out = []
    comps = {c["name"] for c in kb["components"]}
    ports = {f"{p['component']}.{p['port']}": p for p in kb["ports"]}
    ifaces = {}
    for i in kb["interfaces"]:
        ifaces.setdefault(i["name"], []).append(i)
    connected_req = {c["requirer"] for c in kb["connections"]}
    connected_prov = {c["provider"] for c in kb["connections"]}
    mapped = {s["mapped_port"] for s in kb["signals"]}

    def add(rule, sev, key, msg, rec):
        out.append({"rule": rule, "severity": sev, "key": key, "message": msg,
                    "page": rec.get("page") if rec else None, "section": rec.get("section") if rec else None})

    for pid, p in ports.items():  # R1 / R7
        if p["direction"] == "R-Port" and pid not in connected_req:
            add("R1", "high", pid, f"Required port {pid} has no provider connection", p)
        if p["direction"] == "P-Port" and pid not in connected_prov and pid not in mapped:
            add("R7", "low", pid, f"Provided port {pid} has no consumer connection or mapped signal", p)
    for s in kb["signals"]:  # R2
        port = ports.get(s["mapped_port"])
        if not port:
            continue
        for i in ifaces.get(port["interface"], []):
            bits = BITS.get(i["datatype"])
            if bits and isinstance(s["length_bits"], int) and bits != s["length_bits"]:
                add("R2", "high", s["name"], f"Signal {s['name']} is {s['length_bits']} bit but interface "
                    f"{i['name']} defines {i['datatype']} ({bits} bit)", s)
    seen = set()
    for r in kb.get("referenced_swcs", []):  # R3
        if r["name"] not in comps and r["name"] not in seen:
            seen.add(r["name"])
            add("R3", "medium", r["name"], f"{r['name']} is referenced in the text but missing from the component catalogue", r)
    known = {s["name"] for s in kb["signals"]} | {i["element"] for i in kb["interfaces"]}
    for t in kb.get("camel_tokens", []):  # R4
        if t["token"] in known:
            continue
        best = max(known, key=lambda k: difflib.SequenceMatcher(None, t["token"], k).ratio(), default=None)
        if best and difflib.SequenceMatcher(None, t["token"], best).ratio() >= 0.85:
            add("R4", "low", t["token"], f"Terminology: '{t['token']}' is very similar to defined name '{best}'", t)
    for c in kb["connections"]:  # R5 / R6
        p, r = ports.get(c["provider"]), ports.get(c["requirer"])
        for end, port in ((c["provider"], p), (c["requirer"], r)):
            if not port:
                add("R6", "high", end, f"Connection endpoint {end} is not defined in the port table", c)
        if p and r and p["interface"] != r["interface"]:
            add("R5", "high", f"{c['provider']}->{c['requirer']}",
                f"Interface mismatch: {p['interface']} vs {r['interface']}", c)
    for pid, p in ports.items():
        if p["component"] not in comps:
            add("R6", "high", pid, f"Port {pid} belongs to a component missing from the catalogue", p)
        if p["interface"] not in ifaces:
            add("R6", "high", pid, f"Port {pid} references undefined interface {p['interface']}", p)
    return out
