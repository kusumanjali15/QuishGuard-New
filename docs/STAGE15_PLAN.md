# Stage 15 pre-registration - behaviour-only model vs hand rules (RQ: behaviour beats static)

Pre-registered BEFORE building. Stage 15 is a BEHAVIOUR-ONLY model from the Stage 14b traces,
compared with the hand-written rules at a fixed FPR, on a kit-family-disjoint split. It is NOT
the URL model (that is the Stage 13 addendum, docs/STAGE13_ADDENDUM.md).
Revised 2026-11-28 with approved amendments (benign diversity, timing confound, POST-length
confound, exact rule, frozen clustering params, selection note).

## 0. Environment / data location
- The 101 phishing-positive traces live ONLY in the WSL copy /home/user/quishguard-fresh/
  lab14b/traces/ (gitignored; real attacker emails). The Claude-connected folder is the Windows
  copy C:\dev\quishguard-fresh, which does NOT contain them.
- Stage 15 generation + feature extraction runs IN WSL. Only a SCRUBBED behaviour-feature table
  (no identifiers, no origin/URL) leaves WSL for modelling. Raw traces never move.

## 0.5 Recorder enhancement (needed before generating features)
The current trace schema records post_len but NOT field metadata. Add per-send, SCRUBBED
(names/types only, never values):
  - field types present in the submitted form: password / otp-or-code / card  (booleans)
  - hidden_token_field_present: a hidden <input> whose name matches token|csrf|nonce|auth (bool)
Re-generate the 101 kit traces AND the benign traces with the enhanced recorder, using the
SAME driver (quishguard.victim) and the SAME fixed typing delays for kits and benign (amendment 2).

## 1. Features - client-observable behaviour ONLY  (no origin/URL/domain/IP/HTTPS)
HEADLINE model features:
  - n_sends, n_post
  - n_steps                         (page transitions before the send; count only - borderline, own ablation)
  - post_len_max, post_len_total    (see amendment 3: report an ablation WITHOUT these)
  - has_hidden_token_field          (NEW, amendment 3 - CSRF-token presence)
  - sensitive field types: is_password, is_otp_or_code, is_card
  - n_fields_filled, n_forms
ABLATION-ONLY (never in headline):
  - t_first_cred_ms  (amendment 2: can encode server setup php -S vs Docker, not behaviour)
  - origin feature: same-origin vs cross-origin send (amendment/section 6)
DROPPED entirely:
  - mail_exfil   (server sends it; a WebView sensor can never observe it)
  - forced_submit (harness artifact)
Reported ablations: (a) without post_len_*, (b) without n_steps, (c) +t_first_cred_ms, (d) +origin.

## 2. Benign traces - realistic, diverse, local (amendment 1)
>= 12-15 DISTINCT self-hosted apps in Docker, fake accounts, 127.0.0.1 only, driven through the
SAME sensor + schema + victim script as the kits. NEVER any live/real website.
Candidate apps: WordPress, Joomla, Drupal, MediaWiki, Moodle, phpBB, Nextcloud, Gitea, GitLab CE,
Mattermost, Rocket.Chat, Grafana, Matomo, Roundcube, Keycloak/Authentik.
Flow types per app where available: plain login; wrong-password-then-retry; 2FA/OTP; sign-up;
password reset.
Report N as (distinct apps, distinct flows), NOT raw repetitions. EACH APP IS ITS OWN GROUP in
the split (so no app appears in both train and test).

## 3. Kit-family labels + frozen clustering (amendment 5)
- First check DynaPD repo/paper/metadata for family IDs (our extraction shipped none).
- Else derive family by CODEBASE FINGERPRINT: per-kit set of file basenames; build a graph with an
  edge when Jaccard(basename_set_i, basename_set_j) >= 0.80; families = connected components.
  FROZEN: Jaccard threshold = 0.80. Exact-match (1.0) reported as a conservative alternative.
- Compute the clustering ONCE, record the resulting family count here before any modelling:
      FAMILIES = <fill once, then frozen>
- Split: GroupShuffleSplit / StratifiedGroupKFold grouped by family (kits) and by app (benign),
  so no family and no app is in both train and test.

## 4. Exact behaviour-only hand rule (amendment 4)
This is score_send with origin + impersonation REMOVED, leaving behaviour/field terms only.
Inputs (all client-observable, 0/1):
  pw   = password field submitted
  otp  = otp-or-code field submitted
  card = card field submitted
  steps= (n_steps >= 3)
  many = (n_sends >= 5)
  big  = (post_len_total >= 200 bytes)
Score = pw + otp + card + steps + many + big      (ALL WEIGHTS = 1; weights are NOT tuned)
Decision: flag if Score >= T. T is FROZEN on the TRAIN split to hit the target FPR on TRAIN
benign, then applied unchanged to TEST (same protocol as the model).
Note: pw is ~constant across benign and phishing logins, so it does not aid ranking; recorded
for completeness. Separating terms are steps / many / big / otp / card.

## 5. Evaluation protocol
- Metric: recall at a fixed FPR with the threshold FROZEN on train (choose T on train negatives
  for the target FPR, apply to test). Report a confusion matrix at the frozen threshold + AUC.
- FPR floor (set by benign N): report recall @ 10%, 5%, 1% FPR. HEADLINE = 5% FPR. At 1% the cut
  rests on ~1 benign group, so report it with a wide-CI caveat. Do NOT report 0.1% (needs ~1000
  negatives). If total benign traces < 100, drop the 1% column.
- 10-run family/app-disjoint evaluation; report mean +/- std (expect wide CIs, small classes).
- Compare: the behaviour-only hand rule (section 4) vs LightGBM, both behaviour-only.
- class_weight="balanced"; grouped CV; NO oversampling across the split (would leak).

## 5b. Class balance & sample size (amendment 1)
- Positive: 101 kit traces (send-reaching), fixed.
- Benign: ~15 apps x ~3-4 flows => ~45-60 distinct flows; with a few reps ~90-120 traces.
  Report N as distinct apps and distinct flows. Each app = one group.
- If benign distinct flows are few, the FPR floor rises accordingly (see section 5).

## 6. Origin ablation (kept separate)
One extra column adding ONE origin-derived feature (same-origin vs cross-origin send) to the
behaviour model, to quantify origin's contribution. Reported as an ablation, never in the headline.

## 7. Frozen selection note (amendment 5)
Of 301 sampled kits, 101 reached a credential send. Stage 15 and all its numbers apply to the
SUBPOPULATION of kits that reach a send - not to all phishing kits. Stated in notes and paper.

## 8. Expected result - WRITTEN BEFORE RUNNING
Without origin/URL features a phishing login and a benign login behave almost identically (both
type a password/OTP into a form and POST it same-origin). The behaviour-only model MAY NOT
separate them. If so, we report that as the finding: the discriminating signal is
origin/impersonation - exactly what the runtime RULE uses - supporting the rule-based runtime
rather than a learned behaviour classifier replacing it. If some behaviour feature does separate
them, we report the family-disjoint recall@FPR. Either outcome is published honestly; we do not
tune toward a "win".
