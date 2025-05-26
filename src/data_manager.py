# src/data_manager.py
import json
from datetime import datetime
import uuid 

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

DATA_FILE_PATH = "my_personal_data.jsonl" 
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2' 
CHROMA_DB_PATH = "./chroma_db_store" 
COLLECTION_NAME = "personal_log_embeddings"
RAG_ENABLED = SENTENCE_TRANSFORMER_AVAILABLE and CHROMADB_AVAILABLE

embedding_model_instance = None
vector_store_client_instance = None
vector_collection_instance = None
rag_components_initialized = False


def initialize_rag_if_needed():
    global embedding_model_instance, vector_store_client_instance, vector_collection_instance, rag_components_initialized
    if not RAG_ENABLED:
        rag_components_initialized = True 
        return False
    if rag_components_initialized and vector_collection_instance is not None: # Check if fully initialized
        return True

    print("RAG: Attempting to initialize RAG components...")
    try:
        if embedding_model_instance is None:
            embedding_model_instance = SentenceTransformer(EMBEDDING_MODEL_NAME)
            print("RAG: SentenceTransformer model initialized.")
        if vector_store_client_instance is None:
            vector_store_client_instance = chromadb.PersistentClient(path=CHROMA_DB_PATH)
            print("RAG: ChromaDB client initialized.")
        if vector_collection_instance is None:
            vector_collection_instance = vector_store_client_instance.get_or_create_collection(
                name=COLLECTION_NAME,
            )
            print(f"RAG: Chroma collection '{COLLECTION_NAME}' ready. Count: {vector_collection_instance.count()}")
        rag_components_initialized = True
        print("RAG: All RAG components initialized successfully.")
        return True
    except Exception as e:
        print(f"RAG: Critical error initializing RAG components: {e}")
        embedding_model_instance = None
        vector_store_client_instance = None
        vector_collection_instance = None
        rag_components_initialized = True 
        return False

def extract_text_chunks_for_embedding(entry_data):
    """
    Extracts meaningful text chunks from a log entry dictionary for RAG indexing.
    (This version is simplified based on your data structure; you can make it more granular)
    """
    chunks = []
    entry_type = entry_data.get("entry_type", "unknown_entry")
    primary_emotion = entry_data.get("primary_emotion", "")
    summary = entry_data.get("trigger_event", {}).get("summary", "")

    if summary:
        chunks.append(f"Log about '{summary}' (Type: {entry_type}).")

    if primary_emotion:
        chunks.append(f"Felt primarily {primary_emotion} regarding '{summary if summary else 'this event'}'.")
    
    thoughts_list = entry_data.get("my_thoughts_during", [])
    if thoughts_list:
        thoughts_str = ". ".join(thoughts_list)
        chunks.append(f"My thoughts were: {thoughts_str}")

    learnings_list = entry_data.get("reflection_learnings", {}).get("insights_gained", [])
    if learnings_list:
        learnings_str = ". ".join(learnings_list)
        chunks.append(f"Key learnings included: {learnings_str}")
        
    # Add more specific chunking based on other fields if desired

    return [chunk for chunk in chunks if chunk and len(chunk.split()) > 3]


def _index_entry_for_rag(entry_data):
    if not RAG_ENABLED or not rag_components_initialized or not vector_collection_instance or not embedding_model_instance:
        return

    chunks_to_embed = extract_text_chunks_for_embedding(entry_data)
    if not chunks_to_embed:
        return

    try:
        embeddings = embedding_model_instance.encode(chunks_to_embed).tolist()
        
        entry_id_str = str(entry_data.get("entry_id", ""))
        # --- ENSURE THESE METADATA FIELDS MATCH WHAT app.py TRIES TO FILTER ON ---
        entry_type_str = str(entry_data.get("entry_type", "unknown")).lower() # Use consistent casing for filtering
        primary_emotion_str = str(entry_data.get("primary_emotion", "")).lower() 
        tags_list = [str(tag).lower() for tag in entry_data.get("tags", [])]

        metadatas = [{
            "entry_id": entry_id_str,
            "timestamp_utc": str(entry_data.get("timestamp_utc", "")),
            "entry_type": entry_type_str, # THIS IS CRUCIAL FOR FILTERING
            "primary_emotion": primary_emotion_str, # CRUCIAL FOR FILTERING
            "tags_str": ",".join(tags_list), # For potential text search within tags or simple tag filtering
            "source_document_text": chunk 
        } for chunk in chunks_to_embed]
        
        ids = [str(uuid.uuid4()) for _ in chunks_to_embed]

        vector_collection_instance.add(embeddings=embeddings, documents=chunks_to_embed, metadatas=metadatas, ids=ids)
        print(f"RAG: Indexed {len(chunks_to_embed)} chunks for entry_id: {entry_id_str} (Type: {entry_type_str})")
    except Exception as e:
        print(f"RAG: Error during _index_entry_for_rag for entry_id {entry_data.get('entry_id', 'N/A')}: {e}")


def load_data():
    entries = []
    try:
        with open(DATA_FILE_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                line_content = line.strip()
                if line_content:
                    try:
                        entries.append(json.loads(line_content))
                    except json.JSONDecodeError:
                        print(f"Warning: Skipping malformed JSON line: {line_content[:100]}...")
    except FileNotFoundError:
        print(f"Data file '{DATA_FILE_PATH}' not found. Starting with an empty dataset.")
    return entries


def add_entry(entry_type_from_form, data_dict): # Renamed first arg for clarity
    initialize_rag_if_needed()
    timestamp = datetime.utcnow().isoformat() + "Z"
    entry_id = str(uuid.uuid4())

    # The entry_type_from_form IS the main entry_type for RAG filtering
    new_entry_data = {
        "entry_id": entry_id,
        "timestamp_utc": timestamp,
        "entry_type": entry_type_from_form.lower(), # Standardize to lowercase
        **data_dict 
    }
    # Ensure primary_emotion and tags in data_dict are also consistently cased if not already
    if "primary_emotion" in new_entry_data:
        new_entry_data["primary_emotion"] = str(new_entry_data["primary_emotion"]).lower()
    if "tags" in new_entry_data and isinstance(new_entry_data["tags"], list):
        new_entry_data["tags"] = [str(tag).lower() for tag in new_entry_data["tags"]]


    try:
        with open(DATA_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(new_entry_data) + '\n')
        print(f"Entry of type '{new_entry_data['entry_type']}' (ID: {entry_id}) added successfully to JSONL.")
        _index_entry_for_rag(new_entry_data) # Will use the new_entry_data['entry_type'] for metadata
        return new_entry_data
    except Exception as e:
        print(f"Error adding entry (JSONL or RAG indexing): {e}")
        return None

def query_relevant_log_chunks(query_text, n_results=5, filter_metadata=None):
    if not RAG_ENABLED or not initialize_rag_if_needed() or not vector_collection_instance or not embedding_model_instance:
        print("RAG: Querying skipped - RAG not enabled or components not ready.")
        return []
    try:
        query_embedding = embedding_model_instance.encode(query_text).tolist()
        
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ['documents', 'metadatas'] # Include metadatas for debugging/verification
        }

        # Handle simple equality filters. For complex filters like $or, $in, this would need enhancement.
        if filter_metadata and isinstance(filter_metadata, dict):
            # Basic check for $or - if found, this basic filter won't work as ChromaDB expects specific structure.
            if "$or" in filter_metadata or "$and" in filter_metadata:
                print(f"RAG WARNING: Complex filter operators like $or, $and received ({filter_metadata}), "
                      "but current query_relevant_log_chunks handles simple equality filters. "
                      "This filter might not work as expected. Consider enhancing for ChromaDB operators "
                      "or simplifying the filter in the calling code (e.g., app.py).")
                # For now, we will pass it as is, but ChromaDB might error or ignore it if not structured correctly.
                # A robust solution would parse filter_metadata and build the correct ChromaDB 'where' clause.
                # If app.py sends a simple filter like {"entry_type": "emotion_log"}, it will work.
                query_params["where"] = filter_metadata
            else: # Simple key-value filter
                 query_params["where"] = filter_metadata
            print(f"RAG Query: Using metadata filter: {query_params['where']}")
        
        results = vector_collection_instance.query(**query_params)

        if results and results.get('documents') and results['documents'][0]:
            print(f"RAG Query: Found {len(results['documents'][0])} relevant chunks for query '{query_text[:50]}...'")
            # print(f"DEBUG RAG: Metadatas of retrieved chunks: {results.get('metadatas',[[]])[0]}") # For debugging
            return results['documents'][0] 
        else:
            print(f"RAG Query: No relevant chunks found for query '{query_text[:50]}...' (with current filters).")
            return []
    except Exception as e:
        print(f"RAG: Error during query_relevant_log_chunks: {e}")
        return []

def batch_index_all_logs():
    if not RAG_ENABLED or not initialize_rag_if_needed():
        print("Batch Indexing: RAG not enabled or components not ready. Aborting.")
        return

    all_entries = load_data() 
    print(f"Batch Indexing: Found {len(all_entries)} total entries in JSONL.")
    if not all_entries: return

    # Optional: Clear existing collection for a full fresh re-index
    # choice = input(f"Clear collection '{COLLECTION_NAME}' before re-indexing? (yes/no): ").lower()
    # if choice == 'yes':
    #     try:
    #         print(f"Batch Indexing: Deleting collection '{COLLECTION_NAME}'...")
    #         vector_store_client_instance.delete_collection(name=COLLECTION_NAME)
    #         global vector_collection_instance
    #         vector_collection_instance = vector_store_client_instance.get_or_create_collection(name=COLLECTION_NAME) # Recreate
    #         print("Batch Indexing: Collection deleted and re-created.")
    #     except Exception as e:
    #         print(f"Batch Indexing: Error managing collection: {e}. Continuing...")

    for i, entry in enumerate(all_entries):
        print(f"Batch Indexing: Processing entry {i+1}/{len(all_entries)}, ID: {entry.get('entry_id', 'N/A')}")
        _index_entry_for_rag(entry)
    
    print("--- Batch Indexing Summary ---")
    if vector_collection_instance:
         print(f"Total items (chunks) in Chroma collection '{COLLECTION_NAME}' after: {vector_collection_instance.count()}")

# (Main test block can be kept or updated for more specific filter tests)