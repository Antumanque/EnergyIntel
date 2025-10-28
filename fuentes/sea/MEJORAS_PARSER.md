# Mejoras del Parser de Resumen Ejecutivo

## Fecha: 27 de Octubre 2024

## Problema Inicial
El parser original solo detectaba links con el texto exacto "Resumen Ejecutivo", resultando en una tasa de éxito de **14.3%** (4/28 documentos).

## Mejoras Implementadas

### 1. Detección de "Ficha Resumen" para DIAs (+71.4pp)

**Problema:** Las Declaraciones de Impacto Ambiental (DIAs) no tienen "Resumen Ejecutivo", sino "Ficha Resumen" (típicamente Capítulo 10 o 11).

**Solución:** Ampliar patrones de búsqueda para detectar:
- `ficha resumen`
- `ficha_resumen`
- Cualquier link con "ficha" o "cap" o "capitulo" + "resumen"

**Impacto:** Tasa de éxito subió de 14.3% a **85.7%**

```python
# Buscar patrones de DIA (Ficha Resumen)
if ('ficha resumen' in text_lower or
    'ficha_resumen' in text_lower or
    (('ficha' in text_lower or 'cap' in text_lower or 'capitulo' in text_lower) and 'resumen' in text_lower)):
    # Extraer PDF
```

### 2. Aceptar Texto Abreviado en Links (+3.6pp)

**Problema:** Algunos documentos tienen el heading `<h3>Resumen ejecutivo</h3>` pero el link está abreviado como "RESUMEN EJ." en vez del texto completo.

**Solución:** Cuando encontramos el heading "Resumen ejecutivo", tomar **cualquier link a PDF** en el `<ul>` siguiente, sin validar el texto del link.

**Impacto:** Tasa de éxito subió de 85.7% a **89.3%**

```python
if resumen_heading:
    next_sibling = resumen_heading.find_next_sibling()
    if next_sibling and next_sibling.name == 'ul':
        links = next_sibling.find_all('a', href=True)
        for link in links:
            href = link['href']
            # Tomar CUALQUIER link a PDF, sin validar texto
            if href.endswith('.pdf') or 'archivos' in href.lower():
                return result
```

### 3. Patrones Ampliados para EIAs

**Problema:** Algunos EIAs usan variantes como "Capítulo 0" o "Cap_00" en vez de "Capítulo 20".

**Solución:** Detectar múltiples variantes:
- `resumen ejecutivo`
- `capítulo 00` / `capitulo 00` / `cap 00` / `cap. 00` / `cap_00`
- `capítulo 20` / `capitulo 20` / `cap 20` / `cap_20`
- `capitulo_0`

## Resultados Finales

### Tasa de Éxito por Etapa
1. **Versión Original**: 14.3% (4/28)
2. **+ Ficha Resumen**: 85.7% (24/28)
3. **+ Texto Abreviado**: **89.3% (25/28)** ✅

### Mejora Total
- **+75 puntos porcentuales**
- **6.25x más exitoso** que la versión original

### Documentos Restantes (3)
Los 3 documentos que todavía fallan **no tienen links individuales a capítulos** en `documento.php`. Solo tienen el documento firmado completo disponible.

## Archivos Modificados

### `src/parsers/resumen_ejecutivo.py`
- **Líneas 165-262**: ESTRATEGIA 1 y 2 mejoradas
- Detecta "Resumen Ejecutivo" (EIAs) y "Ficha Resumen" (DIAs)
- Acepta texto abreviado cuando hay heading
- Patrones ampliados para variantes

## Lecciones Aprendidas

1. **EIAs vs DIAs tienen estructuras diferentes**
   - EIAs: "Resumen Ejecutivo" (Cap. 0 o 20)
   - DIAs: "Ficha Resumen" (Cap. 10 o 11)

2. **El texto del link puede estar abreviado**
   - No confiar solo en el texto del link
   - Usar el contexto (heading) para validar

3. **Múltiples variantes de numeración**
   - Cap 00, Cap 20, Capítulo 0, etc.
   - Necesario buscar todas las variantes

4. **No todos los documentos tienen links individuales**
   - Algunos solo tienen documento firmado completo
   - 89.3% es probablemente el máximo alcanzable

## Próximos Pasos Sugeridos

1. **Procesar los 3 documentos restantes descargando documento completo**
   - Usar `documento_firmado_url`
   - Descargar PDF completo
   - Extraer solo páginas del resumen ejecutivo

2. **Escalar a toda la base de datos**
   - Procesar los ~29,000 proyectos completos
   - Monitorear tasa de éxito en producción

3. **Implementar caché de resultados**
   - Evitar reprocesar documentos exitosos
   - Solo reintentar errores tras mejoras del parser
