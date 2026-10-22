# Pólizas MG Colima

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

Eliges el auto del boletín de MG Financial Services y capturas **lo que trae el cliente** (pago inicial), el seguro
del primer año, el seguro anual del resto del plazo, el plazo y, si aplica, el precio. Arriba queda **lo que paga el
cliente** con la mejor opción: pago inicial, tasa, mensualidad y plazo.

El enganche se ajusta solo: **pago inicial − seguro del primer año − comisión por apertura (+ bono si va al
enganche)**. Las mensualidades usan el mismo método del cotizador de Autoexpress (validado contra cotizaciones reales):

- Tasa con IVA = tasa × 1.16 redondeada a 2 decimales; pagos fijos.
- Seguro de vida: 0.82% anual sobre el capital, dentro de la mensualidad.
- Comisión por apertura = % + IVA sobre el monto total a financiar (capital + seguros de los años 2 en adelante), dentro
  del pago inicial.
- Desde el mes 13 se suma el seguro de cada año financiado a 12 meses (los meses 13+ son aproximados al centavo).
- Enganche % sobre precio + GAP (si se incluye).

**GAP (pendiente):** la cotización puede llevar GAP o no, y cada rango de precio del vehículo tiene su monto. El
interruptor «Incluir GAP» queda desactivado hasta cargar la tabla en `oferta_mg.py` (`TABLA_GAP`, lista de
`(precio_hasta, monto_gap)`); en cuanto tenga montos se activa solo.

Pestañas: **Comparativo** (todas las ofertas con el mismo pago inicial y el seguro máximo de cada una), **Seguro**
(qué oferta conviene según el costo del seguro), **Por plazo** (mensualidades de 12 a 72 meses). Botón **PDF del
análisis**.

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

Si en Secrets están `[gcp_service_account]` y `SEGUIMIENTO_SHEET_URL` (o `POLIZAS_SHEET_URL`), cada vez que cargas
el Excel o das **Guardar y actualizar estatus**, la app reemplaza la pestaña **Polizas** de ese Google Sheet con una
fila por crédito: cliente, teléfono y su nota, seguimiento, fechas y el estatus calculado ese día (columna
`ACTUALIZADO`). Las demás pestañas no se tocan. Con los mismos secrets de `reportessaleu` se usa su mismo Sheet; desde
esa app se lee como cualquier otra pestaña (`libro.worksheet("Polizas")`).

## Guardar el Excel para no subirlo cada vez

Al cargar el Excel (o los PDF) y al dar **Guardar y actualizar estatus**, la app guarda el Excel y lo abre sola la próxima vez.

- **Sin configurar nada:** se guarda en el servidor de Streamlit. Se pierde si la app se reinicia o se duerme por inactividad (entonces vuelves a subirlo una vez).
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
