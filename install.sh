#!/bin/bash
echo "ASTRO V2.0 o'rnatilmoqda..."

# Veng
python3 -m venv venv
source venv/bin/activate

# Yangi Paketlar
pip install textual langgraph langchain-community langchain-openai chromadb sentence-transformers duckduckgo-search cryptography requests

# Executable qilib o'tqizish
chmod +x astro.py
sudo cp astro.py /usr/local/bin/astro

echo "✅ Tayyor! 'astro run' buyrug'ini tering."
