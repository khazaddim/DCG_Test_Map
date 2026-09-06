# Agents

This repository includes local skills for GitHub Copilot coding agents.

## Available Skills

- `dcg-animation-patterns`: DearCyGui 2D animation, coordinate systems, camera control, DrawStream, and edge-band panning patterns.
- `dcg-perspective-map-patterns`: Perspective and rotating game maps, centered homography transforms, inverse projection, clipping, camera tracking, and atomic front/back drawing buffers that prevent rebuild flicker.
- `scene-class-documentation`: Retained 3D scene-authoring class chooser for demos 11, 14, and 15, including limits, safe fallbacks, and supporting material/projection notes.
- `openspec-epub-workflow`: Generate review-ready markdown book folders and build EPUB files from OpenSpec changes, project files, or diffs using `mark2epub.py`.

## Skill Paths

- `.github/skills/animation_patterns/SKILL.md`
- `.github/skills/perspective_map_patterns/SKILL.md`
- `.github/skills/scene-class-documentation/SKILL.md`
- `.github/skills/openspec-epub-workflow/SKILL.md`

## EPUB Workflow Assets

- Helper script: `.github/skills/openspec-epub-workflow/openspec_to_epub_source.py`
- Converter script: `mark2epub.py`

## Usage Notes

- Prefer the workspace Python interpreter when running helper scripts.
- Keep generated EPUB outputs and generated source folders out of version control unless explicitly requested.
