# SharePoint sync

The Industry Templates SharePoint library holds the planning documents, scenario and scoring
references, evaluation evidence, deployment docs and promoted distributables. It is **not**
tracked by git. Each collaborator syncs the library with the OneDrive client and links it into the
repository as `sharepoint\`, so agents and scripts can use stable `sharepoint\<Industry>\...` paths
while every change syncs to SharePoint for the whole team.

```text
SharePoint: <team site> > <library> > ... > Industry Templates
        ▲  OneDrive sync client (two-way)
        ▼
C:\Users\<you>\<Org>\<Site> - <Library>\...\Industry Templates               (Sync)
C:\Users\<you>\OneDrive - <Org>\<Site> - Industry Templates                  (Add shortcut)
        ▲  directory junction created by `npm run sharepoint:link`
repo\sharepoint\   (gitignored; never committed)
```

Library: get the link from the workstream owner or the team's channel. It is the
`Industry Templates` folder in the team's SharePoint site. The link is not published in this
repository.

Windows only. The link is a directory junction, which needs no administrator rights.

## One-time setup

1. Open the `Industry Templates` folder in SharePoint (link from the workstream owner or the team's
   channel) and choose **Sync** (syncs the library) or **Add shortcut to My files** (syncs only
   `Industry Templates` through your OneDrive). Either works.
2. Keep the files on this device so agents and searches read local files instead of online-only
   placeholders. In File Explorer, right-click the synced folder and choose **Always keep on this
   device** (on Windows 11 it may be under **Show more options**). If the option is missing, run:

   ```powershell
   $lib = "<path to your synced Industry Templates folder>"
   attrib +P -U $lib; attrib +P -U "$lib\*" /S /D
   ```
3. From the repository root:

   ```powershell
   npm install
   npm run sharepoint:link      # finds the synced folder and creates sharepoint\
   npm run sharepoint:doctor    # must end with "SharePoint sync: ready."
   ```

   If detection fails, pass the folder explicitly:

   ```powershell
   npm run sharepoint:link -- --target "<path to your synced Industry Templates folder>"
   ```

## Commands

| Command | What it does |
|---|---|
| `npm run sharepoint:link [-- --target <path>]` | Finds the synced library (OneDrive registry, then known folders), confirms it contains the industry folders, and creates the `sharepoint` junction. Refuses to replace a non-empty plain folder. Replacing an existing link requires `--force true`. |
| `npm run sharepoint:doctor` | Checks the link and its target, that the target is inside a OneDrive sync root, that it is gitignored, OneDrive conflict copies, and online-only files. Exits non-zero when not ready. |
| `npm run sharepoint:unlink` | Removes only the junction. The synced library is never touched. |

## How scripts find the library

`evaluation:archive`, `evaluation:watch`, `evaluation:watch-matrices` and `mos:build` resolve the library root in this order:

1. `--sharepoint-root <path>`
2. `INDUSTRY_TEMPLATES_SHAREPOINT_ROOT`
3. the repository's `sharepoint` link

A plain `sharepoint` folder (not a link) is refused unless passed explicitly with
`--sharepoint-root`, because nothing would sync it to SharePoint.

## Daily use

- Read and edit files under `sharepoint\` like any local folder; OneDrive uploads changes.
- Evaluation archives land directly in the library as
  `sharepoint\<Industry>\<slug>\Evaluation\<version>\` and are visible to everyone once synced.
  Plugins listed in `SHAREPOINT_WAVES` (`scripts\evaluation-workflow.ts`, currently Professional
  Services Waves 1 and 2) use the Retail layout instead:
  `sharepoint\<Industry>\Wave <n>\<Title Case Slug>\Evaluation\v<version>\`.
- After the owner promotes `<slug>-cowork.zip` in a Retail-layout plugin folder, `npm run mos:build`
  writes the derived manifest-1.28 package to its `MOS Package\` folder
  ([release process, Step 6](release-process.md#step-6-publish-and-file-the-evidence)).
- `npm run evaluation:watch-matrices` copies completed workbook/notes pairs from OneDrive's
  `Cowork Plugin Evals\4 - Matrices\2 - Built\` into each matching plugin's `Evaluation Matrices\`
  folder. It keeps the originals, skips identical copies and refuses to overwrite differing files
  ([matrix collection](release-process.md#collect-evaluation-matrices)).
- Close Excel or Word files when done. If two people edit offline at once, OneDrive keeps both as
  `<name>-<COMPUTERNAME>.<ext>`. `sharepoint:doctor` lists these; merge and delete the copy.
- Check the OneDrive tray icon is not paused before archiving evidence.

## Safety rules

- **Never commit the link or its contents.** `.gitignore` ignores `/sharepoint`; `sharepoint:doctor`
  verifies it.
- `git clean -fdX` / `-ffdx` removes only the junction, not the library (verified with Git for
  Windows 2.55). Re-run `npm run sharepoint:link` afterwards.
- Do not delete through the link with recursive tools (`Remove-Item -Recurse sharepoint`,
  `rm -rf sharepoint`) — that deletes the SharePoint files for everyone. Use
  `npm run sharepoint:unlink`.
- Evaluation folders are immutable: never replace a ZIP or report after archiving.
- Recovery: OneDrive keeps version history (right-click > **Version history**) and deleted files go
  to the SharePoint site recycle bin.

## Migrating an existing local mirror

If you previously copied the library into a plain `sharepoint\` folder:

1. Make sure no `evaluation:archive` or `evaluation:watch` run is writing to it.
2. Sync the library (setup steps 1–2).
3. Compare the two trees by content hash. Copy files that exist only in the local mirror into the
   synced folder. For files that differ, decide which version wins; never overwrite blindly.
4. Move the local mirror out of the repository as a backup, for example
   `Move-Item sharepoint "$env:USERPROFILE\industry-templates-sharepoint-backup"`.
5. Run `npm run sharepoint:link` and `npm run sharepoint:doctor`.
6. Delete the backup once you have confirmed everything synced.
