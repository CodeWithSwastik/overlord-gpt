
def tokenize(text):
    """
    Tokenize a string, splitting on spaces, but keeping quoted strings together.

    >hi there lmao "what is really" "this" 
    ['>hi', 'there', 'lmao', 'what is really', 'this']
    """
    tokens = []
    current_token = ""
    in_quotes = False
    for char in text:
        if char == '"':
            if in_quotes:
                tokens.append(current_token)
                current_token = ""
            in_quotes = not in_quotes
        elif char == ' ' and not in_quotes:
            if current_token != "":
                tokens.append(current_token)
                current_token = ""
        else:
            current_token += char
    if current_token != "":
        tokens.append(current_token)
    return tokens

