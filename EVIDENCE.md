# 🔎 Evidence — it really runs (not a mock-up)

This project genuinely runs end-to-end in the cloud: it generates a digest, **emails it**, and **publishes a website** automatically. Here's how to verify that independently.

## 1. The website is live (proves the cloud build + deploy work)
➡️ **https://bestcodereverforsure.github.io/pharma-brief/**
This page is built and published by GitHub Actions on every run — it's not hand-uploaded.

## 2. The email actually sends (proof from the cloud run log)
The automated GitHub Actions run executed the email step and got a success response from Resend (the email provider). Straight from the run log:

```
Sent ✓  (200)  -> ***
{"id":"f97d0a79-1e1c-4e69-87f4-ced8528663fc"}
[main 192a71d] Digest 2026-06-12
```

- `Sent ✓ (200)` = Resend accepted and sent the email (HTTP 200).
- `{"id":"f97d0a79-…"}` = the Resend message ID for that specific email.
- `***` = the recipient is hidden because the email address is stored as an encrypted secret (it's never exposed, even in logs).
- The same run then auto-committed the digest (`Digest 2026-06-12`) and deployed the site.

**Verify it yourself:** open the repo's **Actions** tab → a run of "Pharma Morning Digest (DeepSeek)" → expand **"Generate and email the digest"** → you'll see the `Sent ✓ (200)` line.
➡️ https://github.com/BestCoderEverForSure/pharma-brief/actions

## 3. It has run repeatedly (proof of automation, not a one-off)
The `digests/` folder holds multiple dated digests produced by different runs/engines:
- `2026-06-12.md` (featured, Claude engine)
- `2026-06-12-deepseek.md` (DeepSeek engine)
- `2026-06-12-since-0605.md` (a week-window run)

## 4. The infrastructure that was set up
- **GitHub repository** with a scheduled **GitHub Actions** workflow (`.github/workflows/pharma-digest.yml`) — runs daily at 07:00 Rome, no laptop needed.
- **Resend** (transactional email) wired in via a *send-only* API key, stored as an encrypted GitHub Secret.
- **GitHub Pages** hosting the website, redeployed on every run.

## For the live demo (optional, 1 minute)
Two screenshots make this undeniable in the gallery walk:
1. The **received email** in your Gmail inbox.
2. The **green ✓** on the latest GitHub Actions run.
Drop them in a `screenshots/` folder if you want them in the submission too.
