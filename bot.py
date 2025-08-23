import os
import logging
from dotenv import load_dotenv
import json
import re

# --- Imports ---
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from mistralai.client import MistralClient
from serpapi import GoogleSearch # New import for web search
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# --- Basic Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
load_dotenv()

# --- Load API Keys ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY") # New key for search

# --- Initialize Clients ---
mistral_client = MistralClient(api_key=MISTRAL_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Embedding model loaded successfully.")

# --- Helper Functions ---

def extract_name_from_message(message):
    """Extract name if user introduces themselves"""
    name_patterns = [
        r"my name is (\w+)",
        r"i'm (\w+)",
        r"i am (\w+)",
        r"call me (\w+)"
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, message.lower())
        if match:
            return match.group(1).title()
    return None

def perform_web_search(query: str) -> str:
    """Performs a web search using SerpApi and returns a summary of results."""
    try:
        params = {
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "engine": "google",
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Extract snippets from organic results for context
        snippets = []
        if "organic_results" in results:
            for result in results["organic_results"][:4]: # Get top 4 results
                if "snippet" in result:
                    snippets.append(result["snippet"])
        
        if "answer_box" in results and "snippet" in results["answer_box"]:
             return results["answer_box"]["snippet"]

        print(f"Found {len(snippets)} snippets from web search.")
        return " ".join(snippets) if snippets else "No results found."
    except Exception as e:
        print(f"Error in web search: {e}")
        return "Sorry, I couldn't perform a web search at this time."

# --- Telegram Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    await update.message.reply_html(
        f"Hi {user_name}! I can now search the web and remember our conversations. Ask me anything!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_id = update.effective_user.id
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        # 1. **ALWAYS SEARCH MEMORY FIRST** - This was the key missing piece!
        message_embedding = embedding_model.encode(user_message).tolist()
        params = {
            'query_embedding': message_embedding,
            'match_threshold': 0.3,  # Keep the lower threshold for better recall
            'match_count': 8,        # Keep higher count
            'p_user_id': int(user_id)
        }
        memories = supabase.rpc('match_memories', params).execute()
        
        memory_context = ""
        if memories.data:
            print(f"Found {len(memories.data)} relevant memories.")
            memory_context += "MEMORY from past conversations:\n"
            for memory in memories.data:
                memory_context += f"- {memory['content']}\n"

        # 2. **PLANNING STEP**: Decide if a web search is needed.
        planning_prompt = (
            f"You are a smart router. Based on the user's message, decide if you need to search the web. "
            f"If the question is about current events, news, recent information, specific facts about companies/people, "
            f"weather, or requires up-to-date information, you should search. "
            f"If the user is asking about themselves, chatting casually, or the question can be answered from memory, you don't need to search. "
            f"Respond with a JSON object: {{\"tool\": \"web_search\", \"query\": \"search query\"}} or {{\"tool\": \"none\"}}.\n\n"
            f"User message: '{user_message}'"
        )
        
        planning_response = mistral_client.chat(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": planning_prompt}],
            response_format={"type": "json_object"} # Force JSON output
        )
        
        decision_json = json.loads(planning_response.choices[0].message.content)
        tool_to_use = decision_json.get("tool")

        # 3. **EXECUTION STEP**: Optionally add web search context
        web_context = ""
        if tool_to_use == "web_search":
            search_query = decision_json.get("query")
            print(f"Decision: Use web_search with query: '{search_query}'")
            web_results = perform_web_search(search_query)
            web_context = f"WEB SEARCH RESULTS:\n{web_results}\n\n"
        else:
            print("Decision: Using memory only, no web search needed.")

        # 4. **RESPONSE GENERATION**: Combine memory + web search (if any)
        final_system_instruction = (
            "You are a helpful AI assistant with memory and web search capabilities. IMPORTANT RULES:\n"
            "1. If MEMORY contains the user's name or personal info, ALWAYS use it\n"
            "2. When someone asks 'what's my name?' or 'who am I?', look for their name in MEMORY\n"
            "3. If you have both MEMORY and WEB SEARCH RESULTS, use both appropriately\n"
            "4. For personal questions, prioritize MEMORY. For factual questions, use WEB SEARCH RESULTS\n"
            "5. Be conversational and remember details about the user"
        )

        all_context = f"{memory_context}{web_context}".strip()
        final_user_prompt = (
            f"{all_context if all_context else 'No previous context available.'}\n\n"
            f"User message: '{user_message}'\n"
            f"Response based on the context above:"
        )
        
        final_response = mistral_client.chat(
            model="mistral-small-latest",
            messages=[
                {"role": "system", "content": final_system_instruction},
                {"role": "user", "content": final_user_prompt}
            ]
        )
        bot_response = final_response.choices[0].message.content

        # 5. **SAVE MEMORY** - Keep the enhanced version with name extraction
        # Save the user's message
        memory_to_save = f"User said: '{user_message}'"
        embedding = embedding_model.encode(memory_to_save).tolist()
        supabase.table('memories').insert({
            'user_id': user_id, 'content': memory_to_save, 'embedding': embedding
        }).execute()
        print(f"Saved new memory: '{memory_to_save}'")
        
        # Save name if mentioned
        extracted_name = extract_name_from_message(user_message)
        if extracted_name:
            name_memory = f"The user's name is {extracted_name}"
            name_embedding = embedding_model.encode(name_memory).tolist()
            
            supabase.table('memories').insert({
                'user_id': user_id,
                'content': name_memory,
                'embedding': name_embedding
            }).execute()
            print(f"Saved name memory: '{name_memory}'")
        
        await update.message.reply_text(bot_response)

    except Exception as e:
        logging.error(f"An error occurred in handle_message: {e}")
        await update.message.reply_text("Sorry, something went wrong. Please try again.")

# --- Main Bot Execution ---
def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot with web search and memory is running...")
    application.run_polling()

if __name__ == '__main__':
    main()