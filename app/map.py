import urllib.request
import urllib.parse
import json
import polyline
import config as c


def getMap(start, end):
    print("%" not in start)
    if "%" not in start:
        start = urllib.parse.quote_plus(start)
    if "%" not in end:
        end = urllib.parse.quote_plus(end)
    print([start, end])
    endpoint = 'https://maps.googleapis.com/maps/api/directions/json?'
    api_key = c.Config.GOOGLEMAPS_KEY
    nav_request = 'origin={}&destination={}&key={}'.format(start, end, api_key)
    response = urllib.request.urlopen(endpoint + nav_request).read()
    directions = json.loads(response)
    cords = []
    miles, total = 0, 0,
    status = directions["status"]
    if status == "OK":
        for point in polyline.decode(directions["routes"][0]["overview_polyline"]["points"]):
            cords.append({"lat": point[0], "lng": point[1]})
        miles = int((directions["routes"][0]["legs"][0]["distance"]["value"] / 1000) / 1.6)
        total = miles * 0.45
    else:
        cords = None
    return [cords, miles, total, status]
