# 🚀 Nobaj (نُبَاج) — منصة معالجة الوسائط المتكاملة
**Next-Generation Server-Side Online Media Processing Suite**

[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg?logo=docker&logoColor=white)](#تشغيل-المشروع-باستخدام-docker)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-Engine-007808.svg?logo=ffmpeg&logoColor=white)](https://ffmpeg.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-38B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

[English Documentation Below](#-english-documentation) | [التوثيق باللغة العربية](#-دليل-الاستخدام-بالعربية)

---

## 🇸🇦 دليل الاستخدام بالعربية

**Nobaj** هي منصة وسائط مفتوحة المصدر عالية الأداء، مبنية على **FastAPI** ومحرك **FFmpeg**، تدمج أدوات الفيديو الأساسية في واجهة ويب واحدة فائقة السرعة وعصرية بتقنية **Tailwind CSS**.

### 🌟 الميزات الأساسية:
1. **🗜️ ضغط الفيديو (Video Compressor):**
   - خيارات ضغط ذكية: متوازن (توفير 50-60%)، قوي (70-80%)، وجودة عالية.
   - إمكانية تحديد الدقة: الحفاظ على الأصل، 1080p, 720p, 480p, 360p باستخدام مرشح **Lanczos**.
   - خيارات الترميز: **H.264** للتوافق الشامل، أو **H.265 / HEVC** لضغط مضاعف.
2. **🎵 استخراج الصوت (Audio Extractor):**
   - تحويل واستخراج الصوت بصيغ: **MP3, AAC, WAV, FLAC, OGG**.
   - التحكم بمعدل البت: 128k, 192k, 256k, 320k.
   - دعم القنوات: مجسم (Stereo) أو أحادي (Mono).
3. **🎞️ تحويل الفيديو إلى GIF (Video to GIF):**
   - خوارزمية **Palettegen / Paletteuse** مع ترشيح Bayer لتجنب تشوه الألوان والحصول على أعلى دقة ممكنة.
   - تحديد الإطارات في الثانية (FPS): 10, 15, 20, 24.
   - تحديد أوقات البداية والنهاية (Trim Range) بالثواني.
4. **🚦 نظام طوابير (Queue Management):**
   - حماية السيرفر من الانهيار تحت الضغط عبر تحديد عدد العمليات المتزامنة (`MAX_CONCURRENT_JOBS`).
   - إظهار ترتيب المستخدم في قائمة الانتظار لحظياً (`في الانتظار - دورك: 1`).
5. **🧹 حذف الملفات المؤقتة تلقائياً (Auto Cleanup):**
   - خدمة خلفية تفحص دورياً وتحذف الملفات المرفوعة والناتجة بعد انقضاء الوقت المحدد (`FILE_TTL_MINUTES=30`).
6. **🛡️ معايير أمان عالية:**
   - فحص الامتدادات ونوع الـ MIME.
   - حماية مسارات الملفات من هجمات Path Traversal.
   - وضع قيود على حجم الملف والمدة القصوى.
7. **🌐 واجهة متجاوبة متعددة اللغات:**
   - تصميم متجاوب يعمل بسلاسة على الهواتف والأجهزة اللوحية والمكتبية.
   - قائمة لغات احترافية تدعم 13 لغة: العربية، الإنجليزية، الإسبانية، الفرنسية، الألمانية، البرتغالية، الإيطالية، التركية، الروسية، الصينية المبسطة، اليابانية، الكورية، والهندية.
   - تبديل تلقائي بين RTL للعربية وLTR لبقية اللغات مع حفظ اختيار المستخدم.
8. **📊 إحصائيات واستخدام حقيقي:**
   - عدّاد زوار فريدين وزيارات اليوم وإجمالي العمليات المكتملة.
   - تخزين دائم في SQLite داخل volume مستقل حتى لا تختفي الأرقام بعد إعادة تشغيل الحاوية.
   - لوحة خاصة على `/admin` محمية بقيمة `ADMIN_TOKEN` تعرض تفاصيل العمليات والزيارات اليومية.
9. **📢 مساحات إعلانية جاهزة:**
   - أماكن Responsive محجوزة في الـ Landing Page مع حد أدنى ثابت لتجنب تحرك التصميم.
   - لا يتم تحميل Google AdSense إلا بعد وضع Client وSlot IDs في `.env`.

---

### 🛠️ البنية المعمارية للمشروع:
```plaintext
Nobaj/
├── backend/                    # طبقة الباك إند
│   ├── app/
│   │   ├── main.py             # نقطة انطلاق FastAPI والـ Lifespan
│   │   ├── core/               # الإعدادات، الأمان، والثوابت
│   │   ├── services/
│   │   │   ├── ffmpeg/         # تشغيل أوامر FFmpeg وفحص الملفات والـ GPU
│   │   │   ├── strategies/     # نمط الاستراتيجية (Compress, Audio, GIF)
│   │   │   ├── queue/          # إدارة الطابور والمهام والتحكم في التزامن
│   │   │   └── cleanup/        # مؤقت الحذف التلقائي للملفات القديمة
│   │   └── routes/             # مسارات الـ API والـ Health Check
│   └── requirements.txt
├── frontend/                   # الواجهة الأمامية
│   ├── static/                 # ملفات CSS و JS والشعارات
│   └── templates/index.html    # صفحة التطبيق التفاعلية
├── docker/                     # بيئة Docker
│   ├── Dockerfile
│   └── nginx.conf              # إعدادات Nginx للإنتاج
├── deploy/                     # سكريبتات النشر على السيرفرات
│   └── hetzner-setup.sh
├── docker-compose.yml
├── .env.example
└── README.md
```

---

### 🐳 تشغيل المشروع باستخدام Docker (موصى به)

1. **قم بنسخ ملف البيئة وضبط الإعدادات (اختياري):**
   ```bash
   cp .env.example .env
   # مطلوب للوحة /admin
   sed -i "s/^ADMIN_TOKEN=$/ADMIN_TOKEN=$(openssl rand -hex 32)/" .env
   ```

2. **شغّل المشروع عبر Docker Compose:**
   ```bash
   docker compose up -d --build
   ```

3. افتح متصفحك على: `http://localhost:8000` (منفذ التطبيق مربوط بـ localhost فقط).
4. لتشغيل وسيط Nginx على المنفذ 80، استخدم: `docker compose --profile production up -d --build`.

---

### 🌐 الرفع والتشغيل على سيرفر Hetzner Cloud

تم تجهيز سكريبت إعداد تلقائي لتشغيل السيرفر بأمر واحد على نظام Ubuntu:

1. اتصل بسيرفر Hetzner عبر SSH:
   ```bash
   ssh root@<YOUR_SERVER_IP>
   ```

2. انسخ ملفات المشروع إلى السيرفر أو اسحبها من مستودعك:
   ```bash
   git clone <YOUR_REPO_URL> /opt/nobaj
   cd /opt/nobaj
   ```

3. شغّل سكريبت التثبيت التلقائي:
   ```bash
   sudo bash deploy/hetzner-setup.sh
   ```

يقوم السكريبت تلقائياً بـ:
- تحديث الحزم وتثبيت Docker و Docker Compose.
- إعداد الجدار الناري (UFW) وفتح المنفذين 80 و22. يبقى منفذ التطبيق 8000 محلياً خلف Nginx.
- توليد رمز وصول عشوائي للوحة الإدارة وإنشاء ملف `.env`.
- بناء وتشغيل الحاويات في الخلفية.

**مهم:** إعداد النشر المرفق يخدم HTTP فقط. أضف شهادة TLS ونطاقاً عبر وكيل HTTPS قبل استخدام لوحة الإدارة أو إرسال ملفات خاصة عبر الإنترنت.

---

### ⚙️ خيارات التخصيص (`.env`)

| المتغير | القيمة الافتراضية | الوصف |
| :--- | :--- | :--- |
| `PORT` | `8000` | منفذ تشغيل الخادم |
| `MAX_UPLOAD_SIZE_MB` | `500` | الحد الأقصى لحجم الملف المرفوع (ميجابايت) |
| `MAX_DURATION_SECONDS` | `1800` | الحد الأقصى لمدة الفيديو (30 دقيقة) |
| `MAX_CONCURRENT_JOBS` | `2` | عدد عمليات المعالجة المتزامنة لحماية موارد المعالج |
| `FILE_TTL_MINUTES` | `30` | مدة بقاء الملف قبل حذفه تلقائياً لحفظ المساحة |
| `ENABLE_GPU` | `true` | محاولة استخدام كروت الشاشة للترميز السريع إن وُجدت |
| `ADMIN_TOKEN` | فارغ | رمز طويل للوصول إلى لوحة الإحصائيات الخاصة على `/admin` |
| `GOOGLE_ADSENSE_CLIENT` | فارغ | معرّف ناشر AdSense بعد الموافقة |
| `GOOGLE_ADSENSE_SLOT_TOP` | فارغ | معرّف مساحة الإعلان العلوية |
| `GOOGLE_ADSENSE_SLOT_BOTTOM` | فارغ | معرّف مساحة الإعلان السفلية |

---

<br>

---

## 🇬🇧 English Documentation

**Nobaj** is a high-performance, server-side online media suite built with **FastAPI**, **FFmpeg**, and styled with **Tailwind CSS**. It provides a clean, unified platform for video compression, audio extraction, and ultra-high-quality video-to-GIF conversion.

### 🌟 Key Features:
- **🗜️ Video Compressor:** Smart compression levels (Balanced, Aggressive, High Quality), resolution downscaling (1080p, 720p, 480p, 360p with Lanczos filters), and multi-codec support (H.264, H.265/HEVC, VP9).
- **🎵 Audio Extractor:** Extract soundtracks to MP3, AAC, WAV, FLAC, and OGG formats with customizable bitrates (up to 320 kbps) and channel mappings (Stereo/Mono).
- **🎞️ Video to GIF:** Advanced two-pass `palettegen` & `paletteuse` algorithm with Bayer dithering for rich 256-color reproduction without banding.
- **🚦 Concurrency Queue Manager:** Built-in FIFO queue with bounded simultaneous FFmpeg processes (`MAX_CONCURRENT_JOBS`) to ensure your VPS CPU and memory never choke under load.
- **🧹 Auto-Cleanup Daemon:** Automated background worker that deletes temporary uploads and processed files after `FILE_TTL_MINUTES` expiration.
- **🛡️ Security Hardened:** Strict MIME-type checking, file extension validation, Path Traversal protection, and UUID-based file storage.
- **🌐 13 Languages & Mobile Friendly:** A polished language menu supports Arabic, English, Spanish, French, German, Portuguese, Italian, Turkish, Russian, Simplified Chinese, Japanese, Korean, and Hindi. The interface switches between RTL and LTR automatically and remembers the user's choice.
- **📊 First-party analytics:** Persistent SQLite metrics for visitors and processing operations, plus a token-protected `/admin` dashboard.
- **📢 Ad-ready layout:** Responsive, reserved ad slots that remain empty until valid Google AdSense IDs are configured.

---

### 🚀 Quickstart with Docker Compose

```bash
# 1. Clone repository & enter directory
git clone <YOUR_REPO_URL> nobaj
cd nobaj

# 2. Copy environment file
cp .env.example .env

# 3. Build and launch container
docker compose up -d --build
```
Access the application at `http://localhost:8000`. The app port is bound to localhost; enable the `production` Compose profile to expose Nginx on port 80.

The included deployment proxy is HTTP-only. Configure TLS with your domain before sending private files or using the admin dashboard over the internet.

---

### 🖥️ Hetzner Cloud Server Deployment

Nobaj includes an automated provisioning script for Ubuntu 22.04 / 24.04:

```bash
# Run automated setup on your server
sudo bash deploy/hetzner-setup.sh
```

---

### 🧩 Extensibility: Adding New Tools
Nobaj uses the **Strategy Pattern**. To add a new feature (e.g., Video Watermark or Video Trimmer):
1. Create a new strategy class in `backend/app/services/strategies/your_tool.py` inheriting from `MediaStrategy`.
2. Implement `build_command()` and `get_output_extension()`.
3. Register it in `backend/app/services/strategies/__init__.py`.
4. The API and Queue will automatically support your new tool!

---

### 📜 License
This project is licensed under the MIT License.
