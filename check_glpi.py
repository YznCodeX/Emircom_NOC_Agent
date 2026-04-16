import requests

GLPI_URL  = "http://localhost/api.php/v1"
APP_TOKEN = "Yebjkwq1QLMpq1yKkRfvNPwMvEKIMHelrN5smCke"
USER_TOKEN= "GmPD9nDa3C9nBj0KWbm6cx927XtpmW7tsDlvRhQE"

auth = requests.get(
    f"{GLPI_URL}/initSession",
    headers={"Content-Type":"application/json","App-Token":APP_TOKEN,"Authorization":f"user_token {USER_TOKEN}"},
    timeout=5
)
print("Auth status:", auth.status_code)
session_token = auth.json().get("session_token")
print("Session:", session_token)

headers = {"Content-Type":"application/json","Session-Token":session_token,"App-Token":APP_TOKEN}

r = requests.get(f"{GLPI_URL}/Ticket", headers=headers,
                 params={"range":"0-15","sort":"id","order":"DESC"}, timeout=5)
print("\nLatest GLPI tickets:")
for t in r.json():
    print(f"  #{t['id']} | {t['name']} | status={t['status']}")
