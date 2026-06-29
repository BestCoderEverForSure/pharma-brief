# 📖 The Simple Guide (ELI5)

This explains everything you have, in plain language. No jargon.

---

## What is this project?
A little robot that reads the pharma news for you every morning, writes a 2-3 minute summary (with analysis and a focus on Eli Lilly), and **emails it to you** + **puts it on a website**.

## 🎛️ The Command Centre - your one button
**Double-click `Pharma Command Centre.command`** in this folder. One menu controls everything (simple Mac pop-ups, no typing):
- **Generate a digest now** (on this Mac) - pick window + edition + email
- **Run the cloud digest now** - emails you and updates the website
- **Turn the daily 7am cloud digest ON / OFF**
- **Open the website**
- **Status** - last run, is the daily one on, last cloud run
- **Edit** your watchlist / news sources / calendar
- **Make an audio brief**

*(First time: if macOS blocks it, right-click → Open → Open once.)*
The only thing it can't drive is the premium **Claude** read - for that, type `/pharma-news` in the Claude app.

---

## The one idea to hold onto: 1 recipe, 3 cooks, 1 waiter

- **The recipe** 📋 - a set of instruction files that say what a good digest looks like (what to cover, how to analyse, the Lilly focus, the format). Every cook follows the *same* recipe.
- **Three cooks** 👨‍🍳 - three different AIs that can write the digest:
  - **Gemini** = the *free, reliable* cook who shows up every morning. Reads a fixed list of news sites and summarises them, in the cloud. This is the **default** for the automatic daily brief — free on Google's tier.
  - **DeepSeek** = the *cheap stand-in* cook. Same job as Gemini (same news list, runs in the cloud), but costs a few pennies per brief — switch to it any time from the Command Centre.
  - **Claude** = the *smart* cook. Searches the whole web, finds more, writes richer analysis. Runs on your Mac inside the Claude app, on demand. Costs your Claude plan.
- **The waiter** 📨 - a small script that takes the finished digest and **emails it to you** (via a service called Resend). Same waiter for every cook.

That's the whole thing. Everything below is just *where* and *when* the cooks work.

---

## Where you READ it
- **📧 Email** - lands in your Gmail every morning. This is your main way to read it (works on your phone).
- **🌐 Website** - https://bestcodereverforsure.github.io/pharma-brief/ - a nice page with the latest digest, a calendar of upcoming events (you can subscribe to it), charts, an archive of past digests, and a search box. There's a **▶ Listen** button to hear a brief read aloud, a **Threads** page to follow a topic (e.g. Eli Lilly) across every brief, and you can **install it on your phone and read offline**. Open it anywhere.

---

## When it runs (the automatic part)
- **In the cloud (GitHub), every morning at 7am Rome time.** Mon-Fri it's the tight daily brief; **Saturday** a deeper "Week in Review" (looking back); **Sunday** a "Week Ahead" (looking forward). On the **last weekend of each month** these grow into a "Month in Review" and "Month Ahead", and at the **end of December** into a "Year in Review" and "Year Ahead". This is the reliable one - it runs even if your laptop is closed or off, because it's on GitHub's computers, not yours. It makes the digest (Gemini by default), emails you, posts a Telegram card you can share, and updates the website.
- You don't have to do anything. It just happens.
- **If Gemini is briefly too busy** (Google's free tier sometimes says "overloaded"), it waits and retries for a bit. If it still can't run, you get an email so you know that morning was missed — it does **not** quietly switch to the paid cook. If you'd rather it fall back to DeepSeek on those days so the brief always lands, turn that on in the Command Centre under **Settings → Engine fallback** (off by default).

## How to STOP or START the automatic run
1. Go to **github.com/BestCoderEverForSure/pharma-brief**
2. Click the **"Actions"** tab at the top.
3. Click the workflow named **"Pharma Morning Digest"** on the left.
4. **To stop:** click the **"•••"** button (top right) → **"Disable workflow."**
   **To start again:** same place → **"Enable workflow."**
   **To run it right now (any time):** click **"Run workflow."**

That's the only on/off switch you need.

---

## When YOU want a richer read (on-demand)
Open the Claude app and type **`/pharma-news`**. That runs the *smart* cook (Claude) live - broader research, sharper analysis. Use it when you want the premium version. Variations:
- `/pharma-news evening` → a longer 5-8 minute read with a deep dive.
- `/pharma-news catchup` → everything since the last time you ran it.
- You can also just ask: *"what happened with orforglipron last month?"* - it searches your saved archive.

---

## How to change what it covers
Edit these files (then, for the cloud, push them to GitHub):
- **`pharma-news/watchlist.md`** - the companies, topics, and themes to always track.
- **`pharma-news/catalysts.md`** - upcoming dates (approvals, earnings, conferences) shown on the website timeline.
- **`engine/feeds.txt`** - the news websites the cheap cook reads.

---

## Your private stuff (and why it's safe)
- Your **email address** and **API keys** are stored as encrypted "Secrets" on GitHub and in a private file on your Mac (`~/.config/pharma-news/secrets.env`). They are **never** shown on the public website or in the code.
- The public website and code have **no name, no email** - it's anonymous apart from your GitHub username.

---

## If something looks wrong
- **No email arrived?** Check Gmail spam. Then GitHub → Actions tab → did the last run succeed (green ✓) or fail (red ✗)? Click it to see why.
- **Want to pause everything?** Disable the workflow (see "How to STOP" above).
- See `README.md` for the detailed/technical version, and `ROADMAP.md` for what's done and what's next.
