# Revisión CREDDT / CRNTECH — 3 de noviembre de 2026

## Diagnóstico y alcance

Fuente revisada: repositorio app-prestamos, commit 8cc1ccf06bf74a5cf5ebd25cf3fa7afa3d1eecbf. Coincide con el archivo entregado por el propietario. Es una aplicación Streamlit con SQLAlchemy y PostgreSQL, modalidades Normal, Express e Interés libre, y roles ADMIN, ASESOR y CONSULTA.

Problemas demostrados del original: la autenticación sólo vivía en la conexión de Streamlit; el mismo interés de una cuota podía imputarse de nuevo al dividir su pago; el capital acumulado registrado podía superar el prestado; Normal quincenal podía programar menos dinero que el principal; el contrato de un Normal nuevo no recibía en todos los casos la tasa guardada; las conexiones se construían en cada ejecución; varias escrituras dependían de permisos de pantalla; la baja de usuarios eliminaba identidad operativa; había exceso de jerarquías y valores sin contexto financiero.

Los ensayos originales aislados de un Normal de COP 1.000.000 muestran interés de COP 42.700 en un pago de COP 126.000, frente a COP 85.088,29 al pagarlo en COP 50.000 y COP 76.000. El calendario completo podía clasificar COP 1.264.720,80 como capital. Son defectos contables, no mayores ingresos reales.

## Cambios financieros

La autorización posterior del propietario permite corregir imputaciones, conservando registros históricos y las condiciones de los contratos anteriores. Los créditos nuevos Normal y Express guardan una distribución por cuota versionada en un esquema privado. No se aplica una migración retroactiva de saldos.

Se conserva la fórmula de cuota vigente y sus redondeos. Para contratos nuevos, el capital se distribuye entre las cuotas; el interés contractual total es la diferencia entre la suma pactada de cuotas y el capital. Los centavos se distribuyen sin cambiar el dinero total pactado. Cada cuota guarda por separado su capital e interés pendientes: pagarla por partes sólo consume esos saldos, no vuelve a causar interés.

Ejemplo nuevo: capital COP 1.000.000, 12 cuotas de COP 126.000, total COP 1.512.000. Capital total devuelto: COP 1.000.000. Interés total: COP 512.000. La primera cuota contiene COP 83.333,33 de capital y COP 42.666,67 de interés. La tasa de referencia de la fórmula es 4,27 % mensual; la diferencia se debe al redondeo de la cuota vigente. La clasificación no convierte el interés proyectado en ingreso cobrado.

Los calendarios nuevos que no cubren el principal se rechazan antes de guardar el préstamo. Esto afecta a las condiciones quincenales heredadas inconsistentes; no se duplica automáticamente el número de cuotas ni se inventa una condonación. La simulación muestra la advertencia. Un calendario quincenal viable con tasa personalizada también está cubierto por pruebas.

El abono a capital conserva el recálculo amortizado ya existente sobre las cuotas futuras. La nueva distribución usa Decimal y ajusta la última cuota al centavo para devolver exactamente el saldo. Si hay una cuota parcialmente pagada, se exige completarla antes del recálculo para no borrar obligaciones pendientes. No se recalcula Interés libre con este mecanismo.

Los históricos conservan su modelo. Sus inconsistencias previas requieren una conciliación específica con soportes antes de corregirlos; este cambio no acredita que esos datos antiguos sean correctos. La herramienta administrativa de reconstrucción omite los créditos versionados para no alterar su distribución.

## Interfaz y navegación

Sistema común de colores azul, tinta oscura y superficies claras; encabezado con módulo y responsable; formularios y acciones con foco visible; columnas adaptables; tablas con desplazamiento interno; pestañas horizontales; tamaños táctiles mínimos. Pesos sin decimales en indicadores y entradas monetarias; tasas con decimales y símbolo de porcentaje. La precisión contable interna se mantiene.

El resumen distingue recaudo real de hoy y del mes, cuotas vencidas y próximas, capital pendiente e intereses cobrados. Las proyecciones se etiquetan como obligaciones futuras, no como dinero recibido. El botón Actualizar datos invalida cachés conservando el estado de la conexión actual.

## Autenticación, permisos y persistencia

Recordar dispositivo es opcional y dura SESSION_DAYS (7 días por defecto, rango 1–30). El navegador guarda un identificador aleatorio, nunca la contraseña. PostgreSQL guarda su hash y valida expiración, usuario activo, rol y versión de credencial. Cerrar sesión revoca el identificador; cambiar la contraseña o desactivar la cuenta invalida el acceso. Existe limitación de intentos de inicio de sesión.

Cookie SameSite=Strict y Secure en HTTPS. El componente nativo disponible requiere JavaScript para crear la cookie y no permite HttpOnly: es una limitación real de esta arquitectura. No se colocan tokens en URLs. Nuevas tablas privadas con RLS habilitado y sin acceso PUBLIC, anon ni authenticated; la aplicación usa su conexión de servidor.

Las escrituras de clientes, créditos, pagos y usuarios verifican el rol activo en el backend. La baja de usuarios es lógica y reversible. No se crean cuentas de prueba en producción.

La pantalla actual se recupera mediante vista en la URL. Los filtros y selecciones permanecen durante actualizaciones de la sesión Streamlit; no se promete recuperar un formulario no enviado si el navegador destruye su conexión. Recordar el acceso no evita la suspensión de Render Free ni convierte la aplicación en una aplicación sin conexión.

## Integridad y rendimiento

El pago y su distribución se ejecutan en una transacción bajo bloqueo del préstamo. Se conserva idempotencia y comprobación del estado esperado. Una falla revierte pago, cuotas, distribución y clave de operación. Se verifica la igualdad entre saldos del calendario y capital restante antes y después del pago.

SQLAlchemy usa un motor compartido con pool limitado, pre-ping, reciclaje y tiempos de espera. Cachés cortas de lectura se invalidan al escribir. No hay un caché independiente de saldos para autorizar pagos: se consultan bajo bloqueo.

## Pruebas y limitaciones

Se añadieron dos pruebas de navegación con una misma sesión: cambios sucesivos de módulo, actualización que conserva la sección y acceso rápido desde Resumen. La corrección asigna una identidad estable al menú; evita recrearlo por su índice predeterminado. No depende de volver a pulsar la opción.

Mediciones del laboratorio local (medianas, no tiempos prometidos de Render): simulación Decimal 0,01 ms; consulta real de cartera 23,06 ms; indicadores operativos 27,67 ms; verificación PBKDF2 203,06 ms; registro de pago sin correo 15,65 ms. No incluyen latencia de Internet, despertar de Render Free, envío real de correo ni representación del navegador.

Pruebas aisladas con PostgreSQL local real, nunca con datos ni credenciales de producción. Suite de cálculo e integración: 36 comprobaciones, incluidas distribución completa, fraccionamiento, abono, exceso, rollback, concurrencia, roles, expiración y revocación. Comprobación automática de 26 combinaciones de página y rol. La matriz visual y evidencias se entregan por separado.

No se ha acreditado entrega real de correos: las pruebas desactivan proveedores y recordatorios automáticos. Una tarea en segundo plano iniciada no equivale a entrega al destinatario. No se han firmado contratos reales ni originado créditos reales durante la revisión.

El árbol del repositorio público contiene un archivo prestamos_vfinal.db. No se descargó ni se inspeccionó: no puede afirmarse qué contiene. Antes de mantenerlo público, el propietario debe verificar si contiene datos privados y gestionar su retiro del historial si corresponde. No se elimina como parte de esta migración.

## Archivos de ejecución

web_app.py integra los controles. creddt_finance.py concentra cálculo Decimal. creddt_ledger.py conserva la distribución versionada. creddt_sessions.py valida sesiones y límites de acceso. creddt_cookie.py conecta la cookie propia. creddt_ui.py y creddt_theme.css centralizan presentación; .streamlit/config.toml define el tema. No se requieren dependencias adicionales a las del proyecto.

## Despliegue y reversión

Publicar únicamente archivos de ejecución y documentación revisados. Excluir bases de laboratorio, binarios PostgreSQL, credenciales ficticias, wrappers de preautenticación y scripts de preparación local. Las adiciones de esquema son idempotentes: activo en usuarios y tablas privadas de sesiones, intentos y distribución; no hay UPDATE masivo de pagos ni eliminación de tablas.

Antes de publicar se debe conservar la revisión anterior y el respaldo habitual de la base. Si se revierte el código, las tablas nuevas se conservan; no borrar distribuciones ni sesiones para simular una reversión. Si ya se originaron créditos con distribución nueva, no regresar al motor financiero anterior: eso perdería la política de imputación. Preferir corregir hacia adelante o desactivar temporalmente la originación mientras se revisa el problema.
