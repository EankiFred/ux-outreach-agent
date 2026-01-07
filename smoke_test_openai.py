from openai import OpenAI

client = OpenAI()

resp = client.responses.create(
    model="gpt-5-mini",
    input="Antworte mit genau 6 Wörtern: Läuft der OpenAI Zugriff?"
)

print(resp.output_text)
