# Railway Deployment Guide for Sentinal Honeypot

## Quick Deploy (5 Minutes)

### Prerequisites
- GitHub account
- Railway account (free tier works: https://railway.app)
- OpenRouter API key (get free from: https://openrouter.ai)

---

## Step-by-Step Deployment

### 1. Push Code to GitHub

```bash
cd "/Users/MyWork/My Apps/Sentinal"

# Initialize git (if not already)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Sentinal Honeypot with Orchestra"

# Create new repo on GitHub (via web interface)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/sentinal-honeypot.git
git branch -M main
git push -u origin main
```

### 2. Deploy to Railway

#### Option A: Deploy via Dashboard (Recommended)

1. **Go to Railway**: https://railway.app
2. **Click "New Project"**
3. **Select "Deploy from GitHub repo"**
4. **Choose your `sentinal-honeypot` repository**
5. **Railway will auto-detect** the configuration from `railway.json`

#### Option B: Deploy via CLI

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Link to your repo
railway link

# Deploy
railway up
```

### 3. Configure Environment Variables

In Railway dashboard:

1. **Go to your project** → **Variables tab**
2. **Add these variables**:

```bash
# REQUIRED
OPENROUTER_API_KEY=sk-or-v1-YOUR_ACTUAL_KEY_HERE
MY_API_KEY=sentinal-hackathon-2026

# OPTIONAL (defaults work fine)
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
GUVI_CALLBACK_URL=https://hackathon.guvi.in/api/submit-intelligence
```

3. **Click "Deploy"** (Railway will auto-redeploy with new env vars)

### 4. Get Your Deployment URL

1. **Go to "Settings" tab**
2. **Under "Domains"**, click **"Generate Domain"**
3. **Copy the URL**: `https://your-app-name.up.railway.app`

### 5. Test Your Deployment

```bash
# Replace with YOUR Railway URL
export RAILWAY_URL="https://your-app-name.up.railway.app"

# Test health endpoint
curl $RAILWAY_URL/health

# Expected response:
# {"status":"healthy","version":"1.0.0"}

# Test analyze endpoint
curl -X POST "$RAILWAY_URL/analyze" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sentinal-hackathon-2026" \
  -d '{
    "sessionId": "test-123",
    "message": {
      "sender": "scammer",
      "text": "Your account is blocked! Call 9876543210 urgent KYC",
      "timestamp": 1234567890000
    },
    "conversationHistory": []
  }'

# Expected: JSON response with scam detection and intelligence
```

---

## Configuration Files Explained

### `railway.json`
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"  // Auto-detects Python
  },
  "deploy": {
    "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100
  }
}
```

### `Procfile` (Backup for Railway)
```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

### `requirements.txt`
All dependencies auto-installed by Railway.

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENROUTER_API_KEY` | ✅ Yes | - | Your OpenRouter API key |
| `MY_API_KEY` | ✅ Yes | - | API key for authenticating requests to your honeypot |
| `OPENROUTER_BASE_URL` | ❌ No | `https://openrouter.ai/api/v1` | OpenRouter API endpoint |
| `GUVI_CALLBACK_URL` | ❌ No | `https://hackathon.guvi.in/api/submit-intelligence` | GUVI callback endpoint |
| `PORT` | 🔧 Auto | Railway sets automatically | Server port |

---

## API Endpoints (After Deployment)

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | No | Welcome message |
| `/health` | GET | No | Health check |
| `/analyze` | POST | ✅ API Key | Main scam analysis endpoint |
| `/api/analyze` | POST | ✅ API Key | Alternative analyze endpoint |
| `/debug/session/{sessionId}` | GET | ✅ API Key | Debug session data |
| `/metrics` | GET | ✅ API Key | System metrics |

### Example Request

```bash
curl -X POST "https://your-app.up.railway.app/analyze" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sentinal-hackathon-2026" \
  -d '{
    "sessionId": "scammer-001",
    "message": {
      "sender": "scammer",
      "text": "URGENT! Your account suspended. Call 9876543210 immediately!",
      "timestamp": 1708080000000
    },
    "conversationHistory": []
  }'
```

### Example Response

```json
{
  "status": "success",
  "reply": "Oh no sir! What happened? I don't understand. Please tell me the process.",
  "scamDetected": true,
  "extractedIntelligence": {
    "bankAccounts": [],
    "upiIds": [],
    "phishingLinks": [],
    "phoneNumbers": ["+919876543210"],
    "paymentApps": [],
    "domainRiskScores": {}
  },
  "scamAnalysis": {
    "scamType": "ACCOUNT_THREAT",
    "confidence": 0.87,
    "keywords": ["urgent", "account", "suspended", "immediately", "contains_phone"]
  },
  "scammerProfile": {
    "signature": "a3f8920cd4ab",
    "tactics": ["urgency", "threat", "authority"]
  },
  "engagementMetrics": {
    "turns_completed": 1,
    "time_wasted_seconds": 0,
    "intelligence_density": "low"
  }
}
```

---

## Monitoring Your Deployment

### Railway Dashboard

1. **Deployments tab**: View build logs and deployment history
2. **Metrics tab**: CPU, memory, network usage
3. **Logs tab**: Real-time application logs

### View Logs

```bash
# Via CLI
railway logs

# Or in dashboard: Deployments → View Logs
```

### Common Log Patterns

```
✅ Good:
[INFO] LLM response from meta-llama/llama-3.2-3b-instruct: Oh no sir...
[INFO] Scam detected: KYC_FRAUD (confidence=0.85)
[INFO] Extracted intelligence: 2 items

⚠️ Watch:
[WARNING] LLM rate limited: 5 calls in last minute
[WARNING] Model meta-llama/llama-3.2-3b-instruct timed out

❌ Fix:
[ERROR] Invalid API key
→ Check MY_API_KEY environment variable

[ERROR] OpenRouter API error
→ Check OPENROUTER_API_KEY is valid
```

---

## Resource Usage (Railway Free Tier)

| Resource | Limit | Sentinal Usage | Status |
|----------|-------|----------------|--------|
| **Memory** | 512MB | ~100MB | ✅ Within limit |
| **CPU** | Shared | Low (<10%) | ✅ Efficient |
| **Builds** | 500 hrs/month | Minimal | ✅ Plenty |
| **Bandwidth** | 100GB | <1GB | ✅ More than enough |

**Verdict**: Sentinal fits comfortably within Railway's free tier!

---

## Troubleshooting

### Issue: Build fails with "No module named 'xxx'"

**Solution**: Check `requirements.txt` includes all dependencies
```bash
# If missing, add to requirements.txt:
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
requests==2.31.0
python-dotenv==1.0.0
httpx==0.27.2
```

### Issue: App crashes on startup

**Check logs**:
```bash
railway logs
```

**Common causes**:
1. Missing `OPENROUTER_API_KEY` → Add in Railway Variables
2. Port binding issue → Should use `$PORT` (auto-set by Railway)
3. Import errors → Check all files are committed to git

### Issue: 401 Unauthorized

**Solution**: Check API key header
```bash
# Must include:
-H "x-api-key: sentinal-hackathon-2026"
# (or whatever you set MY_API_KEY to)
```

### Issue: LLM responses fail

**Check**:
1. `OPENROUTER_API_KEY` is valid (test at https://openrouter.ai/keys)
2. Account has credits (free tier has limits)
3. Check logs for model-specific errors

**Fallback**: System uses curated templates when LLM fails, so scammer engagement continues

---

## Custom Domain (Optional)

1. **Go to Settings** → **Domains**
2. **Click "Custom Domain"**
3. **Enter your domain**: `api.sentinal-honeypot.com`
4. **Add CNAME record** in your DNS:
   ```
   CNAME api.sentinal-honeypot.com → your-app.up.railway.app
   ```
5. **Wait for DNS propagation** (~5 minutes)

---

## Scaling Beyond Free Tier

If you exceed free tier limits:

### Vertical Scaling
Railway automatically suggests upgrades when needed.

### Horizontal Scaling
1. **Add Redis** for session state:
   - In Railway, click "New" → "Database" → "Redis"
   - Update code to use Redis instead of in-memory sessions

2. **Add PostgreSQL** for intelligence persistence:
   - In Railway, click "New" → "Database" → "PostgreSQL"
   - Update code to store intelligence in DB

3. **Load Balancing**:
   - Deploy multiple instances
   - Railway handles load balancing automatically

---

## CI/CD (Automatic Deployments)

Railway auto-deploys on every git push to `main`:

```bash
# Make changes
vim main.py

# Commit and push
git add .
git commit -m "Improved scam detection"
git push origin main

# Railway automatically:
# 1. Detects push
# 2. Builds new image
# 3. Runs health checks
# 4. Deploys (zero-downtime)
```

**Control deployments**:
- Settings → Disable "Auto Deploy" to deploy manually
- Use branches for staging: Railway can deploy `main` (prod) and `staging` separately

---

## Security Best Practices

### 1. Rotate API Keys Regularly

```bash
# In Railway dashboard
# Variables → MY_API_KEY → Edit → Save
# (Auto-redeploys)
```

### 2. Use Strong API Keys

```bash
# Generate secure key:
openssl rand -hex 32
# Use output as MY_API_KEY
```

### 3. Monitor Access Logs

```bash
railway logs | grep "401\|403"
# Check for unauthorized access attempts
```

### 4. Rate Limiting

Already implemented in code:
- 10 requests/minute per session
- 30 requests/minute per IP
- 20 LLM calls/minute global

---

## Next Steps After Deployment

### 1. Update GUVI Dashboard
- Add your Railway URL to GUVI competition dashboard
- Test callback endpoint receives intelligence

### 2. Monitor First Scammer
- Watch logs for first scam detection
- Verify intelligence extraction
- Check GUVI callback success

### 3. Share API
- Document your Railway URL
- Share with team/evaluators
- Keep API key secure!

---

## Quick Reference

```bash
# Railway CLI commands
railway login              # Login to Railway
railway link               # Link to project
railway logs              # View logs
railway status            # Check deployment status
railway open              # Open app in browser
railway run <command>     # Run command in Railway environment

# Testing endpoints
export URL="https://your-app.up.railway.app"
curl $URL/health
curl $URL/metrics -H "x-api-key: YOUR_KEY"
```

---

## Support

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **Sentinal Issues**: Check logs in Railway dashboard

---

## Summary

✅ **Configuration files ready** (`railway.json`, `Procfile`, `requirements.txt`)  
✅ **Environment variables documented** (OPENROUTER_API_KEY, MY_API_KEY)  
✅ **Deploy via 1-click**: GitHub → Railway → Deploy button  
✅ **Auto-scaling**: Railway handles scaling automatically  
✅ **Free tier compatible**: <100MB memory, minimal CPU  
✅ **CI/CD ready**: Auto-deploys on git push  

**Your Sentinal honeypot will be live in <5 minutes!**
