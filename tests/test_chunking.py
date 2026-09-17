from api.chunking import split_markdown

DOCUMENT = """# NimbusCRM Pricing

## Starter plan
$12 per user per month.

## Empty section

## Pro plan
$29 per user per month.
"""


def test_split_markdown_creates_one_chunk_per_non_empty_section():
    chunks = split_markdown("NimbusCRM Pricing", DOCUMENT)

    assert [chunk.heading for chunk in chunks] == [
        "NimbusCRM Pricing > Starter plan",
        "NimbusCRM Pricing > Pro plan",
    ]
    assert chunks[1].content == "$29 per user per month."