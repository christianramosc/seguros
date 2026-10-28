# Pólizas MG Colima

> La página **Pólizas** está desactivada por ahora: la app abre directo en **Mejor oferta MG**. Para volver a
> mostrarla, descomenta su línea en `streamlit_app.py`.

App de Streamlit para dar seguimiento a las pólizas de seguro de los créditos de MG Colima (Autoexpress Inbursa) y
saber **a qué clientes contactar** para venderles póliza externa, recordarles el pago de contado o aprovechar el fin
de su crédito.

## Cómo funciona

Cada crédito trae **2 pólizas**: la 1, de contado al comprar el auto (normalmente 1 año), y la 2, del resto del plazo.
Con ellas se calcula el plazo y **todas las oportunidades**:

| Días antes del aniversario | Estatus | Qué hacer |
|---|---|---|
| Más de 52 | PRÓXIMO | Esperar |
| 52 a 45 | LLAMAR YA · PÓLIZA EXTERNA | Cerrar la externa antes del día 45 (límite ideal) |
| 44 a 39 | ÚLTIMA OPORTUNIDAD · EXTERNA | Llamar hoy: cada día es menos probable que la acepten |
| 38 a 31 | EXTERNA CERRADA · ESPERAR CONTADO | Oportunidad 0 de externa; recordarle que pague de contado |
| 30 a 1 | VENTANA DE CONTADO ABIERTA | Que pague de contado antes del día anterior |
| Último año | PRÓXIMO / LLAMAR YA · TERMINA SU CRÉDITO | Ofrecerle seguro: el auto será suyo |
| Después del fin | CRÉDITO TERMINADO · CLIENTE LIBRE | Ofrecer seguro sin restricciones del contrato |

Los días (45 / 38 / 30 / 7) se ajustan en la app.

## Uso

1. **Cargar**: sube los PDF o ZIP de las pólizas (Crédito Click, columna *Impresión*) y/o el Excel
   `Polizas_extraidas.xlsx`. Con ambos, los PDFs nuevos se juntan con los clientes que ya tenías y se conserva el
   seguimiento.
2. **Hoy**: a quién llamar ya, ordenado por lo que vence primero.
3. **Por mes**: oportunidades de los próximos 12 meses y la prima en juego.
4. **Todos**: lista completa con filtros.
5. **Seguimiento**: captura Contactado, Fecha, Resultado y Notas.
6. **Descargas**: *Excel con seguimiento* (hojas *Contacto* y *Base de datos*) y *PDF para contactar*.

La app **no guarda datos de clientes**: descarga el Excel al terminar y súbelo la próxima vez.

### Teléfonos y NOTA TELÉFONO

Muchas pólizas no traen teléfono; se completan a mano en el Excel (por ejemplo, buscando el VIN en BlueService).
La columna **NOTA TELÉFONO** (hojas *Contacto* y *Base de datos*, celda amarilla editable) guarda lo que hay que
revisar de ese número: *sin órdenes de servicio en BlueService*, *número incompleto*, *el VIN está a nombre de otra
persona*… La nota aparece en la app y en el PDF (en naranja, debajo del teléfono).

Si vuelves a subir PDFs junto con el Excel, el teléfono y la nota que ya tenías se conservan cuando el PDF no trae
teléfono. Un Excel anterior sin la columna se actualiza solo al subirlo.

Aseguradoras reconocidas: GNP, Quálitas, Chubb, HDI y Seguros Inbursa.

## Mejor oferta MG (pestaña de arriba)

Eliges el auto del boletín de MG Financial Services y capturas el **desembolso del cliente** (lo que pone de su
bolsa) **o el pago inicial** de la cotización —el otro se calcula y queda bloqueado—, el seguro del primer año, el
seguro anual del resto del plazo, el plazo y, si aplica, el precio. Arriba queda la mejor opción: pago inicial,
desembolso, tasa, mensualidad y plazo, y abajo **hasta cuánto puede valer la póliza** (seguro año 1) en cada plan para
que cumpla sus condiciones. Ej.: MG5 2027 1.5L COM EXCITE MT con pago inicial de $120,000 → desembolso $60,000 (bono
de $60,000 al enganche) y, en el plan 17.74%, la póliza puede valer hasta $16,800 (enganche 30% = $103,200).
Con pago inicial capturado, los planes con bono al enganche descuentan el bono del desembolso (como en la cotización); en Tasa
Baja el bono va a la tasa y el desembolso es todo el pago inicial.

- **Pago inicial** (igual que la cotización) = enganche + comisión por contratación del crédito + seguro contado año
  1 + GAP contado. El enganche incluye el bono cuando va al enganche.
- **Desembolso del cliente** = pago inicial − bono al enganche. El enganche se ajusta solo: desembolso − seguro del
  primer año − GAP contado − comisión (+ bono si va al enganche). Las mensualidades usan el mismo método del cotizador de Autoexpress (validado contra cotizaciones reales):

- Tasa con IVA = tasa × 1.16 redondeada a 2 decimales; pagos fijos.
- Seguro de vida: 0.82% anual sobre el capital, dentro de la mensualidad.
- Comisión por apertura = % + IVA sobre el monto total a financiar (capital + seguros de los años 2 en adelante), dentro
  del pago inicial.
- Desde el mes 13 se suma el seguro de cada año financiado a 12 meses (los meses 13+ son aproximados al centavo).
- Enganche % sobre precio + GAP (si se incluye).

**GAP:** la cotización puede llevarlo o no. En la app eliges **No / Contado / Financiado** y capturas el monto de
la cotización (depende del auto). Contado va en el pago inicial; financiado se suma al precio, entra al enganche % y
al crédito. `TABLA_GAP` en `oferta_mg.py` queda como respaldo si algún día se tiene la tabla por rango de precio.

**Enganche mínimo real del cliente** (lo que pone de su bolsa): con bono al enganche = enganche sistema según el
color de la tabla de bonos − % del bono, exacto (la columna del boletín lo redondea: 9.96% aparece como 10%; el
cotizador acepta el mínimo exacto); en Tasa Baja el
bono va a la tasa y el cliente pone todo el enganche.

**Diseño:** tema oscuro estilo shadcn/ui (paleta zinc, fuente Inter) en `.streamlit/config.toml`; las piezas
propias (encabezado, tarjetas, insignias, títulos de sección) están en `ui.py`. Orden de la página: datos de la
operación → **Mejor opción** (tarjetas) → **Planes del boletín** (una tabla con todos los planes al plazo elegido:
mensualidad, tasa, pago inicial, desembolso, enganche, total, **hasta cuánto puede valer la póliza** y, si no aplica,
por qué) → **Detalle** (pestañas Por plazo · Mínimos por plan · Oferta del auto) → **Descargas** (PDF del análisis con
el nombre del cliente y PDF de mínimos de toda la oferta).

**Desactivados por ahora** (`pag_oferta.py`): `MOSTRAR_GAP = False` hasta tener los precios de GAP actualizados y
`MOSTRAR_SEGURO_2 = False` (el seguro de los años 2+ no se muestra ni entra a la mensualidad). Cámbialos a `True` para
volver a mostrarlos.

**PDF de mínimos de toda la oferta**: todos los autos y planes del boletín con el enganche mínimo del sistema y real
del cliente, comisión, desembolso y pago inicial mínimos (+ seguro de contado) y la mensualidad con el enganche mínimo
en cada plazo, de 12 meses al plazo máximo de cada plan (un bloque por auto, la menor de cada plazo en verde).

**Seguro:** el del año 1 puede ir de **contado** (en el pago inicial) o **financiado** («Autoexpress Multianual
Fraccionado»: el importe anual se financia también el año 1, se amortiza en los meses 1-12, paga comisión y la
cotización muestra el importe primer año en $0); el de los años 2+ puede ir **financiado** (fraccionado desde el mes
13) o de **contado** (el cliente lo paga cada aniversario). Validado con 18 cotizaciones reales (12, 24, 36, 48, 60 y 72 meses; contado y multianual; planes 413, 414, 415,
420, 448, 463 y 470): monto a financiar, comisión, pago inicial y mensualidad al centavo (31 de 33 mensualidades
exactas, las otras 2 a $0.01).

**Bono:** en Tasa Baja va a la tasa. En los planes Estándar 13.74%, 17.74% y Especial 12.09% puede ir **al enganche**
o **al precio**, y cada forma aparece como una opción separada en el comparativo (al precio, el auto queda en precio −
bono y el enganche mínimo se calcula sobre ese precio).

**Cada mes** actualiza en `oferta_mg.py`: `BOLETIN`, `OFERTA_MES`, `VIGENCIA`, `CATALOGO` (precios, bonos, enganche
sistema y tasas bajas), `CURVAS` y, cuando la tengas, `TABLA_GAP`.

## Archivos

```
streamlit_app.py      # entrada: contraseña y pestañas de arriba (Pólizas · Mejor oferta MG)
pag_polizas.py        # página Pólizas (carga, pestañas, descargas)
pag_oferta.py         # página Mejor oferta MG
oferta_mg.py          # catálogo del boletín, cálculo de ofertas y PDF del análisis
ui.py                 # estilos y tarjetas compartidas
seguimiento.py        # estatus por fecha, proyección por mes, seguimiento en el Excel y PDF
polizas.py            # lee los PDF de pólizas y arma el Excel (también corre suelto en Colab)
cotizaciones.py       # lee las cotizaciones de póliza externa y calcula la más barata
hoja_google.py        # copia las pólizas a la pestaña «Polizas» del Google Sheet
almacen.py            # guarda el último Excel (servidor o Google Drive)
packages.txt          # poppler-utils (pdftotext) para Streamlit Cloud
```

## Publicar en Streamlit Community Cloud

1. En [share.streamlit.io](https://share.streamlit.io) → **Create app** → repo `christianramosc/seguros`, rama `main`,
   archivo `streamlit_app.py`.
2. **Advanced settings → Secrets**: `APP_PASSWORD = "tu-clave"` (ver `.streamlit/secrets.toml.example`).
3. **Deploy**. Comparte la app solo con quien deba verla (los archivos traen datos de clientes).

## Correr en local

```bash
pip install -r requirements.txt   # y poppler (pdftotext) instalado en el sistema
streamlit run streamlit_app.py
```

## Colab

`polizas.py` también funciona solo: pégalo en Colab, ejecuta la celda, sube los PDF/ZIP (y el Excel anterior si lo
tienes) con el botón y se descarga el Excel.

### Comparativa con pólizas externas

En **Cotizaciones (opcional)** sube el Excel del Multicotizador (hoja *Comparativo*, una fila por cliente con su
SERIE y una columna por aseguradora terminada en *(VC)* / *(VF)*). La app lo guarda dentro del Excel de pólizas
(hoja *Cotizaciones*, se conserva aunque vuelvas a subir PDFs), muestra la externa más barata y el ahorro contra la
prima anual actual, y el **PDF para contactar** agrega la columna *Póliza externa* y una sección *Comparativa con
pólizas externas* ordenada del mayor ahorro al menor. Puedes subirlo solo, sobre el Excel que ya está abierto.
Las primas fuera de rango (menos del 60 % o más del doble de la mediana del cliente, casi siempre HDI) no cuentan
para la más barata: en el PDF salen tachadas como *omitida*.

## Copia en Google Sheets (para consultar y usar en otras apps)

Si en Secrets están `[gcp_service_account]` y `SEGUIMIENTO_SHEET_URL` (o `POLIZAS_SHEET_URL`), cada vez que abres
la app (con el último Excel guardado), cargas el Excel o das **Guardar y actualizar estatus**, la app reemplaza la pestaña **Polizas** de ese Google Sheet con una
fila por crédito: cliente, teléfono y su nota, seguimiento, fechas y el estatus calculado ese día (columna
`ACTUALIZADO`). Las demás pestañas no se tocan. Con los mismos secrets de `reportessaleu` se usa su mismo Sheet; desde
esa app se lee como cualquier otra pestaña (`libro.worksheet("Polizas")`). Arriba de la página Pólizas se ve «Conectado a <Sheet> · abrir»
(igual que en `reportessaleu`) o el motivo por el que no se puede copiar.

## Guardar el Excel para no subirlo cada vez

Al cargar el Excel (o los PDF) y al dar **Guardar y actualizar estatus**, la app guarda el Excel y lo abre sola la próxima vez.

- **Sin configurar nada:** se guarda en el servidor de Streamlit. Se pierde si la app se reinicia o se duerme por inactividad (entonces vuelves a subirlo una vez).
- **Permanente (Google Sheet):** si ya configuraste la copia en Google Sheets (abajo), el Excel completo también se
  guarda en una pestaña oculta `_Polizas_excel` de ese Sheet y la app lo abre sola aunque se reinicie. No hay que hacer
  nada más.
- **Permanente (Google Drive):**
  1. En Google Cloud Console crea un proyecto, activa **Google Drive API** y crea una **cuenta de servicio** con una clave JSON.
  2. Sube a tu Drive el `Polizas_extraidas.xlsx` y compártelo como **Editor** con el `client_email` de la cuenta de servicio.
  3. Copia el ID del archivo (lo que va entre `/d/` y `/view` en el enlace).
  4. En Streamlit → Settings → Secrets agrega:

```toml
POLIZAS_DRIVE_FILE_ID = "id-del-archivo"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```
