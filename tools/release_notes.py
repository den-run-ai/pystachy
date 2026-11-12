"""Check release notes and render them for GitHub releases.

GitHub renders every newline in a release body as a line break, so notes wrapped
for review in docs/releases/VERSION.md must be unwrapped before publication.

  check FILE...       enforce the release-note rules of docs/writing.md
  render FILE ...     unwrap the notes and append the generated release assets
  refresh ...         rewrite a published body above its generated release assets

render and refresh write to --output, or to stdout without it.
"""

import argparse
import difflib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "den-run-ai/pystachy"
SEMVER = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?")
ASSETS = "## Release assets"
PARAGRAPH_WORDS = 80
TOTAL_WORDS = 700
PRERELEASE = ("As a prerelease, this version does not move GitHub's latest release or "
              "Docker's `latest` tag.")

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]|$)")
LIST_ITEM = re.compile(r"^ *(?:[-*+]|[0-9]{1,9}[.)])(?:[ \t]|$)")
RULE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
HTML = re.compile(r"^ {0,3}<(?:!--|/?[A-Za-z][A-Za-z0-9-]*(?:[\s/>]|$))")
REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:")
INLINE_LINK = re.compile(r"!?\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*<?([^)\s>]*)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE_TARGET = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.M)
AUTOLINK = re.compile(r"<((?:https?|ftp)://[^>\s]+)>")
CODE_SPAN = re.compile(r"(`+)(.+?)\1")
UNPINNED = re.compile(r"^https://github\.com/[^/]+/[^/]+/(?:blob|tree|raw|edit)/(?:main|master|HEAD)(?:/|$)")
PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|FIXME)\b")


def _hard_break(line):
    return line.endswith("  ") or line.rstrip().endswith("\\")


def blocks(text):
    """Yield (kind, lines) for top-level Markdown blocks, enough for release notes.

    Kinds: fence, blank, heading, table, rule, html, reference, code, text. A text block
    is one paragraph, list item or quote line together with its soft-wrapped continuations.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    fence = None
    previous = "blank"
    in_list = False
    current = None
    for line in lines:
        if fence is not None:
            current[1].append(line)
            marker = FENCE.match(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) \
                    and not line[marker.end():].strip():
                fence = None
                yield current
                current, previous = None, "fence"
            continue
        if current is not None and current[0] == "text":
            continues = (line.strip() and not FENCE.match(line) and not HEADING.match(line)
                         and not LIST_ITEM.match(line) and not RULE.match(line)
                         and not HTML.match(line) and not line.lstrip().startswith(("|", ">"))
                         and not _hard_break(current[1][-1]))
            if continues:
                current[1].append(line)
                continue
            yield current
            current = None
        marker = FENCE.match(line)
        if marker:
            fence = marker[1]
            current = ["fence", [line]]
            continue
        stripped = line.strip()
        if not stripped:
            kind = "blank"
        elif HEADING.match(line):
            kind, in_list = "heading", False
        elif stripped.startswith("|"):
            kind, in_list = "table", False
        elif RULE.match(line):
            kind, in_list = "rule", False
        elif HTML.match(line):
            kind = "html"
        elif REFERENCE.match(line):
            kind = "reference"
        elif LIST_ITEM.match(line):
            kind, in_list = "text", True
        elif previous in ("blank", "code") and not in_list and line.startswith(("    ", "\t")):
            kind = "code"  # an indented code block runs until a less indented line
        else:
            kind = "text"
            if previous == "blank" and not line.startswith((" ", "\t")):
                in_list = False
        if kind == "text":
            current = ["text", [line]]
        else:
            yield [kind, [line]]
        previous = kind
    if current is not None:
        yield current


def unwrap(text):
    """Join soft-wrapped lines in paragraphs, list items and quotes; keep other blocks."""
    out = []
    for kind, lines in blocks(text):
        if kind != "text":
            out.extend(lines)
            continue
        first = lines[0].rstrip() if not _hard_break(lines[0]) else lines[0]
        parts = [first] + [line.strip() for line in lines[1:]]
        if len(lines) > 1 and _hard_break(lines[-1]):
            parts[-1] = lines[-1].lstrip()
        out.append(" ".join(parts) if len(parts) > 1 else parts[0])
    return "\n".join(out)


def plain_words(text):
    """Count rendered words: link text without URLs, code spans as their text."""
    text = INLINE_LINK.sub(lambda match: match[1], text)
    text = AUTOLINK.sub("link", text)
    text = CODE_SPAN.sub(lambda match: match[2], text)
    text = re.sub(r"^\s*(?:[-*+]|[0-9]{1,9}[.)])\s+", "", text)
    return sum(1 for word in text.split() if re.search(r"\w", word))


def links(text):
    """Return link targets outside code: inline, reference definitions and autolinks."""
    found = []
    for kind, lines in blocks(text):
        if kind in ("fence", "code"):
            continue
        chunk = CODE_SPAN.sub("", ("\n" if kind == "reference" else " ").join(lines))
        found += [match[2] for match in INLINE_LINK.finditer(chunk)]
        found += REFERENCE_TARGET.findall(chunk)
        found += AUTOLINK.findall(chunk)
    return found


def check_text(text):
    """Return actionable errors for release notes text."""
    errors = []
    parsed = list(blocks(text))
    content = [(kind, lines) for kind, lines in parsed if kind != "blank"]
    if not content:
        return ["Write the release notes; the file is empty."]
    first_kind, first_lines = content[0]
    if first_kind != "text" or LIST_ITEM.match(first_lines[0]) or first_lines[0].lstrip().startswith(">"):
        errors.append("Open with a summary paragraph, not a heading, list, table or code block.")
    total = 0
    for kind, lines in content:
        if kind == "heading":
            level = len(HEADING.match(lines[0])[1])
            title = lines[0].strip().lstrip("#").strip()
            if level == 1:
                errors.append(f"Remove the top-level title '{title}'; the workflow titles the release.")
            elif level > 3:
                errors.append(f"Use a ## or ### heading for '{title}'.")
            if title.lower() == ASSETS[3:].lower():
                errors.append("Remove the 'Release assets' section; the workflow generates it.")
            total += plain_words(title)
        elif kind == "text":
            paragraph = " ".join(line.strip() for line in lines)
            words = plain_words(paragraph)
            total += words
            if words > PARAGRAPH_WORDS:
                errors.append(f"Split the {words}-word paragraph or list item starting "
                              f"'{paragraph[:48]}...' (limit {PARAGRAPH_WORDS} words).")
        elif kind == "html" and not lines[0].lstrip().startswith("<!--"):
            errors.append("Use Markdown instead of raw HTML: " + lines[0].strip()[:60])
    if total > TOTAL_WORDS:
        errors.append(f"Shorten the notes to {TOTAL_WORDS} words outside tables and code (now {total}); "
                      "link details instead of repeating them.")
    for target in links(text):
        if not re.match(r"https://", target):
            errors.append(f"Use an absolute https link instead of '{target}'; GitHub shows the notes "
                          "outside the repository.")
        elif UNPINNED.match(target):
            errors.append(f"Pin '{target}' to a tag or commit; branch links change after release.")
    prose = " ".join(" ".join(lines) for kind, lines in parsed if kind not in ("fence", "code"))
    if PLACEHOLDER.search(CODE_SPAN.sub("", prose)):
        errors.append("Resolve TODO, TBD and FIXME placeholders.")
    return errors


def assets(version, commit, repository, image, prerelease):
    """Return the generated section that follows the curated notes."""
    if not SEMVER.fullmatch(version):
        raise ValueError(f"not a v-prefixed semantic version: {version!r}")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"not a full commit SHA: {commit!r}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError(f"not an owner/name repository: {repository!r}")
    component = r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*"  # Docker's repository name grammar
    if not re.fullmatch(rf"{component}(?:/{component})+", image):
        raise ValueError(f"not a Docker image name: {image!r}")
    base = f"https://github.com/{repository}"
    lines = [
        ASSETS, "",
        "Native compiler archives for Linux x86-64/AArch64 and macOS arm64/x86-64 are attached "
        "below, with their SHA-256 checksums in `SHA256SUMS`. They require LLVM 18 on Linux or "
        f"LLVM 20 on macOS; see the [installation instructions]({base}/blob/{commit}/docs/install.md).",
        "",
        f"Docker image: `{image}:{version}` for linux/amd64 and linux/arm64, with LLVM 18 included.",
        "",
    ]
    if prerelease:
        lines += [PRERELEASE, ""]
    lines += [f"Source commit: [`{commit}`]({base}/commit/{commit}).", ""]
    return "\n".join(lines)


def render(notes, version, commit, repository, image, prerelease):
    errors = check_text(notes)
    if errors:
        raise ValueError("release notes do not meet docs/writing.md:\n  " + "\n  ".join(errors))
    return unwrap(notes).strip("\n") + "\n\n" + assets(version, commit, repository, image, prerelease)


def refresh(current, notes=None, prerelease=False):
    """Replace the curated part of a published body, keeping its generated assets section.

    Curated notes no longer state prerelease status, so it joins the kept section when
    missing. Without notes, only unwrap the published text.
    """
    current = current.replace("\r\n", "\n").replace("\r", "\n")
    match = re.search(r"^## Release assets[ \t]*$", current, re.M)
    if not match:
        raise ValueError("the published body has no '## Release assets' section; edit it by hand")
    if notes is not None:
        errors = check_text(notes)
        if errors:
            raise ValueError("release notes do not meet docs/writing.md:\n  " + "\n  ".join(errors))
    curated = current[:match.start()] if notes is None else notes
    generated = unwrap(current[match.start():]).strip("\n")
    if notes is not None and prerelease and "prerelease" not in generated.lower():
        generated += "\n\n" + PRERELEASE
    return unwrap(curated).strip("\n") + "\n\n" + generated + "\n"


def write(text, output):
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="check notes files")
    check.add_argument("files", nargs="+")
    build = commands.add_parser("render", help="render notes and release assets for a new release")
    build.add_argument("file")
    build.add_argument("--version", required=True)
    build.add_argument("--commit", required=True)
    build.add_argument("--repository", required=True)
    build.add_argument("--image", required=True)
    build.add_argument("--prerelease", required=True, choices=("true", "false"))
    build.add_argument("--output")
    update = commands.add_parser("refresh", help="rewrite a published release body")
    update.add_argument("--version", required=True)
    update.add_argument("--current", required=True,
                        help="JSON from: gh release view VERSION --json body,isDraft,isPrerelease,tagName")
    update.add_argument("--source", choices=("notes", "reflow"), default="notes",
                        help="curated notes from docs/releases, or the published text unwrapped")
    update.add_argument("--output")
    args = parser.parse_args(argv)

    if args.command == "check":
        status = 0
        for name in args.files:
            errors = check_text(Path(name).read_text(encoding="utf-8"))
            for error in errors:
                print(f"{name}: {error}", file=sys.stderr)
            status |= bool(errors)
        if not status:
            print("release notes: " + ", ".join(args.files) + " meet docs/writing.md")
        return status

    try:
        if args.command == "render":
            notes = Path(args.file).read_text(encoding="utf-8")
            write(render(notes, args.version, args.commit, args.repository, args.image,
                         args.prerelease == "true"), args.output)
            return 0
        if not SEMVER.fullmatch(args.version):
            raise ValueError(f"not a v-prefixed semantic version: {args.version!r}")
        current = json.loads(Path(args.current).read_text(encoding="utf-8"))
        if current.get("tagName") != args.version or current.get("isDraft") is not False:
            raise ValueError(f"{args.version} is not a published release; the Release workflow "
                             "writes notes for drafts")
        notes = None
        if args.source == "notes":
            notes = (ROOT / "docs/releases" / f"{args.version}.md").read_text(encoding="utf-8")
        body = refresh(current.get("body") or "", notes, current.get("isPrerelease") is True)
        sys.stderr.writelines(difflib.unified_diff(
            (current.get("body") or "").replace("\r\n", "\n").splitlines(True), body.splitlines(True),
            "published", "refreshed"))
        write(body, args.output)
        return 0
    except (OSError, ValueError) as error:
        print(f"release notes: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
