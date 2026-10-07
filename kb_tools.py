"""Deterministic knowledge-base tools: entity/relationship lookups with page provenance.

These rules complement RAG for structured questions (ports, dependencies, signals, interfaces). Their output is
passed to the generator as additional cited evidence (source type 'kb').
"""
import re


def _w(name):
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", re.I)


class KBTools:
    def __init__(self, kb):
        self.kb = kb
        self.ver = kb.get("version")

    def _fact(self, text, rec):
        return {"text": text, "page": rec.get("page", 0) if rec else 0, "section": rec.get("section", "") if rec else "",
                "kind": "kb", "version": self.ver, "doc_key": self.kb["doc_key"]}

    # ---- lookups -----------------------------------------------------------------------------------------
    def _port(self, comp, port):
        return next((p for p in self.kb["ports"] if p["component"] == comp and p["port"] == port), None)

    def ports_of(self, comp):
        ps = [p for p in self.kb["ports"] if p["component"] == comp["name"]]
        if not ps:
            return None
        txt = (f"{comp['name']} has {len(ps)} ports: " +
               "; ".join(f"{p['port']} ({p['direction']}, {p['interface']})" for p in ps) + ".")
        return self._fact(txt, ps[0])

    def depends_on(self, comp):
        name = comp["name"]
        reqs = {f"{name}.{p['port']}" for p in self.kb["ports"] if p["component"] == name and p["direction"] == "R-Port"}
        deps = [(c["provider"], c["requirer"]) for c in self.kb["connections"] if c["requirer"] in reqs]
        if not deps:
            return None
        txt = f"{name} depends on: " + "; ".join(f"{p.split('.')[0]} (provider port {p.split('.')[1]} -> {r.split('.')[1]})"
                                                for p, r in deps) + "."
        return self._fact(txt, next(c for c in self.kb["connections"] if c["requirer"] in reqs))

    def dependents_of(self, comp):
        name = comp["name"]
        out = [(c["provider"], c["requirer"]) for c in self.kb["connections"] if c["provider"].startswith(name + ".")]
        if not out:
            return None
        return self._fact(f"Components that require ports of {name}: " +
                          "; ".join(f"{r.split('.')[0]} (via {r.split('.')[1]})" for _, r in out) + ".", None)

    def dids_of(self, comp):
        ds = [d for d in self.kb["dids"] if d["owner"] == comp["name"]]
        if not ds:
            return None
        return self._fact(f"{comp['name']} owns DIDs: " + "; ".join(f"{d['did']} {d['name']} ({d['length']} byte)" for d in ds) + ".", ds[0])

    def port_connections(self, pid):
        cs = [c for c in self.kb["connections"] if pid in (c["provider"], c["requirer"])]
        if not cs:
            return None
        parts = []
        for c in cs:
            if c["provider"] == pid:
                parts.append(f"provider {pid} -> requirer {c['requirer']} ({c['purpose']})")
            else:
                parts.append(f"requirer {pid} <- provider {c['provider']} ({c['purpose']})")
        return self._fact(f"Connections of {pid}: " + "; ".join(parts) + ".", cs[0])

    def signal_row(self, s):
        return self._fact(f"Signal {s['name']}: CAN message {s['message']} (ID {s['can_id']}), {s['length_bits']} bit, direction {s['dir']}, "
                          f"cycle {s['cycle']} ms, mapped to port {s['mapped_port']}.", s)

    def element_ports(self, element):
        ifs = {i["name"] for i in self.kb["interfaces"] if i["element"].lower() == element.lower()}
        return [p for p in self.kb["ports"] if p["interface"] in ifs]

    def interface_row(self, name):
        rows = [i for i in self.kb["interfaces"] if i["name"] == name]
        if not rows:
            return None
        els = ", ".join(f"{r['element']} ({r['datatype']})" for r in rows)
        return self._fact(f"{name} is a {rows[0]['kind']} interface with elements/operations: {els}.", rows[0])

    # ---- question routing ---------------------------------------------------------------------------------
    def facts_for(self, q):
        kb, out = self.kb, []
        add = lambda f: out.append(f) if f and f["text"] not in {o["text"] for o in out} else None  # noqa: E731
        ql = q.lower()
        ports_in_q = re.findall(r"SWC_[A-Za-z0-9]+\.[PR]P_[A-Za-z0-9]+", q)
        for pid in ports_in_q:
            add(self.port_connections(pid))
        comps = [c for c in kb["components"] if _w(c["name"]).search(q) or _w(c["name"].replace("SWC_", "")).search(q)]
        sigs = [s for s in kb["signals"] if _w(s["name"]).search(q) or _w(s["message"]).search(q)]
        elems = {i["element"] for i in kb["interfaces"] if _w(i["element"]).search(q)} - {s["name"] for s in sigs}
        ifaces = sorted({i["name"] for i in kb["interfaces"] if _w(i["name"]).search(q)})
        intent = {
            "ports": re.search(r"\bports?\b", ql), "depends": re.search(r"\b(depend\w*|requires?|needs?)\b", ql),
            "consumers": re.search(r"\b(consum\w+|receiv\w+|uses?|used by|read)\b", ql),
            "providers": re.search(r"\b(provid\w+|produc\w+|source|sends?|publish\w*|supplies|which component)\b", ql),
            "datatype": re.search(r"\b(data ?type|type of|width)\b", ql),
            "dids": re.search(r"\b(dids?|data identifiers?)\b", ql),
            "dependents": re.search(r"\b(who requires|required by|dependents?)\b", ql),
        }
        for c in comps[:2]:
            add(self._fact(f"{c['name']} is {'an' if c['type'][0] in 'AEIOU' else 'a'} {c['type']} component: {c['responsibility'][0].lower() + c['responsibility'][1:]}.", c))
            if intent["ports"]:
                add(self.ports_of(c))
            if intent["depends"]:
                add(self.depends_on(c))
            if intent["dependents"]:
                add(self.dependents_of(c))
            if intent["dids"]:
                add(self.dids_of(c))
        for s in sigs[:2]:
            add(self.signal_row(s))
            ports = self.element_ports(s["name"])
            if intent["providers"] or intent["consumers"]:
                prov = [p for p in ports if p["direction"] == "P-Port"]
                cons = [p for p in ports if p["direction"] == "R-Port"]
                if intent["providers"] and prov:
                    add(self._fact(f"{s['name']} is provided by " + ", ".join(f"{p['component']} (port {p['port']}, interface {p['interface']})" for p in prov) + ".", prov[0]))
                if intent["consumers"] and cons:
                    add(self._fact(f"{s['name']} is consumed by " + ", ".join(f"{p['component']} (port {p['port']})" for p in cons) + ".", cons[0]))
            if intent["datatype"]:
                for i in [i for i in kb["interfaces"] if i["element"] == s["name"]]:
                    add(self._fact(f"{s['name']} (interface {i['name']}) has data type {i['datatype']}.", i))
        for e in sorted(elems)[:2]:
            for i in [i for i in kb["interfaces"] if i["element"] == e]:
                add(self._fact(f"{e} (interface {i['name']}) has data type {i['datatype']}.", i))
        for n in ifaces[:2]:
            add(self.interface_row(n))
        if re.search(r"\b(list|all|how many)\b.*\bcomponents\b", ql) and not comps:
            add(self._fact("Components: " + ", ".join(c["name"] for c in kb["components"]) + ".", kb["components"][0]))
        return out[:8]
