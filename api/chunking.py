from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    heading: str
    content: str


def split_markdown(title: str, markdown: str) -> list[Chunk]:
    """Splits a markdown document into one chunk per '## ' section."""
    chunks: list[Chunk] = []
    section = title
    lines: list[str] = []

    def flush() -> None:
        body = "\n".join(lines).strip()
        if body:
            heading = title if section == title else f"{title} > {section}"
            chunks.append(Chunk(heading=heading, content=body))

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            section = line[3:].strip()
            lines.clear()
        elif line.startswith("# "):
            continue
        else:
            lines.append(line)

    flush()
    return chunks