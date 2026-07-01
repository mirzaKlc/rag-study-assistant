# OzetAI

RAG (Retrieval-Augmented Generation) destekli bir çalışma asistanı. Ders notlarınızı ve geçmiş sınavlarınızı yükleyin; Google Gemini ile akademik özetler ve sınav tarzı pratik sorular üretin.

## Mimari

```
ozetAI/
├── app/                    # FastAPI backend
│   ├── api/v1/endpoints/   # /uploads, /ai uç noktaları
│   ├── core/                # config, logging, security
│   ├── models/              # Pydantic şemaları
│   ├── services/            # upload, vector (ChromaDB), ai (Gemini)
│   └── utils/                # PDF/TXT çıkarma, metin parçalama
├── frontend/                # React + TypeScript + Tailwind dashboard
└── requirements.txt
```

**Backend:** FastAPI · ChromaDB (vektör veritabanı) · sentence-transformers / Gemini embeddings · Google Gemini (`google-generativeai`)

**Frontend:** React 19 · TypeScript · Tailwind CSS v4 · Axios · react-markdown

## Özellikler

- Sürükle-bırak dosya yükleme (PDF / TXT) — ders notları ve geçmiş sınavlar için ayrı alanlar
- Yükleme sonrası otomatik metin çıkarma, parçalama (chunking) ve vektör indeksleme
- Gemini ile Markdown formatında akademik özet üretimi
- Geçmiş sınav tarzına uygun, çözümlü pratik soru üretimi (çoktan seçmeli, açık uçlu, doğru/yanlış, kodlama)
- Gece modu öncelikli, kurumsal indigo/slate temalı tek sayfa arayüz

## Kurulum

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
```

`.env` dosyası oluşturun (örnek değişkenler için `app/core/config.py` içine bakın):

```env
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.5-flash
EMBEDDING_PROVIDER=sentence_transformer   # veya "gemini"
ALLOWED_ORIGINS=http://localhost:5173
```

Sunucuyu başlatın:

```bash
uvicorn app.main:app --reload
```

API dokümantasyonu: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend
npm install
cp .env.example .env   # gerekirse VITE_API_BASE_URL değerini güncelleyin
npm run dev
```

Uygulama: `http://localhost:5173`

## API Uç Noktaları

| Yöntem | Yol | Açıklama |
|---|---|---|
| `POST` | `/api/v1/uploads/course-content` | Ders materyali yükle, indeksle |
| `POST` | `/api/v1/uploads/past-exams` | Geçmiş sınav yükle, indeksle |
| `POST` | `/api/v1/ai/summarize` | İndekslenmiş içerikten özet üret |
| `POST` | `/api/v1/ai/generate-questions` | Ders içeriği + sınav stiline göre pratik soru üret |
| `GET` | `/health` | Sağlık kontrolü |

## Klasör Detayları

- `app/services/upload_service.py` — dosya kaydetme + yükleme sonrası otomatik indeksleme
- `app/services/vector_service.py` — ChromaDB embedding/arama soyutlaması
- `app/services/ai_service.py` — Gemini tabanlı özet ve soru üretimi
- `frontend/src/components/Dashboard.tsx` — tek sayfa uygulamanın ana bileşeni
