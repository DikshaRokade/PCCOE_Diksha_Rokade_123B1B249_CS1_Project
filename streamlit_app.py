"""Streamlit engineering UI. Talks to the FastAPI backend (HLD_API_URL, HLD_API_KEY)."""
import os

import pandas as pd
import requests
import streamlit as st

API = os.environ.get("HLD_API_URL", "http://localhost:8000")
KEY = os.environ.get("HLD_API_KEY", "dev-engineer-key")
PROJECT = os.environ.get("HLD_PROJECT", "default")
H = {"X-API-Key": KEY}

st.set_page_config(page_title="AUTOSAR HLD Assistant", layout="wide")
st.title("AUTOSAR HLD Document Analysis Assistant")
st.caption("Grounded, cited answers from approved HLD documents. Every output requires engineer review before use.")


def call(method, path, **kw):
    try:
        r = requests.request(method, f"{API}/projects/{PROJECT}{path}", headers=H, timeout=180, **kw)
    except requests.RequestException as ex:
        st.error(f"Backend not reachable at {API}: {ex}")
        st.stop()
    if r.status_code >= 400:
        st.error(f"{r.status_code}: {r.json().get('detail', r.text)}")
        return None
    return r


docs_r = call("GET", "/documents")
docs = docs_r.json() if docs_r else []
keys = [d["doc_key"] for d in docs]
tabs = st.tabs(["Documents", "Ask", "Entities", "Consistency checks", "Compare versions", "Review & audit"])

with tabs[0]:
    up = st.file_uploader("Upload an approved HLD PDF", type=["pdf"])
    if up and st.button("Ingest"):
        with st.spinner("Extracting, chunking, embedding..."):
            r = call("POST", "/documents", files={"file": (up.name, up.getvalue(), "application/pdf")})
        if r:
            st.success(r.json())
            st.rerun()
    if docs:
        st.dataframe(pd.DataFrame(docs)[["doc_key", "filename", "pages", "chunks", "ingested_at", "ingested_by"]], width="stretch")

with tabs[1]:
    if not keys:
        st.info("Upload a document first.")
    else:
        sel = st.multiselect("Document versions to search", keys, default=keys[:1])
        q = st.text_input("Question", placeholder="At what vehicle speed does auto-lock trigger?")
        if st.button("Ask") and q:
            with st.spinner("Retrieving and generating..."):
                r = call("POST", "/query", json={"question": q, "doc_keys": sel or None})
            if r:
                st.session_state["last"] = r.json()
        res = st.session_state.get("last")
        if res:
            (st.warning if res["abstained"] else st.success)(res["answer"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Confidence", res["confidence"])
            c2.metric("Query coverage", res["coverage"])
            c3.metric("Generation", res["mode"])
            st.markdown("**Sources**")
            for s in res["sources"]:
                with st.expander(f"[{s['id']}] v{s['version']} - page {s['page']} - {s['section']} ({s['type']})"):
                    st.write(s["body"])
            st.markdown("**Engineer review**")
            decision = st.radio("Decision", ["accepted", "edited", "rejected"], horizontal=True)
            edited = st.text_area("Edited answer (if edited)")
            comment = st.text_input("Comment")
            if st.button("Submit review"):
                if call("POST", "/reviews", json={"question": res["question"], "answer": res["answer"], "sources": res["sources"],
                                                     "decision": decision, "edited_answer": edited, "comment": comment}):
                    st.success("Review recorded in the audit trail.")

with tabs[2]:
    if keys:
        dk = st.selectbox("Document", keys, key="ent")
        ent = call("GET", "/entities", params={"doc_key": dk})
        if ent:
            for k, rows in ent.json().items():
                st.subheader(k.capitalize())
                st.dataframe(pd.DataFrame(rows), width="stretch")

with tabs[3]:
    if keys:
        dk = st.selectbox("Document", keys, key="chk")
        r = call("GET", "/checks", params={"doc_key": dk})
        if r:
            df = pd.DataFrame(r.json())
            st.dataframe(df, width="stretch") if len(df) else st.success("No issues flagged")
            st.caption("Flagged items are candidates for engineer review, not confirmed defects.")
            ex = call("GET", "/export", params={"kind": "checks", "doc_key": dk})
            if ex and len(df):
                st.download_button("Download CSV", ex.text, file_name=f"checks_{dk}.csv")

with tabs[4]:
    if len(keys) >= 2:
        o, n = st.selectbox("Old version", keys, index=0), st.selectbox("New version", keys, index=len(keys) - 1)
        r = call("GET", "/compare", params={"old": o, "new": n})
        if r:
            d = r.json()
            st.subheader("Entity changes")
            st.dataframe(pd.DataFrame([{"change": c["key"], "page": c.get("page"), "detail": c.get("fields") or c.get("new") or c.get("old")}
                                       for c in d["entity_changes"]]), width="stretch")
            st.subheader("Text changes")
            for t in d["text_changes"]:
                st.markdown(f"**{t['section']}** ({t['change']}, page {t['page']})")
                for x in t["removed"]:
                    st.markdown(f"- ~~{x}~~")
                for x in t["added"]:
                    st.markdown(f"+ {x}")
    else:
        st.info("Ingest two versions to compare.")

with tabs[5]:
    r = call("GET", "/reviews")
    if r:
        st.subheader("Reviews")
        st.dataframe(pd.DataFrame(r.json()).drop(columns=["sources"], errors="ignore"), width="stretch")
    a = call("GET", "/audit")
    if a:
        st.subheader("Audit log")
        st.dataframe(pd.DataFrame(a.json()), width="stretch")
