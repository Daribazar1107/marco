# Марко — хувийн туслах AI агент

Монгол дуут зааврыг ойлгож, Google Calendar, Gmail, Contacts-той холбогдон цаг товлох,
имэйл бичих, харилцагч хайх үйлдлийг гүйцэтгэдэг вэб туслах.
(МУИС, МТ, дипломын ажил — Ц.Дарьбазар, удирдагч А.Амгалан)

## Архитектур

```
Browser (static/index.html)  ── микрофон, чат, "Илгээх үү?" карт
   │  Supabase нэвтрэлтийн token
   ▼
FastAPI (backend/app)
   voice.py        яриа → текст   (BuzzASR Whisper эсвэл Chimege API)
   agent.py        Gemma 4 (Ollama) tool сонгоно, ажиллуулна
   tools.py        5 tool: calendar үүсгэх/харах, contacts хайх, мэйл ноорог/илгээх
   google_auth.py  Google OAuth, хэрэглэгч бүрийн token
   voice.py        текст → яриа   (edge-tts, mn-MN-BataaNeural)
   ▼
Supabase Postgres: profiles, conversations, messages, google_tokens
```

`send_email` шууд ажиллахгүй: хэрэглэгч "Тийм" дарсны дараа л илгээнэ (human-in-the-loop).

## Файлууд

| Файл | Үүрэг |
|---|---|
| `app/main.py` | Сервер, хуудсууд, `/stt` `/tts` туршилтын endpoint |
| `app/routes/assistant.py` | `/api/voice`, `/api/chat`, `/api/confirm` |
| `app/routes/google.py` | `/api/google/connect`, `callback`, `status` |
| `app/auth.py` | Supabase token шалгах, profile үүсгэх |
| `app/agent.py` | Agent loop, баталгаажуулалт хүлээх үйлдлүүд |
| `app/tools.py` | AI-ийн дуудаж болох 5 функц |
| `app/google_auth.py` | OAuth web flow, token хадгалах/шинэчлэх |
| `app/conversations.py` | Ярианы түүх (сүүлийн 10 мессеж AI-д очно) |
| `app/voice.py`, `app/chimege.py` | Яриа таних, дуу үүсгэх |
| `app/static/index.html` | Марко-гийн вэб хуудас |
| `app/static/tools.html` | Өмнөх яриа ↔ текст туршилтын хуудас (`/tools`) |

## Анх удаа тохируулах

**1. Сангууд**
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Ollama + Gemma 4**
```bash
brew install ollama
ollama serve                 # тусдаа terminal-д ажиллуулж орхино
ollama pull gemma4:26b       # нарийн нэрийг ollama.com/library/gemma4 дээрээс шалгана
```

**3. `.env`** — `.env.example`-ээс дутуу мөрүүдийг нэмнэ. Хамгийн чухал нь:
```
SUPABASE_ANON_KEY=...        # Supabase → Settings → API → anon public
```

**4. Шинэ хүснэгт (google_tokens)**
```bash
alembic upgrade head
```

**5. Google Cloud** (console.cloud.google.com)
- Calendar API, Gmail API, People API-г идэвхжүүлнэ
- OAuth consent screen → External → Test users-д өөрийн Gmail-ийг нэмнэ
- Credentials → OAuth client ID → **Web application**
  - Authorized redirect URI: `http://localhost:8000/api/google/callback`
- JSON-ийг татаж `backend/credentials.json` нэрээр хадгална (git-д орохгүй)

**6. Supabase Auth**: Authentication → Providers → Email асаалттай байх.
Туршилтын үед "Confirm email"-ийг унтраавал бүртгүүлмэгц нэвтэрнэ.

## Ажиллуулах

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
Browser: http://localhost:8000 → бүртгүүлэх/нэвтрэх → **Google холбох** → 🎤 эсвэл Space.

## Chimege руу шилжих

Token болон баримт бичиг ирмэгц `.env`:
```
STT_PROVIDER=chimege
CHIMEGE_TOKEN=...
CHIMEGE_STT_URL=...
CHIMEGE_TOKEN_HEADER=...
```
`app/chimege.py` доторх TODO-г баримт бичигтэй тулгаж шалгана.

## Туршиж үзэх командууд

- «Маргааш 3 цагт Амгалан багштай уулзалт товлооч»
- «Маргааш юу байгаа вэ?»
- «Болдын имэйл хаяг юу вэ?»
- «Болдод маргаашийн уулзалт хойшиллоо гэж мэйл илгээ» → "Тийм, илгээ"
- «Болдод мэйлийн ноорог бичээд хадгал»

Хариу бүрийн дээрх 🔧 мөрийг дарвал AI ямар tool-ыг ямар параметртэй дуудсан нь харагдана.
