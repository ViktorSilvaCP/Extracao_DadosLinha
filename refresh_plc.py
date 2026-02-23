import requests
import os
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("API_MASTER_TOKEN")
port = int(os.getenv("API_PORT", 15789))
url = f"http://localhost:{port}/api/admin/plcs"

data = {
    "name": "Cupper_23",
    "ip": "10.81.72.11",
    "slot": 4,
    "socket_timeout": 5,
    "main_tag": "Count_discharge",
    "feed_tag": "Feed_Progression_INCH",
    "bobina_tag": "Bobina_Consumida",
    "trigger_coil_tag": "Bobina_Trocada",
    "lote_tag": "Cupper22_Bobina_Consumida_Serial",
    "stroke_tag": "oHMI_Daily_Stroke_Count",
    "tool_size_tag": "IGN_Tool_Size",
    "is_active": 1
}

headers = {
    "X-Terminal-Token": token,
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, json=data, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
