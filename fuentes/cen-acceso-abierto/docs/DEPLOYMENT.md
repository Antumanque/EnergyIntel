# Guía de Deployment en Producción

## 🚀 Deployment Simple (Un Solo Comando)

```bash
./deploy.sh
```

Este script ejecuta automáticamente:
1. ✅ **Git pull** - Actualiza código desde GitHub
2. ✅ **Instala dependencias** - uv sync
3. ✅ **Ejecuta migraciones** - Aplica cambios de BD
4. ✅ **Verifica conexión** - Valida que funcione

---

## 📋 Comandos Disponibles

| Comando | Qué hace |
|---------|----------|
| `./deploy.sh` | Deployment completo |
| `./deploy.sh --migrations` | Solo migraciones (sin git pull ni deps) |
| `./deploy.sh --status` | Ver estado de migraciones |

---

## 🔄 Flujo Típico

### En Desarrollo (Local)
```bash
# 1. Hacer cambios
git add .
git commit -m "feat: add new feature"
git push
```

### En Producción (Servidor Antumanque)
```bash
# 2. Un solo comando
./deploy.sh
```

El script hace TODO automáticamente.

---

## 🗄️ Sistema de Migraciones

### ¿Qué son?
Cambios incrementales al schema de BD que se ejecutan en orden.

### Tabla de Tracking
El sistema registra qué migraciones ya se ejecutaron en `schema_migrations`.

**Garantía**: Cada migración se ejecuta **UNA SOLA VEZ**.

### Crear Nueva Migración
```bash
# 1. Crear archivo en db/migrations/
cat > db/migrations/003_add_index.sql << 'SQL'
CREATE INDEX idx_pdf_producer ON formularios_parseados(pdf_producer);
SQL

# 2. Commit y push
git add db/migrations/003_add_index.sql
git commit -m "perf: add index"
git push

# 3. En producción
./deploy.sh  # ← Ejecuta automáticamente la nueva migración
```

---

## ⚠️ Seguridad

El script **siempre pregunta** antes de ejecutar migraciones:

```
📋 MIGRACIONES PENDIENTES QUE SE EJECUTARÍAN:
  - 003_add_index.sql
¿Continuar? (y/N):
```

---

## 🛡️ Manejo de Errores

### Error en Git Pull
```bash
git status  # Ver conflictos
git stash   # Guardar cambios locales
./deploy.sh # Reintentar
```

### Error en Migración
- El sistema hace **rollback automático**
- Ningún dato se pierde
- Corrige el SQL y vuelve a ejecutar

---

## 📚 Best Practices

### 1. Migraciones Idempotentes
✅ Usar `IF EXISTS` / `IF NOT EXISTS`
```sql
ALTER TABLE formularios_parseados
ADD COLUMN IF NOT EXISTS pdf_producer VARCHAR(255);
```

### 2. Nombres Descriptivos
✅ `003_add_pdf_metadata.sql`
❌ `migration3.sql`

### 3. Backup Antes de Cambios Grandes
```bash
mysqldump -u cen_user -p cen_acceso_abierto > backup_$(date +%Y%m%d).sql
./deploy.sh
```

---

**Última actualización**: 2025-10-20
