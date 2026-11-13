# TikTok Username Hunter

Phone-friendly website + Python backend. Uses the public-profile parsing approach described by retroul/TikTok-Username-Checker.

## Run
Requires Python 3.10+.
```bash
python app.py
```
Open http://localhost:8000.

## Put it online
1. Create a GitHub repository and upload `app.py`, `requirements.txt`, and `render.yaml`.
2. In Render, create a Web Service connected to that repository.
3. Use start command `python app.py`.
4. Open the HTTPS URL Render provides on your phone.

## Accuracy and responsible use
TikTok has no official public username availability endpoint. This app reads the public profile page's `__UNIVERSAL_DATA_FOR_REHYDRATION__` JSON, looks for `webapp.user-detail.userInfo.user` (taken) or a recognized not-found status code, then repeats a not-found check before showing a name as available.
TikTok may change the page format, rate-limit or block requests, or reserve a username. An available result is not a guarantee; the final test is attempting to change the username in TikTok. This app does not log in, bypass CAPTCHAs, rotate proxies, create accounts, or reserve names. Checks are paced and batches are capped at 40.

Reference: https://github.com/retroul/TikTok-Username-Checker
