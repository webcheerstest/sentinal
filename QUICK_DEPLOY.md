# 🚀 QUICK START: Deploy to Railway in 5 Minutes

## Option 1: One-Click Deploy (Easiest)

### Step 1: Push to GitHub
```bash
cd "/Users/MyWork/My Apps/Sentinal"
git init
git add .
git commit -m "Sentinal Honeypot - Ready for Railway"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/sentinal-honeypot.git
git push -u origin main
```

### Step 2: Deploy on Railway
1. Go to **https://railway.app**
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Choose **`sentinal-honeypot`**
5. ✅ Auto-deploys!

### Step 3: Set Environment Variables
In Railway dashboard → **Variables tab**:
```
OPENROUTER_API_KEY = sk-or-v1-YOUR_KEY_HERE
MY_API_KEY = sentinal-hackathon-2026
```

### Step 4: Generate Domain
**Settings** → **Domains** → **Generate Domain**

Copy URL: `https://sentinal-xxxxxx.up.railway.app`

### Step 5: Test
```bash
curl https://sentinal-xxxxxx.up.railway.app/health

# Expected: {"status":"healthy","version":"1.0.0"}
```

**DONE!** 🎉

---

## Option 2: CLI Deploy (Automated)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Run deployment script
./deploy_railway.sh

# Follow prompts, then set env vars in Railway dashboard
```

---

## 📋 Checklist

- [ ] Code pushed to GitHub
- [ ] Railway project created
- [ ] Environment variables set (`OPENROUTER_API_KEY`, `MY_API_KEY`)
- [ ] Domain generated
- [ ] Health endpoint tested (`/health` returns 200)
- [ ] Analyze endpoint tested with scam message
- [ ] GUVI dashboard updated with Railway URL

---

## ⚡ Quick Test

```bash
export URL="https://your-app.up.railway.app"

# Health check
curl $URL/health

# Scam detection test
curl -X POST "$URL/analyze" \
  -H "Content-Type: application/json" \
  -H "x-api-key: sentinal-hackathon-2026" \
  -d '{
    "sessionId":"test-1",
    "message":{"sender":"scammer","text":"Urgent! Account blocked. Call 9876543210","timestamp":1708080000000},
    "conversationHistory":[]
  }'
```

---

## 🔧 Configuration Files

✅ `railway.json` — Railway deployment config (with healthcheck)  
✅ `Procfile` — Backup start command  
✅ `requirements.txt` — Python dependencies  
✅ `.env.example` — Environment variable template  
✅ `deploy_railway.sh` — Automated deployment script  

---

## 📖 Full Documentation

See **`RAILWAY_DEPLOY.md`** for:
- Detailed troubleshooting
- Monitoring and logs
- Scaling beyond free tier
- Custom domains
- CI/CD setup
- Security best practices

---

## 💰 Cost

**Free Tier**: 512MB RAM, 500 build hours/month  
**Sentinal Usage**: ~100MB RAM, minimal CPU  
**Verdict**: ✅ Runs comfortably on free tier!

---

## 🆘 Help

- **Railway not detecting app?** → Check `railway.json` exists
- **Build fails?** → Check `requirements.txt` has all dependencies
- **401 errors?** → Check `MY_API_KEY` env variable is set
- **LLM fails?** → Check `OPENROUTER_API_KEY` is valid

Full guide: `RAILWAY_DEPLOY.md`
