---
name: openspec-epub-workflow
description: "Use when: creating EPUBs, ereader review packages, or markdown book folders from OpenSpec proposals, project files, commit ranges, git diffs, change summaries, specs, design.md, proposal.md, or tasks.md. Helps summarize project changes for later review on an ereader using mark2epub."
---

# Review EPUB Workflow

Use this skill when the user wants to turn project material into an EPUB or a mark2epub-ready source folder for ereader review. The source can be an OpenSpec change proposal, selected files, project notes, commit history, git diffs, or a summarized review of recent work.

## When To Use

Use this workflow for requests like:

- "make an EPUB from this OpenSpec proposal"
- "summarize this change for ereader review"
- "turn proposal.md, design.md, tasks.md, and specs into chapters"
- "make an EPUB from these files"
- "summarize the commits on this branch as an ebook"
- "package this PR diff for ereader review"
- "create review chapters from the files I changed"
- "create a markdown folder for mark2epub"
- "package project changes as an ebook"

## Expected Inputs

The source may be one of these:

- An OpenSpec change directory.
- A list of files or folders to summarize.
- A git commit range, branch comparison, or PR diff.
- Existing markdown notes that should be assembled into chapters.

An OpenSpec source usually has this shape:

```text
openspec/changes/<change-id>/
├── proposal.md
├── tasks.md
├── design.md              # optional
└── specs/
    └── <capability>/
        └── spec.md
```

The bundled helper script is:

```text
.github/skills/openspec-epub-workflow/openspec_to_epub_source.py
```

The EPUB converter script is:

```text
mark2epub.py
```

## Workflow

1. Identify the source material and intended review scope.
2. Choose the chapter structure before generating files.
3. For OpenSpec changes, generate a mark2epub-ready source folder with `openspec_to_epub_source.py`.
4. For files, commits, or diffs, create concise markdown chapters first, then assemble them into the same mark2epub folder structure.
5. Build the final EPUB with `mark2epub.py`.
6. Verify the EPUB file exists and report its path.

## Chapter Patterns

Use the source type to decide the chapter layout.

For OpenSpec changes:

- Overview
- Proposal
- Design, if present
- Tasks
- One chapter per spec capability

For selected files:

- Overview of the review purpose
- One chapter per major file or related file group
- Notes on important APIs, data flow, risks, and follow-up questions

For commits or branch diffs:

- Overview of the commit range or branch comparison
- Change summary grouped by subsystem
- Notable commits or milestones
- Files changed and behavioral impact
- Risks, tests, and follow-up work

For mixed project review:

- Executive overview
- Background/context
- Implementation details
- Review notes
- Appendix with raw references or source excerpts when useful

## Commands

For OpenSpec changes, from the repository root, generate the source folder:

```powershell
c:/Chris/DearCyGui/.venv/Scripts/python.exe .\.github\skills\openspec-epub-workflow\openspec_to_epub_source.py openspec/changes/add-multi-controller-support --author "Chris" --force
```

Then build the EPUB:

```powershell
c:/Chris/DearCyGui/.venv/Scripts/python.exe .\mark2epub.py .\Controller_change_epub\add-multi-controller-support .\Controller_change_epub\add-multi-controller-support.epub
```

For a different proposal, replace `add-multi-controller-support` with the OpenSpec change ID.

For files, commits, and diffs, the agent should first create markdown chapter files in the target source folder, then create `description.json`, `css/style.css`, and `images/` using the same output format below. Keep generated summaries concise enough to be pleasant on an ereader, and preserve links or source paths for later lookup.

Useful git commands for gathering source material include:

```powershell
git log --oneline --stat <base>..<head>
git diff --stat <base>..<head>
git diff --name-only <base>..<head>
git show --stat <commit>
```

## Output Format

The generated source folder should contain:

```text
Controller_change_epub/<change-id>/
├── css/
│   └── style.css
├── images/
├── 00_overview.md
├── 01_proposal.md
├── 02_design.md          # only when design.md exists
├── 03_tasks.md
├── 04_spec-<capability>.md
└── description.json
```

The final EPUB should normally be written to:

```text
Controller_change_epub/<change-id>.epub
```

## Quality Checks

Before finishing, verify:

- `description.json` exists in the generated source folder.
- The generated folder has `css/` and `images/` subfolders.
- The chapter markdown files are numbered in reading order.
- `mark2epub.py` prints `eBook creation complete`.
- The final `.epub` file exists.

## Portability Notes

For other repositories, copy this skill folder or recreate the helper script and keep the same input/output contract. If the Python virtual environment path differs, use that repo's configured Python interpreter instead of the hard-coded example path.

Keep generated EPUBs and generated source folders ignored by Git unless the user explicitly wants to commit them.
