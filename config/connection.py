from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

MONGO_URI = "mongodb://Kishan:KishankFitshield@ec2-13-233-104-209.ap-south-1.compute.amazonaws.com:27017/?authMechanism=SCRAM-SHA-256&authSource=Fitshield"

client = MongoClient(MONGO_URI)
db = client["Fitshield"]

def check_connection():
    try:
        client.admin.command('ping')
        return {
            "status": True,
            "message": "MongoDB connection successful."
        }
    except ConnectionFailure as e:
        return {
            "status": False,
            "message": f"MongoDB connection error: {str(e)}"
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"An unexpected error occurred: {str(e)}"
        }
