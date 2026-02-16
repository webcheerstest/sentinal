#!/bin/bash

# Quick Railway Deployment Script for Sentinal Honeypot

set -e

echo "======================================"
echo " SENTINAL HONEYPOT - RAILWAY DEPLOY"
echo "======================================"

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial commit - Sentinal Honeypot"
else
    echo "✅ Git repository already initialized"
fi

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found!"
    echo ""
    echo "Install it with:"
    echo "  npm install -g @railway/cli"
    echo ""
    echo "Or deploy via Railway web dashboard:"
    echo "  https://railway.app/new"
    exit 1
fi

echo ""
echo "🚂 Deploying to Railway..."
echo ""

# Login to Railway
railway login

# Initialize Railway project
echo "Initializing Railway project..."
railway init

# Deploy
echo "Deploying..."
railway up

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Set environment variables in Railway dashboard:"
echo "   - OPENROUTER_API_KEY"
echo "   - MY_API_KEY"
echo ""
echo "2. Generate a domain in Railway Settings → Domains"
echo ""
echo "3. Test your deployment:"
echo "   curl https://your-app.up.railway.app/health"
echo ""
echo "Full guide: See RAILWAY_DEPLOY.md"
