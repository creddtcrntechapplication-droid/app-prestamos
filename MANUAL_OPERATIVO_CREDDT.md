# CREDDT / CRNTECH — guía de operación

## Entrar y mantener el acceso

Ingresa con tu usuario habitual. Marca Recordar este dispositivo únicamente si el equipo es de confianza. El acceso dura siete días por defecto; cerrar sesión, cambiar la contraseña, desactivar el usuario o llegar al vencimiento exige entrar de nuevo. No compartas credenciales. En un dispositivo compartido, cierra sesión al terminar.

Si el teléfono bloquea la pantalla, vuelve a la misma pestaña. Si el navegador recarga la conexión, el sistema intenta restaurar el acceso y la pantalla indicada en la dirección. Una interrupción de Internet o la suspensión del servidor puede requerir esperar la reconexión. No repitas un pago hasta consultar su resultado.

## Módulos y roles

ADMIN administra usuarios, configuración y todas las operaciones. ASESOR registra y gestiona clientes, créditos y recaudos autorizados. CONSULTA accede a las consultas y simulaciones permitidas, sin registrar operaciones. Los controles se verifican también en el servidor.

Resumen separa el dinero efectivamente cobrado de las obligaciones futuras. Clientes registra y consulta personas. Nuevo crédito origina Normal, Express e Interés libre y muestra contratos pendientes. Detalle por crédito muestra cuotas, movimientos y auditoría. Cartera por cliente reúne las obligaciones de una persona. Pagos registra movimientos. Proyección estima cobros futuros. Simulador no crea una deuda. Usuarios es exclusivo del administrador. Mi cuenta permite cambiar la propia contraseña.

## Registrar un Normal

1. Registra o verifica el cliente en Clientes.
2. En Nuevo crédito selecciona Crédito normal y el cliente correcto.
3. Escribe capital, número de cuotas, frecuencia y fecha inicial.
4. Conserva la tasa predeterminada o activa Usar tasa personalizada. La tasa se expresa como porcentaje mensual de referencia de la fórmula, no como porcentaje por cada quince días.
5. Revisa capital, cuota, total y calendario antes de confirmar. Mensual significa intervalos de treinta días exactos; Quincenal, intervalos de quince días exactos.
6. Si el total no cubre el capital, corrige las condiciones. Ese calendario no se puede crear.
7. Confirma la revisión y registra el crédito. Consulta el estado real del contrato en Contratos pendientes. Crédito creado no significa correo entregado ni contrato aceptado.

Los créditos nuevos guardan la tasa y una distribución por cuota. Cambiar la tasa del siguiente crédito no cambia los anteriores. Las cuotas e intereses futuros no son ingreso recibido.

## Registrar un pago

1. Abre Pagos y selecciona el crédito activo.
2. Verifica cliente, saldo, próxima cuota y fecha del movimiento.
3. Para una cuota completa usa Registrar pago de cuota.
4. Para varias cuotas o un importe parcial, selecciona Por número de cuotas o Por valor pagado y completa el campo correspondiente.
5. Registra exactamente el dinero recibido y revisa la confirmación. Un pago parcial no significa que la cuota esté totalmente pagada.
6. Consulta el movimiento en Detalle por crédito. Si falla la comunicación, revisa primero el historial antes de intentar otro pago. El sistema rechaza reintentos de la misma operación y datos que cambiaron por otro operador.

El dinero recibido se divide entre capital e intereses. Para créditos nuevos versionados, fraccionar una cuota no vuelve a causar su interés. Los nuevos capitales y cobros de Normal y Express se registran en pesos enteros, sin centavos ocultos en una cuota recalculada. Un importe superior a todas las cuotas pendientes se rechaza: no se registra un excedente sin explicación.

El administrador puede omitir el comprobante por correo; la decisión queda registrada. Una solicitud de envío en segundo plano no garantiza recepción en la bandeja del cliente.

## Abonar capital y cerrar

En Pagos selecciona Abono a capital. El abono reduce el saldo y recalcula las cuotas pendientes conforme a la regla del producto. Si una cuota está parcialmente pagada, complétala antes del recálculo. Revisa el nuevo calendario, incluida la última cuota ajustada por redondeo. Un pago de cuota y un abono a capital son movimientos distintos.

Interés libre mantiene sus ciclos de treinta días y su capital pendiente. Para terminarlo utiliza la opción de finalizar que registra capital más interés pendiente. No marques como pagado un capital que no se recibió.

Los créditos históricos conservan sus condiciones. Si sus cifras no concilian, el administrador debe comparar contratos y comprobantes antes de cualquier corrección. No uses una reconstrucción del historial como sustituto de una conciliación con extractos.

## Usar celular, tablet y computador

En pantallas pequeñas abre el menú lateral con el botón superior y ciérralo para trabajar en el formulario. Las pestañas se desplazan horizontalmente; las tablas anchas también se desplazan dentro de su recuadro. Los valores en pesos se muestran sin decimales; las tasas conservan su precisión. Los cálculos guardados mantienen centavos cuando corresponde.

Actualizar datos conserva la pantalla y el estado de la conexión actual. Un formulario que aún no se ha enviado puede perderse si el navegador destruye la conexión; recordar el acceso no guarda automáticamente un borrador ni permite trabajar sin Internet.

## Ante un error

Si el saldo cambió, actualiza el crédito y comprueba sus movimientos. Si un pago quedó registrado pero el correo falló, no vuelvas a cobrarlo: revisa el comprobante. Si el calendario no cubre el principal, revisa sus condiciones. Si el acceso expiró, inicia sesión otra vez; si sigue fallando, solicita ayuda al administrador sin compartir la contraseña.


## Navegación compacta

Cinco áreas principales con iconos simples: Inicio, Clientes, Créditos, Cobros y Análisis. Créditos reúne Nuevo crédito, Detalle y Cartera; Análisis reúne Proyección y Simulador. El menú de perfil contiene Mi cuenta, administración de usuarios (solo ADMIN) y Cerrar sesión. Se conservan los permisos del servidor y la vista al actualizar. Las opciones secundarias aparecen únicamente dentro del área seleccionada.


## Mi cuenta y traducción del navegador

Mi cuenta separa Acceso y seguridad de Recordatorios. Los campos de contraseña conservan sus validaciones; el diagnóstico técnico no ocupa el formulario. Procesar avisos manualmente requiere abrir las herramientas y marcar la intención de envío. El estado del proveedor no acredita entrega.

La captura reportada muestra nombres traducidos y un error removeChild compatible con mutaciones externas de React (https://github.com/react/react/issues/11538). Se protege el HTML inicial con lang=es, translate=no y meta notranslate, sin interceptar ni ocultar errores de React. El comando de construcción de Render debe ser `pip install -r requirements.txt && python prepare_frontend.py`. Las pestañas ya traducidas requieren recarga completa; las extensiones pueden ignorar estas indicaciones. Pruebas de plantilla idempotente, navegación y validaciones de cuenta aprobadas; no se envían correos reales durante la revisión.
