# Mercado Pago — Checkout Pro de prueba

## Estado verificado

FitPath implementa Checkout Pro exclusivamente en modo de prueba para un Cliente autenticado:

- `GET /api/v1/client/payments` consulta su membresía, deudas e historial;
- `POST /api/v1/client/payment-intents` crea o reutiliza un intento persistente para una deuda propia;
- `POST /api/v1/client/payment-intents/confirm` consulta el pago en Mercado Pago antes de conciliarlo;
- `POST /api/v1/payments/mercado-pago/webhook` valida la firma, consulta el pago y procesa reintentos de forma idempotente.

Los importes, moneda y conceptos salen de SQLite. El navegador solo envía el ID de la deuda y nunca decide el importe. Una aprobación actualiza pago, deuda y, cuando corresponde, la membresía dentro de una única transacción SQLite.

La integración rechaza pagos con `live_mode` distinto de `false`, exige declarar `MERCADOPAGO_CREDENTIAL_SCOPE=test` y usa únicamente `sandbox_init_point`. Las pruebas automatizadas usan dobles locales: no hubo comunicación real con Mercado Pago porque el entorno actual no tiene credenciales ni URL pública configuradas.

## Configuración local sin compartir secretos

En **Mercado Pago Developers > Tus integraciones**, abrir la aplicación existente, seleccionar el entorno **Prueba** y entrar en **Credenciales de prueba**. Copiar el Access Token únicamente al entorno local. Para Checkout Pro, tanto el token de prueba como el productivo pueden comenzar con `APP_USR`; por eso el prefijo no alcanza para distinguirlos y FitPath exige además el selector explícito `test`.

Configurar localmente, por ejemplo en el `.env` ignorado por Git:

```text
MERCADOPAGO_ACCESS_TOKEN=<Access Token del entorno Prueba>
MERCADOPAGO_CREDENTIAL_SCOPE=test
MERCADOPAGO_PUBLIC_BASE_URL=https://<host-publico-de-desarrollo>
MERCADOPAGO_WEBHOOK_SECRET=<firma secreta del Webhook de prueba>
```

Opcionales:

```text
MERCADOPAGO_TIMEOUT_SECONDS=10
MERCADOPAGO_WEBHOOK_TOLERANCE_SECONDS=300
```

No enviar el Access Token ni el secreto Webhook por chat, no exponerlos al frontend y no versionar `.env`. `MERCADOPAGO_PUBLIC_BASE_URL` debe ser HTTPS y accesible desde Internet; Mercado Pago no puede notificar a `localhost`. Se puede usar un dominio de desarrollo o un túnel HTTPS autorizado por el responsable del proyecto.

En la aplicación de Mercado Pago, configurar las notificaciones Webhooks de prueba con:

```text
https://<host-publico-de-desarrollo>/api/v1/payments/mercado-pago/webhook
```

Seleccionar el evento **Pagos** y copiar localmente la firma secreta mostrada por el panel. Cada preferencia también envía esa URL como `notification_url`.

Referencias oficiales: [crear una aplicación y obtener credenciales de prueba](https://www.mercadopago.com.ar/developers/es/docs/checkout-pro-preferences/create-application), [crear una preferencia](https://www.mercadopago.com.ar/developers/es/reference/online-payments/checkout-pro-preferences/create-preference/post), [configurar URLs de retorno](https://www.mercadopago.com.ar/developers/es/docs/checkout-pro-preferences/configure-back-urls) y [notificaciones de pagos](https://www.mercadopago.com.ar/developers/en/docs/checkout-pro-preferences/payment-notifications).

## Migración y datos de demostración

Aplicar primero las migraciones y semillas ordinarias:

```powershell
python -m backend.migrate --environment development
python -m backend.seed --environment development
```

La migración `0011_mercado_pago_intentos.sql` agrega estados de deuda, intentos persistentes y registro idempotente de Webhooks.

La carga demo es opcional y modifica la SQLite de desarrollo. No se ejecutó. Solo después de autorización explícita y reemplazando el ID por un usuario Cliente local válido:

```powershell
python -m backend.fitpath.payments_demo --user-id <ID_USUARIO> --confirm-development-data
```

El comando es idempotente para el mismo Cliente y día, crea una membresía demo vencida y una deuda en ARS, y falla si se omite la confirmación. Nunca debe apuntarse a una base productiva.

## Demostración real pendiente

1. Configurar las cuatro variables obligatorias sin publicarlas.
2. Exponer Flask mediante el host HTTPS de desarrollo y registrar el Webhook de prueba.
3. Aplicar la migración y, solo con autorización, crear la deuda demo.
4. Iniciar sesión como ese Cliente y abrir **Mi perfil > Membresía**.
5. Crear el checkout y pagar con una cuenta compradora y medios de prueba de Mercado Pago; no usar la cuenta vendedora ni datos reales.
6. Verificar los escenarios pendiente, aprobado y rechazado, y confirmar que el historial, la deuda y la membresía cambien según la respuesta consultada al proveedor.
7. Repetir una notificación desde el simulador Webhook y comprobar que no duplique el efecto.
8. Reiniciar Flask y confirmar que intentos, deuda e historial continúen en SQLite.

Hasta completar esta demostración contra la API de prueba, el módulo se considera implementado y verificado localmente, no validado en conectividad real.

## Pruebas locales

```powershell
python -m unittest -v tests.test_mercado_pago
python -m unittest discover -s tests -v
```

Las pruebas cubren sesión, permiso, CSRF, propiedad de deuda, monto backend, estados pendiente/aprobado/rechazado, rechazo de `live_mode`, firma inválida, Webhook repetido, transacción de deuda/membresía y falta de configuración. Son necesarias, pero no sustituyen la demostración real anterior.
