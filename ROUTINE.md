# Routine: write one Loyara social post

You are run twice a day by a Claude Code routine (08:30 and 19:30 IST). Your job in this run: write ONE
Threads post (plus a LinkedIn sales post on Mon/Wed/Fri mornings, when the brief says it's due) with posters, and hand them to GitHub,
which publishes them. You write the words yourself. Don't call any other AI model or API.

1. `pip install -q -r requirements.txt`
2. `python -m agent.main brief`
   This picks the slot from the current India time and prints the brief: rules, fact sheet, live website
   content, what performed well, recent hooks to avoid, and the exact JSON shape to fill in.
   Read all of it. The rules in it are binding.
3. Write `data/draft.json` in that shape. Before saving, re-read your text against the rules:
   business only, facts only from the fact sheet, no links/phone numbers, length limits, not a repeat.
4. `python -m agent.main build`
   If it prints DRAFT REJECTED, fix what it lists and run it again until it prints READY.
5. Look at each rendered poster PNG it names (open the image). If text overflows, is cut off or looks
   cramped, shorten the fields under `post.poster` / `post.linkedin_poster` in `data/pending.json` and run
   `python -m agent.main rerender`. Repeat until it's clean and readable.
6. Publish by pushing to a new branch:
   ```bash
   KEY=$(python3 -c 'import json;print(json.load(open("data/pending.json"))["key"])')
   git checkout -b "claude/post-$KEY"
   git add data/pending.json posters/
   git commit -m "Post $KEY"
   git push -u origin "claude/post-$KEY"
   ```
   The "Publish post" GitHub Action takes it from there. Don't open a pull request.
7. Report: slot, pillar, the Threads text, the LinkedIn text (if any) and the poster headline(s).

Don't change any file other than `data/draft.json`, `data/pending.json` and the new poster(s).
If the push fails, report the exact error and stop.
