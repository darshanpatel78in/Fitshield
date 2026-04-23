from indian_address_parser import PostalAddress

def parse_address(address):
    try:
        postal_address = PostalAddress(address).__dict__

        # Safely retrieve parsed components with defaults in case of missing data
        country = postal_address.get('country', 'Unknown Country') or 'Unknown Country'
        districts = postal_address.get('districts_found', []) or []
        pincode = postal_address.get('pin_codes_found', ['Unknown Pincode'])[0]
        state = postal_address.get('states_found', ['Unknown State'])[0]
        detailed_address = postal_address.get('street_names_found', []) or []
        city = postal_address.get('village_or_citys_found', []) or []

        # Return structured response
        return detailed_address, city, state, pincode, country

    except AttributeError as e:
        # print(f"Error accessing attributes: {e}")
        return {
            "detailed_address": [],
            "city": [],
            "state": "Error Parsing State",
            "pincode": "Error Parsing Pincode",
            "country": "Error Parsing Country"
        }
    except Exception as e:
        # print(f"An unexpected error occurred: {e}")
        return {
            "detailed_address": [],
            "city": [],
            "state": "Unknown",
            "pincode": "Unknown",
            "country": "Unknown"
        }
