import json, requests

# Fetch the current materials points
r = requests.post("http://127.0.0.1:5001/api/students/5/analyze_material_points")
print("AI Points:", r.text)

# We will manipulate the points and send them to manual_crop_material
pts = r.json()

# Make the home_points 100 pixels wider to simulate dragging
home = pts.get("home_points")
if home:
    home[0][0] -= 100
    home[0][1] -= 100
    home[2][0] += 100
    home[2][1] += 100

payload = {
    "material_type": "hukou",
    "adjustments": {"crop_mode": "none"},
    "home_points": home,
    "personal_points": pts.get("personal_points")
}

print("Sleeping 2 seconds...")
import time
time.sleep(2)

print("\nHitting manual_crop...")
res = requests.post("http://127.0.0.1:5001/api/students/5/manual_crop_material", json=payload)
print("Result:", res.status_code, res.text)
