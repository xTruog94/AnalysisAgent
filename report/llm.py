import json
from openai import OpenAI
    

class Reporter():
    def __init__(self, model: str = "gpt-40"):
        self.client = OpenAI()
        self.model = model
        
    def create_report(self, prompt, data):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                "role": "system",
                "content": f"""
            {prompt}
                """
                },
                {
                    "role": "user",
                    "content": f"analyze this data: {data}"
                }
                ],
            temperature=1.0,
            max_tokens=int(1000),
            top_p=int(0.8),
        )
        return response.choices[0].message.content
    