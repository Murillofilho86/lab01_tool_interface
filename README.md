
## Python

Python 3.14 or newer.

Verify:

```bash
python --version
```

---

## Create a virtual environment

```bash
python -m venv .venv
```

---


## Activate the virtual environment

### Linux / macOS

```bash
source .venv/bin/activate
```



cd lab01_tool_interface
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

python NOME_PROJETO.py                           # v1 e v2, 1 rodada
NOME_PROJETO.py --repeticoes 5                   # variância: seleção não é determinística
NOME_PROJETO.py --model claude-haiku-4-5-20251001   # o desenho importa mais em modelo menor?
NOME_PROJETO.py --forcar                         # Parte C: tool_choice