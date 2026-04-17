# ASTRO V2.0 - Avtonom Tizim Administratori

Astro ochiq kodli va to'liq terminalga markazlashtirilgan sun'iy intellekt agenti. V2.0 versiyada agent oddiy text interfeysidan chiqqan holda, mutlaq interaktiv Textual dashboard (Matrix foni bilan) ostida ishlaydigan va ChromaDB doimiy xotirasiga ega bo'lgan LangGraph mashinasiga o'tqazildi.

## O'zgarishlar (V1.0 -> V2.0)
- **Modul tuzilmasi**: Loyiha tartib bilan (core, ui, tools, agents, memory) maxsus bloklarga bo'lingan.
- **Mukammal U.I.**: Textual yordamida nafas oladigan orb va interaktiv yon panelli terminal yaratildi.
- **Xavfsiz Sudo**: Root paroli Fernet AES-128 binar maxfiyligida `.astro/` bazasida shifrlangan.
- **ChromaDB**: Suhbatlar konteksti kompyuter CPU sigida tezlashtirilgan holda lokal xotiraga yoziladi.
- **Mustaqillik (Zero-Permission)**: Astro barcha so'rovlarni ruxsat kutmasdan `bash_terminal` node'ida o'zi avtonom tarzda ishga tushiradi. Sudo kerak bo'lsa ochiq shifrdan olib avtomatik inyektsiya qiladi.
- **VoIP Integratsiya**: Asterisk AI ovoz monitoringi ekran yonidan dinamik print qilinadi.

## Ishga tushirish:
```bash
# Avval dependencies larni oling:
bash install.sh
textual
langgraph
chromadb

# Agentni chaqirish:
astro run
```
