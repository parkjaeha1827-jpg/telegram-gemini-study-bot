# 🤖 Telegram Gemini Study & Homework Solver Bot
### តេលេក្រាម Bot ដោះស្រាយលំហាត់គ្រប់មុខវិជ្ជាជាមួយ Google Gemini Flash (High Reasoning)

Telegram Bot ឆ្លាតវៃសម្រាប់ជួយសិស្សានុសិស្សក្នុងការដោះស្រាយលំហាត់ សំណួរស្រាវជ្រាវ និងវិញ្ញាសាគ្រប់មុខវិជ្ជា (គណិត, រូប, គីមី, ជីវៈ, ខ្មែរ, អង់គ្លេស, ប្រវត្តិ, ភូមិ...) ដោយប្រើប្រាស់បច្ចេកវិទ្យា **Google Gemini Flash (High Reasoning)** និងអាចដំណើរការ 24/7 នៅលើ **Vercel Serverless** ដោយឥតគិតថ្លៃ។

---

## ✨ លក្ខណៈពិសេសចម្បង (Key Features)

- 📸 **ដោះស្រាយតាមរូបភាព (Photo Multimodal):** គ្រាន់តែថតរូបលំហាត់ពីសៀវភៅ ឬក្រដាសប្រឡងផ្ញើចូល Bot វានឹងស្កេន អានសមីការ និងដោះស្រាយភ្លាមៗ។
- 🧠 **Google Gemini Flash (High Reasoning):** ប្រើប្រាស់ Thinking Mode ដើម្បីគិតវិភាគស៊ីជម្រៅ ដោះស្រាយលំហាត់ពិបាកៗបានយ៉ាងត្រឹមត្រូវ។
- 📚 **គាំទ្រគ្រប់មុខវិជ្ជា (All Subjects Supported):**
  - **គណិតវិទ្យា (Math):** ពិជគណិត, ធរណីមាត្រ, ដេរីវេ, អាំងតេក្រាល, លីមីត, ប្រូបាប, វ៉ិចទ័រ...
  - **រូបវិទ្យា (Physics):** មេកានិច, អគ្គិសនី, ម៉ាញេទិច, រលក, អុបទិក, ទែម៉ូឌីណាមិច...
  - **គីមីវិទ្យា (Chemistry):** សមីការគីមី, គណនាម៉ូល, អាស៊ីត-បាស, គីមីសរីរាង្គ...
  - **ជីវវិទ្យា (Biology):** ហ្សែន/DNA, ការបែងចែកកោសិកា, មរតកវិទ្យា, ប្រព័ន្ធរាងកាយ...
  - **អក្សរសាស្ត្រខ្មែរ (Khmer):** តែងសេចក្តី, វិភាគអត្ថបទ, វេយ្យាករណ៍...
  - **ភាសាអង់គ្លេស (English):** Grammar, Reading, Translation, Vocabulary...
  - **ប្រវត្តិវិទ្យា និងភូមិវិទ្យា (History & Geography)**
  - **ទស្សនវិជ្ជា និងសីលធម៌-ពលរដ្ឋវិទ្យា (Philosophy & Civics)**
- 📝 **បង្ហាញដំណោះស្រាយមួយជំហានម្តងៗ (Step-by-Step):** បង្ហាញបម្រាប់ប្រធាន រូបមន្ត ដំណោះស្រាយលម្អិត ចម្លើយចុងក្រោយ និងគន្លឹះចងចាំ។
- ☁️ **Vercel Serverless Deployment:** មិនបាច់ជួល VPS ឬ Server អស់លុយទេ អាចដាក់លើ Vercel ដំណើរការ ២៤/៧ ដោយមិនបាច់បើកកុំព្យូទ័រចោល។
- 🚀 **Auto-Export to GitHub & Vercel:** មាន Script ស្វ័យប្រវត្តិសម្រាប់រុញកូដទៅ GitHub និងតភ្ជាប់ Vercel ភ្លាមៗ។

---

## 📁 រចនាសម្ព័ន្ធគម្រោង (Project Structure)

```text
├── api/
│   └── webhook.py        # Vercel Serverless Function (Webhook endpoint)
├── bot_core.py           # Logic គ្រប់គ្រង Telegram Bot & ការឆ្លើយតប
├── gemini_solver.py      # Engine ភ្ជាប់ Gemini API + High Reasoning Prompt
├── bot_polling.py        # សម្រាប់រត់តេស្តនៅលើកុំព្យូទ័រផ្ទាល់ខ្លួន (Local Polling)
├── setup_webhook.py      # ឧបករណ៍កំណត់ Telegram Webhook ទៅ Vercel ដោយ 1 Click
├── export_to_github.ps1  # Script ស្វ័យប្រវត្តិនាំចេញកូដទៅ GitHub
├── export_to_github.bat  # គ្រាន់តែ Double-click ដើម្បី Export ទៅ GitHub
├── vercel.json           # ការកំណត់សម្រាប់ Vercel Deployment
├── requirements.txt      # បណ្ណាល័យ Python (requests, python-dotenv)
├── test_bot.py           # Unit tests ផ្ទៀងផ្ទាត់កូដ
└── .env.example          # គំរូ Environment Variables
```

---

## 🛠️ ការណែនាំដំឡើងមួយជំហានម្តងៗ (Step-by-Step Guide)

### ជំហានទី ១៖ យក Telegram Bot Token
1. បើក Telegram ហើយស្វែងរក **[@BotFather](https://t.me/BotFather)**
2. ផ្ញើពាក្យបញ្ជា `/newbot`
3. ដាក់ឈ្មោះ Bot និង Username របស់ Bot (ឧទាហរណ៍៖ `my_study_helper_bot`)
4. អ្នកនឹងទទួលបាន **HTTP API Token** (ឧ. `7123456789:AAFx...`) សូមចម្លងទុក។

### ជំហានទី ២៖ យក Google Gemini API Key
1. ចូលទៅកាន់គេហទំព័រ **[Google AI Studio](https://aistudio.google.com/)**
2. ចុចប៊ូតុង **Get API key**
3. ចុច **Create API key** រួចចម្លង Key នោះទុក។

### ជំហានទី ៣៖ បង្កើតឯកសារ `.env` (សម្រាប់តេស្ត Local)
ចម្លងឯកសារ `.env.example` ទៅជា `.env` រួចបំពេញព័ត៌មាន៖
```env
TELEGRAM_BOT_TOKEN=7123456789:AAFx...
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-2.5-flash
```

---

## 💻 របៀបរត់តេស្តលើកុំព្យូទ័រ (Local Test Mode)

បើចង់តេស្ត Bot ភ្លាមៗដោយមិនទាន់បាច់ Deploy ទៅ Vercel៖
```bash
# ដំឡើង dependencies
pip install -r requirements.txt

# រត់ Bot តាម Long-Polling
python bot_polling.py
```
បន្ទាប់មកបើក Telegram របស់អ្នក រួចផ្ញើសារ `/start` ឬផ្ញើរូបភាពលំហាត់ទៅកាន់ Bot របស់អ្នកដើម្បីតេស្ត!

---

## 🚀 របៀបនាំចេញទៅកាន់ GitHub ដោយស្វ័យប្រវត្តិ (Export to GitHub)

អ្នកអាចជ្រើសរើសវិធីណាមួយខាងក្រោម៖

### វិធីទី ១៖ ចុចលើឯកសារ `.bat`
- គ្រាន់តែ **Double-Click លើឯកសារ `export_to_github.bat`**
- បិទភ្ជាប់ (Paste) URL នៃ GitHub Repository របស់អ្នក (ឧ. `https://github.com/Username/study-bot.git`)
- កម្មវិធីនឹងធ្វើការ Git Commit និង Push ទៅកាន់ GitHub ដោយស្វ័យប្រវត្តិ!

### វិធីទី ២៖ ប្រើប្រាស់ PowerShell
```powershell
.\export_to_github.ps1 -RepoUrl "https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git"
```

---

## ☁️ របៀបដាក់ដំណើរការលើ Vercel (Deploy to Vercel)

បន្ទាប់ពីបាន Push កូដទៅកាន់ GitHub រួចរាល់ហើយ៖

1. ចូលទៅកាន់ **[Vercel Dashboard](https://vercel.com/)** ហើយចុច **Add New... ➜ Project**
2. ជ្រើសរើស **GitHub Repository** របស់អ្នក រួចចុច **Import**
3. នៅក្នុងផ្ទាំង **Environment Variables** សូមបន្ថែម Key ខាងក្រោម៖
   - `TELEGRAM_BOT_TOKEN` : Token ដែលបានពី BotFather
   - `GEMINI_API_KEY` : API Key របស់ Google Gemini
   - `GEMINI_MODEL` : `gemini-2.5-flash`
4. ចុចប៊ូតុង **Deploy**!
5. រង់ចាំប្រហែល ១ នាទី Vercel នឹងផ្តល់ URL មួយឲ្យអ្នក (ឧ. `https://your-bot.vercel.app`)។

---

## 🔗 ភ្ជាប់ Telegram Bot ទៅកាន់ Vercel Webhook

បន្ទាប់ពី Deploy លើ Vercel ជោគជ័យ សូមរត់ពាក្យបញ្ជានេះនៅលើកុំព្យូទ័ររបស់អ្នកដើម្បីភ្ជាប់ Telegram ទៅកាន់ Vercel URL៖

```bash
python setup_webhook.py --set https://your-bot.vercel.app/api/webhook
```

✅ **រួចរាល់ជាស្ថាពរ!** ឥឡូវនេះ Telegram Bot របស់អ្នកនឹងដំណើរការលើ Vercel 24 ម៉ោងលើ 24 ម៉ោងជារៀងរាល់ថ្ងៃ ទោះបីជាអ្នកបិទកុំព្យូទ័រក៏ដោយ!

---

## 🕹️ បញ្ជាសំខាន់ៗក្នុង Telegram Bot

- `/start` : ចាប់ផ្តើម និងបង្ហាញព័ត៌មានទូទៅ
- `/subjects` : មើលបញ្ជីមុខវិជ្ជាទាំងអស់ដែល Bot អាចដោះស្រាយបាន
- `/help` : ការណែនាំអំពីរបៀបថតរូប និងសួរលំហាត់ឲ្យមានប្រសិទ្ធភាព
- `/about` : បង្ហាញព័ត៌មានអំពី Model Gemini និងស្ថានភាព Server
