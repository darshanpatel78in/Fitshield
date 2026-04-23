
from io import BytesIO
import json
import os
import nltk

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from datetime import datetime
from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone_text.sparse import BM25Encoder
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import FrameBreak
from reportlab.platypus import Image
import requests
from svglib.svglib import svg2rlg
from reportlab.lib.colors import HexColor
from fitshield import settings
from fitshield_webapp.utils.claim import nutrient_code_mapping, vitamin_mineral_mapping,nutrient_percentage_mapping,nutrient_name_mapping,nutrient_maps,notes_list,authorised_data,allowed_nutrients,replacement_map,calculate_rda
from config.connection import db
from ..AI.AIModel.ai_model2 import api_key,unit_index_name,ingredient_index_name,pc,embeddings,ingredient_index



# MongoDB Connection
restro_collection = db["RestroData"]
menu_collection = db["RestaurantMenuData"]
nutrient_collection = db["Nutrients"]


ingredients_bm25_path = os.path.join(os.getcwd(), 'fitshield_webapp', 'AI', 'AIModel', 'data', 'ingredients_bm25_values.json')
unit_bm25_path = os.path.join(os.getcwd(), 'fitshield_webapp', 'AI', 'AIModel', 'data', 'unit_bm25_values.json')


ingredient_bm25_encoder = BM25Encoder().load(ingredients_bm25_path)
unit_bm25_encoder = BM25Encoder().load(unit_bm25_path)

ingredient_retriever = PineconeHybridSearchRetriever(
    embeddings=embeddings,
    sparse_encoder=ingredient_bm25_encoder,
    index=ingredient_index,
)


def load_json_file(file_name):

    path = os.path.join(os.getcwd(), 'fitshield_webapp', 'AI', 'AIModel', 'data', 'ifct_usda.json')
    
    if file_name == 'ifct_usda.json':
        file_path = path
    else:
        raise FileNotFoundError(f"File {file_name} not found.")
    
    with open(file_path, 'r') as file:
        combined_data = json.load(file)
        
        usda_data = combined_data.get("USDA", [])
        ifct_data = combined_data.get("IFCT", [])
        
        return usda_data, ifct_data

    


def get_missing_nutrients(nutritional_value_data, advertisement_claims_data):
    nutrient_names_in_table = set()

    if isinstance(nutritional_value_data, dict):
        nutrient_names_in_table = set(nutritional_value_data.keys())
    elif isinstance(nutritional_value_data, list):
        for row in nutritional_value_data[1:]: 
            if isinstance(row, list) and len(row) > 1:
                nutrient_names_in_table.add(row[1].lower())

    missing_nutrients = []

    for claim in advertisement_claims_data:
        nutrient_name = claim["Name of Nutrients"].lower()

        if nutrient_name not in nutrient_names_in_table:
            missing_nutrients.append(claim["Name of Nutrients"])

    return missing_nutrients

def is_indian_code(code):
    code = str(code)
    return code[0].isupper() and len(code) == 4

def get_nutrient_code(ingredient_name, retriever):
    search_result = retriever.invoke(ingredient_name)
    if not search_result:
        return None, None

    matched_food = search_result[0].page_content
    nutrient_data = nutrient_collection.find_one({"Food name": matched_food})

    if not nutrient_data:
        return None, None

    data_ref = "IFCT" if is_indian_code(nutrient_data['Foodcode']) else "USDA"
    return nutrient_data['Foodcode'], data_ref

def is_indian_code(code):

    code = str(code)
    if code[0].isupper() and len(code) == 4:
        return True
    return False

def get_nutrient_code(ingredient_name,retriever):

    simentic_search_result = retriever.invoke(ingredient_name)
    if not simentic_search_result:
        print(f"Ingredient name: {ingredient_name}, Not Found : {simentic_search_result}")
        return None, None

    simentic_search = simentic_search_result[0].page_content

   
    nutrient_data = nutrient_collection.find_one({"Food name": simentic_search})


    if not nutrient_data:
        return None, None  

    data_ref = ""

    if is_indian_code(nutrient_data['Foodcode']):
        data_ref = "IFCT"
    else:
        data_ref = "USDA"

    return nutrient_data['Foodcode'], data_ref


def fetch_restaurant_data(restro_id):
    return restro_collection.find_one({"_id": restro_id})

def fetch_menu_data(restro_id):
    return menu_collection.find_one({"_id": restro_id})

def fetch_nutrient_data(ingredient_name):
    return nutrient_collection.find_one({"Food name": ingredient_name})


def get_nutrient_claims(resto_id, dish_name):
    restaurant_menu_data = menu_collection.find_one({"_id": resto_id})

    if not restaurant_menu_data:
        return None

    menu_data = restaurant_menu_data.get("menu", [])

    dish_data = [dish for dish in menu_data if dish.get("dish_name", "").lower() == dish_name.lower()]

    if not dish_data:
        return None

    dish = dish_data[0]

    claims_details = dish.get("claims_details", [])

    if not claims_details:
        return None

    formatted_claims = []

    for idx, claim in enumerate(claims_details, start=1):
        claim_words = claim.get("Claim Words", "N/A")
        nutrient_name = claim.get("Name of Nutrients", "N/A")
        value = claim.get("Value", "N/A")
        unit = claim.get("Unit", "N/A")
        conversion = claim.get("Convertion for claims", "N/A")
        guideline = claim.get("Guideline", "N/A")
        result = claim.get("Results", "Pass")

        
        formatted_claims.append({
            "Sr No": idx,
            "Claim Words": claim_words,
            "Name of Nutrients": nutrient_name,
            "Value": value,
            "Unit": unit,
            "Convertion for claims": conversion,
            "Guideline": guideline,
            "Results": result
        })

    return formatted_claims

green_color = HexColor("#008B43")


# Function to Draw a Separate Bottom Line
def draw_bottom_line(canvas, doc):
    canvas.setStrokeColor(colors.black) 
    canvas.setLineWidth(3)  
    canvas.line(5, 4240, 3500, 4240) 
    canvas.line(5, 3870, 3500, 3870)  
    return draw_bottom_line


def create_user_pdf(restro_data, menu_data, selected_dish,buffer):
    
    USDA, IFCT = load_json_file('ifct_usda.json')
 
    custom_width = 2600
    custom_height = 4500  

    doc = SimpleDocTemplate(buffer, pagesize=(custom_width, custom_height))

    elements = []
    styles = getSampleStyleSheet()

    path = "https://fitshield-data.s3.ap-south-1.amazonaws.com/Admin/Logo.png"  

    try:
        response = requests.get(path)
        if response.status_code == 200:
            img_data = BytesIO(response.content)
            img = Image(img_data, width=350, height=130) 
        else:
            img = None
    except Exception as e:
        img = None

    if img:
        data = [
            [img, "", ""]  
        ]
    else:
        data = [
            ["Image not found", "", ""]
        ]

    table = Table(data, colWidths=[100, custom_width - 500, 100], hAlign="CENTER")  

    #  Apply Styling to Align Elements Properly
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  
        ('ALIGN', (0, 0), (0, -1), 'LEFT'), 
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),  
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),  
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5) 
    ]))

    elements.append(table)
    elements.append(Spacer(1, 100))

    # Define a Larger Title Style (Font Size 50, Centered)
    title_style = ParagraphStyle(
        'TitleStyle',
        fontSize=50,
        alignment=1, 
        spaceAfter=20
    )

    # Centered Restaurant Details Title (Above Table)
    Restaurant_title = Paragraph("<b>Restaurant Details</b>", title_style)
    elements.append(Restaurant_title)
    elements.append(Spacer(1, 80)) 

    dish_index = next((index for index, dish in enumerate(menu_data.get("menu", [])) if dish.get("dish_name", "").lower() == selected_dish.lower()), None)
    
    # Generate Report ID
    restro_id = restro_data["_id"]
    report_id = f"{restro_id}.{dish_index}" if dish_index is not None else f"RPT-{restro_id}.NA"


    # Define Table Data in 4 Columns (Split as Requested)
    details = [
        ("Date", ":",datetime.now().strftime("%Y-%m-%d"), "Address", ":", restro_data.get("address", "")),
        ("Entity Name", ":", restro_data.get("name", ""), "City", ":", restro_data.get("city", "")),
        ("Entity ID", ":", restro_data.get("_id", ""), "State", ":", restro_data.get("state", "")),
        ("Entity Type", ":", "Restaurant", "Owner Name", ":", restro_data.get("personal_details", {}).get("user_name", "")),
        ("FSSAI ID", ":", restro_data.get("fassi_id", ""), "Report ID", ":", report_id),
        ("Contact Number", ":", restro_data.get("personal_details", {}).get("phone_number", ""), "", "")
    ]

    # Create the Table (4 Columns for Better Alignment)
    table = Table(details, colWidths=[200, 20, 1000, 220, 20, 300], hAlign='LEFT')

    # Apply Styling
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.white), 
        ('BACKGROUND', (2, 0), (2, -1), colors.white), 
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black), 
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'), 
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),  
        ('FONTSIZE', (0, 0), (-1, -1), 24),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))

    # Append the Table to PDF Elements
    elements.append(table)
    elements.append(Spacer(1, 80))  

    # Define Paragraph Style for Date & Title
    styles.add(ParagraphStyle(name="TitleStyle", parent=styles["Title"], fontSize=50, alignment=1))  # Center
    title = Paragraph("<b>Nutritional Report</b>", styles["TitleStyle"]) 
    data = [["", title, ""]]

    title_date_table = Table(data, colWidths=[400, custom_width - 400, 400], hAlign="CENTER") 
    title_date_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'), 
        ('ALIGN', (1, 0), (1, -1), 'CENTER'), 
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (0, -1), 10), 
        ('RIGHTPADDING', (0, 0), (0, -1), 0),    
        ('TOPPADDING', (0, 0), (-1, -1), 25),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5)
    ]))

    elements.append(title_date_table)
    elements.append(Spacer(1, 100))

    styles.add(ParagraphStyle(name="Head", parent=styles["Heading2"], fontSize=35)) 

    # **Food Sample Details Section**
    food_sample_title = Paragraph("<b>Food Sample Details</b>", styles["Head"])
    elements.append(food_sample_title)
    elements.append(Spacer(1, 50))

    # Find the selected dish details
    selected_dish_data = None
    for dish in menu_data.get("menu", []):
        if dish.get("dish_name", "").lower() == selected_dish.lower():
            selected_dish_data = dish
            break  # Exit loop once found

    # Define table header
    food_sample_details = [
        ("Food Dish Name", "Dish Category", "Sub Category", "Serving Size (Approx)")
    ]

    if selected_dish_data:
        dish_variants = selected_dish_data.get("dish_variants", {}).get("normal", {}).get("full", {})
        serving_size = dish_variants.get("serving", {}).get("size", "N/A")
        serving_unit = dish_variants.get("serving", {}).get("unit", "N/A")

        # Add dish data to the table
        food_sample_details.append([
            selected_dish_data.get("dish_name", "N/A"),
            selected_dish_data.get("food_category", "N/A"),
            selected_dish_data.get("cuisine_category", {}).get("subcategory", "N/A"),
            f"{serving_size} {serving_unit}" if serving_size != "N/A" else "N/A"
        ])

    # Fetch Advertisement Claims
    advertisement_claims = get_nutrient_claims(restro_data["_id"], selected_dish)

    # Create second table for food sample details
    table2 = Table(food_sample_details, colWidths=[600, 150, 150, 250], hAlign='LEFT')

    # Styling for the second table
    table2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), green_color), 
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), 
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (0, -1), colors.white),  
        ('BACKGROUND', (1, 1), (-1, -1), colors.white),  
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20), 
        ('TOPPADDING', (0, 0), (-1, -1), 5), 
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey),
        ('WORDWRAP', (0, 0), (-1, -1), True)
    ]))

    elements.append(table2)
    elements.append(Spacer(1, 40))



    # Raw Ingredients Table
    ingredients_title = Paragraph("<b>Raw Ingredients Details</b>", styles["Head"])
    elements.append(ingredients_title)
    elements.append(Spacer(1, 50))

    selected_dish_data = next((dish for dish in menu_data.get("menu", []) if dish.get("dish_name", "").lower() == selected_dish.lower()), None)

    ingredients_table_data = [("Sr No", "Ingredient Name", "Details", "Quantity", "Unit (Metric)", "Food Code", "Data Reference")]

    if selected_dish_data:
        dish_variants = selected_dish_data.get("dish_variants", {}).get("normal", {}).get("full", {})
        ingredients = dish_variants.get("ingredients", [])

        for idx, ingredient in enumerate(ingredients, start=1):
            food_code, data_ref = get_nutrient_code(ingredient.get("name", ""), ingredient_retriever)  # Placeholder for nutrient lookup
            ingredients_table_data.append([
                idx,
                ingredient.get("name", "N/A"),
                ingredient.get("description", "N/A"),
                ingredient.get("quantity", "N/A"),
                ingredient.get("unit", "N/A"),
                food_code if food_code else "N/A",
                data_ref if data_ref else "N/A"
            ])

    table3 = Table(ingredients_table_data, colWidths=[60, 650, 460, 250, 120, 150, 150], hAlign='LEFT')
    table3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), green_color), 
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (0, -1), colors.white), 
        ('BACKGROUND', (1, 1), (-1, -1), colors.white),  
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),  
        ('TOPPADDING', (0, 0), (-1, -1), 8),  
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey)
    ]))
    elements.append(table3)
    elements.append(Spacer(1, 40))


    # Nutritional Value Section
    nutrition_title = Paragraph("<b>Nutritional Value</b>", styles["Head"])
    elements.append(nutrition_title)
    elements.append(Spacer(1, 50))

    nutrient_table_data = [("Sr No", "Nutrient Name", "Value/Serving Size", "Unit", "Contribution %", "% RDA", "IFCT-2017 Method", "USDA Method")]


    # Fetch the dish data
    dish = next((d for d in menu_data.get("menu", []) if d.get("dish_name").lower() == selected_dish.lower()), None)
    if not dish:
        return

    dish_variants = dish.get("dish_variants", {}).get("normal", {}).get("full", {})
    macro_nutrients = dish_variants.get("calculate_nutrients", {}).get("macro_nutrients", [])
    Energy = next((item['value'] for item in macro_nutrients if item['name'] == 'energy'), 0)
    nutrients_data = dish_variants.get("nutrients", {})

    idx = 1

    for nutrient in nutrients_data:

        nutrient_name = nutrient.get("name", "")

        if nutrient_name not in ["ENERC","CHOAVLDF","PROTCNT","FATCE","FIBTG","NA","CHOLC","TOTALFREESUGARS"]:
            continue

        nutrient_name = replacement_map[nutrient_name]

        nutrient_unit = nutrient.get("unit", "")

        value_per_serving = nutrient.get("quantity", 0)

        try:
            value_per_serving = float(value_per_serving)
        except ValueError:
            value_per_serving = 0.0

        if nutrient_name == "Proteins":
            percentage_value = str(round(((value_per_serving  * 4)/Energy) * 100, 2)) + "%"
        elif nutrient_name == "Fats":
            percentage_value = str(round(((value_per_serving  * 9)/Energy) * 100, 2)) + "%"
        elif nutrient_name == "Fibers":
            percentage_value = str(round(((value_per_serving  * 2)/Energy) * 100, 2)) + "%"
        elif nutrient_name == "Carbs":
            percentage_value = str(round(((value_per_serving  * 4)/Energy) * 100, 2)) + "%"
        else:
            percentage_value = "N/A"

        rda_value = calculate_rda(nutrient_name, value_per_serving)

        ifct_methods = {item["Nutrient"]: item.get("Method", "N/A") for item in IFCT}
        usda_methods = {item["Nutrient"]: item.get("Method", "N/A") for item in USDA}

        ifct_method = ifct_methods.get(nutrient_name, "N/A")
        usda_method = usda_methods.get(nutrient_name, "N/A")

        # Construct row data
        row = [
            idx,
            nutrient_name,
            value_per_serving, 
            nutrient_unit,
            percentage_value,
            rda_value, 
            ifct_method,  
            usda_method,  

        ]
        nutrient_table_data.append(row)
        idx += 1

    for claims_data in advertisement_claims:
        nutrient_name = claims_data.get("Name of Nutrients", "")
        nutrient_unit = claims_data.get("Unit", "")
        value_per_serving = claims_data.get("Value", 0)

        if nutrient_name in ["Lactose", "Gluten","Energy","Carbs","Proteins","Fats","Fibers","Sodium","Cholesterol","Sugars"]:
            continue

        try:
            value_per_serving = float(value_per_serving)
        except ValueError:
            value_per_serving = 0.0

        percentage_value = "N/A"
        rda_value = calculate_rda(nutrient_name, value_per_serving)

        # # Creating lookup dictionaries for methods and references
        ifct_methods = {item["Nutrient"]: item.get("Method", "N/A") for item in IFCT}
        usda_methods = {item["Nutrient"]: item.get("Method", "N/A") for item in USDA}

        ifct_method = ifct_methods.get(nutrient_name, "N/A")
        usda_method = usda_methods.get(nutrient_name, "N/A")

        # Construct row data
        row = [
            idx,
            nutrient_name,
            value_per_serving, 
            nutrient_unit,
            percentage_value,
            rda_value,  
            ifct_method, 
            usda_method,  

        ]
        nutrient_table_data.append(row)
        idx += 1

    #  Move table creation **OUTSIDE** the loop
    table4 = Table(nutrient_table_data, colWidths=[60, 300, 250, 60, 145, 120, 700, 700], hAlign='LEFT')

    # Apply styling
    table4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), green_color), 
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), 
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (0, -1), colors.white), 
        ('BACKGROUND', (1, 1), (-1, -1), colors.white),  
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),  
        ('TOPPADDING', (0, 0), (-1, -1), 8), 
        ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey)
    ]))

    elements.append(table4)
    elements.append(Spacer(1, 40))

    advertisement_title = Paragraph("<b>Advertisement Claims</b>", styles["Head"])
    elements.append(advertisement_title)
    elements.append(Spacer(1, 50))

    advertisement_table_data = [
        ("Sr No", "Claim Words", "Name of Nutrients", "Value", "Unit", "Conversion for claims", "Guideline", "Result")
    ]

    if advertisement_claims:
        for row in advertisement_claims:
            advertisement_table_data.append([
                row["Sr No"],
                row["Claim Words"],
                row["Name of Nutrients"],
                row["Value"],
                row["Unit"],
                row["Convertion for claims"],
                row["Guideline"],
                row["Results"]
            ])

        # Create the table for advertisement claims
        table5 = Table(advertisement_table_data, colWidths=[60, 400, 350, 100, 60, 250, 1120, 100], hAlign='LEFT')

        # Apply styling
        table5.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), green_color), 
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), 
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (0, -1), colors.white),  
            ('BACKGROUND', (1, 1), (-1, -1), colors.white), 
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20), 
            ('TOPPADDING', (0, 0), (-1, -1), 8),  
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey)
        ]))

        elements.append(table5)
        elements.append(Spacer(1, 20))
    else:
        elements.append(Paragraph("No Advertisement Claims available.", styles["BodyText"]))
        elements.append(Spacer(1, 20))

    refrence_type_note = ParagraphStyle(
        name='refrence',
        parent=styles['Italic'], 
        fontSize=24, 
    )

    refrence_type = Paragraph("**The referance for the Advertisment claims are from the give document link :- https://fssai.gov.in/upload/uploadfiles/files/Compendium_Advertising_Claims_Regulations_04_03_2021.pdf**", refrence_type_note)

    elements.append(refrence_type)
    elements.append(Spacer(1, 40))

    # **Allergy Content Section**
    allergy_title = Paragraph("<b>Allergy Content</b>", styles["Head"])
    elements.append(allergy_title)
    elements.append(Spacer(1, 50))

    # Define table header
    allergy_table_data = [("Sr No", "Allergen Name")]

    # Find the correct dish data based on selected_dish
    allergic_contents = []
    for dish in menu_data.get("menu", []):
        if dish.get("dish_name").lower() == selected_dish.lower():
            allergic_contents = dish.get("allergic_content", [])
            break 

    # Append allergy data properly
    for idx, allergen in enumerate(allergic_contents, start=1):
        allergy_table_data.append([idx, allergen.strip()])  
        
    # Create table **only if there are allergens** to display
    if len(allergy_table_data) > 1:
        table6 = Table(allergy_table_data, colWidths=[60, 200], hAlign='LEFT')

        # Apply styling
        table6.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), green_color),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), 
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 1), (0, -1), colors.white),  
            ('BACKGROUND', (1, 1), (-1, -1), colors.white),  
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 20),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 20), 
            ('TOPPADDING', (0, 0), (-1, -1), 8),  
            ('GRID', (0, 0), (-1, -1), 1, colors.lightgrey)
        ]))

        elements.append(table6)
        elements.append(Spacer(1, 80))
    else:
        Allergy_style = ParagraphStyle(
            name='allergyStyle',
            parent=styles['BodyText'],
            fontSize=24  
        )
        Allergy_text = "No allergen information available."
        Allergy_para = Paragraph(Allergy_text, Allergy_style)
        elements.append(Allergy_para)
        elements.append(Spacer(1, 80))

    # Calculation Method Section
    calc_method_title = Paragraph("<b>Calculation Method</b>", styles["Head"])
    elements.append(calc_method_title)
    elements.append(Spacer(1, 30))

    # Define a ParagraphStyle with a larger font size
    calc_method_style = ParagraphStyle(
        name='CalcMethodStyle',
        parent=styles['BodyText'],
        fontSize=24  
    )

    # Use the styled ParagraphStyle
    calc_method_text = "Computerized software-based calculation from Raw ingredients"
    calc_method_para = Paragraph(calc_method_text, calc_method_style)


    # Append ONLY the Paragraph object
    elements.append(calc_method_para) 
    elements.append(Spacer(1, 40))


    # Notes Section
    elements.append(Paragraph("Notes", styles['Head']))
    elements.append(Spacer(1, 30))

    notes_table = Table(notes_list, colWidths=[30, 500], rowHeights=[30,30,30,30,30,30,30,30,30,30], hAlign='LEFT')
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.grey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 24),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
    ]))
    elements.append(notes_table)
    elements.append(Spacer(1, 40))

    # Authorised By Section
    elements.append(Paragraph("Authorised by", styles['Head']))
    elements.append(Spacer(1, 30))
   
    authorised_table = Table(authorised_data, colWidths=[200,15, 200, 150], rowHeights=[30,30,30,30,30,10,10,30], hAlign='LEFT')
    authorised_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  
        ('WORDWRAP', (0, 0), (-1, -1)),  
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 24),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6)
    ]))
    elements.append(authorised_table)
    elements.append(Spacer(1, 40))

    # Final Note Style
    final_note_style = ParagraphStyle(
        name='FinalNoteStyle',
        parent=styles['Italic'], 
        fontSize=24,
        alignment=1 
    )

    final_note = Paragraph("**This report is computer generated and does not require a physical signature.**", final_note_style)

    elements.append(final_note) 

    # Add the border when building the PDF
    doc.build(elements, onFirstPage=draw_bottom_line, onLaterPages=draw_bottom_line)


