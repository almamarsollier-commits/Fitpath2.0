# FitPath 2.0 — Bloque 2: propuesta de base de datos

**Estado:** dirección arquitectónica aprobada; tablas de negocio pendientes de implementación y de las decisiones abiertas registradas abajo.

**Fecha:** 2026-11-08

**Alcance:** modelo relacional para SQLite de desarrollo, plan de migraciones y arquitectura backend Flask.

**Base anterior:** gimnasio.db queda fuera del diseño y no se migrará ni modificará.

Esta propuesta conserva las 15 decisiones arquitectónicas y los acuerdos complementarios aprobados en DECISIONES.md. Las tablas de negocio siguen siendo diseño pendiente: la Microtarea 1 agrega únicamente infraestructura, registro de migraciones y configuración; no crea entidades de negocio ni endpoints.

## Convenciones del esquema

- Nombres en español y snake_case. SQLite usa INTEGER para identificadores, booleanos e importes; TEXT para cadenas, fechas y marcas de tiempo; REAL únicamente para mediciones físicas aproximadas.
- Las claves primarias serán INTEGER PRIMARY KEY. Las claves foráneas usarán ON DELETE RESTRICT para proteger registros históricos; las cuentas se desactivan en lugar de borrarlas.
- Instantes guardados como TEXT en formato fijo YYYY-MM-DDTHH:MM:SSZ y validados en el servidor. Fechas calendario, como vencimientos, usan YYYY-MM-DD. SQLite no tiene un tipo fecha/hora nativo.
- Los booleanos usan INTEGER NOT NULL CHECK (valor IN (0,1)). Las capacidades, series, repeticiones y descansos tienen CHECK de rango.
- El dinero usa INTEGER en unidades menores de la moneda. No se usan REAL ni cálculos monetarios en punto flotante.
- Toda conexión ejecuta PRAGMA foreign_keys=ON antes de iniciar transacciones. El esquema se crea desde cero mediante migraciones; no se reutiliza gimnasio.db.
- Los estados iniciales y ARS fueron aprobados el 2026-11-08. Los estados del catálogo (activa/habilitada) no se reutilizan como estados de suscripciones, inscripciones, clases, máquinas, pagos, tickets o liquidaciones.

## Modelo relacional propuesto

### Usuarios, roles, permisos y sedes

- **roles** — id_rol INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE. Contendrá los cinco roles acordados.
- **permisos** — id_permiso INTEGER PRIMARY KEY; clave TEXT NOT NULL UNIQUE; descripcion TEXT.
- **rol_permiso** — rol_id INTEGER NOT NULL FK → roles; permiso_id INTEGER NOT NULL FK → permisos; PRIMARY KEY (rol_id, permiso_id).
- **usuarios** — id_usuario INTEGER PRIMARY KEY; nombre TEXT NOT NULL; apellido TEXT NOT NULL; nombre_usuario TEXT NOT NULL COLLATE NOCASE UNIQUE; email TEXT NOT NULL COLLATE NOCASE UNIQUE; telefono TEXT; rol_id INTEGER NOT NULL FK → roles; activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)). No contiene contraseña ni hash en el Bloque 2; la autenticación corresponde al Bloque 3.
- **clientes** — id_cliente INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios.
- **jefes_sede** — id_jefe_sede INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios; sede_id INTEGER NOT NULL FK → sedes.
- **entrenadores** — id_entrenador INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios; especialidad TEXT NOT NULL.
- **entrenador_sede** — entrenador_id INTEGER NOT NULL FK → entrenadores; sede_id INTEGER NOT NULL FK → sedes; activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)); PRIMARY KEY (entrenador_id, sede_id).
- **tecnicos_mantenimiento** — id_tecnico INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios; sede_id INTEGER NOT NULL FK → sedes.
- **sedes** — id_sede INTEGER PRIMARY KEY; nombre TEXT NOT NULL; direccion TEXT NOT NULL; zona_horaria TEXT NOT NULL. La zona horaria usa un identificador IANA, validado en Flask.
- Por decisión aprobada el 2026-11-08, no se incluye una tabla administradores ni los campos sedes.administrador_id y membresias.administrador_id. El rol Administrador se representa en usuarios.rol_id mientras no se acuerden atributos o relaciones propios.

El perfil Jefe de sede y el perfil Técnico se asocian a una sede. Entrenadores pueden vincularse a varias sedes. La correspondencia entre rol y perfil debe validarse en el servicio; el refuerzo ante escrituras directas en la base sigue pendiente. Administrador se identifica por usuarios.rol_id y sus permisos; no obtiene acceso implícito a datos privados.

### Actividades, clases, disponibilidad e inscripciones

- **actividades** — id_actividad INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE.
- **actividad_sede** — actividad_id INTEGER NOT NULL FK → actividades; sede_id INTEGER NOT NULL FK → sedes; habilitada INTEGER NOT NULL DEFAULT 1 CHECK (habilitada IN (0,1)); PRIMARY KEY (actividad_id, sede_id).
- **clases** — id_clase INTEGER PRIMARY KEY; actividad_id INTEGER NOT NULL; sede_id INTEGER NOT NULL; entrenador_id INTEGER NOT NULL; inicio_utc TEXT NOT NULL; fin_utc TEXT NOT NULL; cupo_maximo INTEGER NOT NULL CHECK (cupo_maximo > 0); estado TEXT NOT NULL CHECK (estado IN ('programada','cancelada','realizada')). FK compuesta (actividad_id, sede_id) → actividad_sede; FK compuesta (entrenador_id, sede_id) → entrenador_sede; CHECK (fin_utc > inicio_utc). El vocabulario de estado fue aprobado el 2026-11-08.
- **disponibilidad_entrenador** — id_disponibilidad INTEGER PRIMARY KEY; entrenador_id INTEGER NOT NULL; sede_id INTEGER NOT NULL; dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 1 AND 7); hora_inicio TEXT NOT NULL; hora_fin TEXT NOT NULL; UNIQUE (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin); FK compuesta (entrenador_id, sede_id) → entrenador_sede; CHECK (hora_fin > hora_inicio). Los intervalos se interpretan como recurrencia semanal; solapamientos se validan en el servicio.
- **inscripciones** — id_inscripcion INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; clase_id INTEGER NOT NULL FK → clases; fecha_utc TEXT NOT NULL; estado TEXT NOT NULL CHECK (estado IN ('activa','cancelada')). Índice único parcial por (cliente_id, clase_id) WHERE estado='activa'.
- **asistencias** — id_asistencia INTEGER PRIMARY KEY; inscripcion_id INTEGER NOT NULL UNIQUE FK → inscripciones; fecha_utc TEXT NOT NULL; estado TEXT NOT NULL CHECK (estado IN ('presente','ausente')).

La clase referencia directamente actividad, sede y entrenador. Las FK compuestas impiden asignar una clase a una sede ajena a la actividad o al entrenador. Un trigger valida las relaciones habilitadas al crear o modificar clases; el servicio vuelve a comprobarlas al programarlas. La disponibilidad de cupos se calcula como cupo_maximo menos inscripciones activas; no se guarda una segunda cantidad que pueda quedar desactualizada.

### Objetivos, rutinas, ejercicios, progreso y alimentación

- **tipos_objetivo** — id_tipo_objetivo INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE.
- **objetivos** — id_objetivo INTEGER PRIMARY KEY; tipo_objetivo_id INTEGER NOT NULL FK → tipos_objetivo; nombre TEXT NOT NULL; descripcion TEXT; UNIQUE (tipo_objetivo_id, nombre). Sin FK inversa ni texto duplicado del tipo.
- **cliente_objetivo** — cliente_id INTEGER NOT NULL FK → clientes; objetivo_id INTEGER NOT NULL FK → objetivos; PRIMARY KEY (cliente_id, objetivo_id).
- **rutinas** — id_rutina INTEGER PRIMARY KEY; nombre TEXT NOT NULL; descripcion TEXT; fecha_creacion_utc TEXT NOT NULL; entrenador_id INTEGER NOT NULL FK → entrenadores; cliente_id INTEGER NOT NULL FK → clientes; objetivo_id INTEGER FK → objetivos; observaciones_entrenador TEXT.
- **ejercicios** — id_ejercicio INTEGER PRIMARY KEY; nombre TEXT NOT NULL; grupo_muscular TEXT; descripcion TEXT. No almacena peso: el peso es una prescripción individual.
- **rutina_ejercicio** — id_rutina_ejercicio INTEGER PRIMARY KEY; rutina_id INTEGER NOT NULL FK → rutinas; ejercicio_id INTEGER NOT NULL FK → ejercicios; orden INTEGER NOT NULL CHECK (orden > 0); series INTEGER NOT NULL CHECK (series > 0); repeticiones INTEGER NOT NULL CHECK (repeticiones > 0); peso_gramos INTEGER CHECK (peso_gramos IS NULL OR peso_gramos >= 0); descanso_segundos INTEGER NOT NULL CHECK (descanso_segundos >= 0); UNIQUE (rutina_id, orden).
- **progresos** — id_progreso INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; fecha_utc TEXT NOT NULL; peso_kg REAL CHECK (peso_kg IS NULL OR peso_kg > 0); porcentaje_grasa REAL CHECK (porcentaje_grasa IS NULL OR porcentaje_grasa BETWEEN 0 AND 100); rendimiento_ejercicios TEXT; observaciones TEXT.
- **planes_alimentacion** — id_plan_alimentacion INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; objetivo_id INTEGER NOT NULL FK → objetivos; nombre TEXT NOT NULL; descripcion TEXT; fecha_creacion_utc TEXT NOT NULL; fecha_actualizacion_utc TEXT NOT NULL; CHECK (fecha_actualizacion_utc >= fecha_creacion_utc).

El acceso a progreso y planes se filtra por cliente propietario y relación funcional autorizada. Las observaciones de entrenador no habilitan por sí solas acceso global a la ficha del cliente.

### Monedas, membresías, deudas y pagos

- **monedas** — codigo TEXT PRIMARY KEY CHECK (length(codigo) = 3 AND codigo = upper(codigo)); decimales INTEGER NOT NULL CHECK (decimales BETWEEN 0 AND 4). ARS será el primer código; el catálogo se mantiene extensible.
- **membresias** — id_membresia INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE; precio_unidades_menores INTEGER NOT NULL CHECK (precio_unidades_menores >= 0); moneda TEXT NOT NULL FK → monedas; descripcion TEXT; activa INTEGER NOT NULL CHECK (activa IN (0,1)). Gratuita y Premium son los nombres iniciales del SRS; no se inventan precios.
- **beneficios** — id_beneficio INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE; descripcion TEXT.
- **membresia_beneficio** — membresia_id INTEGER NOT NULL FK → membresias; beneficio_id INTEGER NOT NULL FK → beneficios; PRIMARY KEY (membresia_id, beneficio_id).
- **cliente_membresia** — id_cliente_membresia INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; membresia_id INTEGER NOT NULL FK → membresias; fecha_inicio TEXT NOT NULL; fecha_fin TEXT; estado TEXT NOT NULL CHECK (estado IN ('activa','vencida','cancelada')); UNIQUE (id_cliente_membresia, cliente_id); CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio). Índice único parcial por cliente WHERE estado='activa'.
- **deudas** — id_deuda INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; cliente_membresia_id INTEGER; concepto TEXT NOT NULL; importe_unidades_menores INTEGER NOT NULL CHECK (importe_unidades_menores > 0); moneda TEXT NOT NULL FK → monedas; vence_el TEXT NOT NULL; FK compuesta (cliente_membresia_id, cliente_id) → cliente_membresia(id_cliente_membresia, cliente_id), para comprobar que la suscripción pertenece al mismo cliente cuando se informa.
- **pagos** — id_pago INTEGER PRIMARY KEY; deuda_id INTEGER NOT NULL FK → deudas; importe_unidades_menores INTEGER NOT NULL CHECK (importe_unidades_menores > 0); metodo TEXT NOT NULL CHECK (metodo IN ('efectivo','transferencia','digital')); estado TEXT NOT NULL CHECK (estado IN ('en_proceso','realizado','anulado')); creado_utc TEXT NOT NULL; realizado_utc TEXT. La moneda del pago es la de su deuda. El vocabulario de estado fue aprobado el 2026-11-08. CHECK ((estado='realizado' AND realizado_utc IS NOT NULL) OR (estado<>'realizado' AND realizado_utc IS NULL)) mantiene consistente estado y realizado_utc.

Una deuda tiene cero o muchos pagos parciales. El saldo se deriva de pagos realizados y la deuda; no se guardan estados parciales duplicados. El servicio impide que la suma confirmada supere la deuda. No hay integración de pagos ni endpoints de pagos habilitados en esta etapa.

### Máquinas, mantenimiento y remuneraciones

- **maquinas** — id_maquina INTEGER PRIMARY KEY; sede_id INTEGER NOT NULL FK → sedes; tipo TEXT NOT NULL; estado TEXT NOT NULL CHECK (estado IN ('operativa','en_reparacion','fuera_de_servicio')); UNIQUE (id_maquina, sede_id). sede_id es la ubicación autorizada por la decisión arquitectónica 7. La diferencia del SRS se registra como aclaración sin modificar el PDF original.
- **tickets_mantenimiento** — id_ticket INTEGER PRIMARY KEY; maquina_id INTEGER NOT NULL FK → maquinas; tecnico_id INTEGER NOT NULL FK → tecnicos_mantenimiento; fecha_generacion_utc TEXT NOT NULL; descripcion TEXT NOT NULL; estado TEXT NOT NULL CHECK (estado IN ('abierto','en_proceso','resuelto','cancelado')); UNIQUE (id_ticket, maquina_id). El vocabulario de estado fue aprobado el 2026-11-08. Un trigger valida que técnico y máquina pertenezcan a la misma sede al crear o modificar el ticket.
- **historial_mantenimiento** — id_historial INTEGER PRIMARY KEY; maquina_id INTEGER NOT NULL FK → maquinas; ticket_id INTEGER; tecnico_id INTEGER NOT NULL FK → tecnicos_mantenimiento; fecha_utc TEXT NOT NULL; estado_anterior TEXT; estado_nuevo TEXT NOT NULL; descripcion TEXT. FK compuesta (ticket_id, maquina_id) → tickets_mantenimiento(id_ticket, maquina_id), para impedir enlazar un ticket de otra máquina. Estado anterior/nuevo usa los estados definidos para máquinas.
- **remuneraciones** — id_remuneracion INTEGER PRIMARY KEY; clase_id INTEGER NOT NULL FK → clases; importe_unidades_menores INTEGER NOT NULL CHECK (importe_unidades_menores >= 0); moneda TEXT NOT NULL FK → monedas; estado_liquidacion TEXT NOT NULL CHECK (estado_liquidacion IN ('pendiente','liquidada','anulada')); liquidada_utc TEXT. El vocabulario de liquidación fue aprobado el 2026-11-08. CHECK ((estado_liquidacion='liquidada' AND liquidada_utc IS NOT NULL) OR (estado_liquidacion<>'liquidada' AND liquidada_utc IS NULL)) exige liquidada_utc solo cuando el estado sea liquidada. La persona entrenadora se obtiene de la clase; no se registra pago al personal.
- **reportes** no es tabla; se derivan de datos existentes según la decisión arquitectónica 12.

## Relaciones y cardinalidades

- Rol 1:N usuarios; usuario 1:0..1 perfil de cliente, jefe de sede, entrenador o técnico. La coherencia rol-perfil se valida en el servicio.
- Actividad N:M sede mediante actividad_sede; entrenador N:M sede mediante entrenador_sede.
- Actividad/sede 1:N clases y entrenador/sede 1:N clases. Cada clase pertenece a una combinación autorizada en ambas relaciones.
- Clase 1:N inscripciones; inscripción 1:0..1 asistencia. Se permite conservar filas canceladas y reactivar mediante una inscripción nueva.
- Tipo de objetivo 1:N objetivos; clientes N:M objetivos mediante cliente_objetivo.
- Cliente 1:N rutinas, progreso, planes de alimentación y suscripciones; entrenador 1:N rutinas.
- Rutina N:M ejercicios mediante rutina_ejercicio, con orden y parámetros por instancia.
- Membresía N:M beneficios mediante membresia_beneficio; cliente 1:N suscripciones históricas, con máximo una activa.
- Cliente 1:N deudas; deuda 1:N pagos parciales. No hay FK de vuelta desde deuda a pago.
- Sede 1:N máquinas y técnicos; máquina 1:N tickets e historial; clase a remuneraciones: cardinalidad pendiente; no se fija UNIQUE(clase_id) hasta resolverla.

## Restricciones y transacciones

- Activar claves foráneas en cada conexión y ejecutar PRAGMA foreign_key_check en verificaciones de esquema. Triggers protegen invariantes entre filas, como la sede compartida por ticket, máquina y técnico.
- Índices únicos parciales impiden más de una inscripción activa al mismo par cliente/clase y más de una membresía activa por cliente. SQLite permite índices UNIQUE parciales con cláusula WHERE.
- Reserva: BEGIN IMMEDIATE; validar que la clase futura esté programada y habilitada, comprobar la membresía requerida, comprobar relación cliente-clase y cupo; insertar; confirmar. La transacción y el índice único previenen carreras, duplicados y sobrecupo.
- Pagos parciales: dentro de una transacción, sumar pagos realizados, rechazar importe mayor al saldo, insertar pago y confirmar estado/fecha. No existe CHECK SQL que valide una suma entre filas; esa regla se prueba en el servicio y con solicitudes concurrentes.
- Asistencia: el entrenador debe ser el asignado a la clase y el cliente debe tener inscripción activa; se valida en el backend.
- Los vocabularios aprobados se aplicarán en las migraciones de negocio; esta Microtarea 1 no crea sus tablas.
- No se eliminan en cascada pagos, asistencias, remuneraciones ni historial de mantenimiento.

## Arquitectura Flask propuesta

Flask será el único backend futuro de FitPath 2.0. apy.py y server.js permanecen como referencia anterior; no se ejecutan ni se conectan al frontend nuevo.

    backend/
      fitpath/
        __init__.py              create_app
        config.py
        api/v1/public.py         salud y datos públicos aprobados
        db/connection.py         sqlite3 y configuración por conexión
        db/migrations.py         registro y aplicación de SQL versionado
        db/schema/               migraciones SQL inmutables
        db/seed/                 roles y permisos de referencia
        models/                  estructuras del dominio
        repositories/            consultas parametrizadas
        services/                reglas y transacciones
        validators/              validación del servidor
        errors.py
      tests/
        unit/
        integration/
        security/
      instance/                   bases locales excluidas de Git

La factory create_app configura el entorno y registra solo blueprints permitidos. Antes de autenticación real, no registra rutas privadas ni administrativas. Las consultas públicas, si se habilitan, contienen únicamente campos no personales. Los módulos privados se incorporan y registran después de autenticación real; el selector demo nunca genera una identidad confiable.

## Archivos SQL versionados propuestos

- 0001_roles_usuarios_sedes_permisos.sql — roles, permisos, usuarios, perfiles, sedes y asignaciones base.
- 0002_actividades_clases_inscripciones.sql — actividades, actividad_sede, entrenador_sede, disponibilidad, clases, inscripciones y asistencias.
- 0003_objetivos_rutinas_progreso.sql — objetivos, rutinas, ejercicios, progreso y planes de alimentación.
- 0004_monedas_membresias_deudas_pagos.sql — monedas, membresías, beneficios, suscripciones, deudas y pagos.
- 0005_maquinas_mantenimiento_remuneraciones.sql — máquinas, tickets, historial y remuneraciones.
- 0006_indices_y_triggers_integridad.sql — índices parciales y disparadores que deban proteger invariantes entre tablas.
- La tabla técnica schema_migrations guarda la versión aplicada y el instante UTC. Cada migración se registra en una transacción.
- Datos de prueba se cargan solo en una base temporal/configuración de prueba. Roles y permisos iniciales son datos de referencia, separados de usuarios ficticios. No se siembran credenciales.
- No se modifica ni se copia gimnasio.db.

## Seguridad y privacidad desde el diseño

- Consultas SQL parametrizadas; validación estricta del cuerpo, tipos, tamaños, enums, rangos y fechas en servidor.
- Acceso denegado por defecto. permisos define acciones; servicios además filtran por sede, propiedad del cliente, clase asignada y necesidad funcional.
- Clientes solo acceden a su información. Entrenadores acceden a clientes vinculados por sus clases/inscripciones o rutinas autorizadas. Técnicos quedan limitados a su sede. El rol Administrador no concede por sí solo lectura de progreso, alimentación o pagos privados.
- No se aceptan roles del cliente ni el selector demo como prueba de autorización. Antes de autenticación real no se registran endpoints sensibles.
- No se guardan contraseñas en texto claro ni secretos en el repositorio. Credenciales, sesiones y OAuth se diseñan en Bloque 3.
- Respuestas y logs no exponen hashes, contraseñas, tokens, datos médicos innecesarios ni trazas internas. Se aplica minimización de datos y política de retención antes de producir.
- La base de desarrollo, pruebas y cualquier producción se separan por configuración. Los fixtures de prueba son explícitamente ficticios.

## Estrategia de pruebas

- Esquema nuevo creado en base temporal: PRAGMA foreign_keys = 1, PRAGMA foreign_key_check vacío, restricciones CHECK, UNIQUE y FK.
- Intentos de crear perfiles con usuarios/roles incompatibles, clases en sedes no asignadas, tickets de otra sede, asistencias sin inscripción y referencias inexistentes deben rechazarse.
- Pruebas concurrentes con conexiones independientes verifican que solicitudes de inscripción no generan duplicados ni superan el cupo.
- Pruebas de membresía verifican una sola activa y preservación del historial; de pagos, importes enteros, pagos parciales y rechazo de saldo excedido; de remuneraciones, moneda/estado coherentes.
- Pruebas de acceso indebido cubren otro cliente, otra sede, entrenador no asignado, técnico de otra sede y administrador sin necesidad funcional. Antes de autenticación, verificar también que esas rutas no figuran en el mapa HTTP.
- Prueba de rutas públicas verifica que ningún campo privado se filtra. Prueba de configuración confirma que dev y tests no apuntan a gimnasio.db ni a la misma base.
- El SRS fija 500 usuarios concurrentes, operaciones habituales menores a 2 segundos y disponibilidad de 99,5 %. SQLite permite múltiples lectores, pero solo un escritor por archivo a la vez; el prototipo no debe declararse conforme sin pruebas de carga y disponibilidad. Si el despliegue previsto excede sus límites, se evalúa una base cliente-servidor antes de producción. Referencias: https://www.sqlite.org/whentouse.html y https://www.sqlite.org/isolation.html.

## Decisiones de esquema aún pendientes

- La cantidad de remuneraciones permitidas por clase y su regla para evitar duplicados.
- Cómo los beneficios de una membresía habilitan clases o actividades.
- Cómo asegurar desde la base la correspondencia entre usuarios.rol_id y sus tablas de perfil.
- Email, nombre de usuario o ambos como identificador de inicio de sesión, antes del Bloque 3.

Estas decisiones no se implementan ni se resuelven por inferencia en la Microtarea 1.

## Primeras tres microtareas

1. **Base Flask y conexión SQLite.** Crear factory, configuración de desarrollo/prueba, conexión con FK habilitadas y runner de migraciones. Pruebas: app factory con DB temporal, PRAGMA por conexión, runner versionado; seguridad: rutas privadas ausentes y rechazo de ruta a gimnasio.db.
2. **Migración de identidad, sedes y permisos.** Crear roles/permisos, usuarios y perfiles mínimos, sedes con zona horaria y relaciones entrenador-sede. Pruebas: UNIQUE, FK, perfil/rol y validación de timezone; seguridad: no sembrar credenciales ni usuarios reales.
3. **Módulo de clases e inscripciones.** Crear catálogos, actividad_sede, entrenador_sede, disponibilidad, clases, inscripciones y asistencias; implementar servicio transaccional de reserva, sin exponer su endpoint antes de auth. Pruebas: FK compuestas, duplicados, cupo concurrente, entrenador/sede, inscripción/asistencia; seguridad: una prueba de autorización indebida debe confirmar que no se modifica la DB.

**Próximo paso:** La Microtarea 1 agrega la infraestructura Flask y SQLite; el usuario reporta 5 pruebas aprobadas con Python 3.15.2 desde su terminal de VS Code; el entorno de Codex no dispone de Python para repetirlas. No se han creado tablas de negocio ni endpoints y la Microtarea 2 no se ha iniciado.
