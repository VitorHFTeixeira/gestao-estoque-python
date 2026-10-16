
import mysql.connector
from mysql.connector import Error


def conectar():
    try:
        conexao = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="stockmanager"
        )

        if conexao.is_connected():
            print("Conexão com MySQL realizada!")
            return conexao

    except Error as erro:
        print(f"Erro ao conectar ao MySQL: {erro}")

    return None
