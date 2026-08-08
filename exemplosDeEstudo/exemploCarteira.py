"""
EXEMPLO 1 — USER-DEFINED TOOLS (você escreve schema + implementação)

Cenário: "Quais das minhas ações caíram mais de 5% essa semana
          e tiveram notícia ruim?"

POR QUE ISSO PRECISA DE UM LLM:
O fluxo de controle depende do DADO, não do código.
Você não sabe, antes de rodar:
  - quantas ações tem na carteira
  - quais delas caíram
  - quantas chamadas de notícia serão feitas (0? 2? 7?)
  - se uma notícia é "ruim" (isso é julgamento, não filtro)

Um script tradicional exigiria um if/else para cada pergunta possível.
Aqui você escreve 3 tools e o modelo compõe a sequência sozinho.

Rodar:  pip install anthropic  &&  export ANTHROPIC_API_KEY=...
        python exemplo_1_carteira.py
"""

import json
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-opus-5"

# ==========================================================================
# METADE 2 — IMPLEMENTAÇÃO (dados falsos para o exemplo rodar sem API paga)
# ==========================================================================

_CARTEIRA = {
    "PETR4.SA": 200, "VALE3.SA": 150, "ITUB4.SA": 300,
    "MGLU3.SA": 1000, "AAPL": 50, "NVDA": 25,
}

_SEMANA = {  # variação % nos últimos 7 dias
    "PETR4.SA": -1.2, "VALE3.SA": -7.8, "ITUB4.SA": +2.1,
    "MGLU3.SA": -12.4, "AAPL": +3.5, "NVDA": -5.9,
}

_NOTICIAS = {
    "VALE3.SA": [
        {"data": "2026-08-04", "titulo": "Vale reduz projeção de produção de minério para 2026"},
        {"data": "2026-08-05", "titulo": "Minério de ferro recua com desaceleração da China"},
    ],
    "MGLU3.SA": [
        {"data": "2026-08-03", "titulo": "Magazine Luiza reporta prejuízo acima do esperado no 2T"},
        {"data": "2026-08-06", "titulo": "Analistas cortam preço-alvo após margem pressionada"},
    ],
    "NVDA": [
        {"data": "2026-08-05", "titulo": "Nvidia anuncia expansão de datacenter na Europa"},
        {"data": "2026-08-06", "titulo": "Setor de chips recua junto com o índice, sem notícia específica"},
    ],
}


def get_portfolio() -> str:
    """Devolve as posições do usuário."""
    return json.dumps({
        "posicoes": [{"ticker": t, "quantidade": q} for t, q in _CARTEIRA.items()]
    })


def get_weekly_performance(ticker: str) -> str:
    """Variação percentual do papel nos últimos 7 dias."""
    if ticker not in _SEMANA:
        raise ValueError(f"ticker desconhecido: {ticker}")
    return json.dumps({
        "ticker": ticker,
        "variacao_pct_7d": _SEMANA[ticker],
        "as_of": "2026-08-07T18:00:00Z",   # sempre devolva a IDADE do dado
    })


def get_stock_news(ticker: str, days: int = 7) -> str:
    """Manchetes recentes do papel. NÃO classifica sentimento de propósito:
    julgar se a notícia é 'ruim' é trabalho do modelo, não da função."""
    return json.dumps({
        "ticker": ticker,
        "janela_dias": days,
        "noticias": _NOTICIAS.get(ticker, []),
    })


# ==========================================================================
# METADE 1 — CONTRATO (o único texto que o Claude enxerga)
# ==========================================================================

TOOLS = [
    {
        "name": "get_portfolio",
        "description": (
            "Retorna todas as posições em carteira do usuário autenticado, com "
            "ticker e quantidade. Chame SEMPRE primeiro quando o usuário falar de "
            "'minhas ações', 'minha carteira' ou 'meus papéis' — você não sabe "
            "quais papéis ele possui sem esta chamada. Não retorna preços nem "
            "preço médio de compra."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_weekly_performance",
        "description": (
            "Retorna a variação percentual de UM papel nos últimos 7 dias corridos. "
            "Valor negativo significa queda. Chame uma vez por ticker — para "
            "analisar vários papéis, faça várias chamadas em paralelo. O campo "
            "as_of traz o horário da apuração: repasse-o ao usuário em vez de "
            "dizer 'agora'. Não retorna preço absoluto nem histórico mais longo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Símbolo oficial em maiúsculas, ex: 'PETR4.SA', 'AAPL'",
                }
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_stock_news",
        "description": (
            "Retorna as manchetes publicadas sobre um papel na janela indicada. "
            "Devolve apenas título e data — NÃO classifica se a notícia é boa ou "
            "ruim; essa avaliação é sua. Use com parcimônia: chame somente para "
            "os papéis que já se mostraram relevantes na análise, não para a "
            "carteira inteira. Lista vazia significa ausência de notícia no período."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Símbolo oficial em maiúsculas"},
                "days": {
                    "type": "integer",
                    "description": "Janela em dias corridos. Padrão 7, máximo 30.",
                },
            },
            "required": ["ticker"],
        },
    },
]

# O elo entre as duas metades: nome no schema -> função Python
TOOL_FUNCTIONS = {
    "get_portfolio": get_portfolio,
    "get_weekly_performance": get_weekly_performance,
    "get_stock_news": get_stock_news,
}


def executar_tool(block):
    """Roda uma tool e embala o resultado. Nunca deixa exception vazar:
    erro vira tool_result com is_error=True para o modelo se recuperar."""
    try:
        resultado = TOOL_FUNCTIONS[block.name](**block.input)
        return {"type": "tool_result", "tool_use_id": block.id, "content": resultado}
    except Exception as e:
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"Erro em {block.name}: {e}",
            "is_error": True,
        }


# ==========================================================================
# O LOOP AGÊNTICO
# ==========================================================================

SYSTEM = (
    "Você é um assistente de análise de carteira. Baseie TODA afirmação "
    "numérica em resultado de tool — nunca em memória. Ao concluir, cite o "
    "as_of dos dados. Se uma notícia for ambígua, diga que é ambígua em vez "
    "de forçar uma classificação."
)


def perguntar(pergunta: str, max_iteracoes: int = 12):
    messages = [{"role": "user", "content": pergunta}]

    for i in range(max_iteracoes):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )

        # --- trace didático: mostra o que o modelo decidiu nesta rodada ---
        chamadas = [b for b in resp.content if b.type == "tool_use"]
        print(f"\n── rodada {i + 1} | stop_reason={resp.stop_reason} "
              f"| {len(chamadas)} tool(s)")
        for b in chamadas:
            print(f"     → {b.name}({json.dumps(b.input, ensure_ascii=False)})")

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            texto = "".join(b.text for b in resp.content if b.type == "text")
            print("\n" + "═" * 70 + f"\nRESPOSTA FINAL\n{'═' * 70}\n{texto}")
            return texto

        # Várias tools podem vir na mesma rodada (parallel tool use):
        # TODOS os resultados vão numa única mensagem user.
        messages.append({
            "role": "user",
            "content": [executar_tool(b) for b in chamadas],
        })

    raise RuntimeError("max_iteracoes atingido — possível loop infinito")


if __name__ == "__main__":
    perguntar(
        "Quais das minhas ações caíram mais de 5% essa semana "
        "e tiveram notícia ruim?"
    )

# ==========================================================================
# O QUE OBSERVAR NO TRACE
# ==========================================================================
#
# rodada 1 → get_portfolio()                      1 chamada
# rodada 2 → get_weekly_performance() x6          6 em PARALELO, uma por papel
# rodada 3 → get_stock_news() x2 ou x3            SÓ para quem caiu >5%
# rodada 4 → texto final                          síntese com julgamento
#
# Repare em três coisas:
#
# 1. A rodada 3 tem 2 ou 3 chamadas, não 6. O modelo filtrou VALE3 (-7,8%),
#    MGLU3 (-12,4%) e NVDA (-5,9%) e descartou os outros três. Esse filtro
#    saiu do dado, não do seu código.
#
# 2. NVDA caiu 5,9% mas as manchetes são neutras/positivas. A resposta certa
#    é excluí-la. Nenhuma query SQL expressa "notícia ruim" — é julgamento
#    semântico, e é exatamente por isso que o LLM está aqui.
#
# 3. Se o usuário perguntar amanhã "e as que SUBIRAM com notícia boa?",
#    você não escreve UMA LINHA de código nova. As mesmas 3 tools atendem.
#    Essa é a utilidade que você estava procurando.