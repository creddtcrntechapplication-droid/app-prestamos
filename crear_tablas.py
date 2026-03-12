import sqlite3

def crear_bd():
    conexion = sqlite3.connect("prestamos.db")
    cursor = conexion.cursor()

    # ===== Clientes =====
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clientes (
        cedula TEXT PRIMARY KEY,
        nombres TEXT,
        apellidos TEXT,
        ciudad TEXT,
        telefono TEXT,
        correo TEXT,
        direccion TEXT,
        empresa TEXT,
        fecha_nacimiento TEXT,
        cargo TEXT
    )
    """)

    # ===== Codeudores =====
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS codeudores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_cedula TEXT,
        nombres TEXT,
        apellidos TEXT,
        ciudad TEXT,
        telefono TEXT,
        correo TEXT,
        direccion TEXT,
        empresa TEXT,
        fecha_nacimiento TEXT,
        cargo TEXT,
        FOREIGN KEY (cliente_cedula) REFERENCES clientes(cedula)
    )
    """)

    # ===== Prestamos =====
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prestamos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_cedula TEXT,
        valor REAL,
        cuotas INTEGER,
        frecuencia TEXT,
        valor_cuota REAL,
        estado TEXT DEFAULT 'Activo',
        FOREIGN KEY (cliente_cedula) REFERENCES clientes(cedula)
    )
    """)

    # ===== Pagos =====
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pagos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prestamo_id INTEGER,
        fecha_pago TEXT,
        valor REAL,
        estado TEXT,
        FOREIGN KEY (prestamo_id) REFERENCES prestamos(id)
    )
    """)

    conexion.commit()
    conexion.close()
    print("✅ Base de datos creada correctamente (prestamos.db)")

if __name__ == "__main__":
    crear_bd()
