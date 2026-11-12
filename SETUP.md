# Loyara social agent: setup

**What it does**
- **Threads, every day.** 2 posts focused on clients, leads and website traffic:
  - 8:30 AM: lead posts (a business problem, then the fix, then a free consultation).
  - 7:30 PM: traffic posts. When the 6 PM blog routine has published a new article, this post teases it and
    links to it. Otherwise it's a direct offer.
- **LinkedIn, every day at 8:30 AM**, alternating:
  - one day a **sales pitch** (problem → solution, a service/package spotlight, or how we work),
  - the next day an **educational** post (a practical tip, a website/Meta Ads lesson, AI in marketing, or
    lessons from the latest blog article).
- **The website blog is unchanged.** Your existing 6 PM routine keeps running on its own.

Every post gets a branded poster and a tracked link. It runs fully in the cloud, so your laptop can stay off.

**Cost:** ₹0 extra. Opus 5.5 writes the posts through your Claude Pro plan, as a routine like your blog.
That's 3 of Pro's 5 routine runs a day: blog 1 + Threads 2. LinkedIn is written in the morning run,
so it uses no extra runs.

## How it works

```
Claude routine (2x/day, Opus 5.5)        GitHub Action (free)
  reads website, blog + results   ──▶     posts to Threads (+ link reply)
  writes Threads (+ LinkedIn M/W/F)       posts to LinkedIn (+ link comment)
  renders poster, pushes to GitHub        records likes/replies/views for next time
```

Your Threads and LinkedIn tokens live only in GitHub Secrets. The routine never sees them.

---

## Step 1: GitHub repository

1. On https://github.com (the same account as your website repo, `kavinvishak01-web`) click **New repository**.
   Name it `Loyara_Social-` and make it **Public**. Public is needed so Threads can download the poster
   images; your tokens stay private in Secrets.
2. Upload this folder. In Terminal:
   ```bash
   cd ~/Desktop/"threads AI agent" && git init && git add . && git commit -m "Loyara social agent" && git branch -M main && git remote add origin https://github.com/kavinvishak01-web/Loyara_Social-.git && git push -u origin main
   ```
3. Check Claude can access it: open https://github.com/settings/installations, click **Configure** next
   to the Claude app, and make sure `Loyara_Social-` is included (or "All repositories" is selected).

## Step 2: Threads token

1. Go to https://developers.facebook.com and click **My Apps → Create App**, then choose the use case
   **"Access the Threads API"**. Name it e.g. "Loyara Poster".
2. Under the use case's permissions, add: `threads_basic`, `threads_content_publish`,
   `threads_manage_insights`, `threads_manage_replies`.
3. Go to **App roles → Roles → Add people → Threads Tester** and enter your Threads username. Then on your phone,
   open **Threads → Settings → Account → Website permissions → Invites** and accept.
4. In the Threads use case **Settings**, open the **User Token Generator** and click **Generate access token** for your account.
5. Get your user ID. Open this in a browser, replacing TOKEN:
   `https://graph.threads.net/v1.0/me?fields=id,username&access_token=TOKEN`
6. If the token only lasts 1 hour, swap it for a 60-day one (App secret is in **App settings → Basic**):
   `https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=APP_SECRET&access_token=TOKEN`

The app can stay in Development mode, since it only posts to your own account.

## Step 3: LinkedIn token (personal profile)

1. Go to https://www.linkedin.com/developers/apps and click **Create app**. LinkedIn requires a Company Page
   to be linked, so use the Loyara page (create one if you don't have it).
2. In the app's **Products** tab, add **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. Go to **Auth** tab → **OAuth 2.0 tools** (or https://www.linkedin.com/developers/tools/oauth/token-generator)
   → pick your app → tick `openid`, `profile`, `w_member_social` → **Request access token**. Copy it.
4. Get your author ID by running this in Terminal (replace TOKEN), then copy the `sub` value:
   ```bash
   curl -s -H "Authorization: Bearer TOKEN" https://api.linkedin.com/v2/userinfo
   ```
   Your author URN is `urn:li:person:` followed by that value, e.g. `urn:li:person:AbC123xyz`.

LinkedIn tokens expire after **60 days** and can't be renewed automatically for personal profiles.
A weekly check opens a GitHub issue (GitHub emails you) when it stops working. Then repeat step 3.3
and update the secret. It takes 2 minutes.

## Step 4: Add the secrets

In the `Loyara_Social-` repo, go to **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|---|---|
| `THREADS_ACCESS_TOKEN` | Step 2.4 / 2.6 |
| `THREADS_USER_ID` | Step 2.5 |
| `LINKEDIN_ACCESS_TOKEN` | Step 3.3 |
| `LINKEDIN_AUTHOR_URN` | Step 3.4, e.g. `urn:li:person:AbC123xyz` |
| `GH_PAT` | GitHub → Settings → Developer settings → Fine-grained tokens → only `Loyara_Social-`, permission **Secrets: Read and write**, 1-year expiry. Used to renew the Threads token weekly. |

Never paste these into chat or code.

## Step 5: The routine

Tell Claude "create the routine", or use https://claude.ai/code/routines with:
- **Repository:** `kavinvishak01-web/Loyara_Social-`
- **Schedule:** `0 3,14 * * *` (= 8:30 AM and 7:30 PM IST)
- **Model:** Opus 5.5
- **Prompt:** "You are the social media writer for Loyara Agency. Follow ROUTINE.md in this repository step by step."

## Step 6: Test

Run the routine once with **Run now**. Within about 5 minutes you should see:
- a new branch appear and disappear in the repo,
- the **Publish post** run under the **Actions** tab turn green,
- the post on Threads (and on LinkedIn if it's a Monday, Wednesday or Friday morning).

Test runs count towards the 5 runs a day.

---

## Changing things

- **What it may say:** `config/business.md`. Add real client results here (with permission) and posts get stronger.
- **Logo:** save a white/transparent PNG as `assets/logo.png`.
- **WhatsApp:** set `"whatsapp_number": "91XXXXXXXXXX"` in `config/settings.json`. Social and ads posts
  will then link to WhatsApp.
- **LinkedIn topics:** `"linkedin" → "angles"` (sales / education) in `config/settings.json`.
- **Threads topics:** `"slots"` and `"pillars"` in `config/settings.json`.
- **If a post fails:** GitHub opens an issue and emails you with the error.

## What you still do (10 minutes a day)

Reply to comments and DMs quickly, on both platforms. That's what spreads posts and turns a commenter
into a client. To see results, check Google Analytics for `utm_source=threads` and `utm_source=linkedin`.
