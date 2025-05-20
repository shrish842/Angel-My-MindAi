import google.generativeai as genai
from .config import GEMINI_API_KEY # Import your API key from config.py

# Configure the generative AI SDK with your API key
if not GEMINI_API_KEY:
    print("DEBUG llm_interaction: CRITICAL - GEMINI_API_KEY is not loaded from config!")
    raise ValueError("GEMINI_API_KEY is missing. Cannot configure Gemini.")
else:
    print("DEBUG llm_interaction: GEMINI_API_KEY loaded successfully.")
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize the GenerativeModel.
MODEL_NAME_PRIMARY = 'gemini-1.5-flash-latest'
MODEL_NAME_FALLBACK = 'gemini-pro'
model = None

try:
    print(f"DEBUG llm_interaction: Attempting to initialize model: {MODEL_NAME_PRIMARY}")
    model = genai.GenerativeModel(MODEL_NAME_PRIMARY)
    print(f"DEBUG llm_interaction: Successfully initialized model: {MODEL_NAME_PRIMARY}")
except Exception as e:
    print(f"DEBUG llm_interaction: Warning - Could not initialize '{MODEL_NAME_PRIMARY}'. Error: {e}")
    print(f"DEBUG llm_interaction: Attempting to initialize fallback model: {MODEL_NAME_FALLBACK}")
    try:
        model = genai.GenerativeModel(MODEL_NAME_FALLBACK)
        print(f"DEBUG llm_interaction: Successfully initialized fallback model: {MODEL_NAME_FALLBACK}")
    except Exception as e_pro:
        print(f"DEBUG llm_interaction: CRITICAL - Failed to initialize any Gemini model. Primary Error: {e}, Fallback Error: {e_pro}")
        # Model remains None, get_ai_response will handle this.

def get_ai_response(user_query, personal_context_string):
    """
    Sends a prompt (user query + personal context) to the Gemini API and returns its response.
    """
    if model is None:
        print("DEBUG llm_interaction: CRITICAL - Gemini model was not initialized. Cannot get AI response.")
        return "My AI core (Gemini model) could not be initialized. Please check the startup logs for errors related to the API key or model availability."

    prompt = f"""
You are 'MyMind AI', a highly personalized AI assistant. Your primary goal is to help the user
understand their emotions, make better decisions, and get advice based on THEIR OWN
past experiences, thoughts, and reflections provided in the 'PERSONAL CONTEXT' section.

--- PERSONAL CONTEXT START ---
{personal_context_string}
--- PERSONAL CONTEXT END ---

User's current query or situation: "{user_query}"

Based EXCLUSIVELY on the provided 'PERSONAL CONTEXT' and the user's current query:
1.  Acknowledge the user's current query/feeling.
2.  If relevant entries exist in the PERSONAL CONTEXT that mirror the current situation or emotion,
    gently remind the user of those past experiences and specifically what they learned or
    what actions they found helpful or unhelpful (as documented by them).
3.  If the user is asking for advice, try to synthesize advice from their own past successful strategies
    or learnings from the PERSONAL CONTEXT.
4.  If the context is insufficient, state that you don't have enough past information from their logs
    to provide a deep insight for this specific query and perhaps suggest what they could log in the future.
5.  Maintain a supportive, empathetic, and reflective tone. Sound like a wise extension of the user's own mind.
6.  Do NOT provide generic advice or information from outside the PERSONAL CONTEXT. Your knowledge is limited to what the user has shared with you in their logs. If the context does not contain relevant information, state that clearly.

Your thoughtful response:
"""

    print("\nDEBUG llm_interaction: --- PROMPT BEING SENT TO GEMINI (first 1000 chars) ---")
    print(prompt[:1000] + ("..." if len(prompt) > 1000 else ""))
    print("DEBUG llm_interaction: --- END OF PROMPT SNIPPET ---\n")

    response_text = None # Initialize response_text

    try:
        response = model.generate_content(prompt)

        print(f"DEBUG llm_interaction: Full API Response object received: {type(response)}")
        if hasattr(response, 'text'):
             print(f"DEBUG llm_interaction: response.text (raw direct attribute): '{response.text}'")
        if hasattr(response, 'parts'):
             print(f"DEBUG llm_interaction: response.parts (raw direct attribute): {response.parts}")
        if hasattr(response, 'prompt_feedback'):
             print(f"DEBUG llm_interaction: response.prompt_feedback: {response.prompt_feedback}")

        if hasattr(response, 'candidates') and response.candidates:
            print(f"DEBUG llm_interaction: Number of candidates: {len(response.candidates)}")
            first_candidate = response.candidates[0]

            # Get the integer value of the finish_reason
            current_finish_reason_value = 0 # Default to UNSPECIFIED
            if hasattr(first_candidate, 'finish_reason'):
                current_finish_reason_value = int(first_candidate.finish_reason)
                print(f"DEBUG llm_interaction: Candidate 0 - finish_reason (int value): {current_finish_reason_value}")
            else:
                print("DEBUG llm_interaction: Candidate 0 - finish_reason attribute MISSING.")


            if hasattr(first_candidate, 'safety_ratings'):
                print(f"DEBUG llm_interaction: Candidate 0 - safety_ratings: {first_candidate.safety_ratings}")

            # Common integer values for FinishReason:
            # STOP = 1, MAX_TOKENS = 2, SAFETY = 3, RECITATION = 4, OTHER = 5
            if current_finish_reason_value == 1 or \
               current_finish_reason_value == 2:  # STOP or MAX_TOKENS
                if hasattr(first_candidate.content, 'parts') and first_candidate.content.parts:
                    response_text = "".join(part.text for part in first_candidate.content.parts if hasattr(part, 'text'))
                    print(f"DEBUG llm_interaction: Candidate 0 - extracted text: '{response_text}'")
                else:
                    print(f"DEBUG llm_interaction: Candidate 0 - Finish reason OK, but no parts found in content.")
            elif current_finish_reason_value == 3:  # SAFETY
                print("DEBUG llm_interaction: Response blocked due to SAFETY reasons.")
                block_details = "Response blocked by safety filters. "
                if hasattr(first_candidate, 'safety_ratings'):
                    for rating in first_candidate.safety_ratings:
                        # HarmProbability typically has integer values:
                        # UNKNOWN=0, NEGLIGIBLE=1, LOW=2, MEDIUM=3, HIGH=4
                        # We are concerned if it's MEDIUM or HIGH (values 3 or 4)
                        rating_category_name = "UNKNOWN_CATEGORY"
                        rating_probability_name = "UNKNOWN_PROBABILITY"
                        rating_probability_value = 0 # Default to UNKNOWN

                        if hasattr(rating, 'category') and hasattr(rating.category, 'name'):
                            rating_category_name = rating.category.name
                        if hasattr(rating, 'probability'):
                            rating_probability_value = int(rating.probability)
                            if hasattr(rating.probability, 'name'):
                                rating_probability_name = rating.probability.name
                            else:
                                rating_probability_name = f"VALUE_{rating_probability_value}"


                        if rating_probability_value >= 3: # If Medium or High (or potentially other non-negligible/low values)
                             block_details += f"Category: {rating_category_name}, Probability: {rating_probability_name}. "
                response_text = f"I'm unable to provide a response for that query due to content safety guidelines. {block_details.strip()}"
            else: # Other finish reasons (RECITATION, OTHER, UNSPECIFIED, UNKNOWN)
                finish_reason_name = f"UNKNOWN_REASON_VALUE_{current_finish_reason_value}"
                if hasattr(first_candidate, 'finish_reason') and hasattr(first_candidate.finish_reason, 'name'):
                    try:
                        finish_reason_name = first_candidate.finish_reason.name
                    except AttributeError: # Should not happen if .name exists
                        pass
                print(f"DEBUG llm_interaction: Candidate finished with reason: {finish_reason_name} (value: {current_finish_reason_value}). No text will be extracted.")
                response_text = f"My AI core processed the request but stopped for the following reason: {finish_reason_name}. I cannot provide a typical response."
        else:
             print("DEBUG llm_interaction: No candidates found in the API response.")
             if hasattr(response, 'text') and response.text:
                 response_text = response.text
                 print(f"DEBUG llm_interaction: Using top-level response.text as fallback: '{response_text}'")


        # Final check and return of response_text
        if response_text is not None and response_text.strip():
            print(f"DEBUG llm_interaction: Final response text to be returned: '{response_text}'")
            return response_text
        else:
            print("DEBUG llm_interaction: No usable text extracted from candidates or response_text is empty/None.")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                block_reason_msg_detail = "Unknown reason"
                if hasattr(response.prompt_feedback, 'block_reason_message') and response.prompt_feedback.block_reason_message:
                    block_reason_msg_detail = response.prompt_feedback.block_reason_message
                elif hasattr(response.prompt_feedback.block_reason, 'name'):
                    block_reason_msg_detail = response.prompt_feedback.block_reason.name

                print(f"DEBUG llm_interaction: Prompt itself was blocked. Reason: {block_reason_msg_detail}")
                return f"My AI core could not process your request because the input was blocked. Reason: {block_reason_msg_detail}."
            else:
                if hasattr(response, 'text') and response.text and response.text.strip():
                    print(f"DEBUG llm_interaction: Last resort fallback to response.text: '{response.text}'")
                    return response.text
                print("DEBUG llm_interaction: AI core responded, but no usable text was found even after fallbacks.")
                return "AI core responded, but no usable text was found. Please check the debug logs for more details (e.g., safety filters or other issues)."

    except Exception as e:
        print(f"DEBUG llm_interaction: Exception during API call or response processing: {e}")
        print(f"DEBUG llm_interaction: Type of exception: {type(e)}")
        if hasattr(e, 'args') and e.args:
            for arg_idx, arg_val in enumerate(e.args):
                print(f"DEBUG llm_interaction: Exception arg [{arg_idx}]: {arg_val}")
                if isinstance(arg_val, str) and "Deadline Exceeded" in arg_val:
                     print("DEBUG llm_interaction: Possible timeout error.")
                if hasattr(arg_val, 'message'):
                     print(f"DEBUG llm_interaction: Detailed API Error Message: {arg_val.message}")
                if hasattr(arg_val, 'code'):
                     print(f"DEBUG llm_interaction: Detailed API Error Code: {arg_val.code}")
        return "I'm sorry, I encountered an unexpected issue while trying to process your request with my AI core. Please check the console for detailed error logs."