-- Base de datos de la demo (datos 100% ficticios)
CREATE DATABASE IF NOT EXISTS cne_demo CHARACTER SET utf8mb4;
USE cne_demo;

DROP TABLE IF EXISTS solicitudes;
-- Los COMMENT forman el diccionario de datos que la app entrega al modelo como contexto
CREATE TABLE solicitudes (
  id            INT AUTO_INCREMENT PRIMARY KEY COMMENT 'Número de la solicitud',
  ciudadano     VARCHAR(80)  NOT NULL COMMENT 'Nombre de quien presenta la solicitud',
  asunto        VARCHAR(160) NOT NULL COMMENT 'Resumen breve de la solicitud',
  categoria     ENUM('Tarifas','Combustibles','Electricidad','Transparencia','Otros') NOT NULL COMMENT 'Tema de la solicitud',
  prioridad     ENUM('baja','media','alta') NOT NULL DEFAULT 'media' COMMENT 'Urgencia de la atención',
  estado        ENUM('pendiente','en_proceso','resuelta') NOT NULL DEFAULT 'pendiente' COMMENT 'Situación actual de la solicitud',
  fecha_ingreso DATE NOT NULL COMMENT 'Fecha en que se recibió la solicitud'
) COMMENT 'Solicitudes y reclamos ciudadanos (datos ficticios)';

INSERT INTO solicitudes (ciudadano, asunto, categoria, prioridad, estado, fecha_ingreso) VALUES
('Ana Rojas',        'Cobro excesivo en boleta de luz',              'Tarifas',       'alta',  'pendiente',  '2026-10-12'),
('Luis Pérez',       'Precio de bencina distinto al informado',      'Combustibles',  'media', 'pendiente',  '2026-10-20'),
('María González',   'Corte de suministro sin aviso previo',         'Electricidad',  'alta',  'en_proceso', '2026-10-25'),
('Carlos Soto',      'Solicitud de información de proyectos',        'Transparencia', 'baja',  'resuelta',   '2026-09-30'),
('Paula Muñoz',      'Consulta por subsidio eléctrico',              'Tarifas',       'media', 'pendiente',  '2026-10-28'),
('Jorge Díaz',       'Medidor con lectura errónea',                  'Electricidad',  'alta',  'pendiente',  '2026-10-05'),
('Camila Fuentes',   'Estación de servicio sin precios visibles',    'Combustibles',  'media', 'en_proceso', '2026-10-18'),
('Pedro Araya',      'Datos de generación por comuna',               'Transparencia', 'baja',  'pendiente',  '2026-10-30'),
('Sofía Castro',     'Reclamo por tarifa residencial',               'Tarifas',       'alta',  'pendiente',  '2026-10-02'),
('Diego Vargas',     'Consulta general',                             'Otros',         'baja',  'resuelta',   '2026-09-22'),
('Valentina Reyes',  'Poste dañado cerca de mi casa',                'Electricidad',  'media', 'pendiente',  '2026-10-27'),
('Matías Herrera',   'Variación de precios en parafina',             'Combustibles',  'media', 'resuelta',   '2026-10-01'),
('Fernanda Silva',   'Acceso a estudios tarifarios',                 'Transparencia', 'baja',  'en_proceso', '2026-10-22'),
('Rodrigo Núñez',    'Facturación duplicada',                        'Tarifas',       'alta',  'pendiente',  '2026-10-29'),
('Javiera Morales',  'Consulta por medidores inteligentes',          'Otros',         'baja',  'pendiente',  '2026-11-01');

-- Usuario de SOLO LECTURA para el MCP (la IA no puede modificar ni borrar datos)
-- Cambia la clave antes de cargar el archivo y usa la misma en MYSQL_PASS del .env
CREATE USER IF NOT EXISTS 'cne_lector'@'localhost' IDENTIFIED BY 'cambia_esta_clave';
GRANT SELECT ON cne_demo.* TO 'cne_lector'@'localhost';
FLUSH PRIVILEGES;
