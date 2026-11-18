Voice Typer - Gemini API: Free vs Paid cost
============================================
(Checked: 2026-11-18. Prices change - always verify at the links below.)

Moving from Free to Paid
------------------------
- There is no fee or subscription for switching. Enabling billing on the Google
  Cloud project behind your API key is free; after that you pay only for usage.
- How to check which tier you are on: https://aistudio.google.com/api-keys
  -> look at the "Plan" / "Billing tier" next to your key's project
  ("Free tier" vs "Tier 1 / Paid").

Model price (gemini-3.5-flash-lite, Standard tier)
--------------------------------------------------
- Input (includes your audio): $0.30 per 1 million tokens
- Output (the transcribed text): $2.50 per 1 million tokens

Rough dictation cost (estimate)
-------------------------------
Assumes about 32 tokens per second of audio (approximate, not re-verified).

  1 minute of speech                 ~ $0.0015  (about 1/6 of a cent)
  10 minutes a day, for a month      ~ $0.50
  1 hour a day, for a month          ~ $3

Most of the cost is the output text. Hebrew text uses more tokens than English,
so real numbers may be somewhat higher or lower.

Notes
-----
- If the lite model fails, the app retries once with gemini-3.8-flash, which is
  likely more expensive (price not checked). This happens only on failures.
- After enabling billing, set a budget alert:
  Google Cloud Console -> Billing -> Budgets & alerts (e.g. $5/month).
  You will get an email if usage spikes unexpectedly (e.g. a leaked key).

Sources
-------
- https://ai.google.dev/gemini-api/docs/pricing
- https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- https://ai.google.dev/gemini-api/docs/generate-content/whats-new-gemini-3.6
