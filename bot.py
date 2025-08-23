# bot.py (Version 5 - With Web Endpoint - FIXED)
import os
import logging
import json
import asyncio
import re
import uvicorn
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from mistralai.client import MistralClient
from serpapi import GoogleSearch
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading

# --- Basic Setup & Client Initialization ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
load_dotenv()

# --- Load API Keys ---
TELEGRAM_TOKEN, MISTRAL_API_KEY, SUPABASE_URL, SUPABASE_KEY, SERPAPI_API_KEY = (
    os.getenv("TELEGRAM_TOKEN"), os.getenv("MISTRAL_API_KEY"), os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY"), os.getenv("SERPAPI_API_KEY")
)

# --- Initialize Clients ---
mistral_client = MistralClient(api_key=MISTRAL_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# Use this smaller model to save memory
embedding_model = SentenceTransformer('sentence-transformers/paraphrase-albert-small-v2')
print("Embedding model loaded successfully.")

# --- Initialize FastAPI ---
app = FastAPI(title="AI Bot API", version="1.0.0")

# --- Add CORS middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, restrict this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        params = {"q": query, "api_key": SERPAPI_API_KEY, "engine": "google"}
        search = GoogleSearch(params)
        results = search.get_dict()
        snippets = [res["snippet"] for res in results.get("organic_results", [])[:4] if "snippet" in res]
        if "answer_box" in results and "snippet" in results["answer_box"]:
             return results["answer_box"]["snippet"]
        print(f"Found {len(snippets)} snippets from web search.")
        return " ".join(snippets) if snippets else "No results found."
    except Exception as e:
        print(f"Error in web search: {e}")
        return f"Error in web search: {e}"

# --- Core Bot Logic (Refactored for reuse) ---
async def get_bot_response(user_id: int, user_message: str) -> str:
    """Core bot logic that can be used by both Telegram and Web API"""
    try:
        # 1. **ALWAYS SEARCH MEMORY FIRST**
        message_embedding = embedding_model.encode(user_message).tolist()
        params = {
            'query_embedding': message_embedding,
            'match_threshold': 0.3,
            'match_count': 8,
            'p_user_id': int(user_id)
        }
        memories = supabase.rpc('match_memories', params).execute()
        
        memory_context = ""
        if memories.data:
            print(f"Found {len(memories.data)} relevant memories.")
            memory_context += "MEMORY from past conversations:\n"
            for memory in memories.data:
                memory_context += f"- {memory['content']}\n"

        # 2. **PLANNING STEP**: Decide if web search is needed
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
            response_format={"type": "json_object"}
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

        # 4. **RESPONSE GENERATION**: Combine memory + web search
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

        # 5. **SAVE MEMORY**
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

        return bot_response

    except Exception as e:
        logging.error(f"Error in get_bot_response: {e}")
        return "Sorry, something went wrong. Please try again."

# --- FastAPI Models ---
class ChatRequest(BaseModel):
    user_id: int
    message: str

class ChatResponse(BaseModel):
    response: str

# --- FastAPI Endpoints ---
@app.get("/")
async def root():
    return {"message": "AI Bot API is running!", "version": "1.0.0"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Web API endpoint for chatting with the bot"""
    bot_response = await get_bot_response(request.user_id, request.message)
    return ChatResponse(response=bot_response)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "telegram_bot": "running", "web_api": "running"}

# --- Telegram Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_name = update.effective_user.first_name
    await update.message.reply_html(
        f"Hi {user_name}! I can remember our conversations and search the web. Ask me anything!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_id = update.effective_user.id
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Use the same core logic as the web API
    bot_response = await get_bot_response(user_id, user_message)
    await update.message.reply_text(bot_response)

# --- Main Application Runner ---
def run_telegram_bot():
    """Run Telegram bot in a separate thread"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Telegram bot is running...")
    application.run_polling()

def run_fastapi():
    """Run FastAPI server"""
    print("FastAPI server starting on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == '__main__':
    # Run both Telegram bot and FastAPI server
    print("Starting AI Bot with both Telegram and Web API...")
    
    # Start Telegram bot in a separate thread
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    
    # Start FastAPI server (blocking)
    run_fastapi()