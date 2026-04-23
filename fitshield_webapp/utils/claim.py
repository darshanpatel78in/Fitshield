import json
import os
import nltk

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from openpyxl import Workbook
from datetime import datetime

from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone_text.sparse import BM25Encoder
from PIL import Image

from openpyxl.styles import Alignment
from reportlab.lib.pagesizes import A1, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import FrameBreak

from reportlab.pdfgen import canvas
from reportlab.graphics import renderPDF, renderPM
from svglib.svglib import svg2rlg
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing

from reportlab.lib.colors import HexColor

from fitshield import settings
# from fitshield_webapp.utils.claim import nutrient_code_mapping, vitamin_mineral_mapping


# Nutrient code mapping
nutrient_code_mapping = {
    "Energy": "ENERC", "Fats": "FATCE", "Cholesterol": "CHOLC", "Saturated Fats": "FASAT",
    "Unsaturated Fat": "N/A", "Trans Fat": "N/A", "Monosaturated Fatty Acids": "FAMS",
    "Polyunsaturated Fatty Acids": "FAPU", "Sugars": "TOTALFREESUGARS", "Protein": "PROTCNT",
    "Sodium": "NA", "Fibre": "FIBTG", "Lactose": "N/A", "Gluten": "N/A"
}

# Vitamin & Mineral Name Mapping
vitamin_mineral_mapping = {
    "THIA": "Vitamin B1", "RIBF": "Vitamin B2", "NIA": "Vitamin B3", "PANTAC": "Vitamin B5",
    "VITB6C": "Vitamin B6", "BIOT": "Vitamin B7", "FOLSUM": "Vitamin B9", "VITC": "Vitamin C",
    "RETOL": "Vitamin A", "ERGCAL": "Vitamin D", "CHOCAL": "Vitamin D", "VITE": "Vitamin E",
    "VITK1": "Vitamin K", "VITK2": "Vitamin K", "CARTOID": "Provitamin A",
    "CA": "Calcium", "CR": "Chromium", "CO": "Cobalt", "CU": "Copper", "FE": "Iron",
    "MG": "Magnesium", "MN": "Manganese", "MO": "Molybdenum", "P": "Phosphorus",
    "K": "Potassium", "ZN": "Zinc", "SE": "Selenium"
}
    
nutrient_maps = {
        "vitamin_b1": "THIA",
        "vitamin_b2": "RIBF",
        "vitamin_b3": "NIA",
        "vitamin_b5": "PANTAC",
        "vitamin_b6": "VITB6C",
        "vitamin_b7": "BIOT",
        "vitamin_b9": "FOLSUM",
        "vitamin_c": "VITC",
        "vitamin_a": "RETOL",
        "vitamin_d2": "ERGCAL",
        "vitamin_d3": "CHOCAL",
        "vitamin_e": "VITE",
        "vitamin_k1": "VITK1",
        "vitamin_k2": "VITK2",
        "provitamin_a": "CARTOID",
        "calcium": "CA",
        "copper": "CU",
        "iron": "FE",
        "magnesium": "MG",
        "manganese": "MN",
        "phosphorus": "P",
        "potassium": "K",
        "zinc": "ZN",
        "saturated_fats" : "FASAT",
        "monosaturated_fatty_acids" : "FAMS",
        "Polyunsaturated_fatty_acids" : "FAPU"
    }


    # Mapping for percentage lookup
nutrient_percentage_mapping = {
        "PROTCNT": "proteins",
        "FIBTG": "fibers",
        "FATCE": "fats",
        "CHOAVLDF": "carbs",
        "NA": "sodium",
        "CHOLC": "cholesterol",
        "ENERC": "energy",
        "TOTALFREESUGARS":"total_free_sugars"
    }

    # Nutrient name mapping (define this outside the loop)
nutrient_name_mapping = {
        "PROTCNT": "Proteins",
        "FIBTG": "Fibers",
        "FATCE": "Fats",
        "CHOAVLDF": "Carbs",
        "NA": "Sodium",
        "CHOLC": "Cholesterol",
        "ENERC": "Energy",
        "TOTALFREESUGARS":"Sugars",
        "RETOL":"vitamin A",
        "THIA": "Vitamin B1",
        "RIBF": "Vitamin B2",
        "NIA": "Vitamin B3",
        "PANTAC": "Vitamin B5",
        "VITB6C": "Vitamin B6",
        "BIOT": "Vitamin B7",
        "FOLSUM": "Vitamin B9",
        "VITC": "Vitamin C",
        "VITE": "Vitamin E",
        "CA" : "Calcium",
        "CU": "Copper",
        "FE": "Iron",
        "MG": "Magnesium",
        "MN":"Manganese",
        "P": "Phosphorus",
        "K":"Potassium",
        "ZN": "Zinc",
        "CARTOID" : "Provitamin A",
        "FASAT" : "Saturated Fats",
        "FAMS" : "Monosaturated Fatty Acids",
        "FAPU" : "Polyunsaturated Fatty Acids",
        "trans_fats" : "Trans Fats",
        "unsaturated_fatty_acids" : "Unsaturated Fatty Acids"
    }

notes_list = [
        ["1.", " The nutritional values provided are estimates based on standard ingredient compositions and may vary."],
        ["2.", " Fitshield does not claim medical accuracy and advises consumers to consult healthcare professionals."],
        ["3.", " The nutritional information is calculated in compliance with FSSAI (India) and FDA (USA) guidelines."],
        ["4.", " This report does not guarantee allergen-free food. Cross-contamination may occur."],
        ["5.", " Customers with severe allergies must verify with the provider before consumption."],
        ["6.", " Fitshield’s software relies on verified food databases but does not replace certified laboratory testing."],
        ["7.", " Any health claims (e.g., 'low fat', 'high protein', 'sugar-free') comply with FSSAI and FDA regulations."],
        ["8.", " Misleading or exaggerated claims are strictly avoided, and only evidence-backed statements are provided."],
        ["9.", " Fitshield provides this report for informational purposes only. It should not be used for medical diagnosis."],
        ["10.", " Fitshield’s software relies on verified food databases but does not replace certified laboratory testing."]
    ]

authorised_data = [
        ["Authority Name", ":", "Fitshield DietFood Private Limited"],
        ["Authorised Person",":", "Mr. Rahul Nanjibhai Virani"],
        ["Email ID",":","Info@fitshield.in"],
        ["Contact Details",":","+91 951-266-2666"],
        ["Address",":","5th Floor, Fitshield Pvt. Ltd, Jivandeep Complex, Varachha Main Rd, near Hirabaug Circle, Navi Shakti Vijay Society, Tapsil Society, Hirabaugh, Surat, Gujarat 395006"],
        ["  "],
        [" "],
        ["If found any complaint, please connect us through E-mail or Call us on phone"]
    ]

allowed_nutrients = {
        "energy": "ENERC",
        "carbs": "CHOAVLDF",
        "proteins": "PROTCNT",
        "fibers": "FIBTG",
        "fats": "FATCE",
        "cholesterol": "CHOLC",
        "sodium": "NA",
        "total_free_sugars": "TOTALFREESUGARS"
    }
replacement_map = {
        "ENERC" : "Energy",
        "CHOAVLDF" :"Carbs",
        "PROTCNT" : "Proteins",
        "FIBTG" : "Fibers",
        "FATCE" : "Fats",
        "CHOLC" : "Cholesterol",
        "NA" : "Sodium",
        "TOTALFREESUGARS" : "Sugars"
    }


   
def calculate_rda(nutrient_name, value):

    rda_values = {
        "Proteins": 54, # g
        "Carbs": 250,# g
        "Fats": 55,# g
        "Fibers": 40,# g
        "Energy": 2000,# kcal
        "Vitamin B1": 1.8, #mg
        "Vitamin B2": 2.5, #mg
        "Vitamin B3": 18, #mg
        "Vitamin B5": 5, #mg
        "Vitamin B6": 2.4, #mg
        "Vitamin C": 80, #mg
        "Vitamin B7": 25,  #ug
        "Vitamin B9": 300, #ug
        "Vitamin A": 1000, #ug
        "Vitamin D": 15, #ug # e
        "Vitamin K": 55, #in ug # e
        "carotenoids": 3000,  # Not specified
        "Vitamin E": 9, #mg
        "Calcium": 1000, #mg,
        "Copper": 17, #mg
        "Iron": 19, #mg
        "Magnesium": 440, #mg
        "Manganese": 4, #mg
        "Phosphorus": 600, #mg  # e
        "Potassium": 3500, #mg
        "Sodium": 2000, #mg
        "Zinc": 17 #mg
    }

    if nutrient_name in rda_values and value:
        return f"{round((value / rda_values[nutrient_name]) * 100, 2)}%"

    return "N/A"  
