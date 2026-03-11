# 📚 ProfeMiro — Sistema de Exámenes Inteligente

Plataforma web para profesores que permite crear, lanzar y corregir exámenes en tiempo real usando IA.

## ✨ Funcionalidades

- **Crear quizzes con IA** — genera preguntas automáticamente por tema o desde un documento CSV/TXT
- **Crear quizzes manualmente** — diseña el examen pregunta a pregunta con imágenes opcionales
- **Lanzar exámenes en tiempo real** — los alumnos se unen con un código de sala
- **Corrección automática** — preguntas tipo test se corrigen solas
- **Corrección manual** — asigna notas a preguntas de respuesta corta
- **Resultados y exportación** — descarga las notas en CSV
- **Gestión de biblioteca** — organiza tus quizzes por secciones
- **Multi-sala** — gestiona varias clases desde el mismo panel

## 🛠️ Stack

- **Frontend/Backend:** Python + Streamlit
- **Base de datos:** MySQL
- **IA:** API compatible con OpenAI (Ollama, OpenAI, Azure, etc.)

## 🚀 Instalación local

### 1. Clona el repositorio
```bash
git clone https://github.com/TU_USUARIO/TU_REPO.git
cd TU_REPO
```

### 2. Instala las dependencias
```bash
pip install -r requirements.txt
```

### 3. Configura la base de datos
- Crea una base de datos MySQL
- Ejecuta el archivo `schema.sql` para crear las tablas

### 4. Configura las variables de entorno
```bash
export DB_HOST=localhost
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=tu_password
export DB_NAME=sistema_examenes
export CENTRO_API_URL=http://IP:PUERTO/v1
export CENTRO_MODEL=nombre_del_modelo
```

### 5. Arranca la app
```bash
streamlit run app_streamlit.py
```

## ☁️ Despliegue en Railway

1. Sube el proyecto a GitHub
2. Crea un nuevo proyecto en [Railway](https://railway.app)
3. Añade un servicio MySQL y ejecuta `schema.sql`
4. Conecta tu repositorio de GitHub
5. Configura las variables de entorno en Railway
6. ¡Listo!

## 📁 Estructura del proyecto

```
├── app_streamlit.py      # Aplicación principal
├── requirements.txt      # Dependencias Python
├── Procfile              # Comando de arranque para Railway
├── schema.sql            # Esquema de la base de datos
├── .streamlit/
│   └── config.toml       # Configuración de Streamlit
└── README.md
```

## 👨‍🏫 Uso

### Para el profesor
1. Regístrate y accede al panel
2. Crea un quiz (con IA, desde documento o manualmente)
3. Lanza el examen desde el Launcher
4. Comparte el código de sala con tus alumnos
5. Revisa los resultados y exporta las notas

### Para el alumno
1. Accede a la URL de la app
2. Introduce tu nombre y el código de sala
3. Responde las preguntas y envía el examen