# app.py
import streamlit as st
from src import data_manager, llm_interaction, config # Your existing modules
import json
# from datetime import datetime # Not directly used in this version's forms

# --- Page Configuration ---
st.set_page_config(
    page_title="MyMind AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---
def format_entry_for_display(entry):
    display_parts = [
        f"**ID:** `{entry.get('entry_id', 'N/A')}`",
        f"**Timestamp:** {entry.get('timestamp_utc', 'N/A')}",
        f"**Type:** {entry.get('entry_type', 'N/A')}",
        f"**Primary Emotion:** {entry.get('primary_emotion', 'N/A')}"
    ]
    # Add more fields as needed for a quick summary
    summary = entry.get("trigger_event", {}).get("summary", "No summary.")
    display_parts.append(f"**Summary:** {summary[:100]}{'...' if len(summary) > 100 else ''}")
    return "\n\n".join(display_parts)


# --- Initialize Session State ---
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'all_entries' not in st.session_state:
    st.session_state.all_entries = data_manager.load_data()
    st.toast(f"Loaded {len(st.session_state.all_entries)} entries from JSONL.")

if 'rag_initialized_dm' not in st.session_state:
    with st.spinner("Initializing AI Core and RAG components..."):
        st.session_state.rag_initialized_dm = data_manager.initialize_rag_if_needed()
    if st.session_state.rag_initialized_dm:
        st.toast("RAG components initialized successfully!", icon="✅")
    else:
        st.error("Failed to initialize RAG components. RAG features may be limited or disabled.")


# --- Sidebar ---
st.sidebar.title("🧠 MyMind AI")
st.sidebar.markdown("Your personal AI assistant.")

app_mode = st.sidebar.radio( # Using radio for a more compact look
    "Choose Action",
    ["Chat with AI", "Add New Log Entry", "View Log Entries"],
    key="app_mode_selector"
)

st.sidebar.markdown("---")
st.sidebar.info(f"Total Log Entries: {len(st.session_state.all_entries)}")
if data_manager.RAG_ENABLED and st.session_state.get('rag_initialized_dm'):
    try:
        if data_manager.vector_collection_instance: # Check if collection is initialized
            st.sidebar.info(f"RAG Index Size: {data_manager.vector_collection_instance.count()} chunks")
        else:
            st.sidebar.warning("RAG collection not ready.")
    except Exception as e:
        st.sidebar.error(f"Error getting RAG count: {e}") # Catch potential errors
else:
    st.sidebar.warning("RAG is disabled or not initialized.")


# --- Main App Logic ---

if app_mode == "Chat with AI":
    st.header("💬 Chat with Your Personal AI")
    st.markdown("Ask for advice, reflections, or guidance based on your logs.")

    # Display chat history
    for user_msg, ai_msg in st.session_state.chat_history:
        with st.chat_message("user", avatar="🧑‍💻"):
            st.write(user_msg)
        with st.chat_message("assistant", avatar="🤖"):
            st.write(ai_msg)

    # User input
    user_query = st.chat_input("What's on your mind, or what can I help you reflect on?")

    if user_query:
        st.session_state.chat_history.append((user_query, None)) # Add user message immediately
        st.rerun() # Rerun to display user message, then process AI response

    # Process the latest user query if AI response is None
    if st.session_state.chat_history and st.session_state.chat_history[-1][1] is None:
        last_user_query = st.session_state.chat_history[-1][0]
        with st.chat_message("assistant", avatar="🤖"): # Show AI thinking within its message block
            with st.spinner("Thinking and searching logs..."):
                context_string = ""
                retrieved_chunks_for_display = []

                if data_manager.RAG_ENABLED and st.session_state.get('rag_initialized_dm'):
                    retrieved_chunks = data_manager.query_relevant_log_chunks(last_user_query, n_results=config.MAX_CONTEXT_ENTRIES_FOR_LLM) # Use config for n_results
                    if retrieved_chunks:
                        context_string = "\n\n---\n\n".join(retrieved_chunks)
                        retrieved_chunks_for_display = retrieved_chunks
                    else:
                        st.sidebar.caption("RAG: No specific chunks found for this query.")
                else: # Fallback if RAG is disabled or failed
                    st.sidebar.warning("RAG disabled/failed. Using recent entries as fallback context.")

                if not context_string: # If RAG found nothing or is disabled, use fallback
                    st.sidebar.caption("Using recent entries as general context.")
                    sorted_entries = sorted(st.session_state.all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
                    context_entries_for_prompt = sorted_entries[:config.MAX_CONTEXT_ENTRIES_FOR_LLM]
                    # For fallback, sending full entries might be too much; consider summarizing or extracting key parts
                    context_string = "\n\n---\n\n".join([
                        f"Entry ID: {e.get('entry_id')}\nType: {e.get('entry_type')}\nSummary: {e.get('trigger_event',{}).get('summary','N/A')}\nThoughts: {'. '.join(e.get('my_thoughts_during',[]))}\nLearnings: {'. '.join(e.get('reflection_learnings',{}).get('insights_gained',[]))}"
                        for e in context_entries_for_prompt
                    ])


                if retrieved_chunks_for_display: # Display RAG context if found
                    with st.expander("ℹ️ View Retrieved Context (from RAG)", expanded=False):
                        for i, chunk in enumerate(retrieved_chunks_for_display):
                            st.caption(f"Chunk {i+1}:")
                            st.markdown(f"> {chunk}")


                ai_response = llm_interaction.get_ai_response(last_user_query, context_string)
                st.write(ai_response)
                st.session_state.chat_history[-1] = (last_user_query, ai_response) # Update with AI response

elif app_mode == "Add New Log Entry":
    st.header("📝 Add New Log Entry")
    st.markdown("Record your thoughts, emotions, or problems to build your personal knowledge base.")

    entry_type_options = ["emotion_log", "problem_solving", "work_task_reflection", "learning_note", "general_note"]
    entry_type = st.selectbox("Type of Entry", entry_type_options, index=0)

    with st.form(f"{entry_type}_form", clear_on_submit=True):
        st.subheader(f"Details for: {entry_type.replace('_', ' ').title()}")

        # Common fields
        situation_summary = st.text_area("Situation / Topic / Summary:", height=100, help="Briefly describe what happened or what this note is about.")
        primary_emotion = st.text_input("Primary Emotion Felt (if applicable):")
        tags_str = st.text_input("Tags (comma-separated, e.g., work, project_alpha, urgent):")

        # Type-specific fields (simplified for this example)
        if entry_type in ["emotion_log", "problem_solving"]:
            thoughts = st.text_area("Your Detailed Thoughts / Analysis:", height=150)
            learnings = st.text_area("Insights, Learnings, or Potential Future Actions:", height=150)
            intensity = st.slider("Intensity / Importance (1-10)", 1, 10, 5) if entry_type == "emotion_log" else None
        else: # For notes, reflections
            notes_details = st.text_area("Detailed Notes / Reflection:", height=200)

        submitted = st.form_submit_button("Save Log Entry")

        if submitted:
            if not situation_summary:
                st.error("The 'Situation / Topic / Summary' field is required.")
            else:
                tags = [t.strip() for t in tags_str.split(',') if t.strip()]
                data_to_log = {
                    "primary_emotion": primary_emotion,
                    "tags": tags,
                    "trigger_event": {"summary": situation_summary, "type": entry_type}, # Simplified trigger
                }
                if entry_type in ["emotion_log", "problem_solving"]:
                    data_to_log["my_thoughts_during"] = [thoughts] if thoughts else []
                    data_to_log["reflection_learnings"] = {"insights_gained": [learnings]} if learnings else {}
                    if intensity: data_to_log["intensity_level"] = intensity
                else:
                    data_to_log["notes_details"] = notes_details # Example field for other types

                new_entry = data_manager.add_entry(entry_type, data_to_log)
                if new_entry:
                    st.session_state.all_entries.append(new_entry)
                    st.success(f"{entry_type.replace('_', ' ').title()} added successfully!")
                    st.balloons()
                    # No need to call st.rerun() explicitly, form submission handles it.
                else:
                    st.error(f"Failed to add {entry_type.replace('_', ' ').title()}.")


elif app_mode == "View Log Entries":
    st.header("📖 View Your Log Entries")

    if not st.session_state.all_entries:
        st.warning("No entries yet. Add some first from the 'Add New Log Entry' section!")
    else:
        col1, col2 = st.columns([3,1])
        with col1:
            search_term = st.text_input("Search entries (searches summaries, thoughts, learnings):", placeholder="e.g., anxious, project deadline, girlfriend")
        with col2:
            num_entries_to_show = st.number_input("Max entries to display:", min_value=1, max_value=len(st.session_state.all_entries), value=min(10, len(st.session_state.all_entries)))

        sorted_entries = sorted(st.session_state.all_entries, key=lambda x: x.get("timestamp_utc", ""), reverse=True)
        
        filtered_entries = sorted_entries
        if search_term:
            search_term_lower = search_term.lower()
            filtered_entries = [
                entry for entry in sorted_entries if
                search_term_lower in entry.get("trigger_event", {}).get("summary", "").lower() or
                any(search_term_lower in thought.lower() for thought in entry.get("my_thoughts_during", [])) or
                any(search_term_lower in insight.lower() for insight in entry.get("reflection_learnings", {}).get("insights_gained", [])) or
                any(search_term_lower in tag.lower() for tag in entry.get("tags", []))
            ]
            st.caption(f"Found {len(filtered_entries)} entries matching '{search_term}'.")


        if not filtered_entries:
            st.info("No entries match your current search criteria or no entries exist.")
        else:
            for entry in filtered_entries[:num_entries_to_show]:
                with st.expander(f"{entry.get('entry_type', 'Entry').replace('_',' ').title()}: {entry.get('trigger_event',{}).get('summary', 'No Summary')[:60]}... ({entry.get('timestamp_utc', 'N/A')[:10]})"):
                    st.markdown(f"**ID:** `{entry.get('entry_id', 'N/A')}`")
                    st.markdown(f"**Timestamp:** {entry.get('timestamp_utc', 'N/A')}")
                    st.markdown(f"**Type:** {entry.get('entry_type', 'N/A')}")
                    st.markdown(f"**Primary Emotion:** {entry.get('primary_emotion', 'N/A')}")
                    st.markdown(f"**Tags:** {', '.join(entry.get('tags', ['N/A']))}")
                    
                    st.markdown("---")
                    st.markdown(f"**Situation / Summary:**\n{entry.get('trigger_event', {}).get('summary', 'N/A')}")
                    
                    if entry.get("my_thoughts_during"):
                        st.markdown(f"**My Thoughts:**")
                        for thought in entry.get("my_thoughts_during"):
                            st.markdown(f"- {thought}")
                    
                    if entry.get("reflection_learnings", {}).get("insights_gained"):
                        st.markdown(f"**Learnings / Insights:**")
                        for insight in entry.get("reflection_learnings").get("insights_gained"):
                            st.markdown(f"- {insight}")
                    
                    if entry.get("notes_details"):
                         st.markdown(f"**Detailed Notes:**\n{entry.get('notes_details')}")

                    # Add more detailed fields as needed
                    # st.json(entry) # For raw JSON view

# --- Optional: Footer ---
st.markdown("---")
st.caption("MyMind AI - Personal Assistant Prototype | B.Tech Major Project")