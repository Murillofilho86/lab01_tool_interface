"""
EXEMPLO 2 — ANTHROPIC-SCHEMA CLIENT TOOL (schema pronto, execução sua)

Cenário: "Tem um bug no meu primes.py. Conserta pra mim."

A DIFERENÇA PARA O EXEMPLO 1:
Aqui você NÃO escreve name, description nem input_schema. Declara só:

    {"type": "text_editor_20250728", "name": "str_replace_based_edit_tool"}

O schema é treinado dentro do modelo. Mas o loop é IDÊNTICO ao do
exemplo 1: chega tool_use, seu código executa, você devolve tool_result.
Anthropic dá o contrato; o handler continua sendo seu.

POR QUE USAR O OFICIAL EM VEZ DE CRIAR O SEU:
Um edit_file() seu funcionaria, mas o modelo viu str_replace_based_edit_tool
milhares de vezes no treino. Schema treinado > schema improvisado.

E por que é client tool e não server tool: você quer auditar e restringir
o que é escrito no seu disco. Execução no cliente é inegociável aqui.

Rodar:  pip install anthropic  &&  export ANTHROPIC_API_KEY=...
        python exemplo_2_editor.py
"""

import pathlib
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-opus-5"

# Confinamento: o modelo NÃO escreve fora daqui. Sem isso, um path
# "../../etc/passwd" vira problema de segurança de verdade.
WORKDIR = pathlib.Path("./sandbox").resolve()
WORKDIR.mkdir(exist_ok=True)


def _resolver(path: str) -> pathlib.Path:
    p = (WORKDIR / path.lstrip("/")).resolve()
    if not p.is_relative_to(WORKDIR):
        raise PermissionError(f"caminho fora do diretório permitido: {path}")
    return p


# ==========================================================================
# OS 4 COMANDOS QUE VOCÊ PRECISA IMPLEMENTAR
# (undo_edit NÃO existe no text_editor_20250728 — só no Sonnet 3.7, obsoleto)
# ==========================================================================

def cmd_view(path: str, view_range=None, **_) -> str:
    p = _resolver(path)
    if p.is_dir():
        return "\n".join(sorted(f.name for f in p.iterdir()))
    linhas = p.read_text(encoding="utf-8").splitlines()
    inicio, fim = 1, len(linhas)
    if view_range:
        inicio, fim = view_range
        fim = len(linhas) if fim == -1 else fim
    # Numerar as linhas é essencial: o insert usa número de linha.
    return "\n".join(f"{i}\t{linhas[i - 1]}" for i in range(inicio, fim + 1))


def cmd_str_replace(path: str, old_str: str, new_str: str = "", **_) -> str:
    p = _resolver(path)
    conteudo = p.read_text(encoding="utf-8")
    ocorrencias = conteudo.count(old_str)
    if ocorrencias == 0:
        raise ValueError("old_str não encontrado — o texto precisa bater exatamente")
    if ocorrencias > 1:
        raise ValueError(f"old_str aparece {ocorrencias} vezes; precisa ser único")
    p.write_text(conteudo.replace(old_str, new_str), encoding="utf-8")
    return f"Editado: {path}"


def cmd_create(path: str, file_text: str, **_) -> str:
    p = _resolver(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(file_text, encoding="utf-8")
    return f"Criado: {path}"


def cmd_insert(path: str, insert_line: int, new_str=None, insert_text=None, **_) -> str:
    # ATENÇÃO — bug conhecido: a documentação diz que o campo é new_str,
    # mas o modelo frequentemente emite insert_text. Aceite os dois.
    texto = new_str if new_str is not None else insert_text
    if texto is None:
        raise ValueError("faltou new_str/insert_text")

    p = _resolver(path)
    linhas = p.read_text(encoding="utf-8").splitlines(keepends=True)
    if not texto.endswith("\n"):
        texto += "\n"
    linhas.insert(insert_line, texto)   # insert_line=0 insere no topo
    p.write_text("".join(linhas), encoding="utf-8")
    return f"Inserido em {path}:{insert_line}"


COMANDOS = {
    "view": cmd_view,
    "str_replace": cmd_str_replace,
    "create": cmd_create,
    "insert": cmd_insert,
}


def executar_editor(block):
    """Dispatcher. Mesma estrutura do exemplo 1, mas roteia por 'command'
    em vez de por nome de tool — é uma tool só com 4 operações."""
    entrada = dict(block.input)
    comando = entrada.pop("command", None)
    try:
        if comando not in COMANDOS:
            raise ValueError(f"comando não suportado: {comando}")
        conteudo = COMANDOS[comando](**entrada)
        return {"type": "tool_result", "tool_use_id": block.id, "content": conteudo}
    except Exception as e:
        # Devolver o erro AO MODELO é o que permite ele se corrigir sozinho:
        # str_replace que não bateu vira um novo view e uma nova tentativa.
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": f"{type(e).__name__}: {e}",
            "is_error": True,
        }


# ==========================================================================
# O LOOP — repare que é o MESMO do exemplo 1
# ==========================================================================

def editar(pedido: str, max_iteracoes: int = 15):
    messages = [{"role": "user", "content": pedido}]

    for i in range(max_iteracoes):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            tools=[{
                "type": "text_editor_20250728",
                "name": "str_replace_based_edit_tool",
                "max_characters": 10000,   # trunca view de arquivo gigante
            }],
            messages=messages,
        )

        chamadas = [b for b in resp.content if b.type == "tool_use"]
        print(f"\n── rodada {i + 1} | stop_reason={resp.stop_reason}")
        for b in chamadas:
            print(f"     → {b.input.get('command')}  {b.input.get('path')}")

        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            texto = "".join(b.text for b in resp.content if b.type == "text")
            print("\n" + "═" * 70 + f"\nRESPOSTA FINAL\n{'═' * 70}\n{texto}")
            return texto

        messages.append({
            "role": "user",
            "content": [executar_editor(b) for b in chamadas],
        })

    raise RuntimeError("max_iteracoes atingido")


if __name__ == "__main__":
    # Arquivo com um bug plantado: 'range(2, n)' devia ser 'range(2, int(n**0.5)+1)'
    # e falta o caso n < 2.
    (WORKDIR / "primes.py").write_text(
        "def is_prime(n):\n"
        "    for i in range(2, n):\n"
        "        if n % i == 0:\n"
        "            return False\n"
        "    return True\n"
        "\n"
        "print([n for n in range(20) if is_prime(n)])\n",
        encoding="utf-8",
    )

    editar(
        "O arquivo primes.py está retornando True para 0 e 1, e está lento "
        "para números grandes. Examine e corrija."
    )

    print("\n--- arquivo depois ---")
    print((WORKDIR / "primes.py").read_text(encoding="utf-8"))

# ==========================================================================
# O QUE OBSERVAR
# ==========================================================================
#
# rodada 1 → view        primes.py     ele LÊ antes de editar
# rodada 2 → str_replace primes.py     conserta o range
# rodada 3 → str_replace primes.py     adiciona o guard n < 2
# rodada 4 → texto final               explica o que mudou
#
# Compare com o exemplo 1:
#   - lá você escreveu 3 schemas (~60 linhas de description)
#   - aqui você escreveu 0 schemas, só 4 handlers
#   - o loop é literalmente o mesmo código
#
# É essa a diferença entre as duas categorias. Nada mais.