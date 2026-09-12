"""
FastAPI-приложение для GPN-парсера.
Endpoints:
  GET  /api/stations  — текущие данные (из кеша или свежий парсинг)
  POST /api/refresh   — принудительно запустить парсер и обновить кеш
"""

from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Добавляем корень проекта в PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.gpn_parser import get_stations_json, export_to_json

app = FastAPI(
    title="GPN Fuel Prices API",
    description="API цен на топливо Газпромнефть (Пермь)",
    version="1.0.0",
)

# CORS — разрешаем GitHub Pages и локальную разработку
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://oompaloomp.github.io",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "*",  # для простоты на этапе разработки
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_PATH = ROOT / "data" / "stations.json"


@app.get("/")
def root():
    return {
        "service": "GPN Fuel Prices API",
        "endpoints": {
            "GET /api/stations": "Текущие цены",
            "POST /api/refresh": "Обновить данные",
        },
    }


@app.get("/api/stations")
def get_stations():
    """Возвращает актуальные данные. Если кеш есть — из него, иначе парсит."""
    if CACHE_PATH.exists():
        try:
            import json
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            return JSONResponse(content=data)
        except Exception:
            pass

    # Кеша нет или он битый — парсим
    try:
        data = get_stations_json()
        export_to_json(CACHE_PATH)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка парсера: {str(e)}")


@app.post("/api/refresh")
def refresh_stations():
    """Принудительно запускает парсер и обновляет stations.json."""
    try:
        path = export_to_json(CACHE_PATH)
        data = get_stations_json()
        return JSONResponse(
            content={
                "status": "ok",
                "message": f"Данные обновлены и сохранены в {path.name}",
                "updated_at": data["updated_at"],
                "stations_count": len(data["stations"]),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
