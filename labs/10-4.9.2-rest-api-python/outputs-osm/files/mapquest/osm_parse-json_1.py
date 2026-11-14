import time
import urllib.parse
import requests

geocode_api = "https://nominatim.openstreetmap.org/search?"
main_api = "https://router.project-osrm.org/route/v1/driving/"
# Nominatim usage policy: the User-Agent header must name the application (no API key needed)
headers = {"User-Agent": "DEVASC-lab-4.9.2 student script (education)"}
# OSRM options: overview=false - no route geometry, steps=true - turn-by-turn steps,
# radiuses - snap each point to a road at most 50 km away ("50000;50000", one value per point)
route_options = {"overview": "false", "steps": "true", "radiuses": "50000;50000"}
orig = "Washington, D.C."
dest = "Baltimore, Md"


def geocode(location):
    # Nominatim: place name -> "lon,lat" (OSRM expects the longitude first)
    time.sleep(1)   # Nominatim usage policy: at most 1 request per second
    url = geocode_api + urllib.parse.urlencode({"format": "json", "limit": 1, "q": location})
    print("Geocoding URL: " + url)
    replydata = requests.get(url, headers=headers, timeout=20)
    print("HTTP Status: " + str(replydata.status_code))
    place = replydata.json()[0]
    return place["lon"] + "," + place["lat"]


points = geocode(orig) + ";" + geocode(dest)
url = main_api + points + "?" + urllib.parse.urlencode(route_options, safe=";")
print("URL: " + url)
replydata = requests.get(url, headers=headers, timeout=20)
print("HTTP Status: " + str(replydata.status_code))

json_data = replydata.json()
print(json_data)
