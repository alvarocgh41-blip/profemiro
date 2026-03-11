import mysql.connector

def conectar():
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",        
            password="root", 
            database="sistema_examenes"
        )
        return conexion
    except mysql.connector.Error as err:
        print(f"❌ Error de conexión a la base de datos: {err}")
        return None