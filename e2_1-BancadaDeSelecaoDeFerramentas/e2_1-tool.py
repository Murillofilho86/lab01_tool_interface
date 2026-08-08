# Saber parametros tools da requisição
# campos: name, descrition, input_schema
# Como identificar o bloco tool_use na resposta e ler o campo name

import os
import json
from pathlib import Path

import anthropic
from dotenv import load_dotenv


ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

api_key = os.environ["ANTHROPIC_API_KEY"]

client = anthropic.Anthropic(api_key=api_key)

tools=[
    {
        "name": "",
        "description":"",
        "input_schema":{}
    }
]