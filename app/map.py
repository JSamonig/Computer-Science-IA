import urllib.request, json, polyline, urllib.parse
import config as c


def getMap(start, end):
    endpoint = 'https://maps.googleapis.com/maps/api/directions/json?'
    api_key = "AIzaSyCdAYtgS0Fvxcx-pavFn2pZx4G6x2rGDo4"

    origin = urllib.parse.quote_plus(start)
    destination = urllib.parse.quote_plus(end)
    nav_request = 'origin={}&destination={}&key={}'.format(origin, destination, api_key)
    response = urllib.request.urlopen(endpoint + nav_request).read()
    directions = json.loads(response)
    cords = []
    miles, total = 0, 0
    if directions["status"] != "NOT_FOUND":
        try:
            for point in polyline.decode(directions["routes"][0]["overview_polyline"]["points"]):
                cords.append({"lat": point[0], "lng": point[1]})
            miles = int((directions["routes"][0]["legs"][0]["distance"]["value"] / 1000) / 1.6)
            total = miles * 0.45
        except:
            cords = [{}]
            miles, total = 0, 0
    return [cords, miles, total]
