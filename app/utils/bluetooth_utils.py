# app/utils/bluetooth_utils.py
import re
import unicodedata

def normalize(text):
    text = unicodedata.normalize('NFKD', text)  # Unicode normalize
    text = text.encode('ascii', 'ignore').decode('utf-8')  # Aksanları kaldır
    text = text.lower().strip()  # Küçük harf, baş-son boşluk temizliği
    text = re.sub(r'[^\w\s]', '', text)  # Noktalama işaretlerini kaldır
    return text
