# Railway Deployment Guide for V-Me2

This guide helps you deploy the V-Me2 Virtual Assistant to Railway.

## Prerequisites

1. **Git Repository**: Your code should be in a GitHub repository
2. **Railway Account**: Sign up at [railway.app](https://railway.app/)
3. **Environment Variables**: API keys and configuration values (see .env.example)

## Deployment Steps

### 1. Prepare Your Repository

Ensure all files are committed to your GitHub repository:
```bash
git add .
git commit -m "Prepare for Railway deployment"
git push origin main
```

### 2. Create Railway Project

1. Open [railway.app](https://railway.app/) in your browser
2. Click "Start a New Project"
3. Choose "Deploy from GitHub repo"
4. Select your V-Me2 repository
5. Railway will automatically detect the buildpacks

### 3. Configure Environment Variables

In Railway dashboard, go to Variables tab and add:

**Required Variables:**
- `GROQ_API_KEY` - Your Groq API key for language model
- `SUPABASE_SERVICE_KEY` - Supabase service role key
- `GITHUB_PAT` - GitHub Personal Access Token
- `RAILWAY_API_TOKEN` - Railway API token (for API access)

**Optional Variables:**
- `OPENAI_API_KEY` - OpenAI API key (if using OpenAI models)
- `SERPAPI_KEY` - SerpAPI key for search functionality
- `CLOUDFLARE_API_TOKEN` - Cloudflare API token
- `TWILIO_API_KEY` - Twilio API key for communication features
- `GOOGLE_SERVICE_ACCOUNT_JSON` - Google service account JSON

### 4. Configure Build Settings

Railway should automatically detect:
- **Build Command**: `npm install && npm run build && pip install -r requirements.txt`
- **Start Command**: `npm start` (serves the built React app)
- **Port**: Auto-assigned by Railway

### 5. Deploy

1. Click "Deploy" in Railway dashboard
2. Monitor the build logs for any issues
3. Once deployed, Railway will provide a public URL

## Project Structure

This is a hybrid React/Python application:

- **Frontend**: React app (built and served via npm/serve)
- **Backend**: Python services (reAct_agent.py, various API integrations)
- **Configuration**: railway.json, Procfile for deployment settings

## Files Created/Modified for Railway

- `public/` - React public assets directory
- `src/index.js` - React entry point
- `src/App.css` - React styles
- `railway.json` - Railway configuration
- `.env.example` - Environment variables template
- `package.json` - Updated with serve dependency and deployment scripts
- `Procfile` - Process configuration for Railway

## Troubleshooting

### Build Fails
- Check that all environment variables are set
- Verify Python requirements.txt is valid
- Ensure Node.js and Python buildpacks are detected

### App Won't Start
- Check the logs for specific error messages
- Verify environment variables are correctly set
- Ensure all API keys are valid

### API Errors
- Verify API keys in environment variables
- Check Supabase connection and permissions
- Validate external service configurations

## Local Development

To run locally:

1. Copy `.env.example` to `.env` and fill in values
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

## Support

- Railway Documentation: [docs.railway.app](https://docs.railway.app/)
- Check Railway logs for deployment issues
- Verify all environment variables are properly configured