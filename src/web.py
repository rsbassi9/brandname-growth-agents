import requests
from bs4 import BeautifulSoup


def fetch_website_summary(url: str) -> str:
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "brandname-growth-agents/0.1"})
        response.raise_for_status()
    except requests.RequestException as exc:
        return f"Website fetch unavailable: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else "No title found"
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = description_tag.get("content", "").strip() if description_tag else "No meta description found"
    headings = [heading.get_text(" ", strip=True) for heading in soup.find_all(["h1", "h2"])][:12]

    return "\n".join(
        [
            f"URL: {url}",
            f"Title: {title}",
            f"Meta description: {description}",
            "Headings:",
            *[f"- {heading}" for heading in headings],
        ]
    )
