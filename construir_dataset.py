"""
Construye el conjunto de datos final de la práctica: World Sustainability Dataset (Kaggle, 2000-2018)
actualizado hasta el último año disponible y enriquecido con variables de género.

Uso (en tu ordenador, con internet):
    pip install wbgapi pandas openpyxl requests
    python construir_dataset.py WorldSustainabilityDataset.csv

Salidas (en la misma carpeta):
    dataset_final.csv        -> una fila por país y año (tidy data), todas las variables
    informe_cobertura.csv    -> por variable: % de valores, primer y último año con datos
"""
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import requests
import wbgapi as wb

KAGGLE = sys.argv[1] if len(sys.argv) > 1 else "WorldSustainabilityDataset.csv"
AÑOS = range(2000, 2025)

kg = pd.read_csv(KAGGLE)
kg = kg.rename(columns={"Country Code": "iso3", "Country Name": "pais", "Year": "anio"})

# 1. Códigos del Banco Mundial que ya están en los nombres de columna (los que llevan puntos)
cod_wb = {}
for c in kg.columns:
    m = re.search(r" - ([A-Z]{2}\.[A-Z0-9.]+)$", c)
    if m:
        cod_wb[m.group(1)] = c
# Doing Business se interrumpió en 2021: estas dos se conservan solo con su histórico
SIN_ACTUALIZAR = {"IC.REG.COST.PC.FE.ZS", "IC.REG.COST.PC.MA.ZS"}

# 2. Indicadores nuevos (enriquecimiento) y equivalentes WDI de las columnas ODS
NUEVOS = {
    "SL.TLF.CACT.FE.ZS": "participacion_laboral_mujeres_pct",
    "SL.TLF.CACT.MA.ZS": "participacion_laboral_hombres_pct",
    "SP.DYN.LE00.FE.IN": "esperanza_vida_mujeres",
    "SP.DYN.LE00.MA.IN": "esperanza_vida_hombres",
    "SH.STA.MMRT": "mortalidad_materna_100k",
    "SL.UEM.TOTL.FE.ZS": "paro_mujeres_pct",      # estimación OIT, más cobertura que la ODS
    "SL.UEM.TOTL.MA.ZS": "paro_hombres_pct",
    "SH.H2O.BASW.ZS": "agua_potable_basica_pct",
    "SN.ITK.DEFC.ZS": "subalimentacion_pct",
    "SI.POV.DDAY": "pobreza_extrema_pct",
    "NY.GDP.PCAP.KD": "pib_pc_constante",      # PIB per cápita en US$ constantes de 2015 (para el desacoplamiento)
}

validos = {e["id"] for e in wb.economy.list()}
isos = sorted(set(kg["iso3"]) & validos)
print(f"Países del Kaggle reconocidos por el Banco Mundial: {len(isos)} de {kg['iso3'].nunique()}")

def descarga(codigo, intentos=3):
    """Una sola petición por indicador (todos los países y años) y filtro local.
    La API del Banco Mundial a veces se cuelga; con timeout y reintentos el script no se queda parado."""
    url = f"https://api.worldbank.org/v2/country/all/indicator/{codigo}"
    params = {"format": "json", "source": 2, "date": f"{AÑOS.start}:{AÑOS.stop - 1}", "per_page": 20000}
    for i in range(1, intentos + 1):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            js = r.json()
            if len(js) < 2 or not js[1]:
                print(f"  ! {codigo}: sin datos ({js[0].get('message', js[0]) if js else 'respuesta vacía'})")
                return None
            filas = [(f["countryiso3code"], int(f["date"]), f["value"]) for f in js[1]
                     if f["countryiso3code"] in isos and f["value"] is not None]
            s = pd.DataFrame(filas, columns=["iso3", "anio", codigo]).set_index(["iso3", "anio"])[codigo]
            return s
        except Exception as e:
            print(f"  ! {codigo}: intento {i}/{intentos} fallido ({type(e).__name__})")
            time.sleep(5)
    return None

# La API tarda entre 1 y 90 s por petición: se descargan 6 indicadores a la vez
codigos = [c for c in cod_wb if c not in SIN_ACTUALIZAR] + list(NUEVOS)
series = []
inicio = time.time()
with ThreadPoolExecutor(max_workers=6) as ex:
    futuros = {ex.submit(descarga, c): c for c in codigos}
    for n, fut in enumerate(as_completed(futuros), 1):
        s = fut.result()
        estado = "sin datos" if s is None else f"{len(s)} valores"
        print(f"[{n}/{len(codigos)}] {futuros[fut]}: {estado}  ({time.time() - inicio:.0f} s)")
        if s is not None:
            series.append(s)
wdi = pd.concat(series, axis=1)
wdi.index.names = ["iso3", "anio"]
wdi = wdi.reset_index()

# Nombres de columna: los originales del Kaggle para las variables existentes, nombres cortos para las nuevas
wdi = wdi.rename(columns={**cod_wb, **NUEVOS})

# 3. Base: todas las combinaciones país x año
base = pd.MultiIndex.from_product([isos, list(AÑOS)], names=["iso3", "anio"]).to_frame(index=False)
df = base.merge(wdi, on=["iso3", "anio"], how="left")

# Valores del Kaggle que el WDI no tenga (y las dos de Doing Business)
df = df.set_index(["iso3", "anio"])
kgi = kg.set_index(["iso3", "anio"])
for col in kgi.columns:
    if col in df.columns:
        df[col] = df[col].combine_first(kgi[col])
    elif col not in ("pais",):
        df[col] = kgi[col].reindex(df.index)
df = df.reset_index()

# 4. Dimensiones estáticas por país (nombre, continente, región ODS) desde el Kaggle
estaticas = ["pais", "Continent", "World Regions (UN SDG Definition)"]
df = df.drop(columns=[c for c in estaticas if c in df.columns]).merge(
    kg.groupby("iso3")[estaticas].last().reset_index(), on="iso3", how="left")

# Nivel de renta: el histórico del Kaggle y, después de 2018, la clasificación vigente del Banco Mundial
renta = "Income Classification (World Bank Definition)"
actual = {e["id"]: e["incomeLevel"] for e in wb.economy.list()}
nombres = {r["id"]: r["value"] for r in wb.income.list()}
df[renta] = df.groupby("iso3")[renta].ffill()
mask = df["anio"] > 2018
df.loc[mask, renta] = df.loc[mask, "iso3"].map(actual).map(nombres)

# 5. CO2 y régimen político desde Our World in Data
co2 = pd.read_csv("https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv",
                  usecols=["iso_code", "year", "co2", "co2_per_capita"])
co2 = co2.rename(columns={"iso_code": "iso3", "year": "anio", "co2": "co2_mt", "co2_per_capita": "co2_pc_owid"})
df = df.merge(co2, on=["iso3", "anio"], how="left")
col_co2 = [c for c in df.columns if c.startswith("Annual production-based emissions")]
if col_co2:
    df["co2_mt"] = df["co2_mt"].combine_first(df[col_co2[0]])
    df = df.drop(columns=col_co2)

try:
    reg = pd.read_csv("https://ourworldindata.org/grapher/political-regime.csv?v=1&csvType=full&useColumnShortNames=true")
    valor = [c for c in reg.columns if c not in ("Entity", "Code", "Year", "entity", "code", "year")][0]
    reg = reg.rename(columns={"Code": "iso3", "code": "iso3", "Year": "anio", "year": "anio"})
    etiquetas = {0: "Closed Autocracy", 1: "Electoral Autocracy", 2: "Electoral Democracy", 3: "Liberal Democracy"}
    # OWID publica ahora el régimen como texto ("Closed autocracy"); antes eran códigos 0-3.
    # Se normaliza al formato del Kaggle ("Closed Autocracy") para que ambas fuentes encajen.
    v = reg[valor]
    reg["regimen"] = v.map(etiquetas) if pd.api.types.is_numeric_dtype(v) else v.str.title()
    df = df.merge(reg[["iso3", "anio", "regimen"]], on=["iso3", "anio"], how="left")
    col_reg = [c for c in df.columns if c.startswith("Regime Type")]
    if col_reg:
        df["regimen"] = df["regimen"].combine_first(df[col_reg[0]])
        df = df.drop(columns=col_reg)
except Exception as e:
    print("  ! Régimen político no descargado:", e)

# Quitar años finales sin casi datos (el WDI tarda en publicar).
# Solo cuentan las variables que el script actualiza: las fijas por país (continente, región, renta)
# siempre tienen valor e inflarían el porcentaje, y las que solo vienen del Kaggle acaban en 2018.
actualizables = [c for c in wdi.columns if c not in ("iso3", "anio")] + ["co2_mt", "regimen"]
actualizables = [c for c in actualizables if c in df.columns]
llenado = df[actualizables].notna().mean(axis=1).groupby(df["anio"]).mean()
ultimo = llenado[llenado > 0.30].index.max()
print("\n% de valores por año (variables actualizables):")
print((llenado * 100).round(0).astype(int).to_string())
print(f"Último año conservado: {ultimo}")
df = df[df["anio"] <= ultimo]

# 6. Indicadores calculados
def col(prefijo):
    return next(c for c in df.columns if c.startswith(prefijo))

pop = col("Population, total")
df["co2_pc"] = df["co2_mt"] * 1e6 / df[pop]
df["brecha_paro_pp"] = df["paro_mujeres_pct"] - df["paro_hombres_pct"]
df["brecha_participacion_pp"] = df["participacion_laboral_hombres_pct"] - df["participacion_laboral_mujeres_pct"]
df["brecha_empresa_pp"] = df[col("Cost of business start-up procedures, female")] - df[col("Cost of business start-up procedures, male")]

def norm(s):
    return (s - s.min()) / (s.max() - s.min())

# Índice de igualdad: escaños de mujeres en el parlamento + participación laboral femenina, normalizados 0-1.
# No incluye el índice Women Business and the Law porque el Banco Mundial dejó de publicarlo en la API
# (solo llega a 2018) y el índice quedaría cortado ahí; esa columna se conserva aparte en el dataset.
esc = col("Proportion of seats held by women")
df["indice_igualdad"] = pd.concat([norm(df[esc]), norm(df["participacion_laboral_mujeres_pct"])], axis=1).mean(axis=1, skipna=False)

# Desacoplamiento por país: crecimiento del PIB per cápita REAL (US$ constantes de 2015, sin el efecto
# de la inflación) frente al del CO2 per cápita, entre el primer y el último año en que hay ambos datos.
# Se guardan esos dos años para poder comprobarlo, y si el tramo es más corto que MIN_AÑOS_DESAC
# el valor se deja vacío (no sería comparable).
MIN_AÑOS_DESAC = 10
ult = df.dropna(subset=["pib_pc_constante", "co2_pc"]).sort_values("anio").groupby("iso3").agg(
    desac_anio_ini=("anio", "first"), desac_anio_fin=("anio", "last"),
    pib_ini=("pib_pc_constante", "first"), pib_fin=("pib_pc_constante", "last"),
    co2_ini=("co2_pc", "first"), co2_fin=("co2_pc", "last"))
# En logaritmos: ln(PIB_fin/PIB_ini) - ln(CO2_fin/CO2_ini). Así un país que parte de un CO2 muy bajo
# (p. ej. Laos, x17) no da valores extremos, y duplicar o reducir a la mitad pesan lo mismo (±0,69).
# > 0: el PIB crece más que las emisiones (desacoplamiento); < 0: las emisiones crecen más que el PIB.
ult["desacoplamiento"] = np.log(ult["pib_fin"] / ult["pib_ini"]) - np.log(ult["co2_fin"] / ult["co2_ini"])
cortos = ult["desac_anio_fin"] - ult["desac_anio_ini"] < MIN_AÑOS_DESAC
ult.loc[cortos, "desacoplamiento"] = float("nan")
print(f"Desacoplamiento: {(ult['desac_anio_ini'] > 2000).sum()} países empiezan después de 2000, "
      f"{cortos.sum()} descartados por tener menos de {MIN_AÑOS_DESAC} años")
df = df.merge(ult[["desacoplamiento", "desac_anio_ini", "desac_anio_fin"]], left_on="iso3", right_index=True, how="left")

df["periodo"] = pd.cut(df["anio"], [1999, 2009, 2018, 2030], labels=["2000-2009", "2010-2018", "2019-2024"])

primeras = ["iso3", "pais", "anio", "periodo", "Continent", "World Regions (UN SDG Definition)", renta, "regimen"]
df = df[[c for c in primeras if c in df.columns] + [c for c in df.columns if c not in primeras]]
df.to_csv("dataset_final.csv", index=False)

# 7. Informe de cobertura para el documento
inf = pd.DataFrame({
    "pct_valores": (df.notna().mean() * 100).round(1),
    "primer_anio": {c: df.loc[df[c].notna(), "anio"].min() for c in df.columns},
    "ultimo_anio": {c: df.loc[df[c].notna(), "anio"].max() for c in df.columns},
})
inf.to_csv("informe_cobertura.csv")
print(f"\nListo: {len(df)} filas x {df.shape[1]} columnas, {df['iso3'].nunique()} países, años {df['anio'].min()}-{df['anio'].max()}")
print("Envía dataset_final.csv e informe_cobertura.csv para actualizar el documento.")
