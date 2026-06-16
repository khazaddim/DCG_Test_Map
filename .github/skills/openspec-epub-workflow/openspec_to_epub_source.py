from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import textwrap
from pathlib import Path
from typing import Iterable

STYLE_CSS = """body {
    font-family: Georgia, serif;
    line-height: 1.6;
    margin: 5%;
    color: #222;
}

h1, h2, h3, h4 {
    page-break-after: avoid;
    color: #1a365d;
}

pre, code {
    font-family: Consolas, monospace;
    white-space: pre-wrap;
}

table {
    border-collapse: collapse;
    width: 100%;
}

th, td {
    border: 1px solid #bbb;
    padding: 0.4em;
    text-align: left;
}

blockquote {
    border-left: 4px solid #999;
    padding-left: 1em;
    color: #555;
}

img {
    max-width: 100%;
    height: auto;
}
"""

FALLBACK_COVER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnY0iQAAAAASUVORK5CYII="
)

IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def find_workspace_root(start: Path) -> Path:
    for path in [start, *start.parents]:
        if (path / "openspec").exists() or (path / "mark2epub.py").exists() or (path / ".git").exists():
            return path
    return start


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "openspec-book"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ensure_cover_image(output_dir: Path, workspace_root: Path, user_cover: str | None) -> str:
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    if user_cover:
        cover_path = Path(user_cover)
        if not cover_path.is_absolute():
            cover_path = workspace_root / cover_path
        if cover_path.exists():
            target = images_dir / cover_path.name
            shutil.copy2(cover_path, target)
            return cover_path.name

    demo_gif = workspace_root / "images" / "demo.gif"
    if demo_gif.exists():
        target = images_dir / demo_gif.name
        shutil.copy2(demo_gif, target)
        return demo_gif.name

    fallback = images_dir / "cover.png"
    fallback.write_bytes(FALLBACK_COVER_PNG)
    return fallback.name


def copy_markdown_images(markdown_text: str, source_dir: Path, output_images_dir: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        raw_path = match.group(1).strip()
        if raw_path.startswith(("http://", "https://", "images/")):
            return match.group(0)

        image_source = (source_dir / raw_path).resolve()
        if image_source.exists() and image_source.is_file():
            target = output_images_dir / image_source.name
            if not target.exists():
                shutil.copy2(image_source, target)
            return match.group(0).replace(raw_path, f"images/{image_source.name}")
        return match.group(0)

    return IMAGE_PATTERN.sub(replace, markdown_text)


def chapter(title: str, body: str, source_note: str | None = None) -> str:
    header = f"# {title}\n\n"
    if source_note:
        header += f"> Source: {source_note}\n\n"
    return header + body.strip() + "\n"


def gather_spec_files(specs_root: Path) -> Iterable[Path]:
    if not specs_root.exists():
        return []
    return sorted(specs_root.rglob("spec.md"))


def relative_note(path: Path, workspace_root: Path) -> str:
    try:
        return str(path.relative_to(workspace_root))
    except ValueError:
        return str(path)


def build_book(
    change_dir: Path,
    output_dir: Path,
    workspace_root: Path,
    title: str | None,
    author: str,
    cover: str | None,
) -> None:
    change_dir = change_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "css").mkdir(exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)

    change_id = change_dir.name
    book_title = title or f"OpenSpec Proposal: {change_id}"
    files_to_include: list[tuple[str, Path | None, str]] = []

    proposal_path = change_dir / "proposal.md"
    tasks_path = change_dir / "tasks.md"
    design_path = change_dir / "design.md"
    specs_root = change_dir / "specs"

    overview = textwrap.dedent(
        f"""
        This EPUB source package was generated from the OpenSpec change folder:

        - Change ID: {change_id}
        - Source directory: {change_dir}

        Included sections are organized as standalone chapters so they can be converted directly with mark2epub.
        """
    ).strip()
    files_to_include.append(("Overview", None, overview))

    if proposal_path.exists():
        files_to_include.append(("Proposal", proposal_path, read_text(proposal_path)))
    if design_path.exists():
        files_to_include.append(("Design", design_path, read_text(design_path)))
    if tasks_path.exists():
        files_to_include.append(("Tasks", tasks_path, read_text(tasks_path)))

    for spec_path in gather_spec_files(specs_root):
        capability = spec_path.parent.name.replace("-", " ").title()
        files_to_include.append((f"Spec - {capability}", spec_path, read_text(spec_path)))

    if len(files_to_include) == 1:
        raise FileNotFoundError("No OpenSpec chapter files were found in the provided change directory.")

    chapter_entries: list[dict[str, str]] = []
    for index, (section_title, source_path, body) in enumerate(files_to_include):
        filename = f"{index:02d}_{slugify(section_title)}.md"
        source_dir = source_path.parent if source_path else change_dir
        adjusted_body = copy_markdown_images(body, source_dir, output_dir / "images")
        note_path = source_path if source_path else change_dir
        source_note = relative_note(note_path, workspace_root)
        (output_dir / filename).write_text(chapter(section_title, adjusted_body, source_note), encoding="utf-8")
        chapter_entries.append({"markdown": filename, "css": ""})

    (output_dir / "css" / "style.css").write_text(STYLE_CSS, encoding="utf-8")
    cover_name = ensure_cover_image(output_dir, workspace_root, cover)

    description = {
        "metadata": {
            "dc:title": book_title,
            "dc:creator": author,
            "dc:language": "en",
            "dc:identifier": slugify(book_title),
        },
        "cover_image": cover_name,
        "default_css": ["style.css"],
        "chapters": chapter_entries,
    }

    (output_dir / "description.json").write_text(json.dumps(description, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a mark2epub-ready source folder from an OpenSpec change proposal."
    )
    parser.add_argument("change_dir", help="Path to an OpenSpec change directory")
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Target folder to generate. Defaults to Controller_change_epub/<change-id>",
    )
    parser.add_argument("--title", help="Optional book title override")
    parser.add_argument("--author", default="OpenSpec Export", help="Book author/creator metadata")
    parser.add_argument("--cover", help="Optional path to a png/jpg/jpeg/gif cover image")
    parser.add_argument("--force", action="store_true", help="Overwrite the output folder if it already exists")
    args = parser.parse_args()

    workspace_root = find_workspace_root(Path.cwd().resolve())
    change_dir = Path(args.change_dir)
    if not change_dir.is_absolute():
        change_dir = workspace_root / change_dir

    if not change_dir.exists():
        raise FileNotFoundError(f"OpenSpec change folder not found: {change_dir}")

    default_output = workspace_root / "Controller_change_epub" / change_dir.name
    output_dir = Path(args.output_dir) if args.output_dir else default_output
    if not output_dir.is_absolute():
        output_dir = workspace_root / output_dir

    if output_dir.exists() and any(output_dir.iterdir()):
        if not args.force:
            raise FileExistsError(
                f"Output directory already exists and is not empty: {output_dir}. Use --force to overwrite."
            )
        shutil.rmtree(output_dir)

    build_book(change_dir, output_dir, workspace_root, args.title, args.author, args.cover)
    print(f"Created mark2epub source folder at: {output_dir}")
    print("Next step: run mark2epub.py against that generated folder.")


if __name__ == "__main__":
    main()
