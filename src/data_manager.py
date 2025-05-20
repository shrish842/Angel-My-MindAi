import json
from datetime import datetime
import uuid # For generating unique IDs for chunks

# --- RAG Specific Imports ---
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMER_AVAILABLE = True
except ImportError:
    print("WARNING: sentence-transformers library not found. RAG features will be disabled.")
    SENTENCE_TRANSFORMER_AVAILABLE = False

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    print("WARNING: chromadb library not found. RAG features will be disabled.")
    CHROMADB_AVAILABLE = False

# --- Constants ---
DATA_FILE_PATH = "my_personal_data.jsonl" # Relative to project root

# --- RAG Configuration (can be moved to config.py later) ---
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' # Or your preferred Sentence Transformer model
CHROMA_DB_PATH = "./chroma_db_store" # Directory to store ChromaDB data
COLLECTION_NAME = "personal_log_embeddings"
RAG_ENABLED = SENTENCE_TRANSFORMER_AVAILABLE and CHROMADB_AVAILABLE

# --- Global RAG Components (initialize once) ---
embedding_model_instance = None
vector_store_client_instance = None
vector_collection_instance = None
rag_components_initialized = False


def initialize_rag_if_needed():
    """Initializes RAG components (embedding model and vector store) if not already done."""
    global embedding_model_instance, vector_store_client_instance, vector_collection_instance, rag_components_initialized

    if not RAG_ENABLED:
        print("RAG: RAG dependencies not met, RAG features are disabled.")
        rag_components_initialized = True # Mark as "initialized" to avoid repeated checks
        return False

    if rag_components_initialized:
        return True # Already initialized (or attempted and failed but marked)

    print("RAG: Attempting to initialize RAG components...")
    try:
        if embedding_model_instance is None:
            print(f"RAG: Initializing SentenceTransformer model: {EMBEDDING_MODEL_NAME}...")
            embedding_model_instance = SentenceTransformer(EMBEDDING_MODEL_NAME)
            print("RAG: SentenceTransformer model initialized.")

        if vector_store_client_instance is None:
            print("RAG: Initializing ChromaDB client...")
            vector_store_client_instance = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            print("RAG: ChromaDB client initialized.")

        if vector_collection_instance is None:
            print(f"RAG: Getting or creating Chroma collection: {COLLECTION_NAME}")
            vector_collection_instance = vector_store_client_instance.get_or_create_collection(
                name=COLLECTION_NAME,
                # Optional: Specify metadata for the embedding function if needed by ChromaDB
                # metadata={"hnsw:space": "cosine"} # Example for cosine distance
            )
            print(f"RAG: Chroma collection '{COLLECTION_NAME}' ready. Current count: {vector_collection_instance.count()}")

        rag_components_initialized = True
        print("RAG: All RAG components initialized successfully.")
        return True
    except Exception as e:
        print(f"RAG: Critical error initializing RAG components: {e}")
        # Potentially set components to None again if partial init failed
        embedding_model_instance = None
        vector_store_client_instance = None
        vector_collection_instance = None
        rag_components_initialized = True # Mark as "initialized" to prevent retry loops if fatal
        return False


def extract_text_chunks_for_embedding(entry_data):
    """
    Extracts meaningful text chunks from a log entry dictionary for RAG indexing.
    Each chunk should be a self-contained piece of information.
    """
    chunks = []
    entry_type = entry_data.get("entry_type", "unknown_entry")
    primary_emotion = entry_data.get("primary_emotion", "")

    # Common preface for context
    # preface = f"Log entry type {entry_type}. "
    # if primary_emotion:
    #     preface += f"Primary emotion was {primary_emotion}. "

    # Trigger/Situation
    trigger_event = entry_data.get("trigger_event", {})
    if trigger_event.get("summary"):
        chunks.append(f"Regarding a situation: {trigger_event['summary']}")
    elif trigger_event.get("topic"): # Fallback for other structures
         chunks.append(f"Regarding the topic: {trigger_event['topic']}")


    # Emotions
    if primary_emotion:
        emotions_text = f"Felt primarily {primary_emotion}."
        secondary_emotions = entry_data.get("secondary_emotions", [])
        if secondary_emotions:
            emotions_text += f" Also felt: {', '.join(secondary_emotions)}."
        chunks.append(emotions_text)

    # Thoughts
    my_thoughts = entry_data.get("my_thoughts_during", [])
    if my_thoughts:
        thoughts_str = ". ".join(my_thoughts)
        chunks.append(f"My thoughts at the time were: {thoughts_str}")

    # Behavioral Reactions / Actions Taken
    reactions = entry_data.get("my_behavioral_reactions", [])
    if reactions:
        reaction_texts = []
        for reaction in reactions:
            action_desc = reaction.get("action", "an action")
            effectiveness = reaction.get("effectiveness", "unknown effectiveness")
            reaction_texts.append(f"I reacted by '{action_desc}', which was of {effectiveness} effectiveness.")
        chunks.append("Regarding my reactions: " + " ".join(reaction_texts))
    elif entry_data.get("actions_taken"): # Fallback for simpler structures
        chunks.append(f"Actions taken: {', '.join(entry_data.get('actions_taken',[]))}")


    # Impact
    immediate_impact = entry_data.get("immediate_impact", {})
    if immediate_impact.get("on_self"):
        impact_str = ". ".join(immediate_impact["on_self"])
        chunks.append(f"The immediate impact on me was: {impact_str}")

    # Reflections/Learnings
    reflection_learnings = entry_data.get("reflection_learnings", {})
    if reflection_learnings.get("insights_gained"):
        insights_str = ". ".join(reflection_learnings["insights_gained"])
        chunks.append(f"Key insights I gained: {insights_str}")
    if reflection_learnings.get("potential_future_actions"):
        future_actions_str = ". ".join(reflection_learnings["potential_future_actions"])
        chunks.append(f"Potential future actions I considered: {future_actions_str}")

    # Filter out empty or very short chunks
    meaningful_chunks = [chunk for chunk in chunks if chunk and len(chunk.split()) > 3] # Min 4 words
    # print(f"DEBUG extract_chunks: For entry {entry_data.get('entry_id')}, extracted: {meaningful_chunks}")
    return meaningful_chunks


def _index_entry_for_rag(entry_data):
    """Helper function to index a single entry's chunks into the vector store."""
    if not RAG_ENABLED or not rag_components_initialized or not vector_collection_instance or not embedding_model_instance:
        # print("RAG: Indexing skipped - RAG not enabled or components not ready.")
        return

    chunks_to_embed = extract_text_chunks_for_embedding(entry_data)
    if not chunks_to_embed:
        # print(f"RAG: No meaningful chunks extracted for entry {entry_data.get('entry_id', 'N/A')}, skipping indexing.")
        return

    try:
        embeddings = embedding_model_instance.encode(chunks_to_embed).tolist()
        metadatas = [{
            "entry_id": str(entry_data.get("entry_id", "")), # Ensure entry_id is a string
            "timestamp_utc": str(entry_data.get("timestamp_utc", "")),
            "entry_type": str(entry_data.get("entry_type", "")),
            "source_document_text": chunk # Storing the original chunk text with metadata
        } for chunk in chunks_to_embed]
        # Generate unique IDs for each chunk to allow updates/deletions if needed later
        ids = [str(uuid.uuid4()) for _ in chunks_to_embed]

        vector_collection_instance.add(
            embeddings=embeddings,
            documents=chunks_to_embed, # Store the document text itself as well
            metadatas=metadatas,
            ids=ids
        )
        print(f"RAG: Successfully indexed {len(chunks_to_embed)} chunks for entry_id: {entry_data.get('entry_id', 'N/A')}")
    except Exception as e:
        print(f"RAG: Error during _index_entry_for_rag for entry_id {entry_data.get('entry_id', 'N/A')}: {e}")


# --- Core Data Management Functions ---

def load_data():
    """Loads all entries from the JSONL data file."""
    # Ensure RAG components are ready for potential subsequent operations if needed by caller
    # initialize_rag_if_needed() # Not strictly needed for just loading JSONL

    entries = []
    try:
        with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line_content = line.strip()
                if line_content:
                    try:
                        entries.append(json.loads(line_content))
                    except json.JSONDecodeError:
                        print(f"Warning: Skipping malformed JSON line in {DATA_FILE_PATH}: {line_content[:100]}...")
    except FileNotFoundError:
        print(f"Data file '{DATA_FILE_PATH}' not found. Starting with an empty dataset.")
    return entries


def add_entry(entry_type, data_dict):
    """
    Adds a new entry to the JSONL data file and indexes it for RAG.
    """
    initialize_rag_if_needed() # Ensure RAG components are ready for indexing

    timestamp = datetime.utcnow().isoformat() + "Z"
    # Use UUID for entry_id for better uniqueness than count-based
    entry_id = str(uuid.uuid4())

    new_entry_data = {
        "entry_id": entry_id,
        "timestamp_utc": timestamp,
        "entry_type": entry_type,
        **data_dict
    }

    try:
        with open(DATA_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_entry_data) + '\n')
        print(f"Entry of type '{entry_type}' (ID: {entry_id}) added successfully to JSONL.")

        # Index the new entry for RAG
        _index_entry_for_rag(new_entry_data)

        return new_entry_data
    except Exception as e:
        print(f"Error adding entry (JSONL or RAG indexing): {e}")
        return None


# --- Interactive Entry Functions (Examples from before, can be moved to app.py or a UI module) ---
def add_emotion_log_entry_interactive():
    """Collects data for an emotion log interactively from the user."""
    # ... (implementation as before, finally calls add_entry)
    print("\n--- Add New Emotion Log ---")
    primary_emotion = input("Primary emotion felt: ")
    # ... (rest of the input collection) ...
    # For brevity, assuming you have this part from previous versions
    # Finally:
    # data_to_log = { ... }
    # return add_entry("emotion_log", data_to_log)
    pass # Replace with full implementation

def add_problem_solving_entry_interactive():
    """Collects data for a problem-solving log interactively."""
    # ... (implementation as before, finally calls add_entry)
    pass # Replace with full implementation


# --- RAG Query Function ---
def query_relevant_log_chunks(query_text, n_results=5):
    """
    Queries the vector store for log chunks relevant to the query_text.
    Returns a list of document texts.
    """
    if not RAG_ENABLED or not initialize_rag_if_needed() or not vector_collection_instance or not embedding_model_instance:
        print("RAG: Querying skipped - RAG not enabled or components not ready.")
        return []

    try:
        query_embedding = embedding_model_instance.encode(query_text).tolist()
        results = vector_collection_instance.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            # include=['metadatas', 'documents', 'distances'] # if you need more than just documents
            include=['documents']
        )
        if results and results.get('documents') and results['documents'][0]:
            # print(f"RAG Query: Found {len(results['documents'][0])} relevant chunks for query '{query_text[:50]}...'")
            return results['documents'][0] # List of document texts
        else:
            # print(f"RAG Query: No relevant chunks found for query '{query_text[:50]}...'")
            return []
    except Exception as e:
        print(f"RAG: Error during query_relevant_log_chunks: {e}")
        return []


# --- Batch Indexing Function (call this separately, e.g., from a script) ---
def batch_index_all_logs():
    """
    Loads all entries from JSONL and indexes them into the vector store.
    Useful for initial setup or re-indexing.
    """
    if not RAG_ENABLED:
        print("Batch Indexing: RAG is disabled. Aborting.")
        return

    if not initialize_rag_if_needed():
        print("Batch Indexing: Failed to initialize RAG components. Aborting.")
        return

    # Optional: Clear existing collection before full re-index if desired
    # choice = input(f"WARNING: This will attempt to re-index all logs. \nDo you want to DELETE and re-create the collection '{COLLECTION_NAME}' first? (yes/no): ").lower()
    # if choice == 'yes':
    #     try:
    #         print(f"Batch Indexing: Deleting collection '{COLLECTION_NAME}'...")
    #         vector_store_client_instance.delete_collection(name=COLLECTION_NAME)
    #         print("Batch Indexing: Collection deleted.")
    #         # Force re-creation in the next call to get_or_create_collection
    #         global vector_collection_instance
    #         vector_collection_instance = None
    #         initialize_rag_if_needed() # Re-initialize to create the collection
    #     except Exception as e:
    #         print(f"Batch Indexing: Error deleting collection: {e}. Continuing without delete.")


    all_entries = load_data() # Load from JSONL
    print(f"Batch Indexing: Found {len(all_entries)} total entries in JSONL.")
    total_indexed_chunks = 0
    entries_processed_for_indexing = 0

    # To avoid re-indexing already processed entries in a naive way,
    # one could fetch all existing entry_ids from Chroma. This is more complex.
    # For now, this will re-process all entries from JSONL.
    # If IDs in Chroma are stable and refer to chunks, clearing is better.

    if vector_collection_instance:
        print(f"Batch Indexing: Current items in Chroma collection '{COLLECTION_NAME}': {vector_collection_instance.count()}")


    for i, entry in enumerate(all_entries):
        print(f"Batch Indexing: Processing entry {i+1}/{len(all_entries)}, ID: {entry.get('entry_id', 'N/A')}")
        # _index_entry_for_rag will handle chunk extraction and adding to Chroma
        _index_entry_for_rag(entry) # This function now prints its own success/failure
        entries_processed_for_indexing +=1


    print("--- Batch Indexing Summary ---")
    print(f"Entries processed from JSONL for indexing: {entries_processed_for_indexing}")
    if vector_collection_instance:
         final_count = vector_collection_instance.count()
         print(f"Total items (chunks) in Chroma collection '{COLLECTION_NAME}' after batch indexing: {final_count}")
    else:
        print("Batch Indexing: Vector collection instance not available to get final count.")


if __name__ == '__main__':
    # This section is for testing data_manager.py directly
    print("Running data_manager.py directly for testing...")

    # Initialize RAG (important for batch indexing)
    if not initialize_rag_if_needed():
        print("Could not initialize RAG components for testing. Some tests might fail or be skipped.")

    # Test batch indexing
    print("\n--- Testing Batch Indexing ---")
    # batch_index_all_logs() # Uncomment to run batch indexing

    # Test adding a new entry
    print("\n--- Testing Add Entry ---")
    # test_entry_data = {
    #     "primary_emotion": "curious",
    #     "secondary_emotions": ["hopeful"],
    #     "trigger_event": {"summary": "Testing the new data manager with RAG.", "type": "test"},
    #     "my_thoughts_during": ["Will this RAG indexing work smoothly?", "I hope the chunks are good."],
    #     "reflection_learnings": {"insights_gained": ["Modular code is good.", "Testing is important."]}
    # }
    # added = add_entry("test_log", test_entry_data)
    # if added:
    #     print(f"Test entry added. ID: {added.get('entry_id')}")

    # Test querying
    print("\n--- Testing RAG Query ---")
    # if RAG_ENABLED and rag_components_initialized and vector_collection_instance:
    #     test_query = "how to handle test situations"
    #     print(f"Querying for: '{test_query}'")
    #     relevant_docs = query_relevant_log_chunks(test_query, n_results=3)
    #     if relevant_docs:
    #         print(f"Found {len(relevant_docs)} relevant documents:")
    #         for idx, doc_text in enumerate(relevant_docs):
    #             print(f"Doc {idx+1}: {doc_text[:150]}...")
    #     else:
    #         print("No relevant documents found for test query.")
    # else:
    #     print("RAG query test skipped as RAG is not fully ready.")

    print("\nData manager test run finished.")