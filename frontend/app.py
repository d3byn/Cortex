import math
import os
import re
import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
POLL_SECONDS = 1.0

st.set_page_config(page_title="Document Intelligence Platform", layout="wide")
st.title("📄 Document Intelligence & Retrieval Platform")
st.caption("Grounded, citation-backed Q&A over your PDF / TXT / Markdown files — powered by Gemini.")


# Text helpers: ensure original text is shown literally, not re-styled.
_MD_INLINE = re.compile(r"([\\`*_\[\]<>])")
_MD_BLOCK_START = re.compile(r"^(\s*)([#>|=+\-]|\d+[.)])", flags=re.MULTILINE)

def escape_markdown(text: str) -> str:
    """Show source text literally instead of letting it style itself."""
    return _MD_BLOCK_START.sub(r"\1\\\2", _MD_INLINE.sub(r"\\\1", text))

def shorten(text: str, limit: int = 700) -> tuple[str, bool]:
    """Trim to `limit` characters on a word boundary. Returns (text, was_cut)."""
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    spaced = cut.rsplit(" ", 1)[0]
    return (spaced if len(spaced) > limit * 0.6 else cut).rstrip(" ,;:-") + "…", True


def relevance_percent(score: float) -> int:
    return round(100 / (1 + math.exp(-max(-30.0, min(30.0, score)))))

def render_citation(index: int, citation: dict) -> None:
    percent = relevance_percent(citation["score"])
    body, truncated = shorten(citation["text"])

    with st.container(border=True):
        header, badge = st.columns([4, 1])
        header.markdown(f"**{index}. {citation['filename']}** (chunk {citation['chunk_index']})")
        badge.markdown(
            f"<div style='text-align:right;opacity:.75'>{percent}% match</div>",
            unsafe_allow_html=True,
        )
        for paragraph in (p for p in body.split("\n") if p.strip()):
            st.markdown(escape_markdown(paragraph))
        if truncated:
            st.caption("Snippet truncated — this is part of a longer chunk.")


# Upload flow: ingest jobs outlive script re-runs, so job_id lives in st.session_state.
# upload_banner carries success/failure messages across re-runs to refresh the document list.
st.session_state.setdefault("ingest_job_id", None)
st.session_state.setdefault("upload_banner", None)
st.session_state.setdefault("uploader_round", 0)
st.session_state.setdefault("history", [])


def start_ingestion(file) -> None:
    """POST the file and remember the job id; the polling fragment takes it from here."""
    try:
        resp = requests.post(
            f"{BACKEND_URL}/ingest",
            files={"file": (file.name, file.getvalue())},
            timeout=120,
        )
    except requests.RequestException as exc:
        st.session_state.upload_banner = ("error", f"Could not reach the backend: {exc}")
        return

    if resp.status_code != 202:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        st.session_state.upload_banner = ("error", f"Upload failed: {detail}")
        return

    st.session_state.ingest_job_id = resp.json()["job_id"]
    st.session_state.upload_banner = None


def finish_ingestion(banner: tuple[str, str]) -> None:
    """Clear the job, show the outcome, and reset the uploader widget."""
    st.session_state.ingest_job_id = None
    st.session_state.upload_banner = banner
    # Bumping the key gives file_uploader a fresh identity, which empties it —
    # otherwise the just-finished file sits there inviting a duplicate ingest.
    st.session_state.uploader_round += 1


@st.fragment(run_every=POLL_SECONDS)
def ingestion_progress() -> None:
    # Poll the backend for the status of the current ingestion job, if any
    job_id = st.session_state.ingest_job_id
    if not job_id:
        return

    try:
        resp = requests.get(f"{BACKEND_URL}/jobs/{job_id}", timeout=10)
    except requests.RequestException as exc:
        st.warning(f"Lost contact with the backend, retrying… ({exc})")
        return

    if resp.status_code == 404:
        finish_ingestion(("error", "That upload job is no longer on the server. Please try again."))
        st.rerun(scope="app")
        return
    if resp.status_code != 200:
        st.warning("Waiting for the backend…")
        return

    job = resp.json()
    status = job.get("status", "processing")
    percent = int(job.get("progress") or 0)
    stage = job.get("stage") or "Processing"
    name = job.get("filename") or "file"

    if status == "complete":
        finish_ingestion(("success", f"✅ **{name}** ingested and ready to query."))
        st.rerun(scope="app")   # refresh the document list in the sidebar
        return
    if status == "failed":
        finish_ingestion(("error", f"❌ Ingestion failed: {job.get('error') or 'unknown error'}"))
        st.rerun(scope="app")
        return

    st.progress(percent / 100, text=f"{stage} — {percent}%")
    st.caption(f"Processing **{name}**… you can keep reading while this finishes.")

# Sidebar: upload + document list (with delete) + search scope

with st.sidebar:
    st.header("📥 Upload a document")

    is_busy = st.session_state.ingest_job_id is not None
    uploaded_file = st.file_uploader(
        "PDF, TXT, or Markdown",
        type=["pdf", "txt", "md"],
        key=f"uploader_{st.session_state.uploader_round}",
        disabled=is_busy,
    )
    if st.button("Processing…" if is_busy else "Ingest file",
                 disabled=is_busy or uploaded_file is None, use_container_width=True):
        start_ingestion(uploaded_file)
        st.rerun()

    if is_busy:
        ingestion_progress()

    if st.session_state.upload_banner:
        kind, message = st.session_state.upload_banner
        (st.success if kind == "success" else st.error)(message)

    st.divider()
    st.header("📚 Your documents")

    try:
        docs_resp = requests.get(f"{BACKEND_URL}/documents", timeout=10)
        documents = docs_resp.json() if docs_resp.status_code == 200 else []
    except requests.RequestException:
        documents = []
        st.error(f"Backend unreachable — is it running on {BACKEND_URL}?")

    if not documents:
        st.caption("No documents ingested yet.")

    for doc in documents:
        col_name, col_delete = st.columns([5, 1])
        col_name.write(f"**{doc['filename']}** — {doc['num_chunks']} chunks")
        if col_delete.button("🗑️", key=f"delete_{doc['id']}", help=f"Delete {doc['filename']}"):
            del_resp = requests.delete(f"{BACKEND_URL}/documents/{doc['id']}", timeout=10)
            if del_resp.status_code == 204:
                st.rerun()
            else:
                st.error(f"Could not delete: {del_resp.text}")

    st.divider()
    doc_options = {"All documents": []}
    for doc in documents:
        doc_options[doc["filename"]] = [doc["id"]]
    selected_label = st.selectbox("Search scope", list(doc_options.keys()))
    selected_document_ids = doc_options[selected_label] or None   # [] -> None means "search everything"

# Main panel: chat

for turn in st.session_state.history:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])

question = st.chat_input("Ask a question about your documents...")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            payload = {"question": question, "document_ids": selected_document_ids}
            try:
                resp = requests.post(f"{BACKEND_URL}/query", json=payload, timeout=60)
            except requests.RequestException as exc:
                resp = None
                st.error(f"Could not reach the backend: {exc}")

        if resp is not None:
            if resp.status_code != 200:
                try:
                    detail = resp.json().get("detail", resp.text)
                except ValueError:
                    detail = resp.text
                st.error(f"Query failed: {detail}")
            else:
                data = resp.json()
                st.write(data["answer"])

                badges = []
                if data["is_grounded"] is True:
                    badges.append("✅ Grounded")
                elif data["is_grounded"] is False:
                    badges.append("⚠️ Not fully grounded")
                else:
                    badges.append("❔ Groundedness unknown")
                if data["retrieval_degraded"]:
                    badges.append("⚠️ Reranker unavailable — showing hybrid search results")
                if data["cached"]:
                    badges.append("⚡ Cached")
                st.caption(" · ".join(badges))

                citations = data["citations"]
                with st.expander(f"📎 Sources / citations ({len(citations)})"):
                    if not citations:
                        st.caption("No matching chunks were found.")
                    for i, citation in enumerate(citations, start=1):
                        render_citation(i, citation)

                with st.expander("🔍 Pipeline trace (observability)"):
                    st.write(f"Search query used: `{data['search_query']}`")
                    st.json(data["trace"])

                st.session_state.history.append({"question": question, "answer": data["answer"]})