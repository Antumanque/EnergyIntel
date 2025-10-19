# First Run Guide - API Data Ingestion Template

## Very First Steps

### 1. Create your .env file
```bash
cp .env.example .env
```

Your `.env` is already configured with the your_data_endpoint URL!

### 2. Start the database
```bash
docker-compose up -d api_db
```

**What happens**: MariaDB 10.11 container starts and runs `db/init.sql` to create the `raw_api_data` table.

Wait about 30 seconds for the database to be healthy:
```bash
docker-compose ps
```

You should see:
```
NAME                      STATUS                   PORTS
api_ingestion_db    Up (healthy)             0.0.0.0:3306->3306/tcp
```

### 3. Run the data ingestion
```bash
docker-compose run --rm api_app
```

**What happens** (step by step):

1. **App starts**: Loads settings from `.env`
2. **Database connection**: Connects to MariaDB at `api_db:3306`
3. **Table verification**: Ensures `raw_api_data` table exists
4. **Fetches URL**: Makes GET request to the your_data_endpoint API
5. **Stores raw data**: Saves the **ENTIRE JSON response as ONE row** in `raw_api_data`
6. **Logs results**: Prints summary and exits

---

## What Gets Stored (Current Behavior)

### ⚠️ Important: Raw Data Dump (Phase 1)

The current implementation stores the **ENTIRE API response as a single JSON blob**.

Example of what goes into the database:

| id | source_url | fetched_at | status_code | data | error_message |
|----|------------|------------|-------------|------|---------------|
| 1 | https://api.example.com/v1/data | 2025-10-18 10:30:00 | 200 | `[{...}, {...}, {...}]` (entire JSON array) | NULL |

The `data` column contains something like:
```json
[
  {
    "id": 1,
    "nombre": "Company A",
    "tipo": "Generador",
    ...
  },
  {
    "id": 2,
    "nombre": "Company B",
    "tipo": "Distribuidor",
    ...
  },
  ...many more objects...
]
```

### This is BY DESIGN
- ✅ **Phase 1**: Raw data dump (what we have now)
- ❌ **Phase 2**: Normalization into separate tables (needs to be built)

---

## Verify the Data

### Connect to database
```bash
docker-compose exec api_db mysql -u api_user -papi_password api_ingestion
```

### Query the raw data
```sql
-- See all fetches
SELECT id, source_url, fetched_at, status_code
FROM raw_api_data;

-- See the actual JSON data (first 1000 chars)
SELECT id, source_url, LEFT(data, 1000) as preview
FROM raw_api_data
WHERE source_url LIKE '%your_data_endpoint%';

-- Count how many objects are in the JSON array
SELECT
  id,
  source_url,
  JSON_LENGTH(data) as num_records,
  fetched_at
FROM raw_api_data
WHERE source_url LIKE '%your_data_endpoint%';
```

---

## Next Phase: Normalization (To Be Built)

To create an `your_data_endpoint` table with **one row per object**, you need to:

### 1. Create the normalized table schema
```sql
CREATE TABLE your_data_endpoint (
  id INT PRIMARY KEY,
  nombre VARCHAR(255),
  tipo VARCHAR(100),
  -- add all other fields from the JSON
  raw_data_id BIGINT,  -- Reference back to raw_api_data
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (raw_data_id) REFERENCES raw_api_data(id)
);
```

### 2. Build a transformation script

Create `src/transformers/your_data_endpoint.py`:
```python
import json
from typing import List, Dict

def parse_your_data_endpoint(raw_json: str) -> List[Dict]:
    """
    Parse the your_data_endpoint JSON array into individual records.

    Args:
        raw_json: The raw JSON string from raw_api_data.data

    Returns:
        List of dictionaries, one per interesado
    """
    data = json.loads(raw_json)

    records = []
    for item in data:
        record = {
            'id': item.get('id'),
            'nombre': item.get('nombre'),
            'tipo': item.get('tipo'),
            # ... map all fields
        }
        records.append(record)

    return records
```

### 3. Add a processing step to main.py

After raw data is stored, optionally run transformations:
```python
# In src/main.py
from src.transformers.your_data_endpoint import parse_your_data_endpoint

# After storing raw data:
if 'your_data_endpoint' in url:
    # Parse and normalize
    records = parse_your_data_endpoint(data)
    for record in records:
        db_manager.insert_interesado(record, raw_data_id=row_id)
```

---

## Current Workflow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                     PHASE 1 (Current)                       │
│                       Raw Data Dump                          │
└─────────────────────────────────────────────────────────────┘

API URL
  ↓
httpx client (with retries)
  ↓
Raw JSON response (entire array)
  ↓
Stored in raw_api_data table
  └─> ONE row with ENTIRE JSON

┌─────────────────────────────────────────────────────────────┐
│                    PHASE 2 (To Build)                       │
│                     Normalization                            │
└─────────────────────────────────────────────────────────────┘

Query raw_api_data.data
  ↓
Parse JSON array
  ↓
Extract each object
  ↓
Insert into your_data_endpoint table
  └─> MANY rows, one per object
```

---

## Do You Need to Build Phase 2 Now?

**No!** The raw data dump is perfectly valid and useful:

### ✅ Advantages of Raw Storage
1. **Historical record**: You have the exact API response at that moment
2. **Flexibility**: Can re-process/re-normalize later without re-fetching
3. **Debugging**: Can see exactly what the API returned
4. **Data recovery**: If normalization has bugs, you still have the source

### When to Build Normalization
- When you need to **query specific fields** efficiently
- When you need to **join with other tables**
- When you need to **update individual records**
- When you need to **analyze trends** across fields

---

## Recommended Approach

1. **Run Phase 1 first** (raw dump) ✅ Ready now!
2. **Inspect the data structure** to understand all fields
3. **Design the normalized schema** based on actual data
4. **Build transformer** to parse and insert
5. **Decide**: Transform on-fetch OR batch-transform later

Would you like help building the normalization step?
