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

## Archivos

```
streamlit_app.py      # la app (contraseña, carga, pestañas, descargas)
seguimiento.py        # estatus por fecha, proyección por mes, seguimiento en el Excel y PDF
polizas.py            # lee los PDF de pólizas y arma el Excel (también corre suelto en Colab)
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
