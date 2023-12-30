import openai
from os import getenv
from dotenv import load_dotenv

load_dotenv()

openai.api_key = getenv('OPENAI_API_KEY') 

with open("prompt.txt") as f:
    prompt = f.read()

conversation = [
{
    "role": "system", 
    "content": prompt
}
]
total_characters = 0

async def get_ai_response(input_text):
    global total_characters

    conversation.append({"role": "user", "content": input_text})
    total_characters = sum(len(d['content']) for d in conversation)

    while total_characters > 4000 and len(conversation) > 1:
        conversation.pop(1)

    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=conversation,
        max_tokens=250,
        temperature=1,
        top_p=0.9,
        frequency_penalty=1,
        presence_penalty=1
    )
    conversation.append({"role": "assistant", "content": response['choices'][0]['message']['content']})
    message = response['choices'][0]['message']['content']
    return message

if __name__ == "__main__":
    resp = get_ai_response("@tapu: what is the meaning of life?\n@swas: 42")
    print(resp)