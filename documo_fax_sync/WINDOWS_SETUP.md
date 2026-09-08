# Setting this up on your Windows Server

No code-writing needed. You'll install one free program, copy a folder onto
the server, edit one settings file, test it safely in stages (nothing
touches your real fax inbox or share folder until you're confident it
works), then tell Windows to run it automatically forever. Steps 1-8
below, in order.

---

## Before you start: get the real network path, not the drive letter

`Z:\` is a shortcut that only exists while someone is logged into that
specific Windows session. A scheduled task that runs "whether user is
logged on or not" (which you want, for 24/7 operation) usually **cannot
see `Z:\`** — it'll fail silently or error.

Find the real path once, right now, so you can use it instead:

1. Open **File Explorer**.
2. Right-click on the `Z:` drive in the left sidebar -> **Properties**.
3. Look for a line like `\\FILESERVER01\Faxes` -- that's the real network
   path. Write it down (with whatever subfolder you want faxes saved into,
   e.g. `\\FILESERVER01\Faxes\Incoming`).

You'll paste that into the settings file in Step 6, instead of `Z:\...`
(Steps 4-5 use a throwaway test folder first, deliberately, before this
real path comes into play at all).

---

## 1. Install Python (one time)

1. Go to `python.org/downloads/windows` and download the latest installer.
2. Run it. **On the very first screen, check the box "Add python.exe to
   PATH"** before clicking Install. This is the one step people miss.
3. Click "Install Now", wait for it to finish, click Close.
4. Verify it worked: open **Command Prompt** (Start menu -> type `cmd` ->
   Enter), type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.x`. If you see an error
   instead, Python didn't get added to PATH -- reinstall and make sure that
   checkbox is checked.

## 2. Copy the program onto the server

Copy the whole `documo_fax_sync` folder (the one this file is in) onto the
server, for example to:

```
C:\Apps\documo_fax_sync
```

Any way of getting it there is fine -- shared drive, USB, downloading a zip
from wherever this project is hosted and extracting it.

## 3. Install its dependencies (copy-paste, one time)

Open **Command Prompt as Administrator** (right-click Command Prompt ->
"Run as administrator"), then run these lines one at a time:

```
cd C:\Apps\documo_fax_sync
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

That last command downloads the small pieces of code this program depends
on. It'll print a bunch of text and finish with something like
`Successfully installed ...`. That's normal, not an error.

## 4. Fill in your settings -- starting with SAFE, throwaway settings

1. In File Explorer, go to `C:\Apps\documo_fax_sync`.
2. Find the file `.env.example`. Copy it, and rename the copy to `.env`
   (just `.env`, nothing before the dot).
3. Right-click `.env` -> **Open with** -> **Notepad**.
4. Find these lines and fill them in like this **for now** -- deliberately
   pointing at a harmless local folder, not your real share, and telling it
   not to change anything in Documo:
   ```
   DOCUMO_API_KEY=your_documo_api_key
   SHARE_DIR=/mnt/fax-share/incoming
   MARK_AS_READ=true
   ```
   Change to:
   ```
   DOCUMO_API_KEY=<paste your real Documo key here>
   SHARE_DIR=C:\Users\<your username>\Desktop\fax_test
   MARK_AS_READ=false
   ```
   `SHARE_DIR` here is just a test folder on your own machine -- it'll be
   created automatically the first time you run it, nothing needs to exist
   there yet. `MARK_AS_READ=false` means it downloads and saves a copy but
   leaves the fax marked "unread" in Documo, so nobody's real workflow is
   affected while you're testing.
5. Save the file (Ctrl+S), close Notepad.

Don't touch any other file. Everything else is already set up.

## 5. Test it safely, in two stages

**Stage A -- prove the API key works, with zero side effects.** This
doesn't download, save, or change anything -- it only asks Documo "what's
there?" and prints the answer. Run:

```
cd C:\Apps\documo_fax_sync
.venv\Scripts\python sync.py --dry-run
```

Look for a line like `Found N inbound fax(es)` and, for each one,
`[DRY RUN] Would save fax ...`. A connection or key problem shows up here
as a clear error instead. If this doesn't come back clean, stop and see
**Troubleshooting** below -- don't move on yet.

**Stage B -- prove it can actually save a file**, still only to the
throwaway test folder from Step 4, still without touching Documo's read
status:

```
.venv\Scripts\python sync.py
```

If you have a real unread fax waiting, look for
`Saved fax ... to C:\Users\...\Desktop\fax_test\...pdf` -- then go check
that folder in File Explorer and confirm the PDF is actually there and
opens correctly. If nothing's currently unread in Documo, send yourself a
test fax first so there's something for it to find.

Repeat Stage B as many times as you like -- since `MARK_AS_READ=false`,
the same fax will keep showing up as "new" and get re-saved each run,
which is fine for testing (it won't create duplicates in the test folder
either, since it overwrites the same filename).

Only once both stages look right, move on to Step 6.

## 6. Switch to your real settings

Open `.env` in Notepad again and change the two lines you set for testing:

```
SHARE_DIR=\\FILESERVER01\Faxes\Incoming
MARK_AS_READ=true
```

(using the real network path you found in "Before you start" up top, not
`Z:\...`). Save and close.

Optionally run `.venv\Scripts\python sync.py` by hand one more time to
confirm a fax now lands in the *real* share folder and gets marked read in
Documo, before handing it off to Task Scheduler.

## 7. Make it run automatically (Task Scheduler)

1. Open **Task Scheduler** (Start menu -> search "Task Scheduler").
2. On the right, click **Create Task...** (not "Create Basic Task" -- the
   plain "Create Task" gives you the option you need in step 3 below).
3. **General** tab:
   - Name: `Documo Fax Sync`
   - Select **"Run whether user is logged on or not"**.
   - Check **"Run with highest privileges"**.
4. **Triggers** tab -> **New...**:
   - Begin the task: **On a schedule**
   - Daily, recurring every 1 day
   - Check **"Repeat task every"** and set it to `15 minutes`, for a
     duration of `Indefinitely`.
   - Click OK.
5. **Actions** tab -> **New...**:
   - Action: **Start a program**
   - Program/script: `C:\Apps\documo_fax_sync\.venv\Scripts\python.exe`
   - Add arguments: `sync.py`
   - Start in: `C:\Apps\documo_fax_sync`
   - Click OK.
6. **Conditions** tab: uncheck "Start the task only if the computer is on
   AC power" (not relevant on a server, but harmless to leave either way).
7. Click **OK** on the main window. Windows will prompt for the
   administrator account's password -- enter it. This is the account the
   task will run as, which is why the network path (not the drive letter)
   matters: this account needs permission to reach that share, same as
   your regular login does.

## 8. Confirm it's actually running on schedule

- In Task Scheduler, find "Documo Fax Sync" in the list, right-click it ->
  **Run**, to fire it immediately once.
- Click the **History** tab at the bottom for that task to see whether it
  ran successfully. (If History is empty/greyed out, click **Enable All
  Tasks History** in the Action menu on the right first.)
- After a real fax comes in, check the network folder a few minutes later
  for a new PDF.

---

## Troubleshooting

- **"'python' is not recognized..."** -- Python wasn't added to PATH.
  Reinstall Python and check that box on the first screen.
- **`DOCUMO_API_KEY is not set`** -- the `.env` file isn't named exactly
  `.env`, isn't in the `documo_fax_sync` folder, or the line wasn't saved.
- **A 401/403-type error when it talks to Documo** -- the API key is
  wrong, expired, or the way it's sent doesn't match what Documo expects.
  See the note at the top of `README.md` ("Verify against the Documo
  docs") -- this is the one part of the setup that may need a small
  settings tweak, not code changes, if Documo's real API differs slightly
  from what was assumed.
- **It works when you run it by hand but not from Task Scheduler** --
  almost always the mapped-drive-letter problem described at the top.
  Double check `SHARE_DIR` in `.env` is the `\\server\share\...` form, not
  `Z:\...`.
- **Faxes aren't showing up even though Documo has new ones** -- run
  `.venv\Scripts\python sync.py` by hand again and read what it prints;
  it logs exactly what it found and any error for each fax it tried to
  save.
