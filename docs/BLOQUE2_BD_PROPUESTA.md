# FitPath 2.0 — Bloque 2: propuesta de base de datos

**Estado:** Las migraciones 0001–0008 de las Microtareas 1–9 están implementadas. El usuario confirmó que la suite acumulada terminó satisfactoriamente desde VS Code. La comprobación aislada de M9 con SQLite temporal también fue satisfactoria. No se habilitan endpoints sensibles ni autenticación.

**Fecha:** 2026-11-09

**Alcance:** modelo relacional para SQLite de desarrollo, plan de migraciones y arquitectura backend Flask.

**Base anterior:** gimnasio.db queda fuera del diseño y no se migrará ni modificará.

> **Nota de vigencia (2026-11-18):** este documento conserva la propuesta y los
> acuerdos del Bloque 2. El estado actual avanzó más allá de las migraciones
> 0001–0008 descritas aquí: existen migraciones hasta 0014, autenticación,
> permisos y APIs por rol. Para el estado vigente consultar
> `docs/ESTADO_ENTREGA.md` y `docs/GUIA_BACKEND_APIS.md`; las referencias de
> implementación de este documento son históricas.

Esta propuesta conserva las 15 decisiones arquitectónicas y los acuerdos complementarios aprobados en DECISIONES.md. Las Microtareas 1 a 3 incorporaron infraestructura, identidad, sedes, actividades, entrenadores y clases. La Microtarea 4 agrega clientes, inscripciones, asistencias y un servicio interno sin endpoints. Las Microtareas 5 y 6 agregan objetivos, rutinas, ejercicios, progreso y alimentación. La Microtarea 7 agrega el catálogo financiero y un servicio interno de registro, sin endpoints, pasarela de pago ni autorización real. La Microtarea 8 agrega perfiles de sede y mantenimiento. La Microtarea 9 completa las tablas principales con remuneraciones, sin pagos reales ni endpoints.

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

- **roles** — id_rol INTEGER PRIMARY KEY; nombre TEXT NOT NULL COLLATE NOCASE UNIQUE, no vacío. Implementada en la migración 0001_identidad_roles_permisos_sedes.sql. El seed controlado contiene los cinco nombres aprobados.
- **permisos** — id_permiso INTEGER PRIMARY KEY; clave TEXT NOT NULL COLLATE NOCASE UNIQUE, no vacía; descripcion TEXT opcional. La tabla está implementada; el catálogo permanece vacío hasta aprobar permisos concretos.
- **rol_permiso** — rol_id INTEGER NOT NULL FK → roles; permiso_id INTEGER NOT NULL FK → permisos; PRIMARY KEY (rol_id, permiso_id). Implementada y vacía; no se asignan permisos por defecto.
- **usuarios** — id_usuario INTEGER PRIMARY KEY; nombre y apellido TEXT NOT NULL; nombre_usuario TEXT NOT NULL COLLATE NOCASE UNIQUE; email TEXT NOT NULL COLLATE NOCASE UNIQUE; telefono TEXT opcional; rol_id INTEGER NOT NULL FK → roles; activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)). Campos requeridos no vacíos y sin espacios externos. Email y nombre de usuario se almacenan recortados y en minúscula ASCII. No contiene contraseña ni hash; la autenticación corresponde al Bloque 3.
- **clientes** — id_cliente INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios. Implementada en 0003, sin duplicar datos del usuario. La compatibilidad entre usuarios.rol_id y el perfil Cliente sigue pendiente.
- **jefes_sede** — id_jefe_sede INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios; sede_id INTEGER NOT NULL FK → sedes. Implementada en 0007; la compatibilidad del rol sigue pendiente.
- **entrenadores** — id_entrenador INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios; especialidad TEXT NOT NULL, no vacía y recortada. Implementada en 0002. La FK no comprueba que usuarios.rol_id sea Entrenador: esa compatibilidad permanece pendiente.
- **entrenador_sede** — entrenador_id INTEGER NOT NULL FK → entrenadores; sede_id INTEGER NOT NULL FK → sedes; activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)); PRIMARY KEY (entrenador_id, sede_id). Implementada como relación N:M.
- **tecnicos_mantenimiento** — id_tecnico INTEGER PRIMARY KEY; usuario_id INTEGER NOT NULL UNIQUE FK → usuarios; sede_id INTEGER NOT NULL FK → sedes. Implementada en 0007; la compatibilidad del rol sigue pendiente.
- **sedes** — id_sede INTEGER PRIMARY KEY; nombre, direccion y zona_horaria TEXT NOT NULL, no vacíos y sin espacios externos. Implementada. La zona horaria usa un identificador IANA que deberá validarse en Flask.
- Por decisión aprobada el 2026-11-08, no se incluye una tabla administradores ni los campos sedes.administrador_id y membresias.administrador_id. El rol Administrador se representa en usuarios.rol_id mientras no se acuerden atributos o relaciones propios.

Los perfiles Jefe de sede y Técnico, asociados cada uno a una sede, están implementados en 0007. El perfil Entrenador y su relación con sedes ya estaban implementados. La correspondencia entre usuarios.rol_id y sus perfiles no se garantiza en SQLite; esa decisión continúa pendiente. Administrador se identifica por usuarios.rol_id y los permisos que se aprueben; no obtiene acceso implícito a datos privados.

### Actividades, clases, disponibilidad e inscripciones

- **actividades** — id_actividad INTEGER PRIMARY KEY; nombre TEXT NOT NULL COLLATE NOCASE UNIQUE, no vacío y recortado. Implementada; representa el tipo de entrenamiento.
- **actividad_sede** — actividad_id INTEGER NOT NULL FK → actividades; sede_id INTEGER NOT NULL FK → sedes; habilitada INTEGER NOT NULL DEFAULT 1 CHECK (habilitada IN (0,1)); PRIMARY KEY (actividad_id, sede_id). Implementada como relación N:M.
- **clases** — id_clase INTEGER PRIMARY KEY; actividad_id, sede_id y entrenador_id INTEGER NOT NULL; inicio_utc y fin_utc TEXT NOT NULL en UTC canónico YYYY-MM-DDTHH:MM:SSZ; cupo_maximo INTEGER NOT NULL CHECK (cupo_maximo > 0); estado TEXT NOT NULL CHECK (estado IN ('programada','cancelada','realizada')). FK compuestas (actividad_id, sede_id) → actividad_sede y (entrenador_id, sede_id) → entrenador_sede; CHECK (fin_utc > inicio_utc). Implementada en 0002.
- **disponibilidad_entrenador** — id_disponibilidad INTEGER PRIMARY KEY; entrenador_id y sede_id INTEGER NOT NULL; dia_semana INTEGER NOT NULL CHECK (dia_semana BETWEEN 1 AND 7); hora_inicio y hora_fin TEXT NOT NULL con formato local HH:MM de 00:00 a 23:59; UNIQUE (entrenador_id, sede_id, dia_semana, hora_inicio, hora_fin); FK compuesta (entrenador_id, sede_id) → entrenador_sede; CHECK (hora_fin > hora_inicio). Implementada como recurrencia semanal. No admite intervalos que crucen medianoche; solapamientos se validan en el servicio.
- **inscripciones** — id_inscripcion INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; clase_id INTEGER NOT NULL FK → clases; fecha_utc TEXT NOT NULL en formato UTC canónico; estado TEXT NOT NULL CHECK (estado IN ('activa','cancelada')). Índice UNIQUE parcial por (cliente_id, clase_id) WHERE estado='activa' e índices para consultar por cliente y clase. Implementada en 0003.
- **asistencias** — id_asistencia INTEGER PRIMARY KEY; inscripcion_id INTEGER NOT NULL UNIQUE FK → inscripciones; fecha_utc TEXT NOT NULL en formato UTC canónico; estado TEXT NOT NULL CHECK (estado IN ('presente','ausente')). Implementada en 0003; no duplica cliente, clase ni entrenador. La autorización del entrenador queda pendiente.

La clase referencia directamente actividad, sede y entrenador. Las FK compuestas impiden combinar una actividad-sede o entrenador-sede inexistentes. Triggers rechazan insertar o reasignar una clase cuando la actividad no está habilitada en la sede o el vínculo entrenador-sede no está activo. Desactivar un vínculo no elimina clases existentes; el ciclo de cancelación o conservación histórica deberá tratarse en servicios. La base no comprueba solapamientos ni convierte la hora UTC a la zona IANA de la sede; esos controles corresponden al backend. La disponibilidad semanal queda registrada, pero su compatibilidad con cada clase se validará en el servicio. El cupo disponible no se almacena como contador duplicado.

Los índices inversos de actividad_sede y entrenador_sede facilitan consultas por sede y comprobaciones de sus claves foráneas. Los índices de clases cubren la agenda por sede/inicio, entrenador/sede/inicio y actividad/sede/inicio; el índice de disponibilidad permite filtrar por sede y día. Las claves primarias y restricciones UNIQUE existentes cubren las búsquedas por actividad, entrenador y franja exacta.

### Objetivos, rutinas, ejercicios, progreso y alimentación

- **tipos_objetivo** — id_tipo_objetivo INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE.
- **objetivos** — id_objetivo INTEGER PRIMARY KEY; tipo_objetivo_id INTEGER NOT NULL FK → tipos_objetivo; nombre TEXT NOT NULL; descripcion TEXT; UNIQUE (tipo_objetivo_id, nombre). Sin FK inversa ni texto duplicado del tipo.
- **cliente_objetivo** — cliente_id INTEGER NOT NULL FK → clientes; objetivo_id INTEGER NOT NULL FK → objetivos; PRIMARY KEY (cliente_id, objetivo_id).
- **rutinas** — id_rutina INTEGER PRIMARY KEY; nombre TEXT NOT NULL; descripcion TEXT; fecha_creacion_utc TEXT NOT NULL; entrenador_id INTEGER NOT NULL FK → entrenadores; cliente_id INTEGER NOT NULL FK → clientes; objetivo_id INTEGER FK → objetivos; observaciones_entrenador TEXT.
- **ejercicios** — id_ejercicio INTEGER PRIMARY KEY; nombre TEXT NOT NULL; grupo_muscular TEXT; descripcion TEXT. No almacena peso: el peso es una prescripción individual.
- **rutina_ejercicio** — id_rutina_ejercicio INTEGER PRIMARY KEY; rutina_id INTEGER NOT NULL FK → rutinas; ejercicio_id INTEGER NOT NULL FK → ejercicios; orden INTEGER NOT NULL CHECK (orden > 0); series INTEGER NOT NULL CHECK (series > 0); repeticiones INTEGER NOT NULL CHECK (repeticiones > 0); peso_gramos INTEGER CHECK (peso_gramos IS NULL OR peso_gramos >= 0); descanso_segundos INTEGER NOT NULL CHECK (descanso_segundos >= 0); UNIQUE (rutina_id, orden).

La migración 0004 implementa estos seis objetos con FK restrictivas, restricciones de texto y fecha UTC canónica, parámetros enteros y orden único por rutina. La clave primaria de cliente_objetivo permite buscar objetivos de un cliente y su índice inverso consultar clientes por objetivo; los índices de rutinas filtran por cliente/entrenador y el de rutina_ejercicio por ejercicio. rutinas.objetivo_id referencia un objetivo existente, pero la base no garantiza que ese objetivo figure en cliente_objetivo para el mismo cliente; esa regla queda pendiente. No se agrega una tabla entrenador-cliente ni autorización de acceso.

- **progresos** — id_progreso INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; fecha_utc TEXT NOT NULL en UTC canónico; peso_kg REAL opcional CHECK numérico y > 0; porcentaje_grasa REAL opcional CHECK numérico y entre 0 y 100; rendimiento_ejercicios TEXT; observaciones TEXT. Implementada en 0005 con índice por cliente/fecha.
- **planes_alimentacion** — id_plan_alimentacion INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; objetivo_id INTEGER NOT NULL FK → objetivos; nombre TEXT NOT NULL; descripcion TEXT opcional; indicaciones TEXT opcional; fecha_creacion_utc y fecha_actualizacion_utc TEXT NOT NULL en UTC canónico; CHECK (fecha_actualizacion_utc >= fecha_creacion_utc). Implementada en 0005.
La migración 0005 agrega FK restrictivas, validaciones de mediciones y fechas, y los índices por cliente/fecha y objetivo. La FK directa plan-objetivo no verifica que el objetivo pertenezca al mismo cliente mediante cliente_objetivo; esa decisión permanece pendiente. El campo indicaciones se incorpora por el requisito explícito de la Microtarea 6.

El acceso a progreso y planes se filtra por cliente propietario y relación funcional autorizada. Las observaciones de entrenador no habilitan por sí solas acceso global a la ficha del cliente.

### Monedas, membresías, deudas y pagos

- **monedas** — codigo TEXT PRIMARY KEY con código ISO de tres letras mayúsculas; decimales INTEGER entre 0 y 4. Implementada en 0006. El seed explícito e idempotente carga ARS con dos decimales; se pueden añadir monedas sin cambiar el esquema.
- **membresias** — id_membresia INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE; precio_unidades_menores INTEGER NOT NULL CHECK (>= 0 y entero); moneda TEXT NOT NULL FK → monedas; descripcion TEXT; activa INTEGER NOT NULL CHECK (activa IN (0,1)). Implementada en 0006. Gratuita y Premium son nombres referenciados por el SRS, pero no se insertan hasta definir precios comerciales; no se inventan importes.
- **beneficios** — id_beneficio INTEGER PRIMARY KEY; nombre TEXT NOT NULL UNIQUE; descripcion TEXT. **membresia_beneficio** crea la relación N:M con clave primaria compuesta. Ambas están implementadas en 0006. Esta relación no especifica elegibilidad para clases o actividades, cuestión todavía pendiente.
- **cliente_membresia** — id_cliente_membresia INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; membresia_id INTEGER NOT NULL FK → membresias; fecha_inicio TEXT NOT NULL; fecha_fin TEXT; estado TEXT NOT NULL CHECK (estado IN ('activa','vencida','cancelada')); UNIQUE (id_cliente_membresia, cliente_id); CHECK (fecha_fin IS NULL OR fecha_fin >= fecha_inicio). Implementada en 0006 con fechas ISO, historial restrictivo e índice único parcial por cliente WHERE estado='activa'.
- **deudas** — id_deuda INTEGER PRIMARY KEY; cliente_id INTEGER NOT NULL FK → clientes; cliente_membresia_id INTEGER opcional; concepto TEXT NOT NULL; importe_unidades_menores INTEGER NOT NULL CHECK (importe > 0 y entero); moneda TEXT NOT NULL FK → monedas; vence_el TEXT NOT NULL. La FK compuesta (cliente_membresia_id, cliente_id) → cliente_membresia(id_cliente_membresia, cliente_id) garantiza que, cuando se informa una suscripción, pertenezca al mismo cliente. Implementada en 0006.
- **pagos** — id_pago INTEGER PRIMARY KEY; deuda_id INTEGER NOT NULL FK → deudas; importe_unidades_menores INTEGER NOT NULL CHECK (importe > 0 y entero); metodo TEXT NOT NULL CHECK (efectivo, transferencia, digital); estado TEXT NOT NULL CHECK (en_proceso, realizado, anulado); creado_utc TEXT NOT NULL; realizado_utc TEXT. Implementada en 0006. La moneda se obtiene de la deuda. CHECK exige realizado_utc cuando el estado sea realizado y lo prohíbe para los demás estados.

Una deuda tiene cero o muchos pagos parciales. El saldo se deriva de pagos realizados y la deuda; no se guardan saldos duplicados. El servicio interno `register_completed_payment` registra únicamente pagos ya recibidos, usa `BEGIN IMMEDIATE` y rechaza importes que excedan el saldo confirmado. No valida identidad ni autorización, no cambia pagos pendientes/anulados, no integra proveedores y no se expone por HTTP. Antes de habilitar su uso desde una interfaz deben incorporarse autenticación y permisos reales.

### Máquinas, mantenimiento y remuneraciones

- **maquinas** — id_maquina INTEGER PRIMARY KEY; sede_id INTEGER NOT NULL FK → sedes; tipo TEXT NOT NULL; estado TEXT NOT NULL CHECK (estado IN ('operativa','en_reparacion','fuera_de_servicio')); UNIQUE (id_maquina, sede_id). Implementada en 0007. `sede_id` define la ubicación conforme a la decisión arquitectónica 7; no se usa la sede del técnico como sustituto.
- **tickets_mantenimiento** — id_ticket INTEGER PRIMARY KEY; maquina_id INTEGER NOT NULL FK → maquinas; tecnico_id INTEGER NOT NULL FK → tecnicos_mantenimiento; fecha_generacion_utc TEXT NOT NULL; descripcion TEXT NOT NULL; estado TEXT NOT NULL CHECK (estado IN ('abierto','en_proceso','resuelto','cancelado')); UNIQUE (id_ticket, maquina_id). Implementada en 0007. Triggers impiden crear o reasignar un ticket entre técnicos y máquinas de sedes distintas.
- **historial_mantenimiento** — id_historial INTEGER PRIMARY KEY; maquina_id INTEGER NOT NULL FK → maquinas; ticket_id INTEGER opcional; tecnico_id INTEGER NOT NULL FK → tecnicos_mantenimiento; fecha_utc TEXT NOT NULL; estado_anterior TEXT; estado_nuevo TEXT NOT NULL; descripcion TEXT. Implementada en 0007. La FK compuesta (ticket_id, maquina_id) → tickets_mantenimiento(id_ticket, maquina_id) impide enlazar un ticket de otra máquina; triggers validan sede entre técnico y máquina. Los estados anterior/nuevo usan el catálogo de estados de máquina.

Los estados y marcas de tiempo se validan en 0007. Todos los vínculos históricos usan `ON DELETE RESTRICT`. Triggers adicionales rechazan cambios de sede de una máquina o un técnico cuando dejarían registros existentes de tickets/historial con sedes incompatibles. No se fuerza que `usuarios.rol_id` coincida con el perfil, decisión todavía pendiente.
- **remuneraciones** — id_remuneracion INTEGER PRIMARY KEY; clase_id INTEGER NOT NULL UNIQUE FK → clases; importe_unidades_menores INTEGER NOT NULL CHECK (entero y >= 0); moneda TEXT NOT NULL FK → monedas; estado_liquidacion TEXT NOT NULL CHECK (pendiente/liquidada/anulada); liquidada_utc TEXT opcional con formato UTC canónico. Implementada en 0008. El CHECK exige fecha únicamente para estado liquidada. UNIQUE(clase_id) permite cero o una remuneración por clase, incluso si se anula; no se reemplaza una fila histórica. La remuneración no duplica entrenador: se obtiene de la clase y un trigger impide reasignar ese entrenador después de registrar una remuneración. Otros triggers impiden cambiar la clase asociada o borrar la fila; se anula mediante estado. No se implementan pagos reales al personal.
- **reportes** no es tabla; se derivan de datos existentes según la decisión arquitectónica 12.

## Relaciones y cardinalidades

- Rol 1:N usuarios; usuario 1:0..1 perfil de cliente, jefe de sede, entrenador o técnico. La coherencia rol-perfil se valida en el servicio.
- Actividad N:M sede mediante actividad_sede; entrenador N:M sede mediante entrenador_sede.
- Actividad/sede 1:N clases y entrenador/sede 1:N clases. Cada clase pertenece a una combinación autorizada en ambas relaciones.
- Clase 1:N inscripciones; inscripción 1:0..1 asistencia. Se conservan filas canceladas y se impide más de una inscripción activa para el mismo cliente y clase. El flujo de cancelación de clases e inscripciones queda pendiente de revisión de negocio.
- Tipo de objetivo 1:N objetivos; clientes N:M objetivos mediante cliente_objetivo.
- Cliente 1:N rutinas, progreso, planes de alimentación y suscripciones; entrenador 1:N rutinas.
- Rutina N:M ejercicios mediante rutina_ejercicio, con orden y parámetros por instancia.
- Membresía N:M beneficios mediante membresia_beneficio; cliente 1:N suscripciones históricas, con máximo una activa.
- Cliente 1:N deudas; deuda 1:N pagos parciales. No hay FK de vuelta desde deuda a pago.
- Sede 1:N máquinas, técnicos y jefes de sede; máquina 1:N tickets e historial; clase 1:0..1 remuneración mediante UNIQUE(clase_id).

## Restricciones y transacciones

- Activar claves foráneas en cada conexión y ejecutar PRAGMA foreign_key_check en verificaciones de esquema. Triggers protegen invariantes entre filas, como la sede compartida por ticket, máquina y técnico.
- Índices únicos parciales impiden más de una inscripción activa al mismo par cliente/clase y más de una membresía activa por cliente. SQLite permite índices UNIQUE parciales con cláusula WHERE.
- Inscripción interna M4: BEGIN IMMEDIATE; comprobar clase futura programada, actividad habilitada, entrenador activo, duplicado y cupo; insertar y confirmar. El servicio no valida elegibilidad de membresía ni identidad/autorización del solicitante, y no se expone por HTTP o el selector demo. Una reserva completa requiere resolver esos controles antes de habilitar operaciones externas.
- Pagos parciales: dentro de una transacción, sumar pagos realizados, rechazar importe mayor al saldo, insertar pago y confirmar estado/fecha. No existe CHECK SQL que valide una suma entre filas; esa regla se prueba en el servicio y con solicitudes concurrentes.
- Asistencia: el esquema conserva una única fila por inscripción. Antes de habilitar su registro, un servicio debe validar inscripción activa, estado de la clase y autorización del entrenador autenticado; no existe operación HTTP para asistencia.
- Los vocabularios aprobados se aplicarán en las migraciones de negocio. La Microtarea 2 solo crea las cinco tablas de identidad y sedes, sin perfiles ni módulos funcionales.
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

## Migraciones y datos iniciales

- 0001_identidad_roles_permisos_sedes.sql — implementada: roles, permisos, rol_permiso, usuarios y sedes.
- 0002_actividades_entrenadores_clases.sql — implementada: entrenadores, entrenador_sede, actividades, actividad_sede, disponibilidad_entrenador y clases.
- 0003_clientes_inscripciones_asistencias.sql — implementada: clientes, inscripciones y asistencias.
- 0004_objetivos_rutinas.sql — implementada: objetivos, rutinas y ejercicios.
- 0005_progreso_alimentacion.sql — implementada: progresos y planes de alimentación.
- 0006_membresias_beneficios_suscripciones_pagos.sql — implementada localmente: monedas, membresías, beneficios, relación membresía-beneficio, suscripciones, deudas y pagos.
- 0007_mantenimiento_perfiles.sql — implementada localmente: técnicos, jefes de sede, máquinas, tickets e historial; no impone compatibilidad rol-perfil.
- 0008_remuneraciones.sql — implementada localmente: máximo una remuneración por clase, moneda del catálogo, estado/fecha consistentes y protección del entrenador histórico.
- La tabla técnica schema_migrations guarda versión, nombre, checksum e instante UTC; cada archivo SQL se registra dentro de su transacción.
- backend/fitpath/seeds.py y los comandos python -m backend.seed --environment development o python -m backend.seed --environment testing cargan explícitamente los cinco roles y ARS (dos decimales). No se ejecutan con la factory ni con migraciones; no siembran usuarios, contraseñas, membresías con precios ni beneficios.
- SQLite NOCASE y lower() solo realizan conversión de mayúsculas ASCII. El esquema exige texto recortado y minúscula ASCII para emails y nombres de usuario, pero no puede garantizar equivalencia/casefold Unicode frente a escrituras directas. Las escrituras futuras del servidor deben normalizar con NFC/casefold; si se requiere garantía también ante SQL directo, habrá que aprobar una collation/función SQLite registrada o una restricción de caracteres.
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
- Pruebas temporales de M7 cubren el catálogo y las FK, máximo una suscripción activa con historial, deudas asociadas al cliente correcto, monedas e importes enteros, pagos parciales, rechazo de sobrepago y concurrencia con conexiones independientes.
- Pruebas temporales de M8 cubren los perfiles de técnico/jefe, sede de máquinas, estados, tickets e historial, triggers de sede, rollback, checksum e idempotencia.
- Pruebas temporales de M9 cubren cardinalidad, importes, moneda, estados/fechas, FK, conservación de historial, inmutabilidad del entrenador destinatario, idempotencia y rollback. El usuario confirmó la ejecución satisfactoria de la suite acumulada desde VS Code.
- Pruebas de acceso indebido cubren otro cliente, otra sede, entrenador no asignado, técnico de otra sede y administrador sin necesidad funcional. Antes de autenticación, verificar también que esas rutas no figuran en el mapa HTTP.
- Prueba de rutas públicas verifica que ningún campo privado se filtra. Prueba de configuración confirma que dev y tests no apuntan a gimnasio.db ni a la misma base.
- El SRS fija 500 usuarios concurrentes, operaciones habituales menores a 2 segundos y disponibilidad de 99,5 %. SQLite permite múltiples lectores, pero solo un escritor por archivo a la vez; el prototipo no debe declararse conforme sin pruebas de carga y disponibilidad. Si el despliegue previsto excede sus límites, se evalúa una base cliente-servidor antes de producción. Referencias: https://www.sqlite.org/whentouse.html y https://www.sqlite.org/isolation.html.

## Decisiones de esquema aún pendientes

- Cómo los beneficios de una membresía habilitan clases o actividades.
- Elegibilidad por membresía antes de una inscripción y autorización del entrenador autenticado para registrar asistencia.
- Tratamiento de clases e inscripciones canceladas más allá de conservar filas históricas.
- Conversión de horarios locales a UTC, solapamientos de disponibilidad y normalización Unicode del catálogo de actividades.
- Cómo asegurar desde la base la correspondencia entre usuarios.rol_id y sus tablas de perfil.
- Email, nombre de usuario o ambos como identificador de inicio de sesión, antes del Bloque 3.
- Si una rutina que indica objetivo debe exigir que ese objetivo esté asociado al mismo cliente, y si se comprobará mediante FK compuesta, trigger o servicio.
- Si el objetivo de un plan de alimentación debe estar asociado al mismo cliente mediante cliente_objetivo o si alcanza la FK directa a objetivos.
- Cómo definir la asignación efectiva y la autorización entre entrenador y cliente; la Microtarea 5 no agrega una relación entrenador-cliente.

Estas decisiones permanecen pendientes; M7 solo guarda la relación genérica entre membresías y beneficios y no aplica elegibilidad a inscripciones. La cardinalidad de remuneraciones fue aprobada para M9; esto no resuelve las demás reglas de negocio ni habilita servicios externos.

## Microtareas del Bloque 2

1. **Infraestructura Flask y SQLite — completada.** Factory, configuraciones separadas, conexión y runner versionado.
2. **Identidad, roles, permisos y sedes — completada.** Migración 0001, seed controlado y pruebas.
3. **Actividades, entrenadores y programación de clases — implementada y validada.** Migración 0002, disponibilidad y clases con validaciones referenciales.
4. **Clientes, inscripciones, asistencias y control de cupos — implementada y validada.** Migración 0003 y servicio interno sin endpoints; la suite completa fue confirmada como satisfactoria por el usuario. Membresía y autorización siguen pendientes.
5. **Objetivos, rutinas y ejercicios — implementada y validada.** Migración 0004 y pruebas con bases temporales; la suite completa fue confirmada como satisfactoria por el usuario. La elegibilidad del objetivo por cliente y la autorización del entrenador quedan pendientes.
6. **Progreso físico y alimentación — implementada y validada.** Migración 0005 y pruebas temporales; la suite completa fue confirmada por el usuario. La pertenencia del objetivo de un plan al mismo cliente permanece pendiente; no se agregan endpoints ni autenticación.
7. **Membresías, beneficios, suscripciones, deudas y pagos — implementada y validada por el usuario.** Migración 0006, seed explícito de ARS, servicio interno para pagos ya realizados y pruebas temporales. No hay precios comerciales, elegibilidad de clases por beneficios, pasarela, autenticación ni endpoints.
8. **Mantenimiento y perfiles pendientes — implementación agregada; suite completa pendiente de VS Code.** Migración 0007 con perfiles de técnico y jefe de sede, máquinas, tickets e historial. La compatibilidad entre rol y perfil sigue pendiente.
9. **Remuneraciones — esquema implementado.** Migración 0008 con UNIQUE(clase_id), validación de liquidación e invariantes del entrenador histórico. El usuario confirmó satisfactoriamente la suite acumulada.

Las tablas principales del modelo propuesto están representadas en las migraciones 0001–0008; permanecen pendientes reglas de negocio, servicios, autenticación y APIs. M7, M8 y M9 quedan separadas para sus commits independientes.
