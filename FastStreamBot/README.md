# ⚡ FastStreamBot — Complete Setup Guide

## Railway pe deploy karo — Step by Step

---

## 📁 Project Structure

```
FastStreamBot/
├── WebStreamer/
│   ├── __init__.py
│   ├── __main__.py          ← Entry point
│   ├── config.py            ← All env variables
│   ├── bot/
│   │   ├── __init__.py      ← Bot clients + multi-bot manager
│   │   └── plugins/
│   │       ├── __init__.py
│   │       └── commands.py  ← Bot commands + link generation
│   ├── server/
│   │   ├── __init__.py
│   │   ├── app.py           ← FastAPI app
│   │   └── stream_routes.py ← Download endpoints
│   └── utils/
│       ├── __init__.py
│       ├── file_info.py     ← Media extraction
│       ├── secure_link.py   ← Token generation/verification
│       └── custom_dl.py     ← Parallel chunk downloader
├── requirements.txt
├── Procfile
├── railway.json
├── nixpacks.toml
├── .env.example
└── .gitignore
```

---

## STEP 1 — Telegram Setup

### 1.1 API ID aur API Hash lo
1. Browser mein jao: https://my.telegram.org
2. Login karo apne number se
3. "API Development Tools" pe click karo
4. App banao (koi bhi naam)
5. `api_id` aur `api_hash` copy karo

### 1.2 Bot Token lo
1. Telegram pe @BotFather open karo
2. `/newbot` bhejo
3. Naam do (example: MyStreamBot)
4. Username do (example: mystreambot_bot)
5. Token copy karo → `123456789:ABCdef...`

### 1.3 BIN_CHANNEL banao
1. Telegram mein ek **Private Channel** banao
2. Bot ko us channel ka **Admin** banao (full permissions)
3. Channel ID pata karo:
   - Channel mein koi bhi message forward karo @userinfobot ko
   - Wo aapko channel ID dega → `-1001234567890` (negative number)

---

## STEP 2 — GitHub pe Upload karo

```bash
# 1. GitHub pe new repository banao (FastStreamBot naam se)

# 2. Apne computer mein terminal kholo
cd FastStreamBot

# 3. Git initialize karo
git init
git add .
git commit -m "Initial commit"

# 4. GitHub se connect karo (apna username daalo)
git remote add origin https://github.com/YOUR_USERNAME/FastStreamBot.git
git branch -M main
git push -u origin main
```

---

## STEP 3 — Railway Deploy

### 3.1 Railway account banao
1. Jao: https://railway.app
2. "Login with GitHub" se login karo

### 3.2 New Project banao
1. Dashboard mein "+ New Project" click karo
2. "Deploy from GitHub repo" select karo
3. Apna `FastStreamBot` repository select karo
4. "Deploy Now" click karo

### 3.3 Environment Variables set karo
Railway dashboard mein:
1. Apna project open karo
2. "Variables" tab pe click karo
3. Ye sab variables add karo:

```
API_ID          = 12345678
API_HASH        = your_api_hash_here
BOT_TOKEN       = 123456:your_bot_token_here
BIN_CHANNEL     = -1001234567890
SECRET_KEY      = MyRandom32CharSecretKey12345678
LINK_EXPIRY_HOURS = 24
HAS_SSL         = True
```

> ⚠️ `FQDN` abhi mat daalo — pehle deploy hone do

### 3.4 Domain generate karo
1. "Settings" tab pe jao
2. "Networking" section mein "Generate Domain" click karo
3. Domain copy karo → `yourapp.up.railway.app`

### 3.5 FQDN variable add karo
Variables mein add karo:
```
FQDN = https://yourapp.up.railway.app
```

### 3.6 Redeploy karo
1. "Deployments" tab pe jao
2. Latest deployment pe "..." click karo
3. "Redeploy" karo

---

## STEP 4 — Test karo

1. Telegram pe apna bot open karo
2. `/start` bhejo
3. Koi bhi file bhejo (video, audio, document)
4. Bot ek link dega
5. Link kholo → fast download start hoga!

---

## STEP 5 — Speed Badhaao (Optional — Multi-Bot)

Zyada speed ke liye 2-3 aur bots banao:

### 5.1 Worker bots banao
```
@BotFather se 3 aur bots banao:
/newbot → Worker1StreamBot → worker1_stream_bot
/newbot → Worker2StreamBot → worker2_stream_bot
/newbot → Worker3StreamBot → worker3_stream_bot
```

### 5.2 Sab bots ko BIN_CHANNEL mein add karo
Teeno worker bots ko apne BIN_CHANNEL mein Admin banao

### 5.3 Railway Variables mein add karo
```
MULTI_TOKEN1 = 111111:worker1_token_here
MULTI_TOKEN2 = 222222:worker2_token_here
MULTI_TOKEN3 = 333333:worker3_token_here
```

### 5.4 Redeploy karo
Ab 4 bots simultaneously downloads serve karenge!

---

## Common Errors aur Fix

### Error: `BIN_CHANNEL` related error
```
Fix: Bot ko channel ka admin banao with all permissions
```

### Error: `API_ID invalid`
```
Fix: my.telegram.org se dobara copy karo, spaces na ho
```

### Error: Port already in use
```
Fix: Railway PORT variable automatically set karta hai, manually mat daalo
```

### Error: `FloodWait`
```
Fix: Thoda wait karo (1-2 min), Telegram rate limit temporarily lagata hai
Bot automatically retry karta hai
```

### Error: Session file not found
```
Fix: Railway pe session file persist nahi hoti — ye normal hai
Bot har restart pe fresh start karta hai (bot token se login)
```

### Deployment fail ho rahi hai
```
Fix checklist:
1. requirements.txt mein sab packages hain?
2. Sab env variables set hain?
3. BIN_CHANNEL negative number hai? (-100...)
4. Bot channel ka admin hai?
```

---

## Local Test karna ho to

```bash
# 1. Python 3.11 install karo

# 2. Virtual environment banao
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

# 3. Dependencies install karo
pip install -r requirements.txt

# 4. .env file banao
cp .env.example .env
# .env file edit karo aur apni values daalo

# 5. Run karo
python -m WebStreamer
```

---

## How it works (Simple)

```
User → Bot pe file bhejta hai
         ↓
Bot → File BIN_CHANNEL pe forward karta hai
         ↓
Bot → Secure token generate karta hai (24hr expiry)
         ↓
Bot → Link deta hai: https://yourapp.railway.app/TOKEN/filename.mkv
         ↓
User link open karta hai
         ↓
Server → Token verify karta hai
         ↓
File ≤ 20MB?  → Telegram CDN redirect (fastest)
File > 20MB?  → Parallel 4-chunk stream (fast)
         ↓
User ko fast download milta hai ✅
```
