from __future__ import annotations

import argparse
import json
import re
import urllib.request


BASE_URL = "https://olhodomilenio.com"
USER_AGENT = "Mozilla/5.0"


def fetch(url: str, accept: str = "text/html") -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode(errors="ignore")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect public Olho do Milenio page scripts for catalog endpoints.")
    parser.add_argument("--path", default="/en")
    parser.add_argument("--api", help="Read a public API path and print its JSON.")
    args = parser.parse_args()
    if args.api:
        response = fetch(f"https://api.olhodomilenio.com/v1/{args.api.lstrip('/')}", "application/json")
        print(json.dumps(json.loads(response), ensure_ascii=True, indent=2))
        return
    page = fetch(f"{BASE_URL}{args.path}")
    scripts = re.findall(r'<script[^>]+src="([^"]+)', page)
    print(f"scripts={len(scripts)}")
    for source in scripts:
        url = f"{BASE_URL}{source}" if source.startswith("/") else source
        content = fetch(url)
        matches = sorted(
            set(
                re.findall(
                    r".{0,70}(?:/api/|supabase|cards|mods|baseURL|axios\.create|https?://).{0,120}",
                    content,
                    re.IGNORECASE,
                )
            )
        )
        if not matches:
            continue
        print(f"url={url}")
        for match in matches[:30]:
            print(match[:260])


if __name__ == "__main__":
    main()
