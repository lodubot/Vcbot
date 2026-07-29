# 🚀 Telegram Multi-Account VC Joiner Bot
### 🛡️ Powered by @Dev_Null_X | Node.js India Developers 🇮🇳

![Banner](https://capsule-render.vercel.app/render?type=waving&color=0:000000,70:00ffcc,100:00ffaa&height=200&section=header&text=TELEGRAM%20VC%20BOT&fontSize=70&animation=fadeIn&fontAlignY=38)

A high-performance, stable, and **Anti-Ban** Telegram Voice Chat joining bot. Manage multiple accounts simultaneously and keep them in VC 24/7 without getting kicked. Works on **Termux, VPS, and Cloud Hosting**.

---

### 🔥 Key Features
- ✅ **Multi-Account Support:** Add unlimited accounts via `/login`.
- 🛡️ **Anti-Ban Logic:** Built-in stay-alive packets to prevent 1-minute kicks.
- ⚙️ **Docker Ready:** Lightweight Alpine-based Dockerfile included.
- ⚡ **Auto-Reconnect:** Sessions are saved locally in `sessions.json`.
- 🔑 **Admin Protected:** Only authorized users can control the bot.

---

### 🛠️ Multi-Platform Setup Guide

#### 📱 Method 1: Termux (Mobile)
Run these commands one by one in your Termux app:
```bash
pkg update && pkg upgrade -y
pkg install nodejs git -y
git clone [https://github.com/Dev-Null-X/TELEGRAM-VC-BOT.git](https://github.com/Dev-Null-X/TELEGRAM-VC-BOT.git)
cd TELEGRAM-VC-BOT
npm install
# Edit config.js (use 'nano config.js')
node index.js

###💻 Method 2: VPS (Ubuntu/Debian)
​Perfect for 24/7 uptime:

sudo apt update && sudo apt upgrade -y
sudo apt install nodejs npm git -y
git clone [https://github.com/Dev-Null-X/TELEGRAM-VC-BOT.git](https://github.com/Dev-Null-X/TELEGRAM-VC-BOT.git)
cd TELEGRAM-VC-BOT
npm install
# Start with PM2 to keep it running 24/7
npm install -g pm2
pm2 start index.js --name "Dev_Null_X_Bot"

###☁️ Method 3: Render (Free Hosting)
​Fork this repository to your GitHub account.
​Login to Render.com and click New > Web Service.
​Connect your GitHub and select TELEGRAM-VC-BOT.
​Build Command: npm install
​Start Command: node index.js
​Add your Environment Variables if needed, or edit config.js before forking.
​📺 Watch Setup Tutorial
​Need help? Watch the full step-by-step video on my YouTube channel:
👉 @Dev_Null_X YouTube Channel
​🤝 Connect & Support
​📢 Telegram: Node.js India Developers
​💻 Developer: @Dev_Null_X
​© 2026 @Dev_Null_X | Distributed under the MIT License.
