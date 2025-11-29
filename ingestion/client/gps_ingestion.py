import mysql.connector
import requests 
import time
import logging 
from math import sqrt 

class GPSIngestion: 
   

   def __init__(self, api_url, db_config):
      self.api_url = api_url

      self.db - mysql.connector.connect(
         host=db_config["host"],
         user=db_config["user"],
         password=db_config["password"],
         database=db_config["database"]

      )

      self.cursor = self.db.cursor(directory=True)

      #start and end coordinates for Cremyll route 
      self.start = (50.366802, -4.161300) #stonehouse 
      self.end = (50.360531, -4.167988) #cremyll

#distance helper 
def distance(self, a, b):
   return sqrt((a[0] - b[0])**2 +(a[1] - b[1])**2)

#calculate progress based on GPS 
def Calculate_Progress(self, lat, lon):
   dist_total = self.distance(self.start, self.end)
   distance_now = self.distance((lat, lon), self.end)
   pct = 100 - ((dist_now / dist_total)* 100)
   return max(0, min(100, pct))

#fetch from external API 
def fetch_gps_from_api(self):
   r = requests.get(self.api_url, timeout=5)
   data = r.json()
   return float(data["lat"]), float(data["lon"])

#GPS needs to be inserted into "SQL" 

def insert_gps(self, ferry_id, lat, lon):
   sql = """
        INSERT INTO GPS_Data (ferry_id, latitude, longitude, timestamp)
        VALUES (%s, %s, %s, NOW())
        """
   self.cursor.exectue(sql, (ferry_id, lat, lon))
   self.db.commit()
   return self.cursor.lastrowid

#insert processed progress
def insert_progress(self, ferry_id, gps_id, progress):
        sql = """
        INSERT INTO Processed_Data (gps_id, ferry_id, progress, timestamp)
        VALUES (%s, %s, %s, NOW())
        """
        self.cursor.execute(sql, (gps_id, ferry_id, progress))
        self.db.commit()

#main loop
def run(self, ferry_id=1, interval=5):
   
    while True:
    try:

        lat, lon = self.fetch_gps_from_api()
        logging.info(f"Fetched GPS: {lat}, {lon}")

        gps_id = self.insert_gps(ferry_id, lat, lon)

        progress = self.calculate_progress(lat, lon)
        logging.ifo(f"Progress: {progress}%")

        self.insert_progress(ferry_id, gps_id, progress)  

      except Exception as e:
        logging.error(f"Error in GPS ingestion: {e}")

        time.sleep(interval)

