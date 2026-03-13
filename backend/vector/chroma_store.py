"""
Chroma Vector Store

Responsibilities:
  - Initialize and manage Chroma vector database
  - Store interaction summaries as embeddings per customer
  - Retrieve semantically relevant memories for a customer query
  - Support context window construction for LLM reasoning

Storage location: ./chroma_db/ (local persistent directory)

Collections:
  - "customer_memories"  → interaction summaries per customer
  - "policy_documents"   → RAG knowledge base (policies, guidelines)
"""

import os
import uuid
from datetime import datetime

import chromadb
from chromadb.config import Settings


# ─────────────────────────────────────────────
# Chroma Client Initialization
# ─────────────────────────────────────────────

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")

def get_chroma_client() -> chromadb.PersistentClient:
    """
    Initialize and return a persistent Chroma client.
    Database is stored locally at ./chroma_db/
    """
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client


# ─────────────────────────────────────────────
# Embedding Function
# ─────────────────────────────────────────────

def get_embedding_function():
    """
    Return the embedding function for Chroma.
    Uses sentence-transformers (all-MiniLM-L6-v2) for local embeddings.
    Falls back to Chroma's default if sentence-transformers unavailable.
    """
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    except Exception as e:
        print(f"[ChromaStore] SentenceTransformer unavailable, using default: {e}")
        return chromadb.utils.embedding_functions.DefaultEmbeddingFunction()


# ─────────────────────────────────────────────
# Get or Create Collection
# ─────────────────────────────────────────────

def get_memory_collection():
    """
    Get or create the 'customer_memories' Chroma collection.
    """
    client     = get_chroma_client()
    embed_fn   = get_embedding_function()

    collection = client.get_or_create_collection(
        name               = "customer_memories",
        embedding_function = embed_fn,
        metadata           = {"description": "Customer interaction summaries for semantic memory"}
    )
    return collection


def get_policy_collection():
    """
    Get or create the 'policy_documents' Chroma collection.
    Used for RAG — retrieval of collection policies and guidelines.
    """
    client     = get_chroma_client()
    embed_fn   = get_embedding_function()

    collection = client.get_or_create_collection(
        name               = "policy_documents",
        embedding_function = embed_fn,
        metadata           = {"description": "Banking collection policies and regulatory guidelines"}
    )
    return collection


# ─────────────────────────────────────────────
# Store Interaction Memory
# ─────────────────────────────────────────────

def store_memory(
    customer_id: str,
    summary: str,
    metadata: dict = None
) -> str:
    """
    Store an interaction summary as an embedding in Chroma.

    Args:
        customer_id: Customer ID (used for filtering on retrieval)
        summary:     Interaction summary text to embed
        metadata:    Optional metadata dict (interaction_type, timestamp, etc.)

    Returns:
        memory_id (str)
    """
    if not summary or not summary.strip():
        return None

    try:
        collection = get_memory_collection()
        memory_id  = str(uuid.uuid4())

        meta = {
            "customer_id": customer_id,
            "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if metadata:
            meta.update(metadata)

        collection.add(
            ids        = [memory_id],
            documents  = [summary],
            metadatas  = [meta],
        )

        print(f"[ChromaStore] Stored memory {memory_id} for customer {customer_id}")
        return memory_id

    except Exception as e:
        print(f"[ChromaStore] store_memory failed: {e}")
        return None


# ─────────────────────────────────────────────
# Retrieve Relevant Memories
# ─────────────────────────────────────────────

def retrieve_memories(
    customer_id: str,
    query: str,
    top_k: int = 3
) -> list[str]:
    """
    Retrieve the top-K most semantically relevant interaction summaries
    for a customer based on a query string.

    Args:
        customer_id: Filter memories to this customer only
        query:       Query text for semantic search
        top_k:       Number of results to return

    Returns:
        List of relevant summary strings
    """
    if not query or not query.strip():
        return []

    try:
        collection = get_memory_collection()

        # Check if collection has any documents for this customer
        existing = collection.get(
            where = {"customer_id": customer_id}
        )
        if not existing or not existing.get("ids"):
            return []

        results = collection.query(
            query_texts = [query],
            n_results   = min(top_k, len(existing["ids"])),
            where       = {"customer_id": customer_id},
        )

        documents = results.get("documents", [[]])[0]
        return documents

    except Exception as e:
        print(f"[ChromaStore] retrieve_memories failed: {e}")
        return []


# ─────────────────────────────────────────────
# Store Policy Document (RAG)
# ─────────────────────────────────────────────

def store_policy_document(
    doc_id: str,
    content: str,
    metadata: dict = None
) -> bool:
    """
    Store a policy document chunk in the policy_documents collection.
    Used for RAG-based policy retrieval.

    Args:
        doc_id:   Unique document chunk ID
        content:  Policy text content
        metadata: Optional metadata (source, category, etc.)

    Returns:
        True if stored successfully
    """
    try:
        collection = get_policy_collection()

        meta = {"source": "policy", "timestamp": datetime.now().strftime("%Y-%m-%d")}
        if metadata:
            meta.update(metadata)

        collection.upsert(
            ids        = [doc_id],
            documents  = [content],
            metadatas  = [meta],
        )
        print(f"[ChromaStore] Stored policy document: {doc_id}")
        return True

    except Exception as e:
        print(f"[ChromaStore] store_policy_document failed: {e}")
        return False


# ─────────────────────────────────────────────
# Retrieve Policy Documents (RAG)
# ─────────────────────────────────────────────

def retrieve_policy_documents(
    query: str,
    top_k: int = 3
) -> list[str]:
    """
    Retrieve relevant policy documents for a given query.
    Used in RAG pipeline for policy-aware recommendations.

    Args:
        query: User query or context string
        top_k: Number of results

    Returns:
        List of relevant policy text chunks
    """
    if not query or not query.strip():
        return []

    try:
        collection = get_policy_collection()

        existing = collection.get()
        if not existing or not existing.get("ids"):
            return []

        results = collection.query(
            query_texts = [query],
            n_results   = min(top_k, len(existing["ids"])),
        )

        documents = results.get("documents", [[]])[0]
        return documents

    except Exception as e:
        print(f"[ChromaStore] retrieve_policy_documents failed: {e}")
        return []


# ─────────────────────────────────────────────
# Delete Customer Memories
# ─────────────────────────────────────────────

def delete_customer_memories(customer_id: str) -> bool:
    """
    Delete all stored memories for a specific customer.
    """
    try:
        collection = get_memory_collection()
        existing   = collection.get(where={"customer_id": customer_id})

        if existing and existing.get("ids"):
            collection.delete(ids=existing["ids"])
            print(f"[ChromaStore] Deleted {len(existing['ids'])} memories for {customer_id}")

        return True

    except Exception as e:
        print(f"[ChromaStore] delete_customer_memories failed: {e}")
        return False


# ─────────────────────────────────────────────
# Seed Default Policy Documents
# ─────────────────────────────────────────────

def seed_policy_documents():
    """
    Seed the policy_documents collection with default banking
    collection policies for RAG retrieval.
    """
    policies = [
        {
            "doc_id":  "POL001",
            "content": (
                "Grace Period Policy: A grace period of up to 7 days may be granted "
                "to borrowers with Days Past Due (DPD) less than 30 days. "
                "The borrower must have no more than 2 grace period requests per loan per year. "
                "Grace period is not available for High risk borrowers without officer approval. "
                "Minimum credit score of 450 is required for grace period eligibility."
            ),
            "metadata": {"category": "grace_policy", "source": "Collections Policy Manual v2.1"}
        },
        {
            "doc_id":  "POL002",
            "content": (
                "Loan Restructuring Policy: Loan restructuring may be considered for borrowers "
                "with DPD between 5 and 90 days. Beyond 90 DPD, the account is referred to the "
                "legal recovery team. Restructuring options include: (1) Tenure extension up to 24 months, "
                "(2) EMI reduction through interest rate adjustment, (3) Partial payment deferral. "
                "Minimum credit score of 400 required. Senior officer approval required for "
                "outstanding balance above ₹1,00,000."
            ),
            "metadata": {"category": "restructure_policy", "source": "Collections Policy Manual v2.1"}
        },
        {
            "doc_id":  "POL003",
            "content": (
                "Recovery Strategy Guidelines: "
                "Low Risk (DPD 0-5): Proactive engagement and friendly reminders. "
                "Medium Risk (DPD 5-29): Grace period outreach or structured repayment plan. "
                "High Risk (DPD 30+): Loan restructuring or intensive recovery with officer escalation. "
                "All High risk accounts require mandatory bank officer review before action. "
                "Self cure probability above 70% indicates low intervention needed."
            ),
            "metadata": {"category": "recovery_strategy", "source": "Risk Management Framework v3.0"}
        },
        {
            "doc_id":  "POL004",
            "content": (
                "Customer Communication Policy: All customer outreach must use the customer's "
                "preferred communication channel as saved in the system. "
                "Communication must be respectful, empathetic, and compliant with RBI guidelines. "
                "Collection calls are permitted only between 8:00 AM and 7:00 PM. "
                "Customers must not be contacted more than 3 times per day. "
                "All interactions must be logged in the system within 24 hours."
            ),
            "metadata": {"category": "communication_policy", "source": "RBI Fair Practices Code"}
        },
        {
            "doc_id":  "POL005",
            "content": (
                "NPA Classification Policy: A loan is classified as Non-Performing Asset (NPA) "
                "when DPD exceeds 90 days. NPA accounts are transferred to the legal recovery team. "
                "Once classified as NPA, standard collection activities are suspended. "
                "Borrower must be formally notified before NPA classification. "
                "Restructuring must be completed before DPD reaches 90 to avoid NPA status."
            ),
            "metadata": {"category": "npa_policy", "source": "RBI Asset Classification Guidelines"}
        },
    ]

    for policy in policies:
        store_policy_document(
            doc_id   = policy["doc_id"],
            content  = policy["content"],
            metadata = policy["metadata"]
        )

    print(f"[ChromaStore] ✅ Seeded {len(policies)} policy documents.")