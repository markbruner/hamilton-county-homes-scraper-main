import re
import pandas as pd
import difflib
import spacy

nlp = spacy.load("en_core_web_sm")

def is_alphanumeric(token):
    """Check if the token text is alphanumeric."""
    return re.match("^(?=.*[0-9])(?=.*[a-zA-Z])[a-zA-Z0-9]+$", token.text) is not None

def correct_street_name_fuzzy(street_name, valid_names, cutoff=0.8):
    matches = difflib.get_close_matches(street_name, valid_names, n=1, cutoff=cutoff)
    return matches[0] if matches else street_name

def owner_address_cleaner(df, field='owner_address'):
    """
    Parses a multiline address column into separate components: street, city, state, and postal code.
    Adds these as new columns and tags whether the owner's address matches the home address.

    Parameters:
    - df (pd.DataFrame): The DataFrame containing the address column.
    - field (str): The name of the column containing the owner's full address. Defaults to 'owner_address'.

    Returns:
    - pd.DataFrame: The original DataFrame with additional columns:
        - 'owner_street_address'
        - 'owner_city'
        - 'owner_state'
        - 'owner_postal_code'
        - 'owner_home_address_match': 'Y' if match is found, 'N' otherwise.
    """

    # Regex pattern to extract address, city, state, and postal code
    pattern = r"(?P<address>.+)\r?\n(?:(?P<city>[A-Z\s]+) (?P<state>[A-Z]{2}) )?(?P<postal_code>\d{5})"

    # Getting the details using regex
    extracted_data = df[field].str.extract(pattern)

    # Replacing the columns with more descriptive names
    extracted_data.columns = ["owner_street_address", "owner_city", "owner_state", "owner_postal_code"]
    # Joining data back
    df = pd.concat([df,extracted_data],axis=1)

    df.loc[df["address"].str.split(expand=True)[0]==df["owner_street_address"].str.split(expand=True)[0],"owner_home_address_match"] = "Y"
    df.loc[df["owner_home_address_match"]!="Y","owner_home_address_match"] = "N"
    return df

def tag_address(address):
    """
    Tag the components of the address using the defined pattern.
    Returns a dictionary with the components tagged.
    """
    # List of spelled-out numbers to exclude from being tagged as 'NUM'
    spelled_out_numbers = {
        "zero", "one", "two", "three", "four", "five", "six", "seven", 
        "eight", "nine", "ten", "eleven", "twelve", "thirteen", 
        "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", 
        "nineteen", "twenty"
    }    
    # Initialize the spaCy model and Matcher
    doc = nlp(address)
    tagged_components = {"st_num": None, "apt_num": None, "street": None}

    # Loop through the tokens to find matches based on conditions
    for i, token in enumerate(doc):
        if i == 0 and token.pos_ == "NUM" and token.text.lower() not in spelled_out_numbers:
            tagged_components["st_num"] = token.text
        elif i == 1 and is_alphanumeric(token) and token.text.lower() not in spelled_out_numbers:
            tagged_components["apt_num"] = token.text
        elif i == 1 and token.pos_=="NUM"and token.text.lower() not in spelled_out_numbers:
            tagged_components["apt_num"] = token.text
        elif i > 0:
            # Concatenate the remaining tokens as the street name
            tagged_components["street"] = " ".join([tok.text for tok in doc[i:]])
            break
    return tagged_components