# SPIRO_CALC | Validación antes de uso en consulta

**Estado: borrador para verificación. No usar para emitir informes clínicos hasta completar la validación.**

## Uso previsto

Transcribir y presentar la espirometría de un equipo identificado, con interpretación
orientativa y conclusión revisada por el médico. No adquiere señales, no calcula
referencias poblacionales ni verifica por sí mismo curvas, técnica, diagnóstico o tratamiento.
No incluye firma electrónica ni sustituye el informe validado del equipo.
Esta versión de prueba marca el PDF como no apto para atención clínica. No
escribe en Google Sheets y no llama a un proveedor de IA. No elimina registros
previos ni cambia la versión desplegada. El PDF se descarga al dispositivo y, si
la app se aloja en un servidor, los datos del formulario se procesan en ese servidor.

## Verificación del entorno real

1. Identificar equipo, modelo, versión de software, modo de estudio, ecuación y
   versión de referencia. Confirmar población/edades cubiertas, unidades y
   reglas de redondeo. Guardar la versión exacta de SPIRO_CALC usada en la prueba.
2. Con el equipo configurado para consulta, preparar estudios de prueba **sin
   datos identificables**. Comparar valores pre/post, predichos, LLN, Z, unidades,
   calidad, fecha/edad y el PDF con el informe fuente. Si el equipo usa otro
   criterio de respuesta al broncodilatador, documentar por separado el resultado
   esperado con cada criterio; no exigir que ambos coincidan.
3. Evaluar como mínimo: basal normal, relación bajo LLN, FVC baja sin TLC,
   calidad insuficiente, referencia desconocida, valor exactamente en el LLN y
   valores a cada lado, fecha incompatible, simple con datos post arrastrados,
   pre/post con calidad no confirmada y umbrales de respuesta en pediatría.
4. Verificar la revisión previa al PDF, cambio de paciente/estudio, corrección y
   reexportación; nunca reutilizar una conclusión anterior. Examinar el PDF
   descargado y sus anexos. Probar iPhone y el navegador de consulta.
5. Revisar dónde se procesan y conservan los datos en el despliegue de consulta:
   acceso restringido, almacenamiento/exportación, registros, retención, eliminación
   y recuperación. Probar con expedientes ficticios. No habilitar almacenamiento
   remoto ni un proveedor de IA con datos clínicos sin revisar el flujo y el acceso.
6. Dejar por escrito los resultados esperados y observados, las discrepancias y
   la aceptación clínica. Bloquear el despliegue si una discrepancia puede
   cambiar una conclusión o si no están verificados los controles de privacidad.

Mientras se completa lo anterior, usar el informe del equipo. Para informes
anteriores, priorizar los que pudieron cambiar conducta y estaban cerca de LLN
o de umbrales de respuesta, o tenían edad/fecha discordante. Revisarlos de forma
local; las pruebas de software no demuestran que un paciente concreto haya sido afectado.

## Referencias clínicas

- [ATS/ERS 2019: estandarización de espirometría](https://pmc.ncbi.nlm.nih.gov/articles/PMC6794117/).
- [ERS/ATS 2022: estrategias de interpretación](https://publications.ersnet.org/content/erj/60/1/2101499).
- [GINA 2026: guía resumida](https://ginasthma.org/wp-content/uploads/2026/07/GINA-Summary-Guide-2026-WEB-WMS.pdf#page=8).

## Ejemplos publicados para pruebas de software

- **GLI 2012, suplemento §4.3.4:** FEV1 medido 2.210 L; predicho 2.7800 L; LLN 2.1741 L; Z −1.55. El FEV1 está por encima de su LLN, aunque equivale a 79.5% del predicho. Este ejemplo solo verifica ese parámetro; no clasifica un estudio completo ni selecciona la ecuación del espirómetro de consulta. [Suplemento GLI 2012](https://publications.ersnet.org/content/erj/suppl/2013/04/19/09031936.00080312.DC1/Supplement_GLI_2012_predicted_values-2.pdf).
- **ERS/ATS, recuadro 1:** con FEV1 pre 2.00 L, post 2.40 L y predicho 3.32 L, el cálculo a partir de los números publicados es +12.04819…% del predicho (+12.05% a dos decimales). El recuadro imprime 12.1%; ambos resultados superan 10%. Se prueba la fórmula con los datos mostrados y la clasificación usa el valor sin redondear. [Estándar ERS/ATS 2022](https://doi.org/10.1183/13993003.01499-2021).

Estas pruebas verifican cálculos y transferencia de valores del software. No reemplazan el cotejo con el equipo ni la validación del uso asistencial.

## Trazabilidad de pruebas

| Riesgo | Control | Verificación |
| --- | --- | --- |
| Se reemplaza el LLN y cambia el patrón | Conservar LLN/Z ingresados; no extrapolar valores faltantes | `test_clinical_references.py` |
| Fecha, fase del estudio o referencias inconsistentes | Bloqueo por fecha imposible; filtrado por fase y verificación de procedencia | `test_study_guard.py`, `test_review_flow.py` |
| Se firma o distribuye una conclusión sin revisar | PDF de prueba con advertencia tras confirmación, con texto clínico separado | `test_report_review.py`, `test_review_flow.py` |
| Se reutiliza el informe de otro estudio | Nueva preparación invalida la descarga y reinicia la revisión | `test_review_flow.py` |
| Se omite un anexo erróneo sin informar | Detener la exportación si falla la incorporación del anexo | `test_report_review.py` |

Ejecutar desde la raíz con las dependencias de `requirements.txt`:

```sh
python -m unittest discover -s tests -v
```
