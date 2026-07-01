---
name: resolve-pr-review-comments
description: >
  Loop through a PR's required gates until both read clean: wait for `ci`
  (fixing failures if any), then wait for the `copilot-review-complete` gate —
  read each unresolved Copilot thread, decide whether it is right, fix the code
  where you agree and reply with reasoning where you don't, resolve every
  thread — commit, run `just pr` to push and refresh, and repeat. Auto-merge is
  armed by the push and held by the gates until a head is clean. Use when the
  user runs /resolve-pr-review-comments or asks to address Copilot review
  comments on a PR. Drives the GitHub API via `gh`.
metadata:
  kind: prompt
  version: "0.8.0"
  user-invocable: "true"
  argument-hint: "[<pr-number-or-url>]"
---

# resolve-pr-review-comments

Invoked as `/resolve-pr-review-comments [<pr-number-or-url>]`. With no argument it
targets the current branch's PR. Prompt-driven: drive `gh` directly and supply the
judgment yourself.

Scope: **GitHub Copilot inline review threads** (author login matches `copilot`
case-insensitively, `__typename` is `Bot`). The PR's top-level review *summary* is
not a resolvable thread — read it for context only.

## How merge is gated

Merging needs three things on the head: the `ci` check passing, a required
`copilot-review-complete` commit status of `success`, and every Copilot thread
resolved. The org gate (a reusable workflow) watches Copilot's review and posts
`copilot-review-complete`: `success` when no unresolved Copilot threads remain,
else `failure`. The native `copilot-pull-request-reviewer` check-run is **not**
the gate — it is excluded from the status rollup; key off `copilot-review-complete`
instead.

*The skill's own loop, step by step — waiting on CI/Copilot (rounded, blue), your
actions and decisions (green — square for actions, diamond for decisions), done
(stadium, grey); node numbers match the steps below:*

```mermaid
flowchart TD
    s1["1: find the PR for the current branch"]:::agent --> s2
    s2("2: wait for ci to settle"):::auto --> s3{"3: ci green?"}:::agent
    s3 -->|no| s11["11: fix the failing ci check"]:::agent --> s10
    s3 -->|yes| s4("4: wait for copilot-review-complete to settle"):::auto --> s5{"5: copilot-review-complete = success?"}:::agent
    s5 ------>|yes| s12(["12: done — auto-merge (already armed) merges the PR"]):::state
    s5 -->|no| s6["6: read and analyze copilot comments"]:::agent --> s7{"7: any comment real/valid?"}:::agent
    s7 -->|yes| s8["8: foreach valid comment — fix code, reply, resolve thread"]:::agent --> s9
    s7 -->|no| s9["9: foreach false positive — reply, resolve thread, add copilot instruction if possible"]:::agent --> s10
    s10["10: commit → `just c` → `just pr`"]:::agent --> s2

    classDef auto stroke:#268bd2,color:#268bd2,stroke-width:2px
    classDef agent stroke:#859900,color:#859900,stroke-width:2px
    classDef state stroke:#657b83,color:#657b83,stroke-width:2px
```

This skill drives that loop end to end: wait for `ci`, fixing it if it's red;
wait for the Copilot gate, triaging its comments if it's red; commit, run
`just pr`, and go around again — until both read green. Auto-merge is safe to
leave on throughout: nothing merges while either check is red or a Copilot
thread is unresolved, and every push resets both checks on the new head, so the
merge only ever fires once the watcher has just certified the current head
clean. Let `just pr` and the gates decide when, rather than hand-managing
auto-merge with `--hold`.

## Step 1 — find the PR

```bash
PR_ARG='__ARGUMENT_OR_EMPTY__'   # the slash-command argument, or empty
OWNER=$(gh repo view --json owner -q .owner.login)
REPO=$(gh repo view --json name -q .name)
NUMBER=$(gh pr view $PR_ARG --json number -q .number)
```

If `gh pr view` reports no PR for the current branch and no argument was given,
stop and ask the user for the PR number — do not guess.

## Steps 2–3 — wait for CI, then branch

Confirm CI is green before even looking at Copilot's review — no point triaging
comments against code that's about to fail its own tests:

```bash
for _ in $(seq 1 60); do
  BUCKET=$(gh pr checks "$NUMBER" --json name,bucket \
    -q '(.[] | select(.name=="ci") | .bucket) // "none"')
  case "$BUCKET" in pass|fail|skipping|cancel) break;; esac
  sleep 10
done
```

(`gh pr checks` is safe here — unlike for the Copilot gate below — because `ci`
always exists once the push triggers it; see Notes. 60×10s gives `ci` up to 10
minutes, comfortably above its observed ~1–2 minute runtime, so a cold-cache or
otherwise slow run doesn't get mistaken for stuck.)

- **`pass`** → continue to **Step 4**.
- **`fail`, `skipping`, or `cancel`** → none of these satisfy the "ci passing"
  merge requirement, so none can be treated as a pass. Check
  `gh pr checks "$NUMBER"` for why: a genuine failure goes to **Step 11**; a
  `skipping`/`cancel` from a superseded or manually-cancelled run means a newer
  run is (or should be) in flight — re-poll, or re-push to retrigger if none is.
- Loop exhausted with no terminal bucket → stop and tell the user; `ci` may be
  stuck queued or the runner may be down.

## Step 11 — fix the failing ci check

`gh pr checks "$NUMBER" --json name,link -q '.[]|select(.name=="ci")|.link'`
opens the failing run; `just c` runs the same lint/type/test gate `ci` does
and is usually the fastest way to reproduce and fix the break. Then go to
**Step 10**.

## Steps 4–5 — wait for the Copilot gate, then branch

Once `ci` is green, wait for the Copilot gate the same way — polling the commit
status directly rather than `gh pr checks` (see Notes for why). Read the SHA
from the PR's head on GitHub, not the local checkout — if the skill was invoked
with an explicit PR number/URL whose head doesn't match the local branch,
`git rev-parse HEAD` would poll the wrong commit's status and report the wrong
gate state:

```bash
SHA=$(gh pr view "$NUMBER" --json headRefOid -q .headRefOid)
for _ in $(seq 1 120); do
  STATE=$(gh api "repos/$OWNER/$REPO/commits/$SHA/statuses" \
    --jq 'map(select(.context=="copilot-review-complete"))[0].state // "none"')
  case "$STATE" in success|failure|error) break;; esac
  sleep 10
done
```

- `success` → **Step 12**, done.
- `failure` → **Step 6** to triage this round's comments. After 5 round trips
  through the loop with threads still remaining, stop, disable auto-merge
  (`gh pr merge "$NUMBER" --disable-auto`), and report what's left — this guards
  against endless Copilot ping-pong.
- `error` or loop exhausted → stop and tell the user (Copilot may be unavailable
  or out of quota, or the gate hit a machinery fault); don't spin forever.

## Steps 6–9 — triage every unresolved comment

Read the unresolved Copilot threads and the diff for the cited files, so your
decision is grounded in the real code (**Step 6**):

```bash
gh api graphql -F owner="$OWNER" -F name="$REPO" -F number="$NUMBER" -f query='
query($owner:String!,$name:String!,$number:Int!){
  repository(owner:$owner,name:$name){
    pullRequest(number:$number){
      reviewThreads(first:100){
        nodes{
          id isResolved isOutdated path line
          comments(first:50){ nodes{ databaseId body author{ login __typename } } }
        }
      }
    }
  }
}'
gh pr diff "$NUMBER"
```

Keep threads where `isResolved` is false and the first comment's author is Copilot;
record each thread's `id`, `path`, `line`, and comment `body`.

Treat every comment with skepticism first — false positives land on almost every
PR. Judge it against the real code, not its own framing: fact-check factual
claims (web search if the code alone doesn't settle it) and weigh it against this
repo's actual goals and conventions (`CLAUDE.md`) before agreeing to change
anything. Neither reflexively agree (Copilot is often right, not always) nor
reflexively defend the code. Act on real bugs, correctness or security risks,
clearer idiomatic forms, and genuine standards violations; disagree with false
positives, style contrary to the repo's conventions, or out-of-scope suggestions
(**Step 7**).

Reply on each thread (not a new top-level comment). Where you **agree**, edit the
code in the working tree — the better long-term design, not the smallest diff —
and reply that it's addressed (e.g. "Done — extracted the guard into
`ensure_loaded`."), but **do not resolve it yet** — leave it for **Step 10**
(**Step 8**). Where you **disagree**, give the reason in a sentence or two,
referencing the code, then resolve it immediately — a disagreement has no code
change riding on it, so there's no race to protect against (**Step 9**). One fix
may settle several threads — note it on each.

```bash
gh api graphql -f threadId='<thread-node-id>' -f body='<reply>' -f query='
mutation($threadId:ID!,$body:String!){
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId,body:$body}){ comment{ url } }
}'
gh api graphql -f threadId='<thread-node-id>' -f query='
mutation($threadId:ID!){ resolveReviewThread(input:{threadId:$threadId}){ thread{ isResolved } } }'
```

If a disagreement is a false positive from a *recurring class* of mistake (not a
one-off), add a short, abstract instruction to `.github/copilot-instructions.md`
to head it off in future reviews — abstract enough to cover the class, not just
this instance. Skip it if the mistake couldn't plausibly recur.

Once every thread has a reply (agreed ones still unresolved), go to **Step 10**.

## Step 10 — commit, push, then resolve

**Commit every code fix before pushing — and push before resolving the
remaining threads.** The org gate re-evaluates `copilot-review-complete` the
instant a thread is resolved; resolving an "agree" thread while its fix is only
local (or committed but unpushed) flips the gate to `success` on the
**old, already-`ci`-green** head, and the already-armed auto-merge can merge
that head — **without your fix** — before the push ever lands. Pushing first
means the fix is already on the head that the gate will see, so there's no
window where a stale head looks clean:

```bash
git add <touched files>
git commit -m '<message>'
just c                    # autofixes throughout — may touch files after the commit above
git status --porcelain   # if non-empty, `just c` autofixed something —
                          # git add -u && git commit -m 'chore: apply autofix' to fold it in
git log --oneline -1     # must show your fix commit(s), not the pre-existing head
```

Commit before running `just c`, not after: some of its checks read the
committed tree rather than the working tree — e.g. `cerberus`'s version-bump
check, which diffs against the last commit — so running it against
uncommitted changes can pass or fail against stale state. If it autofixes
anything post-commit, fold that into a follow-up commit rather than leaving it
uncommitted — an uncommitted autofix is exactly the "unpushed fix" trap Step 10
exists to avoid.

Before running `just pr`, re-run the Step 6 GraphQL query one last time and
confirm every thread from this round — both "agree" and "disagree" — shows
`isResolved: true` except the "agree" ones you're deliberately holding open
until after the push. This catches a thread dropped mid-triage (e.g. a reply
posted but the resolve call missed or failed) before it becomes a stray
unresolved thread on the next round.

Then run `just pr`. It pushes the current head, flips back to ready, and enables
auto-merge (held by the gates until the head is clean). Only once the push has
gone out, resolve every remaining "agree" thread from Step 8 using the same
`resolveReviewThread` mutation above.

- **Changed code** (fixed comments, or fixed a CI failure) → `just pr` flips the
  PR to draft, pushes the fixes, and flips back to ready; that transition
  re-triggers fresh `ci` and Copilot runs on the new commits.
- **No code change** (every thread was a disagreement) → nothing to push, so
  `just pr` just re-flips draft→ready to re-run the watcher and re-count the
  now-resolved threads. It permits this only because Copilot already reviewed
  HEAD; it still refuses if you pre-pushed unreviewed commits.

An unexpected `Everything up-to-date` means an uncommitted fix, not a pushed
one — commit and re-run. Then go back to **Step 2**.

## Step 12 — confirm and report

Reached when `copilot-review-complete` is `success`, with `ci` already green
from Step 3. Every `--ready` run of `just pr` already polls the merge state and
either merges directly or arms auto-merge (`push-branch.ts`) — there's nothing
left to trigger. Just read the outcome:

```bash
gh pr view "$NUMBER" --json state,mergedAt,autoMergeRequest
```

Report whether it merged already or is still queued behind auto-merge. Summarize
per round: agreed-and-fixed (with file:line and what changed) vs. disagreed (with
the reason given), and the final outcome.

## Notes

- The reply, resolve, ready-flip, and merge calls need a token with write access
  (the user's normal `gh auth`). On a permissions error, surface it and stop —
  don't retry blindly.
- Past 100 threads or 50 comments in a thread, paginate with the GraphQL
  `pageInfo`/`endCursor` cursors rather than silently truncating.
- Each push is a fresh head with neither check posted yet, so merge can only
  happen once `ci` and the gate both read clean on the latest head with every
  thread resolved — the loop relies on this, it doesn't race it.
- `gh pr checks --watch` looks like a shortcut for the wait loops above — it
  isn't safe for the Copilot gate: it only reports checks that already exist,
  so a required status not yet posted (a fresh head's `copilot-review-complete`)
  is invisible to it and it returns success early. Confirmed live: a PR with
  `mergeStateStatus: BLOCKED` still showed `--watch --required` reporting all
  visible required checks passing. Poll the status list yourself instead —
  that's why Steps 4–5 use the raw API rather than `gh pr checks`.
