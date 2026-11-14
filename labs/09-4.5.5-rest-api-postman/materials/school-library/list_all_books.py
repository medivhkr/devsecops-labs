#!/usr/bin/env python3
"""Read every book of the School Library the same way the web page does.

The page http://library.demo.local/ starts with GET /api/v1/books and follows the
'Link: <...>; rel="next"' response header page by page (10 books per page). When the
API answers 429 Too Many Requests it waits Retry-After seconds and repeats the call.
"""
import time

import requests

url = "http://library.demo.local/api/v1/books"
books = []
while url:
    r = requests.get(url, headers={"accept": "application/json"}, timeout=10)
    if r.status_code == 429:
        wait = int(r.headers["Retry-After"])
        print(f"GET {url} -> 429 {r.json()['error']} Loading in {wait} seconds ...")
        time.sleep(wait)
        continue
    r.raise_for_status()
    page = r.json()
    books += page
    print(f"GET {url} -> {r.status_code}, {len(page)} books")
    url = r.links.get("next", {}).get("url")

print()
print(f"{'Book ID':<8} {'Title':<42} Author")
shown = books if len(books) <= 10 else books[:6] + [None] + books[-3:]
for book in shown:
    if book is None:
        print("...")
    else:
        print(f"{book['id']:<8} {book['title'][:42]:<42} {book['author']}")
ids = sorted(book["id"] for book in books)
print(f"Total books: {len(books)} (id {ids[0]}..{ids[-1]})")
