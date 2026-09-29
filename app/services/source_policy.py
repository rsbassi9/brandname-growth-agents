"""Separate research evidence from production photos before downloading bytes.

Classification is a conservative filter, not proof of copyright ownership.
Unclassified material needs curation; inspiration never becomes a product input.
"""

import re

PRODUCTION_BUCKETS = frozenset({
    "Store Products", "Shoot Photos", "Photoshoot / Campaign", "Process / Studio", "Design Assets",
})
RESEARCH_LABEL = re.compile(r"asrv|competitor|inspiration|reference|mood.?board", re.IGNORECASE)


def is_production_image(item: dict) -> bool:
    labels = " ".join(str(item.get(key, "")) for key in ("name", "folderPath", "creativeBucket"))
    return (
        str(item.get("mimeType", "")).startswith("image/")
        and item.get("creativeBucket") in PRODUCTION_BUCKETS
        and not RESEARCH_LABEL.search(labels)
    )
