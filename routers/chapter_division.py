import requests
import json
import os
from dotenv import load_dotenv 
from openrouter import OpenRouter

load_dotenv()
 
api_key=os.getenv("OPENROUTER_API_KEY")

async def divide_into_chapters(pages):
    with OpenRouter(api_key=api_key) as client:
        response = client.chat.send(
            model="poolside/laguna-xs-2.1:free",
            messages=[
                {
                "role": "system", 
                "content": """
You are a structural text parsing engine for a book-reading application. 

Your task is to analyze raw text extracted from a PDF, identify the logical structural divisions (such as Chapters, Sections, or Modules), and extract their titles and exact starting page numbers.

### Operational Guidelines:
1. Review the entire text sequentially to locate structural headings.
2. Ignore header/footer noise, page numbers embedded in the text body, and artifacts caused by the PDF-to-text conversion.
3. Identify the true starting page for each division. If a chapter starts mid-page, attribute it to the page number where the heading physically appears.
4. Keep the exact naming convention used in the book (e.g., "Chapter 1: The Beginning" or "Module A - Introduction").

### Output Format:
You must respond exclusively in a valid JSON object matching the following structure. Do not include any conversational text, introductory remarks, or markdown wrapping outside of the JSON.

{
  "book_structure": [
    {
      "type": "chapter", 
      "title": "String",
      "page_number": Integer
    }
  ]
}
""" 
                },
                {
            "role": "user", 
            "content": f"Here are the pages: {pages}"
        }

            ],  
            # Example schema structure used by advanced endpoints
            response_format={"type": "json_object"}
        )

        print(response.choices[0].message.content)
        return response.choices[0].message.content