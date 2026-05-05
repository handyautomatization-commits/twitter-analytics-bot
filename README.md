# 📊 Twitter Analytics Bot

A free, self-hosted Twitter/X analytics bot that sends you a **weekly Telegram report** with AI-powered insights — no Twitter API key required.

> Runs automatically every Sunday via GitHub Actions. All data stays in your own repository.

---

## What you get every week

| Feature | Details |
|---|---|
| 📈 **Weekly overview** | Impressions, engagement rate, likes, retweets, replies |
| 📊 **Week-over-week comparison** | See if you're growing or declining |
| 🏆 **Top 3 posts** | Best performing tweets with AI explanation of *why* they worked |
| 📉 **Bottom 3 posts** | Worst performing tweets with AI explanation of *why* they flopped |
| ⏰ **Best posting times** | Top hours and days by engagement rate |
| 💡 **AI recommendations** | 5 concrete action items for next week (powered by DeepSeek) |
| 🏛️ **Hall of Fame** | All-time top 10 tweets tracked across weeks |
| 📅 **Monthly report** | 4-week rollup sent on the 1st of each month |
| ⚠️ **Cookie expiry alerts** | Warning when your cookies are about to expire |

---

## Setup (15 minutes)

### Step 1 — Fork this repository

Click **Use this template** (or **Fork**) in the top right. Keep it public or make it private — your choice.

### Step 2 — Export your Twitter cookies

1. Open [x.com](https://x.com) in Chrome and log in
2. Install the [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) extension
3. Click the extension icon → **Export** → **Export as JSON**
4. Copy the entire JSON

### Step 3 — Create a Telegram bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot`
2. Copy the **bot token**
3. Add the bot to your channel as admin
4. Get your channel ID (e.g. `@yourchannel` or a numeric ID like `-1001234567890`)

### Step 4 — Add GitHub Secrets

Go to your forked repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret name | Value |
|---|---|
| `TWITTER_COOKIES` | The JSON you copied from Cookie-Editor |
| `TELEGRAM_BOT_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_CHANNEL_ID` | Your channel ID (e.g. `@mychannel`) |
| `DEEPSEEK_API_KEY` | *(Optional)* [Get free key](https://platform.deepseek.com/) for AI insights |

### Step 5 — Enable GitHub Actions

Go to **Actions** tab in your repo → click **"I understand my workflows, go ahead and enable them"**

### Step 5.5 — Choose your language *(optional)*

Reports default to **English**. To switch to Russian, go to your repo → **Settings** → **Secrets and variables** → **Actions** → **Variables** tab → **New repository variable**:

| Variable name | Value |
|---|---|
| `REPORT_LANGUAGE` | `en` or `ru` |

Alternatively, skip this step — on your **first real run** the bot will send a language selection message to Telegram with two buttons (🇬🇧 English / 🇷🇺 Русский). Tap one and your choice is saved automatically.

### Step 6 — Test it

Go to **Actions** → **Weekly Twitter Analytics Report** → **Run workflow** → set `test_mode = true` → **Run workflow**

You'll get a sample report in Telegram within ~3 minutes. If it works, you're all set!

---

## Schedule

| Report | When |
|---|---|
| Weekly report | Every **Sunday at 09:00 UTC** |
| Monthly report | **1st of each month at 09:00 UTC** |

You can also trigger any report manually from the Actions tab.

---

## How it works

```
GitHub Actions (cron)
  └── Playwright opens x.com/i/account_analytics
  └── Intercepts ContentPostListQuery GraphQL response
  └── Parses tweet metrics (no Twitter API needed)
  └── Runs AI analysis via DeepSeek
  └── Sends formatted report to Telegram
  └── Saves data back to your repo
```

No servers, no databases, no monthly fees. Runs entirely on GitHub's free tier.

---

## FAQ

**Q: Do I need a Twitter/X Premium account?**  
A: No. The bot reads from the Analytics page which is available to all accounts.

**Q: How long do cookies last?**  
A: Typically 30–90 days. The bot will warn you in Telegram when they're close to expiring.

**Q: Is this against Twitter's ToS?**  
A: This tool reads data from your own account analytics page — the same data you see when you visit x.com/i/account_analytics manually. Use it responsibly and only for your own account.

**Q: What if I don't add DEEPSEEK_API_KEY?**  
A: The bot still works — you get all metrics, top/bottom posts, and timing insights. You just won't get the AI-written explanations and recommendations.

**Q: The workflow says "ContentPostListQuery not intercepted" — what do I do?**  
A: Your cookies have expired. Re-export from Cookie-Editor and update the `TWITTER_COOKIES` secret.

---

## Tech stack

- **Python 3.11** + Playwright (browser automation)
- **GitHub Actions** (scheduling & hosting)
- **python-telegram-bot** (Telegram delivery)
- **DeepSeek API** (optional AI analysis, free tier available)

---

## License

MIT — free to use, modify, and share.
