#!/usr/bin/env python3
"""
Small helper to query Railway's backboard GraphQL API.

Usage:
  RAILWAY_API_TOKEN=<token> python3 scripts/railway_graphql.py

It will run the "me { workspaces { projects { edges { node { id name } } } } }" query
that Railway support provided, and pretty-print the JSON response.
"""
import os
import sys
import json
import requests
from dotenv import load_dotenv


DEFAULT_URL = "https://backboard.railway.app/graphql/v2"


def query_railway_graphql(query: str, token: str | None, url: str = DEFAULT_URL):
    if not token:
        raise RuntimeError("RAILWAY API token missing. Set RAILWAY_API_TOKEN in the environment.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json={"query": query}, timeout=30)
    try:
        data = resp.json()
    except Exception:
        resp.raise_for_status()
    return resp.status_code, data


RAILWAY_ME_QUERY = """query me {
  me {
    workspaces {
      projects {
        edges {
          node {
            id
            name
          }
        }
      }
    }
  }
}
"""


def main():
    load_dotenv(override=False)
    token = os.environ.get("RAILWAY_API_TOKEN") or os.environ.get("RAILWAY_PAT")
    url = os.environ.get("RAILWAY_GRAPHQL_URL", DEFAULT_URL)
    try:
        status, data = query_railway_graphql(RAILWAY_ME_QUERY, token, url=url)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)

    print(f"HTTP {status}")
    print(json.dumps(data, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
