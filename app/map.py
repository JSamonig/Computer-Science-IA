import urllib.request
import urllib.parse
import json
import polyline
import config as c


def get_map(start, end):
    """
    :param start: start location
    :param end: end location
    :return: [cords, miles, total, status]
    """
    if "%" not in start:  # if not url encoded
        start = urllib.parse.quote_plus(start)
    if "%" not in end:
        end = urllib.parse.quote_plus(end)
    endpoint = "https://maps.googleapis.com/maps/api/directions/json?"
    api_key = c.Config.GOOGLEMAPS_KEY
    nav_request = "origin={}&destination={}&key={}".format(start, end, api_key)
    response = urllib.request.urlopen(endpoint + nav_request).read()
    directions = json.loads(response)
    cords = []
    miles, total = (
        0,
        0,
    )
    status = directions["status"]
    if status == "OK":
        for point in polyline.decode(
            directions["routes"][0]["overview_polyline"]["points"]
        ):
            cords.append(
                {"lat": point[0], "lng": point[1]}
            )  # get polyline (for map route)
        miles = int(
            (directions["routes"][0]["legs"][0]["distance"]["value"] / 1000) / 1.6
        )  # get mileage
        total = round(miles * c.Config.MILEAGE_RATE, 2)  # get cost
    else:
        cords = None
    return [cords, miles, total, status]
