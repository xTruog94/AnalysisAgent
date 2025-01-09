import json
from openai import OpenAI
    

class Reporter():
    def __init__(self, model: str = "gpt-4o"):
        self.client = OpenAI()
        self.model = model
      
    def call(self, system_prompt, user_content):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                "role": "system",
                "content": f"""
            {system_prompt}
                """
                },
                {
                    "role": "user",
                    "content": user_content
                }
                ],
            temperature=1.0,
            max_tokens=int(1000),
            top_p=int(0.8),
        )
        return response.choices[0].message.content
    
    def create_analyse_prompt(self, narrative:str, tweets:list):
        prompt = f"""
        You are a crypto analyst expert. Generate a concise tweet analysis based on the following inputs:

Trending Narrative: {narrative}
Token Tweets: {tweets}

Create a 2-3 sentences tweet that:
1. References the trending narrative
2. Analyzes the token's strength (WEAK/MEDIUM/STRONG) based on sentiment
3. Provides a clear market perspective

Use emojis appropriately and maintain a professional tone. Include $TOKEN cashtag.

Example Output:
📈 [Token analysis with narrative context]. [Sentiment and supporting evidence]. STRONG outlook as [specific reason]. $TOKEN

Remember to:
- Keep within Twitter character limit
- Be specific about why the sentiment is weak/medium/strong
- Connect the token to the broader narrative
- Use data points from the tweets to support your analysis
- Do not use hastags and emojis
        """
        return prompt
    
    def analyse(self, narrative:str, tweets:list):
        user_prompt = self.create_analyse_prompt(narrative, tweets)
        response = self.call(system_prompt= "", user_content= user_prompt)
        return response
    
    def make_report(self, name, ca = "", analyse = "", aisem_score = 0 ):
        return f"""
        ${name}

CA:{ca}

Narrative Trending: {analyse}

AISEM score: {aisem_score}

NFA.
        """
        
    def make_clarify(self, detail_score: list):
        return f"""
Detail score:
{"\n".join(detail_score)}
    """