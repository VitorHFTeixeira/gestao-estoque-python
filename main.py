# =====================================================================
# StockManager Pro - Controle de estoque
#
# Visão geral de como o arquivo está organizado (de cima para baixo):
#   1. Imports e janela principal
#   2. Identidade visual (cores, fontes e estilos)
#   3. Funções auxiliares (usadas por várias telas)
#   4. Layout principal (menu lateral, indicadores, tabela, painel lateral)
#   5. Produtos (carregar, cadastrar, editar, excluir)
#   6. Indicadores e alertas de estoque baixo
#   7. Movimentações (entrada e saída)
#   8. Histórico
#   9. Exportar CSV
#  10. Início da aplicação
#
# O acesso ao banco de dados é feito sempre pela função conectar(),
# que fica no arquivo database.py (na mesma pasta deste arquivo).
# =====================================================================
import csv
import hashlib
import json
import os
import secrets
import unicodedata
from datetime import datetime
import tkinter as tk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog
from database import conectar  # devolve a conexão com o banco (ou None se falhar)


# =====================================================================
# JANELA PRINCIPAL
# Todas as outras janelas (cadastro, edição, movimentação, histórico)
# são filhas desta "janela".
# =====================================================================
janela = tb.Window(
    title="StockManager Pro",
    themename="darkly",
    size=(1280, 760)
)

# Tamanho mínimo pequeno para o sistema funcionar em telas pequenas.
# O layout tem 3 modos conforme a largura da janela:
#   normal (>= 1100 px) | compacto (900 a 1099 px) | estreito (< 900 px)
# Quem troca de modo é a função aplicar_ajuste (lá embaixo).
janela.minsize(780, 520)


# =====================================================================
# IDENTIDADE VISUAL
#   Base neutra e escura. A cor âmbar/vermelha é reservada para o que
#   exige atenção (estoque baixo); o azul é usado só nas ações.
#   Bahnschrift (estilo DIN, comum em logística) nos títulos e números;
#   Segoe UI no texto corrido.
# =====================================================================
estilo = tb.Style()   # objeto que controla a aparência de todos os widgets
cores = estilo.colors  # cores do tema (cores.info, cores.warning, cores.danger...)

FONTE_TITULO = "Bahnschrift"
FONTE_TEXTO = "Segoe UI"

# Senha exigida para EDITAR e EXCLUIR produtos, APAGAR o histórico e
# ALTERAR a própria senha. Ela NÃO fica escrita no código: fica guardada
# "embaralhada" (hash) no arquivo senha.json, na mesma pasta deste arquivo.
# Enquanto esse arquivo não existir, vale a senha padrão abaixo. No primeiro
# uso, troque pelo menu "Alterar senha".
SENHA_PADRAO = "1234"
ARQUIVO_SENHA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "senha.json")

# Cores fixas que uso no sistema inteiro
COR_CARD = cores.bg        # fundo dos "cartões" (painéis)
COR_PAGINA = "#181818"     # fundo da página
COR_MENU = "#101010"       # fundo do menu lateral
COR_TEXTO = "#f2f2f2"
COR_MUTED = "#9a9a9a"      # texto secundário (cinza)
COR_LINHA = "#303030"      # linhas divisórias
COR_ZEBRA = "#292929"      # linhas alternadas da tabela
COR_CABECALHO = "#2b2b2b"  # cabeçalho das tabelas
COR_TRILHO = "#353535"     # fundo da barrinha de nível de estoque

# Estilos de frames e rótulos (usados com style="..." nos widgets)
estilo.configure("Page.TFrame", background=COR_PAGINA)
estilo.configure("Page.TLabel", background=COR_PAGINA, foreground=COR_TEXTO)
estilo.configure("PageMuted.TLabel", background=COR_PAGINA, foreground=COR_MUTED)
estilo.configure("Side.TFrame", background=COR_MENU)
estilo.configure("SideMuted.TLabel", background=COR_MENU, foreground=COR_MUTED)
estilo.configure("Muted.TLabel", background=COR_CARD, foreground=COR_MUTED)


def criar_estilo_menu(nome, fundo, texto, texto_hover):
    #Cria o estilo dos botões do menu lateral (normal e ativo).
    estilo.configure(
        nome,
        background=fundo,
        foreground=texto,
        bordercolor=fundo,
        darkcolor=fundo,
        lightcolor=fundo,
        focuscolor=fundo,
        relief="flat",
        borderwidth=0,
        anchor="w",
        padding=(18, 11),
        font=(FONTE_TEXTO, 11)
    )
    # Cores quando o mouse passa por cima / clica
    estilo.map(
        nome,
        background=[("pressed", COR_LINHA), ("active", COR_LINHA)],
        foreground=[("pressed", texto_hover), ("active", texto_hover)],
        bordercolor=[("pressed", COR_LINHA), ("active", COR_LINHA)],
        darkcolor=[("pressed", COR_LINHA), ("active", COR_LINHA)],
        lightcolor=[("pressed", COR_LINHA), ("active", COR_LINHA)]
    )


# Dois estilos: botão normal do menu e botão da página atual
criar_estilo_menu("Menu.TButton", COR_MENU, COR_MUTED, "white")
criar_estilo_menu("MenuAtivo.TButton", "#1d2630", cores.info, cores.info)

# Estilo padrão das tabelas (Treeview)
estilo.configure(
    "Treeview",
    background=COR_CARD,
    fieldbackground=COR_CARD,
    foreground=COR_TEXTO,
    rowheight=38,
    borderwidth=0,
    font=(FONTE_TEXTO, 10)
)
estilo.map(
    "Treeview",
    background=[("selected", cores.info)],
    foreground=[("selected", "white")]
)
estilo.configure(
    "Treeview.Heading",
    background=COR_CABECALHO,
    foreground=COR_MUTED,
    font=(FONTE_TEXTO, 9, "bold"),
    padding=(10, 10),
    relief="flat",
    borderwidth=0
)
estilo.map("Treeview.Heading", background=[("active", COR_LINHA)])

# Estilo da lista de produtos da tela de movimentação.
# Herda tudo do "Treeview" acima, só deixa as linhas um pouco mais baixas.
estilo.configure("Lista.Treeview", rowheight=32)


# =====================================================================
# FUNÇÕES AUXILIARES
# =====================================================================
def formatar_preco(valor):
    #Formata um número como moeda brasileira: R$ 1.234,56
    #Usada na tabela de produtos e no indicador 'Valor em estoque'.
    texto = f"{float(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def normalizar(texto):
    #Minúsculas e sem acentos, para a busca encontrar 'cafe' em 'Café'.
    #Usada na busca de produtos (movimentação) e nas sugestões de categoria.

    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def centralizar(janela_filha, largura, altura, min_largura=None, min_altura=None):
    # Posiciona uma janela secundária no centro da janela principal.
    # Se a tela for pequena, o tamanho é reduzido para caber.
    # Usada por: cadastro, edição, movimentação e histórico.
    janela.update_idletasks()

    # Nunca deixa a janela maior que a tela
    largura = min(largura, janela.winfo_screenwidth() - 40)
    altura = min(altura, janela.winfo_screenheight() - 100)

    x = janela.winfo_x() + (janela.winfo_width() - largura) // 2
    y = janela.winfo_y() + (janela.winfo_height() - altura) // 2
    janela_filha.geometry(f"{largura}x{altura}+{max(x, 0)}+{max(y, 0)}")

    # Tamanho mínimo: por padrão é o próprio tamanho (a janela só pode crescer)
    janela_filha.minsize(min_largura or largura, min_altura or altura)

    janela_filha.transient(janela)  # fica sempre na frente da principal
    janela_filha.focus_force()


def ajustar_quebra_texto(rotulo, container, margem=56):
    # Faz o texto do rótulo quebrar de linha conforme a largura do
    # container. É isso que deixa os textos responsivos nas janelas
    # que o usuário pode redimensionar.
     
    def ajustar(evento):
        rotulo.configure(wraplength=max(evento.width - margem, 120))

    container.bind("<Configure>", ajustar, add="+")


def barra_nivel(pai, proporcao, cor):
    # Barra fina que mostra o nível do estoque em relação ao mínimo.
    # Usada no painel 'Reposição urgente' (atualizar_alertas).
     
    quadro = tk.Canvas(
        pai,
        height=10,
        highlightthickness=0,
        bd=0,
        bg=COR_CARD
    )
    quadro.pack(fill=X, pady=(8, 0))

    def desenhar(evento=None):
        # Redesenha sempre que o tamanho muda (por isso acompanha a janela)
        quadro.delete("all")
        largura = max(quadro.winfo_width(), 1)
        quadro.create_rectangle(0, 0, largura, 10, fill=COR_TRILHO, outline="")
        quadro.create_rectangle(
            0, 0, largura * proporcao, 10, fill=cor, outline=""
        )

    quadro.bind("<Configure>", desenhar)


def buscar_categorias():
    # Lê do banco todas as categorias que já existem nos produtos.
    # Alimenta a lista de sugestões do campo Categoria (cadastro e edição)
    # e também serve para não criar categorias duplicadas.

    conexao = conectar()

    if conexao is None:
        return []

    cursor = None

    try:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT DISTINCT categoria
            FROM produtos
            WHERE categoria IS NOT NULL AND categoria <> ''
            ORDER BY categoria
        """)
        return [linha[0] for linha in cursor.fetchall()]

    except Exception as erro:
        print(f"Erro ao carregar categorias: {erro}")
        return []

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()


def criar_campos(formulario, itens):
    #Cria os campos de um formulário de produto.
    #Usada por abrir_cadastro e editar_produto.
    #O campo 'categoria' é uma caixa de seleção com as categorias já
    #existentes, mas o usuário também pode digitar uma categoria nova.
    campos = {}

    for chave, rotulo, valor in itens:
        tb.Label(formulario, text=rotulo).pack(anchor=W)

        if chave == "categoria":
            sugestoes = buscar_categorias()

            entrada = tb.Combobox(formulario, values=sugestoes)
            entrada.pack(fill=X, pady=(3, 10))

            # Enquanto digita, a lista mostra só as categorias parecidas
            def filtrar_sugestoes(evento, combo=entrada, todas=sugestoes):
                if evento.keysym in ("Up", "Down", "Return", "Tab", "Escape"):
                    return

                termo = normalizar(combo.get().strip())
                filtradas = [c for c in todas if termo in normalizar(c)]
                combo.configure(values=filtradas or todas)

            entrada.bind("<KeyRelease>", filtrar_sugestoes)

        else:
            entrada = tb.Entry(formulario)
            entrada.pack(fill=X, pady=(3, 10))

        if valor != "":
            entrada.insert(0, str(valor))

        campos[chave] = entrada

    return campos


def validar_produto(campos, parent):
    
    #Lê e valida os campos do produto.
    #Retorna (nome, categoria, quantidade, preco, estoque_minimo)
    #ou None se algum dado for inválido.
    #Usada por salvar_produto (cadastro) e salvar_edicao (edição).
  
    nome = campos["nome"].get().strip()
    categoria = campos["categoria"].get().strip()
    quantidade_texto = campos["quantidade"].get().strip()
    preco_texto = campos["preco"].get().strip().replace(",", ".")
    minimo_texto = campos["estoque_minimo"].get().strip()

    if not nome:
        messagebox.showwarning(
            "Atenção",
            "Informe o nome do produto.",
            parent=parent
        )
        return None

    try:
        quantidade = int(quantidade_texto)
        preco = float(preco_texto)
        estoque_minimo = int(minimo_texto)

        if quantidade < 0 or preco < 0 or estoque_minimo < 0:
            raise ValueError

    except ValueError:
        messagebox.showerror(
            "Dados inválidos",
            "Quantidade e estoque mínimo devem ser números inteiros; "
            "preço deve ser numérico. Os valores não podem ser negativos.",
            parent=parent
        )
        return None

    # Se a categoria digitada já existe (ignorando maiúsculas e acentos),
    # usa a grafia que já está no banco. Evita 'Teclados' e 'teclados'.
    for existente in buscar_categorias():
        if normalizar(existente) == normalizar(categoria):
            categoria = existente
            break

    return nome, categoria or None, quantidade, preco, estoque_minimo


def atualizar_tudo():
    #Recarrega tabela, indicadores e painel de reposição de uma vez.
    #Chamada depois de cadastrar, editar, excluir ou movimentar.
    carregar_produtos()
    atualizar_resumo()
    atualizar_alertas()


def mostrar_somente_baixo():
    #Liga o filtro 'Só estoque baixo' na tabela.
    #Chamada pelo botão 'Ver todos na tabela' do painel Reposição urgente.
    busca.set("")
    somente_baixo.set(True)
    carregar_produtos()


def limpar_filtros():
    # Liga o filtro 'Só estoque baixo' na tabela.
    # Chamada pelo botão 'Ver todos na tabela' do painel Reposição urgente.Botão 'Limpar' da busca: tira a busca e o filtro de estoque baixo.

    busca.set("")
    somente_baixo.set(False)
    carregar_produtos()


def gerar_hash(senha, sal):
    # Embaralha a senha junto com um 'sal' (PBKDF2-SHA256, 200 mil voltas).
    # O resultado não dá para desfazer: só dá para conferir se uma senha
    # digitada gera o mesmo hash. Usada por verificar_senha e salvar_senha.

    return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, 200_000).hex()


def ler_dados_senha():
    # Lê o sal e o hash guardados em senha.json.
    # Se o arquivo não existe ou está estragado, usa a senha padrão.
    # Usada por verificar_senha.

    try:
        with open(ARQUIVO_SENHA, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        return bytes.fromhex(dados["sal"]), dados["hash"]

    except (OSError, ValueError, KeyError, TypeError):
        sal_padrao = b"stockmanager-pro"
        return sal_padrao, gerar_hash(SENHA_PADRAO, sal_padrao)


def verificar_senha(senha_digitada):
    # Devolve True se a senha digitada é a senha atual.
    # Usada por pedir_senha e por abrir_alterar_senha.

    sal, hash_certo = ler_dados_senha()
    hash_digitado = gerar_hash(senha_digitada, sal)

    # compare_digest compara sem pistas de tempo (boa prática para senhas)
    return secrets.compare_digest(hash_digitado, hash_certo)


def salvar_senha(nova_senha):
    # Grava a nova senha (já embaralhada, com um sal novo) em senha.json.
    # Usada por abrir_alterar_senha.

    sal = secrets.token_bytes(16)

    with open(ARQUIVO_SENHA, "w", encoding="utf-8") as arquivo:
        json.dump(
            {"sal": sal.hex(), "hash": gerar_hash(nova_senha, sal)},
            arquivo
        )


def pedir_senha(acao, pai=None):
    #Abre uma janelinha pedindo a senha (os caracteres aparecem como ●).
    #'acao' é só o texto mostrado, ex.: 'editar este produto'.
    #'pai' é a janela que fica por baixo do pedido (se não for informada,
    #é a janela principal). O Histórico informa a própria janela.
    #Devolve True se a senha estiver certa e False se cancelar.
    #Usada por: editar_produto, excluir_produto, apagar_historico e
    #abrir_alterar_senha. Depois de 3 senhas erradas a janela se fecha.

    resultado = {"ok": False, "erros": 0}  # 'erros' conta as tentativas erradas

    dialogo = tb.Toplevel(pai or janela)
    dialogo.title("Senha necessária")
    dialogo.resizable(False, False)
    centralizar(dialogo, 380, 290)
    dialogo.transient(pai or janela)  # fica sempre na frente da janela dona

    corpo_dialogo = tb.Frame(dialogo, padding=28)
    corpo_dialogo.pack(fill=BOTH, expand=True)

    tb.Label(
        corpo_dialogo,
        text="Senha necessária",
        font=(FONTE_TITULO, 18)
    ).pack(anchor=W)

    tb.Label(
        corpo_dialogo,
        text=f"Digite a senha para {acao}.",
        font=(FONTE_TEXTO, 10),
        style="Muted.TLabel",
        wraplength=320
    ).pack(anchor=W, pady=(2, 14))

    campo_senha = tb.Entry(corpo_dialogo, show="●")
    campo_senha.pack(fill=X)

    def confirmar(evento=None):
        # Confere com a senha guardada (veja verificar_senha)
        if verificar_senha(campo_senha.get()):
            resultado["ok"] = True
            dialogo.destroy()
            return

        resultado["erros"] += 1

        # 3 erros: fecha o pedido de senha
        if resultado["erros"] >= 3:
            messagebox.showerror(
                "Acesso negado",
                "Número de tentativas excedido.",
                parent=dialogo
            )
            dialogo.destroy()
            return

        messagebox.showerror(
            "Senha incorreta",
            f"A senha informada está incorreta. Tentativa {resultado['erros']} de 3.",
            parent=dialogo
        )
        campo_senha.delete(0, END)
        campo_senha.focus_set()

    tb.Button(
        corpo_dialogo,
        text="Confirmar",
        bootstyle="info",
        command=confirmar
    ).pack(fill=X, pady=(16, 0))

    tb.Button(
        corpo_dialogo,
        text="Cancelar",
        bootstyle="secondary-outline",
        command=dialogo.destroy
    ).pack(fill=X, pady=(8, 0))

    dialogo.bind("<Return>", confirmar)
    dialogo.bind("<Escape>", lambda evento: dialogo.destroy())

    campo_senha.focus_set()
    dialogo.wait_visibility()
    dialogo.grab_set()           # trava a janela principal até responder
    janela.wait_window(dialogo)  # espera o usuário confirmar ou cancelar

    return resultado["ok"]


# =====================================================================
# LAYOUT PRINCIPAL
# =====================================================================
conteudo = tb.Frame(janela, style="Page.TFrame")
conteudo.pack(fill=BOTH, expand=True)

# Variáveis dos filtros (lidas por carregar_produtos)
busca = tb.StringVar()
somente_baixo = tb.BooleanVar(value=False)


# ---------------------------------------------------------------------
# Menu lateral
# ---------------------------------------------------------------------
menu = tb.Frame(conteudo, style="Side.TFrame", width=250)

# Marca: três barras de nível, a menor em âmbar (estoque baixo)
marca = tk.Canvas(menu, width=40, height=30, bg=COR_MENU, highlightthickness=0, bd=0)
marca.create_rectangle(0, 18, 9, 30, fill=cores.warning, outline="")
marca.create_rectangle(15, 9, 24, 30, fill=cores.info, outline="")
marca.create_rectangle(30, 0, 39, 30, fill=cores.info, outline="")

nome_app = tb.Label(
    menu,
    text="StockManager",
    font=(FONTE_TITULO, 19),
    background=COR_MENU,
    foreground=COR_TEXTO
)

sub_app = tb.Label(
    menu,
    text="Controle de estoque",
    font=(FONTE_TEXTO, 10),
    style="SideMuted.TLabel"
)

separador_menu = tk.Frame(menu, bg=COR_LINHA, height=1)

# Botões do menu: (texto, função chamada ao clicar, é a página atual?)
# As funções usam lambda porque ainda não foram definidas neste ponto
# do arquivo (elas aparecem mais abaixo).

linhas_menu = []

for texto_botao, comando_botao, ativo in [
    ("Visão geral", lambda: atualizar_tudo(), True),
    ("Produtos", lambda: campo_busca.focus_set(), False),
    ("Movimentações", lambda: abrir_movimentacoes(), False),
    ("Histórico", lambda: abrir_historico(), False),
    ("Exportar CSV", lambda: exportar_csv(), False),
    ("Alterar senha", lambda: abrir_alterar_senha(), False),
]:
    linha_menu = tb.Frame(menu, style="Side.TFrame")

    # Faixa à esquerda: indica a página atual
    tk.Frame(
        linha_menu,
        bg=cores.info if ativo else COR_MENU,
        width=3
    ).pack(side=LEFT, fill=Y)

    tb.Button(
        linha_menu,
        text=texto_botao,
        style="MenuAtivo.TButton" if ativo else "Menu.TButton",
        command=comando_botao
    ).pack(side=LEFT, fill=X, expand=True)

    linhas_menu.append(linha_menu)

versao_app = tb.Label(
    menu,
    text="Versão 2.0",
    font=(FONTE_TEXTO, 9),
    style="SideMuted.TLabel"
)


def montar_menu(horizontal):
    # Organiza o menu de dois jeitos:
    # - horizontal=False: coluna na lateral esquerda (modos normal e compacto)
    # - horizontal=True: barra no topo da tela (modo estreito)
    # É chamada na montagem inicial (abaixo) e por aplicar_ajuste, quando a
    # janela muda de tamanho.
    
    # Tira tudo da tela para reorganizar na ordem certa

    for elemento in [marca, nome_app, sub_app, separador_menu, versao_app] + linhas_menu:
        elemento.pack_forget()

    if horizontal:
        menu.pack_configure(side=TOP, fill=X)
        menu.pack_propagate(True)  # a altura passa a ser a dos botões

        # Nesta barra o nome do app não aparece, para caberem os 6 botões.
        for linha in linhas_menu:
            linha.pack(side=LEFT, pady=4)
    else:
        menu.pack_configure(side=LEFT, fill=Y)
        menu.pack_propagate(False)  # mantém a largura que defini

        nome_app.configure(font=(FONTE_TITULO, 19))
        marca.pack(anchor=W, padx=24, pady=(32, 8))
        nome_app.pack(anchor=W, padx=24)
        sub_app.pack(anchor=W, padx=24, pady=(0, 6))
        separador_menu.pack(fill=X, padx=24, pady=(18, 14))

        for linha in linhas_menu:
            linha.pack(fill=X, pady=1)

        versao_app.pack(side=BOTTOM, anchor=W, padx=24, pady=18)


# O menu é o primeiro item do 'conteudo'; 'principal' (abaixo) ocupa o resto.
menu.pack(side=LEFT, fill=Y)
montar_menu(False)


# ---------------------------------------------------------------------
# Área principal (tudo que fica à direita do menu)
# ---------------------------------------------------------------------
principal = tb.Frame(conteudo, style="Page.TFrame", padding=(30, 26))
principal.pack(side=LEFT, fill=BOTH, expand=True)

# Cabeçalho: título à esquerda e botão 'Novo produto' à direita
cabecalho = tb.Frame(principal, style="Page.TFrame")
cabecalho.pack(fill=X)

titulos = tb.Frame(cabecalho, style="Page.TFrame")
titulos.pack(side=LEFT)

titulo_pagina = tb.Label(  # guardado para o tamanho da fonte mudar no modo estreito
    titulos,
    text="Visão geral",
    font=(FONTE_TITULO, 26),
    style="Page.TLabel"
)
titulo_pagina.pack(anchor=W)

tb.Label(
    titulos,
    text=f"Situação do estoque em {datetime.now():%d/%m/%Y}",
    font=(FONTE_TEXTO, 11),
    style="PageMuted.TLabel"
).pack(anchor=W)

tb.Button(
    cabecalho,
    text="Novo produto",
    bootstyle="info",
    padding=(18, 10),
    command=lambda: abrir_cadastro()  # abre a janela de cadastro
).pack(side=RIGHT, anchor=N)


# Faixa de indicadores: um único bloco dividido em 3 colunas iguais.
# O 'Estoque baixo' NÃO fica mais aqui: agora aparece só no painel lateral
# 'Reposição urgente'.
# valores_resumo guarda os rótulos dos números para a função
# atualizar_resumo() trocar o texto depois.
valores_resumo = {}
blocos_faixa = []  # os 3 blocos, guardados para o padding mudar no modo estreito

faixa = tb.Frame(principal)
faixa.pack(fill=X, pady=(22, 16))

for posicao, (chave, titulo, subtitulo) in enumerate([
    ("total", "Produtos cadastrados", "itens no catálogo"),
    ("movs", "Movimentações", "entradas e saídas registradas"),
    ("valor", "Valor em estoque", "quantidade vezes preço"),
]):
    # Cada bloco ocupa uma coluna par (0, 2, 4); as colunas ímpares (1, 3)
    # guardam as linhas divisórias. Usando grid com 'weight' e 'uniform',
    # os 3 blocos dividem a largura por igual quando a janela muda de tamanho.
    coluna = posicao * 2

    if posicao > 0:
        tk.Frame(faixa, bg=COR_LINHA, width=1).grid(
            row=0, column=coluna - 1, sticky="ns", pady=16
        )

    bloco = tb.Frame(faixa, padding=(26, 16))
    bloco.grid(row=0, column=coluna, sticky="nsew")
    blocos_faixa.append(bloco)
    faixa.columnconfigure(coluna, weight=1, uniform="indicadores")

    tb.Label(
        bloco,
        text=titulo,
        font=(FONTE_TEXTO, 10),
        style="Muted.TLabel"
    ).pack(anchor=W)

    rotulo_valor = tb.Label(
        bloco,
        text="0",
        font=(FONTE_TITULO, 28),
        foreground=COR_TEXTO
    )
    rotulo_valor.pack(anchor=W, pady=(2, 0))

    tb.Label(
        bloco,
        text=subtitulo,
        font=(FONTE_TEXTO, 9),
        style="Muted.TLabel"
    ).pack(anchor=W)

    valores_resumo[chave] = rotulo_valor  # atualizar_resumo() usa isto


# Corpo: tabela de produtos à esquerda, reposição urgente à direita.
# Uso grid: a coluna da tabela (0) cresce com a janela (weight=1) e a
# coluna do painel de alertas (1) mantém a largura dela.
corpo = tb.Frame(principal, style="Page.TFrame")
corpo.pack(fill=BOTH, expand=True)
corpo.columnconfigure(0, weight=1)
corpo.rowconfigure(0, weight=1)

painel_tabela = tb.Frame(corpo, padding=22)
painel_tabela.grid(row=0, column=0, sticky="nsew")

painel_alerta = tb.Frame(corpo, padding=22, width=330)
painel_alerta.grid(row=0, column=1, sticky="ns", padx=(16, 0))
painel_alerta.pack_propagate(False)  # mantém a largura (muda no modo compacto)


# ---------------------------------------------------------------------
# Painel de reposição urgente (lado direito)
# O conteúdo é montado pela função atualizar_alertas()
# ---------------------------------------------------------------------
tb.Label(
    painel_alerta,
    text="Reposição urgente",
    font=(FONTE_TITULO, 16)
).pack(anchor=W)

tb.Label(
    painel_alerta,
    text="Produtos no estoque mínimo ou abaixo dele.",
    font=(FONTE_TEXTO, 9),
    style="Muted.TLabel"
).pack(anchor=W)

lista_alertas = tb.Frame(painel_alerta)  # aqui dentro entram os itens em alerta
lista_alertas.pack(fill=BOTH, expand=True, pady=(18, 0))


# ---------------------------------------------------------------------
# Painel da tabela de produtos (lado esquerdo)
# ---------------------------------------------------------------------
cabecalho_tabela = tb.Frame(painel_tabela)
cabecalho_tabela.pack(fill=X)

tb.Label(
    cabecalho_tabela,
    text="Produtos",
    font=(FONTE_TITULO, 16)
).pack(side=LEFT)

# Texto "X produto(s) na lista" (preenchido em carregar_produtos)
info_tabela = tb.Label(
    cabecalho_tabela,
    text="",
    font=(FONTE_TEXTO, 9),
    style="Muted.TLabel"
)
info_tabela.pack(side=RIGHT)

# Busca e filtros
linha_busca = tb.Frame(painel_tabela)
linha_busca.pack(fill=X, pady=(14, 12))

tb.Label(
    linha_busca,
    text="Buscar",
    font=(FONTE_TEXTO, 10),
    style="Muted.TLabel"
).pack(side=LEFT, padx=(0, 10))

campo_busca = tb.Entry(linha_busca, textvariable=busca)
campo_busca.pack(side=LEFT, fill=X, expand=True)

tb.Checkbutton(
    linha_busca,
    text="Só estoque baixo",
    variable=somente_baixo,
    bootstyle="warning-round-toggle",
    command=lambda: carregar_produtos()
).pack(side=LEFT, padx=(16, 0))

tb.Button(
    linha_busca,
    text="Limpar",
    bootstyle="secondary-outline",
    command=limpar_filtros
).pack(side=LEFT, padx=(10, 0))

# Toda vez que o texto da busca muda, a tabela é recarregada
busca.trace_add("write", lambda *args: carregar_produtos())


# Botões de ação ficam embaixo da tabela. Eu os coloco ANTES da tabela no
# código (com side=BOTTOM) para que eles nunca sumam quando a janela
# ficar pequena: quem sobra de espaço é a tabela.

acoes = tb.Frame(painel_tabela)
acoes.pack(side=BOTTOM, fill=X, pady=(14, 0))

tb.Button(
    acoes,
    text="Movimentar estoque",
    bootstyle="success",
    command=lambda: abrir_movimentacoes()
).pack(side=LEFT, padx=(0, 10))

tb.Button(
    acoes,
    text="Editar",
    bootstyle="warning-outline",
    command=lambda: editar_produto()
).pack(side=LEFT, padx=(0, 10))

tb.Button(
    acoes,
    text="Excluir",
    bootstyle="danger-outline",
    command=lambda: excluir_produto()
).pack(side=LEFT)


# Tabela de produtos
tabela_frame = tb.Frame(painel_tabela)
tabela_frame.pack(fill=BOTH, expand=True)

tabela = tb.Treeview(
    tabela_frame,
    columns=("id", "nome", "categoria", "quantidade", "preco", "status"),
    show="headings",
    height=10
)

barra_rolagem = tb.Scrollbar(
    tabela_frame,
    orient=VERTICAL,
    command=tabela.yview,
    bootstyle="round"
)
tabela.configure(yscrollcommand=barra_rolagem.set)

for coluna, texto in [
    ("id", "ID"),
    ("nome", "Produto"),
    ("categoria", "Categoria"),
    ("quantidade", "Quantidade"),
    ("preco", "Preço"),
    ("status", "Situação")
]:
    tabela.heading(coluna, text=texto)

# Responsivo: a coluna 'Produto' (e a categoria) esticam quando a janela
# cresce; as demais têm largura fixa. 'minwidth' permite encolher bastante
# quando a janela fica pequena.
tabela.column("id", width=50, minwidth=40, anchor=CENTER, stretch=False)
tabela.column("nome", width=230, minwidth=120, stretch=True)
tabela.column("categoria", width=130, minwidth=80, stretch=True)
tabela.column("quantidade", width=90, minwidth=70, anchor=CENTER, stretch=False)
tabela.column("preco", width=110, minwidth=90, anchor=E, stretch=False)
tabela.column("status", width=90, minwidth=70, anchor=CENTER, stretch=False)

# Linhas alternadas e destaque de estoque baixo
tabela.tag_configure("zebra", background=COR_ZEBRA)
tabela.tag_configure("baixo", foreground=cores.warning)
tabela.tag_configure("falta", foreground=cores.danger)  # quantidade 0 = vermelho

tabela.pack(side=LEFT, fill=BOTH, expand=True)
barra_rolagem.pack(side=RIGHT, fill=Y)


def duplo_clique_tabela(evento):
    """Duplo clique em uma linha abre a edição do produto."""
    # Só abre a edição se o clique foi em uma linha (não no cabeçalho)
    if tabela.identify_region(evento.x, evento.y) == "cell":
        editar_produto()


tabela.bind("<Double-1>", duplo_clique_tabela)


# =====================================================================
# PRODUTOS: CARREGAR, CADASTRAR, EDITAR E EXCLUIR
# =====================================================================
def carregar_produtos():
    # Busca os produtos no banco e preenche a tabela principal.
    # Respeita a busca (variável 'busca') e o filtro 'Só estoque baixo'.
    # Chamada por: atualizar_tudo, busca, filtros e pelo início do programa.

    # Limpa a tabela antes de preencher de novo

    for item in tabela.get_children():
        tabela.delete(item)

    termo = f"%{busca.get().strip()}%"

    # Monto o WHERE aos poucos: sempre tem a busca, e às vezes o filtro de baixo
    condicoes = ["(nome LIKE %s OR categoria LIKE %s)"]
    parametros = [termo, termo]

    if somente_baixo.get():
        condicoes.append("quantidade <= estoque_minimo")

    conexao = conectar()

    if conexao is None:
        return

    cursor = None

    try:
        cursor = conexao.cursor()

        # ORDER BY id ASC: o produto de ID 1 fica em cima e a lista
        # vai crescendo para baixo (ordem crescente).
        cursor.execute(
            f"""
            SELECT id, nome, categoria, quantidade, preco, estoque_minimo
            FROM produtos
            WHERE {" AND ".join(condicoes)}
            ORDER BY id ASC
            """,
            tuple(parametros)
        )

        produtos = cursor.fetchall()

        for posicao, produto in enumerate(produtos):
            id_produto, nome, categoria, quantidade, preco, minimo = produto

            esta_baixo = quantidade <= minimo
            esta_em_falta = quantidade == 0  # zerou o estoque
            tags = []

            # Linhas alternadas (zebra) para facilitar a leitura
            if posicao % 2 == 1:
                tags.append("zebra")

            # Situação do produto: vermelho se zerou ('Em falta'),
            # âmbar se só está no mínimo ou abaixo ('Baixo'), senão 'Normal'
            if esta_em_falta:
                tags.append("falta")
                situacao = "Em falta"
            elif esta_baixo:
                tags.append("baixo")
                situacao = "Baixo"
            else:
                situacao = "Normal"

            tabela.insert(
                "",
                "end",
                values=(
                    id_produto,
                    nome,
                    categoria or "",
                    quantidade,
                    formatar_preco(preco),
                    situacao
                ),
                tags=tags
            )

        info_tabela.config(text=f"{len(produtos)} produto(s) na lista")

    except Exception as erro:
        print(f"Erro ao carregar produtos: {erro}")

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()


def abrir_cadastro():
    """Janela 'Novo produto'. Aberta pelo botão 'Novo produto' do cabeçalho."""
    cadastro = tb.Toplevel(janela)
    cadastro.title("Novo produto")
    cadastro.resizable(True, True)  # pode ser redimensionada
    centralizar(cadastro, 420, 560)

    formulario = tb.Frame(cadastro, padding=28)
    formulario.pack(fill=BOTH, expand=True)

    tb.Label(
        formulario,
        text="Novo produto",
        font=(FONTE_TITULO, 20)
    ).pack(anchor=W, pady=(0, 18))

    # criar_campos monta os campos; 'categoria' vira lista de sugestões
    campos = criar_campos(formulario, [
        ("nome", "Nome do produto", ""),
        ("categoria", "Categoria (escolha da lista ou digite uma nova)", ""),
        ("quantidade", "Quantidade inicial", ""),
        ("preco", "Preço (ex.: 99.90)", ""),
        ("estoque_minimo", "Estoque mínimo", "")
    ])

    campos["nome"].focus_set()

    def salvar_produto():
        """Valida os dados e grava o produto novo no banco."""
        dados = validar_produto(campos, cadastro)

        if dados is None:
            return

        conexao = conectar()

        if conexao is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível conectar ao banco de dados.",
                parent=cadastro
            )
            return

        cursor = None

        try:
            cursor = conexao.cursor()

            cursor.execute(
                """
                INSERT INTO produtos
                    (nome, categoria, quantidade, preco, estoque_minimo)
                VALUES (%s, %s, %s, %s, %s)
                """,
                dados
            )

            conexao.commit()

            messagebox.showinfo(
                "Sucesso",
                "Produto cadastrado com sucesso!",
                parent=cadastro
            )

            cadastro.destroy()
            atualizar_tudo()  # atualiza tabela, indicadores e alertas

        except Exception as erro:
            conexao.rollback()
            messagebox.showerror(
                "Erro ao cadastrar",
                str(erro),
                parent=cadastro
            )

        finally:
            if cursor is not None:
                cursor.close()

            conexao.close()

    tb.Button(
        formulario,
        text="Cadastrar produto",
        bootstyle="info",
        command=salvar_produto
    ).pack(fill=X, pady=(10, 0))

    tb.Button(
        formulario,
        text="Cancelar",
        bootstyle="secondary-outline",
        command=cadastro.destroy
    ).pack(fill=X, pady=(8, 0))

    cadastro.bind("<Return>", lambda evento: salvar_produto())


def editar_produto():
    #Janela 'Editar produto'. Aberta pelo botão 'Editar' ou por duplo
    #clique na tabela. Edita o produto selecionado na tabela principal.

    selecionado = tabela.selection()

    if not selecionado:
        messagebox.showwarning(
            "Atenção",
            "Selecione um produto para editar.",
            parent=janela
        )
        return

    # Editar exige senha (vale também para o duplo clique na tabela)
    if not pedir_senha("editar este produto"):
        return

    # A primeira coluna da linha selecionada é o ID do produto
    valores = tabela.item(selecionado[0], "values")
    id_produto = valores[0]

    conexao = conectar()

    if conexao is None:
        messagebox.showerror(
            "Erro",
            "Não foi possível conectar ao banco de dados.",
            parent=janela
        )
        return

    cursor = None

    try:
        cursor = conexao.cursor()

        # Busca os dados atuais no banco (e não da tabela, que está formatada)
        cursor.execute(
            """
            SELECT nome, categoria, quantidade, preco, estoque_minimo
            FROM produtos
            WHERE id = %s
            """,
            (id_produto,)
        )

        produto = cursor.fetchone()

    except Exception as erro:
        messagebox.showerror("Erro", str(erro), parent=janela)
        return

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()

    if produto is None:
        messagebox.showerror(
            "Erro",
            "Produto não encontrado.",
            parent=janela
        )
        carregar_produtos()
        return

    nome_atual, categoria_atual, quantidade_atual, preco_atual, minimo_atual = produto

    editor = tb.Toplevel(janela)
    editor.title("Editar produto")
    editor.resizable(True, True)
    centralizar(editor, 420, 560)

    formulario = tb.Frame(editor, padding=28)
    formulario.pack(fill=BOTH, expand=True)

    tb.Label(
        formulario,
        text="Editar produto",
        font=(FONTE_TITULO, 20)
    ).pack(anchor=W, pady=(0, 18))

    # Mesmos campos do cadastro, já preenchidos com os valores atuais
    campos = criar_campos(formulario, [
        ("nome", "Nome do produto", nome_atual),
        ("categoria", "Categoria (escolha da lista ou digite uma nova)", categoria_atual or ""),
        ("quantidade", "Quantidade", quantidade_atual),
        ("preco", "Preço", str(preco_atual)),
        ("estoque_minimo", "Estoque mínimo", minimo_atual)
    ])

    campos["nome"].focus_set()

    def salvar_edicao():
        """Valida e grava as alterações do produto."""
        dados = validar_produto(campos, editor)

        if dados is None:
            return

        conexao_edicao = conectar()

        if conexao_edicao is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível conectar ao banco de dados.",
                parent=editor
            )
            return

        cursor_edicao = None

        try:
            cursor_edicao = conexao_edicao.cursor()

            cursor_edicao.execute(
                """
                UPDATE produtos
                SET nome = %s,
                    categoria = %s,
                    quantidade = %s,
                    preco = %s,
                    estoque_minimo = %s
                WHERE id = %s
                """,
                dados + (id_produto,)
            )

            conexao_edicao.commit()

            messagebox.showinfo(
                "Sucesso",
                "Produto atualizado!",
                parent=editor
            )

            editor.destroy()
            atualizar_tudo()

        except Exception as erro:
            conexao_edicao.rollback()

            messagebox.showerror(
                "Erro ao atualizar",
                str(erro),
                parent=editor
            )

        finally:
            if cursor_edicao is not None:
                cursor_edicao.close()

            conexao_edicao.close()

    tb.Button(
        formulario,
        text="Salvar alterações",
        bootstyle="info",
        command=salvar_edicao
    ).pack(fill=X, pady=(10, 0))

    tb.Button(
        formulario,
        text="Cancelar",
        bootstyle="secondary-outline",
        command=editor.destroy
    ).pack(fill=X, pady=(8, 0))

    editor.bind("<Return>", lambda evento: salvar_edicao())


def excluir_produto():
    #Exclui o produto selecionado na tabela (botão 'Excluir').

    selecionado = tabela.selection()

    if not selecionado:
        messagebox.showwarning(
            "Atenção",
            "Selecione um produto para excluir.",
            parent=janela
        )
        return

    # Excluir também exige senha
    if not pedir_senha("excluir este produto"):
        return

    valores = tabela.item(selecionado[0], "values")
    id_produto = valores[0]
    nome_produto = valores[1]

    # Pergunta antes de apagar
    confirmar = messagebox.askyesno(
        "Confirmar exclusão",
        f"Deseja realmente excluir o produto '{nome_produto}'?",
        parent=janela
    )

    if not confirmar:
        return

    conexao = conectar()

    if conexao is None:
        messagebox.showerror(
            "Erro",
            "Não foi possível conectar ao banco de dados.",
            parent=janela
        )
        return

    cursor = None

    try:
        cursor = conexao.cursor()

        cursor.execute(
            "DELETE FROM produtos WHERE id = %s",
            (id_produto,)
        )

        conexao.commit()

        messagebox.showinfo(
            "Sucesso",
            "Produto excluído!",
            parent=janela
        )

        atualizar_tudo()

    except Exception as erro:
        conexao.rollback()

        # Produto com movimentações não pode ser apagado (chave estrangeira)
        if "foreign key" in str(erro).lower():
            mensagem = (
                "Este produto possui movimentações registradas "
                "e não pode ser excluído."
            )
        else:
            mensagem = str(erro)

        messagebox.showerror(
            "Erro ao excluir",
            mensagem,
            parent=janela
        )

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()


# =====================================================================
# INDICADORES E ALERTAS DE ESTOQUE BAIXO
# =====================================================================
def atualizar_resumo():
    # Atualiza os 3 números da faixa de indicadores do topo
    # (produtos, movimentações e valor em estoque).
    conexao = conectar()

    if conexao is None:
        return

    cursor = None

    try:
        cursor = conexao.cursor()

        cursor.execute("SELECT COUNT(*) FROM produtos")
        valores_resumo["total"].config(text=str(cursor.fetchone()[0]))

        cursor.execute("SELECT COUNT(*) FROM movimentacoes")
        valores_resumo["movs"].config(text=str(cursor.fetchone()[0]))

        cursor.execute("""
            SELECT COALESCE(SUM(quantidade * preco), 0)
            FROM produtos
        """)
        valores_resumo["valor"].config(
            text=formatar_preco(cursor.fetchone()[0])
        )

    except Exception as erro:
        messagebox.showerror(
            "Erro ao atualizar o painel",
            str(erro),
            parent=janela
        )

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()


# Guarda o estado do layout responsivo:
#   modo   -> "normal", "compacto" ou "estreito" (conforme a largura da janela)
#   limite -> quantos produtos cabem no painel de reposição
#   tarefa -> agendamento do ajuste (evita rodar a cada pixel redimensionado)

estado_layout = {"modo": None, "limite": None, "tarefa": None}

# Medidas de cada modo (usadas por aplicar_ajuste e atualizar_alertas)
LARGURA_ALERTA = {"normal": 330, "compacto": 270, "estreito": 240}
QUEBRA_NOME_ALERTA = {"normal": 170, "compacto": 120, "estreito": 100}
TAMANHO_TITULO = {"normal": 26, "compacto": 22, "estreito": 18}
TAMANHO_VALOR = {"normal": 28, "compacto": 20, "estreito": 15}


def calcular_limite_alertas():
    # Calcula quantos produtos em alerta cabem no painel lateral,
    # de acordo com a altura atual da janela.=
    janela.update_idletasks()
    altura = painel_alerta.winfo_height()

    if altura <= 1:  # janela ainda não desenhada
        return 6

    return max(1, min(8, (altura - 170) // 74))


def atualizar_alertas():
    # Monta o painel 'Reposição urgente' (lado direito da tela).
    # Mostra os produtos com quantidade <= estoque mínimo, com barra de nível
    # e o botão 'Repor', que abre a tela de movimentação já em 'Entrada'.

    # Apaga o que estava no painel antes de montar de novo

    for filho in lista_alertas.winfo_children():
        filho.destroy()

    limite = calcular_limite_alertas()
    estado_layout["limite"] = limite

    # Em modos mais estreitos o painel é menor, então o nome quebra antes
    quebra_nome = QUEBRA_NOME_ALERTA.get(estado_layout["modo"], 170)

    conexao = conectar()

    if conexao is None:
        return

    cursor = None

    try:
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM produtos
            WHERE quantidade <= estoque_minimo
        """)
        total_alertas = cursor.fetchone()[0]

        # Os mais críticos (menor quantidade) aparecem primeiro
        cursor.execute(
            """
            SELECT id, nome, quantidade, estoque_minimo
            FROM produtos
            WHERE quantidade <= estoque_minimo
            ORDER BY quantidade ASC, nome ASC
            LIMIT %s
            """,
            (limite,)
        )
        itens = cursor.fetchall()

    except Exception as erro:
        print(f"Erro ao carregar alertas: {erro}")
        return

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()

    # Nenhum produto em alerta: mostra uma mensagem tranquila
    if not itens:
        tb.Label(
            lista_alertas,
            text="Nenhum produto abaixo do mínimo",
            font=(FONTE_TEXTO, 11, "bold"),
            wraplength=quebra_nome + 90
        ).pack(anchor=W, pady=(24, 4))

        tb.Label(
            lista_alertas,
            text="Quando um produto chegar ao estoque mínimo, ele aparece aqui.",
            font=(FONTE_TEXTO, 10),
            style="Muted.TLabel",
            wraplength=quebra_nome + 90
        ).pack(anchor=W)
        return

    for id_produto, nome, quantidade, minimo in itens:
        # Proporção do estoque em relação ao mínimo (0 a 1) para a barrinha
        proporcao = min(quantidade / minimo, 1) if minimo > 0 else 0
        # Vermelho se está na metade do mínimo ou menos; âmbar nos demais
        cor = cores.danger if proporcao <= 0.5 else cores.warning

        linha = tb.Frame(lista_alertas)
        linha.pack(fill=X, pady=(0, 16))

        topo = tb.Frame(linha)
        topo.pack(fill=X)

        # Botão Repor: abre a movimentação com este produto e 'Entrada'
        # já selecionados (liga com abrir_movimentacoes)
        tb.Button(
            topo,
            text="Repor",
            bootstyle="success-outline",
            width=7,
            command=lambda i=id_produto: abrir_movimentacoes(
                produto_id=i, tipo="Entrada"
            )
        ).pack(side=RIGHT)

        textos = tb.Frame(topo)
        textos.pack(side=LEFT, fill=X, expand=True)

        tb.Label(
            textos,
            text=nome,
            font=(FONTE_TEXTO, 10, "bold"),
            wraplength=quebra_nome
        ).pack(anchor=W)

        tb.Label(
            textos,
            text=(
                f"Em falta, mínimo {minimo}" if quantidade == 0
                else f"{quantidade} em estoque, mínimo {minimo}"
            ),
            font=(FONTE_TEXTO, 9),
            style="Muted.TLabel"
        ).pack(anchor=W)

        barra_nivel(linha, proporcao, cor)

    # Se tem mais produtos em alerta do que cabem na tela, avisa quantos faltam
    if total_alertas > len(itens):
        tb.Label(
            lista_alertas,
            text=f"Mais {total_alertas - len(itens)} produto(s) em alerta.",
            font=(FONTE_TEXTO, 9),
            style="Muted.TLabel"
        ).pack(anchor=W, pady=(0, 8))

    # Liga o filtro 'Só estoque baixo' na tabela principal
    tb.Button(
        lista_alertas,
        text="Ver todos na tabela",
        bootstyle="warning-outline",
        command=mostrar_somente_baixo
    ).pack(fill=X)


# =====================================================================
# LAYOUT RESPONSIVO DA JANELA PRINCIPAL
#   Quando a janela é redimensionada, espero um instante (200 ms) e então
#   escolho um dos 3 modos pela largura:
#   - normal   (>= 1100 px): menu na lateral e painel de reposição largo;
#   - compacto (900 a 1099): menu e painel de reposição mais estreitos,
#     fontes menores;
#   - estreito (< 900 px): menu vira uma barra no topo, a coluna Categoria
#     some da tabela, e margens e fontes diminuem.
#   Em qualquer modo, recalculo quantos produtos em alerta cabem no painel.
# =====================================================================
def agendar_ajuste(evento):
    """Chamada a cada mudança de tamanho; agenda aplicar_ajuste."""
    if evento.widget is not janela:  # ignora eventos dos widgets internos
        return

    if estado_layout["tarefa"] is not None:
        janela.after_cancel(estado_layout["tarefa"])

    estado_layout["tarefa"] = janela.after(200, aplicar_ajuste)


def aplicar_ajuste():
    """Escolhe o modo (normal, compacto ou estreito) e adapta a tela."""
    estado_layout["tarefa"] = None

    largura = janela.winfo_width()

    if largura < 900:
        modo = "estreito"
    elif largura < 1100:
        modo = "compacto"
    else:
        modo = "normal"

    mudou_modo = modo != estado_layout["modo"]
    estado_layout["modo"] = modo

    if mudou_modo:
        # Menu: barra no topo (estreito) ou coluna na lateral
        montar_menu(modo == "estreito")

        if modo != "estreito":
            menu.configure(width=190 if modo == "compacto" else 250)

        # Painel de reposição urgente
        painel_alerta.configure(width=LARGURA_ALERTA[modo])

        # Margens da área principal
        principal.configure(padding=(30, 26) if modo == "normal" else (16, 14))

        # Fontes e espaçamento dos indicadores do topo
        titulo_pagina.configure(font=(FONTE_TITULO, TAMANHO_TITULO[modo]))

        for rotulo in valores_resumo.values():
            rotulo.configure(font=(FONTE_TITULO, TAMANHO_VALOR[modo]))

        for bloco in blocos_faixa:
            bloco.configure(padding=(26, 16) if modo == "normal" else (14, 12))

        # Tabela: no modo estreito esconde a coluna Categoria para caber o resto
        if modo == "estreito":
            tabela.configure(
                displaycolumns=("id", "nome", "quantidade", "preco", "status")
            )
        else:
            tabela.configure(displaycolumns="#all")

    # Só refaz o painel se o modo mudou ou se a quantidade que cabe mudou
    if mudou_modo or calcular_limite_alertas() != estado_layout["limite"]:
        atualizar_alertas()


janela.bind("<Configure>", agendar_ajuste)


# =====================================================================
# MOVIMENTAÇÕES (ENTRADAS E SAÍDAS)
# =====================================================================
def abrir_movimentacoes(produto_id=None, tipo="Entrada"):
    # Janela de entrada/saída de estoque.
    # Aberta pelo menu, pelo botão 'Movimentar estoque' e pelo botão 'Repor'
    # do painel de reposição (que já manda produto_id e tipo='Entrada').
    # Se nada for informado, usa o produto selecionado na tabela principal.

    movimentacoes = tb.Toplevel(janela)
    movimentacoes.title("Movimentar estoque")
    movimentacoes.resizable(True, True)
    centralizar(movimentacoes, 480, 700, min_largura=420, min_altura=560)

    formulario = tb.Frame(movimentacoes, padding=28)
    formulario.pack(fill=BOTH, expand=True)

    tb.Label(
        formulario,
        text="Movimentar estoque",
        font=(FONTE_TITULO, 20)
    ).pack(anchor=W)

    descricao = tb.Label(
        formulario,
        text="Escolha o produto pelo nome e registre a entrada ou a saída.",
        font=(FONTE_TEXTO, 10),
        style="Muted.TLabel",
        wraplength=420
    )
    descricao.pack(anchor=W, pady=(2, 18))
    ajustar_quebra_texto(descricao, formulario)  # quebra de linha responsiva

    # Tipo da movimentação: dois botões lado a lado (Entrada / Saída)
    tipo_movimentacao = tb.StringVar(value=tipo)

    linha_tipo = tb.Frame(formulario)
    linha_tipo.pack(fill=X, pady=(0, 16))

    tb.Radiobutton(
        linha_tipo,
        text="Entrada",
        variable=tipo_movimentacao,
        value="Entrada",
        bootstyle="success-outline-toolbutton"
    ).pack(side=LEFT, fill=X, expand=True, padx=(0, 6))

    tb.Radiobutton(
        linha_tipo,
        text="Saída",
        variable=tipo_movimentacao,
        value="Saída",
        bootstyle="danger-outline-toolbutton"
    ).pack(side=LEFT, fill=X, expand=True)

    # Busca de produto pelo nome
    tb.Label(formulario, text="Produto").pack(anchor=W)

    campo_produto = tb.Entry(formulario)
    campo_produto.pack(fill=X, pady=(3, 8))

    # Rodapé (seleção, quantidade e botões). Eu o coloco ANTES da lista no
    # código, com side=BOTTOM, para ele nunca ser cortado: se a janela
    # ficar baixa, quem encolhe é a lista de produtos.

    rodape = tb.Frame(formulario)
    rodape.pack(side=BOTTOM, fill=X)

    rotulo_selecao = tb.Label(
        rodape,
        text="Nenhum produto selecionado",
        font=(FONTE_TEXTO, 10, "bold"),
        style="Muted.TLabel",
        wraplength=420
    )
    rotulo_selecao.pack(anchor=W, pady=(10, 14))
    ajustar_quebra_texto(rotulo_selecao, formulario)

    tb.Label(rodape, text="Quantidade").pack(anchor=W)

    campo_quantidade = tb.Entry(rodape)
    campo_quantidade.pack(fill=X, pady=(3, 18))

    # Os botões usam lambda porque salvar_movimentacao é definida mais abaixo
    tb.Button(
        rodape,
        text="Registrar movimentação",
        bootstyle="success",
        command=lambda: salvar_movimentacao()
    ).pack(fill=X)

    tb.Button(
        rodape,
        text="Fechar",
        bootstyle="secondary-outline",
        command=movimentacoes.destroy
    ).pack(fill=X, pady=(8, 0))

    # Lista de produtos: agora é uma tabela de 2 colunas. O nome fica
    # alinhado à esquerda e o estoque alinhado à direita, em coluna própria.
    # Assim "Teclado mecânico" e "10" não ficam mais embolados.

    quadro_lista = tb.Frame(formulario)
    quadro_lista.pack(fill=BOTH, expand=True)

    lista = tb.Treeview(
        quadro_lista,
        columns=("produto", "estoque"),
        show="headings",
        height=6,
        selectmode="browse",
        style="Lista.Treeview"
    )
    lista.heading("produto", text="Produto", anchor=W)
    lista.heading("estoque", text="Em estoque", anchor=E)
    lista.column("produto", width=260, minwidth=120, anchor=W, stretch=True)
    lista.column("estoque", width=100, minwidth=80, anchor=E, stretch=False)

    rolagem_lista = tb.Scrollbar(
        quadro_lista,
        orient=VERTICAL,
        command=lista.yview,
        bootstyle="round"
    )
    lista.configure(yscrollcommand=rolagem_lista.set)

    lista.pack(side=LEFT, fill=BOTH, expand=True)
    rolagem_lista.pack(side=RIGHT, fill=Y)

    # Dados desta janela:
    #   todos_produtos -> todos os produtos vindos do banco
    #   visiveis       -> os que aparecem na lista depois da busca
    #   escolhido      -> o produto que o usuário escolheu
    todos_produtos = []
    visiveis = []
    escolhido = {"produto": None}

    def recarregar_lista():
       #Lê os produtos do banco e guarda em todos_produtos.

        conexao_lista = conectar()

        if conexao_lista is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível conectar ao banco de dados.",
                parent=movimentacoes
            )
            return False

        cursor_lista = None

        try:
            cursor_lista = conexao_lista.cursor()
            cursor_lista.execute("""
                SELECT id, nome, quantidade
                FROM produtos
                ORDER BY nome
            """)
            linhas = cursor_lista.fetchall()

        except Exception as erro:
            messagebox.showerror(
                "Erro ao carregar produtos",
                str(erro),
                parent=movimentacoes
            )
            return False

        finally:
            if cursor_lista is not None:
                cursor_lista.close()

            conexao_lista.close()

        # Nomes repetidos ganham o código para dar para diferenciar
        contagem = {}

        for _, nome, _ in linhas:
            contagem[nome] = contagem.get(nome, 0) + 1

        todos_produtos.clear()

        for id_p, nome, estoque in linhas:
            rotulo = nome if contagem[nome] == 1 else f"{nome} (código {id_p})"

            todos_produtos.append({
                "id": id_p,
                "nome": nome,
                "estoque": estoque,
                "rotulo": rotulo,
                "busca": normalizar(rotulo)
            })

        # Se já havia um produto escolhido, pega a versão atualizada dele
        atual = escolhido["produto"]

        if atual is not None:
            escolhido["produto"] = next(
                (p for p in todos_produtos if p["id"] == atual["id"]),
                None
            )

        return True

    def atualizar_selecao():
        # Atualiza o texto abaixo da lista com o produto escolhido.
        produto = escolhido["produto"]

        if produto is None:
            rotulo_selecao.config(
                text="Nenhum produto selecionado",
                foreground=COR_MUTED
            )
        else:
            rotulo_selecao.config(
                text=f"{produto['nome']}: {produto['estoque']} em estoque",
                foreground=cores.success
            )

    def filtrar():
        # Mostra na lista só os produtos que combinam com o texto digitado.
        termo = normalizar(campo_produto.get().strip())

        visiveis.clear()

        for item in lista.get_children():
            lista.delete(item)

        for indice, produto in enumerate(todos_produtos):
            if termo in produto["busca"]:
                visiveis.append(produto)
                # O iid é a posição do produto em 'visiveis'
                lista.insert(
                    "",
                    "end",
                    iid=str(len(visiveis) - 1),
                    values=(produto["rotulo"], produto["estoque"])
                )

        if not visiveis:
            lista.insert(
                "", "end", iid="vazio",
                values=("Nenhum produto com esse nome", "")
            )

    def definir_produto(produto):
       # Marca o produto como escolhido e vai para o campo Quantidade.
        escolhido["produto"] = produto
        campo_produto.delete(0, END)
        campo_produto.insert(0, produto["rotulo"])
        filtrar()
        atualizar_selecao()
        campo_quantidade.focus_set()

    def escolher_da_lista(evento=None):
        # Escolhe o produto que está selecionado na lista.
        selecao = lista.selection()

        if selecao and visiveis and selecao[0] != "vazio":
            definir_produto(visiveis[int(selecao[0])])

    def clique_na_lista(evento):
        # Só considera clique em linha (não no cabeçalho da lista)

        if lista.identify_region(evento.x, evento.y) == "cell":
            escolher_da_lista()

    def ao_digitar(evento):
        # Cada tecla digitada no campo Produto refiltra a lista.
        teclas_ignoradas = (
            "Up", "Down", "Return", "Tab", "Escape", "Left", "Right",
            "Home", "End", "Shift_L", "Shift_R", "Control_L", "Control_R"
        )

        if evento.keysym in teclas_ignoradas:
            return

        produto = escolhido["produto"]

        # Mudou o texto depois de escolher: a escolha anterior deixa de valer
        if produto is not None and campo_produto.get() != produto["rotulo"]:
            escolhido["produto"] = None
            atualizar_selecao()

        filtrar()

    def ir_para_lista(evento=None):
        # Seta para baixo no campo Produto: pula para a lista.
        if visiveis:
            lista.focus_set()
            lista.selection_set("0")
            lista.focus("0")

        return "break"

    def confirmar_busca(evento=None):
        # Enter na busca: escolhe direto se sobrou só um produto
        if len(visiveis) == 1:
            definir_produto(visiveis[0])
        else:
            ir_para_lista()

        return "break"

    campo_produto.bind("<KeyRelease>", ao_digitar)
    campo_produto.bind("<Down>", ir_para_lista)
    campo_produto.bind("<Return>", confirmar_busca)
    lista.bind("<ButtonRelease-1>", clique_na_lista)
    lista.bind("<Return>", escolher_da_lista)

    def salvar_movimentacao():
        #Registra a entrada/saída: atualiza a quantidade do produto e
        #grava uma linha na tabela 'movimentacoes' (que alimenta o Histórico).

        produto = escolhido["produto"]

        if produto is None:
            messagebox.showwarning(
                "Atenção",
                "Escolha um produto na lista.",
                parent=movimentacoes
            )
            return

        tipo_selecionado = tipo_movimentacao.get()
        # No banco o tipo é guardado como ENTRADA ou SAIDA (sem acento)
        tipo_db = "ENTRADA" if tipo_selecionado == "Entrada" else "SAIDA"
        quantidade_texto = campo_quantidade.get().strip()

        if not quantidade_texto:
            messagebox.showwarning(
                "Atenção",
                "Informe a quantidade.",
                parent=movimentacoes
            )
            return

        try:
            quantidade = int(quantidade_texto)

            if quantidade <= 0:
                raise ValueError

        except ValueError:
            messagebox.showerror(
                "Dados inválidos",
                "A quantidade deve ser um número inteiro positivo.",
                parent=movimentacoes
            )
            return

        id_do_produto = produto["id"]

        conexao = conectar()

        if conexao is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível conectar ao banco de dados.",
                parent=movimentacoes
            )
            return

        cursor = None

        try:
            cursor = conexao.cursor()

            # FOR UPDATE trava a linha durante a operação,
            # evitando que duas movimentações simultâneas se atropelem.
            cursor.execute(
                """
                SELECT quantidade
                FROM produtos
                WHERE id = %s
                FOR UPDATE
                """,
                (id_do_produto,)
            )

            resultado = cursor.fetchone()

            if resultado is None:
                messagebox.showerror(
                    "Produto não encontrado",
                    "Esse produto não existe mais. Atualize a lista.",
                    parent=movimentacoes
                )
                return

            estoque_atual = resultado[0]

            # Não deixa tirar mais do que existe
            if tipo_db == "SAIDA" and quantidade > estoque_atual:
                messagebox.showwarning(
                    "Estoque insuficiente",
                    f"Estoque disponível: {estoque_atual}",
                    parent=movimentacoes
                )
                return

            if tipo_db == "ENTRADA":
                nova_quantidade = estoque_atual + quantidade
            else:
                nova_quantidade = estoque_atual - quantidade

            cursor.execute(
                """
                UPDATE produtos
                SET quantidade = %s
                WHERE id = %s
                """,
                (nova_quantidade, id_do_produto)
            )

            cursor.execute(
                """
                INSERT INTO movimentacoes
                    (produto_id, tipo, quantidade)
                VALUES (%s, %s, %s)
                """,
                (id_do_produto, tipo_db, quantidade)
            )

            conexao.commit()

            messagebox.showinfo(
                "Sucesso",
                "Movimentação registrada com sucesso!",
                parent=movimentacoes
            )

            campo_quantidade.delete(0, END)

            # Atualiza os números de estoque mostrados nesta janela
            recarregar_lista()
            filtrar()
            atualizar_selecao()
            atualizar_tudo()  # e também a tela principal

        except Exception as erro:
            conexao.rollback()
            messagebox.showerror(
                "Erro",
                str(erro),
                parent=movimentacoes
            )

        finally:
            if cursor is not None:
                cursor.close()

            conexao.close()

    campo_quantidade.bind("<Return>", lambda evento: salvar_movimentacao())

    # Carga inicial da lista e pré-seleção do produto
    if recarregar_lista():
        filtrar()

        alvo = produto_id  # vem do botão 'Repor', se foi ele que abriu

        if alvo is None:
            # Senão, usa o produto selecionado na tabela principal
            linha_selecionada = tabela.selection()

            if linha_selecionada:
                alvo = int(tabela.item(linha_selecionada[0], "values")[0])

        if alvo is not None:
            for produto in todos_produtos:
                if produto["id"] == alvo:
                    definir_produto(produto)
                    break
        else:
            campo_produto.focus_set()


# =====================================================================
# HISTÓRICO DE MOVIMENTAÇÕES
# =====================================================================
def abrir_historico():
    #Janela com todas as entradas e saídas já registradas
    #(dados gravados por salvar_movimentacao).

    janela_historico = tb.Toplevel(janela)
    janela_historico.title("Histórico de movimentações")
    centralizar(janela_historico, 840, 560, min_largura=560, min_altura=380)

    cabecalho_hist = tb.Frame(janela_historico, padding=(26, 22, 26, 0))
    cabecalho_hist.pack(fill=X)

    tb.Label(
        cabecalho_hist,
        text="Histórico de movimentações",
        font=(FONTE_TITULO, 20)
    ).pack(anchor=W)

    # Resumo: "X registro(s): Y entrada(s) e Z saída(s)"
    resumo_hist = tb.Label(
        cabecalho_hist,
        text="",
        font=(FONTE_TEXTO, 10),
        style="Muted.TLabel"
    )
    resumo_hist.pack(anchor=W, pady=(2, 0))

    # Botão no canto superior direito do cabeçalho (place = posição relativa,
    # por isso ele acompanha o tamanho da janela). Usa lambda porque
    # apagar_historico é definida mais abaixo.
    tb.Button(
        cabecalho_hist,
        text="Apagar histórico",
        bootstyle="danger-outline",
        command=lambda: apagar_historico()
    ).place(relx=1.0, x=-26, y=22, anchor="ne")

    quadro = tb.Frame(janela_historico, padding=(26, 16, 26, 26))
    quadro.pack(fill=BOTH, expand=True)

    tabela_hist = tb.Treeview(
        quadro,
        columns=("id", "produto", "tipo", "quantidade"),
        show="headings"
    )

    rolagem = tb.Scrollbar(
        quadro,
        orient=VERTICAL,
        command=tabela_hist.yview,
        bootstyle="round"
    )
    tabela_hist.configure(yscrollcommand=rolagem.set)

    tabela_hist.heading("id", text="ID")
    tabela_hist.heading("produto", text="Produto")
    tabela_hist.heading("tipo", text="Tipo")
    tabela_hist.heading("quantidade", text="Quantidade")

    # A coluna 'Produto' estica com a janela; as outras ficam fixas
    tabela_hist.column("id", width=60, minwidth=40, anchor=CENTER, stretch=False)
    tabela_hist.column("produto", width=320, minwidth=140, stretch=True)
    tabela_hist.column("tipo", width=140, minwidth=80, anchor=CENTER, stretch=False)
    tabela_hist.column("quantidade", width=120, minwidth=80, anchor=CENTER, stretch=False)

    # Entradas em verde e saídas em vermelho
    tabela_hist.tag_configure("ENTRADA", foreground=cores.success)
    tabela_hist.tag_configure("SAIDA", foreground=cores.danger)

    tabela_hist.pack(side=LEFT, fill=BOTH, expand=True)
    rolagem.pack(side=RIGHT, fill=Y)

    def carregar_historico():
        #Lê as movimentações do banco e preenche a tabela do histórico.
        #É chamada ao abrir a janela e de novo depois de apagar o histórico.

        # Limpa a tabela antes de preencher (assim não duplica linhas)
        
        for item in tabela_hist.get_children():
            tabela_hist.delete(item)

        conexao = None
        cursor = None

        try:
            conexao = conectar()
            cursor = conexao.cursor()

            # LEFT JOIN: mantém a movimentação mesmo se o produto foi removido
            cursor.execute("""
                SELECT m.id, p.nome, m.tipo, m.quantidade
                FROM movimentacoes m
                LEFT JOIN produtos p ON p.id = m.produto_id
                ORDER BY m.id DESC
            """)

            linhas = cursor.fetchall()

            for id_mov, nome, tipo_mov, quantidade in linhas:
                tabela_hist.insert(
                    "",
                    "end",
                    values=(
                        id_mov,
                        nome or "(produto removido)",
                        "Entrada" if tipo_mov == "ENTRADA" else "Saída",
                        quantidade
                    ),
                    tags=(tipo_mov,)
                )

            entradas = sum(1 for linha in linhas if linha[2] == "ENTRADA")
            saidas = len(linhas) - entradas

            resumo_hist.config(
                text=f"{len(linhas)} registro(s): {entradas} entrada(s) e {saidas} saída(s)"
            )

        except Exception as erro:
            messagebox.showerror(
                "Erro",
                f"Não foi possível carregar o histórico:\n{erro}",
                parent=janela_historico
            )
            janela_historico.destroy()

        finally:
            if cursor is not None:
                cursor.close()

            if conexao is not None:
                conexao.close()

    def apagar_historico():
        #Apaga TODAS as movimentações (botão 'Apagar histórico').
        #Exige senha e uma confirmação. O estoque dos produtos NÃO muda:
        #só o registro das entradas e saídas é removido.

        # Se não tem nada na tabela, não há o que apagar

        if not tabela_hist.get_children():
            messagebox.showinfo(
                "Histórico vazio",
                "Não há registros para apagar.",
                parent=janela_historico
            )
            return

        # 1º passo: senha (a mesma função usada em editar e excluir)
        if not pedir_senha("apagar todo o histórico", pai=janela_historico):
            return

        # 2º passo: confirmação, porque não dá para desfazer
        confirmar = messagebox.askyesno(
            "Confirmar exclusão",
            "Deseja realmente apagar TODO o histórico de movimentações?\n\n"
            "Essa ação não pode ser desfeita. O estoque dos produtos "
            "não será alterado.",
            icon="warning",
            parent=janela_historico
        )

        if not confirmar:
            return

        conexao = conectar()

        if conexao is None:
            messagebox.showerror(
                "Erro",
                "Não foi possível conectar ao banco de dados.",
                parent=janela_historico
            )
            return

        cursor = None

        try:
            cursor = conexao.cursor()

            # Sem WHERE: apaga todas as linhas da tabela de movimentações
            cursor.execute("DELETE FROM movimentacoes")

            conexao.commit()

            messagebox.showinfo(
                "Sucesso",
                "Histórico apagado!",
                parent=janela_historico
            )

            carregar_historico()  # esvazia a tabela e o resumo desta janela
            atualizar_tudo()      # zera o contador 'Movimentações' da tela principal

        except Exception as erro:
            conexao.rollback()

            messagebox.showerror(
                "Erro ao apagar",
                str(erro),
                parent=janela_historico
            )

        finally:
            if cursor is not None:
                cursor.close()

            conexao.close()

    # Carga inicial: preenche a tabela assim que a janela abre
    carregar_historico()


# =====================================================================
# ALTERAR A SENHA
# =====================================================================
def abrir_alterar_senha():
    #Janela para trocar a senha. Aberta pelo botão 'Alterar senha' do menu.
    #Só abre para quem sabe a senha atual (pedir_senha) e a nova senha vale
    #para editar, excluir e apagar histórico.

    # Primeiro a senha atual: quem não a sabe não passa daqui

    if not pedir_senha("alterar a senha"):
        return

    janela_senha = tb.Toplevel(janela)
    janela_senha.title("Alterar senha")
    janela_senha.resizable(True, True)
    centralizar(janela_senha, 420, 450)

    formulario = tb.Frame(janela_senha, padding=28)
    formulario.pack(fill=BOTH, expand=True)

    tb.Label(
        formulario,
        text="Alterar senha",
        font=(FONTE_TITULO, 20)
    ).pack(anchor=W)

    explicacao = tb.Label(
        formulario,
        text="A nova senha será pedida para editar e excluir produtos, "
             "apagar o histórico e alterar a senha de novo.",
        font=(FONTE_TEXTO, 10),
        style="Muted.TLabel",
        wraplength=340
    )
    explicacao.pack(anchor=W, pady=(2, 18))
    ajustar_quebra_texto(explicacao, formulario)  # quebra de linha responsiva

    tb.Label(formulario, text="Nova senha (mínimo de 4 caracteres)").pack(anchor=W)

    campo_nova = tb.Entry(formulario, show="●")
    campo_nova.pack(fill=X, pady=(3, 12))

    tb.Label(formulario, text="Repita a nova senha").pack(anchor=W)

    campo_confirma = tb.Entry(formulario, show="●")
    campo_confirma.pack(fill=X, pady=(3, 12))

    campo_nova.focus_set()

    def salvar_nova_senha():
        """Confere os dados e grava a nova senha em senha.json."""
        nova = campo_nova.get()
        confirma = campo_confirma.get()

        if len(nova) < 4:
            messagebox.showwarning(
                "Atenção",
                "A nova senha precisa ter pelo menos 4 caracteres.",
                parent=janela_senha
            )
            return

        if nova != confirma:
            messagebox.showerror(
                "Senhas diferentes",
                "A confirmação não é igual à nova senha.",
                parent=janela_senha
            )
            campo_confirma.delete(0, END)
            campo_confirma.focus_set()
            return

        if verificar_senha(nova):
            messagebox.showwarning(
                "Atenção",
                "A nova senha é igual à senha atual.",
                parent=janela_senha
            )
            return

        try:
            salvar_senha(nova)

        except OSError as erro:
            # Ex.: pasta sem permissão de escrita
            messagebox.showerror(
                "Erro ao salvar a senha",
                str(erro),
                parent=janela_senha
            )
            return

        messagebox.showinfo(
            "Sucesso",
            "Senha alterada com sucesso!",
            parent=janela_senha
        )
        janela_senha.destroy()

    tb.Button(
        formulario,
        text="Salvar nova senha",
        bootstyle="info",
        command=salvar_nova_senha
    ).pack(fill=X, pady=(10, 0))

    tb.Button(
        formulario,
        text="Cancelar",
        bootstyle="secondary-outline",
        command=janela_senha.destroy
    ).pack(fill=X, pady=(8, 0))

    janela_senha.bind("<Return>", lambda evento: salvar_nova_senha())


# =====================================================================
# EXPORTAR PRODUTOS PARA CSV (abre no Excel)
# =====================================================================
def exportar_csv():
    #Salva todos os produtos em um arquivo .csv.
    #Separador ';' e codificação utf-8-sig para o Excel abrir com os
    #acentos certos.

    caminho = filedialog.asksaveasfilename(
        parent=janela,
        title="Exportar produtos",
        defaultextension=".csv",
        initialfile="produtos.csv",
        filetypes=[("Arquivo CSV", "*.csv")]
    )

    if not caminho:  # usuário cancelou
        return

    conexao = conectar()

    if conexao is None:
        messagebox.showerror(
            "Erro",
            "Não foi possível conectar ao banco de dados.",
            parent=janela
        )
        return

    cursor = None

    try:
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT id, nome, categoria, quantidade, preco, estoque_minimo
            FROM produtos
            ORDER BY nome
        """)

        linhas = cursor.fetchall()

        with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")

            escritor.writerow([
                "ID", "Produto", "Categoria",
                "Quantidade", "Preço", "Estoque mínimo"
            ])

            for id_p, nome, categoria, quantidade, preco, minimo in linhas:
                escritor.writerow([
                    id_p,
                    nome,
                    categoria or "",
                    quantidade,
                    str(preco).replace(".", ","),  # vírgula decimal (Excel BR)
                    minimo
                ])

        messagebox.showinfo(
            "Sucesso",
            f"{len(linhas)} produto(s) exportado(s) com sucesso!",
            parent=janela
        )

    except Exception as erro:
        messagebox.showerror(
            "Erro ao exportar",
            str(erro),
            parent=janela
        )

    finally:
        if cursor is not None:
            cursor.close()

        conexao.close()


# =====================================================================
# INICIAR A APLICAÇÃO
# Carrega tabela, indicadores e painel de reposição pela primeira vez
# e deixa a janela aberta esperando o usuário (mainloop).
# =====================================================================
atualizar_tudo()
janela.mainloop()