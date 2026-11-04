@echo off
setlocal
REM Preflight output must return to this batch file. A large diff otherwise
REM opens Git's interactive pager and strands the operator at (END).
set "GIT_PAGER=cat"
set "PAGER=cat"
REM --- find the repo ----------------------------------------------------------
REM This script lives IN the clone, so the clone is wherever this script is.
REM %~dp0 is that folder, with a trailing backslash, drive included. Resolving it
REM this way means the folder can be moved, renamed or put on another drive and
REM the script still works. It used to hold a hardcoded D:\ path; the folder moved
REM to C:\Users and every run exited here before reaching git.
cd /d "%~dp0" || (echo [ERROR] could not enter "%~dp0" & pause & exit /b 1)
if not exist ".git" (
  echo [ERROR] no .git here - this script is not sitting in the clone.
  echo         Looked in: "%~dp0"
  echo         Put push.bat back in the pipeline-registry folder and re-run.
  pause & exit /b 1
)
echo [ok] repo: %cd%

REM --- clear a STALE lock, but only if no git process is running ---
if exist ".git\index.lock" (
  tasklist /fi "imagename eq git.exe" 2>nul | find /i "git.exe" >nul
  if errorlevel 1 (
    echo [info] stale index.lock found, no git running - removing it
    del ".git\index.lock"
  ) else (
    echo [ABORT] git is currently running. Not touching the lock.
    echo         Close other git/terminals, then re-run.
    pause & exit /b 1
  )
)

REM --- read-only preflight: no mirroring, staging or record clearing yet -------
echo.
echo === PRE-FLIGHT - NOTHING HAS BEEN STAGED ===
if exist ".git\MERGE_HEAD" (
  echo [ABORT] unfinished merge detected.
  pause & exit /b 1
)
if exist ".git\rebase-merge" (
  echo [ABORT] unfinished rebase detected.
  pause & exit /b 1
)
for %%F in (AGENTS.md CONTROL.txt BLUEPRINT.front.md GUIDE.md PROCESSES.md DIRECTORY.yaml BLUEPRINT.txt shift.py sync_master.py build.py extract.py seal.py clear_pending.py) do (
  if not exist "..\%%F" (
    echo [ABORT] required workspace file missing: ..\%%F
    pause & exit /b 1
  )
)
git fetch origin || (echo [FAIL] fetch failed - nothing changed locally & pause & exit /b 1)
git -c core.safecrlf=false --no-pager diff --check || (echo [ABORT] whitespace/error check failed & pause & exit /b 1)
if not exist "Control\CONTROL.txt" (
  echo [ABORT] required steering source missing: Control\CONTROL.txt
  pause & exit /b 1
)
%SystemRoot%\System32\fc.exe /b "..\CONTROL.txt" "Control\CONTROL.txt" >nul
if errorlevel 1 (
  echo [ABORT] root CONTROL.txt and Control\CONTROL.txt differ.
  pause & exit /b 1
)
python Blueprint\build.py --check --release || (
  echo [ABORT] Blueprint beta is stale or invalid.
  pause & exit /b 1
)
for /f "delims=" %%C in ('git status --porcelain -- Control') do (
  echo [ABORT] Control has changes, but its legacy generator is not compatible
  echo         with the current Blueprint beta. Validate Control separately.
  pause & exit /b 1
)

echo.
echo --- branch and payload ---
git --no-pager status --short --branch
echo.
git -c core.safecrlf=false --no-pager diff --stat
echo.
git -c core.safecrlf=false --no-pager diff --name-status
echo.
echo --- untracked files ---
git ls-files --others --exclude-standard
echo.
echo --- pending record ---
type COMMITS-PENDING.md

echo.
echo --- bootstrap files that will change ---
for %%F in (AGENTS.md shift.py sync_master.py build.py extract.py seal.py clear_pending.py) do (
  if not exist "bootstrap\%%F" (
    echo   ADD bootstrap\%%F
  ) else (
    %SystemRoot%\System32\fc.exe /b "..\%%F" "bootstrap\%%F" >nul
    if errorlevel 1 echo   UPDATE bootstrap\%%F
  )
)

echo.
echo Review every modified, deleted and untracked path above.
echo Typing PUSH authorises the exact displayed payload, bootstrap mirrors,
echo pending-list archival, commit, rebase, push and remote verification.
echo This beta workflow does not seal an edition or refresh Shift or pCloud.
set "BKP_CONFIRM="
set /p "BKP_CONFIRM=Type PUSH to continue, or press Enter to stop: "
if /I not "%BKP_CONFIRM%"=="PUSH" (
  echo [STOPPED] preflight only. Nothing staged, committed or pushed.
  exit /b 0
)
echo [confirmed] beginning the authorised push sequence.
REM --- mirror the bootstrap set into the clone so the push backs it up -------
REM These workspace files live at the Project_Space root and are NOT part of the published
REM volume. AGENTS.md must sit at the root to be read on entry, and none of them
REM may go in Blueprint\ or the compile job would treat them as components. That
REM leaves them on one machine, unbacked. This mirrors them into bootstrap\ so
REM they ride every push.
REM
REM ONE DIRECTION ONLY: root -> clone, overwriting. The root copy is the source;
REM the clone copy is a backup and is never edited. To restore, copy the three
REM files from bootstrap\ up into Project_Space.
echo.
echo === mirroring bootstrap set ===
if not exist "bootstrap" mkdir "bootstrap"
REM 100826: seal.py and clear_pending.py added. push.bat CALLS both, so a repo
REM that does not hold them carries a push script it cannot run after a restore.
for %%F in (AGENTS.md shift.py sync_master.py build.py extract.py seal.py clear_pending.py) do (
  if exist "..\%%F" (
    copy /Y "..\%%F" "bootstrap\%%F" >nul
    echo   mirrored %%F
  ) else (
    echo   [WARN] ..\%%F not found - NOT mirrored
  )
)

REM --- clear the pending list INTO the commit that carries the work -----------
REM The protocol says lines clear on the push, in the same commit. Nothing did
REM it, so the list filled at session rate and never emptied - 71 entries back
REM to 4 July when this was found on 100826. Every line still pending at this
REM point is by definition about to be pushed, so nothing needs judging: the
REM whole block moves to COMMITS-ARCHIVE.md and rides the same commit.
echo.
echo === clearing the pending list ===
python "..\clear_pending.py"
if errorlevel 1 (
  echo [FAIL] could not clear COMMITS-PENDING.md. Nothing staged, nothing pushed.
  pause & exit /b 1
)

echo.
echo === staging changes ===
git add -A || (echo [FAIL] git add failed & pause & exit /b 1)

REM --- commit; capture whether there was anything to commit ---
git diff --cached --quiet
if %errorlevel%==0 (
  echo [info] nothing to commit - working tree already matches last commit.
  echo        Checking whether local is ahead of origin anyway...
) else (
  git commit -m "update register" || (echo [FAIL] commit failed & pause & exit /b 1)
  echo [ok] commit created.
)

REM --- integrate any remote work BEFORE pushing -------------------------------
REM The current beta workflow validates committed generated files but does not
REM write a compile-bot commit. A rebase still protects against concurrent work
REM reaching main between preflight and push.
REM
REM A conflict here is NOT auto-resolved. Derived files are the likely site and
REM taking the wrong side by hand is exactly what the CI hand-edit guard exists
REM to catch. Abort and let a human look.
echo.
echo === integrating remote work ===
git fetch origin || (echo [FAIL] fetch failed & pause & exit /b 1)
git rebase origin/main
if errorlevel 1 (
  echo.
  echo [ABORT] rebase hit a conflict. Nothing has been pushed.
  echo         Derived files ^(Blueprint\GUIDE.txt, PROCESSES.txt, DIRECTORY.*^) are regenerated
  echo         by CI - if the conflict is one of those, take origin's copy.
  echo         Resolve, then re-run this script. To back out entirely:
  echo             git rebase --abort
  pause & exit /b 1
)
echo [ok] local is on top of origin/main.

echo.
echo === pushing ===
git push
if errorlevel 1 (
  echo.
  echo [FAIL] push did NOT succeed. Nothing was published. Read the error above.
  pause & exit /b 1
)

echo.
echo === verifying against origin ===
git fetch origin >nul 2>&1
git --no-pager status -sb
git rev-parse --short HEAD > "%temp%\_lh.txt"
git rev-parse --short origin/main > "%temp%\_rh.txt"
set /p LH=<"%temp%\_lh.txt"
set /p RH=<"%temp%\_rh.txt"

echo.
if "%LH%"=="%RH%" (
  echo [CONFIRMED] local %LH% == origin/main %RH%.  Push is genuinely live.
  echo.
  echo [beta] GitHub validation will check the committed single-source build.
  echo [beta] Edition sealing, Shift refresh and pCloud sync remain paused.
) else (
  echo [WARNING] local %LH% does NOT match origin/main %RH%.
  echo           Do not assume it published. Investigate before trusting.
)
echo.
echo (Verify with a cache-buster on the raw link - a bare fetch can return a)
echo (body from a superseded commit with no error. Trap 1.)
echo (raw.githubusercontent.com/cliffspab/pipeline-registry/main/Blueprint/DEPLOY/routed/BOOT.md?cb=1)
pause
endlocal
