# lab14b - DynaPD live-behaviour lab

Runs real **de-weaponized** DynaPD kits fully contained, and records per-kit behaviour traces
with OUR sensor. Design + safety are pre-registered in `docs/STAGE14B_PLAN.md`. Read that first.

## Golden rule
Build/debug ONLINE with the egress test and our own safe pages only. Run REAL kits only with the
machine physically DISCONNECTED from the network, and only after `egress_test.py` prints ISOLATED.

## One-time setup (WHILE ONLINE)
On the isolated Windows box (admin PowerShell), set up WSL2 + Ubuntu:
    wsl --install -d Ubuntu          # reboot if prompted, then open "Ubuntu"
Inside Ubuntu:
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv php-cli docker.io git
    sudo usermod -aG docker $USER    # then close/reopen the Ubuntu shell
    # get the code + kits (online):
    git clone <your repo URL> quishguard-fresh
    git clone https://github.com/code-philia/DynaPD.git   # the 6,000+ de-weaponized kits
    cd quishguard-fresh
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    python -m playwright install --with-deps chromium

## Verify isolation (the GATE)
    python lab14b/egress_test.py      # must print ISOLATED before any kit runs
Run this with the machine DISCONNECTED, immediately before each real-kit session.

## Record kits   (built next - needs a sample kit layout first)
    # python lab14b/record_kit.py <path-to-one-kit-dir>   # writes a per-kit JSON trace
Traces go to a PRIVATE location only; scrub attacker identifiers before any public release
(see docs/STAGE14B_PLAN.md - Data governance).


## Get the dataset (while ONLINE)
The kits are a Google Drive archive (see DynaPD/README.md). `gdown <id>` often hits a "too many users"
quota; if so, open the link in a browser, **Make a copy** to your own Drive, download that, then
`cp /mnt/c/Users/<you>/Downloads/<file> ~/dynapd.archive` and extract into `~/dynapd_kits/`.

## Validate the recorder OFFLINE-SAFE, before any real kit (self-test)
A safe fake "kit" (`lab14b/selftest_kit/`) posts fake creds to itself and mail()s them to a
configurable address - mirroring DynaPD's email exfil - so you can prove the whole pipeline works
without a real kit:
    python lab14b/record_kit.py lab14b/selftest_kit --out lab14b/traces/selftest.json
Expect: `front_end_fake=True` (the form POST carried the fake password) and `mail_exfil=True
mail_fake=True` (mail() was captured with the fake creds). Open lab14b/traces/selftest.json to see
the per-kit trace shape.

## Record a real kit (DISCONNECTED, after egress_test.py says ISOLATED)
    python lab14b/egress_test.py                 # must print ISOLATED
    python lab14b/record_kit.py ~/dynapd_kits/<one-kit-dir>
Traces + mail logs go to lab14b/traces/ (gitignored - they may contain the kit's attacker address;
scrub before any public release).
