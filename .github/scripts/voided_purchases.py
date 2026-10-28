"""Publishes the purchases Google Play reports as refunded, cancelled or charged back.

Reads Google Play's Voided Purchases API for Viking Saga's Idle RPG and adds the SHA-256 of
each voided purchase token to vikingsaga/voided.json. The game downloads that file and takes
back what it granted for any of its own purchases on the list. Only hashes are published, so
the file can't be traced back to a purchase or a player. Tokens are never printed.
"""
import hashlib
import json
import os
import sys

PACKAGE = "com.trickyshadow.vikingsaga"
OUT = "vikingsaga/voided.json"
URL = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE}/purchases/voidedpurchases"


def main() -> int:
    key = os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "").strip()
    if not key:
        print("::notice::PLAY_SERVICE_ACCOUNT_JSON is not set yet; nothing to do.")
        return 0

    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        json.loads(key), scopes=["https://www.googleapis.com/auth/androidpublisher"]
    )
    session = AuthorizedSession(creds)

    try:
        with open(OUT) as f:
            known = set(json.load(f).get("sha256", []))
    except (FileNotFoundError, json.JSONDecodeError):
        known = set()

    found = set()
    page = None
    while True:
        # type=0: in-app products; Google keeps the last 30 days, so earlier hashes are kept from the file.
        params = {"type": 0, "maxResults": 1000}
        if page:
            params["token"] = page
        r = session.get(URL, params=params, timeout=30)
        if r.status_code != 200:
            print(f"::error::Voided purchases request failed with HTTP {r.status_code}.")
            return 1
        body = r.json()
        for v in body.get("voidedPurchases", []):
            token = v.get("purchaseToken")
            if token:
                found.add(hashlib.sha256(token.encode()).hexdigest())
        page = (body.get("tokenPagination") or {}).get("nextPageToken")
        if not page:
            break

    merged = known | found
    print(f"{len(found)} voided purchases in the last 30 days, {len(merged - known)} new, {len(merged)} listed.")
    if merged != known or not os.path.exists(OUT):
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as f:
            json.dump({"sha256": sorted(merged)}, f, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
