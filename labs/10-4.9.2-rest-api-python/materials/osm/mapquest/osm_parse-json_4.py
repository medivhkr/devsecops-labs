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


def geocode(location):
    # Nominatim: place name -> "lon,lat" (OSRM expects the longitude first)
    time.sleep(1)   # Nominatim usage policy: at most 1 request per second
    url = geocode_api + urllib.parse.urlencode({"format": "json", "limit": 1, "q": location})
    print("Geocoding URL: " + url)
    place = requests.get(url, headers=headers, timeout=20).json()[0]
    return place["lon"] + "," + place["lat"]


while True:
    orig = input("Starting Location: ")
    if orig == "quit" or orig == "q":
        break
    dest = input("Destination: ")
    if dest == "quit" or dest == "q":
        break
    points = geocode(orig) + ";" + geocode(dest)
    url = main_api + points + "?" + urllib.parse.urlencode(route_options, safe=";")
    print("URL: " + url)
    json_data = requests.get(url, headers=headers, timeout=20).json()
    json_status = json_data["code"]
    if json_status == "Ok":
        print("API Status: " + json_status + " = A successful route call.\n")
