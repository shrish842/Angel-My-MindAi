# run_batch_indexer.py
from src.data_manager import batch_index_all_logs, initialize_rag_if_needed

if __name__ == "__main__":
    print("Starting batch indexing process...")
    if initialize_rag_if_needed(): # Ensure components are ready
         batch_index_all_logs()
    else:
        print("Could not initialize RAG components. Batch indexing aborted.")
    print("Batch indexing process finished.")