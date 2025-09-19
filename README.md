# V-Me2
Virtual Assistant - Multi-mode interface for email, coding, document processing, and more

## Features
- React frontend with multiple modes (email, coding, supabase, document processing, schedule, budget, PDF viewer, Google Earth)
- Python backend with AI agents using Groq/LangChain
- Supabase integration for data storage
- Voice controls and conversation modes
- High contrast accessibility support

## Deployment
This project is configured for deployment on Railway. See [RAILWAY_DEPLOYMENT.md](RAILWAY_DEPLOYMENT.md) for detailed deployment instructions.

## Local Development
1. Copy `.env.example` to `.env` and configure your API keys
2. Install dependencies:
   ```bash
   npm install
   pip install -r requirements.txt
   ```
3. Build and run:
   ```bash
   npm run build
   npm start  # Serves built React app
   python reAct_agent.py  # Run in separate terminal
   ```
