import urllib.parse
import requests
import csv
import json
from flask import Flask, jsonify, request
from sklearn.neighbors import NearestNeighbors
import numpy as np
from flask_cors import CORS, cross_origin
from collections import OrderedDict

app = Flask(__name__)
CORS(app)

data = []
data1 = []
data2 = []

locations = "data.txt"
jsonFile = 'data.json'
locations1 = "Hospital.csv"
locations2 = 'data2.csv'

with open(locations, "r") as file, open(locations1, "r") as file1, open(locations2, "r") as file2:
    reader = csv.DictReader(file)
    reader1 = csv.DictReader(file1)
    reader2 = csv.DictReader(file2)

    for line in reader:
        data.append(line)
    for line in reader1:
        data1.append(line)
    for line in reader2:
        data2.append(line)

with open(jsonFile, 'w') as inFile:
    json.dump(data + data1 + data2, inFile)

locations_data = OrderedDict({"restaurant": [], "Hospital": [], "gasStation": []})

# New API key
API_KEY = "AIzaSyB3j2YPg-HifhSfwmd8vuzxTzc5tap-PdY"

def get_photos(name):
    base_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    parameters = {
        'key': API_KEY,
        'input': name,
        'inputtype': 'textquery',
        'fields': 'photos,formatted_address,name,rating,opening_hours,geometry'
    }

    response = requests.get(base_url, params=parameters)
    jformat = response.json()

    print("************************************")
    # Add logging to inspect the response
    print(f"Requesting photos for: {name}")
    print(f"API Response: {json.dumps(jformat, indent=2)}")

    try:
        if 'candidates' in jformat and len(jformat['candidates']) > 0:
            place_id = jformat['candidates']

            with open("place_id.txt", "w") as filee:
                filee.write(json.dumps(place_id, indent=2))

            if place_id and place_id[0].get('photos'):
                photo_reference = place_id[0]['photos'][0].get('photo_reference')

                if photo_reference:
                    base_url1 = "https://maps.googleapis.com/maps/api/place/photo"
                    parameters = {
                        'key': API_KEY,
                        'maxwidth': 400,
                        'photoreference': photo_reference,
                    }
                    url_for_picture = f"{base_url1}?{urllib.parse.urlencode(parameters)}"
                    return url_for_picture
                else:
                    return f"The photo is not available for {name}"
            else:
                return f"The place_id is not available for {name}"
        else:
            return "The Location is not available"
    except KeyError:
        return "The Location is not available"

open("place_id.txt", 'w').close()

def process_data(data, category):
    for line in data:
        name = line.get('name') or line.get('NAME') or line.get('StationName')
        latitude = float(line.get('latitude') or line.get('LATITUDE') or line.get('X'))
        longitude = float(line.get('longitude') or line.get('LONGITUDE') or line.get('Y'))
        image_url = get_photos(name)
        address = ",".join([
            line.get('address') or line.get('ADDRESS') or line.get('StreetAddress', ''),
            line.get('city') or line.get('CITY') or line.get('City', ''),
            line.get('province') or line.get('STATE') or line.get('State', ''),
            line.get('postalCode') or line.get('ZIP', ''),
        ])
        website = line.get('websites', '')

        locations_data[category].append({
            "latitude": latitude,
            "longitude": longitude,
            "name": name,
            "image_url": image_url,
            "address": address,
            "website": website,
        })

process_data(data, "restaurant")
process_data(data1, "Hospital")
process_data(data2, "gasStation")

knn_models = {
    category: NearestNeighbors(n_neighbors=len(locations), algorithm='ball_tree').fit(
        [[loc["latitude"], loc["longitude"]] for loc in locations]
    )
    for category, locations in locations_data.items()
}

@app.route('/api/nearby-location/<category>', methods=['GET', 'POST', 'OPTIONS'])
@cross_origin()
def get_nearby_locations(category):
    if request.method == 'OPTIONS':
        response = jsonify()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        return response

    if request.method == 'POST':
        try:
            request_data = request.json
            if request_data is None or 'latitude' not in request_data or 'longitude' not in request_data:
                return jsonify({"error": "Invalid JSON data"}), 400

            latitude = request_data.get('latitude')
            longitude = request_data.get('longitude')
            user_location = np.array([float(latitude), float(longitude)]).reshape(1, -1)

            knn_model = knn_models.get(category)
            if knn_model is None:
                return jsonify({"error": f"Category '{category}' not found. Available categories: {list(knn_models.keys())}"}), 400

            distances, indices = knn_model.kneighbors(user_location)

            nearby_locations = [
                {
                    "name": locations_data[category][i]["name"],
                    "latitude": locations_data[category][i]["latitude"],
                    "longitude": locations_data[category][i]["longitude"],
                    "distance": distances[0][i],
                    "image_url": locations_data[category][i]["image_url"],
                    "address": locations_data[category][i]["address"],
                }
                for i in indices[0]
            ]
            return jsonify(nearby_locations)

        except Exception as e:
            return jsonify({"error": str(e)}), 501
    else:
        return jsonify({"error": "Invalid method"}), 405

if __name__ == '__main__':
    app.run(port=8080, debug=True)
