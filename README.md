# Cores AI 🧠✨

A multi-platform AI assistant with long-term memory and real-time web access, designed to be a truly personal and intelligent companion.

[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-active-success.svg)]()



Cores AI is a powerful, custom-built chatbot that goes beyond simple conversations. It's an extensible framework that can remember user-specific details across conversations, explore the live internet to answer questions about current events, and be deployed on multiple platforms.

---

## Key Features

* **🧠 Long-Term Memory:** Utilizes a Supabase Postgres database with `pgvector` to remember key facts and context from past conversations, creating a personalized experience.
* **🌐 Real-Time Web Search:** Integrates with SerpApi to perform live Google searches, allowing it to answer questions about news, recent events, and topics outside of its training data.
* **🤖 Advanced AI Core:** Powered by the Mistral AI API, leveraging powerful models for reasoning, planning, and natural language generation.
* **⚡ Multi-Platform Ready:** Deployed and fully operational on **Telegram**, with a backend ready to support a web interface and other future platforms.
* **⚙️ Efficient & Robust:** Built with a sophisticated backend using FastAPI, with intelligent routing to decide when to use memory vs. web search, optimizing for speed and cost.
* **(Optional) Web Interface:** A clean, responsive web UI built with SvelteKit that connects to the same powerful backend, providing a seamless chat experience in the browser.

---

## Architecture

The project uses a modern, decoupled architecture. A central FastAPI backend contains all the core logic, which can be accessed by various frontends (like the Telegram bot or a web app).

<details>
  <summary><strong>Click to view the Architecture Diagram</strong></summary>

  

  * **Frontends (Telegram/Web):** Send user messages to the backend.
  * **Backend (FastAPI on Render):** The central brain. It receives messages, processes them through the core logic, and sends back a response.
  * **Core Logic:**
      1.  **Memory (Supabase):** Searches the vector database for relevant past conversations.
      2.  **Tools (SerpApi):** Can perform a web search if needed.
      3.  **AI (Mistral):** Takes the user's message plus any context from memory or web search to generate the final, intelligent response.

</details>

---

## Getting Started

Follow these steps to get a local copy up and running.

### Prerequisites

* Python 3.11+
* A free [Supabase](https://supabase.com) account
* API keys for:
    * [Mistral AI](https://console.mistral.ai/)
    * [Telegram (from BotFather)](https://core.telegram.org/bots#6-botfather)
    * [SerpApi](https://serpapi.com/)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/your-username/Cores_AI.git](https://github.com/your-username/Cores_AI.git)
    cd Cores_AI
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required packages:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your Environment Variables:**
    * Create a file named `.env` in the root of the project.
    * Add the following lines, replacing the placeholders with your actual keys:
        ```env
        TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
        MISTRAL_API_KEY="YOUR_MISTRAL_API_KEY"
        SUPABASE_URL="YOUR_SUPABASE_URL"
        SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
        SERPAPI_API_KEY="YOUR_SERPAPI_API_KEY"
        ```

5.  **Set up the Supabase Database:**
    * Go to the **SQL Editor** in your Supabase project.
    * Run the SQL commands provided in the repository to create the `memories` table and search function.

---

## Usage

To run the bot locally for development (which starts both the Telegram bot and the FastAPI web server):
bash
python bot.py

Your Telegram bot will start polling for messages, and the web API will be available at http://localhost:8000.

Deployment
The backend is designed for deployment on services like Render. The main branch is configured to run as a FastAPI web service using Gunicorn.

Push the code to a GitHub repository.

Create a new "Web Service" on Render and connect your repository.

Use the following settings:

Runtime: Python 3

Build Command: pip install -r requirements.txt

Start Command: gunicorn -w 1 -k uvicorn.workers.UvicornWorker bot:app

Add your environment variables in the Render dashboard.

Set the Telegram webhook to your new Render URL.
```
***
How to Clone and Run This Project on Another PC 💻

Here are the step-by-step instructions you can share for someone to set up and run your project from GitHub.

1.  **Clone the Repository**
    Open a terminal and run the following command, replacing the URL with your repository's URL.
    bash
    git clone https://github.com/your-username/Cores_AI.git
    

2.  **Navigate to the Project Directory**
    bash
    cd Cores_AI
    

3.  **Create a Virtual Environment**
    This keeps the project's dependencies isolated.
    bash
    # On Windows
    python -m venv venv
    .\venv\Scripts\activate
    

4.  **Install Dependencies**
    This command reads the `requirements.txt` file and installs all the necessary Python libraries.
    bash
    pip install -r requirements.txt
    

5.  **Create the `.env` File**
    Create a file named `.env` in the project folder and paste the following, filling in your own secret API keys.
    env
    TELEGRAM_TOKEN="YOUR_TELEGRAM_TOKEN"
    MISTRAL_API_KEY="YOUR_MISTRAL_API_KEY"
    SUPABASE_URL="YOUR_SUPABASE_URL"
    SUPABASE_KEY="YOUR_SUPABASE_ANON_KEY"
    SERPAPI_API_KEY="YOUR_SERPAPI_API_KEY"
    

6.  **Set Up the Database**
    Log in to your Supabase account, go to the SQL Editor, and run the SQL commands included in the `README.md` to create the `memories` table.

7.  **Run the Bot**
    You're all set! Run the bot locally with:
    bash
    python bot.py
   
