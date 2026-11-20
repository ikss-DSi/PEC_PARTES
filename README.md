# Igualdad de género y sostenibilidad (2000-2024)

Práctica en partes de **Visualización de datos**. 

Autor: **Iker Serrato**.

Este repositorio contiene la **parte 1**: la selección y preparación del conjunto de datos. Partí del *World Sustainability Dataset* de Kaggle (173 países, 2000-2018) y lo actualicé hasta 2024 con los World Development Indicators del Banco Mundial y con datos de Our World in Data. La pregunta que guía el trabajo es si la igualdad de las mujeres y la sostenibilidad avanzan juntas.

## Contenido

| Archivo | Qué es |
| --- | --- |
| `Practica_parte1_Iker_Serrato.pdf` | Documento de la parte 1: justificación, relevancia, complejidad, originalidad, preguntas y diccionario de variables |
| `construir_dataset.py` | Script que descarga los datos de la API del Banco Mundial y de Our World in Data, los une con el Kaggle y calcula los indicadores nuevos |
| `dataset_final.csv` | Conjunto final: 4.325 filas (173 países × 2000-2024) y 75 variables, una fila por país y año |
| `informe_cobertura.csv` | Para cada variable, el % de valores y el primer y último año con datos |
| `graficos_preparacion.ipynb` | Gráficos de la limpieza: completitud por año y filtro del 30 %, cobertura por variable, niveles de renta y valores extremos |
| `WorldSustainabilityDataset.csv`, `Data Dictionary.xlsx` | Conjunto original de Kaggle y su diccionario |

## Cómo reproducirlo

```bash
pip install wbgapi pandas openpyxl requests matplotlib
python construir_dataset.py WorldSustainabilityDataset.csv
```

El script tarda unos minutos, porque hace una consulta a la API por indicador. Genera `dataset_final.csv` e `informe_cobertura.csv`. Después se puede abrir `graficos_preparacion.ipynb` para ver la revisión de los datos.

## Fuentes

- truecue. *World Sustainability Dataset* (CC0). Kaggle. https://www.kaggle.com/datasets/truecue/worldsustainabilitydataset
- Banco Mundial. *World Development Indicators*. https://databank.worldbank.org/source/world-development-indicators
- Our World in Data. Emisiones de CO₂ (https://github.com/owid/co2-data) y tipo de régimen político (https://ourworldindata.org/grapher/political-regime)

## Licencia

- **Código** (`construir_dataset.py`, notebook): MIT, ver [LICENSE](LICENSE).
- **Datos y documentación** (CSV, PDF): CC BY 4.0, https://creativecommons.org/licenses/by/4.0/deed.es. Si los reutilizas, cita: Iker Serrato (2026). *PEC_PARTES*. https://github.com/ikss-DSi/PEC_PARTES
- Los datos del Banco Mundial y de Our World in Data tienen licencia CC BY 4.0. El conjunto original de Kaggle tiene licencia CC0 (dominio público).
