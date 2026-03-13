-- ════════════════════════════════════════════════════════════════
--  ProfeMiro — Schema de base de datos
--  Ejecutar una sola vez para crear todas las tablas
-- ════════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS sistema_examenes CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sistema_examenes;

-- Profesores
CREATE TABLE IF NOT EXISTS profesores (
    id_profesor INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre_sala VARCHAR(50) NOT NULL UNIQUE,
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Salas adicionales por profesor
CREATE TABLE IF NOT EXISTS salas_profesor (
    id INT AUTO_INCREMENT PRIMARY KEY,
    id_profesor INT NOT NULL,
    nombre_sala VARCHAR(50) NOT NULL UNIQUE,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_profesor) REFERENCES profesores(id_profesor) ON DELETE CASCADE
);

-- Quizzes
CREATE TABLE IF NOT EXISTS quizzes (
    id_quiz INT AUTO_INCREMENT PRIMARY KEY,
    id_profesor INT NOT NULL,
    titulo VARCHAR(200) NOT NULL,
    seccion VARCHAR(100) DEFAULT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_profesor) REFERENCES profesores(id_profesor) ON DELETE CASCADE
);

-- Preguntas
CREATE TABLE IF NOT EXISTS preguntas (
    id_pregunta INT AUTO_INCREMENT PRIMARY KEY,
    id_quiz INT NOT NULL,
    enunciado TEXT NOT NULL,
    tipo ENUM('test','corta') NOT NULL,
    respuesta_modelo TEXT,
    orden INT DEFAULT 0,
    FOREIGN KEY (id_quiz) REFERENCES quizzes(id_quiz) ON DELETE CASCADE
);

-- Opciones de preguntas tipo test
CREATE TABLE IF NOT EXISTS opciones (
    id_opcion INT AUTO_INCREMENT PRIMARY KEY,
    id_pregunta INT NOT NULL,
    texto TEXT NOT NULL,
    FOREIGN KEY (id_pregunta) REFERENCES preguntas(id_pregunta) ON DELETE CASCADE
);

-- Salas activas (examen en curso)
CREATE TABLE IF NOT EXISTS salas_activas (
    nombre_sala VARCHAR(50) PRIMARY KEY,
    id_quiz_activo INT NULL,
    estado ENUM('esperando','en_progreso','finalizado') DEFAULT 'esperando',
    FOREIGN KEY (id_quiz_activo) REFERENCES quizzes(id_quiz) ON DELETE SET NULL
);

-- Respuestas de alumnos
CREATE TABLE IF NOT EXISTS respuestas_alumnos (
    id_respuesta INT AUTO_INCREMENT PRIMARY KEY,
    nombre_sala VARCHAR(50) NOT NULL,
    id_quiz INT NOT NULL,
    id_pregunta INT NOT NULL,
    nombre_alumno VARCHAR(100) NOT NULL,
    contenido_respuesta TEXT,
    puntuacion DECIMAL(4,2) DEFAULT NULL,
    fecha_respuesta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (id_quiz) REFERENCES quizzes(id_quiz) ON DELETE CASCADE,
    FOREIGN KEY (id_pregunta) REFERENCES preguntas(id_pregunta) ON DELETE CASCADE
);
