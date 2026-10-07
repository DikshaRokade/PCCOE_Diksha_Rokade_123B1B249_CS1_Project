"""Command-line interface:  python -m hldrag.cli <command>"""
import argparse
import json
import logging

from .pipeline import HLDService


def main():
    logging.basicConfig(level=logging.WARNING)
    ap = argparse.ArgumentParser(prog="hldrag")
    ap.add_argument("--project", default=None)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest"); p.add_argument("pdf", nargs="+")
    p = sub.add_parser("ask"); p.add_argument("question"); p.add_argument("--doc", action="append")
    p = sub.add_parser("checks"); p.add_argument("doc_key")
    p = sub.add_parser("compare"); p.add_argument("old"); p.add_argument("new")
    sub.add_parser("docs")
    sub.add_parser("info")
    a = ap.parse_args()
    s = HLDService(project=a.project)
    if a.cmd == "ingest":
        for f in a.pdf:
            print(json.dumps(s.ingest(f), indent=1))
    elif a.cmd == "ask":
        r = s.query(a.question, a.doc)
        print(r["answer"], f"\n\nconfidence={r['confidence']} mode={r['mode']} coverage={r['coverage']}")
        for src in r["sources"]:
            print(f"  [{src['id']}] v{src['version']} p.{src['page']} {src['section']} ({src['type']})")
    elif a.cmd == "checks":
        for c in s.checks(a.doc_key):
            print(f"{c['rule']} {c['severity']:6} p.{c['page']}  {c['message']}")
    elif a.cmd == "compare":
        d = s.compare(a.old, a.new)
        for c in d["entity_changes"]:
            print(c["key"])
        for t in d["text_changes"]:
            print("TEXT", t["section"], "+", t["added"], "-", t["removed"])
    elif a.cmd == "docs":
        print(json.dumps(s.docs(), indent=1))
    else:
        print(json.dumps(s.info(), indent=1))


if __name__ == "__main__":
    main()
