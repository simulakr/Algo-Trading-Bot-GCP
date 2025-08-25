# 1) Sistemi Güncelle
sudo apt update && sudo apt upgrade -y

# 2) Temel Bağımlılıklar
sudo apt install -y python3-pip python3-venv git tmux

# 3) Projeyi Klonla
git clone https://github.com/simulakr/Algo-Trading-Bot-GCP.git
cd Algo-Trading-Bot-GCP

# 4) Sanal Ortam Oluştur ve Aktive Et
python3 -m venv venv
source venv/bin/activate

# 5) Gerekli Kütüphaneleri Yükle
pip install -r requirements.txt

# 6) Environment Dosyasını Oluştur
nano .env

# .env İçeriği:
BYBIT_API_KEY="your_actual_api_key_here"
BYBIT_API_SECRET="your_actual_secret_here"

# 7) Botu Test Et (ilk çalıştırma)
python main.py

# 8) TMUX ile Sürekli Çalıştır
tmux new -s tradingbot
source venv/bin/activate
python main.py

# TMUX'dan çıkmak için: Ctrl+B, ardından D
# Tekrar girmek için: tmux attach -t tradingbot

# 9) (Opsiyonel) SystemD Service Oluştur
sudo nano /etc/systemd/system/tradingbot.service

# tradingbot.service İçeriği:
[Unit]
Description=Bybit Trading Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Algo-Trading-Bot-GCP
ExecStart=/home/ubuntu/Algo-Trading-Bot-GCP/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# 10) SystemD Service'ı Başlat
sudo systemctl daemon-reload
sudo systemctl start tradingbot
sudo systemctl enable tradingbot

# 11) Logları Kontrol Et
sudo journalctl -u tradingbot -f

# 12) .env dosyasını koruma
chmod 600 .env
