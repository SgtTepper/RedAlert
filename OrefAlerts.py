import requests
import pandas as pd
from progressbar import progressbar
import json

# define start and end dates - format: Day.Month.Year
from_date = "09.05.2021"
to_date = "20.05.2021"

# Get data
alerts_url = f"https://www.oref.org.il//Shared/Ajax/GetAlarmsHistory.aspx?lang=he&fromDate={from_date}&toDate={to_date}&mode=0"
alerts_json = requests.get(alerts_url).json()

# define gaza coordinates
gaza_coords = (31.513, 34.452)

# Break multi-region alerts into separate records
df = pd.DataFrame.from_records(alerts_json)
df["data"] = df["data"].str.split(",")
df = df.explode("data")

# Remove sub-regions such as א, ב, ג, ד
df = df[df["data"].str.len() > 2]

# Change Hatzor to detailed name as the google geocoder fail to detect the correct city
df["data"] = df["data"].replace("חצור", "חצור אשדוד")

total_cities = len(df["data"].unique())
global failed_cities
failed_cities = 0

# Map city names to coordinates
def get_coordinates(city_name):
    city_name = city_name + ", ישראל"

    # areas of cities that make geolocation fail - remove them
    strings_to_remove = ["והפזורה", "מתחם", "אזור תעשייה"]

    for i in strings_to_remove:
        city_name = city_name.replace(i, "")

    # to find cities with areas - תל אביב - מערב becomes תל אביב
    city_name = city_name.split(" - ")[0]

    geocoder_url = f"https://nominatim.openstreetmap.org/search?q={city_name}&format=json&polygon_geojson=1&addressdetails=1"
    geocoding_result = requests.get(geocoder_url).json()

    if not geocoding_result:
        global failed_cities
        failed_cities = failed_cities + 1
        return (None, None, None)

    lat = geocoding_result[0]["lat"]
    long = geocoding_result[0]["lon"]

    for result in geocoding_result:
        if "Polygon" in result["geojson"]["type"]:  # try to find a polygon
            poly = json.dumps(result["geojson"])
            return (lat, long, poly)

    # no polygon found - return the first geojson object
    poly = json.dumps(
        geocoding_result[0]["geojson"]
    )  # no polygon found - take the first object
    return (lat, long, poly)


city_to_coords = {}
# find cities using reverse geolocation
for city in progressbar(df["data"].unique(), redirect_stdout=True):
    city_to_coords[city] = get_coordinates(city)
    print(city, "\t -", city_to_coords[city][0], city_to_coords[city][1])

print(
    f"Geocoding complete. Successfuly found {total_cities-failed_cities}/{total_cities}"
)

# Apply mapping on all data
df["outLat"] = df["data"].apply(lambda x: city_to_coords[x][0])
df["outLong"] = df["data"].apply(lambda x: city_to_coords[x][1])
df["poly"] = df["data"].apply(lambda x: city_to_coords[x][2])

# Fixed Gaza coordinates
df["inLat"] = gaza_coords[0]
df["inLong"] = gaza_coords[1]

# Filter wrong coordinates outside of Israel polygon (only if you use a bad geocoder)
"""
filtered_df = df[(df['outLong'] < 35.8)
                & (df['outLong'] > 33.3)
                & (df['outLat'] < 34.0)
                & (df['outLat'] > 29.2)]

filtered_df.to_csv('RocketLaunchData - Filtered.csv', encoding='utf-8-sig', index=False)
display(filtered_df)
"""

df.to_csv("RocketLaunchData.csv", encoding="utf-8-sig", index=False)

# display(df)