# Data Normalization Strategy

Understanding how raw API data is transformed into normalized database tables.

## 📊 Two-Phase Architecture

### Phase 1: Raw Data Storage (`raw_api_data` table)
- **Purpose**: Complete, unmodified historical record of API responses
- **Retention**: Forever (never deleted)
- **Updates**: Never (each fetch creates a new row)

### Phase 2: Normalized Tables (`interesados`, etc.)
- **Purpose**: Structured, queryable data optimized for analysis
- **Strategy**: **Append-Only** (see below)
- **Source**: Transformed from `raw_api_data`

---

## 🔄 Append-Only Strategy (IMPORTANTE)

### What is "Append-Only"?

The normalization process **ONLY adds new records**. It never:
- ❌ Updates existing records
- ❌ Deletes removed records
- ❌ Modifies historical data

### Why Append-Only?

1. **Historical Preservation**: Keep complete record of all solicitudes ever seen
2. **Audit Trail**: Know when entities were first discovered
3. **Data Safety**: Changes in API don't destroy historical information
4. **Idempotency**: Running ingestion multiple times is safe

---

## 🔍 How It Works

### Example: `interesados` Table

**First Run (all new):**
```sql
-- API returns 200 records
-- Database is empty
-- Result: 200 records inserted
```

**Second Run (same data):**
```sql
-- API returns same 200 records
-- Database has 200 records
-- Result: 0 records inserted (all already exist)
```

**Third Run (5 new, 2 removed, 193 unchanged):**
```sql
-- API returns 198 records (5 new, 2 removed, 193 same)
-- Database has 200 records
-- Result: 5 NEW records inserted
-- The 2 removed records STAY in database (historical record)
```

---

## 📝 Implementation Details

### Unique Key: Composite `(solicitud_id, razon_social)`

**IMPORTANTE**: Una solicitud puede tener **múltiples interesados** (empresas). Por ejemplo:
- Solicitud 219: Codelco + SQM (dos empresas, misma solicitud)
- Solicitud 232: CGE + INERSA (dos empresas, misma solicitud)

Por eso, el unique key es **compuesto**:

```sql
UNIQUE KEY unique_solicitud_razon (solicitud_id, razon_social)
```

Esto permite:
- ✅ Múltiples empresas en la misma solicitud
- ❌ La misma empresa duplicada en la misma solicitud

### Deduplication Logic

Located in `src/database.py` → `insert_interesados_bulk()`:

```python
# PASO 1: Obtener combinaciones (solicitud_id, razon_social) existentes
existing_combinations = SELECT solicitud_id, razon_social
                        FROM interesados
                        WHERE (solicitud_id = X AND razon_social = Y) OR ...

# PASO 2: Filtrar solo registros NUEVOS (combinaciones que no existen)
new_records = [r for r in records
               if (r.solicitud_id, r.razon_social) not in existing_combinations]

# PASO 3: Insertar SOLO los nuevos
INSERT INTO interesados (solicitud_id, razon_social, ...) VALUES (...)
```

### Timestamps

```sql
created_at  -- When first inserted (never changes)
updated_at  -- When last seen (currently NOT updated in append-only)
```

**Note**: In current append-only implementation, `updated_at` = `created_at` since we never update.

---

## 🎯 Testing the Behavior

### Test 1: Initial Load
```bash
# First run
docker-compose run --rm cen_app

# Check results
docker-compose exec cen_db mysql -u cen_user -pcen_password cen_acceso_abierto \
  -e "SELECT COUNT(*) as total FROM interesados;"
```

**Expected**: All records from API inserted

### Test 2: Re-run (No Changes)
```bash
# Run again immediately
docker-compose run --rm cen_app
```

**Expected Log Output**:
```
Found 200 existing solicitud_ids in database
Inserting 0 NEW records (skipping 200 existing)
No new records to insert (all already exist)
```

**Expected Database**: Same count, no duplicates

### Test 3: Verify No Duplicates

**IMPORTANTE**: Es normal tener el mismo `solicitud_id` múltiples veces (múltiples empresas por solicitud).
Lo que NO debería haber es la misma **combinación** (solicitud_id, razon_social).

```sql
-- Should return 0 rows (no duplicate combinations)
SELECT solicitud_id, razon_social, COUNT(*) as count
FROM interesados
GROUP BY solicitud_id, razon_social
HAVING count > 1;
```

**Ejemplo de datos válidos**:
```sql
-- Esto es CORRECTO (múltiples empresas en una solicitud):
solicitud_id | razon_social
219          | Codelco
219          | SQM
232          | CGE
232          | INERSA
```

### Test 4: Historical Preservation
```sql
-- Manually delete a record from API source (simulate removal)
-- Then run ingestion again

-- The deleted record should STILL be in database
SELECT * FROM interesados WHERE solicitud_id = <removed_id>;
-- Should return the record (preserved)
```

---

## 🔗 Data Lineage

Every normalized record links back to its source:

```sql
SELECT
    i.solicitud_id,
    i.razon_social,
    i.created_at as first_seen,
    r.source_url,
    r.fetched_at as api_fetch_time,
    r.status_code
FROM interesados i
JOIN raw_api_data r ON i.raw_data_id = r.id
WHERE i.solicitud_id = 219;
```

**Shows**: Which API call discovered this record and when.

---

## 📈 Monitoring Normalization

### Summary Metrics

After each run, check the summary:

```
INGESTION SUMMARY
============================================================
Total URLs processed: 1
Successful: 1
Failed: 0
Transformed: 1

Transformed Data:
  - https://.../interesados: 5 records
============================================================
```

**"5 records"** = 5 NEW records inserted (not total count)

### Database Queries

**Total records ever seen:**
```sql
SELECT COUNT(*) as total_historical FROM interesados;
```

**Latest raw fetch:**
```sql
SELECT
    JSON_LENGTH(data) as current_api_count
FROM raw_api_data
ORDER BY fetched_at DESC
LIMIT 1;
```

**Compare:**
```sql
SELECT
    (SELECT COUNT(*) FROM interesados) as db_total,
    (SELECT JSON_LENGTH(data) FROM raw_api_data ORDER BY fetched_at DESC LIMIT 1) as api_current,
    (SELECT COUNT(*) FROM interesados) -
    (SELECT JSON_LENGTH(data) FROM raw_api_data ORDER BY fetched_at DESC LIMIT 1) as removed_records;
```

---

## 🚨 When Records Differ

### Database > API Count
**Meaning**: Some records were removed from API but preserved in database

**Example**:
- Database: 250 records
- API: 245 records
- Difference: 5 records removed from API (still in your database)

**Action**: This is expected and correct behavior!

### Database < API Count
**Meaning**: New records in API not yet in database

**Example**:
- Database: 245 records
- API: 250 records
- Difference: 5 new records will be inserted on next run

**Action**: Run ingestion to capture new records

### Database = API Count
**Meaning**: Perfectly in sync (or coincidentally the same)

**Action**: No new records to insert

---

## 🔧 Advanced: Soft Deletes (Future Enhancement)

If you need to track "active" vs "removed" records:

### Option 1: Add `is_active` Column

```sql
ALTER TABLE interesados ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
```

**Logic**: Mark as inactive if not in current API response

### Option 2: Add `last_seen_at` Column

```sql
ALTER TABLE interesados ADD COLUMN last_seen_at TIMESTAMP;
```

**Logic**: Update timestamp when seen in API

### Option 3: Separate Table

```sql
CREATE TABLE interesados_active (
    solicitud_id INT PRIMARY KEY,
    FOREIGN KEY (solicitud_id) REFERENCES interesados(solicitud_id)
);
```

**Logic**: `interesados` = all historical, `interesados_active` = currently in API

---

## 📚 Code References

| Location | Purpose |
|----------|---------|
| `src/database.py:295-391` | `insert_interesados_bulk()` - Main deduplication logic |
| `src/database.py:244-301` | `insert_interesado()` - Single record insert |
| `src/main.py:114-167` | `_transform_if_needed()` - Transformation orchestration |
| `src/transformers/interesados.py` | Raw JSON → Normalized records |

---

## ✅ Best Practices

1. **Never manually UPDATE `interesados` table**
   - Breaks append-only invariant
   - Use raw_api_data if you need to reprocess

2. **Never manually DELETE from `interesados`**
   - Loses historical record
   - If needed, add `is_deleted` flag instead

3. **Always check logs after ingestion**
   - Verify NEW vs EXISTING counts
   - Ensure no unexpected duplicates

4. **Trust the raw data**
   - `raw_api_data` is source of truth
   - Can always rebuild `interesados` from raw

5. **Monitor growth trends**
   - Track new records over time
   - Alert on unexpected spikes or drops

---

## 🎯 Summary

**Key Principle**: **Append-Only = Add New, Never Modify or Delete**

**Benefits**:
- ✅ Complete historical record
- ✅ Safe idempotent operations
- ✅ Audit trail of all solicitudes
- ✅ No data loss from API changes

**Trade-offs**:
- ⚠️ Database grows over time (expected)
- ⚠️ Removed records stay (feature, not bug)
- ⚠️ Need separate queries for "currently active" vs "all historical"

**Perfect For**:
- 📊 Regulatory compliance
- 📈 Historical analysis
- 🔍 Audit requirements
- 🛡️ Data preservation
