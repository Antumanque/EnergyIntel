## 🚀 Quick Iteration Commands

Copy-paste these for rapid development cycles:

```bash
# Full reset workflow
docker-compose down -v && \
docker-compose build cen_app && \
docker-compose up -d cen_db && \
echo "Waiting 30s for database health check..." && \
sleep 30 && \
docker-compose run --rm cen_app
```