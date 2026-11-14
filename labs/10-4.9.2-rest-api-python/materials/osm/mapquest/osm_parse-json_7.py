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
    # Nominatim: place name -> "lon,lat" (OSRM expects the longitude first), None if not found
    time.sleep(1)   # Nominatim usage policy: at most 1 request per second
    url = geocode_api + urllib.parse.urlencode({"format": "json", "limit": 1, "q": location})
    print("Geocoding URL: " + url)
    replydata = requests.get(url, headers=headers, timeout=20)
    replydata.raise_for_status()   # HTTP 4xx/5xx (for example 403 or 429) raises an exception
    places = replydata.json()
    if len(places) == 0:           # Nominatim answers [] when it knows no such place
        return None
    return places[0]["lon"] + "," + places[0]["lat"]


def narrative(step):
    # OSRM sends no ready-made text: build it from the maneuver type, modifier and road name
    kind = step["maneuver"]["type"]
    modifier = step["maneuver"].get("modifier", "straight")
    side = ""
    if "left" in modifier:
        side = "left"
    elif "right" in modifier:
        side = "right"
    road = step.get("name", "")
    if step.get("ref") and step["ref"] != road:    # road number, e.g. "US 50" or "I 95"
        road = road + " (" + step["ref"] + ")" if road else step["ref"]
    onto = " onto " + road if road else ""
    if step.get("destinations"):                   # text of the road signs
        onto = onto + " toward " + step["destinations"]
    if kind == "depart":
        compass = ["north", "northeast", "east", "southeast",
                   "south", "southwest", "west", "northwest"]
        heading = compass[int((step["maneuver"]["bearing_after"] + 22.5) // 45) % 8]
        return "Start out going " + heading + (" on " + road if road else "")
    if kind == "arrive":
        return "You have arrived at your destination" + (", on the " + side if side else "")
    if step.get("mode") == "ferry":
        return "Take the ferry" + onto
    if kind in ("roundabout", "rotary"):
        return "Enter the roundabout and take exit " + str(step["maneuver"].get("exit", 1)) + onto
    if kind in ("exit roundabout", "exit rotary"):
        return "Exit the roundabout" + onto
    if kind == "fork":
        return "Keep " + (side or "straight") + " at the fork" + onto
    if kind == "merge":
        return "Merge" + onto
    if kind == "on ramp":
        return "Take the ramp" + (" on the " + side if side else "") + onto
    if kind == "off ramp":
        return "Take the exit" + (" on the " + side if side else "") + onto
    if kind == "end of road":
        return "At the end of the road turn " + (side or "straight") + onto
    if modifier == "uturn":
        return "Make a U-turn" + onto
    if modifier == "straight":
        return "Continue" + onto
    if modifier.startswith("slight"):
        return "Bear " + side + onto
    return "Turn " + modifier + onto


while True:
    orig = input("Starting Location: ")
    if orig == "quit" or orig == "q":
        break
    dest = input("Destination: ")
    if dest == "quit" or dest == "q":
        break
    if orig == "" or dest == "":
        print("**********************************************")
        print("Missing an entry for one or both locations.")
        print("**********************************************\n")
        continue
    try:
        orig_point = geocode(orig)
        dest_point = geocode(dest)
        if orig_point is None or dest_point is None:
            print("**********************************************")
            if orig_point is None:
                print("Unknown location: " + orig + " (Nominatim found no such place)")
            if dest_point is None:
                print("Unknown location: " + dest + " (Nominatim found no such place)")
            print("**********************************************\n")
            continue
        points = orig_point + ";" + dest_point
        url = main_api + points + "?" + urllib.parse.urlencode(route_options, safe=";")
        print("URL: " + url)
        replydata = requests.get(url, headers=headers, timeout=20)
        if replydata.status_code not in (200, 400):   # OSRM sends its own errors with HTTP 400
            replydata.raise_for_status()
        json_data = replydata.json()
    except (requests.exceptions.RequestException, ValueError) as error:
        print("**********************************************")
        print("Request failed: " + str(error))
        print("**********************************************\n")
        continue
    json_status = json_data.get("code", "unknown")
    if json_status == "Ok":
        print("API Status: " + json_status + " = A successful route call.\n")
        # OSRM gives the duration in seconds and the distance in meters
        secs = round(json_data["routes"][0]["duration"])
        trip_time = "{:02d}:{:02d}:{:02d}".format(secs // 3600, secs // 60 % 60, secs % 60)
        km = json_data["routes"][0]["distance"] / 1000
        print("=============================================")
        print("Directions from " + orig + " to " + dest)
        print("Trip Duration:   " + trip_time)
        print("Kilometers:      " + "{:.2f}".format(km))
        print("Miles:           " + "{:.2f}".format(km / 1.61))
        print("Fuel Used:       not provided by OSRM")
        print("=============================================")
        for each in json_data["routes"][0]["legs"][0]["steps"]:
            print(narrative(each) + " (" + "{:.2f}".format(each["distance"] / 1000) + " km)")
        print("=============================================\n")
    elif json_status == "NoSegment":
        print("**********************************************")
        print("Status Code: " + json_status + "; No road route between the locations.")
        print("OSRM: " + json_data.get("message", "") + " (0 = start, 1 = destination)")
        print("**********************************************\n")
    elif json_status == "NoRoute":
        print("**********************************************")
        print("Status Code: " + json_status + "; No route found between the locations.")
        print("**********************************************\n")
    else:
        print("************************************************************************")
        print("For Status Code: " + json_status + "; Refer to:")
        print("https://project-osrm.org/docs/v5.24.0/api/#responses")
        print("************************************************************************\n")
