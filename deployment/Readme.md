
# Devecho - AI-Powered Social Media Assistant

<img src='https://github.com/SHASWATSINGH3101/DevEcho/blob/main/assets/photo_5984682742954178568_y-modified.png' alt="Devecho" width="350">

## 📌 Overview
**Devecho** is an AI-powered social media assistant designed to generate engaging LinkedIn posts based on user-provided content. It automates data collection, retrieval, and post-generation using AI-driven techniques and multiple autonomous AI agents that collaborate to optimize the content. This combination of intelligent agents and advanced retrieval methods enables users to create high-quality content efficiently.

## 🚀 Features
- **Automated Data Collection**: Fetches relevant information from URLs, GitHub repositories, or topics using specialized AI agents.
- **Retrieval-Augmented Generation (RAG)**: Leverages AI agents to analyze retrieved data and generate contextually accurate responses.
- **Post Optimization**: Uses AI to fine-tune content for engagement, clarity, and tone.
- **LinkedIn Integration**: Allows users to post directly from the assistant.
- **Telegram Bot Support**: Provides a conversational interface for users to interact with the system.

---

## 📂 Project Structure
```bash
shaswatsingh3101-devecho/
├── deployment/
│   ├── knowledge_base.py        # Handles data collection from URLs, GitHub, and topics
│   ├── knowledge_retrieve.py    # Implements RAG pipeline and AI agent coordination for content retrieval
│   ├── linkedin.py              # LinkedIn API interaction (posting, user details)
│   ├── main.py                  # Orchestrates the end-to-end pipeline
│   ├── post_gen.py              # Generates social media posts with optimal engagement using AI agents
│   ├── telegram_bot.py          # Telegram bot interface for user interaction
│   ├── tone_config.py           # Manages different writing tones
│   ├── Procfile                 # Defines process to run the Telegram bot
│   ├── Readme.md                
│   └── requirements.txt         # List of dependencies
├── app/
│   ├── knowledge_base.py        # Handles data collection from URLs, GitHub, and topics
│   ├── knowledge_retrieve.py    # Implements RAG pipeline and AI agent coordination for content retrieval
│   ├── linkedin.py              # LinkedIn API interaction (posting, user details)
│   ├── main.py                  # Orchestrates the end-to-end pipeline
│   ├── post_gen.py              # Generates social media posts with optimal engagement using AI agents
│   ├── telegram_bot.py          # Telegram bot interface for user interaction
│   ├── tone_config.py           # Manages different writing tones
│   └── requirements.txt         # List of dependencies
├── assets/                      # Contains media assets for the project
└── Readme.md 
```

---

## 🔧 Installation
### **1️⃣ Clone the Repository**
```bash
git clone https://github.com/SHASWATSINGH3101/devecho.git
cd devecho
```

### **2️⃣ Install Dependencies**
```bash
pip install -r requirements.txt
```

### **3️⃣ Set Up API Keys**
- Add your **Tavily**, **FireCrawl**, **Groq**, and **LinkedIn API** keys to the environment:
```bash
export TAVILY_API_KEY="your_api_key"
export FIRECRAWL_API_KEY="your_api_key"
export GROQ_API_KEY="your_api_key"
export LINKEDIN_ACCESS_TOKEN="your_api_key"
export BOT_TOKEN="your_telegram_bot_token"
```
- Alternatively, modify the `.env` file and include the above keys.
- How to get the LINKEDIN_ACCESS_TOKEN:- [link](https://www.youtube.com/watch?v=vNPMvmF6ovA)
---

## 📦 Requirements
Ensure you have the following dependencies installed:
```bash
pip install requirements.txt
```

---

## 🛠️ Usage
### **Run the Main Pipeline**
```bash
python main.py
```

### **Run the Telegram Bot**
```bash
python telegram_bot.py
```

### **Using the Telegram Bot**
1. Start the bot with `/start`.
2. Use `/new` to begin post generation.
3. Follow the prompts to provide content.
4. Generate posts and upload them via `/upload_linkedin`.

### **LinkedIn Posting**
To post content directly to LinkedIn:
```bash
python linkedin.py
```

---

## 📜 Available Tones
Devecho supports multiple tones for post-generation:
- **Professional**: Clear and authoritative.
- **Casual**: Conversational and engaging.
- **Educational**: Explanatory and structured.
- **Persuasive**: Compelling with strong CTAs.

Change the tone using:
```bash
python tone_config.py professional
```
or through the Telegram bot with `/tone`.

---
## Deployment

### **1:- Define the Procfile**
Add a `Procfile` in the `app/` directory (already included):
```
worker: python telegram_bot.py
```

---
### **2:- Configure Service**
- Railway will automatically detect the `Procfile` and deploy the Telegram bot.
- Ensure that the port is correctly set if required for any other services.

---

### **3:- Deploy and Monitor**
- Click **Deploy** and monitor the logs to check for successful deployment.
- The Telegram bot should now be live and operational.

---

### ✅ **Next Steps**
- Verify the bot using `/start` on Telegram.
- Use `/new` to generate posts and `/upload_linkedin` to post them.


---
## 📌 Future Enhancements
- More advanced post structuring and style customization.
- Enhanced user feedback loop for refining generated content.
- Integration with additional social media platforms (e.g., Twitter, Facebook).

---

## 🤝 Contributing
We welcome contributions! Fork the repo, create a new branch, and submit a pull request.

---

## License
This project is licensed under the **MIT License**.

---

## Citing the Project

To cite this repository in publications:

```bibtex
@misc{GUARDIAN-EYE.AI,
  author = {SHASWATSINGH3101},
  title = {DevEcho},
  year = {2025},
  howpublished = {\url{https://github.com/SHASWATSINGH3101/DevEcho}},
  note = {GitHub repository},
}
```

---

## Contact
For inquiries or support, connect via:
- 💬 **Discord:** shaswat_singh

---
