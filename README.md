# ASTRO V2.0 - Avtonom Tizim Administratori

Astro ochiq kodli va to'liq terminalga markazlashtirilgan sun'iy intellekt agenti. V2.0 versiyada agent oddiy text interfeysidan chiqqan holda, mutlaq interaktiv Textual dashboard (Matrix foni bilan) ostida ishlaydigan va ChromaDB doimiy xotirasiga ega bo'lgan LangGraph mashinasiga o'tqazildi.

## O'zgarishlar (V1.0 -> V2.0)
- **Modul tuzilmasi**: Loyiha tartib bilan (core, ui, tools, agents, memory) maxsus bloklarga bo'lingan.
- **Mukammal U.I.**: Textual yordamida nafas oladigan orb va interaktiv yon panelli terminal yaratildi.
- **Xavfsiz Sudo**: Root paroli Fernet AES-128 binar maxfiyligida `.astro/` bazasida shifrlangan.
- **ChromaDB**: Suhbatlar konteksti kompyuter CPU sigida tezlashtirilgan holda lokal xotiraga yoziladi.
- **Mustaqillik (Zero-Permission)**: Astro barcha so'rovlarni ruxsat kutmasdan `bash_terminal` node'ida o'zi avtonom tarzda ishga tushiradi. Sudo kerak bo'lsa ochiq shifrdan olib avtomatik inyektsiya qiladi.
- **VoIP Integratsiya**: Asterisk AI ovoz monitoringi ekran yonidan dinamik print qilinadi.

## Interaktiv O'rnatish (Yangi xususiyat)

Astro o'rnatish jarayoni endi butunlay avtomatlashtirilgan va interaktiv CLI sehrgari yordamida ishlaydi.
O'rnatish skriptini ishga tushirganingizda:
1. **Asterisk So'rovi**: Skript sizdan Astro qo'ng'iroqlarni amalga oshirishi uchun Asterisk VoIP tizimi o'rnatilishini xohlaysizmi yo'qmi, deb so'raydi (y/n).
2. **Raqamlar Kiritish**: Agar siz Asterisk o'rnatishni xohlasangiz, qancha raqam o'rnatmoqchi ekanligingizni va har bir raqamni kiritishingiz so'raladi (Masalan, 3 ta raqam: 101, 102, 103).
3. **Avtomatik Konfiguratsiya**: Siz kiritgan raqamlar avtomatik ravishda Asterisk'ning `pjsip.conf` va `extensions.conf` fayllariga yoziladi. Parollar har bir raqam uchun odatiy "pass[raqam]" (masalan pass101) sifatida sozlanadi.
4. **CLI Animatsiyasi**: Orqa fonda tizim paketlarini yuklash, virtual muhit (venv) yaratish va python kutubxonalarini o'rnatish jarayonlari chiroyli CLI spinner (animatsiya) orqali ko'rsatiladi.

### O'rnatishni boshlash:
```bash
# Repozitoriyani klonlash (agar hali qilinmagan bo'lsa):
# git clone <repository_url>
# cd astro

# O'rnatish skriptini ishga tushirish:
bash install.sh
```

O'rnatish tugagandan so'ng ekranda yakuniy tasdiqlash xabari chiqadi va `/usr/local/bin/astro` orqali tizimga global bog'lanadi.

## Agentni chaqirish:
```bash
# Astro-ni istalgan terminaldan ishga tushirish:
astro run
```
